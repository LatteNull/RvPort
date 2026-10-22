"""Deterministic cache isolated to the thread-entry-discovery v1 namespace."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .thread_entry_contracts import validate_thread_entry_document


def cache_key(layer, payload, dependencies=()):
    return identity({
        "namespace": "thread-entry-discovery-v1", "layer": f"{layer}-v1",
        "policy": "thread-entry-discovery-v1", "payload": payload,
        "dependencies": sorted(dependencies),
    })


class ThreadEntryCache:
    def __init__(self, root):
        self.root = Path(root).resolve() / "thread-entry-discovery-v1"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("thread_entry_cache_invalid", "Thread-entry cache path escapes its namespace")
        return path

    def load(self, layer, key, kind):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_thread_entry_document(value, kind)
        except AnalysisError as exc:
            raise AnalysisError("thread_entry_cache_invalid", f"Invalid thread-entry cache entry: {path}") from exc
        except (OSError, ValueError) as exc:
            raise AnalysisError("thread_entry_cache_invalid", f"Invalid thread-entry cache entry: {path}") from exc
        if value.get("status") != "complete":
            return None
        return value

    def publish(self, layer, key, value, *, stability="deterministic"):
        if stability != "deterministic" or value.get("status") != "complete":
            raise AnalysisError("thread_entry_cache_transient", "Only deterministic complete thread-entry results are cacheable")
        validate_thread_entry_document(value, value.get("kind"))
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("thread_entry_cache_collision", f"Conflicting thread-entry cache entry: {path}")
            return path
        descriptor, name = tempfile.mkstemp(prefix=f".{key}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_text(encoding="utf-8") != content:
                    raise AnalysisError("thread_entry_cache_collision", f"Conflicting thread-entry cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
