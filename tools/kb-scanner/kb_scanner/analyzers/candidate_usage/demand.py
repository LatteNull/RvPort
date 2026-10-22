"""复用 Detector 匹配入口和精确 occurrence 身份，不依赖最终 Finding。"""
from dataclasses import dataclass, replace

from ...detectors.candidate_coverage import covered_identifier_candidate
from ...detectors.definitions import DEFAULT_DEFINITIONS
from ...detectors.matchers import KnowledgeIndex, match_fact


CANDIDATES = frozenset({"architecture_identifier_candidate", "architecture_enum_candidate"})


@dataclass(frozen=True, order=True)
class UsageRoot:
    fact_id: str
    subject_id: str
    configuration: str
    matched_evidence_ids: tuple[str, ...]
    configuration_complete: bool


class CandidateUsageDemand:
    def __init__(self, definitions=DEFAULT_DEFINITIONS):
        self.definitions = tuple(definitions.values())
        self.kinds = {definition.input_kind for definition in self.definitions
                      if definition.observation_kind in CANDIDATES}
        self.by_kind = {kind: tuple(item for item in self.definitions if item.input_kind == kind)
                        for kind in self.kinds}

    def select(self, facts, knowledge, *, prepared=None):
        index, entries = prepared if prepared is not None else self.prepare(knowledge)
        referenced = {eid for fact in facts.facts if fact.kind == "enum_reference"
            for eid in fact.metadata.get("enumMemberDeclarationEvidenceIds", ())
            if isinstance(eid, str)}
        roots = set()
        matched_values = {}
        for fact in facts.facts:
            if fact.kind not in self.kinds or fact.kind == "enum_member" and referenced.intersection(fact.evidence_ids):
                continue
            # match_fact 仅依赖 kind/canonical_value 和本次知识索引；身份仍逐 fact 构造。
            value_key = fact.kind, fact.canonical_value
            if value_key not in matched_values:
                matched_values[value_key] = [(definition, match_fact(definition, fact, index))
                    for definition in self.by_kind[fact.kind]]
            matches = matched_values[value_key]
            for definition, match in matches:
                if match is None or match.status != "candidate" or definition.observation_kind not in CANDIDATES:
                    continue
                if (definition.observation_kind == "architecture_identifier_candidate"
                        and covered_identifier_candidate(fact, matches, entries)):
                    continue
                configuration = fact.metadata.get("compilationContextId") or fact.metadata.get("configuration", "default")
                # 与 Detector 身份完全一致；多配置不能按默认配置宣称闭合。
                valid = isinstance(configuration, str) and bool(configuration)
                valid = valid and (not fact.context_ids or fact.context_ids == (configuration,))
                roots.add(UsageRoot(fact.id, fact.subject_id,
                    configuration if isinstance(configuration, str) else "",
                    tuple(fact.evidence_ids), valid))
        return tuple(sorted(roots))

    def prepare(self, knowledge):
        """扫描内复用只读知识索引，不把另一次扫描的知识缓存进全局。"""
        kinds = {kind for definitions in self.by_kind.values() for definition in definitions
                 for kind in definition.knowledge_kinds}
        # 包含同输入类型的全部 matcher，保留 confirmed 覆盖检查，不硬编码知识种类。
        relevant = tuple(entry for entry in knowledge.entries if entry.fact_kind in kinds)
        return KnowledgeIndex(replace(knowledge, entries=relevant)), {entry.id: entry for entry in relevant}
