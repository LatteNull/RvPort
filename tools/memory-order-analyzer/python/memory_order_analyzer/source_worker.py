"""Bounded transport for the independent Clang source-semantics worker."""

import json
from pathlib import Path

from .contracts import AnalysisError, canonical, file_hash
from .execution import run
from .source_contracts import expected_source_protocol, semantic_digest, validate_source_document


def check_source_worker(worker, cwd, *, runner=run):
    result = runner([str(worker), "--source-analysis-protocol"], str(cwd), timeout=10)
    try:
        valid = result["status"] == "completed" and canonical(json.loads(result["stdout"])) == canonical(expected_source_protocol())
    except (ValueError, KeyError, TypeError, RecursionError):
        valid = False
    if not valid:
        raise AnalysisError("source_worker_protocol", "Source worker Clang/LLVM/policy mismatch; rebuild the worker")
    return expected_source_protocol()


def analyze_source(request, worker, directory, *, runner=run):
    validate_source_document(request, "SourceSemanticRequest")
    check_source_worker(worker, directory, runner=runner)
    path = Path(directory) / f"source-request-{request['physical_tu_id']}.json"
    path.write_text(canonical(request), encoding="utf-8")
    try:
        result = runner([str(worker), "--source-request", str(path)], str(directory),
                        timeout=request["budgets"]["worker_seconds"],
                        log_limit=request["budgets"]["worker_output_bytes"])
    finally:
        path.unlink(missing_ok=True)
    if result["status"] != "completed":
        raise AnalysisError(result.get("code") or "source_worker_failed",
                            "Source worker failed: " + result.get("stderr", ""))
    try:
        value = json.loads(result["stdout"])
    except (ValueError, TypeError, RecursionError) as exc:
        raise AnalysisError("source_worker_output", "Invalid source worker JSON") from exc
    if isinstance(value, dict) and "semantic_digest" not in value:
        value["semantic_digest"] = None
        value["semantic_digest"] = semantic_digest(value)
    facts = validate_source_document(value, "SourceSemanticFacts")
    if facts["profile_id"] != request["profile"]["profile_id"] or facts["physical_tu_id"] != request["physical_tu_id"] or facts["source_digest"] != request["profile"]["source"]["sha256"]:
        raise AnalysisError("source_worker_identity", "Source worker result does not match requested profile/TU/source")
    return facts


def analyze_ir_binding(request, worker, directory, *, runner=run):
    """Extract typed LLVM symbol evidence without changing ModuleFacts v2."""
    validate_source_document(request, "LLVMSourceBindingRequest")
    check_source_worker(worker, directory, runner=runner)
    bitcode = request["bitcode"]
    if file_hash(bitcode["path"]) != bitcode["sha256"]:
        raise AnalysisError("bitcode_digest", "LLVM binding bitcode is missing or changed")
    path = Path(directory) / f"ir-binding-request-{request['artifact_key']}.json"
    path.write_text(canonical(request), encoding="utf-8")
    try:
        result = runner([str(worker), "--ir-binding-request", str(path)], str(directory),
                        timeout=request["budgets"]["worker_seconds"],
                        log_limit=request["budgets"]["worker_output_bytes"])
    finally:
        path.unlink(missing_ok=True)
    if result["status"] != "completed":
        raise AnalysisError(result.get("code") or "ir_binding_worker_failed",
                            "LLVM binding worker failed: " + result.get("stderr", ""))
    try:
        value = json.loads(result["stdout"])
    except (ValueError, TypeError, RecursionError) as exc:
        raise AnalysisError("ir_binding_worker_output", "Invalid LLVM binding worker JSON") from exc
    if isinstance(value, dict) and "semantic_digest" not in value:
        value["semantic_digest"] = None
        value["semantic_digest"] = semantic_digest(value)
    facts = validate_source_document(value, "LLVMSourceBindingFacts")
    expected = (request["artifact_key"], request["profile_id"], request["physical_tu_id"], bitcode["sha256"])
    actual = (facts["artifact_key"], facts["profile_id"], facts["physical_tu_id"], facts["bitcode_digest"])
    if actual != expected:
        raise AnalysisError("ir_binding_worker_identity", "LLVM binding result does not match the request")
    return facts
