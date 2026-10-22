"""Finite object-provenance lattice and conservative A5 composition."""

from copy import deepcopy

from .contracts import AnalysisError, identity
from .provenance_contracts import dependency, diagnostic, provenance_document


def storage_instance(kind, source_id, *, artifact_key=None, function_id=None,
                     invocation_id=None, allocation="single", lifetime="live", address_space=0):
    value = {
        "id": "", "kind": kind, "artifact_key": artifact_key, "source_id": source_id,
        "function_id": function_id, "invocation_id": invocation_id,
        "allocation": allocation, "lifetime": lifetime, "address_space": address_space,
    }
    value["id"] = identity({key: item for key, item in value.items() if key != "id"})
    return value


def object_instance(storage, path=(), *, offset=0, size=None):
    value = {"storage": deepcopy(storage), "path": deepcopy(list(path)),
             "byte_range": {"offset": offset, "size": size}}
    value["id"] = identity(value)
    return {"id": value.pop("id"), **value}


def candidate(value, *, guards=(), proof=(), opposed=(), dependencies=()):
    return {"object": deepcopy(value), "guards": sorted(set(guards)), "proof": sorted(set(proof)),
            "opposed": sorted(set(opposed)),
            "dependencies": sorted(deepcopy(list(dependencies)), key=lambda item: (item["kind"], item["id"]))}


def bottom():
    """Internal no-information-yet state. It is never serialized."""
    return {"state": "bottom", "candidates": [], "reason": None}


def must(value, **evidence):
    return {"state": "must", "candidates": [candidate(value, **evidence)], "reason": None}


def may(values, **evidence):
    unique = {item["id"]: item for item in values}
    if not unique:
        return unknown("empty-candidate-set")
    candidates = [candidate(unique[key], **evidence) for key in sorted(unique)]
    if len(candidates) == 1 and not candidates[0]["opposed"]:
        return {"state": "must", "candidates": candidates, "reason": None}
    return {"state": "may", "candidates": candidates, "reason": None}


def unknown(reason, candidates=()):
    return {"state": "unknown", "candidates": sorted(deepcopy(list(candidates)),
                                                       key=lambda item: item["object"]["id"]),
            "reason": str(reason)}


def join(left, right, *, candidate_limit=64, guard_limit=128):
    if left["state"] == "bottom":
        return deepcopy(right)
    if right["state"] == "bottom":
        return deepcopy(left)
    if left["state"] == "unknown" or right["state"] == "unknown":
        return unknown("joined-with-unknown", [*left["candidates"], *right["candidates"]])
    merged = {}
    for item in [*left["candidates"], *right["candidates"]]:
        key = item["object"]["id"]
        if key not in merged:
            merged[key] = deepcopy(item)
        else:
            for field in ("guards", "proof", "opposed"):
                merged[key][field] = sorted(set(merged[key][field]) | set(item[field]))
            deps = {(dep["kind"], dep["id"]): dep for dep in [*merged[key]["dependencies"], *item["dependencies"]]}
            merged[key]["dependencies"] = [deps[key] for key in sorted(deps)]
    candidates = [merged[key] for key in sorted(merged)]
    if len(candidates) > candidate_limit:
        return unknown("candidate-budget-exhausted", candidates[:candidate_limit])
    if sum(len(item["guards"]) for item in candidates) > guard_limit:
        return unknown("guard-budget-exhausted", candidates)
    if len(candidates) == 1 and not candidates[0]["opposed"]:
        return {"state": "must", "candidates": candidates, "reason": None}
    return {"state": "may", "candidates": candidates, "reason": None}


def byte_relation(left, right):
    """Return same/disjoint/overlap/unknown; union path members never become disjoint."""
    if left["storage"]["id"] != right["storage"]["id"]:
        return "disjoint"
    left_union = {item["union_group"] for item in left["path"] if item.get("union_group")}
    right_union = {item["union_group"] for item in right["path"] if item.get("union_group")}
    if left_union & right_union:
        return "overlap"
    a, b = left["byte_range"], right["byte_range"]
    if None in (a["offset"], a["size"], b["offset"], b["size"]):
        return "unknown"
    if a == b:
        return "same"
    if a["offset"] + a["size"] <= b["offset"] or b["offset"] + b["size"] <= a["offset"]:
        return "disjoint"
    return "overlap"


