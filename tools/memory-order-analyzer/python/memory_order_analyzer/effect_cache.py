"""Content-addressed derived cache; raw BC/P1 identities are never rewritten."""

import json
import os
from pathlib import Path
import tempfile

from .contracts import AnalysisError, canonical, identity
from .effect_contracts import validate_effect_document


def local_key(origin, budgets, local_request=None):
    return identity({"layer": "local-v1", "origin": origin, "budgets": budgets,
                     "request": local_request, "analysis": "0.1.0", "policy": "scoped-effects-v1"})


def template_key(scope_id, root, budgets, adoptions, dependencies=()):
    return identity({"layer": "summary-template-v1", "scope": scope_id, "root": root,
                     "budgets": budgets, "adoptions": adoptions,
                     "dependencies": sorted(dependencies), "analysis": "0.1.0",
                     "policy": "scoped-effects-v1"})


def instance_key(template, invocations):
    return identity({"layer": "summary-instance-v1", "template": template,
                     "invocations": invocations})


def scc_key(scope_id, members, member_keys, budgets):
    return identity({"layer": "scc-v1", "scope": scope_id, "members": sorted(members),
                     "member_keys": sorted(member_keys), "budgets": budgets})


class DerivedCache:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layer, key):
        path = (self.root / layer / f"{key}.json").resolve()
        if self.root not in path.parents:
            raise AnalysisError("cache_invalid", "Derived cache path escapes root")
        return path

    def load(self, layer, key, kind):
        path = self._path(layer, key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_effect_document(value, kind)
        except (OSError, ValueError, AnalysisError) as exc:
            raise AnalysisError("cache_invalid", f"Invalid derived cache entry: {path}") from exc
        return value

    def publish(self, layer, key, value):
        path = self._path(layer, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(value)
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise AnalysisError("cache_collision", f"Conflicting derived cache entry: {path}")
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
                    raise AnalysisError("cache_collision", f"Conflicting derived cache entry: {path}")
        finally:
            temporary.unlink(missing_ok=True)
        return path
