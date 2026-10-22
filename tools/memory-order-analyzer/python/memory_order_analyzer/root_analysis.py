"""R1 adapters, exact candidate alignment, root discovery and bounded planning."""

from collections import defaultdict, deque
from copy import deepcopy

from .contracts import AnalysisError, canonical, identity
from .root_contracts import dependency, diagnostic, root_document


def _entry(value):
    if not isinstance(value, dict) or not value.get("artifact_key"):
        return None
    function = value.get("function_id") or value.get("id")
    return ({"artifact_key": value["artifact_key"], "function_id": function}
            if function else None)


def _ref_key(value):
    return canonical(value) if isinstance(value, dict) else None


def _binding(bindings, source_id):
    matches = [item for item in bindings if item.get("source_id") == source_id and
               item.get("resolution") == "exact" and len(item.get("targets", [])) == 1]
    return matches[0]["targets"][0] if len(matches) == 1 else None


def adapt_source_candidates(member, source_facts, source_binding=None):
    """Adapt A1 candidates without promoting AST-only evidence to runtime proof."""
    if not source_facts:
        return []
    nodes = {item["id"]: item for item in source_facts.get("nodes", [])}
    by_from = defaultdict(list)
    for relation in source_facts.get("relations", []):
        by_from[relation.get("from")].append(relation)
    expression = (source_binding or {}).get("expression_bindings", [])
    entities = (source_binding or {}).get("entity_bindings", [])
    result = []
    for call in source_facts.get("relations", []):
        if call.get("kind") != "pthread_create":
            continue
        callbacks = [item for item in by_from[call.get("from")] if item.get("kind") == "callback"]
        target_ids = sorted({item.get("to") for item in callbacks if item.get("to")})
        call_target = _binding(expression, call["from"])
        callback_target = _binding(entities, target_ids[0]) if len(target_ids) == 1 else None
        exact_source = (call.get("status") != "unknown" and len(callbacks) == 1 and
                        callbacks[0].get("status") != "unknown" and len(target_ids) == 1)
        node = nodes.get(call["from"], {})
        result.append({
            "source_id": call["from"], "physical_tu_id": member["physical_tu_id"],
            "profile_id": member["profile_id"], "status": "candidate" if exact_source else "unknown",
            "call_ref": call_target, "callback_source_id": target_ids[0] if len(target_ids) == 1 else None,
            "callback_entry": _entry(callback_target), "callback_candidates": target_ids,
            "source": call.get("source") or node.get("source"),
            "evidence": sorted({call["id"], *(item["id"] for item in callbacks)}),
            "reason": (None if exact_source else call.get("reason") or
                       (callbacks[0].get("reason") if len(callbacks) == 1 else "callback-cardinality")),
        })
    return sorted(result, key=lambda item: item["source_id"])


def adapt_ir_candidates(member, thread_facts):
    """Adapt P3 calls; P3 already checked directness, C ABI and callback SSA propagation."""
    if not thread_facts:
        return []
    result = []
    for call in thread_facts.get("calls", []):
        if call.get("symbol") != "pthread_create":
            continue
        callbacks = call.get("callback_targets", [])
        exact = call.get("direct") is True and call.get("status") == "candidate" and len(callbacks) == 1
        result.append({
            "physical_tu_id": member["physical_tu_id"], "profile_id": member["profile_id"],
            "call_ref": call.get("source"), "caller_entry": _entry(call.get("function")),
            "callback_entry": _entry(callbacks[0]) if len(callbacks) == 1 else None,
            "callback_candidates": sorted((_entry(item) or item for item in callbacks), key=canonical),
            "arguments": ([{"kind": "object", "source": call["arguments"][3]}]
                          if len(call.get("arguments", [])) > 3 and call["arguments"][3] else
                          [{"kind": "null"}]),
            "status": "exact" if exact else "unsupported" if not call.get("direct") else "ambiguous",
            "evidence": [canonical(call.get("source"))],
            "reason": None if exact else call.get("reason") or "callback-cardinality-or-abi",
        })
    return sorted(result, key=lambda item: canonical(item["call_ref"]))


