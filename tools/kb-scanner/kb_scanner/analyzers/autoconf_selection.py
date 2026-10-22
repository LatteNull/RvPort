"""Autoconf event graph: source occurrences, not keyword-based architecture gaps."""
from __future__ import annotations

from ..core import AnalysisSnapshot, CompletionStatus, Diagnostic, DiagnosticSeverity, Entity, ProofPath, Relation, StageResult, stable_id


def analyze_autoconf(context, facts, base, max_relations, max_paths):
    selected = [fact for fact in facts.facts if "autoconf" in fact.metadata and not fact.metadata["autoconf"].get("raw")]
    by_key = {fact.metadata["autoconf"]["key"]: fact for fact in selected}
    entities = {item.id: item for item in (*facts.entities, *base.entities)}
    relations = {item.id: item for item in base.relations}
    proofs = {item.id: item for item in base.proof_paths}
    root = Entity(stable_id("build_entity", 1, "architecture_selector", context.target_arch),
                  "architecture_selector", context.target_arch)
    entities[root.id] = root
    for fact in selected:
        identifier = stable_id("autoconf-occurrence", fact.id)
        entities[identifier] = Entity(identifier, "build_configuration", fact.canonical_value,
                                      properties={"factId": fact.id, "sourceEvidenceId": fact.evidence_ids[0]})
    memo, reasons = {}, set()
    counts = [0, 0]

    def visit(fact, trail=()):
        if fact.id in memo:
            return memo[fact.id]
        if fact.id in trail or len(trail) >= 64:
            reasons.add("autoconf-proof-cycle-or-depth")
            return (), False
        info = fact.metadata["autoconf"]
        parents = [by_key.get(key) for key in info.get("parents", ())]
        complete = not info.get("reason", "") or info.get("resultStatus", info.get("outcome")) in {"accepted", "rejected"}
        incoming = []
        for parent in parents:
            if parent is None:
                complete = False
                reasons.add("autoconf-proof-parent-missing")
            else:
                paths, ok = visit(parent, (*trail, fact.id))
                incoming.extend((parent, path) for path in paths)
                complete = complete and ok
        if not incoming:
            incoming = [(None, ())]
        result = []
        target = stable_id("autoconf-occurrence", fact.id)
        # Relation and proof budgets are independent. Exhausted proof capacity
        # must not erase a bounded source relation or its unknown outcome.
        if counts[0] + len(incoming) > max_relations:
            reasons.add("autoconf-proof-budget")
            memo[fact.id] = (), False
            return memo[fact.id]
        if counts[1] + len(incoming) > max_paths:
            complete = False
            reasons.add("autoconf-proof-budget")
        for parent, prefix in incoming:
            source = root.id if parent is None else stable_id("autoconf-occurrence", parent.id)
            status = "selected" if complete else "unknown"
            metadata = {"autoconf": dict(info), "itemKind": fact.kind, "factId": fact.id,
                        "value": fact.canonical_value, "matchedEvidenceIds": fact.evidence_ids,
                        "configuration": "default", "reason": info.get("reason", "autoconf-static-event")}
            if info.get("outcome") == "rejected" and info.get("bound") and complete:
                metadata["issue"] = "missing_riscv_selection_path"
            identifier = stable_id("autoconf-relation", source, target, status)
            relations[identifier] = Relation(identifier, "includes" if fact.kind == "build_include" else "selects",
                                             source, target, fact.evidence_ids, status=status, metadata=metadata)
            path = (*prefix, identifier)
            proof_status = "complete" if complete else "unknown"
            proof = ProofPath(stable_id("autoconf-proof", fact.id, path, proof_status), root.id, target, path,
                              proof_status, None if complete else "autoconf-proof-incomplete", len(path) + 1, False)
            if counts[1] < max_paths:
                proofs[proof.id] = proof
                counts[1] += 1
            result.append(path)
            counts[0] += 1
        memo[fact.id] = tuple(result), complete
        return memo[fact.id]

    for fact in sorted(selected, key=lambda item: item.id):
        visit(fact)
    diagnostics = tuple(Diagnostic("build-selection.autoconf-partial", "analysis.build-selection",
                                   DiagnosticSeverity.WARNING, reason, producer="autoconf-selection",
                                   details={"reason": reason}) for reason in sorted(reasons))
    return StageResult(AnalysisSnapshot(entities=tuple(sorted(entities.values(), key=lambda item: item.id)),
                                       relations=tuple(sorted(relations.values(), key=lambda item: item.id)),
                                       proof_paths=tuple(sorted(proofs.values(), key=lambda item: item.id))),
                       CompletionStatus.PARTIAL if diagnostics else CompletionStatus.COMPLETE, diagnostics)
