"""纯 fake grammar 节点；不加载原生 Parser、不执行项目。"""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from kb_scanner.core import Evidence, SourceLocation, SourceSpan, stable_id
from kb_scanner.core.metadata import to_json_compatible
from kb_scanner.frontends.cpp.source_positions import SourceByteIndex
from kb_scanner.frontends.cpp.usage_inventory import collect, InventoryBudget, cap_records
from kb_scanner.frontends.cpp.frontend import CppFrontend
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from kb_scanner.core import StageResult, WorkspaceSnapshot
from tests.unit.frontends.cpp.test_frontend import FakeTree
from tests.unit.frontends.cpp.support import make_context
from pathlib import Path
from tests.unit.frontends.cpp.test_tree_sitter_adapter import Node


def fixture(prefix=b""):
    source = prefix + b"void f(){int x;}"
    offset = len(prefix)
    name = Node("identifier", offset+13, offset+14)
    typ = Node("primitive_type", offset+9, offset+12)
    declaration = Node("declaration", offset+9, offset+15,
        children=(typ, name), fields={"type": typ, "declarator": name})
    body = Node("compound_statement", offset+8, len(source), children=(declaration,))
    function = Node("function_definition", offset, len(source), children=(body,), fields={"body": body})
    root = Node("translation_unit", 0, len(source), children=(function,))
    positions = SourceByteIndex.build("a.cpp", source)
    anchor = Evidence(stable_id("anchor"), "enum_member_reference", stable_id("file"),
        "Format::X86", "fake", "fake", "medium", positions.span(offset+13, offset+14))
    return root, source, positions, anchor, name


