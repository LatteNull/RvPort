"""Bounded A4 mutex/RAII facts, owner state machine, and proof composition."""

from collections import defaultdict
from copy import deepcopy
from itertools import combinations

from .contracts import AnalysisError, identity
from .cpp_raii_contracts import cpp_raii_document, dependency, diagnostic
from .cpp_raii_profiles import normalize_synchronization_calls


SOURCE_OPERATIONS = {
    "cpp-raii-owner-construct": "construct",
    "cpp-raii-owner-destruct": "destruct",
    "cpp-raii-owner-move": "move",
    "cpp-raii-owner-lock": "lock",
    "cpp-raii-owner-unlock": "unlock",
    "cpp-raii-owner-owns-lock": "owns-lock",
}
UNSUPPORTED_MARKERS = {
    "adopt_lock": "unsupported-adopt-lock",
    "try_to_lock": "unsupported-try-lock",
    "try_lock": "unsupported-try-lock",
    "release": "unsupported-owner-release",
    "swap": "unsupported-owner-swap",
    "timed_mutex": "unsupported-timed-mutex",
    "recursive_mutex": "unsupported-recursive-mutex",
}
PROVENANCE_OPCODES = {
    "alloca", "load", "store", "bitcast", "addrspacecast", "phi", "select",
    "getelementptr",
}


def _anchor(source):
    source = source or {}
    chain = source.get("inline_chain") or []
    location = source.get("expansion") or (chain[-1] if chain else {})
    return (location.get("file"), location.get("line"), location.get("column"))


def _source_order(relation):
    anchor = _anchor(relation.get("source"))
    return (anchor[0] or "", anchor[1] or 2**31, anchor[2] or 2**31, relation["id"])


def _gap(code, detail, detail_en, *, source=None):
    return diagnostic(
        code, detail, detail_en,
        suggestion="补齐精确 source/IR/profile、对象、路径和线程证据后重试",
        suggestion_en="Retry after completing exact source/IR/profile, object, path, and thread evidence",
        source=source,
    )


def trace_mutex_provenance(seeds, values, *, limit=64):
    """Return a bounded may-root set; ambiguity is never promoted to must identity."""
    registry = {item["id"]: item for item in values}
    pending, visited, roots, opposed = list(sorted(set(seeds))), set(), set(), set()
    while pending:
        current = pending.pop(0)
        if current in visited:
            continue
        if len(visited) >= limit:
            opposed.add("provenance-budget-exhausted")
            break
        visited.add(current)
        node = registry.get(current)
        if node is None:
            roots.add(current)
            continue
        opcode = node.get("details", {}).get("opcode") or node.get("opcode")
        if opcode not in PROVENANCE_OPCODES:
            opposed.add("unsupported-provenance-operation")
            continue
        if opcode == "alloca":
            roots.add(current)
        else:
            pending.extend(item for item in node.get("operands", []) if item not in visited)
    status = "exact" if len(roots) == 1 and not opposed else "candidate" if roots else "unresolved"
    return {"status": status, "roots": sorted(roots), "evidence": sorted(visited),
            "opposed": sorted(opposed)}


def module_synchronization_calls(modules, profile=None):
    """Extract raw calls and adopt only exact profile signatures for C++."""
    raw = []
    signatures = {item["symbol"]: item for item in (profile or {}).get("wrapper_signatures", [])}
    for artifact, module in sorted(modules.items()):
        if profile and (module.get("target") != profile["target"] or
                        module.get("layout") != profile["data_layout"]):
            continue
        values = module.get("values", [])
        for call in module.get("calls", []):
            symbol = call.get("target") or call.get("symbol")
            signature = signatures.get(symbol)
            if not signature and symbol not in {"pthread_mutex_lock", "pthread_mutex_unlock"}:
                continue
            convention = call.get("calling_convention")
            convention = "ccc" if convention in (None, 0, "ccc") else f"llvm:{convention}"
            seeds = list(call.get("arguments", []))
            provenance = trace_mutex_provenance(seeds[:1], values)
            raw.append({
                "id": f"{artifact}:{call['id']}", "symbol": symbol,
                "calling_convention": convention,
                "signature_digest": signature and signature["digest"],
                "evidence": [f"{artifact}:{call['id']}"],
                "source": call.get("source", {}), "arguments": seeds,
                "normal": call.get("normal"), "unwind": call.get("unwind"),
                "mutex_provenance": provenance,
            })
    if profile is None:
        normalized = [{
            "call_id": item["id"],
            "role": "mutex-lock" if item["symbol"] == "pthread_mutex_lock" else "mutex-unlock",
            "profile_id": None, "exception_behavior": "nothrow", "evidence": item["evidence"],
        } for item in raw]
        return raw, normalized, []
    normalized, diagnostics = normalize_synchronization_calls(raw, profile)
    return raw, normalized, diagnostics


