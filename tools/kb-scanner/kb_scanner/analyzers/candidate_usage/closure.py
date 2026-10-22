"""有界查询全使用、值流与控制后果，截断或未知均不构成排除。"""
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryBudget:
    depth: int = 32
    nodes: int = 4096
    edges: int = 8192

    def __post_init__(self):
        if any(type(value) is not int or value < 0 for value in vars(self).values()):
            raise ValueError("usage query budgets must be nonnegative integers")
        if self.depth > 32 or self.nodes > 4096 or self.edges > 8192:
            raise ValueError("usage query budgets exceed hard limits")


def query(index, roots, budget=None):
    budget = budget or QueryBudget()
    reasons = set(index.scope["reasonCodes"])
    if index.scope["status"] != "complete":
        reasons.add("usage-scope-incomplete")
    if not roots or any(root not in index.edges for root in roots):
        reasons.add("usage-root-unresolved")
    queue = deque((root, 0) for root in sorted(set(roots)) if root in index.edges)
    queued = {root for root, _ in queue}
    visited, links, depth_seen = set(), set(), 0
    while queue:
        key, depth = queue.popleft()
        if depth > budget.depth or len(visited) >= budget.nodes:
            reasons.add("usage-query-budget")
            break
        visited.add(key)
        depth_seen = max(depth_seen, depth)
        reasons.update(index.reasons[key])
        for other, link in index.adjacency[key]:
            if link not in links and len(links) >= budget.edges:
                reasons.add("usage-query-budget")
                queue.clear()
                break
            links.add(link)
            if other not in queued:
                queued.add(other)
                queue.append((other, depth+1))
    uses = tuple(sorted(key for key in visited if index.rows[key]["kind"] == "identifier"))
    if not uses:
        reasons.add("usage-no-resolved-uses")
    elif not any(index.rows[key].get("binding", {}).get("role") != "declaration" for key in uses):
        reasons.add("usage-no-observed-use")
    return {"status": "complete" if not reasons else "unknown", "reasonCodes": tuple(sorted(reasons)),
        "recordKeys": tuple(sorted(visited)), "links": tuple(sorted(links)), "useKeys": uses,
        "visited": len(visited), "edgeCount": len(links), "maxDepth": depth_seen,
        "truncated": "usage-query-budget" in reasons}
