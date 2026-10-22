from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

from ..core import stable_id


_WHITESPACE = re.compile(r"\s+")


def canonicalize_fact_value(fact_kind: str, value: str) -> str:
    if not fact_kind or not isinstance(value, str):
        raise ValueError("fact kind and value must be strings")
    normalized = value.strip()
    if fact_kind == "headers":
        normalized = normalized.strip('<>"').replace("\\", "/")
    elif fact_kind in {"compilerFlags", "inline_asm", "comment", "declaration_attribute", "vectorWidthMarkers"}:
        normalized = _WHITESPACE.sub(" ", normalized)
    elif fact_kind in {"assemblyInstructions", "registerNames", "targetFeatures", "architectureAliases"}:
        normalized = _WHITESPACE.sub(" ", normalized).lower()
    if not normalized:
        raise ValueError("canonical fact value must not be empty")
    return normalized


def logical_path(value: str) -> str:
    normalized = str(value).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("logical path must be relative")
    return path.as_posix()


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def knowledge_source_id(source_id: str, path: str, sha256: str) -> str:
    return stable_id("knowledge_source", 1, source_id, logical_path(path), sha256)


def knowledge_entry_id(fact_kind: str, architecture_family: str, canonical_value: str) -> str:
    return stable_id("knowledge_entry", 1, fact_kind, architecture_family, canonical_value)


def knowledge_reference_id(official_url: str, revision: str, logical_location: str, sha256: str) -> str:
    return stable_id("knowledge_reference", 1, official_url, revision, logical_location, sha256)


def curated_entry_id(fact_kind: str, architecture_family: str, canonical_value: str) -> str:
    canonical = canonicalize_fact_value(fact_kind, canonical_value)
    return knowledge_entry_id(fact_kind, architecture_family, canonical)


def candidate_id(category: str, canonical_value: str) -> str:
    return stable_id("knowledge_candidate", 1, category, canonical_value.strip())


def knowledge_snapshot_id(
    catalog_id: str,
    version: str,
    source_ids: tuple[str, ...],
    entry_ids: tuple[str, ...],
) -> str:
    return stable_id("knowledge_snapshot", 1, catalog_id, version, tuple(sorted(source_ids)), tuple(sorted(entry_ids)))
