from __future__ import annotations

import copy
import unittest

from kb_scanner.core import Classification, Observation, stable_id
from kb_scanner.detectors.definitions import DEFAULT_DEFINITIONS
from kb_scanner.projection.contract import FINDING_FIELDS, ProjectionContractError, validate_payload
from kb_scanner.projection.policy import ProjectionPolicy

from .support import payload


class ContractPolicyTests(unittest.TestCase):
    def test_valid_payload_and_static_readiness(self) -> None:
        value = payload()
        validate_payload(value)
        value["summary"]["readiness"] = {
            "state": "needs_review", "confidence": "medium", "dimensions": {}, "blockingDimensions": [],
            "completeness": {}, "staticScopeOnly": True, "compiled": False, "testsExecuted": False, "trace": {},
        }
        validate_payload(value)

    def test_contract_rejects_shape_types_and_mirrors(self) -> None:
        cases = []
        changed = payload(); changed["schemaVersion"] = "2.0"; cases.append(changed)
        changed = payload(); changed["extra"] = 1; cases.append(changed)
        changed = payload(); changed["summary"]["files"] = True; cases.append(changed)
        changed = payload(); changed["findings"] = {}; cases.append(changed)
        changed = payload(); changed["tool"] = []; cases.append(changed)
        finding = {name: None for name in FINDING_FIELDS}
        finding.update({"file": "a.c", "line": 1, "column": 2, "snippet": "x", "trace": {}, "location": {"file": "bad", "line": 1, "column": 2}, "context": {"snippet": "x"}})
        changed = payload(); changed["findings"] = [finding]; cases.append(changed)
        changed = payload(); changed["summary"]["readiness"] = {"state": "ready"}; cases.append(changed)
        changed = payload(); changed["summary"]["readiness"] = {
            "state": "ready", "confidence": "high", "dimensions": {}, "blockingDimensions": [], "completeness": {},
            "staticScopeOnly": False, "compiled": True, "testsExecuted": True, "trace": {},
        }; cases.append(changed)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ProjectionContractError):
                validate_payload(value)

    def test_policy_maps_all_detectors_and_impacts(self) -> None:
        policy = ProjectionPolicy()
        self.assertEqual((), policy.validate_completeness())
        self.assertIn("C_CPP.X86.INTRINSIC_CALL", policy.rule_ids)
        for detector in tuple(DEFAULT_DEFINITIONS) + ("BUILD.SELECTION", "TEST.SELECTION"):
            obs = Observation(stable_id("o", detector), detector, "x86_comment_hint" if "COMMENT" in detector else "riscv_test_coverage_gap" if detector == "TEST.SELECTION" else "x86_intrinsic_reference")
            for impact, severity in (("blocking_issue", "high"), ("actionable_non_blocking", "medium"), ("guarded_inactive", "low"), ("hint", "info"), ("unknown", "medium")):
                classification = Classification(stable_id("c", detector, impact), "p", impact, "because", (obs.id,))
                self.assertEqual(severity, policy.fields(obs, classification)["severity"])
                self.assertTrue(policy.present(obs, classification).rule_id)

    def test_policy_rejects_identity_and_unmapped_detector(self) -> None:
        for args in (("", 1), ("x", 0)):
            with self.assertRaises(ValueError):
                ProjectionPolicy(*args)
        obs = Observation(stable_id("o", "unknown"), "UNKNOWN", "unknown")
        cls = Classification(stable_id("c", "unknown"), "p", "unknown", "reason", (obs.id,))
        with self.assertRaisesRegex(ValueError, "unmapped detector"):
            ProjectionPolicy().present(obs, cls)


if __name__ == "__main__":
    unittest.main()
