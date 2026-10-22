"""Read-only P2 consumption boundary, independent of original P1 commands."""

from copy import deepcopy
from pathlib import Path

from .contracts import AnalysisError, file_hash, read_document, validate
from .effect_contracts import read_effect_document, validate_effect_document
from .effect_references import require, validate_effect_references
from .scope import preflight


def input_hash(path):
    try:
        return file_hash(path)
    except OSError as exc:
        raise AnalysisError("inputs_changed", f"Input unavailable: {path}") from exc


class EffectInputs:
    """Snapshot the exact manifest members. No directory scan, linking or writes.

    BC parsing/LLVM verification remains the worker's responsibility. Hash checks
    cover files before and after consumption; they cannot detect an ABA change.
    """

    def __init__(self, scope, artifacts, modules):
        self.scope, self.artifacts, self.modules = deepcopy((scope, artifacts, modules))
        validate(self.scope, "ScopeManifest")
        members = set(self.scope["members"])
        require(set(self.artifacts) == set(self.modules) == members, "Inputs must match exactly the declared scope")
        self.scope_id = preflight(self.scope, self.artifacts, self.modules)
        require(len({a["profile"] for a in self.artifacts.values()}) == 1, "Mixed analysis profiles")
        self.files = {}
        for artifact in self.artifacts.values():
            path, digest = artifact["path"], artifact["sha256"]
            require(path not in self.files or self.files[path] == digest, "Conflicting hashes for the same BC path")
            self.files[path] = digest
        self.recheck()

    @classmethod
    def load(cls, scope_path, store):
        scope_digest = input_hash(scope_path)
        scope = read_document(scope_path, "ScopeManifest")
        store = Path(store).resolve()
        artifacts, modules, metadata = {}, {}, {}
        for key in scope["members"]:
            for folder, kind, target in (("artifacts", "BCArtifact", artifacts), ("facts", "ModuleFacts", modules)):
                path = (store / folder / f"{key}.json").resolve()
                require(store in path.parents, "Input metadata escapes artifact store")
                before = input_hash(path)
                target[key] = read_document(path, kind)
                metadata[str(path)] = before
        result = cls(scope, artifacts, modules)
        result.files.update(metadata)
        # Snapshot scope itself too, rather than accepting a changed manifest later.
        require(read_document(scope_path, "ScopeManifest") == scope, "Scope changed while loading")
        result.files[str(Path(scope_path).resolve())] = scope_digest
        result.recheck()
        return result

    def recheck(self):
        for path, expected in self.files.items():
            actual = input_hash(path)
            if actual != expected:
                raise AnalysisError("inputs_changed", f"Input changed: {path}")

    def consume(self, value, *, summaries=None, local_facts=None):
        """Validate every supplied dependency, including its own references.

        The caller explicitly supplies the dependency closure, not arbitrary cache
        files inferred from filenames. All products must have the same policy,
        scope, profile and effective budget. No semantic proof is invented here.
        """
        self.recheck()
        validate_effect_document(value, value.get("kind") if isinstance(value, dict) else None)
        for dependency in [*(summaries or {}).values(), *(local_facts or {}).values()]:
            validate_effect_document(dependency, dependency.get("kind") if isinstance(dependency, dict) else None)
        value, summaries = deepcopy(value), deepcopy(summaries or {})
        local_facts = deepcopy(local_facts or {})
        validate_effect_document(value, value.get("kind") if isinstance(value, dict) else None)
        for context, summary in summaries.items():
            validate_effect_document(summary, "EffectSummary")
            require(summary["context_id"] == context, "Dependency map key mismatch")
        for key, local in local_facts.items():
            validate_effect_document(local, "LocalAnalysisFacts")
            require(local["origin"]["artifact_key"] == key, "Local dependency map key mismatch")
        for item in [value, *summaries.values(), *local_facts.values()]:
            if "scope_id" in item:
                require(item["scope_id"] == self.scope_id, "Foreign analysis scope")
            require(item["budgets"] == value["budgets"], "Foreign dependency budget")
            validate_effect_references(item, self.artifacts, self.modules, summaries=summaries, local_facts=local_facts)
        self.recheck()
        return value

    def consume_evaluation(self, request, result, *, summaries=None, local_facts=None):
        """Bind a result to the scheduler's request, not the worker's assertion."""
        validate_effect_document(request, "LocalEvaluationRequest")
        validate_effect_document(result, "LocalEvaluationResult")
        require(result["request"] == request, "Worker substituted evaluation request")
        return self.consume(result, summaries=summaries, local_facts=local_facts)

    def consume_file(self, path, kind, *, summaries=None, local_facts=None):
        before = input_hash(path)
        result = self.consume(read_effect_document(path, kind), summaries=summaries, local_facts=local_facts)
        require(input_hash(path) == before, "Derived input changed while consuming")
        return result
