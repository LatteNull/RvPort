"""Content-addressed cache isolated from P1-P4 and A1 cache namespaces."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .degraded_contracts import validate_degraded_document


def cache_key(layer, payload, dependencies=()):
    return identity({"layer": f"{layer}-v1", "policy": "degraded-source-analysis-v1",
                     "payload": payload, "dependencies": sorted(dependencies)})


class DegradedAnalysisCache:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("degraded_cache_invalid", "Degraded cache path escapes its root")
        return path

    def load(self, layer, key, kind, *, dependencies=None):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_degraded_document(value, kind)
            if dependencies is not None and value.get("dependencies") != dependencies:
                raise AnalysisError("degraded_cache_invalid", "Cached degraded dependencies are stale")
        except AnalysisError as exc:
            if exc.code == "degraded_cache_invalid":
                raise
            raise AnalysisError("degraded_cache_invalid", f"Invalid degraded cache entry: {path}") from exc
        except (OSError, ValueError) as exc:
            raise AnalysisError("degraded_cache_invalid", f"Invalid degraded cache entry: {path}") from exc
        return value

    def publish(self, layer, key, value):
        validate_degraded_document(value, value.get("kind") if isinstance(value, dict) else None)
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("degraded_cache_collision", f"Conflicting degraded cache entry: {path}")
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
                    raise AnalysisError("degraded_cache_collision", f"Conflicting degraded cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