def adapt_cpp_candidates(member, local_facts, source_binding=None):
    """Adapt only A3 constructs carrying exact AST plus verified ABI/IR wrapper evidence."""
    if member["language"] != "c++" or not local_facts:
        return []
    callable_by_id = {item["id"]: item for item in local_facts.get("callables", [])}
    bindings = (source_binding or {}).get("entity_bindings", [])
    result = []
    for operation in local_facts.get("operations", []):
        if operation.get("operation") != "construct":
            continue
        callable_ = callable_by_id.get(operation.get("callable_id"), {})
        target = None
        if callable_.get("resolution") == "exact":
            candidates = [_binding(bindings, node) for node in callable_.get("source_nodes", [])]
            candidates = [item for item in candidates if item]
            target = candidates[0] if len({_ref_key(item) for item in candidates}) == 1 and candidates else None
        exact = (operation.get("outcome") == "success" and
                 operation.get("wrapper_role") == "construct-attempt" and target is not None)
        result.append({
            "physical_tu_id": member["physical_tu_id"], "profile_id": member["profile_id"],
            "operation_id": operation["id"], "call_ref": None,
            "caller_entry": None, "callback_entry": _entry(target),
            "callback_candidates": callable_.get("targets", []), "arguments": [],
            "status": "exact" if exact else
                      "ambiguous" if callable_.get("resolution") == "ambiguous" else "unsupported",
            "evidence": sorted([*operation.get("source_nodes", []), *operation.get("ir_nodes", [])]),
            "reason": None if exact else "a3-callable-or-wrapper-incomplete",
        })
    return sorted(result, key=lambda item: item["operation_id"])


def _site(mechanism, classification, member, source=None, ir=None):
    source, ir = source or {}, ir or {}
    call_ref = ir.get("call_ref") or source.get("call_ref")
    callback_entry = ir.get("callback_entry") or source.get("callback_entry")
    seed = {"mechanism": mechanism, "tu": member["physical_tu_id"],
            "call": call_ref, "source": source.get("source_id"),
            "operation": ir.get("operation_id")}
    return {
        "id": identity(seed), "mechanism": mechanism,
        "physical_tu_ids": [member["physical_tu_id"]], "profile_ids": [member["profile_id"]],
        "classification": classification,
        "callsite": {"source_id": source.get("source_id"), "ir": call_ref,
                     "caller_entry": ir.get("caller_entry") or _entry(source.get("call_ref"))},
        "callback": {"source_entity_id": source.get("callback_source_id"),
                     "entry": callback_entry,
                     "candidates": sorted((ir.get("callback_candidates") or
                                           source.get("callback_candidates") or []), key=canonical)},
        "arguments": deepcopy(ir.get("arguments", [])),
        "evidence": sorted(set([*source.get("evidence", []), *ir.get("evidence", [])])),
        "opposed": [], "reason": ir.get("reason") or source.get("reason"),
    }


