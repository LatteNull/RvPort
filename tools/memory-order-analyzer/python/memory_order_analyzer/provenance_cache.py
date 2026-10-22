"""Content-addressed cache isolated to the A5 protocol namespace."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .provenance_contracts import validate_provenance_document


def cache_key(layer, payload, dependencies=()):
    return identity({
        "namespace": "bounded-object-provenance-v1", "layer": f"{layer}-v1",
        "policy": "bounded-object-provenance-v1", "payload": payload,
        "dependencies": sorted(dependencies),
    })


class ProvenanceCache:
    def __init__(self, root):
        self.root = Path(root).resolve() / "bounded-object-provenance-v1"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("provenance_cache_invalid", "A5 cache path escapes its namespace")
        return path

    def load(self, layer, key, kind, *, dependencies=None):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_provenance_document(value, kind)
            if dependencies is not None and value.get("dependencies") != dependencies:
                raise AnalysisError("provenance_cache_invalid", "Cached A5 dependencies are stale")
        except AnalysisError as exc:
            if exc.code == "provenance_cache_invalid":
                raise
            raise AnalysisError("provenance_cache_invalid", f"Invalid A5 cache entry: {path}") from exc
        except (OSError, ValueError) as exc:
            raise AnalysisError("provenance_cache_invalid", f"Invalid A5 cache entry: {path}") from exc
        return value

    def publish(self, layer, key, value, *, stability="deterministic"):
        if not isinstance(value, dict):
            raise AnalysisError("provenance_cache_invalid", "A5 cache values must be documents")
        if stability != "deterministic" or value.get("status") == "failed":
            raise AnalysisError("provenance_cache_transient", "Transient or failed A5 results are not cacheable")
        validate_provenance_document(value, value.get("kind"))
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("provenance_cache_collision", f"Conflicting A5 cache entry: {path}")
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
                    raise AnalysisError("provenance_cache_collision", f"Conflicting A5 cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
