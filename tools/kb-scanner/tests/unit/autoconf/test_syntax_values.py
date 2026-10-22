import unittest
from types import SimpleNamespace
from unittest.mock import patch

from kb_scanner.frontends.build.autoconf import syntax
from kb_scanner.frontends.build.autoconf.values import UNKNOWN, Value, pattern_match, trim, triplet, value
from .support import assignment, command, group, leaf, source, substitution, variable, word


class SyntaxTests(unittest.TestCase):
    def test_reused_stable_identity_handles_invalid_and_non_json_material(self):
        from enum import Enum
        from pathlib import Path
        from kb_scanner.core import stable_id
        class Role(Enum):
            HOST = "host"
        self.assertEqual(stable_id("entry", Role.HOST, Path("aux/config.sub")), stable_id("entry", "host", "aux/config.sub"))
        with self.assertRaises(ValueError):
            stable_id(" ")
        with self.assertRaises(TypeError):
            stable_id("entry", {1: "not a string key"})

    def native(self, owned, *, missing=False):
        children = [self.native(child) for _, child in owned.children]
        return SimpleNamespace(type=owned.kind, start_byte=owned.start, end_byte=owned.end, children=children,
                               is_missing=missing, has_error=False,
                               field_name_for_child=lambda i: owned.children[i][0])

    def parse(self, original, native=None, **budgets):
        root = native or self.native(original.root)
        with patch.object(syntax, "Language"), patch.object(syntax, "Parser") as parser:
            parser.return_value.parse.return_value.root_node = root
            result = syntax.parse(original.data.decode(), original.path, **budgets)
            parser.return_value.parse.assert_called_once_with(original.data)
        return result

    def test_copy_and_utf8_byte_positions_without_native_points(self):
        original = source(command("echo", "中文"), assignment("cpu", word("riscv64")))
        copied = self.parse(original)
        self.assertEqual(copied.root, original.root)
        node = copied.root.children[1][1]
        self.assertEqual(copied.position(node), (2, 1, node.end - node.start + 1))
        self.assertEqual(copied.position(copied.root)[0], 1)
        self.assertIsNone(node.field("absent"))
        self.assertEqual(node.fields("value"), (node.field("value"),))
        self.assertEqual(copied.text(node), "cpu = riscv64")

    def test_syntax_error_missing_node_depth_and_node_budget(self):
        original = source(command("echo", "hello"))
        for kwargs in ({"max_nodes": 1}, {"max_depth": 1}):
            self.assertEqual(self.parse(original, **kwargs).issue, "autoconf-syntax-budget")
        native = self.native(original.root)
        for field, setting in (("has_error", True), ("is_missing", True), ("type", "ERROR")):
            broken = SimpleNamespace(**{**vars(native), field: setting})
            self.assertEqual(self.parse(original, broken).issue, "autoconf-partial-syntax")
        with self.assertRaises(ValueError):
            syntax.parse("", "configure", max_nodes=0)


class ValueTests(unittest.TestCase):
    def evaluate(self, expression, env=None, callback=None):
        src = source(expression)
        return value(src, src.root.children[0][1], env or {}, callback)

    def test_literals_unknowns_quotes_concat_and_callback(self):
        self.assertEqual(self.evaluate(word("riscv64")), Value("riscv64"))
        self.assertEqual(self.evaluate(word("a\\b")), UNKNOWN)
        self.assertEqual(self.evaluate(leaf("raw_string", "'a$b'")), Value("a$b"))
        self.assertEqual(self.evaluate(variable("cpu"), {"cpu": Value("rv")}), Value("rv"))
        self.assertEqual(self.evaluate(variable("absent")), UNKNOWN)
        expression = group("string", (None, leaf('"', '"')), (None, word("a")),
                           (None, variable("cpu")), (None, leaf('"', '"')))
        self.assertEqual(self.evaluate(expression, {"cpu": Value("rv")}), Value("arv"))
        self.assertEqual(self.evaluate(expression), UNKNOWN)
        self.assertEqual(self.evaluate(leaf("arithmetic_expansion", "$((1))")), UNKNOWN)
        self.assertEqual(self.evaluate(substitution(command("uname", "-m"))), UNKNOWN)
        self.assertEqual(self.evaluate(substitution(command("uname", "-m")), callback=lambda _: Value("rv")), Value("rv"))
        self.assertEqual(value(source(), None, {}), Value(""))

    def test_parameter_trimming_and_missing_values(self):
        env = {"cpu": Value("riscv64-unknown-linux-gnu")}
        for expression, expected in (("${cpu%%-*}", "riscv64"), ("${cpu#*-}", "unknown-linux-gnu"),
                                     ("${cpu%*-gnu}", "riscv64-unknown-linux"), ("${cpu}", env["cpu"].text)):
            self.assertEqual(self.evaluate(leaf("expansion", expression), env).text, expected)
        self.assertEqual(self.evaluate(leaf("expansion", "${missing#*-}")), UNKNOWN)
        self.assertEqual(self.evaluate(leaf("expansion", "${cpu:-x}")), UNKNOWN)
        self.assertEqual(trim("abc", "#", "z"), "abc")
        self.assertEqual(trim("a-b-c", "##", "*-"), "c")
        self.assertEqual(trim("a-b-c", "%", "-*"), "a-b")

    def test_patterns_are_conservative_and_triplets_target_specific(self):
        for text, pattern, expected in ((None, "*", True), (None, "rv*", None), ("riscv64", "riscv??", True),
                                        ("riscv64", "x86*", False), ("a", None, None), ("a", "@(a)", None),
                                        ("a", "[[:alpha:]]", None), ("a", "[a-c]", True)):
            self.assertIs(pattern_match(text, pattern), expected)
        self.assertTrue(triplet("riscv64-unknown-linux-gnu", "riscv64"))
        for text in (None, "", "riscv64", "x86_64-pc-linux", "riscv64--linux", "riscv64-unknown-linux\nextra"):
            self.assertFalse(triplet(text, "riscv64"))
