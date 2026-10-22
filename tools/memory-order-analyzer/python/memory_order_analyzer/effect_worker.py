"""Independent bounded P2 metadata and local evaluation batch transports."""

import json
from copy import deepcopy

from .contracts import AnalysisError, canonical, identity
from .effect_contracts import effect_document, expected_analysis_protocol, validate_effect_document
from .effect_references import require
from .execution import run


def check_analysis_worker(worker, cwd, *, runner=run):
    result = runner([str(worker), "--analysis-protocol"], str(cwd), timeout=10)
    try:
        valid = result["status"] == "completed" and canonical(json.loads(result["stdout"])) == canonical(expected_analysis_protocol())
    except (ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise AnalysisError("analysis_worker_protocol", "Worker analysis/LLVM/policy mismatch; rebuild the worker")
    return expected_analysis_protocol()


def analyze_metadata(inputs, worker, store, *, budgets=None, runner=run):
    """Return explicit per-member results; metadata partial is not semantic success.

    Control errors have a small independent JSON envelope. A transport failure
    never turns missing results into empty LocalAnalysisFacts.
    """
    protocol = check_analysis_worker(worker, store.root, runner=runner)
    budgets = protocol["budgets"] if budgets is None else budgets
    # Reuse the request contract's budget checks without choosing implicit roots.
    effect_document("EffectAnalysisRequest", scope="explicit-input-snapshot", mode="all-defined", roots=[], budgets=budgets)
    inputs.recheck()
    jobs = []
    for key in sorted(inputs.scope["members"]):
        artifact, facts = inputs.artifacts[key], inputs.modules[key]
        jobs.append({"id": key, "path": artifact["path"], "budgets": budgets, "origin": {
            "artifact_key": key, "module_hash": artifact["sha256"], "facts_hash": identity(facts),
            "extractor_version": facts["protocol"]["extractor_version"], "llvm_version": facts["protocol"]["llvm_version"],
            "profile": artifact["profile"]}})
    def consume(job, value):
        value = inputs.consume(value)
        require(value["kind"] == "LocalAnalysisFacts" and value["origin"] == job["origin"] and value["budgets"] == budgets,
                "Worker result does not match its request")
    return _batch(inputs, worker, store, protocol, jobs, budgets, "--local-batch", consume, runner)


def evaluate_batch(inputs, requests, worker, store, *, local_facts, summaries=None, runner=run):
    """Dispatch explicitly planned contexts, preserving not_run and job failures.

    Dependency validation is independent of whether the current worker can use a
    callee's semantics. No request/result is a claim that CFG transfers completed.
    """
    require(isinstance(requests, list) and bool(requests), "Evaluation needs a nonempty request plan")
    for item in [*local_facts.values(), *(summaries or {}).values()]:
        validate_effect_document(item, item.get("kind") if isinstance(item, dict) else None)
    local_facts, summaries = deepcopy(local_facts), deepcopy(summaries or {})
    jobs = []
    for request in requests:
        validate_effect_document(request, "LocalEvaluationRequest")
        validated = inputs.consume(request, local_facts=local_facts, summaries=summaries)
        key = validated["function"]["artifact_key"]
        jobs.append(dict(id=identity(validated), path=inputs.artifacts[key]["path"], request=validated,
                         summaries=[deepcopy(item) for _, item in sorted(summaries.items())]))
    budgets = jobs[0]["request"]["budgets"]
    require(all(job["request"]["budgets"] == budgets for job in jobs), "Mixed evaluation batch budgets")
    require(len({job["id"] for job in jobs}) == len(jobs), "Duplicate evaluation request")
    protocol = check_analysis_worker(worker, store.root, runner=runner)
    def consume(job, value):
        inputs.consume_evaluation(job["request"], value, local_facts=local_facts, summaries=summaries)
    return _batch(inputs, worker, store, protocol, jobs, budgets, "--evaluate-batch", consume, runner)


def _batch(inputs, worker, store, protocol, jobs, budgets, operation, consume, runner):
    request = canonical({"protocol": protocol, "jobs": jobs})
    require(len(jobs) <= budgets["contexts_per_request"] and len(request.encode()) <= 16777216, "Batch request exceeds transport budget")
    with store.temporary() as directory:
        path = directory / "batch.json"
        path.write_text(request, encoding="utf-8")
        result = runner([str(worker), operation, str(path)], str(directory),
                        timeout=budgets["worker_seconds"], log_limit=budgets["worker_output_bytes"])
    inputs.recheck()
    if result["status"] != "completed":
        raise AnalysisError(result["code"], "Analysis worker failed: " + result["stderr"])
    try:
        response = json.loads(result["stdout"])
    except (ValueError, TypeError, RecursionError) as exc:
        raise AnalysisError("analysis_worker_output", "Invalid analysis worker JSON") from exc
    require(isinstance(response, dict) and set(response) == {"protocol_version", "results", "error"}, "Invalid batch response fields")
    require(type(response["protocol_version"]) is int and response["protocol_version"] == 1 and response["error"] is None,
            "Invalid batch response version/error")
    entries = response["results"]
    require(isinstance(entries, list) and len(entries) == len(jobs), "Incomplete batch result plan")
    planned, found = {job["id"]: job for job in jobs}, {}
    for entry in entries:
        require(isinstance(entry, dict) and set(entry) == {"id", "result", "error"}, "Invalid batch result")
        key = entry["id"]
        require(isinstance(key, str) and key in planned and key not in found, "Foreign or duplicate batch result")
        require((entry["result"] is None) != (entry["error"] is None), "Result must contain exactly one outcome")
        if entry["result"] is not None:
            consume(planned[key], entry["result"])
        else:
            error = entry["error"]
            require(isinstance(error, dict) and set(error) == {"code", "detail"} and
                    all(isinstance(error[k], str) and error[k] for k in error), "Invalid member failure")
        found[key] = entry
    inputs.recheck()
    return {key: found[key] for key in sorted(found)}
