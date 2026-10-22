"""Conservative query planning; never substitutes for bounded path search."""
from collections import defaultdict


def _reachable(starts, adjacency, depth):
    seen = set(starts)
    frontier = set(seen)
    for _ in range(depth):
        following = {target for node in frontier for target in adjacency.get(node, ())} - seen
        seen.update(following)
        frontier = following
        if not frontier:
            break
    return seen


def plan_queries(source_ids, target_ids, relations, max_depth, required_evidence_ids=None):
    if max_depth < 1:
        raise ValueError("path depth must be positive")
    sources, targets = set(source_ids), set(target_ids)
    incoming, outgoing = defaultdict(set), defaultdict(set)
    requested_ends = set()
    for relation in relations:
        incoming[relation.target_id].add(relation.source_id)
        outgoing[relation.source_id].add(relation.target_id)
        if required_evidence_ids is not None and any(e in required_evidence_ids for e in relation.evidence_ids):
            requested_ends.add(relation.target_id)
    if required_evidence_ids is not None:
        # A requested edge may be in the MIDDLE of a proof, not its endpoint.
        targets.intersection_update(_reachable(requested_ends, outgoing, max_depth - 1))
    result = defaultdict(set)
    for target in sorted(targets):
        for source in _reachable((target,), incoming, max_depth) & sources:
            result[source].add(target)
    return {source: tuple(sorted(values)) for source, values in sorted(result.items())}
