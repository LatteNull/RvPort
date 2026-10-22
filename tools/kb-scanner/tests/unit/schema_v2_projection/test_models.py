from __future__ import annotations

import unittest

from pydantic import ValidationError

from kb_scanner.projection.v2.models import Conclusion, SourceContext, ContextBudget, SchemaV2Report, confidence_value, stable_view_id
from .support import report


class ModelsTests(unittest.TestCase):
    def test_historical_missing_english_round_trip_preserves_original_advice(self):
        original = report()
        self.assertIsNone(original.findings[0].conclusion.suggestion_en)
        wire = original.model_dump(mode="json", exclude_none=True)
        self.assertNotIn("suggestion_en", wire["findings"][0]["conclusion"])
        self.assertEqual(original, SchemaV2Report.model_validate(wire))
        self.assertTrue(original.findings[0].conclusion.suggestion.isascii())
        with self.assertRaises(ValueError):
            original.findings[0].conclusion.require_bilingual_suggestions()

    def test_explicit_invalid_english_is_not_treated_as_historical_absence(self):
        base = report().findings[0].conclusion.model_dump(exclude_none=True)
        for value in (None, "", " \t\r\n", 0, False, [], {}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                Conclusion.model_validate({**base, "suggestion_en": value})
        with self.assertRaises(ValidationError):
            Conclusion.model_validate({**base, "suggestion_en": "English", "other": "not an extension"})

    def test_new_pair_and_producer_rejects_blank_or_bypassed_invalid_fields(self):
        base = report().findings[0].conclusion.model_dump(exclude_none=True)
        value = Conclusion.model_validate({**base, "suggestion": "请核查目标路径。", "suggestion_en": "Review the target path."})
        value.require_bilingual_suggestions()
        self.assertEqual(value, Conclusion.model_validate(value.model_dump(exclude_none=True)))
        for field in ("suggestion", "suggestion_en"):
            for bad in (None, "", " \t\n", 42):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    value.model_copy(update={field: bad}).require_bilingual_suggestions()

    def test_complete_fixture_builds_immutable_closed_model(self):
        value = report()
        self.assertEqual("2.0", value.schemaVersion)
        with self.assertRaises(ValidationError):
            SchemaV2Report.model_validate({**value.model_dump(mode="json"), "trace": {}})
        with self.assertRaises(ValidationError):
            value.schemaVersion = "1.0"

    def test_context_state_rules_are_closed(self):
        budget = ContextBudget(beforeLines=2, afterLines=2, maxLines=16, maxCharacters=4096, truncated=False)
        with self.assertRaises(ValidationError):
            SourceContext(status="complete", budget=budget)
        with self.assertRaises(ValidationError):
            SourceContext(status="unavailable", reasonCodes=("context_unavailable",), lines=({"line": 1, "text": "x"},), budget=budget)

    def test_stable_ids_ignore_order_only_when_caller_normalizes(self):
        self.assertEqual(stable_view_id("x", "a", 1), stable_view_id("x", "a", 1))
        self.assertNotEqual(stable_view_id("x", "a", 1), stable_view_id("x", "a", 2))
        self.assertEqual(1.0, confidence_value("high"))
        self.assertEqual(0.25, confidence_value("unknown"))
