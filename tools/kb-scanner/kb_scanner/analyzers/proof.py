from __future__ import annotations

from dataclasses import dataclass

from ..core import ProofPath, Relation, stable_id
from ..graph import GraphStore


@dataclass(frozen=True, slots=True)
class ProofBudgets:
    max_depth: int = 8
    max_visited: int = 10_000
    max_paths: int = 4

    def __post_init__(self) -> None:
        if min(self.max_depth, self.max_visited, self.max_paths) < 1:
            raise ValueError("proof budgets must be positive")


class ProofPathResolver:
    __slots__ = ("_store", "_budgets")

    def __init__(self, store: GraphStore, budgets: ProofBudgets = ProofBudgets()) -> None:
        self._store = store
        self._budgets = budgets

    def resolve(
        self,
        source_ids: tuple[str, ...],
        target_ids: tuple[str, ...],
        relations: tuple[Relation, ...],
        *,
        required_evidence_ids: frozenset[str] | None = None,
    ) -> tuple[ProofPath, ...]:
        if required_evidence_ids == frozenset():
            return ()
        by_id = {item.id: item for item in relations}
        proofs: dict[str, ProofPath] = {}
        planner = getattr(self._store, "plan_queries", None)
        plan = None if planner is None else planner(
            source_ids, target_ids, max_depth=self._budgets.max_depth,
            required_evidence_ids=required_evidence_ids,
        )
        targets = tuple(sorted(set(target_ids)))
        for source_id in sorted(set(source_ids)):
            for target_id in targets if plan is None else plan.get(source_id, ()):
                result = self._store.search_paths(
                    source_id,
                    target_id,
                    max_depth=self._budgets.max_depth,
                    max_visited=self._budgets.max_visited,
                    max_paths=self._budgets.max_paths,
                )
                for relation_ids in result.paths:
                    path_relations = tuple(by_id[item] for item in relation_ids if item in by_id)
                    if required_evidence_ids is not None and not any(
                        evidence_id in required_evidence_ids
                        for item in path_relations for evidence_id in item.evidence_ids
                    ):
                        continue
                    local_reasons = {
                        str(item.metadata.get("reason"))
                        for item in path_relations
                        if item.status != "complete" and item.metadata.get("reason")
                    }
                    incomplete = len(path_relations) != len(relation_ids) or any(
                        item.status != "complete" for item in path_relations
                    )
                    status = "partial" if result.status != "complete" or incomplete else "complete"
                    reasons = set(filter(None, (result.reason,))) | local_reasons
                    if len(path_relations) != len(relation_ids):
                        reasons.add("missing-relation")
                    reason = ",".join(sorted(reasons)) or None
                    proof_id = stable_id(
                        "proof_path",
                        1,
                        source_id,
                        target_id,
                        relation_ids,
                        status,
                        reason,
                    )
                    proofs[proof_id] = ProofPath(
                        id=proof_id,
                        source_id=source_id,
                        target_id=target_id,
                        relation_ids=relation_ids,
                        status=status,
                        reason=reason,
                        visited=result.visited,
                        truncated=result.truncated,
                    )
        return tuple(sorted(proofs.values(), key=lambda item: item.id))
