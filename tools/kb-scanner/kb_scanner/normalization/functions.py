"""Validate source ownership before normalized function metadata is consumed."""
from collections.abc import Mapping


def _interval(value, width=2):
    return (isinstance(value, tuple) and len(value) == width
            and all(type(part) is int and part >= 0 for part in value)
            and (value[0] <= value[1] if width == 2 else value[:2] <= value[2:]))


def valid_function(item):
    record = item.metadata.get("function")
    if not isinstance(record, Mapping) or item.location is None:
        return False
    declaration = record.get("declarationBytes")
    name = record.get("nameBytes")
    if not _interval(declaration) or not _interval(name):
        return False
    body = record.get("bodyBytes")
    attrs, nested = record.get("attributes"), record.get("nestedBytes")
    if not isinstance(attrs, tuple) or not isinstance(nested, tuple):
        return False
    intervals = (name, *attrs, *((body,) if body is not None else ()))
    if any(not _interval(value) or value[0] < declaration[0] or value[1] > declaration[1] for value in intervals):
        return False
    if any(not _interval(value) or body is None or value[0] < body[0] or value[1] > body[1] for value in nested):
        return False
    if not _interval(record.get("declarationSpan"), 4):
        return False
    return body is None or _interval(record.get("bodySpan"), 4)


def valid_owner(item, functions):
    owner_id = item.metadata.get("functionOwnerEvidenceId")
    if owner_id is None:
        return "functionOwnerEvidenceId" not in item.metadata
    if not isinstance(owner_id, str) or owner_id not in functions:
        return False
    owner = functions[owner_id]
    if (item.kind != "declaration_attribute" or item.subject_id != owner.subject_id
            or item.location is None or owner.location is None
            or item.location.start.path != owner.location.start.path
            or item.metadata.get("compilationContextId") != owner.metadata.get("compilationContextId")):
        return False
    # Attribute identity is checked against its exact source range, not line proximity.
    location = item.location
    span = (location.start.line, location.start.column, location.end.line, location.end.column)
    return span in owner.metadata.get("function", {}).get("attributeSpans", ())


def merge_metadata(items, metadata):
    """Keep producer conflicts explicit rather than picking the first producer."""
    result = dict(metadata)
    owners = tuple(sorted({item.metadata["functionOwnerEvidenceId"] for item in items
                           if isinstance(item.metadata.get("functionOwnerEvidenceId"), str)}))
    if owners:
        result["functionOwnerEvidenceIds"] = owners
    records = [item.metadata["function"] for item in items if "function" in item.metadata]
    conflict = bool(records) and any(record != records[0] for record in records[1:])
    if conflict:
        result["function"] = {**records[0], "bindingStatus": "unknown", "producerConflict": True}
        result["functionProvenance"] = tuple({"evidenceId": item.id, "producer": item.producer,
            "record": item.metadata["function"]} for item in items if "function" in item.metadata)
    return result, conflict
