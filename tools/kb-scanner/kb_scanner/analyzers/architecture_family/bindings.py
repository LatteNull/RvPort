"""Bind existing proof terminals; never search for or synthesize a proof."""
from collections import defaultdict


def bind(catalog, facts, base, budget):
    members = defaultdict(list)
    for family in catalog["families"]:
        for member in family["members"]:
            members[member["fileId"]].append(member)
    if not members:
        return ()
    entities = {e.id: e for e in base.entities}
    files = {e.name: e.id for e in base.entities if e.kind == "source_file"}
    fact_index = {f.id: f for f in facts.facts}
    evidence = {e.id: e for e in facts.evidence}
    relations = {r.id: r for r in base.relations}
    issues, count, steps = set(), 0, 0
    for proof in sorted(base.proof_paths, key=lambda p: p.id):
        if not proof.relation_ids:
            continue
        terminal = relations.get(proof.relation_ids[-1])
        if terminal is None:
            issues.add("family-invalid-proof")
            continue
        fact = fact_index.get(terminal.metadata.get("factId"))
        file_id = terminal.target_id if terminal.target_id in members else None
        if fact is not None and fact.kind == "build_source":
            path = fact.metadata.get("cmake", {}).get("source", fact.canonical_value)
            file_id = files.get(str(path).removeprefix("./"))
        if file_id not in members or terminal.kind not in {"selects", "excludes", "alternative_to"}:
            continue
        if count >= budget.bindings or steps + len(proof.relation_ids) > budget.proof_steps:
            issues.add("family-binding-budget")
            break
        steps += len(proof.relation_ids)
        chain = [relations.get(rid) for rid in proof.relation_ids]
        configs = {str(r.metadata["configuration"]) for r in chain if r is not None and "configuration" in r.metadata}
        valid = proof.source_id in entities and proof.target_id in entities and len(configs) <= 1
        cursor = proof.source_id
        origins = {}
        for relation in chain:
            if relation is None or relation.source_id != cursor or relation.target_id not in entities or not relation.evidence_ids:
                valid = False
                break
            for eid in relation.evidence_ids:
                item = evidence.get(eid)
                if item is None or item.location is None:
                    valid = False
                    continue
                start, end = item.location.start, item.location.end
                origins[eid] = {"path": start.path, "startLine": start.line, "endLine": end.line}
            cursor = relation.target_id
        if not valid or cursor != proof.target_id:
            issues.add("family-invalid-proof")
            continue
        state = terminal.status if proof.status == "complete" and not proof.truncated and all(r.status in {"complete", "selected", "inactive", "not_selected"} for r in chain) else "unknown"
        state = state if state in {"selected", "inactive", "not_selected"} else "unknown"
        record = {"configuration": next(iter(configs), "default"), "selectionStatus": state,
                  "proofStatus": proof.status, "proofId": proof.id, "relationIds": list(proof.relation_ids),
                  "sources": [origins[k] for k in sorted(origins)], "kind": terminal.kind}
        for member in members[file_id]:
            member["bindings"].append(record)
        count += 1
    return tuple(sorted(issues))