def align_creation_sites(request, evidence):
    """Union AST and IR candidate sets, then intersect proof for exact adoption."""
    binding = next(iter(evidence.get("SourceIRBinding", {}).values()), None)
    sites, frontier, diagnostics = [], [], []
    source_count = ir_count = binding_count = 0
    for member in request["members"]:
        values = evidence.get("by_member", {}).get(member["physical_tu_id"], {})
        source = adapt_source_candidates(member, values.get("SourceSemanticFacts"), binding)
        ir = adapt_ir_candidates(member, values.get("ThreadLocalFacts"))
        cpp = adapt_cpp_candidates(member, values.get("CppThreadLocalFacts"), binding)
        source_count += len(source); ir_count += len(ir) + len(cpp)
        semantic_layers = [values.get(kind) for kind in
                           ("SourceSemanticFacts", "ThreadLocalFacts", "CppThreadLocalFacts")
                           if values.get(kind) is not None]
        if not source and not ir and not cpp and semantic_layers and all(
                item.get("status") == "failed" for item in semantic_layers):
            sites.append(_site("pthread", "failed", member, ir={
                "reason": "all-thread-creation-evidence-failed", "evidence": []}))
        source_by_call = defaultdict(list)
        for item in source:
            source_by_call[_ref_key(item.get("call_ref"))].append(item)
        used = set()
        for ir_item in ir:
            matches = source_by_call.get(_ref_key(ir_item.get("call_ref")), [])
            if len(matches) == 1:
                src = matches[0]; used.add(src["source_id"]); binding_count += 1
                same = src.get("callback_entry") == ir_item.get("callback_entry") and src.get("callback_entry") is not None
                classification = ("dual-exact" if same and ir_item["status"] == "exact" else
                                  "unsupported" if ir_item["status"] == "unsupported" else "ambiguous")
                site = _site("pthread", classification, member, src, ir_item)
                if not same:
                    site["opposed"] = ["source-ir-callback-disagreement"]
                    site["reason"] = "source-ir-callback-disagreement"
            elif len(matches) > 1:
                used.update(item["source_id"] for item in matches)
                site = _site("pthread", "ambiguous", member, matches[0], ir_item)
                site["reason"] = "multiple-source-candidates-for-ir-call"
            else:
                classification = "ir-exact" if ir_item["status"] == "exact" else ir_item["status"]
                site = _site("pthread", classification, member, ir=ir_item)
            sites.append(site)
        for item in source:
            if item["source_id"] not in used:
                sites.append(_site("pthread", "source-candidate", member, source=item))
        for item in cpp:
            classification = "dual-exact" if item["status"] == "exact" else item["status"]
            sites.append(_site("std-thread", classification, member, ir=item))
    sites = sorted({item["id"]: item for item in sites}.values(), key=lambda item: item["id"])
    limits = request["budgets"]
    for name, count, limit in (("source_candidates", source_count, limits["source_candidates"]),
                               ("ir_candidates", ir_count, limits["ir_candidates"]),
                               ("binding_candidates", binding_count, limits["binding_candidates"])):
        if count > limit:
            sites = sites[:limit]
            frontier.append(diagnostic(
                f"{name}-budget-exhausted", f"{name} 预算已耗尽", f"The {name} budget is exhausted",
                suggestion="提高预算或缩小显式 scope", suggestion_en="Increase the budget or reduce the explicit scope",
                source={"count": count, "limit": limit}))
    for site in sites:
        if site["classification"] not in {"dual-exact", "ir-exact"}:
            frontier.append(diagnostic(
                f"thread-creation-{site['classification']}", "线程创建候选没有形成可采纳的精确证明",
                "The thread-creation candidate did not form an adoptable exact proof",
                suggestion="补齐 AST/BC、callback、ABI 与 profile 对齐证据",
                suggestion_en="Complete AST/BC, callback, ABI, and profile alignment evidence",
                source={"site_id": site["id"], "classification": site["classification"]}))
    if not sites:
        diagnostics.append(diagnostic(
            "thread-creation-site-zero", "显式 scope 中没有发现线程创建候选",
            "No thread-creation candidate was found in the explicit scope",
            suggestion="若工程由框架创建线程，请显式声明 framework root",
            suggestion_en="Declare a framework root explicitly when threads are created by a framework"))
    deps = sorted(evidence["dependencies"], key=lambda item: (item["kind"], item["id"]))
    counts = {name: sum(item["classification"] == name for item in sites) for name in (
        "dual-exact", "ir-exact", "source-candidate", "ambiguous", "unsupported", "failed")}
    counts.update({"sites": len(sites), "source_candidates": source_count,
                   "ir_candidates": ir_count, "binding_candidates": binding_count})
    return root_document(
        "ThreadCreationSiteIndex", scope_id=request["scope_id"], request_hash=identity(request),
        status="partial" if frontier else "complete", sites=sites, counts=counts,
        dependencies=deps, diagnostics=diagnostics + frontier, frontier=frontier,
        semantic_digest=None)


def _function_inventory(evidence):
    functions = {}
    for module in evidence.get("ModuleFacts", {}).values():
        artifact = module["artifact_key"]
        for function in module.get("functions", []):
            entry = {"artifact_key": artifact, "function_id": function["id"]}
            functions[canonical(entry)] = {"entry": entry, "name": function.get("name"),
                                            "declaration": function.get("declaration", False),
                                            "linkage": function.get("linkage")}
    return functions


