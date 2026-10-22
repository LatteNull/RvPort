"""Real Bash grammar / pipeline checks. Never counted as isolated unit coverage."""
import json
from hashlib import sha256
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from kb_scanner.core import ScanRequest
from kb_scanner.frontends.build.autoconf.flow import Evaluator
from kb_scanner.frontends.build.autoconf.syntax import parse
from kb_scanner.frontends.build.autoconf.project import analyze_project
from kb_scanner.pipeline.default import create_default_application
from tests.schema_v2_contract import reference_errors


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("cpu=$(uname -m)\ncase $cpu in x86*) exit 1;; riscv*) echo riscv64-unknown-linux-gnu;; *) exit 1;; esac", "accepted"),
    ("cpu=`uname -m`\ncase $cpu in *) exit 1;; riscv*) exit 0;; esac", "rejected"),
    ("cpu=$(uname -m)\ncase $cpu in riscv64) echo error; exit 1;; *) exit 0;; esac", "rejected"),
    ("cpu=$(uname -m)\ncase $cpu in *) echo ${cpu}-unknown-linux-gnu;; esac", "accepted"),
    ("exit 0", "unknown"),
    ("os=$(uname -s)\ncase $os in Linux) echo riscv64-unknown-linux-gnu;; *) exit 1;; esac", "unknown"),
    ("cpu=$(uname -m)\nif test x$cpu = xriscv64; then echo riscv64-unknown-linux-gnu; else exit 1; fi", "accepted"),
    ("if [ a != a ]; then exit 1; elif [ a = a ]; then echo riscv64-unknown-linux-gnu; else exit 1; fi", "accepted"),
    ("cpu=riscv64-unknown-linux-gnu\nbasic=${cpu%%-*}\nprintf '%s\\n' \"$basic-unknown-linux-gnu\"", "accepted"),
    ("eval 'touch /tmp/autoconf-forbidden-marker'\necho riscv64-unknown-linux-gnu", "unknown"),
    ("while true; do :; done\necho riscv64-unknown-linux-gnu", "unknown"),
    ("case x in", "unknown"),
)


