"""Strict P4 contracts; earlier analysis products remain immutable dependencies."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, identity


ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "c-cpp-single-publication-v1"
KINDS = (
    "PublicationRiskRequest",
    "PublicationLocalFacts",
    "SinglePublicationProtocolGraph",
    "PublicationRiskReport",
)


def _load_json(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_publication_protocol(path=ROOT / "protocols/publication-analysis-protocol.json"):
    protocol = _load_json(path, "publication_protocol")
    schema = _load_json(ROOT / "schemas/publication.json", "publication_schema")
    try:
        maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {
            "protocol_version": 1,
            "analysis_version": "0.1.0",
            "llvm_version": "21.1.8",
            "policy_id": "single-publication-risks-v1",
            "model_id": MODEL_ID,
            "kinds": dict.fromkeys(KINDS, 1),
            "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("publication_schema", "Publication budget schema is invalid") from exc
    if json.dumps(protocol, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise AnalysisError("publication_protocol", "Publication protocol does not match supported schemas")
    return protocol


def diagnostic(code, detail, detail_en, *, source=None, context=None, instance=None,
               suggestion=None, suggestion_en=None):
    return {
        "code": code,
        "detail": detail,
        "detail_en": detail_en,
        "suggestion": suggestion,
        "suggestion_en": suggestion_en,
        "source": deepcopy(source),
        "thread_context_id": context,
        "thread_instance_id": instance,
    }


def _unique(items, field, detail):
    values = [item[field] for item in items]
    if len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _analysis_registry(value):
    artifact = value["origin"]["artifact_key"]
    registry = set()
    for item in value["analysis_evidence"]:
        reference = item["ref"]
        marker = (reference["artifact_key"], reference["function_id"], reference["analysis_id"])
        if marker in registry:
            raise AnalysisError("invalid_reference", "Duplicate P4 analysis evidence")
        if reference["artifact_key"] != artifact or item["source"]["artifact_key"] != artifact:
            raise AnalysisError("invalid_reference", "Foreign P4 analysis evidence")
        if reference["function_id"] != item["source"]["function_id"]:
            raise AnalysisError("invalid_reference", "P4 analysis evidence has a foreign function owner")
        for dependency in item["inputs"]:
            if "analysis_id" in dependency:
                key = (dependency["artifact_key"], dependency["function_id"], dependency["analysis_id"])
                if key not in registry:
                    raise AnalysisError("invalid_reference", "P4 analysis evidence is dangling or cyclic")
            elif dependency["artifact_key"] != artifact:
                raise AnalysisError("invalid_reference", "P4 analysis evidence has a foreign raw input")
        registry.add(marker)
    return registry


def _proof_is_closed(proof, registry):
    for reference in proof:
        if "analysis_id" in reference:
            marker = (reference["artifact_key"], reference["function_id"], reference["analysis_id"])
            if marker not in registry:
                raise AnalysisError("invalid_reference", "P4 proof references missing analysis evidence")


def outcome_counts(protocols, assessments):
    statuses = {name: sum(item["status"] == name for item in protocols)
                for name in ("candidate", "evaluated", "unknown", "unsupported", "excluded")}
    finding = sum(item["status"] == "finding" for item in assessments)
    discharged = sum(item["status"] == "discharged" for item in assessments)
    evaluated = statuses["evaluated"]
    planned = len(protocols)
    return {
        "planned": planned,
        "candidate": statuses["candidate"],
        "evaluated": evaluated,
        "finding": finding,
        "discharged": discharged,
        "unknown": statuses["unknown"] + sum(item["status"] == "unknown" for item in assessments),
        "unsupported": statuses["unsupported"] + sum(item["status"] == "unsupported" for item in assessments),
        "excluded": statuses["excluded"],
        "evaluated_ratio": evaluated / planned if planned else None,
    }


def layer_counts(items):
    values = {name: sum(item["status"] == name for item in items)
              for name in ("complete", "partial", "failed", "not_run")}
    total = len(items)
    return {"planned": total, **values,
            "complete_ratio": values["complete"] / total if total else None}


def _validate_local(value):
    artifact = value["origin"]["artifact_key"]
    registry = _analysis_registry(value)
    accesses = _unique(value["accesses"], "id", "Duplicate publication access")
    observations = _unique(value["observations"], "id", "Duplicate publication observation")
    _unique(value["initializers"], "id", "Duplicate publication initializer")
    _unique(value["gates"], "id", "Duplicate publication gate")
    _unique(value["returns"], "id", "Duplicate publication return dependency")
    _unique(value["order"], "id", "Duplicate publication order edge")
    for category in ("accesses", "initializers", "observations", "gates", "returns", "order"):
        for item in value[category]:
            source = item.get("source") or item.get("terminator") or item.get("before")
            if source and source["artifact_key"] != artifact:
                raise AnalysisError("invalid_reference", "Foreign publication-local source")
            _proof_is_closed(item["proof"], registry)
    for item in value["observations"]:
        if item["access_id"] not in accesses:
            raise AnalysisError("invalid_reference", "Observation has a dangling access")
    for item in value["gates"]:
        if item["observation_id"] not in observations:
            raise AnalysisError("invalid_reference", "Gate has a dangling observation")
    for item in value["returns"]:
        if item["observation_id"] not in observations:
            raise AnalysisError("invalid_reference", "Return dependency has a dangling observation")
    access_sources = {json.dumps(item["source"], sort_keys=True) for item in value["accesses"]}
    for item in value["order"]:
        if item["after"]["artifact_key"] != artifact:
            raise AnalysisError("invalid_reference", "Foreign publication-local order endpoint")
        if item["before"]["function_id"] != item["after"]["function_id"]:
            raise AnalysisError("invalid_reference", "Publication-local order crosses functions")
        if (json.dumps(item["before"], sort_keys=True) not in access_sources or
                json.dumps(item["after"], sort_keys=True) not in access_sources):
            raise AnalysisError("invalid_reference", "Publication-local order has a dangling access")
    if value["status"] == "complete" and value["frontier"]:
        raise AnalysisError("invalid_reference", "Complete publication-local facts have a frontier")


def _validate_graph(value):
    observations = _unique(value["successful_observations"], "id", "Duplicate successful observation")
    protocols = _unique(value["protocols"], "id", "Duplicate publication protocol")
    assessments = _unique(value["assessments"], "id", "Duplicate publication assessment")
    dependency_keys = [(item["kind"], item["id"]) for item in value["dependencies"]]
    if len(dependency_keys) != len(set(dependency_keys)):
        raise AnalysisError("invalid_reference", "Duplicate publication dependency")
    for item in value["protocols"]:
        if item["successful_observation"] not in observations:
            raise AnalysisError("invalid_reference", "Protocol has a dangling successful observation")
        if any(identifier not in assessments for identifier in item["assessment_ids"]):
            raise AnalysisError("invalid_reference", "Protocol has a dangling assessment")
    for item in value["assessments"]:
        if item["protocol_id"] not in protocols:
            raise AnalysisError("invalid_reference", "Assessment has a dangling protocol")
    if value["counts"] != outcome_counts(value["protocols"], value["assessments"]):
        raise AnalysisError("invalid_reference", "Publication outcome counts do not match graph contents")
    if value["status"] == "complete" and value["frontier"]:
        raise AnalysisError("invalid_reference", "Complete publication graph has a frontier")


def _validate_report(value):
    if value["member_counts"] != layer_counts(value["members"]):
        raise AnalysisError("invalid_reference", "Publication member counts do not match plan")
    findings = [item for item in value["findings"] if item["status"] == "finding"]
    if len(findings) != len(value["findings"]):
        raise AnalysisError("invalid_reference", "Report findings contain a non-finding assessment")
    if value["outcome_counts"]["finding"] != len(findings):
        raise AnalysisError("invalid_reference", "Report finding count mismatch")
    stages = [value[name] for name in (
        "input_integrity", "p1_analysis", "p2_analysis", "p3_analysis",
        "publication_local_analysis", "candidate_modeling", "risk_evaluation",
    )]
    if value["exit_code"] == 0 and (set(stages) != {"complete"} or findings):
        raise AnalysisError("invalid_reference", "Exit zero requires complete stages and zero findings")
    if value["exit_code"] == 3 and (set(stages) != {"complete"} or not findings):
        raise AnalysisError("invalid_reference", "Exit three requires complete stages and findings")
    if value["exit_code"] == 2 and all(state == "complete" for state in stages):
        raise AnalysisError("invalid_reference", "Exit two requires an incomplete stage")
    if value["exit_code"] == 1 and value["verdict"] != "failed":
        raise AnalysisError("invalid_reference", "Exit one requires failed verdict")


def _validate_semantics(value, kind):
    if kind == "PublicationRiskRequest":
        if "\0" in value["thread_request"]:
            raise AnalysisError("invalid_reference", "Thread request path contains NUL")
    elif kind == "PublicationLocalFacts":
        _validate_local(value)
    elif kind == "SinglePublicationProtocolGraph":
        _validate_graph(value)
    elif kind == "PublicationRiskReport":
        _validate_report(value)


def validate_publication_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown publication contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    schema = _load_json(ROOT / "schemas/publication.json", "publication_schema")
    try:
        jsonschema.Draft202012Validator(
            {"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}
        ).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    _validate_semantics(value, kind)
    return value


def publication_document(kind, **fields):
    protocol = expected_publication_protocol()
    return validate_publication_document({
        "schema_version": 1,
        "kind": kind,
        "analysis_version": protocol["analysis_version"],
        "policy_id": protocol["policy_id"],
        **fields,
    }, kind)


def read_publication_document(path, kind):
    return validate_publication_document(_load_json(path, "input_invalid"), kind)


def successful_observation_id(local_observation_id, thread_effect_id, thread_instance_id,
                              invocation_id, predicate, gate_id):
    return identity({
        "layer": "successful-observation-v1",
        "local_observation": local_observation_id,
        "thread_effect": thread_effect_id,
        "thread_instance": thread_instance_id,
        "invocation": invocation_id,
        "predicate": predicate,
        "gate": gate_id,
    })


def protocol_candidate_id(**roles):
    return identity({"layer": "single-publication-protocol-v1", **roles})
