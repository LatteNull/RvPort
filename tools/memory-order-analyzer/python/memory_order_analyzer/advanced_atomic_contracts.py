"""Strict A6 contracts for bounded fence/RMW/CAS publication analysis."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, canonical, file_hash, identity


ROOT = Path(__file__).resolve().parents[2]
POLICY_ID = "fence-rmw-publication-v1"
MODEL_ID = "bounded-advanced-atomic-publication-v1"
KINDS = (
    "FenceRmwPublicationRequest",
    "AtomicSourceConstructFacts",
    "AdvancedAtomicFunctionFacts",
    "AdvancedAtomicLocalFacts",
    "BoundedAtomicCommunicationGraph",
    "AdvancedPublicationProtocolOverlay",
    "FenceRmwPublicationReport",
)


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_advanced_atomic_protocol(path=ROOT / "protocols/advanced-atomic-analysis-protocol.json"):
    protocol = _load(path, "advanced_atomic_protocol")
    schema = _load(ROOT / "schemas/advanced_atomic.json", "advanced_atomic_schema")
    try:
        maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {
            "protocol_version": 1,
            "analysis_version": "0.1.0",
            "llvm_version": "21.1.8",
            "policy_id": POLICY_ID,
            "model_id": MODEL_ID,
            "cache_namespace": POLICY_ID,
            "kinds": dict.fromkeys(KINDS, 1),
            "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("advanced_atomic_schema", "Advanced atomic budget schema is invalid") from exc
    if canonical(protocol) != canonical(expected):
        raise AnalysisError("advanced_atomic_protocol", "Advanced atomic protocol does not match supported schemas")
    return protocol


def diagnostic(code, detail, detail_en, *, relevant=True, references=(), suggestion=None,
               suggestion_en=None):
    if (suggestion is None) != (suggestion_en is None):
        raise AnalysisError("schema_invalid", "Bilingual suggestions must be supplied together")
    return {
        "code": code,
        "detail": detail,
        "detail_en": detail_en,
        "suggestion": suggestion,
        "suggestion_en": suggestion_en,
        "relevant": relevant,
        "references": sorted(set(references)),
    }


def dependency(kind, identifier, value):
    return {"kind": kind, "id": identifier, "digest": identity(value)}


def semantic_digest(value):
    ignored = {"semantic_digest", "cache", "operational", "attempt", "duration_ms"}

    def strip(item):
        if isinstance(item, dict):
            return {key: strip(child) for key, child in item.items() if key not in ignored}
        if isinstance(item, list):
            return [strip(child) for child in item]
        return item

    return identity(strip(value))


def _unique(items, field, detail):
    values = [item[field] for item in items]
    if len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _validate_inputs(value):
    if not value["module_facts"] and not value["source_facts"]:
        raise AnalysisError("input_invalid", "A6 requires at least one AST or LLVM fact input")
    paths = []
    for name in ("module_facts", "source_facts"):
        paths.extend(value[name])
    for name in ("thread_graph", "provenance_graph", "publication_graph", "root_plan",
                 "demand_graph", "candidate_graph"):
        if value[name] is not None:
            paths.append(value[name])
    seen = set()
    for item in paths:
        path = Path(item["path"])
        if "\0" in str(path):
            raise AnalysisError("input_invalid", "Input path contains NUL")
        marker = (str(path), item["sha256"])
        if marker in seen:
            raise AnalysisError("invalid_reference", "Duplicate A6 input")
        seen.add(marker)


def verify_input(reference, *, base=None):
    path = Path(reference["path"])
    if base is not None and not path.is_absolute():
        path = Path(base) / path
    if not path.is_file():
        raise AnalysisError("input_invalid", f"Missing A6 dependency: {path}")
    if file_hash(path) != reference["sha256"]:
        raise AnalysisError("input_digest", f"A6 dependency digest mismatch: {path}")
    return _load(path, "input_invalid")


def _validate_events(value):
    event_ids = _unique(value["events"], "id", "Duplicate advanced atomic event")
    for event in value["events"]:
        kind, outcome = event["kind"], event["outcome"]
        if kind == "cas":
            if outcome not in {"success", "failure", "spurious-failure"}:
                raise AnalysisError("schema_invalid", "CAS event requires an explicit outcome")
            if outcome == "success" and not (event["read_effect"] and event["write_effect"] and event["mo_member"]):
                raise AnalysisError("schema_invalid", "CAS success must be a read and MO modification")
            if outcome != "success" and (event["write_effect"] or event["mo_member"]):
                raise AnalysisError("schema_invalid", "CAS failure must be read-only and outside MO")
        elif outcome != "single":
            raise AnalysisError("schema_invalid", "Only CAS may have conditional outcomes")
        if kind == "fence" and (event["object_key"] is not None or event["mo_member"] or
                                event["read_effect"] or event["write_effect"]):
            raise AnalysisError("schema_invalid", "Fence cannot masquerade as an object access")
        if kind == "rmw" and not (event["read_effect"] and event["write_effect"] and event["mo_member"]):
            raise AnalysisError("schema_invalid", "RMW must be a read and MO modification")
    return event_ids


def _validate_graph(value):
    events = _validate_events(value)
    edges = _unique(value["rf_edges"], "id", "Duplicate RF edge")
    for edge in value["rf_edges"]:
        if edge.get("write_event") not in events or edge.get("read_event") not in events:
            raise AnalysisError("invalid_reference", "RF edge references a missing event")
    for order in value["mo_orders"]:
        if any(item not in events for item in order.get("events", [])):
            raise AnalysisError("invalid_reference", "MO order references a missing event")
    for assignment in value["assignments"]:
        if any(item not in edges for item in assignment.get("rf_edges", [])):
            raise AnalysisError("invalid_reference", "Assignment references a missing RF edge")
    if value["status"] == "complete" and any(item["relevant"] for item in value["frontier"]):
        raise AnalysisError("invalid_reference", "Complete communication graph has relevant frontier")


def _validate_overlay(value):
    ids = _unique(value["protocols"], "id", "Duplicate A6 protocol overlay")
    del ids
    for item in value["protocols"]:
        if item.get("assessment") not in {"risk", "discharged-within-bounded-model", "unknown", "unsupported"}:
            raise AnalysisError("schema_invalid", "Invalid A6 protocol assessment")
        if item.get("assessment") == "discharged-within-bounded-model" and item.get("frontier"):
            raise AnalysisError("invalid_reference", "A discharged A6 protocol cannot retain frontier")


def _validate_report(value):
    exit_code = value["exit_code"]
    verdict = value["verdict"]
    relevant = any(item["relevant"] for item in value["frontier"])
    if value["safety"] != "not_established":
        raise AnalysisError("schema_invalid", "A6 never establishes whole-program safety")
    if exit_code == 0 and (value["status"] != "complete" or value["findings"] or relevant or
                           verdict != "complete-no-supported-risk"):
        raise AnalysisError("invalid_reference", "Exit zero requires complete bounded analysis without risk")
    if exit_code == 3 and (not value["findings"] or verdict != "risk"):
        raise AnalysisError("invalid_reference", "Exit three requires at least one risk finding")
    if exit_code == 2 and (not relevant or verdict != "inconclusive"):
        raise AnalysisError("invalid_reference", "Exit two requires candidate-relevant frontier")
    if exit_code == 1 and verdict != "failed":
        raise AnalysisError("invalid_reference", "Exit one requires failed verdict")


def _validate_semantics(value, kind):
    if kind == "FenceRmwPublicationRequest":
        _validate_inputs(value)
    elif kind == "AdvancedAtomicLocalFacts":
        _validate_events(value)
        if value["status"] == "complete" and any(item["relevant"] for item in value["frontier"]):
            raise AnalysisError("invalid_reference", "Complete local facts have relevant frontier")
    elif kind == "BoundedAtomicCommunicationGraph":
        _validate_graph(value)
    elif kind == "AdvancedPublicationProtocolOverlay":
        _validate_overlay(value)
    elif kind == "FenceRmwPublicationReport":
        _validate_report(value)


def validate_advanced_atomic_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown advanced atomic contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    schema = _load(ROOT / "schemas/advanced_atomic.json", "advanced_atomic_schema")
    try:
        jsonschema.Draft202012Validator(
            {"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}
        ).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    _validate_semantics(value, kind)
    if kind != "FenceRmwPublicationRequest" and value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest mismatch")
    return value


def advanced_atomic_document(kind, **fields):
    protocol = expected_advanced_atomic_protocol()
    result = {
        "schema_version": 1,
        "kind": kind,
        "analysis_version": protocol["analysis_version"],
        "policy_id": protocol["policy_id"],
        **deepcopy(fields),
    }
    if kind != "FenceRmwPublicationRequest":
        result["semantic_digest"] = semantic_digest(result)
    return validate_advanced_atomic_document(result, kind)


def read_advanced_atomic_document(path, kind):
    return validate_advanced_atomic_document(_load(path, "input_invalid"), kind)


def failed_report(code, detail, detail_en=None):
    item = diagnostic(code, detail, detail_en or detail, relevant=True)
    return advanced_atomic_document(
        "FenceRmwPublicationReport",
        model_id=MODEL_ID,
        scope_id=None,
        language_standard=None,
        status="failed",
        verdict="failed",
        safety="not_established",
        exit_code=1,
        stages={"input_integrity": "failed"},
        counts={},
        outputs=[],
        cache={"hits": 0, "misses": 0},
        findings=[],
        frontier=[item],
        diagnostics=[item],
        limitations=["not-a-whole-program-safety-proof"],
    )
