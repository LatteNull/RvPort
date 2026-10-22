"""Versioned JSON contracts and content identities."""

import hashlib
import json
from pathlib import Path

import jsonschema

SCHEMA_VERSION = 1
KIND_VERSIONS = {"ModuleFacts": 2, "RunReport": 2}
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "contracts.json"


class AnalysisError(Exception):
    """A classified, reportable failure, not a safety finding."""

    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def as_dict(self):
        return {"code": self.code, "detail": self.detail}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def identity(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def document(kind, **fields):
    result = {"schema_version": KIND_VERSIONS.get(kind, SCHEMA_VERSION), "kind": kind, **fields}
    validate(result, kind)
    return result


def validate(value, kind):
    expected_version = KIND_VERSIONS.get(kind, SCHEMA_VERSION)
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != expected_version:
        raise AnalysisError("schema_version", f"{kind} requires schema_version={expected_version}; re-extract facts or regenerate reports, do not convert historical JSON")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if kind not in schema["$defs"]:
        raise AnalysisError("schema_invalid", f"Unknown contract: {kind}")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "ModuleFacts":
        from .semantic import validate_graph
        validate_graph(value)
    return value


def read_document(path, kind):
    try:
        return validate(json.loads(Path(path).read_text(encoding="utf-8")), kind)
    except (OSError, ValueError) as exc:
        raise AnalysisError("input_invalid", str(exc)) from exc


def validate_references(references, available):
    missing = sorted(set(references) - set(available))
    if missing:
        raise AnalysisError("invalid_reference", f"Missing references: {missing}")
