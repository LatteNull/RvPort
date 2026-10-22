"""Strict, versioned contracts for P5 validation evidence."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, canonical, identity


ROOT = Path(__file__).resolve().parents[2]
POLICY_ID = "analysis-validation-v1"
KINDS = (
    "ValidationSuiteManifest",
    "TruthAnnotation",
    "AnalysisValidationRequest",
    "AnalysisValidationReport",
    "AnalysisExtensionDecision",
    "BackendEvidenceBundle",
)
CAPABILITIES = ("b1-cmake-scope", "std-thread", "pointer-analysis", "fence-rmw")


def _load_json(path, code="input_invalid"):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_validation_protocol(path=ROOT / "protocols/validation-analysis-protocol.json"):
    protocol = _load_json(path, "validation_protocol")
    schema = _load_json(ROOT / "schemas/validation.json", "validation_schema")
    try:
        maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {
            "protocol_version": 1,
            "analysis_version": "0.1.0",
            "policy_id": POLICY_ID,
            "runner_version": "0.1.0",
            "kinds": dict.fromkeys(KINDS, 1),
            "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("validation_schema", "Validation budget schema is invalid") from exc
    if canonical(protocol) != canonical(expected):
        raise AnalysisError("validation_protocol", "Validation protocol does not match supported schemas")
    return protocol


def diagnostic(code, detail, detail_en, *, suggestion=None, suggestion_en=None):
    if (suggestion is None) != (suggestion_en is None):
        raise AnalysisError("diagnostic_translation", "Suggestion and suggestion_en must be paired")
    return {
        "code": code,
        "detail": detail,
        "detail_en": detail_en,
        "suggestion": suggestion,
        "suggestion_en": suggestion_en,
    }


def _unique(items, field, detail):
    values = [item[field] for item in items]
    if len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _assert_sorted(items, field, detail):
    values = [item[field] for item in items]
    if values != sorted(values):
        raise AnalysisError("ordering_invalid", detail)


def _validate_suite(value):
    profiles = _unique(value["profiles"], "id", "Duplicate validation profile")
    cases = _unique(value["cases"], "id", "Duplicate validation case")
    _assert_sorted(value["profiles"], "id", "Profiles must use deterministic ID order")
    _assert_sorted(value["cases"], "id", "Cases must use deterministic ID order")
    for profile in value["profiles"]:
        if profile["language"] == "c" and profile["standard"] not in ("c11", "c17"):
            raise AnalysisError("profile_invalid", "C profile cannot use a C++ standard")
        if profile["language"] == "c++" and profile["standard"] not in ("c++17", "c++20"):
            raise AnalysisError("profile_invalid", "C++ profile cannot use a C standard")
    for case in value["cases"]:
        if case["profile_id"] not in profiles:
            raise AnalysisError("invalid_reference", f"Unknown profile for case {case['id']}")
        _unique(case["sources"], "path", f"Duplicate source path for case {case['id']}")
        if case["truth"]["role"] != "truth":
            raise AnalysisError("invalid_reference", "Truth file must have the truth role")
        if case["compile_commands"]["role"] != "compile-database" or case["scope"]["role"] != "scope":
            raise AnalysisError("invalid_reference", "Case compile database/scope roles are invalid")
        if case["id"] not in cases:
            raise AnalysisError("invalid_reference", "Unreachable validation case")


def _assertion_key(item):
    return (item["code"], item["object"], item["thread_relation"], item["evidence_relation"])


def _validate_truth(value):
    required = {_assertion_key(item) for item in value["expected"]["required_findings"]}
    forbidden = {_assertion_key(item) for item in value["expected"]["forbidden_findings"]}
    if len(required) != len(value["expected"]["required_findings"]) or len(forbidden) != len(value["expected"]["forbidden_findings"]):
        raise AnalysisError("invalid_reference", "Duplicate truth finding assertion")
    if required & forbidden:
        raise AnalysisError("truth_conflict", "A truth finding cannot be both required and forbidden")


def _metric_matches(metric):
    expected = metric["hit"] / metric["total"] if metric["total"] else None
    return metric["value"] == expected


def _validate_report(value):
    for name, layer in value["layers"].items():
        if layer["hit"] > layer["total"]:
            raise AnalysisError("invalid_reference", f"Layer {name} hit exceeds total")
        if layer["status"] == "complete" and layer["hit"] != layer["total"]:
            raise AnalysisError("invalid_reference", f"Complete layer {name} must hit its full denominator")
    for name in ("precision", "recall", "supported_precision", "supported_recall", "exact_match", "abstention"):
        if not _metric_matches(value["metrics"][name]):
            raise AnalysisError("invalid_reference", f"Metric {name} does not match hit/total")
    incomplete = any(layer["status"] != "complete" for layer in value["layers"].values())
    if value["exit_code"] == 0 and (value["verdict"] != "matched" or incomplete):
        raise AnalysisError("invalid_reference", "Exit zero requires a matched, complete validation")
    if value["exit_code"] == 3 and (value["verdict"] != "mismatch" or incomplete):
        raise AnalysisError("invalid_reference", "Exit three requires a complete mismatch")
    if value["exit_code"] == 2 and not incomplete:
        raise AnalysisError("invalid_reference", "Exit two requires incomplete validation evidence")
    if value["exit_code"] == 1 and value["verdict"] != "failed":
        raise AnalysisError("invalid_reference", "Exit one requires a failed validation")


def _validate_decision(value):
    capabilities = _unique(value["entries"], "capability", "Duplicate extension decision")
    if capabilities != set(CAPABILITIES):
        raise AnalysisError("invalid_reference", "Extension decision must cover the four P5 candidates")


def _validate_semantics(value, kind):
    if kind == "ValidationSuiteManifest":
        _validate_suite(value)
    elif kind == "TruthAnnotation":
        _validate_truth(value)
    elif kind == "AnalysisValidationReport":
        _validate_report(value)
    elif kind == "AnalysisExtensionDecision":
        _validate_decision(value)


def validate_validation_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown validation contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    schema = _load_json(ROOT / "schemas/validation.json", "validation_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    _validate_semantics(value, kind)
    return value


def validation_document(kind, **fields):
    protocol = expected_validation_protocol()
    return validate_validation_document({
        "schema_version": 1,
        "kind": kind,
        "analysis_version": protocol["analysis_version"],
        "policy_id": protocol["policy_id"],
        **fields,
    }, kind)


def read_validation_document(path, kind):
    return validate_validation_document(_load_json(path), kind)


def write_validation_document(path, value, kind):
    validate_validation_document(value, kind)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")
    return identity(value)


def failed_validation_report(code, detail, detail_en=None):
    empty = {name: {"status": "failed" if name == "request_input" else "not_run", "hit": 0, "total": 1}
             for name in ("request_input", "compile", "p1", "p2", "p3", "p4", "truth", "sampling", "performance", "backend")}
    zero = {"hit": 0, "total": 0, "value": None}
    return validation_document(
        "AnalysisValidationReport",
        request_hash="0" * 64,
        suite_digest="0" * 64,
        layers=empty,
        cases=[],
        metrics={"true_positive": 0, "false_positive": 0, "false_negative": 0,
                 "precision": deepcopy(zero), "recall": deepcopy(zero),
                 "supported_precision": deepcopy(zero), "supported_recall": deepcopy(zero),
                 "exact_match": deepcopy(zero), "abstention": deepcopy(zero)},
        performance={},
        backend_dependencies=[],
        diagnostics=[diagnostic(code, detail, detail_en or detail)],
        frontier=[],
        safety="not_established",
        verdict="failed",
        exit_code=1,
    )
