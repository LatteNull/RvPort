"""Versioned contracts for bounded object provenance (A5)."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, canonical, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/bounded_object_provenance.json"
PROTOCOL = ROOT / "protocols/bounded-object-provenance-protocol.json"
KINDS = (
    "BoundedObjectProvenanceRequest", "SourceObjectPathRequest",
    "SourceObjectPathFacts", "LLVMObjectProvenanceRequest",
    "LLVMObjectProvenanceFacts", "BoundedObjectProvenanceGraph",
    "BoundedObjectProvenanceReport", "ObjectProvenanceValidationSuite",
    "ObjectProvenanceValidationTruth", "ObjectProvenanceValidationReport",
)


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_provenance_protocol(path=PROTOCOL):
    value = _load(path, "provenance_protocol")
    schema = _load(SCHEMA, "provenance_schema")
    try:
        maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {
            "protocol_version": 1, "analysis_version": "0.1.0",
            "llvm_version": "21.1.8", "policy_id": "bounded-object-provenance-v1",
            "kinds": dict.fromkeys(KINDS, 1), "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("provenance_schema", "A5 budget schema is invalid") from exc
    if canonical(value) != canonical(expected):
        raise AnalysisError("provenance_protocol", "A5 protocol does not match supported schemas")
    return value


def dependency(kind, key, value):
    return {"kind": str(kind), "id": str(key), "digest": identity(value)}


def diagnostic(code, detail, detail_en, *, limitation=None, limitation_en=None,
               suggestion=None, suggestion_en=None, source=None, limit=4096):
    def bounded(text):
        text = str(text)
        while len(text.encode("utf-8")) > limit and text:
            text = text[:-1]
        return text or "-"
    return {
        "code": str(code), "detail": bounded(detail), "detail_en": bounded(detail_en),
        "limitation": bounded(limitation or "有限对象来源结果不代表全程序别名、安全或 happens-before 证明"),
        "limitation_en": bounded(limitation_en or
                                  "Bounded object provenance is not a whole-program alias, safety, or happens-before proof"),
        "suggestion": bounded(suggestion) if suggestion is not None else None,
        "suggestion_en": bounded(suggestion_en) if suggestion_en is not None else None,
        "source": deepcopy(source),
    }


def semantic_digest(value):
    copy = deepcopy(value)
    copy.pop("semantic_digest", None)
    if copy.get("kind") == "BoundedObjectProvenanceReport":
        copy.pop("cache", None)
    return identity(copy)


def _unique_sorted(items, key, detail):
    values = [key(item) for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _dependencies(items, detail="Dependencies must be unique and sorted"):
    return _unique_sorted(items, lambda item: (item["kind"], item["id"]), detail)


def _validate_domain(domain):
    candidates = domain["candidates"]
    _unique_sorted(candidates, lambda item: item["object"]["id"],
                   "Candidate objects must be unique and sorted")
    for item in candidates:
        if item["guards"] != sorted(set(item["guards"])) or item["proof"] != sorted(set(item["proof"])):
            raise AnalysisError("invalid_reference", "Candidate guards and proof must be unique and sorted")
        if item["opposed"] != sorted(set(item["opposed"])):
            raise AnalysisError("invalid_reference", "Opposed evidence must be unique and sorted")
        _dependencies(item["dependencies"])
        if item["object"]["id"] != identity({
                "storage": item["object"]["storage"], "path": item["object"]["path"],
                "byte_range": item["object"]["byte_range"]}):
            raise AnalysisError("object_identity", "Object identity does not match storage, path, and byte range")
    if domain["state"] == "must" and (len(candidates) != 1 or candidates[0]["opposed"] or domain["reason"] is not None):
        raise AnalysisError("domain_invalid", "must requires one unopposed candidate and no reason")
    if domain["state"] == "may" and (not candidates or domain["reason"] is not None):
        raise AnalysisError("domain_invalid", "may requires candidates and no unknown reason")
    if domain["state"] == "unknown" and domain["reason"] is None:
        raise AnalysisError("domain_invalid", "unknown requires a reason")


def _validate_request(value):
    _unique_sorted(value["members"], lambda item: item["physical_tu_id"],
                   "Request members must be unique and sorted")
    if value["roots"] != sorted(set(value["roots"])):
        raise AnalysisError("invalid_reference", "Request roots must be unique and sorted")
    _dependencies(value["dependencies"])
    if len(value["members"]) > value["budgets"]["translation_units"]:
        raise AnalysisError("translation-unit-budget", "A5 request exceeds translation unit budget")
    for member in value["members"]:
        allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if member["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
        if member["standard"] not in allowed:
            raise AnalysisError("profile_conflict", "Member language and standard disagree")
        if member["source_request"] is None and member["llvm_request"] is None:
            raise AnalysisError("invalid_reference", "A5 member requires AST or LLVM evidence request")


def _validate_source(value):
    allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if value["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
    if value["standard"] not in allowed:
        raise AnalysisError("profile_conflict", "Source language and standard disagree")
    _unique_sorted(value["paths"], lambda item: item["id"], "Source paths must be unique and sorted")
    _dependencies(value["dependencies"])
    for item in value["paths"]:
        if item["evidence"] != sorted(set(item["evidence"])):
            raise AnalysisError("invalid_reference", "Source path evidence must be unique and sorted")
        if item["status"] == "exact" and item["reason"] is not None:
            raise AnalysisError("source_path_invalid", "Exact source paths cannot have an unknown reason")
        # A source fact deliberately has no runtime object/domain field.
        if "object" in item["base"] or "alias" in item["base"] or "noalias" in item["base"]:
            raise AnalysisError("source_runtime_proof", "AST-only facts cannot publish runtime alias identities")
    if value["status"] == "complete" and value["frontier"]:
        raise AnalysisError("invalid_reference", "Complete source path facts cannot contain frontier")


def _validate_llvm(value):
    _unique_sorted(value["values"], lambda item: item["id"], "LLVM values must be unique and sorted")
    _dependencies(value["dependencies"])
    for item in value["values"]:
        _validate_domain(item["domain"])
    if value["status"] == "complete" and value["frontier"]:
        raise AnalysisError("invalid_reference", "Complete LLVM provenance facts cannot contain frontier")


def _validate_graph(value):
    objects = _unique_sorted(value["objects"], lambda item: item["id"], "Objects must be unique and sorted")
    _unique_sorted(value["domains"], lambda item: item["id"], "Domains must be unique and sorted")
    _unique_sorted(value["relations"], lambda item: item["id"], "Relations must be unique and sorted")
    _unique_sorted(value["adapters"], lambda item: item["id"], "Adapters must be unique and sorted")
    _dependencies(value["dependencies"])
    for item in value["domains"]:
        _validate_domain(item["domain"])
        if not {candidate["object"]["id"] for candidate in item["domain"]["candidates"]} <= objects:
            raise AnalysisError("invalid_reference", "Graph domain references a missing object")
    for adapter in value["adapters"]:
        if adapter.get("status") == "exact" and adapter.get("object_id") not in objects:
            raise AnalysisError("invalid_reference", "Exact adapter references a missing object")
    if value["status"] == "complete" and value["frontier"]:
        raise AnalysisError("invalid_reference", "Complete graph cannot contain frontier")


def _validate_report(value):
    expected = 1 if value["status"] == "failed" else 2 if value["status"] == "partial" else 0
    if value["exit_code"] != expected:
        raise AnalysisError("report_status", "A5 report exit code does not match completeness")
    declared = _dependencies(value["dependencies"])
    if value["graph"] is not None and (value["graph"]["kind"], value["graph"]["id"]) not in declared:
        raise AnalysisError("invalid_reference", "A5 report graph is missing from dependencies")
    if value["findings"] is not None or value["safety"] != "not_established":
        raise AnalysisError("safety_claim", "A5 cannot publish findings or safety conclusions")


def _validate_validation(value):
    if value["kind"] == "ObjectProvenanceValidationReport":
        if set(value["languages"]) != {"c11", "c17", "c++17", "c++20"}:
            raise AnalysisError("validation_denominator", "A5 report must preserve all four language denominators")
        return
    _unique_sorted(value["cases"], lambda item: item.get("id", item.get("case_id")),
                   "A5 validation cases must be unique and sorted")
    if {item.get("standard") for item in value["cases"]} != {"c11", "c17", "c++17", "c++20"}:
        raise AnalysisError("validation_denominator", "A5 truth must cover all four standards")


def validate_provenance_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown A5 contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    schema = _load(SCHEMA, "provenance_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "BoundedObjectProvenanceRequest":
        _validate_request(value)
    elif kind == "SourceObjectPathFacts":
        _validate_source(value)
    elif kind == "LLVMObjectProvenanceFacts":
        _validate_llvm(value)
    elif kind == "BoundedObjectProvenanceGraph":
        _validate_graph(value)
    elif kind == "BoundedObjectProvenanceReport":
        _validate_report(value)
    elif kind.startswith("ObjectProvenanceValidation"):
        _validate_validation(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def provenance_document(kind, **fields):
    protocol = expected_provenance_protocol()
    result = {
        "schema_version": 1, "kind": kind,
        "analysis_version": protocol["analysis_version"],
        "policy_id": protocol["policy_id"], **fields,
    }
    if result.get("semantic_digest") is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_provenance_document(result, kind)


def read_provenance_document(path, kind):
    return validate_provenance_document(_load(path, "input_invalid"), kind)
