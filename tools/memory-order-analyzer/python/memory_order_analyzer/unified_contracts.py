"""Versioned contracts for the project-level analysis entry point."""

from copy import deepcopy
import json
from pathlib import Path, PurePath

import jsonschema

from .contracts import AnalysisError, canonical, identity
from .finding_contracts import validate_finding


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/unified_project_analysis.json"
PROTOCOL = ROOT / "protocols/unified-project-analysis-protocol.json"
POLICY_ID = "unified-project-analysis-v1"
KINDS = ("UnifiedMemoryOrderAnalysisRequest", "UnifiedAnalysisPlan",
         "ScopeAnalysisExecutionRecord", "UnifiedMemoryOrderAnalysisReport")
PROTOCOL_KINDS = (*KINDS, "MemoryOrderFindingProjection")
LATEST_KIND_VERSIONS = dict.fromkeys(PROTOCOL_KINDS, 1)
LATEST_KIND_VERSIONS["UnifiedMemoryOrderAnalysisRequest"] = 2


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_unified_protocol(path=PROTOCOL):
    value = _load(path, "unified_protocol")
    schema = _load(SCHEMA, "unified_schema")
    maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
    expected = {"protocol_version": 2, "analysis_version": "0.1.0",
                "policy_id": POLICY_ID, "cache_namespace": POLICY_ID,
                "finding_schema_version": "2.0", "kinds": LATEST_KIND_VERSIONS,
                "budgets": maxima}
    if canonical(value) != canonical(expected):
        raise AnalysisError("unified_protocol", "Unified protocol and schema maxima disagree")
    return value


def diagnostic(code, detail, detail_en, *, suggestion="检查输入证据、分析边界和预算后重试",
               suggestion_en="Inspect input evidence, analysis boundaries, and budgets before retrying",
               stage=None, scope_id=None, relevant=True, references=()):
    return {"code": str(code), "detail": str(detail)[:4096], "detail_en": str(detail_en)[:4096],
            "suggestion": str(suggestion)[:4096], "suggestion_en": str(suggestion_en)[:4096],
            "stage": stage, "scope_id": scope_id, "relevant": bool(relevant),
            "references": sorted(set(str(item) for item in references))}


def semantic_digest(value):
    payload = deepcopy(value)
    payload.pop("semantic_digest", None)
    if payload.get("kind") == "UnifiedMemoryOrderAnalysisRequest":
        payload["cancel_file"] = None
        payload["cache"] = {"mode": "disabled", "resume": False}
        payload["bundle"]["path"] = None
        for item in payload["source_requests"]:
            item["path"] = None
    if payload.get("kind") == "UnifiedMemoryOrderAnalysisReport":
        for reference in payload.get("artifacts", []):
            reference.pop("path", None)
        for reference in payload.get("scope_records", []):
            reference.pop("path", None)
    if payload.get("kind") == "ScopeAnalysisExecutionRecord":
        for stage in payload.get("stages", []):
            # Cache provenance is operational metadata. Cold and warm execution
            # must retain the same semantic identity.
            stage["cache"] = "miss" if stage.get("cache") != "disabled" else "disabled"
    return identity(payload)


