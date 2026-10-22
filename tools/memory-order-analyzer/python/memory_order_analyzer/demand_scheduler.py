"""Deterministic artifact batches and isolated R3 worker execution."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, canonical, identity
from .execution import OutputStore, run
from .demand_contracts import expected_demand_protocol


def plan_batches(nodes, members, budgets):
    members_by_artifact = {item["artifact_key"]: item for item in members}
    grouped = {}
    for node in nodes:
        if node["state"] != "demanded":
            continue
        grouped.setdefault(node["artifact_key"], []).append(node)
    batches = []
    size = budgets["functions_per_batch"]
    for artifact in sorted(grouped):
        member = members_by_artifact.get(artifact)
        if member is None or member["bc_digest"] is None:
            continue
        ordered = sorted(grouped[artifact], key=lambda item: (item["function_id"], item["context_id"], item["layers"]))
        for offset in range(0, len(ordered), size):
            values = ordered[offset:offset + size]
            batch_id = identity({"artifact": artifact, "demands": [item["id"] for item in values]})
            batches.append({"id": batch_id, "artifact_key": artifact, "member": member,
                            "nodes": values, "schedule_index": len(batches)})
    return batches


def plan_index_batches(members, skip=()):
    skipped = set(skip)
    batches = []
    for member in sorted(members, key=lambda item: item["artifact_key"]):
        if member["artifact_key"] in skipped or member["bc_digest"] is None:
            continue
        batch_id = identity({"artifact": member["artifact_key"], "stage": "index"})
        batches.append({"id": batch_id, "artifact_key": member["artifact_key"], "member": member,
                        "nodes": [], "schedule_index": len(batches)})
    return batches


def worker_job(batch, artifact_path, budgets):
    member = batch["member"]
    demands = [{"function_id": item["function_id"], "function_name": item["function_name"],
                "context_id": item["context_id"], "layers": sorted(item["layers"])}
               for item in batch["nodes"]]
    demands.sort(key=lambda item: (item["function_id"], item["context_id"]))
    return {
        "id": batch["id"], "path": str(artifact_path), "artifact_key": member["artifact_key"],
        "bc_digest": member["bc_digest"], "physical_tu_id": member["physical_tu_id"],
        "profile_id": member["profile_id"], "target": member["target"],
        "data_layout": member["data_layout"], "abi": member["abi"],
        "demands": demands, "budgets": budgets,
    }


def _execute(batch, artifact_path, worker, store, budgets, runner):
    started = monotonic()
    request = {"protocol": expected_demand_protocol(),
               "jobs": [worker_job(batch, artifact_path, budgets)]}
    with store.temporary() as temporary:
        path = temporary / "request.json"
        path.write_text(canonical(request) + "\n", encoding="utf-8")
        result = runner([str(worker), "--demand-batch", str(path)], str(temporary),
                        timeout=budgets["worker_seconds"], log_limit=budgets["worker_output_bytes"])
    attempt = {
        "attempt": identity({"batch": batch["id"], "schedule": batch["schedule_index"]}),
        "batch_id": batch["id"], "artifact_key": batch["artifact_key"],
        "schedule_index": batch["schedule_index"], "status": result["status"],
        "exit_code": result["exit_code"], "code": result["code"],
        "wall_seconds": monotonic() - started,
    }
    if result["status"] != "completed":
        return batch, None, {**attempt, "detail": result["stderr"] or result["code"] or "worker failed"}
    try:
        output = json.loads(result["stdout"])
        if output.get("error") is not None or output.get("protocol_version") != 1 or len(output.get("results", [])) != 1:
            raise ValueError("invalid worker envelope")
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return batch, None, {**attempt, "status": "failed", "code": "invalid-worker-output", "detail": str(exc)}
    entry = output["results"][0]
    if entry.get("id") != batch["id"]:
        return batch, None, {**attempt, "status": "failed", "code": "invalid-worker-output", "detail": "batch id mismatch"}
    if entry.get("error") is not None:
        return batch, entry, {**attempt, "status": "failed", "code": entry["error"].get("code"),
                              "detail": entry["error"].get("detail")}
    metrics = entry.setdefault("metrics", {})
    metrics["wall_seconds"] = attempt["wall_seconds"]
    for field in ("cpu_seconds", "peak_rss_bytes", "output_bytes"):
        metrics[field] = result.get(field, metrics.get(field, 0))
    return batch, entry, {**attempt, "status": "completed", "code": None, "detail": None,
                          "metrics": metrics}


def execute_batches(batches, artifact_paths, worker, output, budgets, *, runner=run):
    store = OutputStore(output)
    if not batches:
        return [], []
    results, attempts = [], []
    max_workers = min(budgets["workers"], len(batches))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pending = {pool.submit(_execute, batch, artifact_paths[batch["artifact_key"]], worker,
                               store, budgets, runner): batch for batch in batches}
        for future in as_completed(pending):
            try:
                batch, entry, attempt = future.result()
            except Exception as exc:  # executor/runtime isolation, not semantic analysis
                batch = pending[future]
                entry = None
                attempt = {"attempt": identity({"batch": batch["id"], "exception": type(exc).__name__}),
                           "batch_id": batch["id"], "artifact_key": batch["artifact_key"],
                           "schedule_index": batch["schedule_index"], "status": "failed",
                           "exit_code": None, "code": "worker-crash", "detail": str(exc), "wall_seconds": 0.0}
            results.append((batch, entry)); attempts.append(attempt)
    results.sort(key=lambda item: item[0]["schedule_index"])
    attempts.sort(key=lambda item: item["schedule_index"])
    return results, attempts
