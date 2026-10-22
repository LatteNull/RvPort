"""Offline orchestration for R3 demand-driven function analysis."""

from copy import deepcopy
from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, file_hash, identity, read_document
from .demand_adapters import concurrent_access_view, effect_view, thread_view
from .demand_cache import DemandAnalysisCache, cache_key
from .demand_contracts import (
    LAYERS, demand_document, dependency, diagnostic, read_demand_document,
)
from .demand_graph import expand_demands, graph_counts, normalized_nodes, seed_demands
from .demand_scheduler import execute_batches, plan_batches, plan_index_batches
from .execution import OutputStore
from .pipeline import write_json
from .root_contracts import read_root_document
from .thread_entry_contracts import read_thread_entry_document


def _resolve_evidence(store, reference):
    root = Path(store).resolve()
    path = (root / reference["path"]).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AnalysisError("invalid_reference", "R3 evidence path escapes the artifact store") from exc
    if not path.is_file():
        raise AnalysisError("invalid_reference", f"R3 evidence is missing: {reference['path']}")
    if reference["kind"] == "RootDrivenAnalysisPlan":
        value = read_root_document(path, reference["kind"])
    elif reference["kind"] == "ThreadEntryRootOverlay":
        value = read_thread_entry_document(path, reference["kind"])
    else:
        raise AnalysisError("invalid_reference", f"Unsupported R3 evidence kind: {reference['kind']}")
    if value.get("schema_version") != reference["schema_version"] or \
            value.get("policy_id") != reference["producer"] or identity(value) != reference["digest"]:
        raise AnalysisError("invalid_reference", f"R3 evidence identity changed: {reference['path']}")
    return value


def _load_inputs(request, artifact_store):
    resolved = {item["kind"]: _resolve_evidence(artifact_store, item) for item in request["evidence"]}
    root = Path(artifact_store).resolve()
    paths = {}
    for member in request["members"]:
        if member["bc_digest"] is None:
            continue
        key = member["artifact_key"]
        manifest_path = root / "artifacts" / f"{key}.json"
        artifact = read_document(manifest_path, "BCArtifact")
        if artifact["artifact_key"] != key or artifact["sha256"] != member["bc_digest"]:
            raise AnalysisError("lineage_conflict", f"R3 BC manifest identity changed: {key}")
        canonical_path = root / "artifacts" / f"{key}.bc"
        path = canonical_path if canonical_path.is_file() else Path(artifact["path"])
        if not path.is_file() or file_hash(path) != member["bc_digest"]:
            raise AnalysisError("artifact_missing", f"R3 BC is missing or changed: {key}")
        paths[key] = path.resolve()
    return resolved["RootDrivenAnalysisPlan"], resolved["ThreadEntryRootOverlay"], paths


def _deduplicate_frontier(items, limit):
    result, seen = [], set()
    for item in sorted(items, key=lambda value: (value["code"], value.get("artifact_key") or "",
                                                  value.get("function_id") or "", value.get("context_id") or "",
                                                  value.get("layer") or "", value.get("attempt") or "")):
        key = identity(item)
        if key not in seen:
            seen.add(key); result.append(item)
        if len(result) == limit:
            break
    return result


def _cache_lookup(cache, request, member, node, shards, hits):
    loaded = []
    for layer in node["layers"]:
        key = cache_key(
            bc_digest=member["bc_digest"], profile_id=member["profile_id"], target=member["target"],
            data_layout=member["data_layout"], function_id=node["function_id"], layer=layer,
            context_id=node["context_id"], policy_id=request["policy_id"], budgets=request["budgets"])
        kind = LAYERS[layer]
        value = cache.load(layer, key, kind)
        if value is None:
            return False
        loaded.append(value)
    for value in loaded:
        shards[(value["function_id"], value["context_id"], value["layer"])] = value
    hits[0] += len(loaded)
    node["state"] = "completed"
    return True


