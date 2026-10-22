"""Monotonic root-driven function/context demand graph for R3."""

from copy import deepcopy

from .contracts import AnalysisError, canonical, identity
from .demand_contracts import diagnostic


SYSTEM_EXTERNALS = {
    "pthread_create", "pthread_join", "pthread_mutex_lock", "pthread_mutex_unlock",
    "thrd_create", "malloc", "calloc", "realloc", "free", "memcpy", "memmove", "memset",
}


def function_name(function_id):
    marker = ":symbol:"
    if marker not in function_id:
        raise AnalysisError("invalid_reference", f"R3 function identity has no symbol spelling: {function_id}")
    return function_id.split(marker, 1)[1]


def node_key(artifact_key, function_id, context_id, layers):
    return identity({"artifact_key": artifact_key, "function_id": function_id,
                     "context_id": context_id, "layers": sorted(layers)})


def _seed_item(entry, context_id, physical_tu_id, layers, *, root_id=None, consumers=()):
    key = node_key(entry["artifact_key"], entry["function_id"], context_id, layers)
    return {
        "id": key, "artifact_key": entry["artifact_key"], "function_id": entry["function_id"],
        "function_name": function_name(entry["function_id"]), "context_id": context_id,
        "physical_tu_id": physical_tu_id, "layers": sorted(layers), "state": "demanded",
        "root_ids": sorted({root_id} - {None}), "consumers": sorted(set(consumers)),
        "reasons": ["execution-root"], "depth": 0,
    }


def seed_demands(request, plan, overlay):
    """Merge R1 and R1.1 demand slices without inventing all-defined roots."""
    nodes = {}
    roots_by_context = {item["id"]: item.get("root_ids", []) for item in plan.get("contexts", [])}
    for item in plan.get("demands", []):
        context_id = item["context"]
        seed = _seed_item(item["function"], context_id, item.get("physical_tu_id"), request["layers"],
                          root_id=(roots_by_context.get(context_id) or [None])[0],
                          consumers=item.get("consumers", []))
        nodes[seed["id"]] = seed
    overlay_roots = {item["id"]: item for item in overlay.get("roots", [])}
    for item in overlay.get("demands", []):
        root = overlay_roots.get(item.get("root_id"), {})
        context_id = root.get("context_id") or identity({"root": item.get("root_id"), "entry": item["entry"]})
        seed = _seed_item(item["entry"], context_id, item.get("physical_tu_id"), request["layers"],
                          root_id=item.get("root_id"), consumers=("P2", "P3"))
        if seed["id"] in nodes:
            current = nodes[seed["id"]]
            current["root_ids"] = sorted(set(current["root_ids"] + seed["root_ids"]))
            current["consumers"] = sorted(set(current["consumers"] + seed["consumers"]))
        else:
            nodes[seed["id"]] = seed
    frontier = []
    if not request["closed_scope"]:
        frontier.append(diagnostic(
            "open-scope-frontier", "开放 scope 可能遗漏外部调用目标或回调",
            "The open scope may omit external call targets or callbacks",
            suggestion="提供闭合 scope 或显式外部边界", suggestion_en="Provide a closed scope or explicit external boundaries"))
    members = {item["physical_tu_id"]: item for item in request["members"]}
    for node in nodes.values():
        member = members.get(node["physical_tu_id"])
        if member is None or member["evidence_mode"] in {"ast-only", "failed"}:
            node["state"] = "partial"
            frontier.append(diagnostic(
                "ast-only-no-runtime-facts" if member and member["evidence_mode"] == "ast-only" else "dependency-failed",
                "需求函数缺少可用 BC 运行时事实", "The demanded function lacks usable BC runtime facts",
                artifact_key=node["artifact_key"], root_id=(node["root_ids"] or [None])[0],
                function_id=node["function_id"], context_id=node["context_id"]))
    if not nodes:
        frontier.append(diagnostic("zero-demand-roots", "R1/R1.1 未提供可分析执行根",
                                   "R1/R1.1 provided no analyzable execution roots"))
    ordered = {key: nodes[key] for key in sorted(nodes)}
    root_ids = {root for node in ordered.values() for root in node["root_ids"]}
    contexts = {node["context_id"] for node in ordered.values()}
    limits = request["budgets"]
    for exceeded, code, reason, reason_en in (
        (len(root_ids) > limits["roots"], "root-budget-exhausted", "执行根预算已耗尽", "The execution-root budget is exhausted"),
        (len(contexts) > limits["contexts"], "context-budget-exhausted", "上下文预算已耗尽", "The context budget is exhausted"),
        (len(ordered) > limits["demands"], "demand-budget-exhausted", "函数需求预算已耗尽", "The function-demand budget is exhausted"),
    ):
        if exceeded:
            frontier.append(diagnostic(code, reason, reason_en))
    if len(ordered) > limits["demands"]:
        keep = set(list(ordered)[:limits["demands"]])
        ordered = {key: value for key, value in ordered.items() if key in keep}
    if any(item["code"] in {"root-budget-exhausted", "context-budget-exhausted"} for item in frontier):
        for node in ordered.values():
            node["state"] = "partial"
    return ordered, [], frontier


def definition_index(indexes):
    by_name = {}
    for artifact, index in indexes.items():
        for symbol in index.get("symbols", []):
            if symbol["materializable"] or not symbol["declaration"]:
                by_name.setdefault(symbol["name"], []).append({
                    "artifact_key": artifact, "function_id": symbol["id"], "name": symbol["name"]})
    for values in by_name.values():
        values.sort(key=lambda item: (item["artifact_key"], item["function_id"]))
    return by_name


