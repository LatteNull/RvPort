from __future__ import annotations

import collections
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kb_scanner.compatibility.differential import normalize_payload, validate_ledger
from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_application


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets/riscv-porting"
BASELINES = ROOT / "tests/fixtures/compatible-cutover"


def run(app, fixture: Path) -> tuple[object, dict]:
    output = Path(tempfile.mkdtemp(prefix="kb-cutover-"))
    result = app.run(ScanRequest(str(fixture), str(RULES), str(output), schema_version="1.0"))
    return result, json.loads((output / "scan-result.json").read_text())


def fixture_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def semantic_signature(payload: dict, result: object, fixture: Path) -> dict:
    normalized = normalize_payload(payload, (str(fixture),))
    semantic_findings = [
        {
            key: finding.get(key)
            for key in (
                "rule_id", "finding_type", "severity", "is_blocking", "is_actionable",
                "file", "line", "column", "reason", "suggestion", "trace",
            )
        }
        for finding in normalized["findings"]
    ]
    serialized_findings = json.dumps(semantic_findings, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    diagnostics = normalized["diagnostics"]
    serialized_diagnostics = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    summary = {
        key: normalized["summary"][key]
        for key in (
            "files", "findings", "issues", "hints", "blocking", "portabilityGaps",
            "inactiveOrGuarded", "referenceSources", "references",
        )
    }
    readiness = normalized["summary"].get("readiness")
    if readiness is not None:
        summary["readiness"] = {
            key: readiness[key]
            for key in ("state", "confidence", "staticScopeOnly", "compiled", "testsExecuted")
        }
    return {
        "exitCode": result.exit_code,
        "artifacts": [item.name for item in result.artifacts],
        "summary": summary,
        "ruleCounts": dict(sorted(collections.Counter(item["rule_id"] for item in normalized["findings"]).items())),
        "findingTypeCounts": dict(sorted(collections.Counter(item["finding_type"] for item in normalized["findings"]).items())),
        "severityCounts": dict(sorted(collections.Counter(item["severity"] for item in normalized["findings"]).items())),
        "blocking": sum(bool(item["is_blocking"]) for item in normalized["findings"]),
        "actionable": sum(bool(item["is_actionable"]) for item in normalized["findings"]),
        "semanticFindingsSha256": hashlib.sha256(serialized_findings).hexdigest(),
        "diagnosticsSha256": hashlib.sha256(serialized_diagnostics).hexdigest(),
    }


class CompatibleCutoverDifferentialTests(unittest.TestCase):
    def test_reviewed_ledger_has_no_blocker_and_covers_every_changed_fixture(self) -> None:
        ledger = json.loads((BASELINES / "differential-ledger.json").read_text())
        self.assertEqual((), validate_ledger(ledger))
        self.assertFalse(any(item["status"] == "deferred-blocking" for item in ledger["decisions"]))
        matrix = json.loads((BASELINES / "matrix-differential-golden-v1.json").read_text())
        reviewed = {item["fixture"] for item in ledger["decisions"]}
        for entry in matrix["entries"]:
            if entry["legacy"] != entry["staged"]:
                self.assertIn(entry["id"], reviewed)

    def test_every_matrix_entry_matches_reviewed_staged_signature_without_executing_legacy(self) -> None:
        active = json.loads((BASELINES / "fixture-matrix.json").read_text())["fixtures"]
        active_ids = {item["id"] for item in active}
        self.assertEqual(5, len(active_ids))
        current = json.loads((ROOT / "tests/fixtures/open-source-regression-baseline.json").read_text())["matrix"]
        self.assertEqual(active_ids, set(current))
        for entry in active:
            fixture = Path(entry["path"])
            if not fixture.is_absolute():
                fixture = ROOT / fixture
            with self.subTest(fixture=entry["id"]):
                self.assertTrue(fixture.is_dir())
                before = fixture_digest(fixture)
                new_result, new = run(create_default_application(), fixture)
                self.assertEqual(before, fixture_digest(fixture))
                self.assertEqual("1.0", new["schemaVersion"])
                self.assertEqual(current[entry["id"]], semantic_signature(new, new_result, fixture))


if __name__ == "__main__":
    unittest.main()