def _unique_sorted(items, key, detail):
    values = [key(item) for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _safe_reference_path(path):
    value = PurePath(path)
    if value.is_absolute() or ".." in value.parts:
        raise AnalysisError("path_unsafe", "Artifact references must stay relative to their declared root")


def _validate_request(value):
    selection = value["scope_selection"]
    ids = selection["scope_ids"]
    if ids != sorted(ids):
        raise AnalysisError("invalid_reference", "Scope selection must be sorted")
    if (selection["mode"] == "all") != (not ids):
        raise AnalysisError("request_invalid", "all selection requires no scope IDs; explicit selection requires IDs")
    _unique_sorted(value["source_requests"], lambda item: item["record_id"],
                   "Source requests must have unique sorted record IDs")
    _unique_sorted(value["explicit_roots"],
                   lambda item: (item["kind"], item["symbol"], item.get("artifact_key") or "", item.get("function_id") or ""),
                   "Explicit roots must be unique and sorted")
    _safe_reference_path(value["bundle"]["path"])
    for item in value["source_requests"]:
        _safe_reference_path(item["path"])
        if value["schema_version"] == 1 and "schema_version" in item:
            raise AnalysisError("schema_version", "Unified request v1 cannot reference versioned source requests")
        if value["schema_version"] == 2 and item.get("schema_version") != 2:
            raise AnalysisError("schema_version", "Unified request v2 requires source request schema_version=2")
    cancel = value["cancel_file"]
    if cancel is not None and (not Path(cancel).is_absolute() or ".." in PurePath(cancel).parts):
        raise AnalysisError("path_unsafe", "Cancel file must be an absolute path without traversal")
    if len(ids) > value["budgets"]["scopes"]:
        raise AnalysisError("budget_exceeded", "Selected scopes exceed the scope budget")


def _validate_plan(value):
    selected = value["selected_scopes"]
    if selected != sorted(selected):
        raise AnalysisError("invalid_reference", "Selected scopes must be sorted")
    ids = _unique_sorted(value["stages"], lambda item: item["id"], "Plan stages must be unique and sorted")
    edges = _unique_sorted(value["edges"], lambda item: (item["from"], item["to"]),
                           "Plan edges must be unique and sorted")
    del edges
    if any(stage["scope_id"] not in selected for stage in value["stages"]):
        raise AnalysisError("invalid_reference", "Plan stage belongs to an unselected scope")
    if any(set(stage["dependencies"]) - ids for stage in value["stages"]):
        raise AnalysisError("invalid_reference", "Plan stage has an undeclared dependency")
    if any(edge["from"] not in ids or edge["to"] not in ids for edge in value["edges"]):
        raise AnalysisError("invalid_reference", "Plan edge has an undeclared endpoint")
    expected = {(dependency, stage["id"]) for stage in value["stages"] for dependency in stage["dependencies"]}
    actual = {(edge["from"], edge["to"]) for edge in value["edges"]}
    if actual != expected:
        raise AnalysisError("invalid_reference", "Plan edges and stage dependencies disagree")
    remaining = {stage["id"]: set(stage["dependencies"]) for stage in value["stages"]}
    while remaining:
        ready = {key for key, dependencies in remaining.items() if not dependencies}
        if not ready:
            raise AnalysisError("plan_cycle", "Analysis plan contains a dependency cycle")
        remaining = {key: dependencies - ready for key, dependencies in remaining.items() if key not in ready}


def _validate_execution(value):
    _unique_sorted(value["tu_modes"], lambda item: item["record_id"], "TU modes must be unique and sorted")
    _unique_sorted(value["stages"], lambda item: item["stage_id"], "Stage results must be unique and sorted")
    for item in value["tu_modes"]:
        if item["available_evidence"] != sorted(item["available_evidence"]):
            raise AnalysisError("invalid_reference", "Available evidence must be sorted")
        if item["missing_evidence"] != sorted(item["missing_evidence"]):
            raise AnalysisError("invalid_reference", "Missing evidence must be sorted")
        expected = {"ast-ir": ("ast", "ir"), "ast-only": ("ast",), "ir-only": ("ir",), "failed": ()}[item["mode"]]
        if tuple(item["available_evidence"]) != expected:
            raise AnalysisError("evidence_mode", "TU mode disagrees with available evidence")
    incomplete = any(item["status"] not in {"complete", "skipped-not-applicable"} for item in value["stages"])
    if value["status"] == "complete" and (incomplete or value["frontier"]):
        raise AnalysisError("report_status", "Complete scope execution cannot contain incomplete stages or frontier")


def _validate_report(value):
    expected_collections = {"findings": "risk", "source_candidates": "source-candidate",
                            "discharged_assessments": "discharged-within-bounded-model"}
    for collection, expected_verdict in expected_collections.items():
        _unique_sorted(value[collection], lambda item: item["id"], f"{collection} must be unique and sorted")
        for item in value[collection]:
            validate_finding(item)
            if item["conclusion"]["verdict"] != expected_verdict:
                raise AnalysisError("report_collection", f"{collection} contains the wrong Finding verdict")
    expected_verdict = ("failed" if value["status"] == "failed" else
                        "inconclusive" if value["status"] in {"partial", "cancelled"} or value["source_candidates"] or value["frontier"] else
                        "risk" if value["findings"] else
                        "no-finding-within-supported-model")
    expected_exit = {"failed": 1, "risk": 3, "inconclusive": 2,
                     "no-finding-within-supported-model": 0}[expected_verdict]
    if value["verdict"] != expected_verdict or value["exit_code"] != expected_exit:
        raise AnalysisError("report_status", "Unified report verdict or exit code disagrees with its contents")
    _unique_sorted(value["scope_records"], lambda item: item["id"], "Scope records must be unique and sorted")
    _unique_sorted(value["artifacts"], lambda item: (item["kind"], item["id"]),
                   "Artifact references must be unique and sorted")
    for reference in [*value["scope_records"], *value["artifacts"]]:
        _safe_reference_path(reference["path"])


def validate_unified_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown unified contract: {kind}")
    latest_version = LATEST_KIND_VERSIONS[kind]
    supported_versions = {1, latest_version} if latest_version > 1 else {1}
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value.get("schema_version") not in supported_versions or value.get("kind") != kind):
        raise AnalysisError("schema_version", f"{kind} supports schema_version=1..{latest_version} and the matching kind")
    schema = _load(SCHEMA, "unified_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "UnifiedMemoryOrderAnalysisRequest":
        _validate_request(value)
    elif kind == "UnifiedAnalysisPlan":
        _validate_plan(value)
    elif kind == "ScopeAnalysisExecutionRecord":
        _validate_execution(value)
    else:
        _validate_report(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def unified_document(kind, *, schema_version=None, **fields):
    protocol = expected_unified_protocol()
    if schema_version is None:
        version = (2 if kind == "UnifiedMemoryOrderAnalysisRequest"
                   and any(item.get("schema_version") == 2 for item in fields.get("source_requests", []))
                   else 1)
    else:
        version = schema_version
    result = {"schema_version": version, "kind": kind, "analysis_version": protocol["analysis_version"],
              "policy_id": protocol["policy_id"], **deepcopy(fields)}
    if kind == "UnifiedMemoryOrderAnalysisReport":
        result.setdefault("finding_schema_version", protocol["finding_schema_version"])
    result["semantic_digest"] = semantic_digest(result)
    return validate_unified_document(result, kind)


def read_unified_document(path, kind):
    return validate_unified_document(_load(path, "input_invalid"), kind)


def failed_report(code, detail, detail_en=None, *, project=None, request_digest=None, bundle_id=None,
                  cancelled=False):
    item = diagnostic(code, detail, detail_en or detail)
    return unified_document(
        "UnifiedMemoryOrderAnalysisReport", project=project or {"id": "unknown", "name": "unknown"},
        request_digest=request_digest, bundle_id=bundle_id,
        status="cancelled" if cancelled else "failed",
        verdict="inconclusive" if cancelled else "failed", exit_code=2 if cancelled else 1,
        scope_records=[], summary={"scopes": 0, "translation_units": 0, "formal_findings": 0,
                                   "source_candidates": 0, "discharged_assessments": 0,
                                   "unsupported": 0, "frontier": 1, "abstention": 1},
        findings=[], source_candidates=[], discharged_assessments=[], unsupported=[], frontier=[item],
        diagnostics=[item], artifacts=[])
