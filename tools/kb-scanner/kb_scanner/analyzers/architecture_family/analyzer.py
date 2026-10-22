"""Non-executing family relations and catalog, downstream of existing proofs."""
from ...core import AnalysisSnapshot, CompletionStatus, Diagnostic, DiagnosticSeverity, Entity, Relation, StageResult, stable_id
from .grouping import FamilyBudget, discover
from .bindings import bind

CATALOG_KIND = "architecture_family_catalog"


class ArchitectureFamilyAnalyzer:
    def __init__(self, budget=None):
        self.budget = budget or FamilyBudget()

    def analyze(self, context, facts, knowledge, base):
        catalog = discover(facts.entities, self.budget)
        issues = set(catalog["reasonCodes"])
        issues.update(bind(catalog, facts, base, self.budget))
        if not catalog["families"] and not issues:
            return StageResult(base)
        entities = {e.id: e for e in base.entities}
        relations = list(base.relations)
        added = 0
        for family in catalog["families"]:
            entity = Entity(family["id"], "architecture_family", family["template"])
            entities[entity.id] = entity
            for member in family["members"]:
                if member["fileId"] not in entities:
                    issues.add("family-member-unavailable")
                    continue
                if added >= self.budget.relations:
                    issues.add("family-relation-budget")
                    continue
                relations.append(Relation(stable_id("candidate-member", member["fileId"], entity.id),
                    "candidate_member_of", member["fileId"], entity.id,
                    metadata={"semanticRole": "candidate", "path": member["path"], "rule": member["rule"]}))
                added += 1
        catalog["reasonCodes"] = sorted(issues)
        catalog["discoveryStatus"] = "partial" if issues else "complete"
        root = Entity(stable_id(CATALOG_KIND, 1), CATALOG_KIND, "授权路径的架构候选目录", properties=catalog)
        entities[root.id] = root
        diagnostics = tuple(Diagnostic(reason, "analysis.architecture-family", DiagnosticSeverity.WARNING,
            "架构家族分析不完整；保留原有事实与结论。", producer="architecture-family",
            details={"reason": reason, "message_en": "Architecture family analysis is incomplete; existing facts and conclusions are preserved."}) for reason in sorted(issues))
        return StageResult(AnalysisSnapshot(tuple(sorted(relations, key=lambda r: r.id)),
            tuple(sorted(entities.values(), key=lambda e: e.id)), base.proof_paths),
            CompletionStatus.PARTIAL if issues else CompletionStatus.COMPLETE, diagnostics)
