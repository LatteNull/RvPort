"""Strict AST-assisted contracts, identities, and semantic validation."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, canonical, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/source_evidence.json"
PROTOCOL = ROOT / "protocols/source-evidence-protocol.json"
KINDS = (
    "CompilationProfileIdentity", "LLVMSourceBindingRequest", "LLVMSourceBindingFacts",
    "SourceSemanticRequest", "SourceSemanticFacts",
    "ProgramEntityIndexRequest", "ProgramEntityIndex", "SourceIRBindingRequest",
    "SourceIRBinding", "CanonicalObjectOverlay", "AstAssistedAnalysisRequest",
    "AstAssistedAnalysisReport", "AstAssistedCandidateSlices",
    "AstIrValidationSuite", "AstIrValidationTruth", "AstAssistedValidationReport",
)
LATEST_KIND_VERSIONS = dict.fromkeys(KINDS, 1)
LATEST_KIND_VERSIONS.update({"CompilationProfileIdentity": 2, "SourceSemanticRequest": 2})


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_source_protocol(path=PROTOCOL):
    value = _load(path, "source_protocol")
    schema = _load(SCHEMA, "source_schema")
    try:
        maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {
            "protocol_version": 2, "analysis_version": "0.1.0", "llvm_version": "21.1.8",
            "policy_id": "ast-cross-tu-evidence-v1", "kinds": LATEST_KIND_VERSIONS,
            "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("source_schema", "Source evidence budget schema is invalid") from exc
    if canonical(value) != canonical(expected):
        raise AnalysisError("source_protocol", "Source evidence protocol does not match supported schemas")
    return value


def diagnostic(code, detail, detail_en, *, suggestion=None, suggestion_en=None, source=None):
    return {"code": code, "detail": detail, "detail_en": detail_en,
            "suggestion": suggestion, "suggestion_en": suggestion_en,
            "source": deepcopy(source)}


def counts(planned, visited=None, emitted=None, skipped=0, failed=0):
    visited = planned if visited is None else visited
    emitted = visited - skipped - failed if emitted is None else emitted
    values = (planned, visited, emitted, skipped, failed)
    if any(type(item) is not int or item < 0 for item in values):
        raise AnalysisError("counts_invalid", "Counts must be non-negative integers")
    if visited > planned or emitted + skipped + failed > visited:
        raise AnalysisError("counts_invalid", "Counts exceed their planned or visited denominator")
    return {"planned": planned, "visited": visited, "emitted": emitted,
            "skipped": skipped, "failed": failed,
            "ratio": None if planned == 0 else emitted / planned}


def dependency(kind, key, value):
    return {"kind": kind, "id": key, "digest": identity(value)}


def semantic_digest(value):
    copy = deepcopy(value)
    copy.pop("semantic_digest", None)
    if copy.get("kind") == "AstAssistedAnalysisReport":
        copy.pop("cache", None)
    return identity(copy)


def _unique(items, key, detail):
    values = [item[key] for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _unique_dependencies(items, detail):
    values = [(item["kind"], item["id"]) for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _validate_profile(value):
    version = value["schema_version"]
    language_fields = {"dialect", "standard_source", "standard_option"}
    if version == 1:
        if language_fields & value.keys() or value["standard"] not in {"c11", "c17", "c++17", "c++20"}:
            raise AnalysisError("schema_version", "CompilationProfileIdentity v1 only supports the original four standards")
    else:
        if not language_fields <= value.keys():
            raise AnalysisError("schema_invalid", "CompilationProfileIdentity v2 requires the versioned language context")
        from .language_standards import validate_standard_context
        validate_standard_context(value["language"], value["standard"], value["dialect"],
                                  value["standard_source"], value["standard_option"])
    payload = {key: item for key, item in value.items()
               if key not in {"schema_version", "kind", "analysis_version", "policy_id", "profile_id"}}
    if value["profile_id"] != identity(payload):
        raise AnalysisError("profile_digest", "Compilation profile identity does not match its content")
    if value["source"]["path"] != str(Path(value["source"]["path"]).resolve()):
        raise AnalysisError("profile_path", "Compilation profile source path must be absolute and normalized")
    if value["working_directory"] != str(Path(value["working_directory"]).resolve()):
        raise AnalysisError("profile_path", "Compilation profile working directory must be absolute and normalized")
    if value["argv_digest"] != identity(value["argv"]):
        raise AnalysisError("profile_digest", "Compilation argv digest does not match argv")


def _validate_facts(value):
    nodes = _unique(value["nodes"], "id", "Source nodes must be unique and sorted")
    relations = _unique(value["relations"], "id", "Source relations must be unique and sorted")
    del relations
    for node in value["nodes"]:
        if node["canonical_decl"] not in nodes:
            raise AnalysisError("invalid_reference", "Source node has a dangling canonical declaration")
    for relation in value["relations"]:
        if relation["from"] not in nodes or relation["to"] is not None and relation["to"] not in nodes:
            raise AnalysisError("invalid_reference", "Source relation has a dangling endpoint")


def _validate_ir_facts(value):
    _unique(value["symbols"], "id", "LLVM binding symbols must be unique and sorted")


def _validate_index(value):
    _unique_dependencies(value["dependencies"], "Index dependencies must be unique and sorted")
    _unique(value["entities"], "id", "Program entities must be unique and sorted")
    declaration_owners = set()
    for entity in value["entities"]:
        if entity["declarations"] != sorted(set(entity["declarations"])) or entity["definitions"] != sorted(set(entity["definitions"])):
            raise AnalysisError("invalid_reference", "Entity declarations and definitions must be unique and sorted")
        overlap = declaration_owners & set(entity["declarations"])
        if overlap:
            raise AnalysisError("invalid_reference", "A source declaration belongs to multiple program entities")
        declaration_owners.update(entity["declarations"])
        if entity["resolution"] in {"resolved", "exact"} and not entity["definitions"]:
            raise AnalysisError("invalid_reference", "Resolved entity requires a definition")
        if entity["resolution"] in {"ambiguous", "conflict"} and not entity["candidates"]:
            raise AnalysisError("invalid_reference", "Ambiguous entity requires candidates")


def _validate_binding(value):
    _unique_dependencies(value["dependencies"], "Binding dependencies must be unique and sorted")
    ids = _unique(value["entity_bindings"], "id", "Entity bindings must be unique and sorted")
    ids |= _unique(value["expression_bindings"], "id", "Expression bindings must be unique and sorted")
    if len(ids) != len(value["entity_bindings"]) + len(value["expression_bindings"]):
        raise AnalysisError("invalid_reference", "Binding identities overlap across layers")
    for item in [*value["entity_bindings"], *value["expression_bindings"]]:
        target_count = len(item["targets"])
        expected = "zero" if target_count == 0 else "one-to-one" if target_count == 1 else "one-to-many"
        if item["cardinality"] not in {expected, "many-to-one"}:
            raise AnalysisError("invalid_reference", "Binding cardinality does not match targets")
        if item["resolution"] == "exact" and target_count != 1:
            raise AnalysisError("invalid_reference", "Exact binding must have exactly one target")


def _validate_overlay(value):
    _unique_dependencies(value["dependencies"], "Overlay dependencies must be unique and sorted")
    _unique(value["mappings"], "program_object_id", "Overlay mappings must be unique and sorted")
    for item in value["mappings"]:
        if item["artifact_objects"] != sorted(item["artifact_objects"], key=canonical):
            raise AnalysisError("invalid_reference", "Overlay artifact objects must be deterministically sorted")


def _validate_slices(value):
    _unique_dependencies(value["dependencies"], "Candidate-slice dependencies must be unique and sorted")
    _unique(value["slices"], "id", "Candidate slices must be unique and sorted")
    for item in value["slices"]:
        if item["artifacts"] != sorted(set(item["artifacts"])) or item["program_objects"] != sorted(set(item["program_objects"])):
            raise AnalysisError("invalid_reference", "Candidate slice members must be unique and sorted")
        if (item["status"] == "complete") != (not item["missing"]):
            raise AnalysisError("invalid_reference", "Candidate slice status disagrees with missing dependencies")


def _validate_report(value):
    if (value["status"] == "complete") != (value["exit_code"] == 0):
        raise AnalysisError("report_status", "Only complete AST-assisted reports may exit zero")
    if value["status"] in {"partial", "not_run"} and value["exit_code"] != 2:
        raise AnalysisError("report_status", "Partial or not-run AST-assisted reports require exit code 2")
    if value["status"] == "failed" and value["exit_code"] != 1:
        raise AnalysisError("report_status", "Failed AST-assisted reports require exit code 1")


def _validate_validation(value):
    if value["kind"] in {"AstIrValidationSuite", "AstIrValidationTruth"}:
        _unique(value["cases"], "id" if value["kind"] == "AstIrValidationSuite" else "case_id",
                "AST/IR validation cases must be unique and sorted")
    if value["kind"] == "AstAssistedValidationReport":
        required = {"profile_replay", "source_extraction", "entity_resolution", "entity_binding",
                    "expression_binding", "overlay", "candidate_slices"}
        if set(value["layers"]) != required:
            raise AnalysisError("schema_invalid", "AST-assisted validation layers are incomplete")


def validate_source_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown source evidence contract: {kind}")
    latest_version = LATEST_KIND_VERSIONS[kind]
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value.get("schema_version") not in ({1, latest_version} if latest_version > 1 else {1})):
        raise AnalysisError("schema_version", f"{kind} supports schema_version=1..{latest_version}")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    schema = _load(SCHEMA, "source_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "CompilationProfileIdentity":
        _validate_profile(value)
    elif kind == "SourceSemanticRequest":
        if value["profile"]["schema_version"] != value["schema_version"]:
            raise AnalysisError("schema_version", "SourceSemanticRequest and compilation profile versions must match")
    elif kind == "SourceSemanticFacts":
        _validate_facts(value)
    elif kind == "LLVMSourceBindingFacts":
        _validate_ir_facts(value)
    elif kind == "ProgramEntityIndex":
        _validate_index(value)
    elif kind == "SourceIRBinding":
        _validate_binding(value)
    elif kind == "CanonicalObjectOverlay":
        _validate_overlay(value)
    elif kind == "AstAssistedCandidateSlices":
        _validate_slices(value)
    elif kind == "AstAssistedAnalysisReport":
        _validate_report(value)
    elif kind in {"AstIrValidationSuite", "AstIrValidationTruth", "AstAssistedValidationReport"}:
        _validate_validation(value)
    if "semantic_digest" in value and value["semantic_digest"] != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def source_document(kind, *, schema_version=None, **fields):
    protocol = expected_source_protocol()
    version = LATEST_KIND_VERSIONS[kind] if schema_version is None else schema_version
    result = {"schema_version": version, "kind": kind, "analysis_version": protocol["analysis_version"],
              "policy_id": protocol["policy_id"], **fields}
    if "semantic_digest" in result and result["semantic_digest"] is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_source_document(result, kind)


def read_source_document(path, kind):
    return validate_source_document(_load(path, "input_invalid"), kind)
