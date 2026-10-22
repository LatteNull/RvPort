"""Versioned contracts for R3 demand-driven function analysis sidecars."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/demand_driven_analysis.json"
PROTOCOL = ROOT / "protocols/demand-driven-analysis-protocol.json"
KINDS = (
    "DemandDrivenAnalysisRequest", "LLVMModuleIndexFacts", "FunctionSemanticFacts",
    "FunctionEffectFacts", "FunctionThreadFacts", "AnalysisDemandGraph",
    "WorkerExecutionManifest", "DemandDrivenAnalysisReport",
)
LAYERS = {"semantic": "FunctionSemanticFacts", "effect": "FunctionEffectFacts",
          "thread": "FunctionThreadFacts"}
REQUIRED_EVIDENCE = {"RootDrivenAnalysisPlan", "ThreadEntryRootOverlay"}
NODE_STATES = ("indexed", "demanded", "scheduled", "materialized", "completed", "partial", "failed")
OPERATIONAL_FIELDS = {
    "attempt", "worker", "worker_id", "batch_id", "schedule_index", "cache_hit",
    "cpu_seconds", "wall_seconds", "peak_rss_bytes", "output_bytes", "started_at",
    "finished_at", "module_parses", "cache_hits", "cache_misses",
    "scheduled", "materialized", "cache_hit", "cache-hit", "module_parse",
}


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_demand_protocol(path=PROTOCOL):
    value = _load(path, "demand_protocol")
    schema = _load(SCHEMA, "demand_schema")
    maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
    expected = {
        "protocol_version": 1, "analysis_version": "0.1.0", "llvm_version": "21.1.8",
        "policy_id": "demand-driven-function-analysis-v1",
        "cache_namespace": "demand-driven-function-analysis-v1",
        "kinds": dict.fromkeys(KINDS, 1), "budgets": maxima,
    }
    if value != expected:
        raise AnalysisError("demand_protocol", "R3 protocol and schema maxima disagree")
    return value


def dependency(kind, key, value):
    # R3 references bind semantic content. Operational scheduling/cache metrics are
    # deliberately excluded so cold and warm executions have the same meaning.
    return {"kind": str(kind), "id": str(key),
            "digest": value.get("semantic_digest") or identity(value)}


def diagnostic(code, reason, reason_en, *, suggestion=None, suggestion_en=None,
               artifact_key=None, root_id=None, function_id=None, context_id=None,
               layer=None, attempt=None, limit=4096):
    def bounded(value):
        value = str(value)
        while value and len(value.encode("utf-8")) > limit:
            value = value[:-1]
        return value or "-"
    return {
        "code": str(code), "reason": bounded(reason), "reason_en": bounded(reason_en),
        "suggestion": bounded(suggestion) if suggestion is not None else None,
        "suggestion_en": bounded(suggestion_en) if suggestion_en is not None else None,
        "artifact_key": artifact_key, "root_id": root_id, "function_id": function_id,
        "context_id": context_id, "layer": layer, "attempt": attempt,
    }


def _without_operational(value):
    if isinstance(value, dict):
        return {key: _without_operational(item) for key, item in value.items()
                if key not in OPERATIONAL_FIELDS and key not in {"resources", "cache"}}
    if isinstance(value, list):
        return [_without_operational(item) for item in value]
    return value


def semantic_digest(value):
    clean = deepcopy(value)
    clean.pop("semantic_digest", None)
    if clean.get("kind") == "WorkerExecutionManifest":
        clean.pop("batches", None)
        clean.pop("metrics", None)
    return identity(_without_operational(clean))


def _unique_sorted(items, key, detail):
    values = [key(item) for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _dependencies(items):
    return _unique_sorted(items, lambda item: (item["kind"], item["id"]),
                          "R3 dependencies must be unique and sorted")


def _validate_request(value):
    _unique_sorted(value["members"], lambda item: item["physical_tu_id"],
                   "R3 request members must be unique and sorted")
    evidence = _unique_sorted(value["evidence"], lambda item: (item["kind"], item["id"]),
                              "R3 request evidence must be unique and sorted")
    missing = REQUIRED_EVIDENCE - {kind for kind, _ in evidence}
    if missing:
        raise AnalysisError("invalid_reference", f"R3 request is missing required evidence: {sorted(missing)}")
    if len(value["members"]) > value["budgets"]["translation_units"]:
        raise AnalysisError("translation-unit-budget", "R3 request exceeds translation unit budget")
    if value["layers"] != sorted(value["layers"]):
        raise AnalysisError("schema_invalid", "R3 layers must be sorted")
    for reference in value["evidence"]:
        path = Path(reference["path"])
        if path.is_absolute() or ".." in path.parts:
            raise AnalysisError("invalid_reference", "R3 evidence paths must remain relative to the artifact store")
    for member in value["members"]:
        allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if member["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
        if member["standard"] not in allowed:
            raise AnalysisError("profile_conflict", "R3 member language and standard disagree")
        if "windows" in member["target"].lower() or "msvc" in member["abi"].lower() or \
                "clang-cl" in member["profile_id"].lower():
            raise AnalysisError("unsupported_profile", "R3 excludes Windows, MSVC, and clang-cl")
        has_ir = member["evidence_mode"] in {"ast+ir", "ir-only"}
        if has_ir != (member["bc_digest"] is not None):
            raise AnalysisError("lineage_conflict", "R3 IR availability and BC digest disagree")
        if member["language"] == "c" and any(token in member["profile_id"].lower()
                                              for token in ("libstdc++", "libc++", "cxx")):
            raise AnalysisError("profile_conflict", "R3 C members cannot depend on a C++ standard-library profile")
        for field in ("target", "data_layout", "abi"):
            if member[field] != value[field]:
                raise AnalysisError("profile_conflict", f"R3 member {field} disagrees with request")


def _validate_output(value):
    _dependencies(value.get("dependencies", []))
    if value.get("status") in {"complete", "completed"} and value.get("frontier"):
        raise AnalysisError("completeness_invalid", "Complete R3 artifacts cannot retain a frontier")
    if value.get("status") in {"partial", "failed"} and not value.get("frontier"):
        raise AnalysisError("completeness_invalid", "Partial or failed R3 artifacts require a frontier")


def _validate_index(value):
    _validate_output(value)
    _unique_sorted(value["symbols"], lambda item: item["id"],
                   "R3 module symbols must be unique and sorted")
    if value["counts"].get("materialized_functions") != 0 or \
            value["counts"].get("materialized_instructions") != 0:
        raise AnalysisError("eager_materialization", "R3 module indexing must not materialize function bodies")


def _validate_shard(value):
    _validate_output(value)
    expected = LAYERS.get(value["layer"])
    if value["kind"] != expected:
        raise AnalysisError("schema_invalid", "R3 shard kind and analysis layer disagree")
    if value["status"] == "completed" and not value["facts"].get("reference_closed", False):
        raise AnalysisError("invalid_reference", "Completed R3 shards must have a closed reference set")


def _validate_graph(value):
    _validate_output(value)
    _unique_sorted(value["nodes"], lambda item: item["id"], "R3 demand nodes must be unique and sorted")
    _unique_sorted(value["edges"], lambda item: item["id"], "R3 demand edges must be unique and sorted")
    node_ids = {item["id"] for item in value["nodes"]}
    for node in value["nodes"]:
        if node.get("state") not in NODE_STATES:
            raise AnalysisError("state_invalid", "R3 demand node has an invalid state")
    for edge in value["edges"]:
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            raise AnalysisError("invalid_reference", "R3 demand edge refers to an unknown node")


def _validate_report(value):
    _validate_output(value)
    expected = 1 if value["status"] == "failed" else 2 if value["status"] == "partial" else 0
    if value["exit_code"] != expected:
        raise AnalysisError("report_status", "R3 report exit code does not match completeness")
    if value["safety"] != "not_evaluated" or value["findings"] is not None:
        raise AnalysisError("safety_claim", "R3 cannot publish findings or safety conclusions")
    declared = _dependencies(value["dependencies"])
    for field in ("demand_graph", "worker_manifest"):
        reference = value[field]
        if reference is not None and (reference["kind"], reference["id"]) not in declared:
            raise AnalysisError("invalid_reference", f"R3 report {field} is missing from dependencies")
    counts = value["counts"]
    if {"demanded", "completed", "partial", "failed"} <= counts.keys() and \
            counts["demanded"] != counts["completed"] + counts["partial"] + counts["failed"]:
        raise AnalysisError("count_mismatch", "R3 terminal demand counts do not equal demanded count")


def validate_demand_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown R3 contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    schema = _load(SCHEMA, "demand_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "DemandDrivenAnalysisRequest":
        _validate_request(value)
    elif kind == "LLVMModuleIndexFacts":
        _validate_index(value)
    elif kind in set(LAYERS.values()):
        _validate_shard(value)
    elif kind == "AnalysisDemandGraph":
        _validate_graph(value)
    elif kind == "DemandDrivenAnalysisReport":
        _validate_report(value)
    else:
        _validate_output(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def demand_document(kind, **fields):
    protocol = expected_demand_protocol()
    result = {"schema_version": 1, "kind": kind,
              "analysis_version": protocol["analysis_version"],
              "policy_id": protocol["policy_id"], **fields}
    if result.get("semantic_digest") is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_demand_document(result, kind)


def read_demand_document(path, kind):
    return validate_demand_document(_load(path, "input_invalid"), kind)


def validate_reference_closure(root_key, documents):
    visiting, complete = set(), set()
    def visit(key):
        if key in visiting:
            raise AnalysisError("dependency_cycle", f"R3 dependency cycle includes {key[0]}:{key[1]}")
        if key in complete:
            return
        if key not in documents:
            raise AnalysisError("invalid_reference", f"R3 dependency is missing: {key[0]}:{key[1]}")
        visiting.add(key)
        value = documents[key]
        for reference in value.get("dependencies", []):
            child = (reference["kind"], reference["id"])
            if child in documents:
                if child in visiting:
                    raise AnalysisError("dependency_cycle", f"R3 dependency cycle includes {child[0]}:{child[1]}")
                expected = documents[child].get("semantic_digest") or identity(documents[child])
                if reference["digest"] != expected:
                    raise AnalysisError("invalid_reference", f"R3 dependency digest changed: {child[0]}:{child[1]}")
                visit(child)
        visiting.remove(key); complete.add(key)
    visit(root_key)
    return True