class AutoconfTargetComponentTests(unittest.TestCase):
    def test_pinned_gnu_scripts_and_real_libarchive_input_are_conservative(self):
        root = ROOT / "tests/fixtures/autoconf-target"
        oracle = json.loads((root / "oracle.json").read_text())
        for version, expected in oracle["gnu"].items():
            for name in ("config.guess", "config.sub"):
                path = root / "gnu" / version / name
                data = path.read_bytes()
                self.assertEqual(sha256(data).hexdigest(), expected[name])
                self.assertEqual("riscv" in data.decode(), expected["riscvLiteralPresent"])
                result = analyze_project({name: data.decode()}, "riscv64")[name]
                terminal = [r for r in result.records if r.metadata["autoconf"].get("outcome")]
                self.assertTrue(terminal)
                self.assertTrue(all(r.metadata["autoconf"]["outcome"] == expected["expected"] for r in terminal))
                self.assertEqual(result.diagnostics, (expected["reason"],))
                self.assertLess(len(result.records), 2000)
        data = (root / "libarchive/configure.ac").read_bytes()
        self.assertEqual(sha256(data).hexdigest(), oracle["libarchive"]["configure.ac"])
        result = analyze_project({"configure.ac": data.decode()}, "riscv64")["configure.ac"]
        declarations = {r.metadata["autoconf"]["declaration"]: r for r in result.records if "declaration" in r.metadata["autoconf"]}
        self.assertEqual(declarations["AC_CANONICAL_HOST"].line, 92)
        self.assertEqual(declarations["AC_CONFIG_AUX_DIR"].line, 26)
        self.assertIn(oracle["libarchive"]["reason"], result.diagnostics)

    def test_real_grammar_matches_independent_small_oracle(self):
        for text, expected in CASES:
            with self.subTest(text=text):
                src = parse(text, "config.guess")
                engine = Evaluator({src.path: src}, "riscv64", src.path)
                with patch("subprocess.run", side_effect=AssertionError("project execution forbidden")):
                    outcome = engine.run(src.path)
                self.assertEqual(outcome.status, expected, outcome)
        self.assertFalse(Path("/tmp/autoconf-forbidden-marker").exists())

    def scan(self, files, version="2.0", compile_commands=False):
        with tempfile.TemporaryDirectory() as temporary:
            source_root, output = Path(temporary) / "source", Path(temporary) / "out"
            source_root.mkdir()
            for name, text in files.items():
                path = source_root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            database = None
            if compile_commands:
                (source_root / "main.c").write_text("int main(void) { return 0; }\n")
                database = source_root / "compile_commands.json"
                database.write_text(json.dumps([{"directory": str(source_root), "file": "main.c", "arguments": ["cc", "-m64", "-c", "main.c"]}]))
            before = {str(p.relative_to(source_root)): p.read_bytes() for p in source_root.rglob("*") if p.is_file()}
            request = ScanRequest(str(source_root), str(ROOT / "rulesets/riscv-porting"), str(output), schema_version=version,
                                  **({"compile_commands_path": str(database)} if database else {}))
            with patch("subprocess.run", side_effect=AssertionError("project execution forbidden")):
                result = create_default_application().run(request)
            self.assertEqual(result.exit_code, 0, result.diagnostics)
            self.assertEqual(before, {str(p.relative_to(source_root)): p.read_bytes() for p in source_root.rglob("*") if p.is_file()})
            self.assertEqual({p.name for p in output.iterdir()}, {"scan-result.json", "scan-report.html", "scan.log"})
            payload = json.loads((output / "scan-result.json").read_text())
            if version == "2.0":
                schema = json.loads((ROOT / "schemas/scan-result-v2.schema.json").read_text())
                self.assertEqual(list(Draft202012Validator(schema).iter_errors(payload)), [])
                self.assertEqual(reference_errors(payload), [])
            return payload

    def test_cross_file_rejection_source_chain_context_and_unchanged_v1_v2(self):
        padding = "".join(f"# context {i}\n" for i in range(25))
        files = {"configure": padding + 'cpu=$(./config.guess)\nhost=$(./config.sub "$cpu")\nexit\n' + padding,
                 "config.guess": 'cpu=$(uname -m)\necho "$cpu-unknown-linux-gnu"\n',
                 "config.sub": 'case "$1" in riscv*) exit 1;; *) exit 0;; esac\n'}
        payload = self.scan(files)
        found = [f for f in payload["findings"] if f["fact"]["primaryLocation"]["file"] == "configure"]
        self.assertTrue(found)
        self.assertEqual(len(payload["findings"]), 1)
        finding = found[0]
        chain = finding["evidenceChain"]
        locations = {step["source"]["file"] for step in chain["steps"] if step.get("source")}
        self.assertTrue({"configure", "config.guess", "config.sub"} <= locations, locations)
        self.assertFalse({"classification", "assessment"} & {step["kind"] for step in chain["steps"]})
        self.assertTrue(finding["conclusion"]["suggestion"])
        self.assertTrue(finding["conclusion"]["suggestion_en"])
        self.assertEqual(len(finding["fact"]["extensions"]["org.rvport.kb-scanner.autoconf"]["digest"]), 64)
        self.assertEqual(chain["status"], "complete")
        self.assertTrue(finding["conclusion"]["actionable"])
        self.assertFalse(finding["conclusion"]["blocking"])
        location = finding["fact"]["primaryLocation"]
        self.assertEqual(len(location["context"]["lines"]), 41)
        self.assertTrue(location["context"]["highlights"])
        legacy = self.scan(files, "1.0")
        self.assertEqual(legacy["schemaVersion"], "1.0")
        self.assertNotIn("evidenceChain", legacy["findings"][0])

    def test_no_autoconf_generated_from_compile_database_and_target_environment_not_leaked(self):
        self.assertTrue(all(item["fact"]["primaryLocation"]["file"] == "compile_commands.json" for item in self.scan({}, compile_commands=True)["findings"]))
        files = {"configure": 'cpu=$(uname -m)\ncase "$cpu" in riscv64) exit 0;; *) exit 1;; esac\n'}
        self.assertFalse(any(item["fact"]["primaryLocation"]["file"] == "configure" for item in self.scan(files, compile_commands=True)["findings"]))
        unknown = self.scan({"configure.ac": "AC_CANONICAL_HOST\nAC_CONFIG_AUX_DIR([missing])\n"})
        self.assertTrue(unknown["findings"])
        self.assertTrue(all(item["conclusion"]["status"] == "unknown" for item in unknown["findings"]))
