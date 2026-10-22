"""Content-addressed cache isolated to concurrent-access candidate artifacts."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .concurrent_access_contracts import validate_concurrent_access_document


def cache_key(stage, request, dependency_digests):
    return identity({"namespace": "concurrent-access-candidate-graph-v1", "stage": stage,
                     "request": request, "dependencies": sorted(dependency_digests)})


class ConcurrentAccessCache:
    def __init__(self, root):
        self.root = Path(root) / "concurrent-access-candidate-graph-v1"

    def _path(self, stage, key):
        if not stage or Path(stage).is_absolute() or ".." in Path(stage).parts:
            raise AnalysisError("invalid_reference", "R2 cache stage escapes its namespace")
        if not isinstance(key, str) or len(key) != 64 or any(ch not in "0123456789abcdef" for ch in key):
            raise AnalysisError("invalid_reference", "R2 cache key must be a SHA-256 digest")
        return self.root / stage / f"{key}.json"

    def load(self, stage, key, kind):
        path = self._path(stage, key)
        if not path.is_file():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if set(envelope) != {"namespace", "stage", "key", "artifact"} or \
                    envelope["namespace"] != "concurrent-access-candidate-graph-v1" or \
                    envelope["stage"] != stage or envelope["key"] != key:
                raise AnalysisError("cache_invalid", "R2 cache envelope binding is invalid")
            value = validate_concurrent_access_document(envelope["artifact"], kind)
        except (AnalysisError, OSError, ValueError, KeyError, TypeError) as exc:
            raise AnalysisError("cache_invalid", f"Invalid R2 cache entry: {path}") from exc
        return value if value.get("status") == "complete" else None

    def publish(self, stage, key, value):
        if value.get("status") != "complete":
            raise AnalysisError("cache_transient", "Partial or failed R2 artifacts cannot be cached")
        path = self._path(stage, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            current = self.load(stage, key, value["kind"])
            if current != value:
                raise AnalysisError("cache_collision", f"Conflicting R2 cache entry: {path}")
            return path
        envelope = {"namespace": "concurrent-access-candidate-graph-v1", "stage": stage,
                    "key": key, "artifact": value}
        handle, temporary = tempfile.mkstemp(prefix=".r2-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(canonical(envelope)); stream.write("\n")
            try:
                os.link(temporary, path)
            except FileExistsError:
                current = self.load(stage, key, value["kind"])
                if current != value:
                    raise AnalysisError("cache_collision", f"Conflicting R2 cache entry: {path}")
        finally:
            Path(temporary).unlink(missing_ok=True)
        return path
