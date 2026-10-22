"""Content-addressed P3 cache with transitive identities."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .thread_contracts import validate_thread_document


def local_thread_key(origin, budgets, model_id):
    return identity({"layer": "thread-local-v1", "origin": origin, "budgets": budgets,
                     "model": model_id, "analysis": "0.1.0", "policy": "thread-sync-contexts-v1"})


def context_template_key(scope_id, entry, arguments, budgets, model_id, dependencies):
    return identity({"layer": "thread-context-template-v1", "scope": scope_id, "entry": entry,
                     "arguments": arguments, "budgets": budgets, "model": model_id,
                     "dependencies": sorted(dependencies)})


def graph_key(request, dependencies):
    return identity({"layer": "thread-graph-v1", "request": request,
                     "dependencies": sorted(dependencies)})


class ThreadCache:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("thread_cache_invalid", "Thread cache path escapes root")
        return path

    def load(self, layer, key, kind):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_thread_document(value, kind)
        except (OSError, ValueError, AnalysisError) as exc:
            raise AnalysisError("thread_cache_invalid", f"Invalid thread cache entry: {path}") from exc
        return value

    def publish(self, layer, key, value):
        validate_thread_document(value, value.get("kind") if isinstance(value, dict) else None)
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("thread_cache_collision", f"Conflicting thread cache entry: {path}")
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
                    raise AnalysisError("thread_cache_collision", f"Conflicting thread cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