def discover_execution_roots(request, sites, evidence):
    inventory = _function_inventory(evidence)
    roots, frontier, diagnostics = [], [], []
    for item in request["explicit_roots"]:
        exact = canonical(item["entry"]) in inventory and not inventory[canonical(item["entry"])]["declaration"]
        root = {
            "id": identity({"explicit": item["id"], "entry": item["entry"]}), "kind": item["kind"],
            "entry": item["entry"], "source_entity_id": item["source_entity_id"],
            "arguments": item["arguments"], "creation_site_id": None,
            "thread_context_key": identity({"entry": item["entry"], "arguments": item["arguments"]}),
            "thread_instance_key": identity({"explicit": item["id"]}),
            "status": "complete" if exact else "partial", "evidence": [item["id"]],
        }
        roots.append(root)
        if not exact:
            frontier.append(diagnostic(
                "explicit-root-unresolved", "显式执行根没有绑定到 scope 内的精确定义",
                "The explicit execution root did not bind to an exact in-scope definition",
                suggestion="修正 artifact/function 或补齐对应 TU", suggestion_en="Fix artifact/function or include the defining TU",
                source={"root_id": root["id"], "entry": item["entry"]}))
    if request["discover_main"]:
        mains = [item for item in inventory.values() if item["name"] == "main" and not item["declaration"]]
        if len(mains) == 1:
            entry = mains[0]["entry"]
            roots.append({
                "id": identity({"kind": "main", "entry": entry}), "kind": "main", "entry": entry,
                "source_entity_id": None, "arguments": [], "creation_site_id": None,
                "thread_context_key": identity({"entry": entry, "arguments": []}),
                "thread_instance_key": identity({"kind": "main", "entry": entry}),
                "status": "complete", "evidence": ["p1-main-definition"],
            })
        elif len(mains) > 1:
            frontier.append(diagnostic(
                "main-root-ambiguous", "scope 中存在多个 main 定义", "Multiple main definitions exist in the scope",
                suggestion="缩小 scope 或显式指定 program root", suggestion_en="Reduce the scope or specify a program root explicitly",
                source={"candidates": [item["entry"] for item in mains]}))
        else:
            diagnostics.append(diagnostic(
                "main-root-absent", "启用了 main 发现但 scope 中没有 main 定义",
                "Main discovery was enabled but no main definition exists in the scope",
                suggestion="库分析请显式声明 exported root", suggestion_en="Declare exported roots explicitly for library analysis"))
    for site in sites["sites"]:
        if site["classification"] not in {"dual-exact", "ir-exact"}:
            continue
        entry = site["callback"]["entry"]
        kind = "pthread" if site["mechanism"] == "pthread" else "std-thread"
        context = identity({"entry": entry, "arguments": site["arguments"]})
        roots.append({
            "id": identity({"kind": kind, "site": site["id"], "entry": entry}), "kind": kind,
            "entry": entry, "source_entity_id": site["callback"]["source_entity_id"],
            "arguments": site["arguments"], "creation_site_id": site["id"],
            "thread_context_key": context,
            "thread_instance_key": identity({"site": site["id"], "context": context}),
            "status": "complete", "evidence": site["evidence"],
        })
    roots = sorted({item["id"]: item for item in roots}.values(), key=lambda item: item["id"])
    if len(roots) > request["budgets"]["roots"]:
        roots = roots[:request["budgets"]["roots"]]
        frontier.append(diagnostic("roots-budget-exhausted", "执行根预算已耗尽",
                                   "The execution-root budget is exhausted"))
    if not roots:
        frontier.append(diagnostic(
            "execution-root-zero", "没有形成可分析的 ExecutionRoot", "No analyzable ExecutionRoot was formed",
            suggestion="启用 main 发现、声明显式根或补齐线程创建证据",
            suggestion_en="Enable main discovery, declare an explicit root, or complete thread-creation evidence"))
    deps = [dependency("ThreadCreationSiteIndex", sites["scope_id"], sites)]
    return root_document(
        "ExecutionRootIndex", scope_id=request["scope_id"], request_hash=identity(request),
        status="partial" if frontier else "complete", roots=roots,
        counts={"roots": len(roots), "complete": sum(item["status"] == "complete" for item in roots),
                "partial": sum(item["status"] != "complete" for item in roots)},
        dependencies=deps, diagnostics=diagnostics + frontier, frontier=frontier,
        semantic_digest=None)


