"""在当前解析有效期内，以正式事实选择用途采集锚点。"""
from ..core import CompletionStatus, FrontendSnapshot
from ..normalization import CppEvidenceNormalizer
from ..analyzers.candidate_usage.demand import CandidateUsageDemand


class UsageAnchorSelector:
    """仅处理标量 Evidence；不保存语法树，也不输出预归一化事实。"""

    def __init__(self, context, knowledge, *, normalizer=None, demand=None):
        self.context, self.knowledge = context, knowledge
        self.normalizer = normalizer or CppEvidenceNormalizer()
        self.demand = demand or CandidateUsageDemand()
        self.prepared = self.demand.prepare(knowledge)
        self.test_values = frozenset(entry.canonical_value for entry in knowledge.entries)

    def test_anchors(self, evidence, usage_anchors):
        """仅选择采集需求，不以索引命中代替正式知识/用途判断。"""
        ids = {item.id for item in usage_anchors}
        return tuple(item for item in evidence if item.id in ids or item.kind == "inline_asm"
                     or item.kind in {"call_expression", "macro_argument_token", "macro_expansion", "type_reference"}
                     and item.value in self.test_values)

    def select(self, entity, evidence):
        # 这是采集需求（允许保守多选），不是最终 fact 或排除证明。
        # 同 kind/value 的匹配结果相同；保留声明以满足正式引用校验，
        # 引用只预归一化一个代表，选中后展开全部原始 occurrence。
        declarations = {"enum_declaration", "enum_member_declaration", "macro_definition", "function_declaration"}
        inputs = declarations | {"enum_member_reference", "macro_expansion", "preprocessor_condition", "preprocessor_branch"}
        seen, representatives = set(), []
        for item in evidence:
            if item.kind not in inputs:
                continue
            key = item.kind, item.value
            if item.kind in declarations or key not in seen:
                representatives.append(item)
                seen.add(key)
        result = self.normalizer.normalize(self.context, FrontendSnapshot((entity,), tuple(representatives)))
        if result.value is None or result.status in {CompletionStatus.FAILED, CompletionStatus.UNAVAILABLE}:
            return ()
        roots = self.demand.select(result.value, self.knowledge, prepared=self.prepared)
        identifiers = {identifier for root in roots for identifier in root.matched_evidence_ids}
        selected = {(item.kind, item.value) for item in representatives if item.id in identifiers}
        return tuple(item for item in evidence if (item.kind, item.value) in selected)
