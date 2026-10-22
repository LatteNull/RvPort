import unittest

from kb_scanner.frontends.build.autoconf.flow import Evaluator, State
from kb_scanner.frontends.build.autoconf.values import Value
from .support import arm, assignment, case, command, condition, group, leaf, source, substitution, variable, word


class FlowTests(unittest.TestCase):
    def run_source(self, src, args=(), **budgets):
        engine = Evaluator({src.path: src}, "riscv64", src.path, **budgets)
        engine.retain(src)
        result = engine.run(src.path, args, bound=src.path == "configure")
        return result, engine

    def test_cpu_case_first_match_rejection_and_retained_inactive_facts(self):
        src = source(assignment("cpu", substitution(command("uname", "-m"))),
                     case(variable("cpu"), arm(["x86*", "amd64"], command("exit", "1")),
                          arm("riscv*", command("echo", "riscv64-unknown-linux-gnu")), arm("*", command("exit", "1"))))
        result, engine = self.run_source(src)
        self.assertEqual(result.status, "accepted")
        raw = [r for r in engine.records[src.path] if r.metadata["autoconf"].get("raw")]
        self.assertTrue(any("exit 1" in r.value for r in raw))
        src = source(case(word("riscv64"), arm("*", command("exit", "1")), arm("riscv*", command("exit", "0"))))
        self.assertEqual(self.run_source(src)[0].status, "rejected")

    def test_unknown_branches_join_without_inventing_platform(self):
        for statements, expected in (([case(variable("os"), arm("Linux", command("exit", "1")), arm("*", command("exit", "2")))], "rejected"),
                                     ([case(variable("os"), arm("Linux", command("exit", "1")), arm("*", command("exit", "0")))], "unknown"),
                                     ([assignment("os", substitution(command("uname", "-s"))), command("echo", variable("os"))], "unknown")):
            self.assertEqual(self.run_source(source(*statements))[0].status, expected)

    def test_quoted_pattern_is_literal_no_match_and_fallthrough_unknown(self):
        src = source(case(word("rv"), arm(leaf("raw_string", "'*'"), command("exit", "1"))), command("exit", "0"), path="configure")
        self.assertEqual(self.run_source(src)[0].status, "accepted")
        fall = group("case_item", ("value", word("*")), (None, leaf(";&", ";&")))
        self.assertIn("fallthrough", self.run_source(source(case(word("rv"), fall)))[0].reason)
        for pattern in ("@(riscv64)", leaf("string", '"*"')):
            self.assertEqual(self.run_source(source(case(variable("x"), arm(pattern, command("exit", "1")))))[0].status, "unknown")

    def test_if_elif_else_and_unknown_test(self):
        for test, expected in ((command("true"), "accepted"), (command("false"), "rejected"),
                               (command("test", "x", "=", "x"), "accepted"),
                               (command("test", variable("x"), "=", "yes"), "unknown")):
            src = source(condition(test, [command("exit", "0")], [command("exit", "1")]), path="configure")
            self.assertEqual(self.run_source(src)[0].status, expected)
        src = source(condition(command("false"), [command("exit", "1")], [command("exit", "2")],
                               [(command("false"), [command("exit", "3")]), (command("true"), [command("exit", "0")])]), path="configure")
        self.assertEqual(self.run_source(src)[0].status, "accepted")
        src = source(condition(command("test", variable("u"), "=", "a"), [command("exit", "1")], [command("exit", "2")]), path="configure")
        self.assertEqual(self.run_source(src)[0].status, "rejected")

    def test_test_expressions_unary_and_unsupported_condition(self):
        for args, expected in ((["a", "!=", "b"], True), (["a", "==", "a"], True), (["-n", "a"], True),
                               (["-z", leaf("raw_string", "''")], True), (["-e", "file"], None), (["a"], None)):
            src = source(command("test", *args))
            engine = Evaluator({src.path: src}, "riscv64", src.path)
            self.assertIs(engine.condition(src, src.root.children[0][1], State(), ()), expected)
        test = group("test_command", (None, leaf("[", "[")), (None, group("binary_expression", ("left", word("a")),
                     ("operator", leaf("!=", "!=")), ("right", word("b")))), (None, leaf("]", "]")))
        self.assertEqual(self.run_source(source(condition(test, [command("exit", "0")]), path="configure"))[0].status, "accepted")
        for test in (command("external-check"), group("test_command"), leaf("list", "true && false")):
            self.assertEqual(self.run_source(source(condition(test, [command("exit", "0")]), path="configure"))[0].status, "unknown")

    def test_outputs_statuses_and_unsupported_are_not_accepted(self):
        for statements in ([command("exit", "0")], [command("echo", "riscv64-unknown-linux"), command("exit", "1")],
                           [command("echo", "-n", "riscv64-unknown-linux")], [command("printf", "%d", "1")],
                           [command("external-command"), command("exit", "0")], [command("echo", variable("u"))],
                           [command("exit", "bad")], [leaf("while_statement", "while true; do :; done")]):
            self.assertNotEqual(self.run_source(source(*statements))[0].status, "accepted")
        for cmd in (command("printf", "%s", "riscv64-unknown-linux"),
                    command("printf", leaf("raw_string", "'%s\\n'"), "riscv64-unknown-linux")):
            self.assertEqual(self.run_source(source(cmd))[0].status, "accepted")
        self.assertEqual(self.run_source(source(command("echo", "riscv64-unknown-"), command("echo", "linux")))[0].status, "unknown")
        self.assertEqual(self.run_source(source(command("echo", "x" * 4097)))[0].reason, "autoconf-output-unsupported-or-budget")
        self.assertEqual(self.run_source(source(command("false"), command("exit")))[0].status, "rejected")
        self.assertEqual(self.run_source(source(command(":"), path="configure"))[0].status, "accepted")

    def test_helper_calls_propagate_arguments_result_and_source_parents(self):
        main = source(assignment("guess", substitution(command("sh", "./config.guess"))),
                      assignment("host", substitution(command("./config.sub", variable("guess")))), command("exit"), path="configure")
        guess = source(command("echo", "riscv64-unknown-linux"))
        sub = source(case(variable("1"), arm("riscv*", command("echo", variable("1"))), arm("*", command("exit", "1"))), path="config.sub")
        engine = Evaluator({s.path: s for s in (main, guess, sub)}, "riscv64", "configure")
        result = engine.run("configure", bound=True)
        self.assertEqual(result.status, "accepted")
        self.assertEqual(set(engine.records), {"configure", "config.guess", "config.sub"})
        keys = {r.metadata["autoconf"]["key"] for items in engine.records.values() for r in items}
        self.assertTrue(all(set(r.metadata["autoconf"]["parents"]) <= keys for items in engine.records.values() for r in items))
        engine.sources["config.sub"] = source(command("exit", "1"), path="config.sub")
        self.assertEqual(engine.run("configure", bound=True).status, "rejected")
        self.assertEqual(self.run_source(sub)[0].status, "unknown")

    def test_helpers_safety_unknown_commands_cycles_and_budgets(self):
        for name, reason in (("config.sub", "path-unbound"), ("/config.sub", "path-unbound"),
                             ("../config.sub", "outside-workspace"), ("./config.sub", "unavailable"),
                             ("curl", "command-unsupported")):
            self.assertIn(reason, self.run_source(source(command(name), path="configure"))[0].reason)
        main = source(command("./config.guess"), path="configure")
        helper = source(command("./config.guess"))
        engine = Evaluator({s.path: s for s in (main, helper)}, "riscv64", "configure")
        self.assertIn("cycle", engine.run("configure").reason)
        for kwargs in ({"max_steps": 1}, {"max_depth": 1}, {"max_paths": 1}):
            nested = condition(command("test", variable("u"), "=", "x"), [condition(command("true"), [command(":")])], [command(":")])
            result, _ = self.run_source(source(nested, command(":")), **kwargs)
            self.assertIn("budget", result.reason)
        with self.assertRaises(ValueError):
            Evaluator({}, "riscv64", "configure", max_steps=0)

    def test_unsupported_assignment_substitution_and_parse_issue(self):
        for stmt in (group("variable_assignment"), assignment("x+=", word("1")),
                     assignment("x", substitution(command("evil"))),
                     assignment("x", substitution(command("uname", "-m"), command("evil"))),
                     group("command", ("name", word("echo")), (None, leaf("redirect", "> file")))):
            self.assertEqual(self.run_source(source(stmt, path="configure"))[0].status, "unknown")
        self.assertEqual(self.run_source(source(command("exit", "0"), issue="syntax-error", path="configure"))[0].status, "unknown")

    def test_globbing_and_field_splitting_do_not_fabricate_known_arguments(self):
        for argument in (word("*"), variable("x")):
            src = source(assignment("x", leaf("raw_string", "'a b'")), command("echo", argument))
            self.assertEqual(self.run_source(src)[0].status, "unknown")
        helper = source(command("echo", "riscv64-unknown-linux"))
        main = source(command("./config.guess"), command("echo", "extra"), path="config.sub")
        engine = Evaluator({s.path: s for s in (main, helper)}, "riscv64", main.path)
        result = engine.run(main.path)
        self.assertEqual(result.output, "riscv64-unknown-linux\nextra")
        self.assertEqual(result.status, "unknown")

    def test_multiple_helper_outcomes_join_and_unknown_output_propagate(self):
        helper = source(case(variable("1"), arm("yes", command("exit", "1")), arm("*", command("exit", "2"))))
        main = source(assignment("x", substitution(command("./config.guess", variable("u")))), command("exit"), path="configure")
        engine = Evaluator({s.path: s for s in (main, helper)}, "riscv64", main.path)
        result = engine.run(main.path)
        self.assertEqual(result.status, "unknown")
        self.assertTrue(any(r.metadata["autoconf"].get("helperResult") for r in engine.records[main.path]))
