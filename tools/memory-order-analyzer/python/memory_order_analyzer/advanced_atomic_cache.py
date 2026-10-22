"""Content-addressed cache for complete A6 sidecars."""

import json
import os
from pathlib import Path
import tempfile

from .advanced_atomic_contracts import validate_advanced_atomic_document
from .contracts import AnalysisError, canonical, identity


def analysis_key(request):
    return identity({"layer": "fence-rmw-publication-v1", "request": request,
                     "policy": "fence-rmw-publication-v1", "analysis": "0.1.0"})


class AdvancedAtomicCache:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("advanced_atomic_cache_invalid", "A6 cache path escapes root")
        return path

    def load(self, layer, key, kind):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_advanced_atomic_document(value, kind)
        except (OSError, ValueError, AnalysisError) as exc:
            raise AnalysisError("advanced_atomic_cache_invalid", f"Invalid A6 cache entry: {path}") from exc
        if value.get("status") != "complete":
            raise AnalysisError("advanced_atomic_cache_invalid", "A6 cache cannot contain partial/failed semantics")
        return value

    def publish(self, layer, key, value):
        validate_advanced_atomic_document(value, value.get("kind") if isinstance(value, dict) else None)
        if value.get("status") != "complete":
            raise AnalysisError("advanced_atomic_cache_incomplete", "Only complete A6 semantics may be cached")
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("advanced_atomic_cache_collision", f"Conflicting A6 cache entry: {path}")
            return path
        descriptor, name = tempfile.mkstemp(prefix=f".{key}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_text(encoding="utf-8") != content:
                    raise AnalysisError("advanced_atomic_cache_collision", f"Conflicting A6 cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