def _mutex(object_id, source_nodes=(), ir_nodes=(), *, resolution="exact", kind="plain"):
    key = identity({"namespace": "a4-mutex", "object": object_id})
    return {"id": key, "object_id": object_id, "kind": kind, "resolution": resolution,
            "source_nodes": sorted(set(source_nodes)), "ir_nodes": sorted(set(ir_nodes))}


def _owner(object_id, owner_kind, mutex_ids=(), source_nodes=(), ir_nodes=()):
    return {
        "id": identity({"namespace": "a4-owner", "object": object_id}),
        "object_id": object_id, "owner_kind": owner_kind,
        "mutex_ids": sorted(set(mutex_ids)), "state": "uninitialized", "thread_id": None,
        "guard": None, "source_nodes": sorted(set(source_nodes)), "ir_nodes": sorted(set(ir_nodes)),
    }


def _relation_owner_kind(relation):
    reason = relation.get("reason") or ""
    for token, kind in (("lock-guard", "lock-guard"), ("unique-lock", "unique-lock"),
                        ("scoped-lock", "scoped-lock"), ("pthread", "pthread-direct")):
        if token in reason:
            return kind
    return "unknown"


def build_local_facts(scope_id, member, source_facts, profile=None, *, modules=None):
    """Build an additive local sidecar; source-only evidence remains partial."""
    language, standard, tu = member["language"], member["standard"], member["physical_tu_id"]
    dependencies = []
    if source_facts is not None:
        dependencies.append(dependency("SourceSemanticFacts", tu, source_facts))
    if profile is not None:
        dependencies.append(dependency("CppRaiiSynchronizationProfile", profile["profile_id"], profile))
    relations = sorted((source_facts or {}).get("relations", []), key=_source_order)
    raw, normalized, frontier = module_synchronization_calls(modules or {}, profile if language == "c++" else None)
    raw_by_id = {item["id"]: item for item in raw}
    roles_by_anchor = defaultdict(list)
    for item in normalized:
        roles_by_anchor[_anchor(raw_by_id[item["call_id"]].get("source"))].append(item)

    mutexes, owners, operations = {}, {}, []
    owner_mutexes = defaultdict(set)
    for relation in relations:
        kind = relation["kind"]
        if kind in {"cpp-raii-mutex-object", "pthread-mutex-object"}:
            object_id = relation.get("to") or relation["from"]
            mutexes.setdefault(object_id, _mutex(object_id, [relation["from"]], resolution="candidate"))
        elif kind == "cpp-raii-owner-object":
            object_id = relation.get("to") or relation["from"]
            owners.setdefault(object_id, _owner(object_id, _relation_owner_kind(relation), (), [relation["from"]]))
        elif kind == "cpp-raii-mutex-argument" and relation.get("to"):
            owner_mutexes[relation["from"]].add(relation["to"])

    if language == "c":
        for item in raw:
            provenance = item["mutex_provenance"]
            object_id = provenance["roots"][0] if provenance["status"] == "exact" else f"ir-mutex:{item['id']}"
            mutex = mutexes.setdefault(object_id, _mutex(
                object_id, ir_nodes=item["evidence"], resolution=provenance["status"]))
            owner_id = f"pthread-owner:{object_id}"
            owner = owners.setdefault(owner_id, _owner(owner_id, "pthread-direct", [mutex["id"]],
                                                        ir_nodes=item["evidence"]))
            role = "lock" if item["symbol"] == "pthread_mutex_lock" else "unlock"
            operations.append({
                "id": identity({"tu": tu, "call": item["id"], "operation": role}),
                "operation": role, "owner_id": owner["id"], "mutex_ids": [mutex["id"]],
                "outcome": "success" if provenance["status"] == "exact" else "unknown",
                "guard": item.get("normal"), "thread_id": None, "source_nodes": [],
                "ir_nodes": item["evidence"], "sequence": len(operations),
            })
    else:
        constructor_mutexes = {}
        for relation in relations:
            if relation["kind"] == "cpp-raii-mutex-argument" and relation.get("to"):
                constructor_mutexes.setdefault(relation["from"], set()).add(relation["to"])
        for relation in relations:
            operation = SOURCE_OPERATIONS.get(relation["kind"])
            if operation is None:
                reason = relation.get("reason") or ""
                for marker, code in UNSUPPORTED_MARKERS.items():
                    if marker in reason:
                        frontier.append(_gap(code, "该 RAII mutex 形状不在首版支持范围内",
                                             "This RAII mutex shape is outside the first supported model",
                                             source={"relation_id": relation["id"]}))
                continue
            owner_object = relation.get("to") or relation["from"]
            owner = owners.get(owner_object)
            if owner is None:
                owner = _owner(owner_object, _relation_owner_kind(relation), (), [relation["from"]])
                owners[owner_object] = owner
            object_ids = set(constructor_mutexes.get(relation["from"], set()))
            object_ids.update(owner_mutexes.get(relation["from"], set()))
            if not object_ids:
                object_ids.update(owner.get("object_mutex_ids", []))
            mutex_ids = list(owner["mutex_ids"]) if not object_ids else []
            for object_id in sorted(object_ids):
                mutex = mutexes.setdefault(object_id, _mutex(object_id, [relation["from"]], resolution="candidate"))
                mutex_ids.append(mutex["id"])
            matches = roles_by_anchor.get(_anchor(relation.get("source")), [])
            expected = ({"construct": {"owner-construct", "mutex-lock", "scoped-lock"},
                         "destruct": {"owner-destruct", "mutex-unlock"},
                         "move": {"owner-move"}, "lock": {"owner-lock", "mutex-lock"},
                         "unlock": {"owner-unlock", "mutex-unlock"},
                         "owns-lock": {"owner-owns-lock"}})[operation]
            matched = [item for item in matches if item["role"] in expected]
            exact = relation.get("status") != "unknown" and len(matched) == 1 and bool(mutex_ids)
            ir_nodes = matched[0]["evidence"] if len(matched) == 1 else []
            for mutex in mutexes.values():
                if mutex["id"] in mutex_ids:
                    mutex["source_nodes"] = sorted(set([*mutex["source_nodes"], relation["from"]]))
                    mutex["ir_nodes"] = sorted(set([*mutex["ir_nodes"], *ir_nodes]))
                    mutex["resolution"] = "exact" if exact else mutex["resolution"]
            owner["mutex_ids"] = sorted(set([*owner["mutex_ids"], *mutex_ids]))
            owner["ir_nodes"] = sorted(set([*owner["ir_nodes"], *ir_nodes]))
            op = {
                "id": identity({"tu": tu, "relation": relation["id"], "ir": ir_nodes}),
                "operation": operation, "owner_id": owner["id"], "mutex_ids": mutex_ids,
                "outcome": "success" if exact else "unknown", "guard": relation.get("reason"),
                "thread_id": None, "source_nodes": [relation["from"]], "ir_nodes": ir_nodes,
                "sequence": len(operations), "owner_kind": owner["owner_kind"],
            }
            operations.append(op)
            if not exact:
                frontier.append(_gap(
                    "raii-evidence-incomplete", "RAII 操作缺少精确 AST、profile 与 IR wrapper 证据",
                    "The RAII operation lacks exact AST, profile, and IR wrapper evidence",
                    source={"operation_id": op["id"], "physical_tu_id": tu}))

    if source_facts is None:
        frontier.append(_gap("source-evidence-missing", "源码语义事实缺失",
                             "Source semantic facts are missing", source={"physical_tu_id": tu}))
    if language == "c++" and profile is None:
        frontier.append(_gap("library-profile-unsupported", "缺少 C++ RAII 同步 profile",
                             "The C++ RAII synchronization profile is missing",
                             source={"physical_tu_id": tu}))
    if language == "c++" and profile is not None and profile["status"] != "verified":
        frontier.append(_gap("library-profile-unsupported", "C++ RAII 同步 profile 未经验证",
                             "The C++ RAII synchronization profile is unverified",
                             source={"profile_id": profile["profile_id"]}))
    frontier = sorted({identity(item): item for item in frontier}.values(), key=lambda item: (item["code"], identity(item)))
    status = "complete" if source_facts and source_facts.get("status") == "complete" and not frontier else "partial"
    return cpp_raii_document(
        "CppRaiiLocalFacts", scope_id=scope_id, physical_tu_id=tu,
        profile_id=member["profile_id"], language=language, standard=standard, status=status,
        synchronization_profile_id=profile["profile_id"] if profile else None,
        mutexes=sorted(mutexes.values(), key=lambda item: item["id"]),
        owners=sorted(owners.values(), key=lambda item: item["id"]),
        operations=sorted(operations, key=lambda item: item["id"]), accesses=[],
        dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
        diagnostics=frontier, frontier=frontier, semantic_digest=None,
    )


