"""Atomic content-addressed caches for AST-assisted evidence layers."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .source_contracts import validate_source_document


def cache_key(layer, payload, dependencies=()):
    return identity({"layer": f"{layer}-v1", "policy": "ast-cross-tu-evidence-v1",
                     "payload": payload, "dependencies": sorted(dependencies)})


class SourceEvidenceCache:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("source_cache_invalid", "Source evidence cache path escapes root")
        return path

    def load(self, layer, key, kind, *, dependencies=None):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_source_document(value, kind)
            if dependencies is not None and value.get("dependencies") != dependencies:
                raise AnalysisError("source_cache_invalid", "Cached dependency identities are stale")
        except (OSError, ValueError, AnalysisError) as exc:
            raise AnalysisError("source_cache_invalid", f"Invalid source evidence cache entry: {path}") from exc
        return value

    def publish(self, layer, key, value):
        validate_source_document(value, value.get("kind") if isinstance(value, dict) else None)
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("source_cache_collision", f"Conflicting source evidence cache entry: {path}")
            return path
        descriptor, name = tempfile.mkstemp(prefix=f".{key}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush(); os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_text(encoding="utf-8") != content:
                    raise AnalysisError("source_cache_collision", f"Conflicting source evidence cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
