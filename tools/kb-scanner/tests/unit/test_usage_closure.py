"""以合成语法验证候选值及其控制后果；不调用 native parser。"""
import unittest

from kb_scanner.analyzers.candidate_usage.index import ScopeIndex
from kb_scanner.analyzers.candidate_usage.closure import query, QueryBudget
from kb_scanner.frontends.cpp.usage_bindings import bind
from tests.unit.test_usage_bindings import fixture, row


def scope(rows, **kwargs):
    # 这些使用图测试只关注已规范化树，不复测完整的 source span 合同。
    return {"records": bind([{**r, "span": (1, r["key"][0]+1, 1, r["key"][1]+1)} for r in rows]),
            "status": "complete", "reasonCodes": (), **kwargs}


def base():
    rows = fixture()
    typ = row("primitive_type", 2, rows[2]["key"], "int")
    rows[2]["fields"]["type"] = typ["key"]
    rows.insert(3, typ)
    return rows


class UsageClosureTests(unittest.TestCase):
    def test_canonical_edges_are_shared_without_reusing_root_budgets(self):
        index = ScopeIndex(scope(base()))
        root = base()[-1]["key"]
        full = query(index, (root,))
        again = query(index, (root,))
        self.assertEqual(full, again)
        for first, second in zip(full["links"], again["links"]):
            self.assertIs(first, second)
            left, right = first
            self.assertIs(first, dict(index.adjacency[left])[right])
            self.assertIs(first, dict(index.adjacency[right])[left])
        other_root = full["useKeys"][0]
        from_other = query(index, (other_root,))
        self.assertEqual(full["recordKeys"], from_other["recordKeys"])
        self.assertTrue(query(index, (root,), QueryBudget(edges=0))["truncated"])
        self.assertEqual(full, query(index, (root,)))
        independent = query(ScopeIndex(scope(base())), (root,))
        self.assertEqual(full, independent)
        self.assertIsNot(full["links"][0], independent["links"][0])

    def test_local_uses_close_and_unknown_unrelated_call_does_not_pollute(self):
        rows = base()
        root = rows[-1]["key"]
        rows.append(row("call_expression", 10, rows[1]["key"]))
        index = ScopeIndex(scope(rows))
        result = query(index, (root,))
        self.assertEqual("complete", result["status"])
        self.assertEqual(2, len(result["useKeys"]))
        self.assertNotIn(rows[-1]["key"], result["recordKeys"])
        self.assertEqual((root,), index.roots_at((1, 5, 1, 6)))
        self.assertEqual((), index.roots_at((10, 10, 10, 11)))

    def test_controlled_call_and_value_escape_keep_unknown(self):
        for kind, reason in (("call_expression", "usage-unknown-call"),
                             ("return_statement", "usage-return-escape"),
                             ("pointer_expression", "usage-address-escape"),
                             ("field_expression", "usage-external-write"),
                             ("while_statement", "usage-unsupported-syntax")):
            rows = base()
            operation = row(kind, 6, rows[1]["key"])
            use = row("identifier", 7, operation["key"], "X86")
            index = ScopeIndex(scope(rows+[operation, use]))
            result = query(index, (rows[-1]["key"],))
            self.assertEqual("unknown", result["status"])
            self.assertIn(reason, result["reasonCodes"])
        rows = base()
        condition = row("if_statement", 7, rows[1]["key"])
        read = row("identifier", 8, condition["key"], "X86")
        body = row("compound_statement", 9, condition["key"])
        call = row("call_expression", 10, body["key"])
        result = query(ScopeIndex(scope(rows+[condition, read, body, call])), (rows[-1]["key"],))
        self.assertIn("usage-unknown-call", result["reasonCodes"])

    def test_whitelist_type_operators_integer_and_unbound_paths(self):
        cases = (("binary_expression", "+", "", "usage-unsupported-operator"),
                 ("binary_expression", "==", "", None),
                 ("assignment_expression", "+=", "", "usage-unsupported-operator"),
                 ("assignment_expression", "=", "", None),
                 ("type_qualifier", "", "volatile", "usage-unsupported-type"),
                 ("type_qualifier", "", "const", None),
                 ("primitive_type", "", "float", "usage-unsupported-type"),
                 ("number_literal", "", "1.0", "usage-noninteger-value"),
                 ("number_literal", "", "0x10UL", None),
                 ("identifier", "", "missing", "usage-unresolved-binding"))
        for kind, operator, text, reason in cases:
            root = row(kind, 0, text=text, operator=operator)
            index = ScopeIndex(scope([root]))
            self.assertEqual(set() if reason is None else {reason}, index.reasons[root["key"]])

    def test_field_object_escape_is_not_lost_and_member_name_is_not_a_local_use(self):
        for field, expected in (("argument", "unknown"), ("field", "complete")):
            rows = base()
            expression = row("field_expression", 6, rows[1]["key"])
            use = row("identifier", 7, expression["key"], "X86")
            expression["fields"] = {field: use["key"]}
            result = query(ScopeIndex(scope(rows+[expression, use])), (rows[-1]["key"],))
            self.assertEqual(expected, result["status"])

    def test_local_array_requires_fixed_size_and_local_binding(self):
        rows = base()
        array = row("array_declarator", 6, rows[2]["key"])
        size = row("number_literal", 7, array["key"], "4")
        array["fields"] = {"declarator": rows[4]["key"], "size": size["key"]}
        rows[4]["parent"] = array["key"]
        rows[2]["fields"]["declarator"] = array["key"]
        subscript = row("subscript_expression", 8, rows[1]["key"])
        read = row("identifier", 9, subscript["key"], "X86")
        subscript["fields"] = {"argument": read["key"]}
        # 父记录必须先于其子记录，使用位置晚于声明。
        ordered = rows[:4]+[array, size, rows[4], rows[5], subscript, read]
        index = ScopeIndex(scope(ordered))
        self.assertNotIn("usage-array-binding-unknown", index.reasons[subscript["key"]])
        size["text"] = "dynamic"
        index = ScopeIndex(scope(ordered))
        self.assertIn("usage-array-binding-unknown", index.reasons[subscript["key"]])

    def test_budget_partial_missing_roots_and_determinism(self):
        index = ScopeIndex(scope(base()))
        root = base()[-1]["key"]
        for budget in (QueryBudget(depth=0), QueryBudget(nodes=0), QueryBudget(edges=0)):
            result = query(index, (root,), budget)
            self.assertEqual("unknown", result["status"])
            self.assertTrue(result["truncated"])
        for bad in (-1, True, "0"):
            with self.assertRaises(ValueError):
                QueryBudget(nodes=bad)
        for options in ({"depth": 33}, {"nodes": 4097}, {"edges": 8193}):
            with self.assertRaises(ValueError):
                QueryBudget(**options)
        for roots in ((), ((100, 101, "identifier"),)):
            self.assertIn("usage-root-unresolved", query(index, roots)["reasonCodes"])
        self.assertEqual(query(index, (root,)), query(index, (root, root)))
        partial = ScopeIndex(scope(base(), status="partial", reasonCodes=("usage-scope-budget",)))
        self.assertIn("usage-scope-incomplete", query(partial, (root,))["reasonCodes"])

    def test_later_overwrite_does_not_hide_earlier_escape_or_other_uses(self):
        rows = base()
        operation = row("call_expression", 6, rows[1]["key"])
        escaped = row("identifier", 7, operation["key"], "X86")
        overwrite = row("assignment_expression", 8, rows[1]["key"], operator="=")
        written = row("identifier", 9, overwrite["key"], "X86")
        literal = row("number_literal", 10, overwrite["key"], "0")
        overwrite["fields"] = {"left": written["key"], "right": literal["key"]}
        result = query(ScopeIndex(scope(rows+[operation, escaped, overwrite, written, literal])), (rows[-1]["key"],))
        self.assertIn("usage-unknown-call", result["reasonCodes"])
        self.assertIn(escaped["key"], result["useKeys"])
        self.assertIn(written["key"], result["useKeys"])

    def test_shadowed_inner_escape_is_not_an_outer_binding(self):
        rows = base()
        inner = row("compound_statement", 6, rows[1]["key"])
        declaration = row("declaration", 7, inner["key"])
        typ = row("primitive_type", 8, declaration["key"], "int")
        name = row("identifier", 9, declaration["key"], "X86")
        declaration["fields"] = {"type": typ["key"], "declarator": name["key"]}
        call = row("call_expression", 10, inner["key"])
        read = row("identifier", 11, call["key"], "X86")
        result = query(ScopeIndex(scope(rows+[inner, declaration, typ, name, call, read])), (rows[-1]["key"],))
        self.assertEqual("complete", result["status"])
        self.assertNotIn(read["key"], result["useKeys"])
        self.assertEqual(2, len(result["useKeys"]))