def _wrap_index(request, member, raw):
    return demand_document(
        "LLVMModuleIndexFacts", artifact_key=raw["artifact_key"], physical_tu_id=raw["physical_tu_id"],
        bc_digest=raw["bc_digest"], profile_id=raw["profile_id"], target=raw["target"],
        data_layout=raw["data_layout"], abi=raw["abi"], status="complete",
        symbols=raw["symbols"], source_bindings=raw.get("source_bindings", []), counts=raw["counts"],
        dependencies=[dependency("DemandDrivenAnalysisRequest", request["scope_id"], request)],
        diagnostics=[], frontier=[], semantic_digest=None)


def _wrap_shard(request, member, index, raw, attempt):
    status = raw["status"]
    frontier = []
    if status != "completed":
        error = raw.get("error") or {"code": "function-shard-failed", "detail": "unknown function shard failure"}
        frontier.append(diagnostic(
            error["code"], "函数分析 shard 未完整完成", "The function-analysis shard did not complete",
            suggestion=error.get("detail"), suggestion_en=error.get("detail"),
            artifact_key=member["artifact_key"], function_id=raw["function_id"],
            context_id=raw["context_id"], layer=raw["layer"], attempt=attempt))
    return demand_document(
        LAYERS[raw["layer"]], scope_id=request["scope_id"], artifact_key=member["artifact_key"],
        physical_tu_id=member["physical_tu_id"], bc_digest=member["bc_digest"],
        function_id=raw["function_id"], function_name=raw["function_name"],
        context_id=raw["context_id"], layer=raw["layer"], status=status,
        facts=raw["facts"], counts=raw.get("counts", {}),
        dependencies=[dependency("LLVMModuleIndexFacts", member["artifact_key"], index)],
        diagnostics=deepcopy(frontier), frontier=frontier, semantic_digest=None)


def _worker_frontier(batch, attempt):
    code = attempt.get("code") or "worker-crash"
    reason = "R3 worker 批次失败或超时"
    reason_en = "An R3 worker batch failed or timed out"
    return [diagnostic(code, reason, reason_en, suggestion=attempt.get("detail"),
                       suggestion_en=attempt.get("detail"), artifact_key=batch["artifact_key"],
                       function_id=node["function_id"], context_id=node["context_id"],
                       attempt=attempt["attempt"])
            for node in batch["nodes"]] or [diagnostic(
                code, reason, reason_en, suggestion=attempt.get("detail"), suggestion_en=attempt.get("detail"),
                artifact_key=batch["artifact_key"], attempt=attempt["attempt"])]