def _exact_call_edges(evidence):
    edges = {}
    modules = evidence.get("ModuleFacts", {})
    for module in modules.values():
        artifact = module["artifact_key"]
        definitions = {item["id"] for item in module.get("functions", []) if not item.get("declaration")}
        for call in module.get("calls", []):
            if call.get("kind") == "direct" and call.get("function") and call.get("target") in definitions:
                caller = {"artifact_key": artifact, "function_id": call["function"]}
                target = {"artifact_key": artifact, "function_id": call["target"]}
                seed = {"caller": caller, "target": target, "call": call["id"], "proof": "p1-local-direct"}
                edges[identity(seed)] = {"id": identity(seed), **seed}
    binding = next(iter(evidence.get("SourceIRBinding", {}).values()), None)
    if binding:
        expr = binding.get("expression_bindings", [])
        entities = binding.get("entity_bindings", [])
        for facts in evidence.get("SourceSemanticFacts", {}).values():
            for relation in facts.get("relations", []):
                if relation.get("kind") != "call" or not relation.get("to"):
                    continue
                call = _binding(expr, relation["from"]); target = _binding(entities, relation["to"])
                caller, callee = _entry(call), _entry(target)
                if caller and callee:
                    seed = {"caller": caller, "target": callee, "call": call.get("id"), "proof": "a1-exact-binding"}
                    edges[identity(seed)] = {"id": identity(seed), **seed}
    for summary in evidence.get("EffectSummary", {}).values():
        for adoption in summary.get("adoptions", []):
            if adoption.get("kind") not in {"unique-definition", "odr-body-under-contract"}:
                continue
            caller, target = _entry(adoption.get("call")), _entry(adoption.get("target"))
            if caller and target:
                seed = {"caller": caller, "target": target,
                        "call": adoption["call"].get("id"), "proof": "p2-adoption"}
                edges[identity(seed)] = {"id": identity(seed), **seed}
    return sorted(edges.values(), key=lambda item: item["id"])


