"""Versioned contracts for execution-root-driven analysis (R1)."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/execution_root_analysis.json"
PROTOCOL = ROOT / "protocols/execution-root-analysis-protocol.json"
KINDS = (
    "ExecutionRootDiscoveryRequest", "ThreadCreationSiteIndex",
    "ExecutionRootIndex", "RootDrivenAnalysisPlan", "RootDrivenAnalysisReport",
)
CLASSIFICATIONS = (
    "dual-exact", "ir-exact", "source-candidate", "ambiguous", "unsupported", "failed",
)


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_root_protocol(path=PROTOCOL):
    value = _load(path, "root_protocol")
    schema = _load(SCHEMA, "root_schema")
    maxima = {name: rule["maximum"] for name, rule in
              schema["$defs"]["Budgets"]["properties"].items()}
    expected = {
        "protocol_version": 1, "analysis_version": "0.1.0",
        "llvm_version": "21.1.8", "policy_id": "execution-root-driven-analysis-v1",
        "cache_namespace": "execution-root-driven-analysis-v1",
        "kinds": dict.fromkeys(KINDS, 1), "budgets": maxima,
    }
    if value != expected:
        raise AnalysisError("root_protocol", "R1 protocol and schema maxima disagree")
    return value


def dependency(kind, key, value):
    return {"kind": kind, "id": str(key), "digest": identity(value)}


def diagnostic(code, detail, detail_en, *, limitation=None, limitation_en=None,
               suggestion=None, suggestion_en=None, source=None, limit=4096):
    def bounded(value):
        value = str(value)
        while len(value.encode("utf-8")) > limit and value:
            value = value[:-1]
        return value or "-"
    return {
        "code": str(code), "detail": bounded(detail), "detail_en": bounded(detail_en),
        "limitation": bounded(limitation or
                              "R1 仅规划执行根和受限可达域，不评估风险、安全或完整 happens-before"),
        "limitation_en": bounded(limitation_en or
                                 "R1 only plans execution roots and bounded reachability; it does not evaluate risk, safety, or complete happens-before"),
        "suggestion": bounded(suggestion) if suggestion is not None else None,
        "suggestion_en": bounded(suggestion_en) if suggestion_en is not None else None,
        "source": deepcopy(source),
    }


def semantic_digest(value):
    copy = deepcopy(value)
    copy.pop("semantic_digest", None)
    if copy.get("kind") == "RootDrivenAnalysisReport":
        copy.pop("cache", None)
    return identity(copy)


def _unique_sorted(items, key, detail):
    values = [key(item) for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _dependencies(items):
    return _unique_sorted(items, lambda item: (item["kind"], item["id"]),
                          "Dependencies must be unique and sorted")


def _validate_inputs(items, detail):
    _unique_sorted(items, lambda item: (item["kind"], item["id"]), detail)
    for item in items:
        path = Path(item["path"])
        if path.is_absolute() or ".." in path.parts:
            raise AnalysisError("invalid_reference", "Evidence input paths must remain relative to the artifact store")


def _validate_request(value):
    _unique_sorted(value["members"], lambda item: item["physical_tu_id"],
                   "Request members must be unique and sorted")
    _unique_sorted(value["explicit_roots"], lambda item: item["id"],
                   "Explicit roots must be unique and sorted")
    _validate_inputs(value["global_evidence"], "Global evidence must be unique and sorted")
    all_inputs = {(item["kind"], item["id"]): item for item in value["global_evidence"]}
    if len(value["members"]) > value["budgets"]["translation_units"]:
        raise AnalysisError("translation-unit-budget", "R1 request exceeds translation unit budget")
    for member in value["members"]:
        allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if member["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
        if member["standard"] not in allowed:
            raise AnalysisError("profile_conflict", "Member language and standard disagree")
        _validate_inputs(member["evidence"], "Member evidence must be unique and sorted")
        for item in member["evidence"]:
            key = (item["kind"], item["id"])
            if key in all_inputs:
                raise AnalysisError("invalid_reference", "Evidence input is declared more than once")
            all_inputs[key] = item
        kinds = {item["kind"] for item in member["evidence"]}
        if not kinds & {"ModuleFacts", "SourceSemanticFacts", "ThreadLocalFacts", "CppThreadLocalFacts"}:
            raise AnalysisError("invalid_reference", "Each member requires at least one supported evidence layer")
        if member["language"] == "c" and "CppThreadLocalFacts" in kinds:
            raise AnalysisError("profile_conflict", "C members cannot depend on C++ standard-library models")
    for root in value["explicit_roots"]:
        if root["kind"] == "framework" and root["source_entity_id"] is None:
            raise AnalysisError("invalid_reference", "Framework roots require an explicit source entity")


def _validate_site_index(value):
    _unique_sorted(value["sites"], lambda item: item["id"], "Creation sites must be unique and sorted")
    _dependencies(value["dependencies"])
    for site in value["sites"]:
        if site.get("classification") not in CLASSIFICATIONS:
            raise AnalysisError("classification_invalid", "Unknown thread-creation classification")
        if site["classification"] in {"dual-exact", "ir-exact"} and not site.get("callback", {}).get("entry"):
            raise AnalysisError("classification_invalid", "Exact creation sites require an exact callback entry")


def _validate_root_index(value):
    _unique_sorted(value["roots"], lambda item: item["id"], "Execution roots must be unique and sorted")
    _dependencies(value["dependencies"])
    for root in value["roots"]:
        if root.get("status") == "complete" and not root.get("entry"):
            raise AnalysisError("root_invalid", "Complete execution roots require an entry")
        if root.get("kind") in {"pthread", "std-thread"}:
            if not root.get("creation_site_id") or not root.get("thread_instance_key"):
                raise AnalysisError("root_invalid", "Thread roots must retain creation-site instance identity")


def _validate_plan(value):
    for field in ("reachable_functions", "call_edges", "contexts", "demands", "p2_requests", "p3_requests", "a3_overlays"):
        _unique_sorted(value[field], lambda item: item["id"], f"{field} must be unique and sorted")
    declared = _dependencies(value["dependencies"])
    for field in ("thread_creation_sites", "execution_roots"):
        ref = value[field]
        if (ref["kind"], ref["id"]) not in declared:
            raise AnalysisError("invalid_reference", f"Plan {field} is missing from dependencies")


def _validate_report(value):
    expected = 1 if value["status"] == "failed" else 2 if value["status"] == "partial" else 0
    if value["exit_code"] != expected:
        raise AnalysisError("report_status", "R1 report exit code does not match completeness")
    declared = _dependencies(value["dependencies"])
    for field in ("thread_creation_sites", "execution_roots", "plan"):
        ref = value[field]
        if ref is not None and (ref["kind"], ref["id"]) not in declared:
            raise AnalysisError("invalid_reference", f"Report {field} is missing from dependencies")
    if value["findings"] is not None or value["safety"] != "not_evaluated":
        raise AnalysisError("safety_claim", "R1 cannot publish findings or safety conclusions")


def validate_root_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown R1 contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    schema = _load(SCHEMA, "root_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "ExecutionRootDiscoveryRequest":
        _validate_request(value)
    elif kind == "ThreadCreationSiteIndex":
        _validate_site_index(value)
    elif kind == "ExecutionRootIndex":
        _validate_root_index(value)
    elif kind == "RootDrivenAnalysisPlan":
        _validate_plan(value)
    else:
        _validate_report(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def root_document(kind, **fields):
    protocol = expected_root_protocol()
    result = {"schema_version": 1, "kind": kind,
              "analysis_version": protocol["analysis_version"],
              "policy_id": protocol["policy_id"], **fields}
    if result.get("semantic_digest") is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_root_document(result, kind)


def read_root_document(path, kind):
    return validate_root_document(_load(path, "input_invalid"), kind)