def propagate_load(stores, *, exact_range=True, no_clobber=True, captured=False,
                   lifetime="live", atomic=False, volatile=False, load_hops=1, hop_limit=16):
    reasons = []
    if len(stores) != 1:
        reasons.append("non-unique-reaching-store")
    if not exact_range:
        reasons.append("non-exact-range")
    if not no_clobber:
        reasons.append("memory-clobber")
    if captured:
        reasons.append("storage-escaped")
    if lifetime != "live":
        reasons.append("lifetime-not-live")
    if atomic or volatile:
        reasons.append("atomic-or-volatile-pointer-load")
    if load_hops > hop_limit:
        reasons.append("load-hop-budget-exhausted")
    if reasons:
        candidates = [] if not stores else [candidate(item) for item in stores[:1]]
        return unknown(";".join(reasons), candidates)
    return must(stores[0], proof=("unique-dominating-store", "memoryssa-no-clobber", "not-captured"))


def specialize(domain, bindings, *, expired_returns=()):
    """Substitute parameter/receiver storage identities at a verified direct call."""
    if domain["state"] == "unknown":
        return deepcopy(domain)
    result = bottom()
    for item in domain["candidates"]:
        source = item["object"]["storage"]["source_id"]
        if source in expired_returns:
            return unknown("expired-local-return", domain["candidates"])
        replacement = bindings.get(source)
        original = item["object"]
        if replacement is None:
            target = deepcopy(original)
        else:
            left, right = replacement["byte_range"], original["byte_range"]
            offset = (left["offset"] + right["offset"]
                      if left["offset"] is not None and right["offset"] is not None else None)
            size = right["size"] if right["size"] is not None else left["size"]
            target = object_instance(replacement["storage"],
                                     [*replacement["path"], *original["path"]],
                                     offset=offset, size=size)
        current_item = {**deepcopy(item), "object": target}
        current = {"state": "may" if current_item["opposed"] else "must",
                   "candidates": [current_item], "reason": None}
        result = join(result, current)
    return result


def exact_adapter(name, domain, *, consumer):
    if domain["state"] != "must" or len(domain["candidates"]) != 1 or domain["candidates"][0]["opposed"]:
        return {"id": identity({"name": name, "consumer": consumer}), "consumer": consumer,
                "status": "ambiguous", "object_id": None,
                "reason": "mutex-provenance-ambiguous" if consumer == "A4" else "object-provenance-ambiguous"}
    return {"id": identity({"name": name, "consumer": consumer}), "consumer": consumer,
            "status": "exact", "object_id": domain["candidates"][0]["object"]["id"], "reason": None}