def build_analysis_plan(request, sites, roots, evidence):
    inventory = _function_inventory(evidence)
    edges = _exact_call_edges(evidence)
    adjacency = defaultdict(list)
    for edge in edges:
        adjacency[canonical(edge["caller"])].append(edge)
    reachable, used_edges, frontier, diagnostics = {}, {}, [], []
    complete_roots = [root for root in roots["roots"] if root["status"] == "complete"]
    for root in roots["roots"]:
        if root["status"] != "complete":
            frontier.append(diagnostic(
                "execution-root-incomplete", "执行根缺少完整、可采用的入口证据",
                "An execution root lacks complete, adoptable entry evidence",
                source={"root_id": root["id"], "kind": root["kind"], "entry": root["entry"]}))
    if not complete_roots:
        frontier.append(diagnostic(
            "execution-root-plan-empty", "没有可用于深度分析的完整执行根",
            "No complete execution root is available for deep analysis",
            suggestion="补充闭合 scope、精确入口或线程创建证据",
            suggestion_en="Provide a closed scope, exact entry, or thread-creation evidence"))
    queue = deque((root, root["entry"], 0) for root in complete_roots)
    seen = set()
    iterations = 0
    while queue:
        root, entry, distance = queue.popleft()
        if distance > request["budgets"]["wrapper_depth"]:
            frontier.append(diagnostic(
                "wrapper-depth-budget-exhausted", "调用 wrapper 深度预算已耗尽",
                "The call-wrapper depth budget is exhausted",
                source={"root_id": root["id"], "entry": entry, "distance": distance}))
            continue
        key = (root["id"], canonical(entry))
        if key in seen:
            continue
        seen.add(key); iterations += 1
        if iterations > request["budgets"]["functions"]:
            frontier.append(diagnostic("functions-budget-exhausted", "可达函数预算已耗尽",
                                       "The reachable-function budget is exhausted"))
            break
        item = {"id": identity({"root": root["id"], "entry": entry}),
                "root_id": root["id"], "entry": entry, "distance": distance,
                "status": "complete" if canonical(entry) in inventory else "partial"}
        reachable[item["id"]] = item
        if item["status"] != "complete":
            frontier.append(diagnostic(
                "reachable-definition-missing", "可达入口缺少 scope 内定义",
                "A reachable entry lacks an in-scope definition",
                source={"root_id": root["id"], "entry": entry}))
            continue
        for edge in adjacency.get(canonical(entry), []):
            if len(used_edges) >= request["budgets"]["call_edges"]:
                frontier.append(diagnostic("call-edges-budget-exhausted", "调用边预算已耗尽",
                                           "The call-edge budget is exhausted"))
                queue.clear(); break
            used_edges[edge["id"]] = edge
            queue.append((root, edge["target"], distance + 1))
    reachable_entries = {canonical(item["entry"]) for item in reachable.values()}
    relevant_sites = []
    exact_site_ids = {root["creation_site_id"] for root in roots["roots"] if root["creation_site_id"]}
    for site in sites["sites"]:
        relevant = site["id"] in exact_site_ids or canonical(site["callsite"].get("caller_entry")) in reachable_entries
        if relevant:
            relevant_sites.append(site)
            if site["classification"] not in {"dual-exact", "ir-exact"}:
                frontier.append(diagnostic(
                    "candidate-relevant-thread-creation-incomplete",
                    "根可达切片中的线程创建候选不完整",
                    "A thread-creation candidate in the root-reachable slice is incomplete",
                    source={"site_id": site["id"], "classification": site["classification"]}))
    if not request["closed_scope"]:
        frontier.append(diagnostic(
            "open-scope-frontier", "开放 scope 可能遗漏外部回调或调用目标",
            "The open scope may omit external callbacks or call targets",
            suggestion="提供闭合 scope 或显式声明外部边界和 framework root",
            suggestion_en="Provide a closed scope or explicitly declare external boundaries and framework roots"))
    contexts, demands, p2, p3, overlays = {}, {}, [], [], []
    artifact_to_tu = {}
    for member in request["members"]:
        for ref in member["evidence"]:
            if ref["kind"] == "ModuleFacts":
                artifact_to_tu[ref["id"]] = member["physical_tu_id"]
    for root in roots["roots"]:
        context = {"id": root["thread_context_key"], "entry": root["entry"],
                   "arguments": root["arguments"], "root_ids": [root["id"]]}
        if context["id"] not in contexts and len(contexts) >= request["budgets"]["contexts"]:
            frontier.append(diagnostic(
                "contexts-budget-exhausted", "分析上下文预算已耗尽",
                "The analysis-context budget is exhausted", source={"root_id": root["id"]}))
            continue
        if context["id"] in contexts:
            contexts[context["id"]]["root_ids"].append(root["id"])
            contexts[context["id"]]["root_ids"] = sorted(set(contexts[context["id"]]["root_ids"]))
        else:
            contexts[context["id"]] = context
        p2.append({"id": identity({"consumer": "P2", "root": root["id"]}),
                   "root_id": root["id"], "scope_id": request["scope_id"], "mode": "roots",
                   "roots": [{"artifact_key": root["entry"]["artifact_key"],
                              "function_id": root["entry"]["function_id"],
                              "arguments": root["arguments"]}]})
        p3.append({"id": identity({"consumer": "P3", "root": root["id"]}),
                   "root_id": root["id"], "scope_id": request["scope_id"],
                   "model_id": "posix-pthread-v1", "roots": [{
                       "artifact_key": root["entry"]["artifact_key"],
                       "function_id": root["entry"]["function_id"], "arguments": root["arguments"]}]})
        if root["kind"] == "std-thread":
            overlays.append({"id": identity({"a3": root["id"]}), "root_id": root["id"],
                             "creation_site_id": root["creation_site_id"],
                             "thread_context_key": root["thread_context_key"],
                             "thread_instance_key": root["thread_instance_key"]})
    for item in reachable.values():
        key = {"function": item["entry"], "context": next(
            root["thread_context_key"] for root in roots["roots"] if root["id"] == item["root_id"]),
            "physical_tu_id": artifact_to_tu.get(item["entry"]["artifact_key"]),
            "consumers": ["P2", "P3"]}
        key["id"] = identity(key)
        demands[key["id"]] = key
    observed_functions = set()
    for summary in evidence.get("EffectSummary", {}).values():
        for invocation in summary.get("invocations", []):
            entry = _entry(invocation.get("function"))
            if entry:
                observed_functions.add(canonical(entry))
    observed_members = {facts["origin"]["artifact_key"] for facts in
                        evidence.get("ThreadLocalFacts", {}).values()}
    planned_entries = {canonical(item["entry"]) for item in reachable.values()}
    deep_observed = planned_entries & observed_functions
    reconciliation = {
        "planned_functions": len(planned_entries), "indexed_functions": len(planned_entries & set(inventory)),
        "deep_observed_functions": len(deep_observed),
        "missing_deep_observation": sorted(planned_entries - deep_observed),
        "p3_observed_artifacts": len({item["entry"]["artifact_key"] for item in reachable.values()} & observed_members),
    }
    relevant_exact = sum(item["classification"] in {"dual-exact", "ir-exact"} for item in relevant_sites)
    root_complete = sum(item["status"] == "complete" for item in roots["roots"])
    reachable_complete = sum(item["status"] == "complete" for item in reachable.values())
    completeness = {
        "root": {"planned": len(roots["roots"]), "complete": root_complete,
                 "ratio": root_complete / len(roots["roots"]) if roots["roots"] else 0.0},
        "reachable": {"planned": len(reachable), "complete": reachable_complete,
                      "ratio": reachable_complete / len(reachable) if reachable else 0.0},
        "candidate_relevant": {"planned": len(relevant_sites), "complete": relevant_exact,
                               "ratio": relevant_exact / len(relevant_sites) if relevant_sites else 1.0},
    }
    if len(frontier) > request["budgets"]["frontier_items"]:
        frontier = frontier[:request["budgets"]["frontier_items"]]
        frontier.append(diagnostic("frontier-budget-exhausted", "frontier 预算已耗尽",
                                   "The frontier budget is exhausted"))
    site_ref = dependency("ThreadCreationSiteIndex", sites["scope_id"], sites)
    root_ref = dependency("ExecutionRootIndex", roots["scope_id"], roots)
    deps = sorted([site_ref, root_ref, *evidence["dependencies"]], key=lambda item: (item["kind"], item["id"]))
    return root_document(
        "RootDrivenAnalysisPlan", scope_id=request["scope_id"], request_hash=identity(request),
        status="partial" if frontier else "complete", thread_creation_sites=site_ref,
        execution_roots=root_ref, reachable_functions=sorted(reachable.values(), key=lambda item: item["id"]),
        call_edges=sorted(used_edges.values(), key=lambda item: item["id"]),
        contexts=sorted(contexts.values(), key=lambda item: item["id"]),
        demands=sorted(demands.values(), key=lambda item: item["id"]),
        p2_requests=sorted(p2, key=lambda item: item["id"]),
        p3_requests=sorted(p3, key=lambda item: item["id"]),
        a3_overlays=sorted(overlays, key=lambda item: item["id"]),
        reconciliation=reconciliation, completeness=completeness,
        counts={"roots": len(roots["roots"]), "reachable_functions": len(reachable),
                "call_edges": len(used_edges), "contexts": len(contexts), "demands": len(demands),
                "candidate_relevant_sites": len(relevant_sites)},
        dependencies=deps, diagnostics=diagnostics + frontier, frontier=frontier,
        semantic_digest=None)


