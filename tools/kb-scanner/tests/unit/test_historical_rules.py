"""Unit contracts for retained rule functions; no project scan or native parser."""
import json
import re
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from kb_scanner import rules as rules
from kb_scanner.models import BranchInfo, CallFact, CompileCommandContext, ConditionFrame, FileFacts, IncludeFact, MacroBranchGroup, ProjectFacts, Rule, TextFact


FILE = Path("/p/a.c")


def rule(match=None, identifier="test", language="any"):
    return Rule(identifier, language, "medium", "high", match or {}, {"zh-CN": {"title": "标题", "reason": "原因"}, "en-US": {"title": "Title"}})


def project(files=None, **kwargs):
    return ProjectFacts(Path("/p"), files if files is not None else [FileFacts(FILE)], "static", **kwargs)


class HistoricalRulesTests(unittest.TestCase):
    def test_loading_valid_invalid_rules_and_generated_facts(self):
        with patch.object(Path, "rglob", return_value=[Path("a.yaml"), Path("b.yaml"), Path("c.yaml"), Path("d.yaml")]), patch.object(Path, "read_text", side_effect=['id: test\n', '[]', 'message: {}', OSError("gone")]):
            loaded, diagnostics = rules.load_rules(Path("/rules"))
        self.assertEqual(["test"], [r.id for r in loaded])
        self.assertEqual(3, len(diagnostics))
        with patch.object(Path, "exists", return_value=False):
            self.assertEqual({}, rules.load_generated_entries(Path("/rules")))
        data = {"compilerFlags": ["-march", "-mtune", "-mcpu", "-mavx"], "intrinsics": ["_mm_x"], "metadata": {"x": 1}}
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "glob", return_value=[Path("gcc-x86-entries.json")]), patch.object(Path, "read_text", return_value=json.dumps(data)):
            self.assertEqual({"compilerFlags": {"-mavx"}, "intrinsics": {"_mm_x"}}, rules.load_generated_entries(Path("/rules")))

    def test_language_and_path_admission(self):
        cases = [("any", "a.c", True), ("any", "a.spec", False), ("build", "Makefile", True), ("build", "a.c", False),
                 ("rpm-spec", "a.spec", True), ("rpm-spec", "a.c", False), ("asm", "a.S", True), ("asm", "a.c", False),
                 ("c-cpp", "a.h", True), ("c", "a.c", True), ("c", "a.cpp", False), ("cpp", "a.cpp", True),
                 ("cpp", "a.c", False), ("unknown", "a.txt", True)]
        for language, name, expected in cases:
            self.assertEqual(expected, rules._rule_applies_to_file(rule(language=language), Path(name)))
        self.assertFalse(rules._path_allowed(FILE, {"pathNameIn": ["other.c"]}))
        self.assertFalse(rules._path_allowed(FILE, {"pathSuffixIn": [".cpp"]}))
        self.assertTrue(rules._path_allowed(FILE, {"pathSuffixIn": [".C"]}))

    def test_include_call_macro_and_text_matchers(self):
        facts = FileFacts(FILE, includes=[IncludeFact("x.h", FILE, 1, True), IncludeFact("x.h", FILE, 2, False), IncludeFact("z.h", FILE, 3, True)],
                          calls=[CallFact("_mm_x", FILE, 4, "_mm_x()"), CallFact("_mm_x", FILE, 5, "WRAP()", via_macro="WRAP", macro_definition_line=3), CallFact("plain", FILE, 6, "plain()")],
                          texts=[TextFact(FILE, 7, "-mavx")])
        cases = [({"include": {"generatedSet": "headers"}}, {"headers": {"x.h"}}, 2),
                 ({"call": {"nameRegex": "^_mm"}}, {}, 2), ({"call": {"generatedSet": "intrinsics"}}, {"intrinsics": {"_mm_x"}}, 2),
                 ({"call": {}}, {}, 0), ({"macroExpansion": {"expandedCallNameRegex": "^_mm"}}, {}, 1),
                 ({"macroExpansion": {}}, {}, 0), ({"text": {"generatedSet": "compilerFlags", "singleFindingPerLine": True}}, {"compilerFlags": {"-mavx"}}, 1),
                 ({"text": {}}, {}, 0), ({"text": {"regex": "(-m)(avx)", "symbolGroup": 2}}, {}, 1)]
        for match, generated, count in cases:
            with self.subTest(match=match):
                found = list(rules._iter_matches(rule(match), facts, generated))
                self.assertEqual(count, len(found))
                self.assertTrue(all(x["file"] == FILE and x["line"] >= 1 for x in found))

    def test_text_filters_and_metadata_are_independent(self):
        for text, metadata, filtering in [("// avx", {}, {"ignoreCommentLines": True}), ("#endif avx", {}, {"ignoreEndifLines": True}),
            ("avx", {"changelog": True}, {"ignoreRpmChangelog": True}), ("avx", {"section": "build"}, {"rpmSections": ["check"]}),
            ("avx", {}, {"pathNameIn": ["other"]})]:
            facts = FileFacts(FILE, texts=[TextFact(FILE, 1, text, metadata=metadata)])
            self.assertEqual([], list(rules._iter_matches(rule({"text": {"regex": "avx", **filtering}}), facts, {})))
        text = TextFact(FILE, 1, "x", metadata={"section": "build", "archTokens": ["x86"], "rpmTag": None})
        self.assertEqual({"metadata": {"section": "build", "archTokens": ["x86"]}}, rules._text_metadata_trace(text, {}))
        self.assertEqual({}, rules._text_metadata_trace(text, {"traceMetadataKeys": ["rpmTag", "unknown"]}))
        self.assertEqual({}, rules._rpm_metadata(NS(metadata=[])))
        self.assertTrue(rules._is_comment_line("# flags", Path("Makefile")))
        self.assertFalse(rules._is_comment_line("code", FILE))

    def test_symbol_fallback_locale_conditions_and_comments(self):
        match = re.search("(avx)(2)?", "avx")
        for group in (9, "bad", 2, 0):
            self.assertEqual("avx", rules._match_symbol(match, {"symbolGroup": group}))
        self.assertEqual("Title", rules._message(rule(), "en-US")["title"])
        self.assertEqual("标题", rules._message(rule(), "unknown")["title"])
        condition = ConditionFrame("ifdef", "X", "X", 1)
        self.assertEqual(["X"], rules._condition_macros([condition, condition, NS(macro=None)]))
        for augment in (rules._augment_reason, rules._augment_reason_en):
            self.assertEqual("reason", augment("reason", [], {}))
            self.assertIn("X", augment("reason", ["X"], {"symbol": "_mm_x"}))
            self.assertIn("X", augment("reason", ["X"], {}))
        for text, block, expected in [("// avx", False, "avx"), ("/* avx */", False, "avx"), (" * avx", True, "avx"),
                                      ("* avx", False, "avx"), ("code // avx", False, "avx"), ("code", False, None)]:
            self.assertEqual(expected, rules._comment_text(text, block))
        lines = ["/* avx", " * sse", " */", "// plain", "code", "// x86"]
        found = list(rules._iter_comment_hint_candidates(project([FileFacts(FILE, texts=[TextFact(FILE, i, text) for i, text in enumerate(lines, 1)])])))
        self.assertEqual([1, 2, 6], [f["line"] for f in found])

    def test_build_context_and_alternative_cache(self):
        value = project()
        self.assertEqual("unknown", rules._build_context(value, FILE)["included_in_riscv_build"])
        value.compile_contexts[str(FILE)] = CompileCommandContext(FILE)
        self.assertEqual("not_reached_from_compile_database", rules._build_context(value, FILE)["reason"])
        value.compile_reachable_files.add(str(FILE))
        self.assertEqual("true", rules._build_context(value, FILE)["included_in_riscv_build"])
        self.assertEqual("build_file_not_represented_in_compile_database", rules._build_context(value, Path("Makefile"))["reason"])
        self.assertFalse(rules._alternative_impl(value, FILE)["is_x86_scoped"])
        for alt in ("riscv", "generic", "none"):
            x86 = Path("/p/x86/a_x86.c")
            value = project([FileFacts(x86), FileFacts(Path(f"/p/{alt}/a_x86.c"))])
            result = rules._alternative_impl(value, x86)
            self.assertEqual(alt != "none", result["has_compatible_alternative"])
            self.assertEqual(result, rules._alternative_impl(value, x86))
        self.assertEqual("a.c", str(rules._safe_relative(Path("/outside/a.c"), Path("/p"))))

    def test_branch_context_siblings_and_classification_policies(self):
        condition = ConditionFrame("ifdef", "__AVX__", "__AVX__", 1, "g", "x86_branch")
        source = FileFacts(FILE)
        value = project([source])
        for role, expected in (("riscv_branch", "riscv"), ("generic_branch", "generic"), ("fallback_branch", "fallback")):
            source.branch_groups["g"] = MacroBranchGroup("g", FILE, 1, [BranchInfo("ifdef", "__AVX__", 1, "x86_branch"), BranchInfo("else", "", 2, role)])
            self.assertEqual(expected, rules._branch_context(source, [condition])["compatible_branch_kind"])
            result = rules._classify_candidate(value, source, {"file": FILE, "conditions": [condition]})
            self.assertEqual("guarded", result["finding_type"])
        source.branch_groups.clear()
        self.assertEqual("inactive", rules._classify_candidate(value, source, {"file": FILE, "conditions": [condition]})["finding_type"])
        condition.branch_role = "unknown"
        self.assertEqual("portability_gap", rules._classify_candidate(value, source, {"file": FILE, "conditions": [condition]})["finding_type"])
        self.assertFalse(rules._is_guarded_x86_candidate([], "x86_branch"))
        self.assertFalse(rules._is_guarded_x86_candidate([condition], "riscv_branch"))
        for conditions, target, expected in (([], "riscv64", False), ([ConditionFrame("if", "defined(__AVX__)", None, 1)], "riscv64", True), ([condition], "x86", False)):
            self.assertEqual(expected, rules._is_inactive_for_target(conditions, target))
        for kind, text in (("else", "__AVX__"), ("ifndef", "__AVX__"), ("if", "123"), ("if", "defined(__AVX__) || __riscv"), ("if", "__AVX__ && UNKNOWN")):
            self.assertFalse(rules._condition_is_x86_only(ConditionFrame(kind, text, None, 1)))
        for alt in (True, False):
            with patch.object(rules, "_alternative_impl", return_value={"is_x86_scoped": True, "has_compatible_alternative": alt}):
                self.assertEqual("inactive" if alt else "portability_gap", rules._classify_candidate(value, source, {"file": FILE})["finding_type"])
        with patch.object(rules, "_build_context", return_value={"included_in_riscv_build": "false"}):
            self.assertEqual("inactive", rules._classify_candidate(value, source, {"file": FILE})["finding_type"])

    def test_evaluate_rules_merges_compile_evidence_and_preserves_hints(self):
        source = FileFacts(FILE, texts=[TextFact(FILE, 1, "-mavx"), TextFact(FILE, 2, "// avx")])
        context = CompileCommandContext(FILE, tokens=["cc", "-mavx", "-D__AVX__=1"], defines={"__AVX__": "1", "PLAIN": None})
        value = project([source], compile_contexts={str(FILE): context}, compile_reachable_files={str(FILE)})
        flag_rule = rule({"text": {"regex": "-mavx"}}, "C_CPP.X86.COMPILER_FLAG")
        macro_rule = rule(identifier="C_CPP.X86.PLATFORM_MACRO")
        found = rules.evaluate_rules(value, [flag_rule, macro_rule, rule(language="rpm_spec")])
        self.assertEqual({"C_CPP.X86.COMPILER_FLAG", "C_CPP.X86.PLATFORM_MACRO", "COMMENT.ARCH.HINT"}, {f.rule_id for f in found})
        flag = next(f for f in found if f.rule_id == flag_rule.id)
        self.assertEqual(1, len(flag.trace["compileCommandEvidence"]))
        self.assertEqual(3, len(rules._deduplicate([*found, flag])))
        self.assertFalse(rules._merge_compile_command_evidence(found, flag))
        macro = next(f for f in found if f.rule_id == macro_rule.id)
        self.assertFalse(rules._merge_compile_command_evidence([], replace(macro, trace={})))
        self.assertEqual([], list(rules._iter_compile_command_matches(project(), flag_rule, {}, {})))
        missing = project(compile_contexts={str(FILE): context})
        self.assertEqual([], list(rules._iter_compile_command_matches(missing, flag_rule, {}, {})))
        self.assertTrue(missing.diagnostics)
        outside = project(compile_contexts={"/outside/a.c": context})
        self.assertEqual([], list(rules._iter_compile_command_matches(outside, flag_rule, {}, {"/outside/a.c": FileFacts(Path("/outside/a.c"))})))
        for tokens, expected in ((["cc", "-DX"], 1), (["cc", "-D", "X=1"], 1), (["cc", "-D"], None)):
            self.assertEqual(expected, rules._token_index(tokens, "-DX=1", "X"))
        self.assertEqual([("-march=x86", 1)], rules._compile_command_flag_tokens(["cc", "-march", "x86"], rule({"text": {"regex": "^-march="}}), {}))

    def test_severity_table_and_hidden_candidate_policy(self):
        base = {"rule_id": "unknown", "base_severity": "medium", "finding_type": "issue", "is_reference_source": True, "condition_macros": [], "source_kind": "code", "snippet": "x"}
        for overrides, expected in (({"finding_type": "hint"}, "info"), ({"source_kind": "comment"}, "info"), ({"finding_type": "inactive"}, "info"), ({"is_reference_source": False}, "medium")):
            self.assertEqual(expected, rules._apply_severity_policy(**{**base, **overrides}))
        for collection, expected in ((rules.LOW_RULES, "low"), (rules.MEDIUM_RULES, "medium"), (rules.HIGH_RULES, "high"), (rules.CRITICAL_RULES, "critical")):
            self.assertEqual(expected, rules._apply_severity_policy(**{**base, "rule_id": next(iter(collection))}))
        critical = next(iter(rules.CRITICAL_RULES))
        self.assertEqual("high", rules._apply_severity_policy(**{**base, "rule_id": critical, "condition_macros": ["X"]}))
        self.assertEqual("high", rules._apply_severity_policy(**{**base, "rule_id": critical, "finding_type": "portability_gap"}))
        source = FileFacts(FILE, texts=[TextFact(FILE, 2, "-mavx", conditions=[ConditionFrame("ifdef", "__AVX__", "__AVX__", 1, "g", "x86_branch")])])
        value = project([source], include_comment_hints=False)
        self.assertEqual([], rules.evaluate_rules(value, [rule({"text": {"regex": "-mavx"}})]))
        value.include_inactive_branches = True
        self.assertEqual(1, len(rules.evaluate_rules(value, [rule({"text": {"regex": "-mavx"}})])))
