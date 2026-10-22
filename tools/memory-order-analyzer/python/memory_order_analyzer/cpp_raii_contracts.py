"""Strict additive A4 contracts for bounded C++ RAII synchronization."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, canonical, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/cpp_raii_synchronization.json"
PROTOCOL = ROOT / "protocols/cpp-raii-synchronization-protocol.json"
KINDS = (
    "CppRaiiSynchronizationRequest", "CppRaiiSynchronizationProfile",
    "CppRaiiLocalFacts", "CppRaiiSynchronizationGraph",
    "CppRaiiSynchronizationReport", "CppRaiiValidationSuite",
    "CppRaiiValidationTruth", "CppRaiiValidationReport",
)
OWNER_STATES = {"uninitialized", "owns", "deferred", "moved-from", "released", "unknown"}
WRAPPER_ROLES = {
    "mutex-lock", "mutex-unlock", "owner-construct", "owner-destruct",
    "owner-move", "owner-lock", "owner-unlock", "owner-owns-lock", "scoped-lock",
}


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_cpp_raii_protocol(path=PROTOCOL):
    value = _load(path, "cpp_raii_protocol")
    schema = _load(SCHEMA, "cpp_raii_schema")
    try:
        maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {
            "protocol_version": 1,
            "analysis_version": "0.1.0",
            "llvm_version": "21.1.8",
            "policy_id": "cpp-raii-synchronization-v1",
            "kinds": dict.fromkeys(KINDS, 1),
            "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("cpp_raii_schema", "C++ RAII budget schema is invalid") from exc
    if canonical(value) != canonical(expected):
        raise AnalysisError("cpp_raii_protocol", "C++ RAII protocol does not match supported schemas")
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
        "limitation": bounded(limitation or "受限模型结果不代表全程序安全证明"),
        "limitation_en": bounded(limitation_en or "A bounded-model result is not a whole-program safety proof"),
        "suggestion": bounded(suggestion) if suggestion is not None else None,
        "suggestion_en": bounded(suggestion_en) if suggestion_en is not None else None,
        "source": deepcopy(source),
    }


def semantic_digest(value):
    copy = deepcopy(value)
    copy.pop("semantic_digest", None)
    if copy.get("kind") == "CppRaiiSynchronizationReport":
        copy.pop("cache", None)
    return identity(copy)


def synchronization_profile_id(value):
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
    _unique_sorted(value["members"], lambda item: item["physical_tu_id"],
                   "Request members must be unique and sorted")
    if value["roots"] != sorted(set(value["roots"])):
        raise AnalysisError("invalid_reference", "Request roots must be unique and sorted")
    declared = _dependencies(value["dependencies"])
    _dependencies(value["synchronization_profiles"], "Synchronization profiles must be unique and sorted")
    if len(value["synchronization_profiles"]) > value["budgets"]["profiles"]:
        raise AnalysisError("profile_budget", "A4 request exceeds its profile budget")
    for profile in value["synchronization_profiles"]:
        if profile["kind"] != "CppRaiiSynchronizationProfile":
            raise AnalysisError("invalid_reference", "A4 synchronization profile has a wrong kind")
    for member in value["members"]:
        allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if member["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
        if member["standard"] not in allowed:
            raise AnalysisError("profile_conflict", "Member language and standard disagree")
        for reference in (member["source_facts"], member["ir_facts"]):
            if reference is not None and (reference["kind"], reference["id"]) not in declared:
                raise AnalysisError("invalid_reference", "Member evidence is missing from request dependencies")
    cpp_standards = {item["standard"] for item in value["members"] if item["language"] == "c++"}
    if cpp_standards and not value["synchronization_profiles"]:
        raise AnalysisError("invalid_reference", "C++ members require explicit A4 synchronization profiles")


def _validate_profile(value):
    if value["profile_id"] != synchronization_profile_id(value):
        raise AnalysisError("profile_digest", "C++ RAII profile identity does not match content")
    _dependencies(value["header_digests"], "Header digests must be unique and sorted")
    _unique_sorted(value["wrapper_signatures"], lambda item: (item["role"], item["symbol"]),
                   "Wrapper signatures must be unique and sorted")
    roles = {item["role"] for item in value["wrapper_signatures"]}
    if not {"mutex-lock", "mutex-unlock"} <= roles:
        raise AnalysisError("abi_wrapper_mismatch", "Verified A4 profiles require lock and unlock wrappers")
    for item in value["wrapper_signatures"]:
        if item["role"] not in WRAPPER_ROLES or item["parameter_roles"] != sorted(set(item["parameter_roles"])):
            raise AnalysisError("invalid_reference", "Invalid or unsorted A4 wrapper signature")
    if value["provenance"] != sorted(set(value["provenance"])):
        raise AnalysisError("invalid_reference", "Profile provenance must be unique and sorted")


def _validate_local(value):
    allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if value["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
    if value["standard"] not in allowed:
        raise AnalysisError("profile_conflict", "A4 local language and standard disagree")
    mutexes = _unique_sorted(value["mutexes"], lambda item: item["id"], "Mutexes must be unique and sorted")
    owners = _unique_sorted(value["owners"], lambda item: item["id"], "Owners must be unique and sorted")
    operations = _unique_sorted(value["operations"], lambda item: item["id"], "Operations must be unique and sorted")
    accesses = _unique_sorted(value["accesses"], lambda item: item["id"], "Accesses must be unique and sorted")
    _dependencies(value["dependencies"])
    if value["language"] == "c" and (value["synchronization_profile_id"] is not None or any(
            item["owner_kind"] != "pthread-direct" for item in value["owners"])):
        raise AnalysisError("profile_conflict", "C local facts cannot adopt the C++ RAII model")
    for owner in value["owners"]:
        if owner["state"] not in OWNER_STATES or not set(owner["mutex_ids"]) <= mutexes:
            raise AnalysisError("invalid_reference", "Owner has invalid state or dangling mutex")
    for operation in value["operations"]:
        if operation["owner_id"] is not None and operation["owner_id"] not in owners:
            raise AnalysisError("invalid_reference", "Operation has a dangling owner")
        if not set(operation["mutex_ids"]) <= mutexes:
            raise AnalysisError("invalid_reference", "Operation has a dangling mutex")
    for access in value["accesses"]:
        if access.get("owner_id") not in owners:
            raise AnalysisError("invalid_reference", "Access has a dangling owner")
        if access.get("access_kind") not in {"read", "write", "read-write", "unknown"}:
            raise AnalysisError("invalid_reference", "Access has an invalid kind")
    if value["status"] == "complete" and value["frontier"]:
        raise AnalysisError("invalid_reference", "Complete A4 local facts cannot contain frontier")


def _validate_graph(value):
    _dependencies(value["profiles"], "Graph profiles must be unique and sorted")
    _dependencies(value["dependencies"])
    mutexes = _unique_sorted(value["mutexes"], lambda item: item["id"], "Graph mutexes must be unique and sorted")
    owners = _unique_sorted(value["owners"], lambda item: item["id"], "Graph owners must be unique and sorted")
    operations = _unique_sorted(value["operations"], lambda item: item["id"], "Graph operations must be unique and sorted")
    accesses = _unique_sorted(value["accesses"], lambda item: item["id"], "Graph accesses must be unique and sorted")
    regions = _unique_sorted(value["held_regions"], lambda item: item["id"], "Held regions must be unique and sorted")
    _unique_sorted(value["proofs"], lambda item: item["id"], "Proofs must be unique and sorted")
    for owner in value["owners"]:
        if owner["state"] not in OWNER_STATES or not set(owner["mutex_ids"]) <= mutexes:
            raise AnalysisError("invalid_reference", "Graph owner has invalid state or dangling mutex")
    for region in value["held_regions"]:
        if (region["owner_id"] not in owners or not set(region["mutex_ids"]) <= mutexes
                or region["acquire_id"] not in operations or region["release_id"] not in operations
                or not set(region["access_ids"]) <= accesses):
            raise AnalysisError("invalid_reference", "Held region has dangling references")
    for proof in value["proofs"]:
        if proof["mutex_id"] not in mutexes or not set(proof["region_ids"]) <= regions:
            raise AnalysisError("invalid_reference", "A4 proof has dangling references")
        if proof["status"] != "complete":
            raise AnalysisError("invalid_reference", "Published A4 proofs must be complete")
    if value["status"] == "complete" and (value["gaps"] or value["frontier"]):
        raise AnalysisError("invalid_reference", "Complete A4 graph cannot contain gaps or frontier")


def _validate_report(value):
    expected = 1 if value["status"] == "failed" else 2 if value["status"] == "partial" else 0
    if value["exit_code"] != expected:
        raise AnalysisError("report_status", "A4 report exit code does not match completeness")
    _dependencies(value["profiles"], "Report profiles must be unique and sorted")
    declared = _dependencies(value["dependencies"])
    if value["graph"] is not None and (value["graph"]["kind"], value["graph"]["id"]) not in declared:
        raise AnalysisError("invalid_reference", "A4 report graph is missing from dependencies")


def _validate_validation(value):
    if value["kind"] == "CppRaiiValidationReport":
        required_languages = {"c11", "c17", "c++17", "c++20"}
        if set(value["languages"]) != required_languages:
            raise AnalysisError("validation_denominator", "A4 report must preserve all four language denominators")
        return
    _unique_sorted(value["cases"], lambda item: item.get("id", item.get("case_id")),
                   "A4 validation cases must be unique and sorted")
    if value["kind"] == "CppRaiiValidationSuite":
        standards = {item.get("standard") for item in value["cases"]}
        if standards != {"c11", "c17", "c++17", "c++20"}:
            raise AnalysisError("validation_denominator", "A4 suite must cover all four standards")
        vendors = {item.get("vendor") for item in value["cases"] if item.get("language") == "c++"}
        if not {"libstdc++", "libc++"} <= vendors:
            raise AnalysisError("validation_denominator", "A4 C++ truth requires libstdc++ and libc++")
    elif value["kind"] == "CppRaiiValidationTruth":
        for item in value["cases"]:
            for field in ("mutexes", "owners", "regions", "proofs", "unknown"):
                if item.get(field, []) != sorted(set(item.get(field, []))):
                    raise AnalysisError("validation_denominator", f"Truth {field} must be unique and sorted")


def validate_cpp_raii_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown C++ RAII contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    schema = _load(SCHEMA, "cpp_raii_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "CppRaiiSynchronizationRequest":
        _validate_request(value)
    elif kind == "CppRaiiSynchronizationProfile":
        _validate_profile(value)
    elif kind == "CppRaiiLocalFacts":
        _validate_local(value)
    elif kind == "CppRaiiSynchronizationGraph":
        _validate_graph(value)
    elif kind == "CppRaiiSynchronizationReport":
        _validate_report(value)
    elif kind.startswith("CppRaiiValidation"):
        _validate_validation(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def cpp_raii_document(kind, **fields):
    protocol = expected_cpp_raii_protocol()
    result = {
        "schema_version": 1, "kind": kind,
        "analysis_version": protocol["analysis_version"],
        "policy_id": protocol["policy_id"], **fields,
    }
    if result.get("semantic_digest") is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_cpp_raii_document(result, kind)


def read_cpp_raii_document(path, kind):
    return validate_cpp_raii_document(_load(path, "input_invalid"), kind)
