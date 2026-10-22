from __future__ import annotations

import unittest

from kb_scanner.core import (
    Assessment,
    AssessmentSnapshot,
    Classification,
    ClassificationSnapshot,
    CoverageStatus,
    Observation,
    TestRole,
    TestRoleEvidence,
    TestRoleStrength,
    TestSelectionStatus,
    candidate_test_path,
    explicit_test_target,
    stable_id,
)


class CoreModelTests(unittest.TestCase):
    def test_path_and_target_role_policy_is_conservative(self) -> None:
        for value in ("tests/a.c", "src/test_math.cpp", "src/math_test.cc", "test/a.c"):
            self.assertTrue(candidate_test_path(value), value)
        for value in ("examples/test_math.c", "benchmarks/math_test.c", "tools/test-gen.c", "src/contest.c", ""):
            self.assertFalse(candidate_test_path(value), value)
        self.assertTrue(candidate_test_path(r"tests\case.c"))
        self.assertTrue(explicit_test_target("anything", "ctest"))
        self.assertTrue(explicit_test_target("check-local", "make"))
        self.assertTrue(explicit_test_target("test-fast", "make"))
        self.assertFalse(explicit_test_target("contest", "make"))
        self.assertEqual(TestRole.TARGET.value, "test_target")
        self.assertEqual(TestSelectionStatus.NOT_SELECTED.value, "not_selected")
        self.assertEqual(CoverageStatus.GAP.value, "gap")

    def test_test_role_metadata_is_frozen_and_candidate_cannot_promote(self) -> None:
        metadata = {"values": ["a"]}
        role = TestRoleEvidence(TestRole.CANDIDATE, TestRoleStrength.CANDIDATE, "path", metadata=metadata)
        metadata["values"].append("b")
        self.assertEqual(role.metadata["values"], ("a",))
        with self.assertRaises(ValueError):
            TestRoleEvidence(TestRole.SOURCE, TestRoleStrength.CANDIDATE, "path")
        with self.assertRaises(ValueError):
            TestRoleEvidence(TestRole.CANDIDATE, TestRoleStrength.CANDIDATE, "")

    def test_classification_and_snapshot_are_immutable_and_compatible(self) -> None:
        observation_id = stable_id("observation", 1)
        evidence_ids = (stable_id("evidence", 2), stable_id("evidence", 1), stable_id("evidence", 1))
        item = Classification(
            stable_id("classification", 1),
            "policy",
            "blocking_issue",
            "selected",
            (observation_id,),
            evidence_ids,
            (),
            (),
            (),
            "high",
            {"nested": [1]},
        )
        self.assertEqual(item.evidence_ids, tuple(sorted(set(evidence_ids))))
        self.assertEqual(item.metadata["nested"], (1,))
        observation = Observation(observation_id, "unit", "kind")
        self.assertEqual(ClassificationSnapshot((observation,)).classifications, ())
        self.assertEqual(ClassificationSnapshot((observation,), [item]).classifications, (item,))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            Classification("bad", "p", "unknown", "reason")
        with self.assertRaises(ValueError):
            Classification(stable_id("c"), "p", "not-real", "reason")
        with self.assertRaises(ValueError):
            Classification(stable_id("c"), "", "unknown", "reason")

    def test_assessment_extended_references_keep_old_constructor_compatible(self) -> None:
        old = Assessment(stable_id("assessment", "old"), "project", "unknown")
        self.assertEqual(old.classification_ids, ())
        item = Assessment(
            stable_id("assessment", "new"),
            "dimension",
            "satisfied",
            confidence="high",
            metadata={"scope": {"static": True}},
            classification_ids=(stable_id("classification"),),
            observation_ids=(stable_id("observation"),),
            proof_path_ids=(stable_id("proof"),),
        )
        self.assertEqual(AssessmentSnapshot([item]).assessments, (item,))  # type: ignore[arg-type]
        self.assertTrue(item.metadata["scope"]["static"])
        with self.assertRaises(ValueError):
            Assessment(stable_id("assessment", "bad"), "dimension", "unknown", classification_ids=("bad",))


if __name__ == "__main__":
    unittest.main()