def _external(name):
    return name in SYSTEM_EXTERNALS or name.startswith("llvm.") or name.startswith("__cxa_") or \
        name.startswith("_Unwind_") or name.startswith("__gxx_")


def expand_demands(request, parent, shards, indexes, nodes, edges, frontier):
    """Expand only exact direct calls/callbacks. Returns newly inserted node ids."""
    definitions = definition_index(indexes)
    targets = []
    seen = set()
    for shard in shards:
        if shard["status"] != "completed":
            continue
        facts = shard["facts"]
        for call in facts.get("calls", []):
            name = call.get("target_name")
            if call.get("binding") != "exact" or not name:
                frontier.append(diagnostic(
                    "indirect-call-frontier", "间接调用未扩展为所有定义",
                    "An indirect call was not expanded to all definitions",
                    artifact_key=parent["artifact_key"], root_id=(parent["root_ids"] or [None])[0],
                    function_id=parent["function_id"], context_id=parent["context_id"], layer=shard["layer"]))
                continue
            if _external(name):
                continue
            key = (name, call["id"], "direct-call")
            if key not in seen:
                seen.add(key); targets.append(key)
        for call in facts.get("thread_calls", []):
            for callback in call.get("callbacks", []):
                name = function_name(callback)
                key = (name, call["source"], "callback")
                if key not in seen:
                    seen.add(key); targets.append(key)
    inserted = []
    for name, callsite, reason in sorted(targets):
        candidates = definitions.get(name, [])
        if len(candidates) != 1:
            code = "missing-definition" if not candidates else "ambiguous-call-target"
            frontier.append(diagnostic(
                code, "直接调用或回调目标无法在显式 scope 内唯一绑定",
                "A direct-call or callback target cannot be uniquely bound in the explicit scope",
                artifact_key=parent["artifact_key"], root_id=(parent["root_ids"] or [None])[0],
                function_id=parent["function_id"], context_id=parent["context_id"],
                suggestion=f"核对调用点 {callsite} 的 linkage/ABI/scope",
                suggestion_en=f"Review linkage, ABI, and scope for callsite {callsite}"))
            continue
        candidate = candidates[0]
        member = next((item for item in request["members"] if item["artifact_key"] == candidate["artifact_key"]), None)
        child_id = node_key(candidate["artifact_key"], candidate["function_id"], parent["context_id"], request["layers"])
        edge_id = identity({"source": parent["id"], "target": child_id, "callsite": callsite, "reason": reason})
        if not any(item["id"] == edge_id for item in edges):
            edges.append({"id": edge_id, "source": parent["id"], "target": child_id,
                          "callsite": callsite, "kind": reason,
                          "recursive": child_id == parent["id"]})
        if child_id in nodes:
            child = nodes[child_id]
            child["root_ids"] = sorted(set(child["root_ids"] + parent["root_ids"]))
            child["consumers"] = sorted(set(child["consumers"] + parent["consumers"]))
            if reason not in child["reasons"]:
                child["reasons"].append(reason); child["reasons"].sort()
            continue
        if len(nodes) >= request["budgets"]["demands"]:
            frontier.append(diagnostic(
                "demand-budget-exhausted", "函数需求预算已耗尽", "The function-demand budget is exhausted",
                artifact_key=candidate["artifact_key"], function_id=candidate["function_id"],
                context_id=parent["context_id"]))
            continue
        if parent["depth"] + 1 > request["budgets"]["recursion_depth"]:
            frontier.append(diagnostic(
                "recursion-budget", "递归或调用深度预算已耗尽", "The recursion or call-depth budget is exhausted",
                artifact_key=candidate["artifact_key"], function_id=candidate["function_id"],
                context_id=parent["context_id"]))
            continue
        child = {
            "id": child_id, "artifact_key": candidate["artifact_key"],
            "function_id": candidate["function_id"], "function_name": name,
            "context_id": parent["context_id"], "physical_tu_id": member["physical_tu_id"] if member else None,
            "layers": sorted(request["layers"]), "state": "demanded",
            "root_ids": deepcopy(parent["root_ids"]), "consumers": deepcopy(parent["consumers"]),
            "reasons": [reason], "depth": parent["depth"] + 1,
        }
        if member is None or member["evidence_mode"] in {"ast-only", "failed"}:
            child["state"] = "partial"
            frontier.append(diagnostic(
                "ast-only-no-runtime-facts" if member and member["evidence_mode"] == "ast-only" else "dependency-failed",
                "被调用函数缺少可用 BC 运行时事实", "The called function lacks usable BC runtime facts",
                artifact_key=child["artifact_key"], function_id=child["function_id"], context_id=child["context_id"]))
        nodes[child_id] = child; inserted.append(child_id)
    edges.sort(key=lambda item: item["id"])
    return inserted


def graph_counts(nodes):
    counts = {state: 0 for state in ("indexed", "demanded", "scheduled", "materialized", "completed", "partial", "failed")}
    for node in nodes.values():
        counts[node["state"]] = counts.get(node["state"], 0) + 1
    counts["total"] = len(nodes)
    return counts


def normalized_nodes(nodes):
    result = []
    for key in sorted(nodes):
        item = deepcopy(nodes[key])
        item["root_ids"] = sorted(set(item["root_ids"])); item["consumers"] = sorted(set(item["consumers"]))
        item["reasons"] = sorted(set(item["reasons"]))
        result.append(item)
    return result
