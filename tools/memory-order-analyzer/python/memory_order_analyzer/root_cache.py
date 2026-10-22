"""Deterministic R1 cache isolated from P1--A5 namespaces."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .root_contracts import validate_root_document


def cache_key(layer, payload, dependencies=()):
    return identity({
        "namespace": "execution-root-driven-analysis-v1", "layer": f"{layer}-v1",
        "policy": "execution-root-driven-analysis-v1", "payload": payload,
        "dependencies": sorted(dependencies),
    })


class RootAnalysisCache:
    def __init__(self, root):
        self.root = Path(root).resolve() / "execution-root-driven-analysis-v1"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("root_cache_invalid", "R1 cache path escapes its namespace")
        return path

    def load(self, layer, key, kind):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_root_document(value, kind)
        except AnalysisError as exc:
            raise AnalysisError("root_cache_invalid", f"Invalid R1 cache entry: {path}") from exc
        except (OSError, ValueError) as exc:
            raise AnalysisError("root_cache_invalid", f"Invalid R1 cache entry: {path}") from exc
        return value

    def publish(self, layer, key, value, *, stability="deterministic"):
        if stability != "deterministic" or value.get("status") == "failed":
            raise AnalysisError("root_cache_transient", "Transient or failed R1 results are not cacheable")
        validate_root_document(value, value.get("kind"))
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("root_cache_collision", f"Conflicting R1 cache entry: {path}")
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
                    raise AnalysisError("root_cache_collision", f"Conflicting R1 cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
