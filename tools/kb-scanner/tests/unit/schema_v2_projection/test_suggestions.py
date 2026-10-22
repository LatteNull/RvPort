"""Pure presentation policy, with independently authored bilingual expectations."""
import dataclasses
import json
import unittest

from kb_scanner.projection.v2.suggestions import SUGGESTIONS, select_suggestion
from .support import ROOT


class SuggestionTests(unittest.TestCase):
    def test_all_templates_match_reviewed_text_and_are_immutable(self):
        expected = json.loads((ROOT / "tests/fixtures/bilingual-suggestions/expected-pairs.json").read_text(encoding="utf-8"))
        self.assertEqual(set(expected), set(SUGGESTIONS))
        for key, pair in SUGGESTIONS.items():
            with self.subTest(key=key):
                self.assertEqual(expected[key], dataclasses.asdict(pair))
                self.assertRegex(pair.zh, r"[\u4e00-\u9fff]")
                self.assertTrue(pair.en.isascii())
                self.assertNotIn("codec", pair.en.lower())
                self.assertEqual(pair.zh.count("RISC-V"), pair.en.count("RISC-V"))
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    pair.zh = "changed"
        with self.assertRaises(TypeError):
            SUGGESTIONS["unknown"] = SUGGESTIONS["hint"]

    def test_known_states_and_specific_gap_actions(self):
        cases = [
            ("blocking_issue", "complete", "x86_intrinsic_reference", "blocking"),
            ("actionable_non_blocking", "complete", "x86_intrinsic_reference", "local"),
            ("actionable_non_blocking", "complete", "build_selected_x86_dependency", "local"),
            ("actionable_non_blocking", "complete", "architecture_enum_candidate", "local"),
            ("actionable_non_blocking", "complete", "missing_riscv_selection_path", "selection_gap"),
            ("actionable_non_blocking", "complete", "riscv_test_coverage_gap", "test_gap"),
            ("hint", "complete", "x86_comment_hint", "hint"),
            ("guarded_inactive", "complete", "x86_intrinsic_reference", "inactive"),
            ("blocking_issue", "inactive", "x86_intrinsic_reference", "inactive"),
        ]
        for impact, status, kind, expected in cases:
            with self.subTest(impact=impact, status=status, kind=kind):
                self.assertEqual(SUGGESTIONS[expected], select_suggestion(impact, status, kind))

    def test_incomplete_evidence_overrides_actionable_and_inactive_templates(self):
        for status in ("unknown", "partial", "ambiguous"):
            for impact in ("blocking_issue", "actionable_non_blocking", "guarded_inactive", "hint"):
                with self.subTest(status=status, impact=impact):
                    self.assertEqual(SUGGESTIONS["unknown"], select_suggestion(impact, status, "riscv_test_coverage_gap"))
        self.assertEqual(SUGGESTIONS["unknown"], select_suggestion("unknown", "inactive", "x86_intrinsic_reference"))

    def test_missing_or_future_inputs_conservatively_preserve_facts(self):
        cases = [("blocking_issue", "complete", "unknown"),
                 ("actionable_non_blocking", "complete", "future_type"),
                 ("future_impact", "complete", "x86_intrinsic_reference"),
                 ("blocking_issue", "future_status", "x86_intrinsic_reference")]
        for args in cases:
            with self.subTest(args=args):
                pair = select_suggestion(*args)
                self.assertEqual(SUGGESTIONS["unknown"], pair)
                self.assertIn("保留该事实", pair.zh)
                self.assertIn("Preserve this fact", pair.en)
