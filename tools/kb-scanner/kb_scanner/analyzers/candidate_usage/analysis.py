"""在既有分析之后追加用途图，不删除事实或替换执行证明。"""
from dataclasses import replace
from ...core import AnalysisSnapshot, Entity, StageResult, stable_id, normalize_project_path
from ...frontends.cpp.compilation_database import compilation_context_id
from .demand import CandidateUsageDemand
from .session import UsageSession
from .proofs import materialize
from .conflicts import ExecutionConflictIndex


CATALOG_KIND = "candidate_usage_catalog"


class CandidateUsageAnalyzer:
    def __init__(self, demand=None, scan_budget=None, query_budget=None):
        self.demand = demand or CandidateUsageDemand()
        self.scan_budget, self.query_budget = scan_budget, query_budget

    def analyze(self, context, facts, knowledge, base):
        roots = self.demand.select(facts, knowledge)
        if not roots:
            return StageResult(base)
        configured = {}
        subjects = {entity.name: entity.id for entity in facts.entities if entity.kind == "source_file"}
        for unit in context.compile_contexts:
            try:
                path = normalize_project_path(unit.path, context.input_root)
            except ValueError:
                continue
            if path in subjects:
                configured.setdefault(subjects[path], set()).add(compilation_context_id(unit, context.input_root))
        # 默认 Tree-sitter inventory 不证明编译数据库中的任一具体配置。
        roots = tuple(replace(root, configuration_complete=False)
            if root.subject_id in configured and root.configuration not in configured[root.subject_id]
            else root for root in roots)
        session = UsageSession(facts, roots, self.scan_budget, self.query_budget)
        scope_facts = {fact.id: fact for fact in facts.facts if fact.kind == "usage_scope"}
        conflicts = ExecutionConflictIndex(facts, knowledge, roots)
        entities = {entity.id: entity for entity in (*facts.entities, *base.entities)}
        relations = {relation.id: relation for relation in base.relations}
        proofs = {proof.id: proof for proof in base.proof_paths}
        entries = []
        for root in sorted(roots):
            resolution = session.resolve(root)
            resolution = conflicts.annotate(root, resolution, session, scope_facts)
            extra_entities, extra_relations, extra_proofs, summary = materialize(root, resolution, session, scope_facts)
            entities.update((entity.id, entity) for entity in extra_entities)
            relations.update((relation.id, relation) for relation in extra_relations)
            proofs.update((proof.id, proof) for proof in extra_proofs)
            entries.append(summary)
        catalog = Entity(stable_id(CATALOG_KIND, 1), CATALOG_KIND, "候选用途审计", properties={
            "version": 1, "entries": tuple(entries), "rootCount": len(roots),
            "scopeIndexes": len(session.indexes), "recordCount": session.record_count,
            "visits": session.visits, "cacheHits": session.cache_hits})
        entities[catalog.id] = catalog
        # unknown 是用途结果，不将项目静态解析状态伪装为 failed 或迁移 ready。
        return StageResult(AnalysisSnapshot(tuple(sorted(relations.values(), key=lambda value: value.id)),
            tuple(sorted(entities.values(), key=lambda value: value.id)), tuple(sorted(proofs.values(), key=lambda value: value.id))))
