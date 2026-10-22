"""Strict additive A3 contracts for bounded C++ thread lifecycle analysis."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, canonical, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/cpp_thread_lifecycle.json"
PROTOCOL = ROOT / "protocols/cpp-thread-lifecycle-protocol.json"
KINDS = (
    "CppThreadLifecycleRequest", "CppThreadLibraryProfile", "CppThreadLocalFacts",
    "CppThreadLifecycleGraph", "CppThreadLifecycleReport", "CppThreadValidationSuite",
    "CppThreadValidationTruth", "CppThreadValidationReport",
)
STATES = {
    "empty", "construction-pending", "joinable", "joined", "detached",
    "moved-from", "failed", "terminated-path", "unknown",
}


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_cpp_thread_protocol(path=PROTOCOL):
    value = _load(path, "cpp_thread_protocol")
    schema = _load(SCHEMA, "cpp_thread_schema")
    try:
        maxima = {
            name: rule["maximum"]
            for name, rule in schema["$defs"]["Budgets"]["properties"].items()
        }
        expected = {
            "protocol_version": 1,
            "analysis_version": "0.1.0",
            "llvm_version": "21.1.8",
            "policy_id": "cpp-thread-lifecycle-v1",
            "kinds": dict.fromkeys(KINDS, 1),
            "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("cpp_thread_schema", "C++ thread budget schema is invalid") from exc
    if canonical(value) != canonical(expected):
        raise AnalysisError("cpp_thread_protocol", "C++ thread protocol does not match supported schemas")
    return value


def dependency(kind, key, value):
    return {"kind": kind, "id": key, "digest": identity(value)}


def diagnostic(code, detail, detail_en, *, suggestion=None, suggestion_en=None,
               source=None, limit=4096):
    def bounded(text):
        text = str(text)
        while len(text.encode("utf-8")) > limit and text:
            text = text[:-1]
        return text or "-"
    return {
        "code": str(code), "detail": bounded(detail), "detail_en": bounded(detail_en),
        "suggestion": bounded(suggestion) if suggestion is not None else None,
        "suggestion_en": bounded(suggestion_en) if suggestion_en is not None else None,
        "source": deepcopy(source),
    }


def semantic_digest(value):
    copy = deepcopy(value)
    copy.pop("semantic_digest", None)
    if copy.get("kind") == "CppThreadLifecycleReport":
        copy.pop("cache", None)
    return identity(copy)


def library_profile_id(value):
    ignored = {"schema_version", "kind", "analysis_version", "policy_id",
               "profile_id", "semantic_digest", "status", "provenance"}
    return identity({key: item for key, item in value.items() if key not in ignored})


def _unique_sorted(items, key, detail):
    values = [key(item) for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _dependencies(items, detail="Dependencies must be unique and sorted"):
    return _unique_sorted(items, lambda item: (item["kind"], item["id"]), detail)


def _validate_request(value):
    member_ids = _unique_sorted(value["members"], lambda item: item["physical_tu_id"],
                                "Request members must be unique and sorted")
    del member_ids
    if value["roots"] != sorted(set(value["roots"])):
        raise AnalysisError("invalid_reference", "Request roots must be unique and sorted")
    declared = _dependencies(value["dependencies"])
    profiles = _dependencies(value["library_profiles"], "Library profiles must be unique and sorted")
    for profile in value["library_profiles"]:
        if profile["kind"] != "CppThreadLibraryProfile":
            raise AnalysisError("invalid_reference", "A3 library profile dependency has a wrong kind")
    for member in value["members"]:
        allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if member["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
        if member["standard"] not in allowed:
            raise AnalysisError("profile_conflict", "Member language and standard disagree")
        if member["language"] == "c" and value["library_profiles"]:
            # Mixed scopes are valid; C members simply cannot carry C++ local evidence.
            pass
        for reference in (member["source_facts"], member["ir_facts"]):
            if reference is not None and (reference["kind"], reference["id"]) not in declared:
                raise AnalysisError("invalid_reference", "Member evidence is missing from request dependencies")
    if not profiles and any(item["language"] == "c++" for item in value["members"]):
        raise AnalysisError("invalid_reference", "C++ members require an explicit library profile dependency")


def _validate_profile(value):
    if value["profile_id"] != library_profile_id(value):
        raise AnalysisError("profile_digest", "C++ thread library profile identity does not match content")
    _dependencies(value["header_digests"], "Header digests must be unique and sorted")
    roles = _unique_sorted(value["wrapper_signatures"], lambda item: (item["role"], item["symbol"]),
                           "Wrapper signatures must be unique and sorted")
    del roles
    for item in value["wrapper_signatures"]:
        if item["parameter_roles"] != sorted(set(item["parameter_roles"])):
            raise AnalysisError("invalid_reference", "Wrapper parameter roles must be unique and sorted")
    if value["provenance"] != sorted(set(value["provenance"])):
        raise AnalysisError("invalid_reference", "Profile provenance must be unique and sorted")


def _validate_local(value):
    allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if value["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
    if value["standard"] not in allowed:
        raise AnalysisError("profile_conflict", "Local facts language and standard disagree")
    callables = _unique_sorted(value["callables"], lambda item: item["id"],
                               "Callables must be unique and sorted")
    operations = _unique_sorted(value["operations"], lambda item: item["id"],
                                "Operations must be unique and sorted")
    _dependencies(value["dependencies"])
    if value["language"] == "c" and (callables or operations or value["library_profile_id"] is not None):
        raise AnalysisError("profile_conflict", "C local facts cannot adopt the C++ thread library model")
    for item in value["callables"]:
        for name in ("capture_ids", "targets", "source_nodes", "ir_nodes"):
            if item[name] != sorted(set(item[name])):
                raise AnalysisError("invalid_reference", f"Callable {name} must be unique and sorted")
        if item["resolution"] == "exact" and len(item["targets"]) != 1:
            raise AnalysisError("invalid_reference", "Exact callable requires one target")
    for item in value["operations"]:
        if item["callable_id"] is not None and item["callable_id"] not in callables:
            raise AnalysisError("invalid_reference", "Operation has a dangling callable")
        for name in ("source_nodes", "ir_nodes"):
            if item[name] != sorted(set(item[name])):
                raise AnalysisError("invalid_reference", f"Operation {name} must be unique and sorted")


def _validate_graph(value):
    _dependencies(value["profiles"], "Graph profiles must be unique and sorted")
    _dependencies(value["dependencies"])
    objects = _unique_sorted(value["objects"], lambda item: item["id"], "Object states must be unique and sorted")
    contexts = _unique_sorted(value["contexts"], lambda item: item["id"], "Contexts must be unique and sorted")
    instances = _unique_sorted(value["instances"], lambda item: item["id"], "Instances must be unique and sorted")
    transitions = _unique_sorted(value["transitions"], lambda item: item["id"], "Transitions must be unique and sorted")
    relations = _unique_sorted(value["relations"], lambda item: item["id"], "Relations must be unique and sorted")
    gaps = _unique_sorted(value["gaps"], lambda item: item["id"], "Gaps must be unique and sorted")
    del objects, transitions, relations, gaps
    for item in value["instances"]:
        if item["context_id"] not in contexts:
            raise AnalysisError("invalid_reference", "Thread instance has a dangling context")
        if item["parent_id"] is not None and item["parent_id"] not in instances:
            raise AnalysisError("invalid_reference", "Thread instance has a dangling parent")
        if item["cardinality"] == "single" and item["reason"] is not None:
            raise AnalysisError("invalid_reference", "Single instance cannot have an abstraction reason")
        if item["cardinality"] != "single" and item["reason"] is None:
            raise AnalysisError("invalid_reference", "Merged instance requires an abstraction reason")
    for item in value["objects"]:
        if item["state"] not in STATES:
            raise AnalysisError("invalid_reference", "Unknown thread object state")
        if item["instance_id"] is not None and item["instance_id"] not in instances:
            raise AnalysisError("invalid_reference", "Object state has a dangling instance")
    if any(item["cardinality"] != "single" for item in value["instances"]):
        if value["status"] == "complete" or not value["frontier"]:
            raise AnalysisError("invalid_reference", "Merged instances require partial status and frontier")
    if value["status"] == "complete" and (value["gaps"] or value["frontier"]):
        raise AnalysisError("invalid_reference", "Complete lifecycle graph cannot contain gaps or frontier")


def _validate_report(value):
    expected = 1 if value["status"] == "failed" else 2 if value["status"] == "partial" else 0
    if value["exit_code"] != expected:
        raise AnalysisError("report_status", "Lifecycle report exit code does not match completeness")
    _dependencies(value["profiles"], "Report profiles must be unique and sorted")
    _dependencies(value["dependencies"])
    if value["graph"] is not None and (value["graph"]["kind"], value["graph"]["id"]) not in _dependencies(value["dependencies"]):
        raise AnalysisError("invalid_reference", "Report graph is missing from dependencies")


def _validate_validation(value):
    if value["kind"] == "CppThreadValidationSuite":
        _unique_sorted(value["cases"], lambda item: item["id"], "Validation cases must be unique and sorted")
        standards = {item["standard"] for item in value["cases"]}
        if standards != {"c11", "c17", "c++17", "c++20"}:
            raise AnalysisError("validation_denominator", "Validation suite must cover all four profiles independently")
        vendors = {item["vendor"] for item in value["cases"] if item["language"] == "c++"}
        if not {"libstdc++", "libc++"} <= vendors:
            raise AnalysisError("validation_denominator", "C++ truth must cover libstdc++ and libc++")
    elif value["kind"] == "CppThreadValidationTruth":
        _unique_sorted(value["cases"], lambda item: item["case_id"], "Truth cases must be unique and sorted")
        for item in value["cases"]:
            for field in ("callables", "instances", "relations", "unknown"):
                if item[field] != sorted(set(item[field])):
                    raise AnalysisError("validation_denominator", f"Truth {field} must be unique and sorted")


def validate_cpp_thread_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown C++ thread contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    schema = _load(SCHEMA, "cpp_thread_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "CppThreadLifecycleRequest":
        _validate_request(value)
    elif kind == "CppThreadLibraryProfile":
        _validate_profile(value)
    elif kind == "CppThreadLocalFacts":
        _validate_local(value)
    elif kind == "CppThreadLifecycleGraph":
        _validate_graph(value)
    elif kind == "CppThreadLifecycleReport":
        _validate_report(value)
    elif kind.startswith("CppThreadValidation"):
        _validate_validation(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def cpp_thread_document(kind, **fields):
    protocol = expected_cpp_thread_protocol()
    result = {
        "schema_version": 1, "kind": kind,
        "analysis_version": protocol["analysis_version"],
        "policy_id": protocol["policy_id"], **fields,
    }
    if result.get("semantic_digest") is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_cpp_thread_document(result, kind)


def read_cpp_thread_document(path, kind):
    return validate_cpp_thread_document(_load(path, "input_invalid"), kind)