def _state_transition(state, operation, owner_kind):
    kind = operation["operation"]
    if kind == "construct":
        if owner_kind == "unique-lock" and "defer" in (operation.get("guard") or ""):
            return "deferred"
        return "owns" if state in {"uninitialized", "released"} else "unknown"
    if kind == "lock":
        return "owns" if state in {"deferred", "released", "uninitialized"} else "unknown"
    if kind == "unlock":
        return "released" if state == "owns" else "unknown"
    if kind == "destruct":
        return "released" if state in {"owns", "deferred", "released"} else "unknown"
    if kind == "move":
        return "owns" if state == "owns" else "unknown"
    return state if kind == "owns-lock" else "unknown"


def _thread_for_operation(operation, thread_graph, lifecycle_graph):
    markers = set(operation["source_nodes"] + operation["ir_nodes"])
    candidates = set()
    for graph in (thread_graph or {}, lifecycle_graph or {}):
        for item in [*graph.get("instances", []), *graph.get("contexts", [])]:
            evidence = set(item.get("evidence", [])) | set(item.get("source_nodes", [])) | set(item.get("ir_nodes", []))
            if markers & evidence:
                candidates.add(item["id"])
    return next(iter(candidates)) if len(candidates) == 1 else operation.get("thread_id")


def _mhp_evidence(left, right, thread_graph, lifecycle_graph):
    """Return explicit may-parallel evidence for two concrete thread instances."""
    if not left or not right or left == right:
        return []
    pair = {left, right}
    evidence = []
    for item in (thread_graph or {}).get("mhp", []):
        if item.get("relation") == "may_parallel" and {item.get("left"), item.get("right")} == pair:
            evidence.extend([item.get("id"), *(ref.get("id") for ref in item.get("proof", []))])
    for item in (lifecycle_graph or {}).get("relations", []):
        relation = item.get("relation")
        if relation in {"may-parallel", "may_parallel"} and {item.get("from"), item.get("to")} == pair:
            evidence.append(item.get("id"))
    return sorted({item for item in evidence if item})