def compose_evidence(source_facts, llvm_facts, budgets, *, scope_id=None,
                     entity_indexes=(), source_bindings=(), effect_summaries=()):
    """Align source paths and compose only verified direct-call candidates."""
    domain_map, relations, frontier = {}, [], []
    by_operand, formals, returns = {}, {}, {}
    for facts in llvm_facts:
        tu = facts["physical_tu_id"]
        for value in facts["values"]:
            key = f"{tu}:{value['id']}"
            domain_map[key] = deepcopy(value["domain"])
            by_operand[(tu, value.get("function_id"), value.get("ir_name"))] = (key, value["domain"])
            if value["opcode"] == "argument":
                formals.setdefault((value.get("function_id"), value.get("argument_index")), []).append(
                    (tu, value["domain"]))
        for returned in facts.get("returns", []):
            item = by_operand.get((tu, returned["function_id"], returned["value"]))
            if item:
                returns.setdefault(returned["function_id"], []).append(
                    (tu, item[1], returned.get("lifetime", "unknown")))

    def append_relation(value):
        if len(relations) >= budgets["relations"]:
            if not any(item["code"] == "relation-budget-exhausted" for item in frontier):
                frontier.append(diagnostic("relation-budget-exhausted", "对象关系预算已耗尽",
                                           "Object relation budget exhausted"))
            return False
        relations.append(value)
        return True

    def resolve_local(domain, tu, function, depth=0, seen=()):
        """Follow worker value identities without treating unknown instructions as objects."""
        if depth >= budgets["load_hops"]:
            if not any(item["code"] == "load-hop-budget-exhausted" for item in frontier):
                frontier.append(diagnostic("load-hop-budget-exhausted", "局部值传播预算已耗尽",
                                           "Local value propagation budget exhausted"))
            return unknown("load-hop-budget-exhausted", domain["candidates"])
        result, resolved_any, unresolved = bottom(), False, False
        for item in domain["candidates"]:
            storage = item["object"]["storage"]
            source = storage["source_id"]
            local = by_operand.get((tu, function, source))
            marker = (tu, function, source)
            if storage["kind"] != "unknown" or not local or marker in seen:
                unresolved = True
                current = {"state": "may" if item["opposed"] else "must",
                           "candidates": [deepcopy(item)], "reason": None}
                result = join(result, current, candidate_limit=budgets["candidate_targets"],
                              guard_limit=budgets["guards"])
                continue
            resolved_any = True
            nested = resolve_local(local[1], tu, function, depth + 1, (*seen, marker))
            for nested_item in nested["candidates"]:
                clean = deepcopy(item)
                clean["opposed"] = [value for value in clean["opposed"] if value not in {
                    "llvm-pointer-may-be-captured", "llvm-unknown-storage-kind"}]
                clean["guards"] = sorted(set(clean["guards"]) | set(nested_item["guards"]))
                clean["proof"] = sorted(set(clean["proof"]) | set(nested_item["proof"]) |
                                        {"bounded-local-value-resolution"})
                clean["opposed"] = sorted(set(clean["opposed"]) | set(nested_item["opposed"]))
                deps = {(value["kind"], value["id"]): value for value in
                        [*clean["dependencies"], *nested_item["dependencies"]]}
                clean["dependencies"] = [deps[key] for key in sorted(deps)]
                outer = {"state": "may" if clean["opposed"] else "must",
                         "candidates": [clean], "reason": None}
                current = specialize(outer, {source: nested_item["object"]})
                result = join(result, current, candidate_limit=budgets["candidate_targets"],
                              guard_limit=budgets["guards"])
            if nested["state"] == "unknown":
                unresolved = True
        if not resolved_any:
            return deepcopy(domain)
        if unresolved and result["state"] != "unknown":
            return unknown("local-value-resolution-incomplete", result["candidates"])
        return result

    contexts = 0
    adjacency = {}
    for facts in llvm_facts:
        for edge in facts.get("call_edges", []):
            if edge.get("status") == "direct" and edge.get("callee"):
                adjacency.setdefault(edge["caller"], set()).add(edge["callee"])

    def reaches(start, goal, seen=None):
        if start == goal:
            return True
        seen = set() if seen is None else seen
        if start in seen:
            return False
        seen.add(start)
        return any(reaches(item, goal, seen) for item in adjacency.get(start, ()))

    recursive = sum(reaches(callee, caller) for caller, targets in adjacency.items() for callee in targets)

    def a1_definition(callee):
        matches = []
        for index in entity_indexes:
            if scope_id is not None and index.get("scope_id") != scope_id:
                continue
            for entity in index.get("entities", []):
                key = entity.get("key", {})
                if (entity.get("kind") == "function" and entity.get("resolution") == "resolved" and
                        key.get("symbol") == callee and entity.get("definitions")):
                    matches.append(entity)
        return matches[0] if len(matches) == 1 else None

    def p2_adoption(facts, edge, target_facts):
        matches = []
        for summary in effect_summaries:
            if scope_id is not None and summary.get("scope_id") != scope_id:
                continue
            for adoption in summary.get("adoptions", []):
                call, target = adoption.get("call", {}), adoption.get("target") or {}
                if (adoption.get("kind") != "unknown" and
                        call.get("artifact_key") == facts.get("artifact_key") and
                        call.get("function_id") == edge.get("caller") and
                        call.get("id") == edge.get("id") and
                        target.get("artifact_key") == target_facts.get("artifact_key") and
                        target.get("id") == edge.get("callee")):
                    matches.append(adoption)
        return matches[0] if len(matches) == 1 else None
    stop_contexts = False
    for facts in llvm_facts:
        if stop_contexts:
            break
        tu = facts["physical_tu_id"]
        for edge in facts.get("call_edges", []):
            if edge.get("status") != "direct":
                continue
            contexts += 1
            if contexts > budgets["call_contexts"]:
                frontier.append(diagnostic("call-context-budget-exhausted", "直接调用上下文预算已耗尽",
                                           "Direct-call context budget exhausted"))
                stop_contexts = True
                break
            callee = edge.get("callee")
            definition_tus = {item[0] for key, items in formals.items() if key[0] == callee for item in items}
            definition_tus.update(item[0] for item in returns.get(callee, ()))
            exact_definition = len(definition_tus) == 1
            target_tu = next(iter(definition_tus)) if exact_definition else None
            target_facts = next((item for item in llvm_facts if item["physical_tu_id"] == target_tu), None)
            compatible = bool(target_facts and facts.get("target") == target_facts.get("target") and
                              facts.get("data_layout") == target_facts.get("data_layout"))
            source_definition = a1_definition(callee)
            adopted_call = (p2_adoption(facts, edge, target_facts)
                            if target_facts is not None else None)
            adopted_exact = source_definition is not None and adopted_call is not None
            bindings = {}
            for index, operand in enumerate(edge.get("arguments", [])):
                actual_entry = (by_operand.get((tu, edge["caller"], operand)) or
                                by_operand.get((tu, None, operand)))
                formal_entries = [item for item in formals.get((callee, index), ()) if item[0] == target_tu]
                actual = actual_entry[1] if actual_entry else None
                formal = formal_entries[0][1] if len(formal_entries) == 1 else None
                formal_candidate = (formal and len(formal["candidates"]) == 1 and
                                    formal["candidates"][0]["object"]["storage"]["kind"] in
                                    {"parameter", "receiver"})
                status = ("exact" if exact_definition and adopted_exact and compatible and actual and
                          actual["state"] == "must" and formal_candidate else "candidate")
                append_relation({
                    "id": identity({"edge": edge["id"], "argument": index}),
                    "kind": "direct-actual-to-formal", "from": f"{edge['id']}:{index}",
                    "to": f"{callee}:arg:{index}", "status": status,
                    "proof": ["a1-exact-definition", "p2-adopted-direct-call",
                              "compatible-profile-target-data-layout"] if status == "exact" else [],
                    "opposed": [] if status == "exact" else ["missing-ambiguous-or-incompatible-binding"],
                })
                if status == "exact":
                    source_id = formal["candidates"][0]["object"]["storage"]["source_id"]
                    bindings[source_id] = actual["candidates"][0]["object"]
                    domain_map[f"{edge['id']}:argument:{index}"] = specialize(formal, bindings)
            result_operand = edge.get("result")
            returned = [item for item in returns.get(callee, ()) if item[0] == target_tu]
            if result_operand and exact_definition and adopted_exact and compatible and len(returned) == 1:
                _, returned_domain, lifetime = returned[0]
                returned_domain = resolve_local(returned_domain, target_tu, callee)
                result = (unknown("expired-local-return", returned_domain["candidates"])
                          if lifetime == "expired" else specialize(returned_domain, bindings))
                result_key = f"{edge['id']}:return"
                domain_map[result_key] = result
                append_relation({
                    "id": identity({"edge": edge["id"], "return": result_operand}),
                    "kind": "direct-return-to-call", "from": f"{callee}:return",
                    "to": result_key, "status": "exact" if result["state"] == "must" else "candidate",
                    "proof": ["unique-scoped-definition", "return-value-specialization"],
                    "opposed": [] if result["state"] == "must" else [result.get("reason") or "ambiguous-return"],
                })
    if recursive > budgets["recursive_iterations"]:
        frontier.append(diagnostic("recursive-budget-exhausted", "递归合并预算已耗尽",
                                   "Recursive merge budget exhausted"))
    source_by_tu = {item["physical_tu_id"]: item for item in source_facts}

    def source_binding(path, facts, matches):
        declaration = path["base"].get("declaration_id")
        compatible = []
        for binding in source_bindings:
            if scope_id is not None and binding.get("scope_id") != scope_id:
                continue
            for item in binding.get("entity_bindings", []):
                if (item.get("source_id") != declaration or item.get("resolution") != "exact" or
                        item.get("cardinality") != "one-to-one" or item.get("opposed")):
                    continue
                targets = item.get("targets", [])
                if (len(targets) == 1 and targets[0].get("artifact_key") == facts.get("artifact_key") and
                        targets[0].get("id") in matches):
                    compatible.append(item)
        return compatible[0] if len(compatible) == 1 else None

    for facts in llvm_facts:
        source = source_by_tu.get(facts["physical_tu_id"])
        if not source or source["profile_id"] != facts["profile_id"]:
            continue
        for path in source["paths"]:
            name = path["base"].get("name")
            if not name:
                continue
            source_offset = sum(item.get("offset_bits") or 0 for item in path["segments"]) // 8
            matches = []
            for value in facts["values"]:
                for item in value["domain"]["candidates"]:
                    origin = item["object"]["storage"]["source_id"].lstrip("%@")
                    if origin == name and item["object"]["byte_range"]["offset"] == source_offset:
                        matches.append(value["id"])
            binding = source_binding(path, facts, matches)
            status = ("exact" if path["status"] == "exact" and len(matches) == 1 and binding
                      else "candidate")
            append_relation({
                "id": identity({"path": path["id"], "matches": matches}),
                "kind": "source-ir-object-alignment", "from": path["id"],
                "to": matches[0] if len(matches) == 1 else None, "status": status,
                "proof": ["physical-tu", "profile", "a1-source-ir-binding", "byte-offset"]
                         if status == "exact" else [],
                "opposed": [] if status == "exact" else ["binding-cardinality-or-layout-mismatch"],
            })
    relations.sort(key=lambda item: item["id"])
    return sorted(domain_map.items()), relations, frontier