def _process(results, attempts, request, members_by_artifact, indexes, shards, nodes, cache, frontier, metrics):
    attempts_by_batch = {item["batch_id"]: item for item in attempts}
    for batch, entry in results:
        attempt = attempts_by_batch[batch["id"]]
        metrics["module_parses"] += int((entry or {}).get("metrics", {}).get("module_parses", 0))
        metrics["materialized_functions"] += int((entry or {}).get("metrics", {}).get("materialized_functions", 0))
        metrics["materialized_instructions"] += int((entry or {}).get("metrics", {}).get("materialized_instructions", 0))
        metrics["analysis_queries"] += int((entry or {}).get("metrics", {}).get("analysis_queries", 0))
        metrics["cpu_seconds"] += float((entry or {}).get("metrics", {}).get("cpu_seconds", 0.0))
        metrics["wall_seconds"] += float(attempt.get("wall_seconds", 0.0))
        metrics["peak_rss_bytes"] = max(metrics["peak_rss_bytes"], int((entry or {}).get("metrics", {}).get("peak_rss_bytes", 0)))
        if entry is None or attempt["status"] != "completed":
            items = _worker_frontier(batch, attempt); frontier.extend(items)
            for node in batch["nodes"]:
                node["state"] = "failed"
            continue
        member = members_by_artifact[batch["artifact_key"]]
        index = _wrap_index(request, member, entry["index"])
        previous = indexes.get(batch["artifact_key"])
        if previous is not None and previous != index:
            raise AnalysisError("index_nondeterministic", f"R3 module index changed within request: {batch['artifact_key']}")
        indexes[batch["artifact_key"]] = index
        for raw in entry["shards"]:
            shard = _wrap_shard(request, member, index, raw, attempt["attempt"])
            key = (shard["function_id"], shard["context_id"], shard["layer"])
            shards[key] = shard
            frontier.extend(shard["frontier"])
            if shard["status"] == "completed":
                key_hash = cache_key(
                    bc_digest=member["bc_digest"], profile_id=member["profile_id"], target=member["target"],
                    data_layout=member["data_layout"], function_id=shard["function_id"], layer=shard["layer"],
                    context_id=shard["context_id"], policy_id=request["policy_id"], budgets=request["budgets"])
                cache.publish(shard["layer"], key_hash, shard)
        for node in batch["nodes"]:
            values = [shards.get((node["function_id"], node["context_id"], layer)) for layer in node["layers"]]
            if any(value is None or value["status"] == "failed" for value in values):
                node["state"] = "failed"
            elif any(value["status"] == "partial" for value in values):
                node["state"] = "partial"
            else:
                node["state"] = "completed"
        exceeded = []
        if float((entry or {}).get("metrics", {}).get("cpu_seconds", 0.0)) > request["budgets"]["cpu_seconds"]:
            exceeded.append(("cpu-budget-exhausted", "worker CPU 预算已耗尽", "The worker CPU budget is exhausted"))
        if int((entry or {}).get("metrics", {}).get("peak_rss_bytes", 0)) > request["budgets"]["rss_bytes"]:
            exceeded.append(("rss-budget-exhausted", "worker RSS 预算已耗尽", "The worker RSS budget is exhausted"))
        if int((entry or {}).get("metrics", {}).get("output_bytes", 0)) > request["budgets"]["worker_output_bytes"]:
            exceeded.append(("worker-output-budget-exhausted", "worker 输出预算已耗尽", "The worker output budget is exhausted"))
        for code, reason, reason_en in exceeded:
            for node in batch["nodes"]:
                if node["state"] == "completed":
                    node["state"] = "partial"
                item = diagnostic(code, reason, reason_en, artifact_key=batch["artifact_key"],
                                  function_id=node["function_id"], context_id=node["context_id"],
                                  attempt=attempt["attempt"])
                frontier.append(item)


def _report(request, graph, manifest, indexes, shards, cache_hits, metrics):
    terminal = {state: sum(node["state"] == state for node in graph["nodes"])
                for state in ("completed", "partial", "failed")}
    demanded = len(graph["nodes"])
    status = "failed" if demanded and terminal["failed"] == demanded else \
             "partial" if graph["frontier"] or manifest["frontier"] or terminal["partial"] or terminal["failed"] else "complete"
    frontier = _deduplicate_frontier([*graph["frontier"], *manifest["frontier"]], request["budgets"]["frontier_items"])
    dependencies = sorted([
        dependency("AnalysisDemandGraph", request["scope_id"], graph),
        dependency("WorkerExecutionManifest", request["scope_id"], manifest),
    ], key=lambda item: (item["kind"], item["id"]))
    indexed = sum(item["counts"].get("defined_functions", 0) for item in indexes.values())
    counts = {"indexed": indexed, "demanded": demanded, "scheduled": metrics["scheduled"],
              "materialized": metrics["materialized_functions"], **terminal,
              "cache_hit": cache_hits, "module_parse": metrics["module_parses"]}
    coverage = {"root": {"planned": demanded, "complete": terminal["completed"],
                           "ratio": terminal["completed"] / demanded if demanded else 0.0},
                "reachable": deepcopy(graph["counts"]),
                "candidate_relevant": {"status": "partial" if frontier else "complete"}}
    resources = {key: metrics[key] for key in ("cpu_seconds", "wall_seconds", "peak_rss_bytes", "output_bytes")}
    return demand_document(
        "DemandDrivenAnalysisReport", scope_id=request["scope_id"], request_hash=identity(request),
        status=status, exit_code=1 if status == "failed" else 2 if status == "partial" else 0,
        safety="not_evaluated", findings=None, demand_graph=dependencies[0], worker_manifest=dependencies[1],
        counts=counts, coverage=coverage, resources=resources,
        cache={"hits": cache_hits, "misses": len(shards) - cache_hits}, dependencies=dependencies,
        diagnostics=deepcopy(frontier), frontier=frontier, semantic_digest=None)


