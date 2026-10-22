"""Strict versioned contracts for evidence-driven thread-entry discovery."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/thread_entry_discovery.json"
PROTOCOL = ROOT / "protocols/thread-entry-discovery-protocol.json"
KINDS = (
    "ThreadEntryDiscoveryRequest", "ThreadEntryLocalFacts", "ThreadEntrySiteIndex",
    "ThreadEntryRootOverlay", "ThreadEntryDiscoveryReport",
)
EVIDENCE_STATUSES = {
    "dual-exact", "ir-exact", "source-candidate", "ir-candidate",
    "ambiguous", "unsupported", "failed",
}
EXECUTION_SEMANTICS = {
    "creates-thread", "may-create-thread", "does-not-create-thread", "unknown",
}
ROOT_DISPOSITIONS = {"adopted", "conditional-frontier", "excluded", "frontier"}
API_FAMILIES = {"pthread", "c11-thread", "std-thread", "std-jthread", "std-async", "framework"}


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_thread_entry_protocol(path=PROTOCOL):
    value = _load(path, "thread_entry_protocol")
    schema = _load(SCHEMA, "thread_entry_schema")
    maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
    expected = {
        "protocol_version": 1, "analysis_version": "0.1.0", "llvm_version": "21.1.8",
        "policy_id": "thread-entry-discovery-v1", "cache_namespace": "thread-entry-discovery-v1",
        "kinds": dict.fromkeys(KINDS, 1), "budgets": maxima,
    }
    if value != expected:
        raise AnalysisError("thread_entry_protocol", "Thread-entry protocol and schema maxima disagree")
    return value


def dependency(kind, key, value):
    return {"kind": str(kind), "id": str(key), "digest": identity(value)}


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
                              "入口发现不建立 MHP、同步、happens-before、风险或安全结论"),
        "limitation_en": bounded(limitation_en or
                                 "Entry discovery does not establish MHP, synchronization, happens-before, risk, or safety"),
        "suggestion": bounded(suggestion) if suggestion is not None else None,
        "suggestion_en": bounded(suggestion_en) if suggestion_en is not None else None,
        "source": deepcopy(source),
    }


def semantic_digest(value):
    copy = deepcopy(value)
    copy.pop("semantic_digest", None)
    if copy.get("kind") == "ThreadEntryDiscoveryReport":
        copy.pop("cache", None)
    return identity(copy)


def model_profile_digest(value):
    copy = deepcopy(value)
    copy.pop("digest", None)
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


def validate_model_profile(profile):
    schema = _load(SCHEMA, "thread_entry_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": "#/$defs/ModelProfile", "$defs": schema["$defs"]}).validate(profile)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("model_profile_invalid", str(exc)) from exc
    if profile["api_family"] not in API_FAMILIES:
        raise AnalysisError("model_profile_invalid", "Unknown API family")
    allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if profile["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
    if not set(profile["standards"]) <= allowed:
        raise AnalysisError("profile_conflict", "Model language and standards disagree")
    _unique_sorted(profile["header_digests"], lambda item: (item["kind"], item["id"]),
                   "Model header digests must be unique and sorted")
    _unique_sorted(profile["canonical_entities"], lambda item: item.get("id", ""),
                   "Model canonical entities must be uniquely identified and sorted")
    _unique_sorted(profile["brokers"], lambda item: (item.get("role", ""), item.get("symbol", "")),
                   "Model brokers must be unique and sorted")
    if profile["digest"] != model_profile_digest(profile):
        raise AnalysisError("semantic_digest", "Thread-entry model profile digest does not match content")
    return profile


def _validate_request(value):
    _unique_sorted(value["members"], lambda item: item["physical_tu_id"],
                   "Request members must be unique and sorted")
    _validate_inputs(value["global_evidence"], "Global evidence must be unique and sorted")
    all_inputs = {(item["kind"], item["id"]) for item in value["global_evidence"]}
    if len(value["members"]) > value["budgets"]["translation_units"]:
        raise AnalysisError("translation-unit-budget", "Request exceeds the translation unit budget")
    for member in value["members"]:
        allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if member["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
        if member["standard"] not in allowed:
            raise AnalysisError("profile_conflict", "Member language and standard disagree")
        _validate_inputs(member["evidence"], "Member evidence must be unique and sorted")
        for item in member["evidence"]:
            key = (item["kind"], item["id"])
            if key in all_inputs:
                raise AnalysisError("invalid_reference", "Evidence input is declared more than once")
            all_inputs.add(key)
        if member["language"] == "c" and any(item["kind"].startswith("Cpp") for item in member["evidence"]):
            raise AnalysisError("profile_conflict", "C members cannot depend on C++ models")
    _unique_sorted(value["model_profiles"], lambda item: item["id"],
                   "Model profiles must be unique and sorted")
    if len(value["model_profiles"]) > value["budgets"]["profiles"]:
        raise AnalysisError("profile-budget", "Request exceeds the model profile budget")
    for profile in value["model_profiles"]:
        validate_model_profile(profile)
    _unique_sorted(value["framework_descriptors"], lambda item: item.get("id", ""),
                   "Framework descriptors must be uniquely identified and sorted")


def _validate_candidate(candidate, layer):
    required = {"id", "layer", "physical_tu_id", "profile_id", "api_family", "model_id",
                "callsite_id", "operation", "callback", "launch_policy", "guard", "evidence",
                "status", "reason", "metadata"}
    if set(candidate) != required:
        raise AnalysisError("candidate_invalid", f"Candidate fields disagree: {sorted(set(candidate) ^ required)}")
    if candidate["layer"] != layer or candidate["api_family"] not in API_FAMILIES:
        raise AnalysisError("candidate_invalid", "Candidate layer or API family is invalid")
    if candidate["status"] not in {"exact", "candidate", "unknown", "unsupported", "failed", "excluded"}:
        raise AnalysisError("candidate_invalid", "Candidate status is invalid")
    if candidate["callback"].get("candidates", []) != sorted(candidate["callback"].get("candidates", []), key=str):
        raise AnalysisError("candidate_invalid", "Callback candidates must be sorted")
    if candidate["evidence"] != sorted(set(candidate["evidence"])):
        raise AnalysisError("candidate_invalid", "Candidate evidence must be unique and sorted")


def _validate_local_facts(value):
    for field, layer in (("source_candidates", "source"), ("ir_candidates", "ir")):
        _unique_sorted(value[field], lambda item: item["id"], f"{field} must be unique and sorted")
        for candidate in value[field]:
            _validate_candidate(candidate, layer)
    _dependencies(value["dependencies"])
    allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if value["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
    if value["standard"] not in allowed:
        raise AnalysisError("profile_conflict", "Local fact language and standard disagree")


def _validate_site(site):
    required = {"id", "physical_tu_id", "profile_id", "api_family", "model_id", "callsite_id",
                "observations", "evidence_status", "execution_semantics", "root_disposition",
                "callback", "object_lineage", "handle_lineage", "guard", "cardinality",
                "evidence", "opposed", "reason"}
    if set(site) != required:
        raise AnalysisError("site_invalid", f"Site fields disagree: {sorted(set(site) ^ required)}")
    if site["api_family"] not in API_FAMILIES or site["evidence_status"] not in EVIDENCE_STATUSES:
        raise AnalysisError("site_invalid", "Site API family or evidence status is invalid")
    if site["execution_semantics"] not in EXECUTION_SEMANTICS or site["root_disposition"] not in ROOT_DISPOSITIONS:
        raise AnalysisError("site_invalid", "Site execution semantics or disposition is invalid")
    if site["observations"] != sorted(set(site["observations"])):
        raise AnalysisError("site_invalid", "Site observations must be unique and sorted")
    if site["evidence"] != sorted(set(site["evidence"])) or site["opposed"] != sorted(set(site["opposed"])):
        raise AnalysisError("site_invalid", "Site evidence and opposed evidence must be unique and sorted")
    if site["root_disposition"] == "adopted":
        if site["execution_semantics"] != "creates-thread" or not site["callback"].get("entry"):
            raise AnalysisError("site_invalid", "Adopted sites require creates-thread semantics and an exact callback")
        if site["evidence_status"] not in {"dual-exact", "ir-exact"}:
            raise AnalysisError("site_invalid", "Adopted sites require exact evidence")
    if site["execution_semantics"] == "does-not-create-thread" and site["root_disposition"] != "excluded":
        raise AnalysisError("site_invalid", "Non-creating sites must be excluded")


def _validate_site_index(value):
    _unique_sorted(value["sites"], lambda item: item["id"], "Thread-entry sites must be unique and sorted")
    _dependencies(value["dependencies"])
    for site in value["sites"]:
        _validate_site(site)


def _validate_overlay(value):
    for field in ("roots", "contexts", "demands"):
        _unique_sorted(value[field], lambda item: item["id"], f"Overlay {field} must be unique and sorted")
    declared = _dependencies(value["dependencies"])
    for field in ("site_index", "base_execution_roots", "base_plan"):
        ref = value[field]
        if ref is not None and (ref["kind"], ref["id"]) not in declared:
            raise AnalysisError("invalid_reference", f"Overlay {field} is missing from dependencies")
    for root in value["roots"]:
        if not root.get("entry") or not root.get("creation_site_id") or not root.get("context_id"):
            raise AnalysisError("root_invalid", "Overlay roots require entry, creation site, and context")


def _validate_report(value):
    expected = 1 if value["status"] == "failed" else 2 if value["status"] == "partial" else 0
    if value["exit_code"] != expected:
        raise AnalysisError("report_status", "Thread-entry report exit code does not match completeness")
    if value["safety"] != "not_evaluated" or value["findings"] is not None:
        raise AnalysisError("safety_claim", "Thread-entry discovery cannot publish findings or safety conclusions")
    declared = _dependencies(value["dependencies"])
    for field in ("site_index", "root_overlay"):
        ref = value[field]
        if ref is not None and (ref["kind"], ref["id"]) not in declared:
            raise AnalysisError("invalid_reference", f"Report {field} is missing from dependencies")


def validate_thread_entry_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown thread-entry contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    schema = _load(SCHEMA, "thread_entry_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "ThreadEntryDiscoveryRequest":
        _validate_request(value)
    elif kind == "ThreadEntryLocalFacts":
        _validate_local_facts(value)
    elif kind == "ThreadEntrySiteIndex":
        _validate_site_index(value)
    elif kind == "ThreadEntryRootOverlay":
        _validate_overlay(value)
    else:
        _validate_report(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def thread_entry_document(kind, **fields):
    protocol = expected_thread_entry_protocol()
    result = {"schema_version": 1, "kind": kind,
              "analysis_version": protocol["analysis_version"],
              "policy_id": protocol["policy_id"], **fields}
    if result.get("semantic_digest") is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_thread_entry_document(result, kind)


def read_thread_entry_document(path, kind):
    return validate_thread_entry_document(_load(path, "input_invalid"), kind)