def _conflicting_access_evidence(left, right, accesses):
    """Return evidence only for a same-object pair with at least one write."""
    result = []
    for first_id in left.get("access_ids", []):
        first = accesses.get(first_id)
        if first is None:
            continue
        for second_id in right.get("access_ids", []):
            second = accesses.get(second_id)
            if second is None or first.get("object_id") != second.get("object_id"):
                continue
            kinds = {first.get("access_kind"), second.get("access_kind")}
            if "write" in kinds:
                result.extend([first_id, second_id, *first.get("evidence", []),
                               *second.get("evidence", [])])
    return sorted(set(result))


def build_synchronization_graph(request, local_facts, profiles, *, thread_graph=None,
                                lifecycle_graph=None, degraded_report=None, publication_graph=None):
    """Run the bounded owner lattice and publish only closed exact mutex proofs."""
    budgets = request["budgets"]
    mutexes = {item["id"]: deepcopy(item) for facts in local_facts for item in facts["mutexes"]}
    owners = {item["id"]: deepcopy(item) for facts in local_facts for item in facts["owners"]}
    operations = sorted((deepcopy(item) for facts in local_facts for item in facts["operations"]),
                        key=lambda item: (item.get("sequence", 0), item["id"]))
    accesses = {item["id"]: deepcopy(item) for facts in local_facts for item in facts["accesses"]}
    frontier = [deepcopy(item) for facts in local_facts for item in facts["frontier"]]
    gaps, regions, proofs = [], [], []
    states = {key: value["state"] for key, value in owners.items()}
    open_regions = {}
    for operation in operations[:budgets["transitions"]]:
        owner_id = operation["owner_id"]
        owner = owners.get(owner_id)
        if owner is None:
            continue
        operation["thread_id"] = _thread_for_operation(operation, thread_graph, lifecycle_graph)
        before = states[owner_id]
        after = _state_transition(before, operation, owner["owner_kind"])
        if operation["outcome"] != "success" or any(mutexes[key]["resolution"] != "exact" for key in operation["mutex_ids"]):
            after = "unknown"
        if operation["operation"] in {"construct", "lock"} and after == "owns":
            open_regions[owner_id] = operation
        if operation["operation"] in {"unlock", "destruct"} and before == "owns" and after == "released":
            acquire = open_regions.pop(owner_id, None)
            if acquire is not None and operation["thread_id"] is not None:
                region = {
                    "id": identity({"owner": owner_id, "acquire": acquire["id"], "release": operation["id"]}),
                    "owner_id": owner_id, "mutex_ids": sorted(set(operation["mutex_ids"] or acquire["mutex_ids"])),
                    "thread_id": operation["thread_id"], "acquire_id": acquire["id"],
                    "release_id": operation["id"],
                    "access_ids": sorted(item["id"] for item in accesses.values()
                                         if item.get("owner_id") == owner_id and
                                         item.get("thread_id") in {None, operation["thread_id"]}),
                    "guard": operation["guard"],
                    "status": "complete", "evidence": sorted(set([
                        *acquire["source_nodes"], *acquire["ir_nodes"],
                        *operation["source_nodes"], *operation["ir_nodes"],
                    ])),
                }
                regions.append(region)
        states[owner_id] = after
        owner["state"] = after
        owner["thread_id"] = operation["thread_id"]
    if len(operations) > budgets["transitions"]:
        frontier.append(_gap("transitions-budget-exhausted", "状态转换预算已耗尽",
                             "The state-transition budget is exhausted"))
    for owner_id, acquire in open_regions.items():
        gaps.append(_gap("unclosed-held-region", "持锁区间在某条路径上没有闭合",
                         "A held region is not closed on every path",
                         source={"owner_id": owner_id, "acquire_id": acquire["id"]}))
    by_mutex = defaultdict(list)
    for region in regions[:budgets["held_regions"]]:
        for mutex_id in region["mutex_ids"]:
            by_mutex[mutex_id].append(region)
    if len(regions) > budgets["held_regions"]:
        regions = regions[:budgets["held_regions"]]
        frontier.append(_gap("held-regions-budget-exhausted", "持锁区间预算已耗尽",
                             "The held-region budget is exhausted"))
    for mutex_id, values in sorted(by_mutex.items()):
        for left, right in combinations(sorted(values, key=lambda item: item["id"]), 2):
            mhp = _mhp_evidence(left["thread_id"], right["thread_id"],
                                thread_graph, lifecycle_graph)
            conflicts = _conflicting_access_evidence(left, right, accesses)
            if not mhp or not conflicts:
                continue
            selected = [left, right]
            evidence = sorted(set([*mhp, *conflicts,
                                   *(value for item in selected for value in item["evidence"])]))
            for proof_kind in ("mutual-exclusion", "mutex-sync-candidate"):
                proofs.append({
                    "id": identity({"kind": proof_kind, "mutex": mutex_id,
                                    "regions": [item["id"] for item in selected]}),
                    "proof_kind": proof_kind, "mutex_id": mutex_id,
                    "region_ids": [item["id"] for item in selected],
                    "thread_ids": sorted({left["thread_id"], right["thread_id"]}),
                    "guard": None, "status": "complete", "evidence": evidence,
                    "limitations": ["bounded-same-plain-mutex", "not-general-happens-before"],
                })
    if not proofs and (mutexes or owners):
        gaps.append(_gap("mutex-proof-incomplete", "未形成跨线程闭合的同 mutex 证明链",
                         "No closed cross-thread same-mutex proof chain was established"))
    gaps = sorted({identity(item): item for item in gaps}.values(), key=lambda item: (item["code"], identity(item)))
    frontier = sorted({identity(item): item for item in frontier}.values(), key=lambda item: (item["code"], identity(item)))
    status = "partial" if gaps or frontier or any(item["status"] != "complete" for item in local_facts) else "complete"
    deps = [dependency("CppRaiiSynchronizationRequest", request["scope_id"], request)]
    deps.extend(dependency("CppRaiiLocalFacts", item["physical_tu_id"], item) for item in local_facts)
    for kind, value in (("ThreadContextGraph", thread_graph), ("CppThreadLifecycleGraph", lifecycle_graph),
                        ("DegradedSourceReport", degraded_report),
                        ("SinglePublicationProtocolGraph", publication_graph)):
        if value:
            deps.append(dependency(kind, value.get("scope_id", kind), value))
    counts = {"mutexes": len(mutexes), "owners": len(owners), "operations": len(operations),
              "accesses": len(accesses), "held_regions": len(regions),
              "proofs": len(proofs), "gaps": len(gaps)}
    return cpp_raii_document(
        "CppRaiiSynchronizationGraph", scope_id=request["scope_id"], request_hash=identity(request),
        status=status,
        profiles=sorted((dependency("CppRaiiSynchronizationProfile", item["profile_id"], item)
                         for item in profiles), key=lambda item: (item["kind"], item["id"])),
        mutexes=sorted(mutexes.values(), key=lambda item: item["id"]),
        owners=sorted(owners.values(), key=lambda item: item["id"]),
        operations=sorted(operations, key=lambda item: item["id"]),
        accesses=sorted(accesses.values(), key=lambda item: item["id"]),
        held_regions=sorted(regions, key=lambda item: item["id"]),
        proofs=sorted(proofs, key=lambda item: item["id"]), gaps=gaps, counts=counts,
        dependencies=sorted(deps, key=lambda item: (item["kind"], item["id"])),
        diagnostics=frontier, frontier=frontier, semantic_digest=None,
    )


