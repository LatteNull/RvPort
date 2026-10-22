"""Content-addressed A3 cache isolated from P1-P4 and A1/A2 namespaces."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .cpp_thread_contracts import validate_cpp_thread_document


def cache_key(layer, payload, dependencies=()):
    return identity({
        "namespace": "cpp-thread-lifecycle-v1", "layer": f"{layer}-v1",
        "policy": "cpp-thread-lifecycle-v1", "payload": payload,
        "dependencies": sorted(dependencies),
    })


class CppThreadCache:
    def __init__(self, root):
        self.root = Path(root).resolve() / "cpp-thread-lifecycle-v1"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("cpp_thread_cache_invalid", "A3 cache path escapes its namespace")
        return path

    def load(self, layer, key, kind, *, dependencies=None):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_cpp_thread_document(value, kind)
            if dependencies is not None and value.get("dependencies") != dependencies:
                raise AnalysisError("cpp_thread_cache_invalid", "Cached A3 dependencies are stale")
        except AnalysisError as exc:
            if exc.code == "cpp_thread_cache_invalid":
                raise
            raise AnalysisError("cpp_thread_cache_invalid", f"Invalid A3 cache entry: {path}") from exc
        except (OSError, ValueError) as exc:
            raise AnalysisError("cpp_thread_cache_invalid", f"Invalid A3 cache entry: {path}") from exc
        return value

    def publish(self, layer, key, value, *, stability="deterministic"):
        if not isinstance(value, dict):
            raise AnalysisError("cpp_thread_cache_invalid", "A3 cache values must be documents")
        if stability != "deterministic" or value.get("status") == "failed":
            raise AnalysisError("cpp_thread_cache_transient", "Transient or failed A3 results are not cacheable")
        validate_cpp_thread_document(value, value.get("kind"))
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("cpp_thread_cache_collision", f"Conflicting A3 cache entry: {path}")
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
                    raise AnalysisError("cpp_thread_cache_collision", f"Conflicting A3 cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
