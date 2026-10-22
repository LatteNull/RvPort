"""Shared relation-endpoint index and occurrence-driven source graph queries."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import chain


_KINDS = {"selects": "selects", "selects_source": "selects", "adds_argument": "selects",
          "uses_source": "selects", "includes": "includes", "defines": "defines",
          "has_branch": "contains", "contains": "contains", "invokes_macro": "invokes_macro",
          "expands_to": "expands_to", "calls": "calls", "depends_on": "contains",
          "requires": "contains", "excludes": "selects", "produces": "contains",
          "alternative_to": "alternative_to", "guarded_by": "selects",
          "function_attribute_owner": "defines", "function_body_contains": "contains"}
_EXPAND = {"invokes_macro", "expands_to", "calls", "alternative_to"}


@dataclass(frozen=True)
class Arc:
    source: str
    target: str
    kind: str
    relation_ids: tuple[str, ...]


@dataclass(frozen=True)
class Query:
    evidence_ids: tuple[str, ...]
    arcs: tuple[Arc, ...]
    reasons: tuple[str, ...]
    visited: int
    paths: int


class SourceChainIndex:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.incoming = defaultdict(list)
        self.outgoing = defaultdict(list)
        self.scoped_incoming = defaultdict(list)
        self.scoped_outgoing = defaultdict(list)
        self.macro_files = defaultdict(set)
        self.evidence_nodes = {identifier: "e:" + identifier for identifier, evidence in snapshot.evidence.items() if evidence.location}
        facts = getattr(snapshot, "facts", {})
        endpoints = {}
        for identifier, entity in snapshot.entities.items():
            evidence_id = entity.properties.get("sourceEvidenceId")
            fact = facts.get(entity.properties.get("factId"))
            if evidence_id is None and fact is not None and len(fact.evidence_ids) == 1:
                evidence_id = fact.evidence_ids[0]
            endpoints[identifier] = self.evidence_nodes.get(evidence_id, "n:" + identifier)
        for relation in sorted(snapshot.relations.values(), key=lambda r: r.id):
            effect = relation.metadata.get('macroEffect')
            if effect:
                files = self.macro_files[effect['invocationId'], relation.metadata.get('configuration')]
                files.add(effect.get('translationUnit'))
                for eid in relation.evidence_ids:
                    evidence = snapshot.evidence.get(eid)
                    if evidence is not None and evidence.location:
                        files.add(getattr(getattr(evidence.location, 'start', None), 'path', None))
            if relation.kind not in _KINDS:
                continue
            source = endpoints.get(relation.source_id, "n:" + relation.source_id)
            target = endpoints.get(relation.target_id, "n:" + relation.target_id)
            mids = []
            for identifier in relation.evidence_ids:
                item = snapshot.evidence.get(identifier)
                if item is not None and item.location and (
                    relation.kind in {"expands_to", "calls"} and item.kind == "macro_replacement_token"
                    or relation.kind == "includes" and item.kind == "include"
                ):
                    mids.append(self.evidence_nodes[identifier])
            if relation.kind == "guarded_by":
                source, target = target, source
            sequence = [source, *sorted(set(mids) - {source, target}), target]
            for left, right in zip(sequence, sequence[1:]):
                if left == right:
                    continue
                arc = Arc(left, right, _KINDS[relation.kind], (relation.id,))
                self.incoming[right].append(arc)
                self.outgoing[left].append(arc)
                invocation = effect['invocationId'] if effect else None
                self.scoped_incoming[invocation, right].append(arc)
                self.scoped_outgoing[invocation, left].append(arc)

    def query(self, anchor, *, configuration=None, max_depth=16, max_visited=256, max_paths=32):
        if min(max_depth, max_visited, max_paths) < 1:
            raise ValueError("source-chain budgets must be positive")
        if anchor not in self.evidence_nodes:
            raise ValueError("source-chain anchor must have a source location")
        start = self.evidence_nodes[anchor]
        queue = deque([(start, 0)])
        visited = set()
        arcs = set()
        reasons = set()
        invocation = self.snapshot.evidence[anchor].metadata.get('callEvidenceId')
        macro_files = self.macro_files.get((invocation, configuration), set()) - {None}

        def adjacent(node, incoming):
            if not invocation:
                return (self.incoming if incoming else self.outgoing).get(node, ())
            scoped = self.scoped_incoming if incoming else self.scoped_outgoing
            return chain(scoped.get((None, node), ()), scoped.get((invocation, node), ()))

        def applicable(arc):
            if invocation:
                for rid in arc.relation_ids:
                    relation = self.snapshot.relations[rid]
                    effect = relation.metadata.get('macroEffect')
                    if not effect and relation.kind in {'calls', 'invokes_macro', 'expands_to'}:
                        return False
                    if macro_files and relation.kind == 'includes' and any(
                        self.snapshot.evidence[eid].location.start.path not in macro_files
                        for eid in relation.evidence_ids if eid in self.snapshot.evidence
                        and self.snapshot.evidence[eid].kind == 'include' and self.snapshot.evidence[eid].location
                    ):
                        return False
            configs = {self.snapshot.relations[rid].metadata.get("configuration") for rid in arc.relation_ids}
            configs.discard(None)
            configs.discard("default")
            return not configuration or configuration == "default" or not configs or configs == {configuration}

        while queue:
            node, depth = queue.popleft()
            if node in visited:
                continue
            if len(visited) >= max_visited:
                reasons.add("reference_budget_exceeded")
                break
            visited.add(node)
            if node.startswith("n:") and node[2:] not in self.snapshot.entities:
                reasons.add("missing_reference")
            candidates = [(arc, arc.source) for arc in adjacent(node, True) if applicable(arc)]
            if node.startswith("e:") and self.snapshot.evidence[node[2:]].metadata.get("sourceChain", {}).get("role") == "recipe":
                origins = {eid for successor in adjacent(node, False) if successor.target in visited
                           for rid in successor.relation_ids for eid in self.snapshot.relations[rid].evidence_ids}
                candidates = [(arc, other) for arc, other in candidates if not other.startswith("e:") or other[2:] in origins]
            # Only invocation/replacement descendants, never fan out through
            # abstract file/configuration entities into unrelated occurrences.
            if node.startswith("e:"):
                candidates.extend((arc, arc.target) for arc in adjacent(node, False) if
                    (arc.kind in _EXPAND or any(self.snapshot.relations[rid].kind == "function_attribute_owner" for rid in arc.relation_ids))
                    and arc.target.startswith("e:") and applicable(arc))
            if depth >= max_depth:
                if any(other not in visited for _, other in candidates):
                    reasons.add("reference_budget_exceeded")
                continue
            for arc, other in candidates:
                arcs.add(arc)
                if other not in visited:
                    queue.append((other, depth + 1))
        arcs = {arc for arc in arcs if arc.source in visited and arc.target in visited}
        degree = {node: 0 for node in visited}
        followers = defaultdict(set)
        for arc in arcs:
            if arc.target not in followers[arc.source]:
                degree[arc.target] += 1
                followers[arc.source].add(arc.target)
        ready = [node for node, count in degree.items() if count == 0]
        processed = 0
        while ready:
            node = ready.pop()
            processed += 1
            for target in followers[node]:
                degree[target] -= 1
                if degree[target] == 0:
                    ready.append(target)
        if processed != len(visited):
            reasons.add("cycle_detected")
        incoming = defaultdict(list)
        for arc in sorted(arcs, key=lambda a: (a.source, a.target, a.relation_ids)):
            incoming[arc.target].append(arc)
        projected = set()
        paths = 0
        for target in sorted(n for n in visited if n.startswith("e:")):
            pending = [(target, (), (target,))]
            while pending:
                node, tail, seen = pending.pop()
                for arc in incoming.get(node, ()):
                    if arc.source in seen:
                        reasons.add("cycle_detected")
                        continue
                    sequence = (*arc.relation_ids, *tail)
                    if arc.source.startswith("e:"):
                        if paths >= max_paths:
                            reasons.add("reference_budget_exceeded")
                            break
                        projected.add(Arc(arc.source[2:], target[2:], arc.kind, tuple(dict.fromkeys(sequence))))
                        paths += 1
                    elif len(seen) >= max_depth:
                        reasons.add("reference_budget_exceeded")
                    else:
                        pending.append((arc.source, sequence, (*seen, arc.source)))
                if paths >= max_paths:
                    break
        return Query(tuple(sorted(n[2:] for n in visited if n.startswith("e:"))),
                     tuple(sorted(projected, key=lambda a: (a.source, a.target, a.kind, a.relation_ids))),
                     tuple(sorted(reasons)), len(visited), paths)


def primary_path(anchor, arcs, *, max_depth=16, max_paths=32):
    """One real directed path through the anchor; bounded deterministic search."""
    incoming, outgoing = defaultdict(set), defaultdict(set)
    for arc in arcs:
        if arc.kind == "alternative_to":
            continue
        incoming[arc.target].add(arc.source)
        outgoing[arc.source].add(arc.target)

    def walk(adjacency, initial):
        pending, completed = [initial], []
        while pending and len(completed) < max_paths:
            path = pending.pop()
            choices = sorted(adjacency[path[-1]] - set(path), reverse=True)
            if not choices or len(path) >= max_depth:
                completed.append(path)
            else:
                pending.extend((*path, node) for node in choices[:max_paths])
        return min(completed or [initial], key=lambda p: (-len(p), p))

    upstream = tuple(reversed(walk(incoming, (anchor,))))
    # Keep the anchor even under a small limit; downstream cannot revisit it.
    return walk(outgoing, upstream)
