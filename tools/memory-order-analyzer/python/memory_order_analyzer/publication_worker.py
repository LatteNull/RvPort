"""Bounded transport for independent P4 LLVM publication sidecars."""

import json

from .contracts import AnalysisError, canonical, identity
from .effect_references import require
from .execution import run
from .publication_contracts import expected_publication_protocol, validate_publication_document


def check_publication_worker(worker, cwd, *, runner=run):
    result = runner([str(worker), "--publication-analysis-protocol"], str(cwd), timeout=10)
    try:
        valid = (result["status"] == "completed" and
                 canonical(json.loads(result["stdout"])) == canonical(expected_publication_protocol()))
    except (ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise AnalysisError("publication_worker_protocol", "Worker publication/LLVM/policy mismatch; rebuild the worker")
    return expected_publication_protocol()


def analyze_publication_facts(inputs, worker, store, *, budgets=None, runner=run):
    protocol = check_publication_worker(worker, store.root, runner=runner)
    budgets = protocol["budgets"] if budgets is None else budgets
    jobs = []
    inputs.recheck()
    for key in sorted(inputs.scope["members"]):
        artifact, facts = inputs.artifacts[key], inputs.modules[key]
        jobs.append({"id": key, "path": artifact["path"], "budgets": budgets, "origin": {
            "artifact_key": key, "module_hash": artifact["sha256"], "facts_hash": identity(facts),
            "extractor_version": facts["protocol"]["extractor_version"],
            "llvm_version": facts["protocol"]["llvm_version"], "profile": artifact["profile"],
        }})
    require(len(jobs) <= budgets["protocol_candidates"], "Publication member plan exceeds candidate budget")
    request = canonical({"protocol": protocol, "jobs": jobs})
    require(len(request.encode()) <= 16777216, "Publication batch request exceeds transport budget")
    with store.temporary() as directory:
        path = directory / "publication-batch.json"
        path.write_text(request, encoding="utf-8")
        result = runner([str(worker), "--publication-batch", str(path)], str(directory),
                        timeout=budgets["worker_seconds"], log_limit=budgets["worker_output_bytes"])
    inputs.recheck()
    if result["status"] != "completed":
        raise AnalysisError(result["code"], "Publication analysis worker failed: " + result["stderr"])
    try:
        response = json.loads(result["stdout"])
    except (ValueError, TypeError, RecursionError) as exc:
        raise AnalysisError("publication_worker_output", "Invalid publication worker JSON") from exc
    require(isinstance(response, dict) and set(response) == {"protocol_version", "results", "error"},
            "Invalid publication batch response fields")
    require(type(response["protocol_version"]) is int and response["protocol_version"] == 1 and response["error"] is None,
            "Invalid publication batch response version/error")
    require(isinstance(response["results"], list) and len(response["results"]) == len(jobs),
            "Incomplete publication batch result plan")
    planned, found = {job["id"]: job for job in jobs}, {}
    for entry in response["results"]:
        require(isinstance(entry, dict) and set(entry) == {"id", "result", "error"},
                "Invalid publication batch result")
        key = entry["id"]
        require(isinstance(key, str) and key in planned and key not in found,
                "Foreign or duplicate publication result")
        require((entry["result"] is None) != (entry["error"] is None),
                "Publication result must contain one outcome")
        if entry["result"] is not None:
            local = validate_publication_document(entry["result"], "PublicationLocalFacts")
            require(local["origin"] == planned[key]["origin"], "Publication worker origin mismatch")
            require(local["budgets"] == budgets, "Publication worker budget mismatch")
        else:
            error = entry["error"]
            require(isinstance(error, dict) and set(error) == {"code", "detail"} and
                    all(isinstance(error[name], str) and error[name] for name in error),
                    "Invalid publication member failure")
        found[key] = entry
    inputs.recheck()
    return {key: found[key] for key in sorted(found)}