def build_synchronization_report(request, graph, profiles, *, hits=0, misses=0):
    graph_ref = dependency("CppRaiiSynchronizationGraph", graph["scope_id"], graph)
    profiles_ref = sorted((dependency("CppRaiiSynchronizationProfile", item["profile_id"], item)
                           for item in profiles), key=lambda item: (item["kind"], item["id"]))
    diagnostics = [*graph["gaps"], *graph["diagnostics"]]
    if graph["proofs"]:
        diagnostics.append(diagnostic(
            "bounded-mutex-proof", "已在受限模型内建立同 mutex 证明；未建立全程序安全",
            "A same-mutex proof was established in the bounded model; whole-program safety was not established",
            limitation="证明不包含通用 happens-before、原子 reads-from、fence 或 release sequence",
            limitation_en="The proof excludes general happens-before, atomic reads-from, fences, and release sequences",
            suggestion="结合候选相关完整性和未建模边界解释该证明",
            suggestion_en="Interpret this proof together with candidate completeness and unmodeled boundaries"))
    return cpp_raii_document(
        "CppRaiiSynchronizationReport", scope_id=request["scope_id"], request_hash=identity(request),
        status=graph["status"], exit_code=2 if graph["status"] == "partial" else 0,
        safety="not_established", findings=None, graph=graph_ref, profiles=profiles_ref,
        counts=deepcopy(graph["counts"]),
        dependencies=sorted([graph_ref, dependency("CppRaiiSynchronizationRequest", request["scope_id"], request)],
                            key=lambda item: (item["kind"], item["id"])),
        diagnostics=diagnostics, frontier=[*graph["frontier"], *graph["gaps"]],
        cache={"hits": hits, "misses": misses}, semantic_digest=None,
    )


def failed_synchronization_report(code, detail, detail_en=None):
    item = _gap(code, f"C++ RAII 同步分析失败：{detail}",
                f"C++ RAII synchronization analysis failed: {detail_en or detail}")
    return cpp_raii_document(
        "CppRaiiSynchronizationReport", scope_id=None, request_hash=None, status="failed",
        exit_code=1, safety="not_established", findings=None, graph=None, profiles=[], counts={},
        dependencies=[], diagnostics=[item], frontier=[item], cache={"hits": 0, "misses": 0},
        semantic_digest=None,
    )
