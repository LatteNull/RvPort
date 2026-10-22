from __future__ import annotations

import unittest

from kb_scanner.compatibility.cleanup import validate_cleanup_inventory
from kb_scanner.compatibility.differential import compare_payloads, normalize_payload, validate_ledger


class DifferentialCleanupTests(unittest.TestCase):
    def test_normalizes_roots_slashes_and_finding_order(self) -> None:
        value = {"findings": [{"file": "b.c", "line": 2}, {"file": "C:\\work\\a.c", "line": 1}], "diagnostics": ["z", "a"]}
        normalized = normalize_payload(value, ("C:/work",))
        self.assertEqual("$ROOT/a.c", normalized["findings"][0]["file"])
        self.assertEqual(["a", "z"], normalized["diagnostics"])

    def test_comparator_reports_type_keys_length_and_values(self) -> None:
        differences = compare_payloads({"a": [1, 2], "gone": 1}, {"a": [1, "x", 3], "new": 2})
        self.assertTrue(any("length" in item for item in differences))
        self.assertTrue(any("type" in item for item in differences))
        self.assertTrue(any("missing" in item for item in differences))
        self.assertTrue(any("unexpected" in item for item in differences))
        self.assertEqual((), compare_payloads({"x": 1}, {"x": 1}))

    def test_ledger_requires_auditable_approved_corrections(self) -> None:
        base = {"schemaVersion": "1.0", "allowedStatuses": ["parity-required", "approved-correction", "deferred-blocking"], "decisions": []}
        self.assertEqual((), validate_ledger(base))
        decision = {"id": "d", "status": "approved-correction", "fixture": "f", "field": "$.x", "legacyValue": 1, "newValue": 2, "reason": "proof", "evidenceIds": [], "proofPathIds": []}
        value = {**base, "decisions": [decision, decision]}
        failures = validate_ledger(value)
        self.assertTrue(any("no evidence" in item for item in failures))
        self.assertTrue(any("duplicated" in item for item in failures))
        self.assertTrue(validate_ledger([]))
        self.assertTrue(validate_ledger({**base, "allowedStatuses": []}))

    def test_cleanup_inventory_validation(self) -> None:
        entry = {"path": "kb_scanner/legacy.py", "replacement": "new", "fixtures": ["f"], "disposition": "retained-deferred", "exitCondition": "golden"}
        valid = {"schemaVersion": "1.0", "entries": [entry]}
        self.assertEqual((), validate_cleanup_inventory(valid))
        invalid = {"schemaVersion": "2", "entries": [entry, entry | {"path": "../bad", "fixtures": [], "disposition": "bad", "replacement": ""}]}
        self.assertGreaterEqual(len(validate_cleanup_inventory(invalid)), 4)
        self.assertTrue(validate_cleanup_inventory([]))
        self.assertTrue(validate_cleanup_inventory({"schemaVersion": "1.0", "entries": {}}))


if __name__ == "__main__":
    unittest.main()