def build_graph(request, source_facts=(), llvm_facts=(), *, domains=(), relations=(), adapters=(),
                extra_frontier=(), failures=()):
    source_by_tu = {item["physical_tu_id"]: item for item in source_facts}
    llvm_by_tu = {item["physical_tu_id"]: item for item in llvm_facts}
    failures_by_tu = {}
    for failure in failures:
        failures_by_tu.setdefault(failure["physical_tu_id"], []).append({
            "layer": failure["layer"], "code": failure["diagnostic"]["code"]})
    members, diagnostics, frontier = [], [], list(deepcopy(extra_frontier))
    for member in request["members"]:
        tu = member["physical_tu_id"]
        source, llvm = source_by_tu.get(tu), llvm_by_tu.get(tu)
        mode = "ast+ir" if source and llvm else "ast-only" if source else "ir-only" if llvm else "failed"
        member_status = "failed" if mode == "failed" else (
            "partial" if mode != "ast+ir" or source.get("status") != "complete" or llvm.get("status") != "complete"
            else "complete")
        members.append({"physical_tu_id": tu, "mode": mode, "status": member_status,
                        "source_digest": source.get("semantic_digest") if source else None,
                        "llvm_digest": llvm.get("semantic_digest") if llvm else None,
                        "failures": sorted(failures_by_tu.get(tu, ()),
                                           key=lambda item: (item["layer"], item["code"]))})
        if member_status != "complete":
            frontier.append(diagnostic("candidate-evidence-incomplete",
                                       f"翻译单元 {tu} 的候选相关证据不完整",
                                       f"Candidate-relevant evidence is incomplete for translation unit {tu}"))
    objects = {}
    normalized_domains = []
    for key, domain in sorted(domains, key=lambda item: item[0]):
        for item in domain["candidates"]:
            objects[item["object"]["id"]] = item["object"]
        normalized_domains.append({"id": str(key), "domain": deepcopy(domain)})
    status = "failed" if members and all(item["status"] == "failed" for item in members) else (
        "partial" if frontier or any(item["status"] != "complete" for item in members) else "complete")
    raw_dependencies = [*request["dependencies"],
                        *(dependency(item["kind"], item["semantic_digest"], item)
                          for item in [*source_facts, *llvm_facts])]
    deps = sorted({(item["kind"], item["id"]): item for item in raw_dependencies}.values(),
                  key=lambda item: (item["kind"], item["id"]))
    return provenance_document(
        "BoundedObjectProvenanceGraph", scope_id=request["scope_id"],
        request_hash=request["semantic_digest"], status=status, members=members,
        objects=[objects[key] for key in sorted(objects)], domains=normalized_domains,
        relations=sorted(deepcopy(list(relations)), key=lambda item: item["id"]),
        adapters=sorted(deepcopy(list(adapters)), key=lambda item: item["id"]),
        counts={"planned": len(request["members"]),
                "completed": sum(item["status"] == "complete" for item in members),
                "objects": len(objects), "domains": len(normalized_domains)},
        dependencies=deps, diagnostics=diagnostics, frontier=frontier, semantic_digest=None)


