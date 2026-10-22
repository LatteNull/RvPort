"""Read-only R3 views for existing P2/P3/R2 consumers.

These functions deliberately return R3 view kinds.  They never serialize a partial
ModuleFacts, LocalAnalysisFacts, ThreadLocalFacts, or ConcurrentAccessCandidateGraph.
"""

from copy import deepcopy

from .contracts import identity
from .demand_contracts import diagnostic


def _complete(shards, layer):
    selected = [item for item in shards if item["layer"] == layer]
    missing = [item for item in selected if item["status"] != "completed"]
    frontier = [entry for item in missing for entry in item.get("frontier", [])]
    if missing and not frontier:
        frontier.append(diagnostic(
            "missing-function-shard", "函数 shard 不完整，不能适配为旧分析输入",
            "A function shard is incomplete and cannot be adapted to legacy analysis input",
            function_id=missing[0].get("function_id"), context_id=missing[0].get("context_id"), layer=layer))
    return selected, frontier


def effect_view(shards):
    selected, frontier = _complete(shards, "effect")
    effects = []
    for shard in selected:
        if shard["status"] == "completed":
            for effect in shard["facts"].get("effects", []):
                effects.append({**deepcopy(effect), "function_id": shard["function_id"],
                                "context_id": shard["context_id"], "artifact_key": shard["artifact_key"]})
    effects.sort(key=lambda item: (item["artifact_key"], item["function_id"], item["context_id"], item["source"]))
    return {"kind": "R3EffectShardView", "status": "partial" if frontier else "complete",
            "effects": effects, "frontier": frontier, "semantic_digest": identity(effects)}


def effect_summary_views(shards):
    """Build in-memory P2-compatible slices without claiming EffectSummary identity."""
    view = effect_view(shards)
    grouped = {}
    for effect in view["effects"]:
        key = (effect["artifact_key"], effect["function_id"], effect["context_id"])
        grouped.setdefault(key, []).append(effect)
    summaries = []
    for (artifact, function, context), effects in sorted(grouped.items()):
        normalized = []
        for effect in effects:
            ordering = effect.get("atomic_order")
            failure_ordering = None
            if isinstance(ordering, str) and "/" in ordering:
                ordering, failure_ordering = ordering.split("/", 1)
            atomic = ordering not in {None, "not_atomic"}
            guard = effect.get("guard")
            normalized.append({
                "id": effect["source"], "source": {"id": effect["source"]},
                "context_id": context,
                "invocation_id": identity({"function": function, "context": context}),
                "kind": effect["kind"],
                "address": {"domain_id": effect.get("object")} if effect.get("object") else {},
                "size_bytes": effect.get("size_bytes"), "atomic": atomic,
                "volatile": bool(effect.get("volatile", False)),
                "ordering": ordering if atomic else None,
                "failure_ordering": failure_ordering,
                "guards": [guard] if guard is not None else [],
                "multiplicity": effect.get("multiplicity", "single"),
                "proof": sorted(set(effect.get("proof", []))),
            })
        normalized.sort(key=lambda item: item["id"])
        summaries.append({
            "kind": "R3FunctionEffectInput", "status": "complete",
            "root": {"artifact_key": artifact, "function_id": function},
            "context_id": context, "effects": normalized,
        })
    return {"kind": "R3EffectSummaryInputView", "status": view["status"],
            "summaries": summaries, "frontier": view["frontier"],
            "semantic_digest": identity(summaries)}


def thread_view(shards):
    selected, frontier = _complete(shards, "thread")
    calls, nodes, edges = [], [], []
    for shard in selected:
        if shard["status"] != "completed":
            continue
        prefix = {"function_id": shard["function_id"], "context_id": shard["context_id"],
                  "artifact_key": shard["artifact_key"]}
        calls.extend([{**deepcopy(item), **prefix} for item in shard["facts"].get("thread_calls", [])])
        nodes.extend([{**deepcopy(item), **prefix} for item in shard["facts"].get("order_nodes", [])])
        edges.extend([{**deepcopy(item), **prefix} for item in shard["facts"].get("order_edges", [])])
    key = lambda item: (item["artifact_key"], item["function_id"], item["context_id"],
                        item.get("source", item.get("id", "")), item.get("target", ""))
    calls.sort(key=key); nodes.sort(key=key); edges.sort(key=key)
    semantic = {"calls": calls, "nodes": nodes, "edges": edges}
    return {"kind": "R3ThreadShardView", "status": "partial" if frontier else "complete",
            **semantic, "frontier": frontier, "semantic_digest": identity(semantic)}


