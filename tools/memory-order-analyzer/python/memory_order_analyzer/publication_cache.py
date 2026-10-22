"""Content-addressed P4 caches with complete transitive input identities."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .publication_contracts import validate_publication_document


def local_key(origin, budgets, model_id):
    return identity({"layer": "publication-local-v1", "origin": origin,
                     "budgets": budgets, "model": model_id,
                     "analysis": "0.1.0", "policy": "single-publication-risks-v1"})


def template_key(scope_id, request, dependencies):
    return identity({"layer": "publication-template-v1", "scope": scope_id,
                     "request": request, "dependencies": sorted(dependencies)})


def graph_key(request, thread_graph, dependencies):
    return identity({"layer": "publication-graph-v1", "request": request,
                     "thread_graph": identity(thread_graph),
                     "dependencies": sorted(dependencies)})


class PublicationCache:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("publication_cache_invalid", "Publication cache path escapes root")
        return path

    def load(self, layer, key, kind):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_publication_document(value, kind)
        except (OSError, ValueError, AnalysisError) as exc:
            raise AnalysisError("publication_cache_invalid", f"Invalid publication cache entry: {path}") from exc
        return value

    def publish(self, layer, key, value):
        validate_publication_document(value, value.get("kind") if isinstance(value, dict) else None)
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("publication_cache_collision", f"Conflicting publication cache entry: {path}")
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
                    raise AnalysisError("publication_cache_collision", f"Conflicting publication cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