def build_report(request, graph, *, hits=0, misses=0):
    graph_ref = dependency(graph["kind"], graph["semantic_digest"], graph)
    modes = {name: sum(item["mode"] == name for item in graph["members"])
             for name in ("ast+ir", "ir-only", "ast-only", "failed")}
    return provenance_document(
        "BoundedObjectProvenanceReport", scope_id=request["scope_id"],
        request_hash=request["semantic_digest"], status=graph["status"],
        exit_code=1 if graph["status"] == "failed" else 2 if graph["status"] == "partial" else 0,
        safety="not_established", findings=None, graph=graph_ref, modes=modes,
        counts=deepcopy(graph["counts"]), dependencies=[graph_ref],
        diagnostics=deepcopy(graph["diagnostics"]), frontier=deepcopy(graph["frontier"]),
        cache={"hits": hits, "misses": misses}, semantic_digest=None)


def failed_report(code, detail, detail_en=None):
    item = diagnostic(code, detail, detail_en or detail)
    return provenance_document(
        "BoundedObjectProvenanceReport", scope_id=None, request_hash=None,
        status="failed", exit_code=1, safety="not_established", findings=None,
        graph=None, modes={"ast+ir": 0, "ir-only": 0, "ast-only": 0, "failed": 1},
        counts={"planned": 0, "completed": 0}, dependencies=[], diagnostics=[item],
        frontier=[item], cache={"hits": 0, "misses": 0}, semantic_digest=None)


