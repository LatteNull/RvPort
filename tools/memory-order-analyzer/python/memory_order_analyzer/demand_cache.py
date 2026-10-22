"""Content-addressed completed-shard cache for R3."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .demand_contracts import validate_demand_document


def cache_key(*, bc_digest, profile_id, target, data_layout, function_id, layer,
              context_id, policy_id, budgets, extractor_version="0.1.0"):
    return identity({
        "namespace": "demand-driven-function-analysis-v1", "bc_digest": bc_digest,
        "profile_id": profile_id, "target": target, "data_layout": data_layout,
        "function_id": function_id, "layer": layer, "context_id": context_id,
        "policy_id": policy_id, "budgets": budgets, "extractor_version": extractor_version,
    })


class DemandAnalysisCache:
    def __init__(self, root):
        self.root = Path(root) / "demand-driven-function-analysis-v1"

    def _path(self, layer, key):
        if layer not in {"semantic", "effect", "thread"}:
            raise AnalysisError("invalid_reference", "R3 cache layer is invalid")
        if not isinstance(key, str) or len(key) != 64 or any(ch not in "0123456789abcdef" for ch in key):
            raise AnalysisError("invalid_reference", "R3 cache key must be a SHA-256 digest")
        return self.root / layer / f"{key}.json"

    def load(self, layer, key, kind):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if set(envelope) != {"namespace", "layer", "key", "artifact"} or \
                    envelope["namespace"] != "demand-driven-function-analysis-v1" or \
                    envelope["layer"] != layer or envelope["key"] != key:
                raise AnalysisError("cache_invalid", "R3 cache envelope binding is invalid")
            value = validate_demand_document(envelope["artifact"], kind)
        except (AnalysisError, OSError, ValueError, KeyError, TypeError) as exc:
            raise AnalysisError("cache_invalid", f"Invalid R3 cache entry: {path}") from exc
        return value if value.get("status") == "completed" else None

    def publish(self, layer, key, value):
        if value.get("status") != "completed":
            raise AnalysisError("cache_transient", "Only completed R3 function shards can be cached")
        validate_demand_document(value, value["kind"])
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            current = self.load(layer, key, value["kind"])
            if current != value:
                raise AnalysisError("cache_collision", f"Conflicting R3 cache entry: {path}")
            return path
        envelope = {"namespace": "demand-driven-function-analysis-v1", "layer": layer,
                    "key": key, "artifact": value}
        handle, temporary = tempfile.mkstemp(prefix=".r3-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(canonical(envelope)); stream.write("\n")
            try:
                os.link(temporary, path)
            except FileExistsError:
                current = self.load(layer, key, value["kind"])
                if current != value:
                    raise AnalysisError("cache_collision", f"Conflicting R3 cache entry: {path}")
        finally:
            Path(temporary).unlink(missing_ok=True)
        return path