def concurrent_access_view(shards):
    effects = effect_view(shards); threads = thread_view(shards)
    frontier = [*effects["frontier"], *threads["frontier"]]
    accesses = []
    for item in effects["effects"]:
        if item["kind"] in {"read", "write", "rmw", "cas"}:
            accesses.append({"id": identity(item), **deepcopy(item)})
    accesses.sort(key=lambda item: item["id"])
    semantic = {"accesses": accesses, "effect_digest": effects["semantic_digest"],
                "thread_digest": threads["semantic_digest"]}
    return {"kind": "R3ConcurrentAccessInputView", "status": "partial" if frontier else "complete",
            **semantic, "frontier": frontier, "safety": "not_evaluated", "findings": None,
            "semantic_digest": identity(semantic)}


def normalize_semantics(value):
    """Remove only documented operational fields for eager/lazy comparison."""
    ignored = {"cache", "resources", "attempt", "worker", "worker_id", "batch_id",
               "schedule_index", "cache_hit", "cpu_seconds", "wall_seconds", "peak_rss_bytes",
               "output_bytes", "started_at", "finished_at", "semantic_digest"}
    if isinstance(value, dict):
        return {key: normalize_semantics(item) for key, item in sorted(value.items()) if key not in ignored}
    if isinstance(value, list):
        normalized = [normalize_semantics(item) for item in value]
        if all(isinstance(item, dict) and "id" in item for item in normalized):
            normalized.sort(key=lambda item: item["id"])
        return normalized
    return value


def compare_semantics(eager, lazy):
    left, right = normalize_semantics(eager), normalize_semantics(lazy)
    return {"exact": left == right, "eager_digest": identity(left), "lazy_digest": identity(right)}


def eager_function_view(module_facts, function_id):
    """Project one demanded function from P1 v2 without treating it as an R3 shard."""
    function = next(item for item in module_facts["functions"] if item["id"] == function_id)
    prefix = function_id + ":b"
    events = [item for item in module_facts["events"] if item["function"] == function_id]
    calls = [item for item in module_facts["calls"] if item["function"] == function_id]
    terminators = [block["terminator"] for block in function["blocks"]]
    instruction_ids = {item["id"] for item in module_facts["values"] if item["id"].startswith(prefix)}
    instruction_ids.update(item["id"] for item in events)
    instruction_ids.update(item["id"] for item in calls)
    instruction_ids.update(item["id"] for item in terminators)
    kind = {"load": "read", "store": "write", "atomicrmw": "rmw", "cmpxchg": "cas"}
    accesses = [{"id": item["id"], "kind": kind.get(item["kind"], item["kind"]),
                 "atomic_order": item["ordering"]} for item in events]
    return {
        "function": {"id": function["id"], "name": function["name"], "linkage": function["linkage"]},
        "blocks": [{"id": item["id"], "successors": item["successors"]} for item in function["blocks"]],
        "instructions": sorted(instruction_ids),
        "accesses": sorted(accesses, key=lambda item: item["id"]),
        "calls": sorted([{"id": item["id"], "target_name": item["target"]} for item in calls],
                        key=lambda item: item["id"]),
        "returns": sorted(item["id"] for item in terminators if item["opcode"] == "ret"),
    }


def lazy_function_view(shards, function_id, context_id):
    """Normalize complete R3 layer shards to the same demanded-function projection."""
    selected = {(item["layer"]): item for item in shards
                if item["function_id"] == function_id and item["context_id"] == context_id}
    if set(selected) != {"semantic", "effect", "thread"} or \
            any(item["status"] != "completed" for item in selected.values()):
        return {"status": "partial", "frontier": [diagnostic(
            "missing-function-shard", "函数层 shard 不完整，无法比较 eager/lazy",
            "Function-layer shards are incomplete; eager/lazy comparison is unavailable",
            function_id=function_id, context_id=context_id)]}
    semantic = selected["semantic"]["facts"]
    effect = selected["effect"]["facts"]
    thread = selected["thread"]["facts"]
    accesses = [item for item in semantic["accesses"] if item["kind"] != "call"]
    view = {
        "function": {key: semantic["function"][key] for key in ("id", "name", "linkage")},
        "blocks": semantic["blocks"],
        "instructions": sorted(item["id"] for item in semantic["instructions"]),
        "accesses": sorted([{"id": item["id"], "kind": item["kind"],
                             "atomic_order": item["atomic_order"]} for item in accesses],
                           key=lambda item: item["id"]),
        "calls": sorted([{"id": item["id"], "target_name": item["target_name"]}
                         for item in semantic["calls"]], key=lambda item: item["id"]),
        "returns": sorted(item["source"] for item in semantic["returns"]),
    }
    effect_ids = {item["source"] for item in effect["effects"] if item["kind"] != "call"}
    thread_ids = {item["id"] for item in thread["order_nodes"]}
    demanded_ids = {item["id"] for item in view["accesses"]} | {item["id"] for item in view["calls"]}
    view["layer_consistency"] = {
        "effect_accesses": effect_ids == {item["id"] for item in view["accesses"]},
        "thread_order": demanded_ids <= thread_ids,
    }
    return {"status": "complete", "view": view, "frontier": []}