def analyze_demanded_functions(request_path, artifact_store, output, worker,
                               *, runner=None, clock=monotonic):
    started = clock()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "analyze-demanded-functions requires a fresh output directory")
    request = read_demand_document(request_path, "DemandDrivenAnalysisRequest")
    plan, overlay, artifact_paths = _load_inputs(request, artifact_store)
    nodes, edges, frontier = seed_demands(request, plan, overlay)
    members_by_artifact = {item["artifact_key"]: item for item in request["members"]}
    indexes, shards, attempts = {}, {}, []
    cache = DemandAnalysisCache(Path(artifact_store) / "derived")
    cache_hits = [0]
    for node in nodes.values():
        member = members_by_artifact.get(node["artifact_key"])
        if node["state"] == "demanded" and member:
            _cache_lookup(cache, request, member, node, shards, cache_hits)
    metrics = {"scheduled": 0, "module_parses": 0, "materialized_functions": 0,
               "materialized_instructions": 0, "analysis_queries": 0,
               "cpu_seconds": 0.0, "wall_seconds": 0.0, "peak_rss_bytes": 0, "output_bytes": 0}
    initial = plan_batches(list(nodes.values()), request["members"], request["budgets"])
    covered = {item["artifact_key"] for item in initial}
    initial += plan_index_batches(request["members"], covered)
    for index, batch in enumerate(initial): batch["schedule_index"] = index
    if runner is None:
        from .execution import run as runner
    store = OutputStore(output)
    results, round_attempts = execute_batches(initial, artifact_paths, worker, store.root, request["budgets"], runner=runner)
    attempts.extend(round_attempts); metrics["scheduled"] += sum(len(item["nodes"]) for item in initial)
    _process(results, round_attempts, request, members_by_artifact, indexes, shards, nodes,
             cache, frontier, metrics)

    for iteration in range(request["budgets"]["scc_iterations"]):
        for node in list(nodes.values()):
            if node["state"] != "completed" or node.get("expanded"):
                continue
            values = [shards[(node["function_id"], node["context_id"], layer)] for layer in node["layers"]]
            expand_demands(request, node, values, indexes, nodes, edges, frontier)
            node["expanded"] = True
        pending = [node for node in nodes.values() if node["state"] == "demanded"]
        if not pending:
            break
        for node in pending:
            member = members_by_artifact.get(node["artifact_key"])
            if member: _cache_lookup(cache, request, member, node, shards, cache_hits)
        pending = [node for node in nodes.values() if node["state"] == "demanded"]
        batches = plan_batches(pending, request["members"], request["budgets"])
        for index, batch in enumerate(batches, start=len(attempts)): batch["schedule_index"] = index
        results, round_attempts = execute_batches(batches, artifact_paths, worker, store.root, request["budgets"], runner=runner)
        attempts.extend(round_attempts); metrics["scheduled"] += sum(len(item["nodes"]) for item in batches)
        _process(results, round_attempts, request, members_by_artifact, indexes, shards, nodes,
                 cache, frontier, metrics)
    else:
        for node in nodes.values():
            if node["state"] == "demanded":
                node["state"] = "partial"
                frontier.append(diagnostic("recursion-budget", "递归/SCC 迭代预算已耗尽",
                                           "The recursion/SCC iteration budget is exhausted",
                                           artifact_key=node["artifact_key"], function_id=node["function_id"],
                                           context_id=node["context_id"]))

    if clock() - started > request["budgets"]["request_seconds"]:
        frontier.append(diagnostic("request-time-budget-exhausted", "R3 请求时间预算已耗尽",
                                   "The R3 request-time budget is exhausted"))
    if metrics["cpu_seconds"] > request["budgets"]["cpu_seconds"]:
        frontier.append(diagnostic("cpu-budget-exhausted", "R3 请求 CPU 预算已耗尽",
                                   "The R3 request CPU budget is exhausted"))
        for node in nodes.values():
            if node["state"] == "completed": node["state"] = "partial"
    if metrics["peak_rss_bytes"] > request["budgets"]["rss_bytes"]:
        frontier.append(diagnostic("rss-budget-exhausted", "R3 请求 RSS 预算已耗尽",
                                   "The R3 request RSS budget is exhausted"))
        for node in nodes.values():
            if node["state"] == "completed": node["state"] = "partial"
    frontier = _deduplicate_frontier(frontier, request["budgets"]["frontier_items"])
    graph_status = "partial" if frontier or any(node["state"] != "completed" for node in nodes.values()) else "complete"
    index_refs = [dependency("LLVMModuleIndexFacts", key, value) for key, value in sorted(indexes.items())]
    shard_refs = [dependency(value["kind"], f"{value['function_id']}@{value['context_id']}", value)
                  for _, value in sorted(shards.items())]
    graph = demand_document(
        "AnalysisDemandGraph", scope_id=request["scope_id"], request_hash=identity(request),
        status=graph_status, nodes=normalized_nodes(nodes), edges=sorted(edges, key=lambda item: item["id"]),
        counts=graph_counts(nodes), dependencies=sorted([*index_refs, *shard_refs], key=lambda item: (item["kind"], item["id"])),
        diagnostics=deepcopy(frontier), frontier=frontier, semantic_digest=None)
    worker_frontier = _deduplicate_frontier([
        item for item in frontier if item["code"] in {"worker-crash", "timed_out", "nonzero_exit", "invalid-worker-output", "inputs_changed", "reader_failed"}
    ], request["budgets"]["frontier_items"])
    manifest_status = "partial" if worker_frontier else "complete"
    manifest = demand_document(
        "WorkerExecutionManifest", scope_id=request["scope_id"], request_hash=identity(request),
        status=manifest_status, batches=attempts, metrics=deepcopy(metrics),
        dependencies=sorted(index_refs, key=lambda item: (item["kind"], item["id"])),
        diagnostics=deepcopy(worker_frontier), frontier=worker_frontier, semantic_digest=None)
    effect = effect_view(list(shards.values())); thread = thread_view(list(shards.values()))
    r2 = concurrent_access_view(list(shards.values()))
    metrics["output_bytes"] = sum(len(str(value).encode("utf-8")) for value in [*indexes.values(), *shards.values(), graph, manifest])
    report = _report(request, graph, manifest, indexes, shards, cache_hits[0], metrics)
    if metrics["output_bytes"] > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request-output-budget-exhausted", "R3 output exceeds request_output_bytes")
    write_json(store, request, "request.json")
    for key, value in sorted(indexes.items()): write_json(store, value, f"indexes/{key}.json")
    for key, value in sorted(shards.items()):
        write_json(store, value, f"shards/{value['layer']}/{identity(key)}.json")
    write_json(store, graph, "demand-graph.json")
    write_json(store, manifest, "worker-manifest.json")
    write_json(store, {"schema_version": 1, **effect}, "views/effects.json")
    write_json(store, {"schema_version": 1, **thread}, "views/threads.json")
    write_json(store, {"schema_version": 1, **r2}, "views/concurrent-access.json")
    write_json(store, report, "report.json")
    return report


def failed_report(code, detail, detail_en=None):
    item = diagnostic(code, detail, detail_en or detail,
                      suggestion="修复请求、依赖或 worker 后重试",
                      suggestion_en="Fix the request, dependency, or worker and retry")
    return demand_document(
        "DemandDrivenAnalysisReport", scope_id="failed", request_hash="0" * 64,
        status="failed", exit_code=1, safety="not_evaluated", findings=None,
        demand_graph=None, worker_manifest=None,
        counts={"indexed": 0, "demanded": 0, "scheduled": 0, "materialized": 0,
                "completed": 0, "partial": 0, "failed": 0, "cache_hit": 0, "module_parse": 0},
        coverage={}, resources={}, cache={"hits": 0, "misses": 0}, dependencies=[],
        diagnostics=[item], frontier=[item], semantic_digest=None)
