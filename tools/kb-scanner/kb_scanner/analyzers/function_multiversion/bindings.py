"""按源码范围关联既有事实和 proof；不构造运行时选择证明。"""
from bisect import bisect_right
from collections import defaultdict

from .grouping import source


def associate(catalog, snapshot, base, budget):
    evidence = {e.id: e for e in snapshot.evidence}
    intervals, attributes = defaultdict(list), defaultdict(list)
    for group in catalog["groups"]:
        for fact_id in group["attributeFactIds"]:
            attributes[fact_id].append(group)
        for declaration in group["declarations"]:
            record = declaration["record"]
            span = record["bodySpan"]
            if span is not None:
                intervals[(group["path"], group["configuration"])].append((tuple(span[:2]), tuple(span[2:]), declaration, group))
    starts = {}
    for key, values in intervals.items():
        values.sort(key=lambda value: (value[0], value[1], value[2]["factId"]))
        starts[key] = [v[0] for v in values]
    count, links, issues, bound = 0, [], set(), defaultdict(list)
    for fact in sorted(snapshot.facts, key=lambda item: item.id):
        if fact.kind in {"function_declaration", "function_semantics"}:
            continue
        configuration = fact.context_ids[0] if len(fact.context_ids) == 1 else "source-unconfigured"
        for eid in fact.evidence_ids:
            item = evidence[eid]
            if item.location is None:
                continue
            start, end = item.location.start, item.location.end
            key = (start.path, configuration)
            index = bisect_right(starts.get(key, ()), (start.line, start.column)) - 1
            if index < 0:
                continue
            lower, upper, declaration, group = intervals[key][index]
            record = declaration["record"]
            if (end.line, end.column) > upper or any(tuple(span[:2]) <= (start.line, start.column) < tuple(span[2:]) for span in record["nestedSpans"]):
                continue
            if count >= budget.associations:
                issues.add("multiversion-association-budget-exceeded")
                break
            count += 1
            dependency = {"factId": fact.id, "evidenceId": eid, "functionFactId": declaration["factId"],
                          "kind": fact.kind, "source": source(item), "status": "unresolved"}
            group["dependencies"].append(dependency)
            bound[fact.id].append(group)
            links.append((declaration["evidenceIds"][0], eid, configuration))
        if issues:
            break
    # Exact fact endpoints only. A selected file is not a selected runtime clone.
    relations = {r.id: r for r in base.relations}
    entities = {e.id for e in base.entities}
    for proof in sorted(base.proof_paths, key=lambda item: item.id):
        if not proof.relation_ids:
            continue
        terminal = relations.get(proof.relation_ids[-1])
        if terminal is None:
            continue
        fid = terminal.metadata.get("factId")
        groups = {g["id"]: g for g in (*attributes.get(fid, ()), *bound.get(fid, ()))}
        if not groups:
            continue
        if count + len(proof.relation_ids) > budget.associations:
            issues.add("multiversion-association-budget-exceeded")
            break
        count += len(proof.relation_ids)
        cursor, origins, configurations = proof.source_id, {}, set()
        valid = cursor in entities
        chain = []
        for rid in proof.relation_ids:
            relation = relations.get(rid)
            if relation is None or relation.source_id != cursor or relation.target_id not in entities or not relation.evidence_ids:
                valid = False
                break
            chain.append(relation)
            configuration = relation.metadata.get("configuration", "source-unconfigured")
            configurations.add(configuration)
            for eid in relation.evidence_ids:
                item = evidence.get(eid)
                if item is None or item.location is None:
                    valid = False
                else:
                    origins[eid] = source(item)
            cursor = relation.target_id
        if not valid or cursor != proof.target_id or len(configurations) != 1:
            issues.add("multiversion-existing-proof-invalid")
            continue
        configuration = next(iter(configurations))
        complete = proof.status == "complete" and not proof.truncated and all(r.status in {"complete", "selected", "inactive", "not_selected"} for r in chain)
        for group in groups.values():
            if configuration != group["configuration"]:
                continue
            group["bindings"].append({"factId": fid, "configuration": configuration,
                "selectionStatus": terminal.status if complete and terminal.status in {"selected", "inactive", "not_selected"} else "unknown",
                "scope": "source_occurrence", "runtimeVersionSelection": "unknown",
                "proofId": proof.id, "relationIds": list(proof.relation_ids), "sources": list(origins.values())})
    if issues:
        for group in catalog["groups"]:
            group["reasonCodes"] = sorted(set(group["reasonCodes"]) | issues)
            group["defaultGap"] = False
            if group["defaultPresence"] == "absent_in_scope":
                group["defaultPresence"] = "unknown"
    catalog["associationCount"] = count
    return links, issues
