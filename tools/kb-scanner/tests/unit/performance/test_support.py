from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from kb_scanner.core import StageResult, CompletionStatus
from tests.performance.observation import counts, observe, ObservedStage
from tests.performance.support import (
    ARTIFACTS, accept_run, digest, run_process, runtime_metadata, verify_inputs, verify_report, verify_limits,
)


class ObservationTests(unittest.TestCase):
    def test_transparent_calls_empty_and_populated_counts(self):
        events = []
        arg = SimpleNamespace(files=(1, 2, 3))
        result = StageResult(SimpleNamespace(evidence=(1, 2)))
        original = Mock(return_value=result)
        stage = ObservedStage("frontend", SimpleNamespace(analyze=original), events.append, iter((1, 4)).__next__)
        self.assertIs(result, stage.analyze(arg, flag=True))
        original.assert_called_once_with(arg, flag=True)
        self.assertEqual([{"files": 3}], events[0]["input"])
        self.assertEqual({"flag": {}}, events[0]["keywordInput"])
        self.assertEqual({"evidence": 2}, events[1]["output"])
        self.assertEqual(3, events[1]["elapsedSeconds"])
        self.assertEqual({}, counts(None))

    def test_error_and_profile_wrapping(self):
        events = []
        error = ValueError("injected")
        @dataclass(frozen=True)
        class Profile:
            normalizer: object
        delegate = SimpleNamespace(normalize=Mock(side_effect=error))
        profile = Profile(delegate)
        wrapped = observe(profile, events.append)
        self.assertIs(profile.normalizer, delegate)
        with self.assertRaises(ValueError) as raised:
            wrapped.normalizer.normalize(None)
        self.assertIs(error, raised.exception)
        self.assertEqual("error", events[-1]["event"])


class PerformanceSupportTests(unittest.TestCase):
    def test_input_digest_sets_bytes_and_escape(self):
        root = Path("/fixture")
        manifest = {"a.c": hashlib.sha256(b"ok").hexdigest()}
        provenance = {"files": 1, "manifestDigest": digest(manifest)}
        self.assertEqual(digest(manifest), verify_inputs(root, ("a.c",), manifest, provenance, lambda _: b"ok"))
        for files, source, meta, content in (
            ((), manifest, provenance, b"ok"),
            (("a.c",), manifest, {}, b"ok"),
            (("a.c",), manifest, provenance, b"bad"),
            (("../a.c",), {"../a.c": manifest["a.c"]}, {"files": 1, "manifestDigest": digest({"../a.c": manifest["a.c"]})}, b"ok"),
        ):
            with self.assertRaises(ValueError):
                verify_inputs(root, files, source, meta, lambda _: content)
        with self.assertRaises(FileNotFoundError):
            verify_inputs(root, ("a.c",), manifest, provenance, Mock(side_effect=FileNotFoundError()))

    def test_runtime_identity_is_required(self):
        result = runtime_metadata(lambda _: "1", lambda _: b"facts", "image", "revision", (Path("a.py"),))
        self.assertEqual(3, len(result["knowledge"]))
        for image, revision, version in (("", "rev", "1"), ("img", "", "1"), ("img", "rev", "")):
            with self.assertRaises(ValueError):
                runtime_metadata(lambda _: version, lambda _: b"", image, revision)
        with self.assertRaises(FileNotFoundError):
            runtime_metadata(lambda _: "1", Mock(side_effect=FileNotFoundError()), "img", "rev")

    def test_actual_container_limits_not_just_declared_budget(self):
        values = {"cpu.max": "200000 100000", "memory.max": "2147483648", "memory.swap.max": "0"}
        self.assertEqual(2, verify_limits(lambda path: values[path.name])["cpu"])
        for key, value in (("cpu.max", "max 100000"), ("cpu.max", "100000 100000"), ("cpu.max", ""),
                           ("memory.max", "max"), ("memory.swap.max", "100")):
            invalid = {**values, key: value}
            with self.assertRaises(ValueError):
                verify_limits(lambda path: invalid[path.name])
        def legacy(path):
            data = {"cpu.cfs_quota_us": "200000", "cpu.cfs_period_us": "100000",
                    "memory.limit_in_bytes": "2147483648", "memory.memsw.limit_in_bytes": "2147483648"}
            if path.name not in data:
                raise FileNotFoundError()
            return data[path.name]
        self.assertEqual(0, verify_limits(legacy)["swapBytes"])

    def test_process_exit_classification_and_timeout(self):
        for code, status in ((0, "normal"), (2, "nonzero"), (-11, "native-signal"), (139, "native-signal"), (137, "nonzero")):
            execute = Mock(return_value=SimpleNamespace(returncode=code))
            result = run_process(["scanner"], "out", "err", execute=execute, clock=iter((1, 3)).__next__)
            self.assertEqual(status, result["status"])
            self.assertEqual(2, result["elapsedSeconds"])
            self.assertEqual(300, execute.call_args.kwargs["timeout"])
        execute = Mock(side_effect=subprocess.TimeoutExpired(["scanner"], 300))
        self.assertEqual("timeout", run_process([], None, None, execute=execute)["status"])

    def test_report_artifacts_schema_input_count_and_validator(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            with self.assertRaises(ValueError):
                verify_report(output, 2, load=Mock())
            for name in ARTIFACTS:
                (output / name).write_text("")
            payload = {"schemaVersion": "2.0", "summary": {"files": 2}, "findings": []}
            (output / "scan-result.json").write_text(json.dumps(payload))
            validate = Mock()
            self.assertEqual(0, verify_report(output, 2, load=validate)["findings"])
            validate.assert_called_once_with(payload)
            with self.assertRaises(ValueError):
                verify_report(output, 3, load=validate)
            with self.assertRaises(ValueError):
                verify_report(output, 2, load=Mock(side_effect=ValueError()))
            with patch("kb_scanner.projection.v2.models.SchemaV2Report.model_validate", return_value="model"), patch("kb_scanner.projection.v2.validation.V2ReferentialIntegrityValidator.validate") as validator:
                verify_report(output, 2)
                validator.assert_called_once_with("model")

    def test_acceptance_requires_every_stage_resources_and_budget(self):
        stages = ("workspace_collector", "knowledge_provider", "frontend", "normalizer", "analyzer", "detector", "classifier", "assessor", "report_projector")
        events = [{"event": "end", "stage": x, "output": {"files": 810}} for x in stages]
        resource = {"event": "resource", "maxRssKiB": 512, "exitCode": 0}
        outcome = {"status": "normal", "elapsedSeconds": 20}
        self.assertEqual(resource, accept_run(outcome, events + [resource], 810))
        for result, trace, size in (
            ({**outcome, "status": "timeout"}, events, 810),
            ({**outcome, "elapsedSeconds": 300}, events, 810),
            (outcome, [], 810), (outcome, events, 810),
            (outcome, events + [resource], 9),
            (outcome, events + [{**resource, "maxRssKiB": None}], 810),
        ):
            with self.assertRaises(ValueError):
                accept_run(result, trace, size)
