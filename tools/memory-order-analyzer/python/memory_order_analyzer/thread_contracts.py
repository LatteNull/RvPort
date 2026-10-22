"""Strict P3 contracts and identities; P1/P2 documents remain immutable."""

import json
from copy import deepcopy
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, identity


ROOT = Path(__file__).resolve().parents[2]
KINDS = (
    "ThreadAnalysisRequest",
    "ThreadLocalFacts",
    "ExecutionOrderFacts",
    "ThreadContextGraph",
    "ThreadAnalysisReport",
)


def _load_json(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_thread_protocol(path=ROOT / "protocols/thread-analysis-protocol.json"):
    protocol = _load_json(path, "thread_protocol")
    schema = _load_json(ROOT / "schemas/threading.json", "thread_schema")
    try:
        maxima = {
            name: rule["maximum"]
            for name, rule in schema["$defs"]["Budgets"]["properties"].items()
        }
        expected = {
            "protocol_version": 1,
            "analysis_version": "0.1.0",
            "llvm_version": "21.1.8",
            "policy_id": "thread-sync-contexts-v1",
            "model_id": "posix-pthread-v1",
            "kinds": dict.fromkeys(KINDS, 1),
            "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("thread_schema", "Thread budget schema is invalid") from exc
    if json.dumps(protocol, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise AnalysisError("thread_protocol", "Thread protocol does not match supported schemas")
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
            raise AnalysisError("invalid_reference", "Duplicate P3 analysis evidence")
        if reference["artifact_key"] != artifact or item["source"]["artifact_key"] != artifact:
            raise AnalysisError("invalid_reference", "Foreign P3 analysis evidence")
        if reference["function_id"] != item["source"]["function_id"]:
            raise AnalysisError("invalid_reference", "P3 analysis evidence has a foreign function owner")
        for dependency in item["inputs"]:
            if "analysis_id" in dependency:
                key = (dependency["artifact_key"], dependency["function_id"], dependency["analysis_id"])
                if key not in registry:
                    raise AnalysisError("invalid_reference", "P3 analysis evidence is dangling or cyclic")
            elif dependency["artifact_key"] != artifact:
                raise AnalysisError("invalid_reference", "P3 analysis evidence has a foreign raw input")
        registry.add(marker)
    return registry


def _proof_is_closed(proof, registry):
    for reference in proof:
        if "analysis_id" in reference:
            marker = (reference["artifact_key"], reference["function_id"], reference["analysis_id"])
            if marker not in registry:
                raise AnalysisError("invalid_reference", "P3 proof references missing analysis evidence")


def _validate_semantics(value, kind):
    if kind == "ThreadLocalFacts":
        artifact = value["origin"]["artifact_key"]
        registry = _analysis_registry(value)
        sources = set()
        for call in value["calls"]:
            marker = json.dumps(call["source"], sort_keys=True)
            if marker in sources:
                raise AnalysisError("invalid_reference", "Duplicate thread call source")
            sources.add(marker)
            if call["source"]["artifact_key"] != artifact or call["function"]["artifact_key"] != artifact:
                raise AnalysisError("invalid_reference", "Foreign thread call source")
            if call["source"]["function_id"] != call["function"]["id"]:
                raise AnalysisError("invalid_reference", "Thread call has a foreign function owner")
        for item in value["provenance"]:
            if item["source"]["artifact_key"] != artifact:
                raise AnalysisError("invalid_reference", "Foreign provenance source")
            _proof_is_closed(item["proof"], registry)
        return
    if kind == "ExecutionOrderFacts":
        registry = _analysis_registry(value)
        nodes = {json.dumps(item["source"], sort_keys=True) for item in value["nodes"]}
        if len(nodes) != len(value["nodes"]):
            raise AnalysisError("invalid_reference", "Duplicate execution-order node")
        edge_ids = _unique(value["edges"], "id", "Duplicate execution-order edge")
        del edge_ids
        for edge in value["edges"]:
            if json.dumps(edge["before"], sort_keys=True) not in nodes or json.dumps(edge["after"], sort_keys=True) not in nodes:
                raise AnalysisError("invalid_reference", "Execution-order edge has a dangling endpoint")
            _proof_is_closed(edge["proof"], registry)
        return
    if kind != "ThreadContextGraph":
        return
    contexts = _unique(value["contexts"], "id", "Duplicate thread context")
    instances = _unique(value["instances"], "id", "Duplicate thread instance")
    lifecycle = _unique(value["lifecycles"], "id", "Duplicate lifecycle event")
    effects = _unique(value["effects"], "id", "Duplicate thread effect")
    anchors = _unique(value["anchors"], "id", "Duplicate thread anchor")
    _unique(value["order"], "id", "Duplicate graph order edge")
    _unique(value["mhp"], "id", "Duplicate MHP relation")
    _unique(value["synchronization"], "id", "Duplicate synchronization candidate")
    seen = set()
    roots = set()
    for item in value["instances"]:
        if item["context_id"] not in contexts:
            raise AnalysisError("invalid_reference", "Thread instance has a dangling context")
        if item["parent_id"] is None:
            roots.add(item["root_id"])
        elif item["parent_id"] not in seen:
            raise AnalysisError("invalid_reference", "Thread instance parent is dangling or cyclic")
        if (item["cardinality"] == "single") != (item["reason"] is None):
            raise AnalysisError("invalid_reference", "Invalid thread instance abstraction reason")
        seen.add(item["id"])
    endpoints = lifecycle | effects | anchors
    for item in value["lifecycles"]:
        if item["thread_instance_id"] not in instances:
            raise AnalysisError("invalid_reference", "Lifecycle event has a dangling instance")
    for item in value["effects"]:
        if item["thread_instance_id"] not in instances:
            raise AnalysisError("invalid_reference", "Thread effect has a dangling instance")
    for item in value["anchors"]:
        if item["thread_instance_id"] not in instances:
            raise AnalysisError("invalid_reference", "Thread anchor has a dangling instance")
    for edge in value["order"]:
        if edge["before"] not in endpoints or edge["after"] not in endpoints:
            raise AnalysisError("invalid_reference", "Graph order edge has a dangling endpoint")
    for item in value["mhp"]:
        if item["left"] not in instances or item["right"] not in instances or item["left"] >= item["right"]:
            raise AnalysisError("invalid_reference", "MHP pair is dangling or not canonical")
    for item in value["synchronization"]:
        if item["left_thread"] not in instances or item["right_thread"] not in instances:
            raise AnalysisError("invalid_reference", "Synchronization candidate has a dangling instance")
    if any(item["cardinality"] != "single" for item in value["instances"]):
        if value["status"] == "complete" or not value["frontier"]:
            raise AnalysisError("invalid_reference", "Merged instances require partial status and frontier")
    if not roots:
        raise AnalysisError("invalid_reference", "Thread graph has no root instance")


def validate_thread_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown thread contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    schema = _load_json(ROOT / "schemas/threading.json", "thread_schema")
    try:
        jsonschema.Draft202012Validator(
            {"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}
        ).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    _validate_semantics(value, kind)
    return value


def thread_document(kind, **fields):
    protocol = expected_thread_protocol()
    return validate_thread_document({
        "schema_version": 1,
        "kind": kind,
        "analysis_version": protocol["analysis_version"],
        "policy_id": protocol["policy_id"],
        **fields,
    }, kind)


def read_thread_document(path, kind):
    value = _load_json(path, "input_invalid")
    return validate_thread_document(value, kind)


def thread_context_id(scope_id, entry, arguments, model_id, budgets):
    return identity({"layer": "thread-context-v1", "scope": scope_id, "entry": entry,
                     "arguments": arguments, "model": model_id, "budgets": budgets})


def thread_instance_id(root_id, context_id, parent_id, create, cardinality, reason):
    return identity({"layer": "thread-instance-v1", "root": root_id, "context": context_id,
                     "parent": parent_id, "create": create, "cardinality": cardinality,
                     "reason": reason})
