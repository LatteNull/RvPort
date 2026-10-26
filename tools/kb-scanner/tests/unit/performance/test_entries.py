from contextlib import ExitStack
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import runpy
import unittest
from unittest.mock import Mock, patch

from kb_scanner.core import StageResult
from tests.performance import child
from tests import run_performance_tests as entry


class EntryTests(unittest.TestCase):
    def test_child_script_exit_code_is_propagated(self):
        with ExitStack() as stack:
            stack.enter_context(patch("sys.argv", ["child", "/source", "/output"]))
            stack.enter_context(patch("kb_scanner.adapters.cli.StagedContextFactory", return_value=Mock(build=Mock(return_value=StageResult("context")))))
            stack.enter_context(patch("kb_scanner.pipeline.default.create_default_profile"))
            stack.enter_context(patch("tests.performance.observation.observe"))
            stack.enter_context(patch("kb_scanner.pipeline.orchestrator.StagedPipelineRunner", return_value=Mock(run=Mock(return_value=SimpleNamespace(exit_code=2)))))
            stack.enter_context(patch("resource.getrusage", return_value=SimpleNamespace(ru_maxrss=1)))
            stack.enter_context(patch("builtins.print"))
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module("tests.performance.child", run_name="__main__")
            self.assertEqual(2, raised.exception.code)

    def test_child_uses_formal_pipeline_with_optional_profiling(self):
        for profile in (False, True):
            args = ["child", "/source", "/out/report"] + (["--profile"] if profile else [])
            context = StageResult("context")
            runner = Mock()
            runner.run.return_value = SimpleNamespace(exit_code=0)
            with ExitStack() as stack:
                stack.enter_context(patch("sys.argv", args))
                stack.enter_context(patch.object(child, "StagedContextFactory", return_value=Mock(build=Mock(return_value=context))))
                stack.enter_context(patch.object(child, "create_default_profile", return_value="profile"))
                stack.enter_context(patch.object(child, "observe", return_value=SimpleNamespace(analyzer=Mock())))
                stack.enter_context(patch.object(child, "replace", return_value="observed"))
                stack.enter_context(patch.object(child, "StagedPipelineRunner", return_value=runner))
                stack.enter_context(patch.object(child.faulthandler, "dump_traceback_later"))
                cancel = stack.enter_context(patch.object(child.faulthandler, "cancel_dump_traceback_later"))
                stack.enter_context(patch.object(child.resource, "getrusage", return_value=SimpleNamespace(ru_maxrss=9)))
                profiler = stack.enter_context(patch("cProfile.Profile"))
                stack.enter_context(patch("builtins.print"))
                self.assertEqual(0, child.main())
                runner.run.assert_called_once_with("context", ())
                cancel.assert_called_once()
                self.assertFalse(profiler.called)

    def test_profile_dumps_even_on_alarm(self):
        for interrupted in (False, True):
            delegate = Mock()
            delegate.analyze.return_value = "snapshot"
            with patch.object(child.signal, "signal", return_value="old") as register, patch.object(child.signal, "setitimer"), patch("cProfile.Profile") as factory:
                if interrupted:
                    delegate.analyze.side_effect = lambda *_: register.call_args_list[0].args[1](None, None)
                    with self.assertRaises(SystemExit):
                        child.ProfiledAnalyzer(delegate, Path("/tmp/profile")).analyze("ctx")
                else:
                    self.assertEqual("snapshot", child.ProfiledAnalyzer(delegate, Path("/tmp/profile")).analyze("ctx"))
                factory.return_value.dump_stats.assert_called_once_with("/tmp/profile")

    def test_parent_preflight_and_explicit_runs(self):
        for mode in ("normal", "profile", "missing_context", "database", "missing_workspace", "bad_input", "bad_report"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as raw, ExitStack() as stack:
                out = Path(raw) / "output"
                argv = ["benchmark", "--source", "/source", "--output", str(out), "--image-id", "image", "--revision", "rev"]
                if mode == "profile":
                    argv.append("--profile")
                stack.enter_context(patch("sys.argv", argv))
                read_text = Path.read_text
                def read(path, *args, **kwargs):
                    if path.name == "PROVENANCE.json":
                        return json.dumps({"inputManifest": "input-manifest.json", "files": 1, "budget": {"seconds": 300}})
                    if path.name == "input-manifest.json":
                        return json.dumps({"a.c": "fake-digest"})
                    return read_text(path, *args, **kwargs)
                stack.enter_context(patch.object(Path, "read_text", read))
                stack.enter_context(patch.object(Path, "rglob", return_value=iter(())))
                stack.enter_context(patch.object(entry, "runtime_metadata", return_value={"runtime": "fake"}))
                stack.enter_context(patch.object(entry, "verify_limits", return_value={"cpu": 2}))
                context = None if mode == "missing_context" else SimpleNamespace(compile_commands_path="db" if mode == "database" else None)
                stack.enter_context(patch.object(entry, "StagedContextFactory", return_value=Mock(build=Mock(return_value=SimpleNamespace(value=context)))))
                workspace = None if mode == "missing_workspace" else SimpleNamespace(files=("a.c",))
                stack.enter_context(patch.object(entry, "ProjectWorkspaceCollector", return_value=Mock(collect=Mock(return_value=SimpleNamespace(value=workspace)))))
                stack.enter_context(patch.object(entry, "verify_inputs", side_effect=ValueError("bad") if mode == "bad_input" else None, return_value="digest"))
                stack.enter_context(patch.object(entry, "accept_run", return_value={"rss": 1}))
                stack.enter_context(patch.object(entry, "verify_report", side_effect=ValueError("bad") if mode == "bad_report" else None, return_value={"ok": True}))
                def execute(command, events, stderr):
                    events.write(json.dumps({"stage": "fake"}) + "\n")
                    return {"status": "normal", "elapsedSeconds": 1}
                process = stack.enter_context(patch.object(entry, "run_process", side_effect=execute))
                stack.enter_context(patch("builtins.print"))
                if mode not in ("normal", "profile"):
                    with self.assertRaises(ValueError):
                        entry.main()
                else:
                    self.assertEqual(1 if mode == "profile" else 0, entry.main())
                    record = json.loads((out / "performance.json").read_text())
                    self.assertEqual(mode == "normal", record["passed"])
                    self.assertEqual(1 if mode == "profile" else 2, process.call_count)

    def test_parent_merges_base_manifest_without_overlap(self):
        with tempfile.TemporaryDirectory() as raw, ExitStack() as stack:
            out = Path(raw) / "output"
            argv = ["benchmark", "--source", "/source", "--output", str(out), "--image-id", "image", "--revision", "rev"]
            stack.enter_context(patch("sys.argv", argv))
            read_text = Path.read_text
            def read(path, *args, **kwargs):
                if path.name == "PROVENANCE.json":
                    return json.dumps({"inputManifest": "input-manifest.json", "baseInputManifest": "base-input-manifest.json", "files": 1, "budget": {"seconds": 300}})
                if path.name == "input-manifest.json":
                    return json.dumps({"a.c": "fake-digest"})
                if path.name == "base-input-manifest.json":
                    return json.dumps({"b.c": "fake-digest"})
                return read_text(path, *args, **kwargs)
            stack.enter_context(patch.object(Path, "read_text", read))
            stack.enter_context(patch.object(Path, "rglob", return_value=iter(())))
            stack.enter_context(patch.object(entry, "runtime_metadata", return_value={"runtime": "fake"}))
            stack.enter_context(patch.object(entry, "verify_limits", return_value={"cpu": 2}))
            context = SimpleNamespace(compile_commands_path=None)
            stack.enter_context(patch.object(entry, "StagedContextFactory", return_value=Mock(build=Mock(return_value=SimpleNamespace(value=context)))))
            stack.enter_context(patch.object(entry, "ProjectWorkspaceCollector", return_value=Mock(collect=Mock(return_value=SimpleNamespace(value=SimpleNamespace(files=("a.c", "b.c")))))))
            captured = {}
            def fake_verify_inputs(source, files, manifest, provenance):
                captured["manifest"] = manifest
                return "digest"
            stack.enter_context(patch.object(entry, "verify_inputs", side_effect=fake_verify_inputs))
            stack.enter_context(patch.object(entry, "accept_run", return_value={"rss": 1}))
            stack.enter_context(patch.object(entry, "verify_report", return_value={"ok": True}))
            def execute(command, events, stderr):
                events.write(json.dumps({"stage": "fake"}) + "\n")
                return {"status": "normal", "elapsedSeconds": 1}
            process = stack.enter_context(patch.object(entry, "run_process", side_effect=execute))
            stack.enter_context(patch("builtins.print"))
            self.assertEqual(0, entry.main())
            self.assertEqual(2, process.call_count)
            self.assertEqual({"a.c": "fake-digest", "b.c": "fake-digest"}, captured["manifest"])

    def test_parent_rejects_overlapping_base_manifest(self):
        with tempfile.TemporaryDirectory() as raw, ExitStack() as stack:
            out = Path(raw) / "output"
            argv = ["benchmark", "--source", "/source", "--output", str(out), "--image-id", "image", "--revision", "rev"]
            stack.enter_context(patch("sys.argv", argv))
            read_text = Path.read_text
            def read(path, *args, **kwargs):
                if path.name == "PROVENANCE.json":
                    return json.dumps({"inputManifest": "input-manifest.json", "baseInputManifest": "base-input-manifest.json", "files": 1, "budget": {"seconds": 300}})
                if path.name == "input-manifest.json":
                    return json.dumps({"a.c": "fake-digest"})
                if path.name == "base-input-manifest.json":
                    return json.dumps({"a.c": "fake-digest"})
                return read_text(path, *args, **kwargs)
            stack.enter_context(patch.object(Path, "read_text", read))
            stack.enter_context(patch.object(Path, "rglob", return_value=iter(())))
            stack.enter_context(patch.object(entry, "runtime_metadata", return_value={"runtime": "fake"}))
            stack.enter_context(patch.object(entry, "verify_limits", return_value={"cpu": 2}))
            with self.assertRaises(ValueError):
                entry.main()

    def test_parent_module_entrypoint_propagates_parse_failure(self):
        with patch("sys.argv", ["benchmark"]):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module("tests.run_performance_tests", run_name="__main__")
            self.assertEqual(2, raised.exception.code)
