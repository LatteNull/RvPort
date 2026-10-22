from __future__ import annotations

import json
import unittest
from pathlib import Path

from kb_scanner.core import AnalysisSnapshot


ROOT = Path(__file__).resolve().parents[1]


class EvidenceGraphContractTests(unittest.TestCase):
    def test_analysis_snapshot_defaults_do_not_create_a_report_contract(self) -> None:
        snapshot = AnalysisSnapshot()
        self.assertEqual((snapshot.entities, snapshot.relations, snapshot.proof_paths), ((), (), ()))
        self.assertFalse((ROOT / "scan-graph.json").exists())

    def test_behavior_matrix_tracks_graph_classification_and_external_validation_boundaries(self) -> None:
        payload = json.loads((ROOT / "rulesets" / "riscv-porting" / "behavior-acceptance.json").read_text(encoding="utf-8"))
        statuses = {item["id"]: item["status"] for item in payload["capabilities"]}
        self.assertEqual(statuses["macro-and-alternative-reachability"], "graph-backed")
        self.assertEqual(statuses["build-source-selection"], "graph-backed")
        self.assertEqual(statuses["rpm-packaging-selection"], "graph-backed")
        self.assertEqual(statuses["test-role-and-selection"], "classification-backed")
        self.assertEqual(statuses["blocking-severity-readiness"], "classification-backed")
        self.assertEqual(statuses["real-riscv-build-and-test"], "external-validation-deferred")

    def test_networkx_is_locked_only_in_standalone_test_dependency_path(self) -> None:
        runtime = (ROOT / "requirements" / "runtime.lock").read_text(encoding="utf-8")
        dockerfile = (ROOT / "Dockerfile.test").read_text(encoding="utf-8")
        compose = (ROOT / "compose.test.yml").read_text(encoding="utf-8")
        self.assertIn("networkx==3.6.1", runtime)
        self.assertIn("target: kb-scanner-test", compose)
        self.assertIn("COPY tools/kb-scanner", dockerfile)
        self.assertNotIn("backend/Dockerfile", dockerfile)


if __name__ == "__main__":
    unittest.main()
