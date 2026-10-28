"""Strict, self-contained v2/v3 projection contracts for memory-order findings."""

from copy import deepcopy
import json
from pathlib import Path, PurePosixPath

import jsonschema

from .contracts import AnalysisError, identity


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/memory_order_finding.json"
PRODUCER_PREFIX = "org.rvport.memory-order-analyzer."


def _schema():
    try:
        return json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError("finding_schema", f"Invalid finding schema: {SCHEMA}") from exc


def finding_digest(value):
    payload = deepcopy(value)
    payload.pop("semanticDigest", None)
    return identity(payload)


def provenance(kind, identifier, producer, schema_version, digest):
    return {"kind": str(kind), "id": str(identifier), "producer": str(producer),
            "schemaVersion": int(schema_version), "digest": str(digest)}


def _unique_sorted(items, key, detail):
    values = [key(item) for item in items]
    if values != sorted(values) or len(values) != len(set(values)):
        raise AnalysisError("invalid_reference", detail)
    return set(values)


def _validate_source(source):
    if source is None:
        return
    path = source["file"]
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in path or ":" in pure.parts[0]:
        raise AnalysisError("path_unsafe", "Finding source paths must be project-relative POSIX paths")
    span = source["span"]
    start = (span["start"]["line"], span["start"]["column"])
    end = (span["end"]["line"], span["end"]["column"])
    if end <= start:
        raise AnalysisError("span_invalid", "Source spans are one-based and end-exclusive")
    context = source["context"]
    lines = context["lines"]
    if [item["line"] for item in lines] != sorted({item["line"] for item in lines}):
        raise AnalysisError("context_invalid", "Context lines must be unique and sorted")
    if sum(len(item["text"].encode("utf-8")) for item in lines) > context["budget"]["maxCharacters"]:
        raise AnalysisError("context_budget", "Context characters exceed the declared budget")
    line_numbers = {item["line"] for item in lines}
    for highlight in context["highlights"]:
        if highlight["line"] not in line_numbers or highlight["endColumn"] <= highlight["startColumn"]:
            raise AnalysisError("context_invalid", "Highlights must reference context lines and be end-exclusive")
    if context["status"] == "complete" and (context["reasonCodes"] or context["budget"]["truncated"]):
        raise AnalysisError("context_invalid", "Complete source context cannot have reasons or truncation")
    if context["status"] != "complete" and not context["reasonCodes"]:
        raise AnalysisError("context_invalid", "Partial or unavailable context requires a reason code")
    if context["status"] == "unavailable" and (lines or context["highlights"]):
        raise AnalysisError("context_invalid", "Unavailable context cannot contain source lines")


def _validate_provenance(items):
    _unique_sorted(items, lambda item: (item["kind"], item["id"], item["producer"]),
                   "Provenance entries must be unique and sorted")
    if any(not item["producer"].startswith(PRODUCER_PREFIX) for item in items):
        raise AnalysisError("provenance_invalid", "Finding provenance must use the memory-order namespace")


