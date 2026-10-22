"""按文件、作用域、签名和配置分桶；缺失证据不等于缺少实现。"""
from collections import defaultdict
from dataclasses import dataclass

from ...core import stable_id
from .attributes import decode, semantic_rule


@dataclass(frozen=True)
class Budget:
    declarations: int = 20000
    groups: int = 10000
    versions: int = 64
    attribute_chars: int = 65536
    attribute_options: int = 128
    associations: int = 100000

    def __post_init__(self):
        if any(type(value) is not int or value < 0 for value in vars(self).values()):
            raise ValueError("multiversion budgets must be nonnegative integers")


def source(item):
    if item.location is None:
        return None
    start, end = item.location.start, item.location.end
    return {"path": start.path, "startLine": start.line, "startColumn": start.column,
            "endLine": end.line, "endColumn": end.column, "value": str(item.value), "kind": item.kind}


def discover(snapshot, budget, profiles=None):
    profiles = profiles or {}
    evidence = {item.id: item for item in snapshot.evidence}
    functions = sorted((f for f in snapshot.facts if f.kind == "function_declaration"), key=lambda f: f.id)
    owners = {eid: f.id for f in functions[:budget.declarations] for eid in f.evidence_ids}
    attrs = defaultdict(list)
    orphans = []
    for fact in snapshot.facts:
        if fact.kind != "declaration_attribute":
            continue
        decoded = decode(fact.canonical_value, budget.attribute_chars, budget.attribute_options)
        if decoded["mechanism"] == "unknown" and not any("functionInventory" in evidence[eid].metadata for eid in fact.evidence_ids):
            continue
        ids = fact.metadata.get("functionOwnerEvidenceIds", (fact.metadata.get("functionOwnerEvidenceId"),))
        found = {owners[eid] for eid in ids if eid in owners}
        if len(found) == 1:
            attrs[next(iter(found))].append((fact, decoded))
        else:
            orphans.append((fact, decoded))
    buckets = defaultdict(list)
    for fact in functions[:budget.declarations]:
        record = fact.metadata["function"]
        item = evidence[fact.evidence_ids[0]]
        configuration = fact.context_ids[0] if len(fact.context_ids) == 1 else "source-unconfigured"
        key = (item.location.start.path, record["signature"], record["linkage"], record["internal"], configuration)
        buckets[key].append((fact, record, attrs[fact.id]))
    groups, issues = [], set()
    discovery_truncated = len(functions) > budget.declarations
    for key, members in sorted(buckets.items()):
        if not any(attributes for _, _, attributes in members):
            continue
        if len(groups) >= budget.groups:
            issues.add("multiversion-budget-exceeded")
            continue
        groups.append(_group(key, members, evidence, budget, profiles.get(key[-1]), discovery_truncated))
    for fact, decoded in sorted(orphans, key=lambda pair: pair[0].id):
        if len(groups) >= budget.groups:
            issues.add("multiversion-budget-exceeded")
            continue
        item = evidence[fact.evidence_ids[0]]
        path = item.location.start.path if item.location else "<unknown>"
        key = (path, "<unbound>:" + fact.id, "unknown", False, fact.context_ids[0] if len(fact.context_ids) == 1 else "source-unconfigured")
        group = _group(key, (), evidence, budget, None, True)
        group.update(mechanism=decoded["mechanism"], attributeFactIds=[fact.id], evidenceIds=list(fact.evidence_ids),
                     sources=[s for eid in fact.evidence_ids if (s := source(evidence[eid])) is not None])
        groups.append(group)
    if discovery_truncated:
        issues.add("multiversion-budget-exceeded")
    _semantic_hints(groups, snapshot, evidence, budget.declarations)
    return {"version": 1, "groups": groups, "declarationCount": len(functions),
            "retainedDeclarationCount": min(len(functions), budget.declarations),
            "groupCount": sum(any(a for _, _, a in m) for m in buckets.values()) + len(orphans),
            "discoveryStatus": "partial" if issues else "complete", "reasonCodes": sorted(issues)}