def compare_truth(suite, truth, actuals):
    cases = {item["case_id"]: item for item in truth["cases"]}
    metrics = {"planned": len(suite["cases"]), "completed": 0, "tp": 0, "fp": 0,
               "fn": 0, "abstention": 0}
    languages = {name: {key: 0 for key in metrics} for name in ("c11", "c17", "c++17", "c++20")}
    diagnostics = []
    for case in suite["cases"]:
        language = case["standard"]
        expected = cases[case["id"]]
        actual = actuals.get(case["id"])
        languages[language]["planned"] += 1
        if actual is None:
            metrics["abstention"] += 1; languages[language]["abstention"] += 1
            continue
        metrics["completed"] += 1; languages[language]["completed"] += 1
        expected_ids = set(expected.get("must_objects", []))
        actual_ids = set(actual.get("must_objects", []))
        tp, fp, fn = len(expected_ids & actual_ids), len(actual_ids - expected_ids), len(expected_ids - actual_ids)
        metrics["tp"] += tp; metrics["fp"] += fp; metrics["fn"] += fn
        languages[language]["tp"] += tp; languages[language]["fp"] += fp; languages[language]["fn"] += fn
        if actual.get("status") != "complete" or actual.get("unknown", False):
            metrics["abstention"] += 1; languages[language]["abstention"] += 1
        if fp or fn:
            diagnostics.append(diagnostic("truth-mismatch", f"用例 {case['id']} 与人工真值不一致",
                                          f"Case {case['id']} differs from adjudicated truth"))
    status = "complete" if metrics["completed"] == metrics["planned"] and not diagnostics else "partial"
    return provenance_document(
        "ObjectProvenanceValidationReport", suite_version=suite["suite_version"], status=status,
        metrics=metrics, languages=languages, diagnostics=diagnostics, semantic_digest=None)
