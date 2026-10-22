from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def stable_id(kind: str, *identity_parts: Any) -> str:
    if not kind or not kind.strip():
        raise ValueError("kind must not be empty")
    payload = {
        "version": 1,
        "kind": kind.strip(),
        "parts": [_canonicalize(item) for item in identity_parts],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonicalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if isinstance(value, Path):
        if value.is_absolute():
            raise ValueError("absolute paths must be normalized before stable ID construction")
        return str(value).replace("\\", "/")
    if is_dataclass(value):
        return {field.name: _canonicalize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("stable ID mapping keys must be strings")
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonicalize(item) for item in value]
    raise TypeError(f"unsupported stable ID material: {type(value).__name__}")
