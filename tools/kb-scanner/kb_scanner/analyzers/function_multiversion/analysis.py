"""函数版本结构位于既有 source/build proof 之后，成员边不参与执行证明。"""
from ...core import AnalysisSnapshot, CompletionStatus, Diagnostic, DiagnosticSeverity, Entity, Relation, StageResult, stable_id
from .grouping import Budget, discover
from .bindings import associate

CATALOG_KIND = "function_multiversion_catalog"


class FunctionMultiversionAnalyzer:
    def __init__(self, budget=None, profiles=None):
        self.budget = budget or Budget()
        # Optional trusted, already collected metadata; never infer a compiler version.
        self.profiles = dict(profiles or {})

    def analyze(self, context, facts, knowledge, base):
        catalog = discover(facts, self.budget, self.profiles)
        if not catalog["groups"] and not catalog["reasonCodes"]:
            return StageResult(base)
        links, binding_issues = associate(catalog, facts, base, self.budget)
        issues = set(catalog["reasonCodes"]) | binding_issues
        entities = {e.id: e for e in base.entities}
        relations = {r.id: r for r in base.relations}
        def node(eid):
            identifier = stable_id("function_source_node", eid)
            entities[identifier] = Entity(identifier, "function_source", "真实函数源码", properties={"sourceEvidenceId": eid})
            return identifier
        for group in catalog["groups"]:
            entities[group["id"]] = Entity(group["id"], "function_version_group", group["signature"])
            for declaration in group["declarations"]:
                eid = declaration["evidenceIds"][0]
                nid = node(eid)
                rid = stable_id("function_version_member", nid, group["id"])
                relations[rid] = Relation(rid, "function_version_member", nid, group["id"], evidence_ids=(eid,),
                    metadata={"semanticRole": "non_executing_membership", "configuration": group["configuration"]})
        owners = {e.id: e.metadata.get("functionOwnerEvidenceId") for e in facts.evidence}
        for group in catalog["groups"]:
            for eid in group["evidenceIds"]:
                owner = owners.get(eid)
                if owner is not None:
                    rid = stable_id("function_attribute_owner", eid, owner, group["configuration"])
                    relations[rid] = Relation(rid, "function_attribute_owner", node(eid), node(owner), evidence_ids=(eid, owner), status="complete",
                        metadata={"semanticRole": "source_provenance", "configuration": group["configuration"]})
        for owner, dependency, configuration in links:
            rid = stable_id("function_body_contains", owner, dependency, configuration)
            relations[rid] = Relation(rid, "function_body_contains", node(owner), node(dependency), evidence_ids=(owner, dependency), status="complete",
                metadata={"semanticRole": "source_provenance", "configuration": configuration})
        catalog["reasonCodes"] = sorted(issues)
        catalog["discoveryStatus"] = "partial" if issues else "complete"
        root = Entity(stable_id(CATALOG_KIND, 1), CATALOG_KIND, "函数版本组", properties=catalog)
        entities[root.id] = root
        diagnostics = tuple(Diagnostic(reason, "analysis.function-multiversion", DiagnosticSeverity.WARNING,
            "函数版本分析存在未闭合证据，保留原始事实。", producer="function-multiversion",
            details={"message_en": "Function version analysis has incomplete evidence; original facts are retained."}) for reason in sorted(issues))
        return StageResult(AnalysisSnapshot(tuple(sorted(relations.values(), key=lambda r: r.id)),
            tuple(sorted(entities.values(), key=lambda e: e.id)), base.proof_paths),
            CompletionStatus.PARTIAL if issues else CompletionStatus.COMPLETE, diagnostics)
