"""复用局部 Detector 的确认事实，合并同根因属性候选而非删除扫描事实。"""
from dataclasses import replace
from collections import defaultdict

from ..core import DetectionSnapshot, Observation, StageResult, stable_id
from ..analyzers.function_multiversion.analysis import CATALOG_KIND
from ..classifiers.risk import confirmed_dependency


class FunctionMultiversionDetector:
    def detect(self, context, facts, analysis, knowledge, base):
        groups = [g for entity in analysis.entities if entity.kind == CATALOG_KIND for g in entity.properties["groups"]]
        if not groups:
            return StageResult(base)
        guards = defaultdict(list)
        entities = {e.id: e for e in analysis.entities}
        branch_roles = defaultdict(set)
        for relation in analysis.relations:
            if relation.kind == "guarded_by" and relation.status == "complete" and relation.source_id in entities:
                branch_roles[relation.target_id].add(entities[relation.source_id].properties.get("role", "unknown"))
        for relation in analysis.relations:
            if relation.kind == "guarded_by" and relation.status == "complete" and relation.source_id in entities and relation.target_id in entities:
                role = "x86" if branch_roles[relation.target_id] - {"unknown"} == {"x86"} else "unknown"
                for eid in relation.evidence_ids:
                    guards[eid].append((relation, role))
        evidence_by_fact = {f.id: f.evidence_ids for f in facts.facts}
        by_fact = {}
        for group in groups:
            for fid in (*group["attributeFactIds"], *(d["factId"] for d in group["dependencies"])):
                by_fact.setdefault(fid, []).append(group)
        result, merged = [], {}
        for observation in base.observations:
            relevant = by_fact.get(observation.metadata.get("factId"), ())
            if not relevant:
                result.append(observation)
                continue
            group_ids = tuple(sorted({g["id"] for g in relevant}))
            # Confirmed feature facts are never swallowed by a group observation.
            if observation.kind == "target_attribute_candidate" and all(g["mechanism"] not in {"single_target", "target_version"} for g in relevant):
                for gid in group_ids:
                    merged.setdefault(gid, []).append(observation)
                continue
            result.append(replace(observation, metadata={**observation.metadata, "functionMultiversionGroups": group_ids,
                "functionBodyDependency": "confirmed_x86" if confirmed_dependency(observation) else "unknown"}))
        for group in groups:
            if group["mechanism"] in {"single_target", "target_version"}:
                continue
            if not group["defaultGap"] and not group["reasonCodes"]:
                continue
            selection = _selection(group, guards, evidence_by_fact)
            if selection["foreign"]:
                continue
            provenance = merged.get(group["id"], ())
            kind = "function_multiversion_fallback_gap" if group["defaultGap"] else "function_multiversion_unknown"
            reason = "multiversion-default-absent-in-scope" if group["defaultGap"] else next(iter(group["reasonCodes"]), "multiversion-binding-ambiguous")
            result.append(Observation(stable_id(kind, group["id"]), "function-multiversion", kind,
                evidence_ids=tuple(group["evidenceIds"]), relation_ids=selection["relations"],
                confidence="medium", status="confirmed_local" if group["defaultGap"] else "unknown",
                metadata={"rootCauseId": group["id"], "configuration": group["configuration"],
                    "functionMultiversionGroups": (group["id"],), "matchedEvidenceIds": tuple(group["evidenceIds"]),
                    "mergedObservationIds": tuple(sorted(o.id for o in provenance)),
                    "mergedProvenance": tuple({"observationId": o.id, "evidenceIds": o.evidence_ids,
                        "relationIds": o.relation_ids, "knowledgeIds": o.knowledge_ids, "metadata": o.metadata} for o in provenance),
                    "proofPathIds": selection["proofs"],
                    "functionMultiversion": {"reason": reason, "defaultGap": group["defaultGap"],
                        "sourceExcluded": selection["excluded"],
                        "groupCompleteness": group["groupCompleteness"], "ruleStatus": group["semanticRule"]["status"]}}))
        return StageResult(DetectionSnapshot(tuple(sorted(result, key=lambda o: o.id))))


def _selection(group, guards, evidence_by_fact):
    """只有每个属性 occurrence 均闭合排除，才允许整组 inactive。"""
    excluded, foreign, relations, proofs = set(), set(), set(), set()
    for fid in group["attributeFactIds"]:
        excluded_occurrences, foreign_occurrences = set(), set()
        for eid in evidence_by_fact[fid]:
            for guard, role in guards.get(eid, ()):
                configuration = guard.metadata.get("configuration", "source-unconfigured")
                if configuration != group["configuration"]:
                    continue
                disposition = guard.metadata.get("architectureDisposition")
                if disposition == "foreign":
                    foreign_occurrences.add(eid)
                if disposition == "foreign" or role == "x86":
                    excluded_occurrences.add(eid)
                    relations.add(guard.id)
        if set(evidence_by_fact[fid]) <= excluded_occurrences:
            excluded.add(fid)
        if set(evidence_by_fact[fid]) <= foreign_occurrences:
            foreign.add(fid)
        bindings = [b for b in group["bindings"] if b["factId"] == fid]
        if bindings and all(b["selectionStatus"] in {"inactive", "not_selected"} for b in bindings):
            excluded.add(fid)
            for binding in bindings:
                relations.update(binding["relationIds"])
                proofs.add(binding["proofId"])
    required = set(group["attributeFactIds"])
    bounded = not any("budget-exceeded" in reason for reason in group["reasonCodes"])
    complete = bounded and bool(required) and required <= excluded
    return {"excluded": complete, "foreign": bool(required) and required <= foreign,
            "relations": tuple(sorted(relations)) if complete else (),
            "proofs": tuple(sorted(proofs)) if complete else ()}