def _semantic_hints(groups, snapshot, evidence, limit):
    index = defaultdict(list)
    for fact in sorted(snapshot.facts, key=lambda f: f.id):
        if fact.kind != "function_semantics":
            continue
        for eid in fact.evidence_ids:
            item = evidence[eid]
            if item.location is not None:
                index[item.location.start].append((fact.context_ids, fact.metadata["functionSemantics"]))
    retained = 0
    for group in groups:
        hints, keys = [], defaultdict(set)
        for declaration in group["declarations"]:
            for eid in declaration["evidenceIds"]:
                for contexts, record in index.get(evidence[eid].location.start, ()):
                    if len(contexts) != 1 or (group["configuration"] != "source-unconfigured" and contexts[0] != group["configuration"]):
                        continue
                    if retained >= limit:
                        group["reasonCodes"] = sorted(set(group["reasonCodes"]) | {"multiversion-budget-exceeded"})
                        group["groupCompleteness"], group["defaultGap"] = "unknown", False
                        continue
                    retained += 1
                    hints.append({"configuration": contexts[0], **record})
                    keys[contexts[0]].add(record.get("canonicalKey"))
        conflict = any(len(values) != 1 or None in values for values in keys.values())
        if conflict:
            group["reasonCodes"] = sorted(set(group["reasonCodes"]) | {"multiversion-semantic-binding-ambiguous"})
            group["groupCompleteness"], group["defaultGap"] = "unknown", False
        if group["groupCompleteness"] != "complete" and group["defaultPresence"] == "absent_in_scope":
            group["defaultPresence"] = "unknown"
        group["semanticBindings"] = hints


def _group(key, members, evidence, budget, profile, truncated):
    path, signature, linkage, internal, configuration = key
    reasons, versions, origins, fact_ids, evidence_ids, declarations = set(), [], {}, set(), set(), []
    mechanisms, returns = set(), set()
    for fact, record, attrs in sorted(members, key=lambda item: item[0].id):
        declarations.append({"factId": fact.id, "evidenceIds": fact.evidence_ids, "record": record})
        if not attrs:
            reasons.add("multiversion-unclassified-declaration")
        returns.add(record["returnType"])
        if record["bindingStatus"] != "complete" or record["conditional"] or record.get("producerConflict"):
            reasons.add("multiversion-binding-ambiguous")
        if record["inventoryTruncated"]:
            truncated = True
        for eid in fact.evidence_ids:
            if (description := source(evidence[eid])) is not None:
                origins[eid] = description
        for attr, decoded in attrs:
            fact_ids.add(attr.id)
            evidence_ids.update(attr.evidence_ids)
            mechanisms.add(decoded["mechanism"])
            if decoded["status"] != "complete":
                reasons.add(decoded["reason"])
            for eid in attr.evidence_ids:
                if (description := source(evidence[eid])) is not None:
                    origins[eid] = description
            for option in decoded["options"]:
                versions.append({"option": option, "functionFactId": fact.id, "attributeFactId": attr.id,
                                 "definition": "unknown" if record["bindingStatus"] != "complete" else "present" if record["bodyBytes"] is not None else "declaration_only",
                                 "conditional": record["conditional"], "bodySpan": record["bodySpan"], "path": path})
    if len(returns) > 1 or len(mechanisms) != 1:
        reasons.add("multiversion-binding-ambiguous")
    mechanism = next(iter(mechanisms)) if len(mechanisms) == 1 else "unknown"
    if mechanism == "target" and len({v["option"] for v in versions}) == 1:
        mechanism = "single_target"
    if len(versions) > budget.versions or truncated:
        reasons.add("multiversion-budget-exceeded")
    rule = semantic_rule(profile, mechanism)
    default = [v for v in versions if v["option"] == "default"]
    complete = not reasons
    presence = ("present" if default and not any(v["conditional"] for v in default) else
                "not_applicable" if complete and mechanism == "single_target" else
                "absent_in_scope" if complete and rule["status"] == "applicable" else "unknown")
    definition = ("present" if presence == "present" and any(v["definition"] == "present" for v in default) else
                  "declaration_only" if presence == "present" and all(v["definition"] == "declaration_only" for v in default) else "not_applicable" if presence == "not_applicable" else "unknown")
    if definition == "declaration_only":
        reasons.add("multiversion-default-declaration-only")
    if rule["status"] == "unknown" and mechanism != "single_target":
        reasons.add("multiversion-compiler-profile-unknown")
    gap = complete and presence == "absent_in_scope" and rule["requiresDefault"]
    if gap:
        reasons.add("multiversion-default-absent-in-scope")
    return {"id": stable_id("function_multiversion_group", 1, key), "path": path, "signature": signature,
            "configuration": configuration, "linkage": linkage, "internal": internal, "mechanism": mechanism,
            "groupCompleteness": "complete" if complete else "unknown", "defaultPresence": presence,
            "defaultDefinition": definition, "defaultGap": bool(gap), "semanticRule": rule,
            "targetApplicability": "unknown", "targetSelection": "unknown", "bodyDependency": "unknown",
            "versions": versions[:budget.versions], "versionCount": len(versions), "reasonCodes": sorted(reasons),
            "declarations": declarations, "attributeFactIds": sorted(fact_ids), "evidenceIds": sorted(evidence_ids),
            "sources": [origins[eid] for eid in sorted(origins)], "dependencies": [], "bindings": []}
