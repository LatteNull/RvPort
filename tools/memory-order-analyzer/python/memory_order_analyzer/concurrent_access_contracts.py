"""Versioned contracts for the R2 concurrent-access candidate sidecar."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/concurrent_access_candidate.json"
PROTOCOL = ROOT / "protocols/concurrent-access-candidate-protocol.json"
KINDS = (
    "ConcurrentAccessCandidateRequest", "ConcurrentAccessProjectionFacts",
    "ExecutionInstanceBindingOverlay", "AccessProtectionOverlay",
    "ConcurrentAccessCandidateGraph", "ConcurrentAccessCandidateReport",
)
REQUIRED_INPUTS = {"RootDrivenAnalysisPlan", "ThreadEntryRootOverlay", "EffectSummary"}
SORTED_OUTPUT_FIELDS = {
    "ConcurrentAccessProjectionFacts": ("accesses", "observed_not_demanded"),
    "ExecutionInstanceBindingOverlay": ("roots", "contexts", "instances", "invocations", "mhp", "exclusions"),
    "AccessProtectionOverlay": ("protections",),
    "ConcurrentAccessCandidateGraph": ("accesses", "candidates", "exclusions", "atomic_handoff"),
}


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_concurrent_access_protocol(path=PROTOCOL):
    value = _load(path, "concurrent_access_protocol")
    schema = _load(SCHEMA, "concurrent_access_schema")
    maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
    expected = {
        "protocol_version": 1, "analysis_version": "0.1.0", "llvm_version": "21.1.8",
        "policy_id": "concurrent-access-candidate-graph-v1",
        "cache_namespace": "concurrent-access-candidate-graph-v1",
        "kinds": dict.fromkeys(KINDS, 1), "budgets": maxima,
    }
    if value != expected:
        raise AnalysisError("concurrent_access_protocol", "R2 protocol and schema maxima disagree")
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
                              "R2 只生成受限并发访问候选，不证明 data race、happens-before 或程序安全"),
        "limitation_en": bounded(limitation_en or
                                 "R2 only generates bounded concurrent-access candidates; it does not prove data races, happens-before, or program safety"),
        "suggestion": bounded(suggestion) if suggestion is not None else None,
        "suggestion_en": bounded(suggestion_en) if suggestion_en is not None else None,
        "source": deepcopy(source),
    }


def semantic_digest(value):
    copy = deepcopy(value)
    copy.pop("semantic_digest", None)
    if copy.get("kind") == "ConcurrentAccessCandidateReport":
        copy.pop("cache", None)
    return identity(copy)


def _unique_sorted(items, key, detail):
    values = [key(item) for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _dependencies(items):
    return _unique_sorted(items, lambda item: (item["kind"], item["id"]),
                          "Dependencies must be unique and sorted")


def _validate_request(value):
    _unique_sorted(value["members"], lambda item: item["physical_tu_id"],
                   "Request members must be unique and sorted")
    keys = _unique_sorted(value["evidence"], lambda item: (item["kind"], item["id"]),
                          "Request evidence must be unique and sorted")
    kinds = {kind for kind, _ in keys}
    missing = REQUIRED_INPUTS - kinds
    if missing:
        raise AnalysisError("invalid_reference", f"R2 request is missing required evidence: {sorted(missing)}")
    if len(value["members"]) > value["budgets"]["translation_units"]:
        raise AnalysisError("translation-unit-budget", "R2 request exceeds translation unit budget")
    for member in value["members"]:
        allowed = {"compiler-default", "c89", "c99", "c11", "c17", "c23"} if member["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}
        if member["standard"] not in allowed:
            raise AnalysisError("profile_conflict", "Member language and standard disagree")
        if member["source_digest"] is None and member["bc_digest"] is None:
            raise AnalysisError("lineage_conflict", "A request member requires source or BC lineage")
        if (member["source_digest"] is None or member["bc_digest"] is None) and \
                member["source_ir_binding_digest"] is not None:
            raise AnalysisError("lineage_conflict", "A source/IR binding requires both source and BC lineage")
    for item in value["evidence"]:
        path = Path(item["path"])
        if path.is_absolute() or ".." in path.parts:
            raise AnalysisError("invalid_reference", "Evidence paths must remain relative to the artifact store")


def _validate_sorted_outputs(value):
    for field in SORTED_OUTPUT_FIELDS.get(value["kind"], ()):
        _unique_sorted(value[field], lambda item: item["id"], f"{field} must be unique and sorted")
    _dependencies(value.get("dependencies", []))
    if value.get("status") == "complete" and value.get("frontier"):
        raise AnalysisError("completeness_invalid", "Complete R2 artifacts cannot retain a frontier")


def _validate_graph(value):
    _validate_sorted_outputs(value)
    declared = _dependencies(value["dependencies"])
    for field in ("projection", "execution_instances", "protection"):
        ref = value[field]
        if (ref["kind"], ref["id"]) not in declared:
            raise AnalysisError("invalid_reference", f"Graph {field} is missing from dependencies")
    access_ids = {item["id"] for item in value["accesses"]}
    for pair in [*value["candidates"], *value["exclusions"]]:
        if pair.get("left") not in access_ids or pair.get("right") not in access_ids:
            raise AnalysisError("invalid_reference", "Candidate/exclusion refers to an unknown access")


def _validate_report(value):
    expected = 1 if value["status"] == "failed" else 2 if value["status"] == "partial" else 0
    if value["exit_code"] != expected:
        raise AnalysisError("report_status", "R2 report exit code does not match completeness")
    if value["safety"] != "not_evaluated" or value["findings"] is not None:
        raise AnalysisError("safety_claim", "R2 cannot publish findings or safety conclusions")
    declared = _dependencies(value["dependencies"])
    if value["graph"] is not None and (value["graph"]["kind"], value["graph"]["id"]) not in declared:
        raise AnalysisError("invalid_reference", "Report graph is missing from dependencies")


def validate_concurrent_access_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown R2 contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    # Preserve the R2-specific diagnostic even though the strict JSON Schema also
    # constrains these fields.  This is a semantic boundary, not merely a shape error.
    if kind == "ConcurrentAccessCandidateReport" and {
            "status", "exit_code", "safety", "findings", "dependencies", "graph"
    } <= value.keys():
        _validate_report(value)
    schema = _load(SCHEMA, "concurrent_access_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "ConcurrentAccessCandidateRequest":
        _validate_request(value)
    elif kind == "ConcurrentAccessCandidateGraph":
        _validate_graph(value)
    elif kind == "ConcurrentAccessCandidateReport":
        pass
    else:
        _validate_sorted_outputs(value)
    if value.get("semantic_digest") != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def concurrent_access_document(kind, **fields):
    protocol = expected_concurrent_access_protocol()
    result = {"schema_version": 1, "kind": kind,
              "analysis_version": protocol["analysis_version"],
              "policy_id": protocol["policy_id"], **fields}
    if result.get("semantic_digest") is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_concurrent_access_document(result, kind)


def read_concurrent_access_document(path, kind):
    return validate_concurrent_access_document(_load(path, "input_invalid"), kind)


def validate_reference_closure(root_key, documents):
    """Validate a resolved document graph and reject stale references or cycles."""
    visiting, complete = set(), set()
    def visit(key):
        if key in visiting:
            raise AnalysisError("dependency_cycle", f"R2 dependency cycle includes {key[0]}:{key[1]}")
        if key in complete:
            return
        if key not in documents:
            raise AnalysisError("invalid_reference", f"R2 dependency is missing: {key[0]}:{key[1]}")
        visiting.add(key)
        value = documents[key]
        for ref in value.get("dependencies", []):
            child = (ref["kind"], ref["id"])
            if child not in documents:
                continue
            if ref["digest"] != identity(documents[child]):
                raise AnalysisError("invalid_reference", f"R2 dependency digest changed: {child[0]}:{child[1]}")
            visit(child)
        visiting.remove(key); complete.add(key)
    visit(root_key)
    return True


def validate_compatibility(request, artifacts):
    """Reject opposed scope/build identities; absent optional fields stay explicit unknowns."""
    expected = {"scope_id": request["scope_id"], "target": request["target"],
                "data_layout": request["data_layout"], "abi": request["abi"]}
    requested_members = {item["physical_tu_id"]: item for item in request["members"]}
    for artifact in artifacts:
        for field, wanted in expected.items():
            observed = artifact.get(field)
            if observed is not None and observed != wanted:
                raise AnalysisError("dependency_mismatch",
                                    f"R2 dependency {artifact.get('kind')} has incompatible {field}")
        artifact_members = artifact.get("members", [])
        if artifact.get("physical_tu_id"):
            artifact_members = [artifact]
        for observed_member in artifact_members:
            physical_tu_id = observed_member.get("physical_tu_id")
            if physical_tu_id is None:
                continue
            wanted_member = requested_members.get(str(physical_tu_id))
            if wanted_member is None:
                raise AnalysisError(
                    "dependency_mismatch",
                    f"R2 dependency {artifact.get('kind')} references an unrequested physical TU")
            aliases = {
                "profile_id": ("profile_id",),
                "source_digest": ("source_digest", "source_hash"),
                "bc_digest": ("bc_digest", "artifact_key", "module_hash"),
                "source_ir_binding_digest": ("source_ir_binding_digest", "binding_digest"),
            }
            for field, names in aliases.items():
                observed = next((observed_member.get(name) for name in names
                                 if observed_member.get(name) is not None), None)
                if observed is not None and observed != wanted_member[field]:
                    raise AnalysisError(
                        "dependency_mismatch",
                        f"R2 dependency {artifact.get('kind')} has incompatible {field} for {physical_tu_id}")
    return True
