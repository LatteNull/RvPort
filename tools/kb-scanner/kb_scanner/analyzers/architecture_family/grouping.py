"""Linear bucket discovery followed by deterministic bounded materialization."""
from collections import defaultdict
from dataclasses import dataclass

from ...core import stable_id
from .paths import VERSION, candidates


@dataclass(frozen=True)
class FamilyBudget:
    paths: int = 100000
    families: int = 10000
    members: int = 128
    bindings: int = 4096
    proof_steps: int = 10000
    relations: int = 10000

    def __post_init__(self):
        if any(v < 0 for v in vars(self).values()):
            raise ValueError("family budgets must be nonnegative")


def discover(entities, budget):
    sources = sorted((e for e in entities if e.kind == "source_file" and "pathObservation" in e.properties), key=lambda e: (e.name, e.id))
    buckets, folded = defaultdict(list), defaultdict(set)
    reasons = set()
    if len(sources) > budget.paths:
        reasons.add("family-path-budget")
    operations = 0
    for entity in sources[:budget.paths]:
        folded[entity.name.casefold()].add(entity.name)
        for candidate in candidates(entity.name):
            buckets[candidate.key].append((candidate, entity))
            operations += 1
    keys = sorted(key for key, values in buckets.items() if any(c.role == "x86" for c, _ in values))
    if len(keys) > budget.families:
        reasons.add("family-count-budget")
    families = []
    for key in keys[:budget.families]:
        values = buckets[key]
        member_reasons = ("family-member-budget",) if len(values) > budget.members else ()
        reasons.update(member_reasons)
        members = []
        for candidate, entity in values[:budget.members]:
            ambiguous = candidate.ambiguous or len(folded[entity.name.casefold()]) > 1
            members.append({"fileId": entity.id, "path": candidate.path, "roleHint": candidate.role,
                "candidateStatus": "ambiguous" if ambiguous else "unknown", "token": candidate.token,
                "rule": candidate.rule, "observation": dict(entity.properties["pathObservation"]), "bindings": []})
        families.append({"id": stable_id("architecture-family", VERSION, key), "template": key,
            "status": "ambiguous" if any(m["candidateStatus"] == "ambiguous" for m in members) else "unknown",
            "memberCount": len(values), "members": members, "reasonCodes": list(member_reasons),
            "alternativeStatus": "unknown", "candidateAbsence": "no-candidate-observed-in-scope" if len(values) == 1 else None})
    return {"version": VERSION, "scope": "authorized-file-list", "discoveryStatus": "partial" if reasons else "complete",
            "pathCount": len(sources), "pathsProcessed": min(len(sources), budget.paths), "familyCount": len(keys),
            "bucketOperations": operations, "reasonCodes": sorted(reasons), "families": families}
