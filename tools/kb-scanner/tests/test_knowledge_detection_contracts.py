from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from kb_scanner.core import CompletionStatus
from kb_scanner.knowledge import GeneratedFactsKnowledgeProvider
from tests.unit.knowledge_detection.support import make_context


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets" / "riscv-porting"


class KnowledgeDetectionContractTests(unittest.TestCase):
    def test_real_manifest_is_explicit_v2_and_preserves_frozen_legacy_hashes(self) -> None:
        payload = json.loads((RULES / "knowledge-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(payload), {"schemaVersion", "catalogId", "version", "sources"})
        self.assertEqual(payload["schemaVersion"], "2.0")
        self.assertNotIn("curatedSets", payload)
        self.assertNotIn("detectors", payload)
        expected = {
            "generated/clang-x86-entries.json": "adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7",
            "generated/gcc-x86-entries.json": "22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191",
        }
        declared = {item["path"]: item["sha256"] for item in payload["sources"]}
        self.assertEqual({path: declared[path] for path in expected}, expected)
        for path, digest in expected.items():
            self.assertEqual(hashlib.sha256((RULES / path).read_bytes()).hexdigest(), digest)
        self.assertEqual({item["kind"] for item in payload["sources"]}, {"legacy-generated", "generated-v2", "curated-v1"})
        self.assertNotIn("audit/candidate-decisions.json", json.dumps(payload))

    def test_real_provider_loads_legacy_and_new_kinds_with_provenance(self) -> None:
        result = GeneratedFactsKnowledgeProvider().load(make_context(ROOT, rule_dir=RULES))
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertTrue({
            "headers", "intrinsics", "builtins", "vectorTypes", "platformMacros", "compilerFlags",
            "assemblyInstructions", "registerNames", "cpuPlatformApis", "targetFeatures", "architectureAliases", "vectorWidthMarkers",
        } <= {item.fact_kind for item in result.value.entries})
        self.assertEqual(len(result.value.sources), 6)
        legacy = [item for item in result.value.sources if item.source_id in {"clang-x86-entries", "gcc-x86-entries"}]
        self.assertTrue(all(item.kind == "generated-json" and "originalSource" in item.metadata for item in legacy))
        add = next(item for item in result.value.entries if item.fact_kind == "assemblyInstructions" and item.canonical_value == "add")
        self.assertEqual(len(add.source_ids), 2)

    def test_behavior_matrix_is_requirement_driven_and_records_curated_gap(self) -> None:
        payload = json.loads((RULES / "behavior-acceptance.json").read_text(encoding="utf-8"))
        allowed = {
            "generated-fact-local", "structural-candidate", "needs-curated-knowledge", "needs-graph",
            "needs-build", "needs-packaging", "needs-classification", "generated-knowledge-local",
            "curated-knowledge-local", "knowledge-backed-candidate",
            "graph-backed", "classification-backed", "external-validation-deferred",
        }
        capabilities = payload["capabilities"]
        self.assertEqual(len({item["id"] for item in capabilities}), len(capabilities))
        self.assertTrue(all(item["status"] in allowed and item["reason"] for item in capabilities))
        self.assertFalse(any(item["status"] == "needs-curated-knowledge" for item in capabilities))
        self.assertTrue(any(item["status"] == "curated-knowledge-local" for item in capabilities))
        self.assertNotIn("legacyRuleId", json.dumps(payload))
        plan = (ROOT / "docs" / "knowledge.md").read_text(encoding="utf-8")
        self.assertIn("curated/x86-migration-semantics.json", plan)
        self.assertIn("accepted entries only", plan)

    def test_new_provider_and_detector_sources_do_not_import_legacy_or_yaml(self) -> None:
        files = [
            ROOT / "kb_scanner" / "knowledge" / "provider.py",
            ROOT / "kb_scanner" / "detectors" / "definitions.py",
            ROOT / "kb_scanner" / "detectors" / "matchers.py",
            ROOT / "kb_scanner" / "detectors" / "local.py",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for forbidden in ("import yaml", "from yaml", "kb_scanner.rules", "..rules", "Legacy", "Finding", "Assessment("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)

    def test_core_contracts_do_not_depend_on_parsers_validation_or_legacy_models(self) -> None:
        files = [
            ROOT / "kb_scanner" / "core" / "knowledge.py",
            ROOT / "kb_scanner" / "core" / "facts.py",
            ROOT / "kb_scanner" / "core" / "results.py",
            ROOT / "kb_scanner" / "core" / "observations.py",
            ROOT / "kb_scanner" / "core" / "protocols.py",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for forbidden in (
            "pydantic",
            "tree_sitter",
            "import yaml",
            "from yaml",
            "kb_scanner.models",
            "Legacy",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
