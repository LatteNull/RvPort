"""Real-parser component checks against the independently written source oracle."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_application
from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator
from kb_scanner.projection.v2.models import SchemaV2Report

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/source-evidence-chain"


class SourceChainComponentTests(unittest.TestCase):
    def scan(self, changes=None, version="2.0"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "input"
            root.mkdir()
            for name in ("Makefile", "main.cpp", "wrapper.h"):
                text = (FIXTURE / name).read_text()
                if changes and name in changes:
                    text = changes[name](text)
                (root / name).write_text(text)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            output = Path(temp) / "output"
            with patch("subprocess.run", side_effect=AssertionError("must not execute build tools")):
                result = create_default_application().run(ScanRequest(str(root), str(ROOT / "rulesets/riscv-porting"), str(output), schema_version=version))
            self.assertEqual(0, result.exit_code, result.diagnostics)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            self.assertEqual({"scan-result.json", "scan-report.html", "scan.log"}, {p.name for p in output.iterdir()})
            payload = json.loads((output / "scan-result.json").read_text())
            if version == "2.0":
                V2ReferentialIntegrityValidator().validate(SchemaV2Report.model_validate(payload))
            return payload, (output / "scan-report.html").read_text()

    def intrinsic(self, payload):
        return next(f for f in payload["findings"] if f["fact"]["symbol"] == "_mm256_setzero_si256")

    def test_oracle_actual_source_path_context_spans_and_knowledge_side_branch(self):
        payload, html = self.scan()
        finding = self.intrinsic(payload)
        chain = finding["evidenceChain"]
        self.assertEqual("complete", chain["status"])
        steps = {s["id"]: s for s in chain["steps"]}
        main = [steps[sid] for sid in chain["primaryPath"]]
        self.assertEqual([
            ("Makefile", 6, "$(CPPFLAGS)"),
            ("Makefile", 1, "-DUSE_AVX2=1"), ("Makefile", 6, "$(CXX) $(CPPFLAGS) -c main.cpp -o main.o"),
            ("main.cpp", 4, "defined(USE_AVX2)"), ("main.cpp", 5, "WRAP_OUTER"),
            ("wrapper.h", 2, "WRAP_OUTER"), ("wrapper.h", 2, "WRAP_INNER"),
            ("wrapper.h", 1, "WRAP_INNER"), ("wrapper.h", 1, "_mm256_setzero_si256"),
        ], [(s["source"]["file"], s["source"]["span"]["start"]["line"], s["symbol"]) for s in main])
        pairs = {(e["fromStepId"], e["toStepId"]) for e in chain["edges"]}
        self.assertTrue(all(pair in pairs for pair in zip(chain["primaryPath"], chain["primaryPath"][1:])))
        for step in main:
            source = step["source"]
            lines = {line["line"]: line["text"] for line in source["context"]["lines"]}
            self.assertEqual("complete", source["context"]["status"])
            self.assertTrue(source["context"]["highlights"])
            for hit in source["context"]["highlights"]:
                self.assertTrue(lines[hit["line"]][hit["startColumn"]-1:hit["endColumn"]-1])
        self.assertEqual([], chain["impactStepIds"])
        self.assertFalse({"classification", "assessment", "knowledge_match"} & {s["kind"] for s in main})
        knowledge_edges = [e for e in chain["edges"] if e["kind"] == "matches_knowledge"]
        self.assertTrue(knowledge_edges)
        for edge in knowledge_edges:
            self.assertEqual("_mm256_setzero_si256", steps[edge["fromStepId"]]["symbol"])
            self.assertEqual(64, len(steps[edge["toStepId"]]["knowledge"]["sourceSha256"]))
        self.assertIn(chain["primaryPath"][0], html)

    def test_unused_unknown_other_source_cannot_invent_build_upstream(self):
        for replacement in ("", "$(UNKNOWN)"):
            payload, _ = self.scan({"Makefile": lambda t: t.replace("$(CPPFLAGS) -c", replacement + " -c")})
            chain = self.intrinsic(payload)["evidenceChain"]
            self.assertNotEqual("complete", chain["status"])
            main = [s for s in chain["steps"] if s["id"] in chain["primaryPath"]]
            self.assertFalse(any(s.get("source", {}).get("file") == "Makefile" for s in main))
        payload, _ = self.scan({"Makefile": lambda t: t.replace("main.cpp", "other.cpp")})
        self.assertNotEqual("complete", self.intrinsic(payload)["evidenceChain"]["status"])

    def test_zero_existence_numeric_undef_and_source_override(self):
        for flag, source, expected in (
            ("=0", lambda t: t, "complete"),
            ("=0", lambda t: t.replace("defined(USE_AVX2)", "USE_AVX2"), "inactive"),
            ("=1 -UUSE_AVX2", lambda t: t, "inactive"),
            ("=1", lambda t: t.replace("#if defined", "#undef USE_AVX2\n#if defined"), "inactive"),
        ):
            payload, _ = self.scan({"Makefile": lambda t: t.replace("=1", flag), "main.cpp": source})
            chain = self.intrinsic(payload)["evidenceChain"]
            self.assertEqual(expected, chain["status"])

    def test_explicit_v1_stays_available_and_missing_include_is_partial(self):
        legacy, _ = self.scan(version="1.0")
        self.assertEqual("1.0", legacy["schemaVersion"])
        self.assertNotIn("evidenceChain", legacy["findings"][0])
        payload, _ = self.scan({"main.cpp": lambda t: '#include "missing.h"\n' + t})
        self.assertNotEqual("complete", self.intrinsic(payload)["evidenceChain"]["status"])
