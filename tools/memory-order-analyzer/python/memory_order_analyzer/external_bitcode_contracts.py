"""Strict sidecar contracts for externally produced LLVM bitcode."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, canonical, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/external_bitcode.json"
PROTOCOL = ROOT / "protocols/external-bitcode-ingestion-protocol.json"
POLICY_ID = "external-bitcode-ingestion-v1"
KINDS = ("ExternalBitcodeBundleManifest", "ExternalBitcodeArtifactRecord",
         "ExternalBitcodeIngestionReport")
LATEST_KIND_VERSIONS = dict.fromkeys(KINDS, 1)
LATEST_KIND_VERSIONS["ExternalBitcodeArtifactRecord"] = 2


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_external_bitcode_protocol(path=PROTOCOL):
    value = _load(path, "external_bitcode_protocol")
    schema = _load(SCHEMA, "external_bitcode_schema")
    try:
        maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {
            "protocol_version": 2, "ingestion_version": "0.1.0", "llvm_version": "21.1.8",
            "policy_id": POLICY_ID, "cache_namespace": POLICY_ID,
            "kinds": LATEST_KIND_VERSIONS, "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("external_bitcode_schema", "External bitcode budget schema is invalid") from exc
    if canonical(value) != canonical(expected):
        raise AnalysisError("external_bitcode_protocol", "External bitcode protocol does not match its schema")
    return value


def semantic_digest(value):
    payload = deepcopy(value)
    payload.pop("semantic_digest", None)
    if payload.get("kind") == "ExternalBitcodeIngestionReport":
        payload.pop("cache", None)
        for item in payload.get("scopes", []):
            item.pop("path", None)
    return identity(payload)


def diagnostic(code, detail, detail_en, *, relevant=True, record_id=None, references=()):
    return {"code": code, "detail": str(detail)[:4096], "detail_en": str(detail_en)[:4096],
            "suggestion": "检查外部 bundle、上游构建记录和证据边界后重试",
            "suggestion_en": "Inspect the external bundle, upstream build record, and evidence boundary before retrying",
            "relevant": bool(relevant), "record_id": record_id,
            "references": sorted(set(str(item) for item in references))}


def _unique(items, key, detail):
    values = [key(item) for item in items]
    if len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _validate_record(value):
    produced = value["status"] == "produced"
    if produced != (value["bitcode"] is not None) or produced == (value["diagnostic"] is not None):
        raise AnalysisError("schema_invalid", "Produced records require bitcode and no diagnostic; missing/failed require a diagnostic")
    language_fields = {"dialect", "standard_source", "standard_option"}
    if value["schema_version"] == 1:
        if language_fields & value.keys() or value["standard"] not in {"c11", "c17", "c++17", "c++20"}:
            raise AnalysisError("schema_version", "ExternalBitcodeArtifactRecord v1 only supports the original four standards")
    else:
        if not language_fields <= value.keys():
            raise AnalysisError("schema_invalid", "ExternalBitcodeArtifactRecord v2 requires the versioned language context")
        if value["standard"] == "unsupported":
            if produced:
                raise AnalysisError("profile_conflict", "Unsupported language standards cannot produce trusted bitcode")
            if value["standard_source"] != "explicit" or value["dialect"] not in {"iso", "gnu"} or not value["standard_option"]:
                raise AnalysisError("profile_conflict", "Unsupported explicit standards require their original option")
        else:
            from .language_standards import validate_standard_context
            validate_standard_context(value["language"], value["standard"], value["dialect"],
                                      value["standard_source"], value["standard_option"])
    if value["module_kind"] == "translation-unit" and not value["physical_tu_id"]:
        raise AnalysisError("schema_invalid", "Translation-unit records require a physical TU identity")


def _validate_manifest(value):
    if not value["records"]:
        raise AnalysisError("request_invalid", "An external bitcode bundle must plan at least one record")
    paths = _unique(value["records"], lambda item: item["path"], "Duplicate standalone record path")
    del paths
    if value["records"] != sorted(value["records"], key=lambda item: item["path"]):
        raise AnalysisError("invalid_reference", "Standalone record references must be sorted by path")
    targets = _unique(value["scopes"], lambda item: item["target_id"], "Duplicate scope target_id")
    del targets
    if value["scopes"] != sorted(value["scopes"], key=lambda item: item["target_id"]):
        raise AnalysisError("invalid_reference", "Scopes must be sorted by target_id")
    if any(scope["record_ids"] != sorted(scope["record_ids"]) for scope in value["scopes"]):
        raise AnalysisError("invalid_reference", "Scope record membership must be sorted")
    if len(value["records"]) > value["budgets"]["max_records"]:
        raise AnalysisError("budget_exceeded", "Planned records exceed max_records")


def _validate_report(value):
    relevant = any(item["relevant"] for item in value["frontier"])
    published = value["counts"].get("published", 0)
    planned = value["counts"].get("planned", 0)
    if value["exit_code"] == 0 and (value["status"] != "complete" or relevant or published != planned or not planned):
        raise AnalysisError("invalid_reference", "Exit zero requires a nonempty complete bundle")
    if value["exit_code"] == 2 and (value["status"] != "partial" or not published or not relevant):
        raise AnalysisError("invalid_reference", "Exit two requires usable partial results and frontier")
    if value["exit_code"] == 1 and (value["status"] != "failed" or published):
        raise AnalysisError("invalid_reference", "Exit one requires no published artifacts")


def validate_external_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown external bitcode contract: {kind}")
    latest_version = LATEST_KIND_VERSIONS[kind]
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value.get("schema_version") not in ({1, latest_version} if latest_version > 1 else {1})):
        raise AnalysisError("schema_version", f"{kind} supports schema_version=1..{latest_version}")
    schema = _load(SCHEMA, "external_bitcode_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "ExternalBitcodeArtifactRecord":
        _validate_record(value)
    elif kind == "ExternalBitcodeBundleManifest":
        _validate_manifest(value)
    else:
        _validate_report(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest mismatch")
    return value


def external_document(kind, *, schema_version=None, **fields):
    protocol = expected_external_bitcode_protocol()
    if schema_version is None:
        version = (2 if kind == "ExternalBitcodeArtifactRecord"
                   and {"dialect", "standard_source", "standard_option"} <= fields.keys()
                   else 1)
    else:
        version = schema_version
    result = {"schema_version": version, "kind": kind, "ingestion_version": protocol["ingestion_version"],
              "policy_id": protocol["policy_id"], **deepcopy(fields)}
    result["semantic_digest"] = semantic_digest(result)
    return validate_external_document(result, kind)


def read_external_document(path, kind):
    return validate_external_document(_load(path, "input_invalid"), kind)


def failed_report(code, detail, detail_en=None, *, bundle_id=None):
    item = diagnostic(code, detail, detail_en or detail)
    return external_document(
        "ExternalBitcodeIngestionReport", bundle_id=bundle_id, status="failed", exit_code=1,
        semantic_analysis="not_run", safety="not_evaluated", findings=None,
        counts={"planned": 0, "produced": 0, "missing": 0, "upstream_failed": 0,
                "hash_failed": 0, "format_failed": 0, "reader_failed": 0,
                "published": 0, "facts_complete": 0, "facts_partial": 0,
                "source_bound": 0, "scope_resolved": 0},
        ratios={"published": None, "facts_complete": None, "source_bound": None,
                "scope_resolved": None}, record_artifacts=[], scopes=[], artifacts=[],
        cache={"hits": 0, "misses": 0}, frontier=[item], diagnostics=[item])
