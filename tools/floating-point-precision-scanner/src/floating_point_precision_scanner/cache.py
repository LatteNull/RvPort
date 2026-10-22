"""Canonical source/IR/evidence 的内容寻址缓存。"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import canonical_json, semantic_digest

CACHE_SCHEMA_VERSION = "1.0"
CACHE_KINDS = frozenset({"source-facts", "ir-facts", "evidence"})
CACHE_MODES = frozenset({"off", "read-only", "write-only", "read-write"})


@dataclass(frozen=True, slots=True)
class CacheConfig:
    mode: str = "off"
    root: Path | None = None
    max_entry_bytes: int = 67_108_864

    @property
    def readable(self) -> bool:
        return self.mode in {"read-only", "read-write"}

    @property
    def writable(self) -> bool:
        return self.mode in {"write-only", "read-write"}


@dataclass(slots=True)
class CacheStats:
    hit: int = 0
    miss: int = 0
    corrupt: int = 0
    write: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "hit": self.hit,
            "miss": self.miss,
            "corrupt": self.corrupt,
            "write": self.write,
        }


def cache_key(kind: str, inputs: Mapping[str, Any]) -> str:
    if kind not in CACHE_KINDS:
        raise ValueError("unsupported_cache_kind")
    return semantic_digest(
        {
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "kind": kind,
            "inputs": inputs,
        }
    )


class AnalysisCache:
    def __init__(
        self,
        config: CacheConfig,
        *,
        replace: Callable[[str, str], None] = os.replace,
        sync: Callable[[int], None] = os.fsync,
    ) -> None:
        if config.mode not in CACHE_MODES:
            raise ValueError("invalid_cache_mode")
        if config.mode != "off" and config.root is None:
            raise ValueError("cache_root_required")
        self.config = config
        self.stats = CacheStats()
        self._replace = replace
        self._sync = sync
        self.root = config.root.resolve() if config.root is not None else None

    def path_for(self, kind: str, key: str) -> Path:
        if self.root is None or kind not in CACHE_KINDS or len(key) != 64:
            raise ValueError("invalid_cache_path")
        candidate = self.root / kind / key[:2] / f"{key}.json"
        resolved_parent = candidate.parent.resolve()
        try:
            resolved_parent.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("cache_path_outside_root") from exc
        return candidate

    def read(self, kind: str, key: str) -> Mapping[str, Any] | None:
        if not self.config.readable:
            return None
        path = self.path_for(kind, key)
        try:
            if path.is_symlink() or not path.is_file():
                self.stats.miss += 1
                return None
            if path.stat().st_size > self.config.max_entry_bytes:
                raise ValueError("cache_entry_too_large")
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(envelope, Mapping):
                raise ValueError("invalid_cache_envelope")
            required = {
                "kind": "FloatingPointAnalysisCacheEntry",
                "schema_version": CACHE_SCHEMA_VERSION,
                "cache_kind": kind,
                "cache_key": key,
            }
            if any(envelope.get(name) != value for name, value in required.items()):
                raise ValueError("cache_identity_mismatch")
            payload = envelope.get("payload")
            if not isinstance(payload, Mapping):
                raise ValueError("invalid_cache_payload")
            payload_text = canonical_json(payload).encode("utf-8")
            if len(payload_text) != envelope.get("payload_bytes"):
                raise ValueError("cache_size_mismatch")
            if semantic_digest(payload) != envelope.get("payload_sha256"):
                raise ValueError("cache_digest_mismatch")
            self.stats.hit += 1
            return dict(payload)
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            self.stats.corrupt += 1
            return None

    def write(
        self,
        kind: str,
        key: str,
        payload: Mapping[str, Any],
        *,
        dependencies: Mapping[str, str],
    ) -> bool:
        if not self.config.writable:
            return False
        path = self.path_for(kind, key)
        payload_bytes = canonical_json(payload).encode("utf-8")
        envelope = {
            "kind": "FloatingPointAnalysisCacheEntry",
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_kind": kind,
            "cache_key": key,
            "payload_sha256": semantic_digest(payload),
            "payload_bytes": len(payload_bytes),
            "dependencies": dict(sorted(dependencies.items())),
            "payload": payload,
        }
        encoded = (
            json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        if len(encoded) > self.config.max_entry_bytes:
            raise ValueError("cache_entry_too_large")
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                self._sync(stream.fileno())
            if path.exists():
                existing = self.read(kind, key)
                if existing is not None and semantic_digest(existing) != semantic_digest(payload):
                    raise ValueError("cache_publish_conflict")
            self._replace(temporary, str(path))
            temporary = ""
            self.stats.write += 1
            return True
        finally:
            if temporary:
                with suppress(FileNotFoundError):
                    os.unlink(temporary)