class UsageInventoryTests(unittest.TestCase):
    def run_collect(self, data, **kwargs):
        return collect(*data[:3], data[3].subject_id, "fake", (data[3],), **kwargs)

    def test_scalar_records_and_original_anchor_are_immutable(self):
        data = fixture()
        original = data[3]
        scope = self.run_collect(data)[0]
        record = scope.metadata["usageScope"]
        self.assertEqual(1, scope.metadata["identityVersion"])
        self.assertEqual(stable_id("usage_scope", 1, original.subject_id, scope.location, "fake"), scope.id)
        self.assertEqual("complete", record["status"])
        self.assertEqual(5, record["recordCount"])
        self.assertEqual("x", record["records"][-1]["text"])
        self.assertEqual((1, 14, 1, 15), record["records"][-1]["span"])
        self.assertEqual(original, data[3])
        self.assertEqual(scope, self.run_collect(data)[0])
        self.assertIn('"records"', json.dumps(to_json_compatible(scope.metadata)))
        self.assertEqual((8, 16, "compound_statement"), record["records"][0]["fields"]["body"])

    def test_absent_and_outside_anchors_skip_scopes(self):
        data = fixture()
        args = (*data[:3], data[3].subject_id, "fake")
        self.assertEqual((), collect(*args, ()))
        self.assertEqual((), collect(*args, (replace(data[3], location=None),)))
        outside = replace(data[3], location=SourceSpan(SourceLocation("a.cpp", 2, 1), SourceLocation("a.cpp", 2, 2)))
        self.assertEqual((), collect(*args, (outside,)))

    def test_budgets_fail_closed(self):
        for value in (-1, True, 1.5, "1"):
            with self.assertRaises(ValueError):
                InventoryBudget(file_nodes=value)
        for options in ({"file_nodes": 100001}, {"scope_nodes": 10001}, {"token_bytes": 257}):
            with self.assertRaises(ValueError):
                InventoryBudget(**options)
        data = fixture()
        self.assertEqual((), self.run_collect(data, budget=InventoryBudget(file_nodes=0)))
        for budget, reason in ((InventoryBudget(scope_nodes=0), "usage-scope-budget"),
                               (InventoryBudget(token_bytes=0), "usage-token-budget")):
            scope = self.run_collect(data, budget=budget)[0].metadata["usageScope"]
            self.assertEqual("partial", scope["status"])
            self.assertIn(reason, scope["reasonCodes"])
        root = data[0]
        root.children.append(Node("declaration", 0, 1))
        scope = self.run_collect(data, budget=InventoryBudget(file_nodes=2))[0].metadata["usageScope"]
        self.assertIn("usage-file-budget", scope["reasonCodes"])

    def test_errors_unsupported_owner_and_utf8(self):
        data = fixture("// 中文\r\n".encode())
        self.assertEqual(2, self.run_collect(data)[0].location.start.line)
        data[-1].is_missing = True
        self.assertIn("usage-partial-parse", self.run_collect(data)[0].metadata["usageScope"]["reasonCodes"])
        data = fixture()
        fn = data[0].children[0]
        data[0].children = [Node("template_declaration", 0, len(data[1]), children=(fn,))]
        self.assertIn("usage-unsupported-owner", self.run_collect(data)[0].metadata["usageScope"]["reasonCodes"])

    def test_file_budget_includes_function_records(self):
        data = fixture()
        complete = self.run_collect(data, budget=InventoryBudget(file_nodes=6))[0]
        self.assertEqual("complete", complete.metadata["usageScope"]["status"])
        partial = self.run_collect(data, budget=InventoryBudget(file_nodes=5))[0]
        self.assertEqual(4, partial.metadata["usageScope"]["recordCount"])
        self.assertIn("usage-file-budget", partial.metadata["usageScope"]["reasonCodes"])
        self.assertEqual((), complete.knowledge_sources)

    def test_file_budget_freezes_each_scalar_scope_only_once(self):
        data = fixture()
        with patch("kb_scanner.frontends.cpp.usage_inventory.Evidence", wraps=Evidence) as constructor:
            result = self.run_collect(data, budget=InventoryBudget(file_nodes=5))
        self.assertEqual(1, constructor.call_count)
        self.assertEqual("partial", constructor.call_args.kwargs["metadata"]["usageScope"]["status"])
        self.assertEqual(4, result[0].metadata["usageScope"]["recordCount"])
        with self.assertRaises(TypeError):
            result[0].metadata["usageScope"]["status"] = "complete"
        again = self.run_collect(data)
        self.assertEqual("complete", again[0].metadata["usageScope"]["status"])
        self.assertEqual("partial", result[0].metadata["usageScope"]["status"])

    def test_invalid_nested_range_and_operator_are_recorded(self):
        data = fixture()
        data[-1]._fields["operator"] = Node("operator", 13, 14)
        record = self.run_collect(data)[0].metadata["usageScope"]["records"][-1]
        self.assertEqual("x", record["operator"])
        data[-1].end_byte = len(data[1])+1
        scope = self.run_collect(data)[0].metadata["usageScope"]
        self.assertEqual("partial", scope["status"])
        self.assertIn("usage-invalid-range", scope["reasonCodes"])

    def test_scan_record_cap_never_changes_original_facts(self):
        data = fixture()
        original = data[3]
        self.assertEqual((original, 0), cap_records(original, 0))
        scope = self.run_collect(data)[0]
        self.assertEqual((scope, 0), cap_records(scope, 5))
        trimmed, remaining = cap_records(scope, 4)
        self.assertEqual(0, remaining)
        self.assertEqual(scope.id, trimmed.id)
        self.assertEqual((), trimmed.metadata["usageScope"]["records"])
        self.assertEqual("partial", trimmed.metadata["usageScope"]["status"])
        self.assertIn("usage-scan-record-budget", trimmed.metadata["usageScope"]["reasonCodes"])

    def test_frontend_record_budget_is_shared_across_files_and_preserves_anchors(self):
        data = fixture()
        scope = self.run_collect(data)[0]
        originals, results = [], []
        for name in ("a.c", "b.c"):
            entity = make_source_file_entity(name, ("c",), "0.1.0")
            original = replace(data[3], id=stable_id("anchor", name), subject_id=entity.id)
            scoped = replace(scope, id=stable_id("scope", name), subject_id=entity.id)
            originals.append(original)
            results.append(StageResult((original, scoped)))
        root = Path("/tmp")
        result = CppFrontend(FakeTree(results), usage_record_limit=5).analyze(make_context(root), WorkspaceSnapshot(root, ("a.c", "b.c")))
        self.assertTrue(all(item in result.value.evidence for item in originals))
        scopes = [item.metadata["usageScope"] for item in result.value.evidence if item.kind == "usage_scope"]
        self.assertEqual(5, sum(item["recordCount"] for item in scopes))
        self.assertEqual(1, sum("usage-scan-record-budget" in item["reasonCodes"] for item in scopes))