def build_root_report(request, sites, roots, plan, *, hits=0, misses=0):
    refs = [dependency("ThreadCreationSiteIndex", sites["scope_id"], sites),
            dependency("ExecutionRootIndex", roots["scope_id"], roots),
            dependency("RootDrivenAnalysisPlan", plan["scope_id"], plan)]
    status = plan["status"]
    counts = {name: sites["counts"].get(name, 0) for name in (
        "dual-exact", "ir-exact", "source-candidate", "ambiguous", "unsupported", "failed")}
    return root_document(
        "RootDrivenAnalysisReport", scope_id=request["scope_id"], request_hash=identity(request),
        status=status, exit_code=2 if status == "partial" else 0,
        safety="not_evaluated", findings=None,
        thread_creation_sites=refs[0], execution_roots=refs[1], plan=refs[2],
        classification_counts=counts, root_counts=deepcopy(roots["counts"]),
        reachable_counts={"planned": plan["completeness"]["reachable"]["planned"],
                          "complete": plan["completeness"]["reachable"]["complete"]},
        analysis_counts=deepcopy(plan["reconciliation"]), completeness=deepcopy(plan["completeness"]),
        dependencies=sorted(refs, key=lambda item: (item["kind"], item["id"])),
        diagnostics=deepcopy(plan["diagnostics"]), frontier=deepcopy(plan["frontier"]),
        cache={"hits": hits, "misses": misses}, semantic_digest=None)


def failed_root_report(code, detail, detail_en=None):
    item = diagnostic(
        code, f"执行根驱动分析失败：{detail}", f"Execution-root-driven analysis failed: {detail_en or detail}",
        suggestion="修复请求、显式 evidence 引用或 profile 后重试",
        suggestion_en="Repair the request, explicit evidence references, or profiles and retry")
    return root_document(
        "RootDrivenAnalysisReport", scope_id=None, request_hash=None, status="failed", exit_code=1,
        safety="not_evaluated", findings=None, thread_creation_sites=None, execution_roots=None, plan=None,
        classification_counts={}, root_counts={}, reachable_counts={}, analysis_counts={}, completeness={},
        dependencies=[], diagnostics=[item], frontier=[item], cache={"hits": 0, "misses": 0},
        semantic_digest=None)
