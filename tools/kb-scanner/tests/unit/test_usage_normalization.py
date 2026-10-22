"""纯 DTO 的用途规范化合同；不加载真实 parser。"""
from dataclasses import replace
from pathlib import Path
import unittest

from kb_scanner.core import SourceLocation, SourceSpan, stable_id, FrontendSnapshot, Entity, CompletionStatus
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from kb_scanner.normalization.usage import validate_usage, merge_usage
from tests.unit.test_usage_inventory import fixture
from kb_scanner.frontends.cpp.usage_inventory import collect
from tests.unit.knowledge_detection.support import make_context


def sample():
    data = fixture()
    return collect(*data[:3], data[3].subject_id, "fake", (data[3],))[0]


def changed(item, **updates):
    return replace(item, metadata={**item.metadata, "usageScope": {**item.metadata["usageScope"], **updates}})


class UsageNormalizationTests(unittest.TestCase):
    def test_valid_complete_and_partial(self):
        item = sample()
        self.assertEqual((), validate_usage(item))
        self.assertEqual((), validate_usage(changed(item, records=(), recordCount=0,
            status="partial", reasonCodes=("usage-scope-budget",))))
        self.assertEqual(({}, False), merge_usage((), {}))
        metadata, conflict = merge_usage((item,), {})
        self.assertFalse(conflict)
        self.assertEqual(item.id, metadata["usageProvenance"][0]["evidenceId"])

    def test_summary_and_missing_scope(self):
        item = sample()
        for broken in (replace(item, metadata={}), replace(item, location=None)):
            self.assertEqual(("usage-invalid-scope",), validate_usage(broken))
        for updates in ({"version": True}, {"version": 2}, {"status": "bad"},
                        {"records": None}, {"recordCount": True}, {"recordCount": 1},
                        {"scopeLimit": 10001}, {"reasonCodes": "bad"}, {"reasonCodes": (1,)}):
            with self.subTest(updates=updates):
                self.assertEqual(("usage-invalid-summary",), validate_usage(changed(item, **updates)))
        for updates in ({"reasonCodes": ("bad",)}, {"records": (), "recordCount": 0}):
            self.assertEqual(("usage-inconsistent-completion",), validate_usage(changed(item, **updates)))

    def test_record_validation(self):
        item = sample()
        rows = list(item.metadata["usageScope"]["records"])
        for updates in ({"key": ()}, {"key": (True, 1, "x")}, {"span": (1, 0, 1, 2)},
                        {"kind": "bad"}, {"fields": []}, {"children": None},
                        {"text": 1}, {"operator": None}):
            candidate = [{**rows[0], **updates}, *rows[1:]]
            self.assertEqual(("usage-invalid-record",), validate_usage(changed(item, records=tuple(candidate))))
        candidate = [{**rows[0], "span": (1, 1, 2, 1)}, *rows[1:]]
        self.assertEqual(("usage-invalid-span",), validate_usage(changed(item, records=tuple(candidate))))
        no_columns = replace(item, location=SourceSpan(SourceLocation("a.cpp", 1), SourceLocation("a.cpp", 1)))
        self.assertEqual(("usage-invalid-span",), validate_usage(no_columns))
        self.assertEqual(("usage-duplicate-record",), validate_usage(changed(item, records=tuple(rows+[rows[-1]]), recordCount=6)))

    def test_references_and_partial_endpoint(self):
        item = sample()
        rows = [dict(row) for row in item.metadata["usageScope"]["records"]]
        for index, field, value, code in (
            (0, "parent", rows[1]["key"], "usage-invalid-owner"),
            (1, "parent", None, "usage-invalid-parent"),
            (1, "parent", (0, 1, "absent"), "usage-invalid-parent"),
            (0, "children", ((0, 99, "bad"),), "usage-invalid-endpoint"),
            (0, "children", ((),), "usage-invalid-endpoint"),
            (0, "fields", {"absent": (1, 2, "missing")}, "usage-dangling-endpoint"),
            (0, "fields", {"wrong": rows[-1]["key"]}, "usage-conflicting-parent"),
        ):
            candidate = [dict(row) for row in rows]
            candidate[index][field] = value
            self.assertEqual((code,), validate_usage(changed(item, records=tuple(candidate))))
        partial = changed(item, records=tuple(rows[:-1]), recordCount=4,
            status="partial", reasonCodes=("usage-scope-budget",))
        self.assertEqual((), validate_usage(partial))

    def test_producer_and_configuration_conflicts_preserve_provenance(self):
        item = sample()
        other = replace(item, id=stable_id("other"), producer="clang")
        self.assertFalse(merge_usage((item, other), {})[1])
        for different in (changed(other, status="partial", reasonCodes=("usage-partial-parse",)),
                          replace(other, metadata={**other.metadata, "compilationContextId": stable_id("config")})):
            merged, conflict = merge_usage((item, different), {})
            self.assertTrue(conflict)
            self.assertEqual("partial", merged["usageScope"]["status"])
            self.assertEqual(2, len(merged["usageProvenance"]))
            self.assertEqual((merged, conflict), merge_usage((different, item), {}))

    def test_normalizer_appends_without_changing_original_fact(self):
        data = fixture()
        # type_reference 不要求枚举定义引用，隔离测试仅关注归一化追加合同。
        original = replace(data[3], kind="type_reference")
        entity = Entity(original.subject_id, "source_file", "a.cpp")
        context = make_context(Path("/tmp"))
        normalizer = CppEvidenceNormalizer()
        baseline = normalizer.normalize(context, FrontendSnapshot((entity,), (original,)))
        item = sample()
        result = normalizer.normalize(context, FrontendSnapshot((entity,), (original, item)))
        self.assertEqual(CompletionStatus.COMPLETE, result.status)
        self.assertIn(baseline.value.facts[0], result.value.facts)
        self.assertIn(original, result.value.evidence)
        scoped = next(f for f in result.value.facts if f.kind == "usage_scope")
        self.assertEqual(item.metadata["usageScope"], scoped.metadata["usageScope"])
        self.assertIs(item.metadata["usageScope"], scoped.metadata["usageScope"])
        invalid = normalizer.normalize(context, FrontendSnapshot((entity,), (original, changed(item, recordCount=99))))
        self.assertEqual(CompletionStatus.PARTIAL, invalid.status)
        self.assertEqual(baseline.value.facts, invalid.value.facts)
        self.assertEqual("normalization.invalid-usage-structure", invalid.diagnostics[0].code)

    def test_normalizer_keeps_configurations_separate_and_conflicts_partial(self):
        item = sample()
        entity = Entity(item.subject_id, "source_file", "a.cpp")
        normalizer, context = CppEvidenceNormalizer(), make_context(Path("/tmp"))
        configurations = tuple(replace(item, id=stable_id("evidence", i), metadata={
            **item.metadata, "compilationContextId": stable_id("config", i)}) for i in range(2))
        result = normalizer.normalize(context, FrontendSnapshot((entity,), (item, *configurations)))
        self.assertEqual(3, len(result.value.facts))
        self.assertEqual(3, len({f.scope for f in result.value.facts}))
        other = replace(changed(item, status="partial", reasonCodes=("usage-partial-parse",)),
            id=stable_id("other"), producer="clang")
        result = normalizer.normalize(context, FrontendSnapshot((entity,), (item, other)))
        self.assertEqual(CompletionStatus.PARTIAL, result.status)
        self.assertEqual("partial", result.value.facts[0].metadata["usageScope"]["status"])
        self.assertEqual(2, len(result.value.facts[0].evidence_ids))
        for config in (None, "wrong", 1):
            self.assertEqual(("usage-invalid-configuration",), validate_usage(replace(item,
                metadata={**item.metadata, "compilationContextId": config})))

    def test_disconnected_and_missing_reverse_parent_links_are_rejected(self):
        item = sample()
        rows = [dict(row) for row in item.metadata["usageScope"]["records"]]
        rows[1]["children"] = ()
        rows[1]["fields"] = {}
        self.assertEqual(("usage-invalid-parent",), validate_usage(changed(item, records=tuple(rows))))
        rows = [dict(row) for row in item.metadata["usageScope"]["records"]]
        rows[0]["children"], rows[0]["fields"] = (), {}
        rows[1]["parent"] = rows[1]["key"]
        rows[1]["children"] = (*rows[1]["children"], rows[1]["key"])
        self.assertEqual(("usage-disconnected-records",), validate_usage(changed(item, records=tuple(rows))))

    def test_binding_cannot_reference_other_declarations_or_fake_scope(self):
        item = sample()
        records = item.metadata["usageScope"]["records"]
        for field, value in (("declaration", (0, 1, "identifier")),
                             ("declarationOwner", None), ("scope", None),
                             ("possibleDeclarations", ()), ("status", "unknown")):
            rows = [dict(row) for row in records]
            rows[-1]["binding"] = {**rows[-1]["binding"], field: value}
            self.assertEqual(("usage-invalid-binding",), validate_usage(changed(item, records=tuple(rows))))
        rows = [dict(row) for row in records]
        del rows[-1]["binding"]
        self.assertEqual(("usage-invalid-binding",), validate_usage(changed(item, records=tuple(rows))))
        # 拒绝子节点先于父节点，不按遍历乱序 silently 改变声明可见性。
        rows = [records[0], records[2], records[1], *records[3:]]
        self.assertEqual(("usage-invalid-order",), validate_usage(changed(item, records=tuple(rows))))
