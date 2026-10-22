from __future__ import annotations

from collections import deque
from typing import Protocol

import networkx as nx

from ..core import Entity, PathSearchResult, Relation


class GraphStore(Protocol):
    def add_entity(self, entity: Entity) -> None: ...

    def add_relation(self, relation: Relation) -> None: ...

    def entity(self, entity_id: str) -> Entity | None: ...

    def outgoing(self, entity_id: str, kind: str | None = None) -> tuple[Relation, ...]: ...

    def incoming(self, entity_id: str, kind: str | None = None) -> tuple[Relation, ...]: ...

    def search_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        max_depth: int,
        max_visited: int,
        max_paths: int,
    ) -> PathSearchResult: ...


class NetworkXGraphStore:
    """NetworkX adapter whose public boundary contains only scanner-owned objects."""

    __slots__ = ("_graph", "_entities", "_relations", "_outgoing_cache")

    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()
        self._entities: dict[str, Entity] = {}
        self._relations: dict[str, Relation] = {}
        self._outgoing_cache: dict[str, tuple[Relation, ...]] = {}

    def add_entity(self, entity: Entity) -> None:
        existing = self._entities.get(entity.id)
        if existing is not None and existing != entity:
            raise ValueError(f"entity identity collision: {entity.id}")
        self._entities[entity.id] = entity
        self._graph.add_node(entity.id)

    def add_relation(self, relation: Relation) -> None:
        if relation.source_id not in self._entities or relation.target_id not in self._entities:
            raise ValueError("both relation endpoints must be registered entities")
        existing = self._relations.get(relation.id)
        if existing is not None:
            if existing != relation:
                raise ValueError(f"relation identity collision: {relation.id}")
            return
        self._relations[relation.id] = relation
        self._graph.add_edge(relation.source_id, relation.target_id, key=relation.id)
        self._outgoing_cache.pop(relation.source_id, None)

    def entity(self, entity_id: str) -> Entity | None:
        return self._entities.get(entity_id)

    def outgoing(self, entity_id: str, kind: str | None = None) -> tuple[Relation, ...]:
        if entity_id not in self._entities:
            return ()
        if entity_id not in self._outgoing_cache:
            self._outgoing_cache[entity_id] = tuple(sorted(
                (self._relations[key] for _, _, key in self._graph.out_edges(entity_id, keys=True)),
                key=_relation_key,
            ))
        relations = self._outgoing_cache[entity_id]
        return relations if kind is None else tuple(item for item in relations if item.kind == kind)

    def plan_queries(self, source_ids, target_ids, *, max_depth, required_evidence_ids=None):
        from .queries import plan_queries
        return plan_queries(source_ids, target_ids, tuple(self._relations.values()), max_depth, required_evidence_ids)

    def incoming(self, entity_id: str, kind: str | None = None) -> tuple[Relation, ...]:
        if entity_id not in self._entities:
            return ()
        relations = (
            self._relations[key]
            for _, _, key in self._graph.in_edges(entity_id, keys=True)
            if kind is None or self._relations[key].kind == kind
        )
        return tuple(sorted(relations, key=_relation_key))

    def search_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        max_depth: int,
        max_visited: int,
        max_paths: int,
    ) -> PathSearchResult:
        if min(max_depth, max_visited, max_paths) < 1:
            raise ValueError("path budgets must be positive")
        if source_id not in self._entities or target_id not in self._entities:
            return PathSearchResult(status="unknown", reason="missing-endpoint")

        queue = deque([(source_id, tuple(), frozenset({source_id}))])
        paths: list[tuple[str, ...]] = []
        visited = 0
        reasons: set[str] = set()
        truncated = False
        while queue:
            if visited >= max_visited:
                truncated = True
                reasons.add("max-visited")
                break
            current, relation_ids, seen = queue.popleft()
            visited += 1
            if current == target_id:
                paths.append(relation_ids)
                if len(paths) >= max_paths:
                    if queue:
                        truncated = True
                        reasons.add("max-paths")
                    break
                continue
            outgoing = self.outgoing(current)
            if len(relation_ids) >= max_depth:
                if outgoing:
                    truncated = True
                    reasons.add("max-depth")
                continue
            for relation in outgoing:
                if relation.target_id in seen:
                    reasons.add("cycle")
                    continue
                queue.append(
                    (
                        relation.target_id,
                        (*relation_ids, relation.id),
                        seen | {relation.target_id},
                    )
                )

        ordered = tuple(sorted(set(paths)))
        if ordered:
            status = "partial" if truncated or "cycle" in reasons else "complete"
        elif truncated or "cycle" in reasons:
            status = "partial"
        else:
            status = "not_found"
        reason = ",".join(sorted(reasons)) or None
        return PathSearchResult(ordered, status, visited, truncated, reason)

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relation_count(self) -> int:
        return len(self._relations)


def _relation_key(relation: Relation) -> tuple[str, str, str, str]:
    return relation.kind, relation.source_id, relation.target_id, relation.id