def validate_finding(value):
    try:
        jsonschema.Draft202012Validator(
            {"$ref": "#/$defs/MemoryOrderFindingProjection", "$defs": _schema()["$defs"]}
        ).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if value.get("semanticDigest") != finding_digest(value):
        raise AnalysisError("semantic_digest", "Finding semantic digest does not match content")
    conclusion = value["conclusion"]
    if value["fact"]["kind"] == "source-candidate" and conclusion["verdict"] != "source-candidate":
        raise AnalysisError("safety_claim", "AST-only facts cannot become formal risk or discharge conclusions")
    if value["schemaVersion"] == "2.0":
        if conclusion["confidence"] is None or "evidenceLevel" in conclusion:
            raise AnalysisError("schema_invalid", "Version 2 requires numeric confidence and no evidenceLevel")
    else:
        expected = {"source-candidate": "source-only", "inconclusive": "incomplete",
                    "risk": "bounded-model", "discharged-within-bounded-model": "bounded-model"}
        if conclusion.get("evidenceLevel") != expected[conclusion["verdict"]]:
            raise AnalysisError("schema_invalid", "Evidence level disagrees with verdict")
        if conclusion["verdict"] in {"source-candidate", "inconclusive"} and (
                conclusion["severity"] != "info" or conclusion["blocking"] or
                conclusion["confidence"] is not None or conclusion["status"] not in {"unknown", "partial"}):
            raise AnalysisError("safety_claim", "Unproven candidates cannot have a risk grade or probability")
    occurrences = _unique_sorted(value["occurrences"], lambda item: item["id"],
                                 "Occurrences must be unique and sorted")
    if value["primaryOccurrenceId"] not in occurrences:
        raise AnalysisError("invalid_reference", "Primary occurrence is not declared")
    steps = _unique_sorted(value["evidenceChain"]["steps"], lambda item: item["id"],
                           "Evidence steps must be unique and sorted")
    edges = _unique_sorted(value["evidenceChain"]["edges"], lambda item: item["id"],
                           "Evidence edges must be unique and sorted")
    del edges
    chain = value["evidenceChain"]
    if chain["rootStepId"] not in steps or set(chain["primaryPath"]) - steps or set(chain["impactStepIds"]) - steps:
        raise AnalysisError("invalid_reference", "Evidence chain references an undeclared step")
    adjacency = {(edge["fromStepId"], edge["toStepId"]) for edge in chain["edges"]}
    if any(edge["fromStepId"] not in steps or edge["toStepId"] not in steps for edge in chain["edges"]):
        raise AnalysisError("invalid_reference", "Evidence edge references an undeclared step")
    if any((left, right) not in adjacency for left, right in zip(chain["primaryPath"], chain["primaryPath"][1:])):
        raise AnalysisError("invalid_reference", "Primary path must be connected by declared edges")
    for item in chain["breaks"]:
        if item["fromStepId"] is not None and item["fromStepId"] not in steps:
            raise AnalysisError("invalid_reference", "Evidence break references an undeclared source step")
        if set(item["candidateStepIds"]) - steps:
            raise AnalysisError("invalid_reference", "Evidence break references an undeclared candidate step")
    if chain["status"] == "complete" and (chain["breaks"] or chain["reasonCodes"] or chain["budget"]["truncated"]):
        raise AnalysisError("finding_status", "Complete evidence chains cannot contain known breaks")
    if chain["status"] != "complete" and (not chain["breaks"] or not chain["reasonCodes"]):
        raise AnalysisError("finding_status", "Incomplete evidence chains require reasons and breaks")
    if chain["budget"]["visited"] > chain["budget"]["maxVisited"] or chain["budget"]["paths"] > chain["budget"]["maxPaths"]:
        raise AnalysisError("finding_budget", "Evidence usage exceeds its declared budget")
    if value["conclusion"]["status"] != chain["status"]:
        raise AnalysisError("finding_status", "Conclusion and evidence-chain status must agree")
    if value["conclusion"]["verdict"] == "source-candidate" and chain["status"] == "complete":
        raise AnalysisError("safety_claim", "Source-only candidates cannot be complete")
    if value["fact"]["kind"] == "source-candidate" and value["conclusion"]["verdict"] != "source-candidate":
        raise AnalysisError("safety_claim", "AST-only facts cannot become formal risk or discharge conclusions")
    all_provenance = [value["fact"]["provenance"]]
    all_provenance += [item["provenance"] for item in value["occurrences"]]
    all_provenance += [item["provenance"] for item in chain["steps"]]
    all_provenance += [item["provenance"] for item in chain["edges"]]
    for items in all_provenance:
        _validate_provenance(items)
    _validate_source(value["fact"]["primaryLocation"])
    for item in value["occurrences"]:
        if item["scopeId"] != value["scopeId"]:
            raise AnalysisError("profile_conflict", "Occurrence belongs to another scope")
        _validate_source(item["location"])
    for item in chain["steps"]:
        _validate_source(item["source"])
    return value


def finding_document(**fields):
    result = {"schemaVersion": "3.0", "kind": "MemoryOrderFindingProjection", **deepcopy(fields)}
    result["semanticDigest"] = finding_digest(result)
    return validate_finding(result)


def read_finding(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError("input_invalid", f"Invalid or missing finding JSON: {path}") from exc
    return validate_finding(value)
