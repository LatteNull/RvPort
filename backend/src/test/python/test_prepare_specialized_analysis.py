import argparse
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace, ModuleType
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "main" / "resources" / "analysis" / "prepare_specialized_analysis.py"
SPEC = importlib.util.spec_from_file_location("prepare_specialized_analysis", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrepareSpecializedAnalysisTests(unittest.TestCase):
    def test_source_and_artifact_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "a.c"
            source.write_text("int a;", encoding="utf-8")
            digest = MODULE.sha256(source)
            self.assertEqual(MODULE.optional_verified_source(root, "a.c", digest), source)
            self.assertIsNone(MODULE.optional_verified_source(root, "missing.c", digest))
            for name, expected in (("../escape", digest), ("a.c", "wrong"), ("a.c", "0" * 64)):
                with self.assertRaises(ValueError):
                    MODULE.optional_verified_source(root, name, expected)
            (root / "dir").mkdir()
            with self.assertRaises(ValueError):
                MODULE.optional_verified_source(root, "dir", digest)
            for name in ("../escape", "missing", "dir"):
                with self.assertRaises(ValueError):
                    MODULE.safe(root, name)
            artifact = {"path": "a.c", "sha256": digest, "bytes": source.stat().st_size}
            self.assertEqual(MODULE.verified_artifact(root, artifact), source)
            for change in ({"bytes": None}, {"bytes": 0}, {"sha256": "bad"}, {"sha256": "0" * 64}):
                with self.assertRaises(ValueError):
                    MODULE.verified_artifact(root, {**artifact, **change})

    def test_fp_adapter_preserves_context_identity_and_failures(self):
        compilation = ModuleType("floating_point_precision_scanner.compilation")
        context = SimpleNamespace(file="a.c", language="c", context_id="ctx", physical_tu_id="tu",
                                  target="x86_64-pc-linux-gnu", abi={})
        compilation.load_compilation_plan = lambda request: SimpleNamespace(contexts=[context])
        with patch.dict("sys.modules", {"floating_point_precision_scanner.compilation": compilation}), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "a.c"
            source.write_text("int a;")
            db = root / "compile_commands.json"
            db.write_text(json.dumps([{"file": str(source), "directory": str(root), "arguments": ["gcc", "-c", str(source)]}]))
            bc = root / "a.bc"
            bc.write_bytes(b"fixture")
            args = argparse.Namespace(manifest=None, compile_database=db, source_root=root, cache=root,
                                      artifact_root=root, run_id="run", source_revision="revision", build_run="build",
                                      timeout=60, max_frontend_output_bytes=1024, output=root / "request.json")
            MODULE.fp(args)
            self.assertNotIn("bitcode_artifact_set", json.loads(args.output.read_text()))
            args.manifest = root / "platform.json"
            record = {"source": {"path": "a.c"}, "language": "c", "context_id": "ctx", "artifact_key": "key",
                      "status": "produced", "profile": {"name": "custom", "version": "1"},
                      "bitcode": {"path": "a.bc", "bytes": bc.stat().st_size, "sha256": MODULE.sha256(bc)}}
            for profile in ("custom", "build-faithful", "source-preserving"):
                record["profile"]["name"] = profile
                args.manifest.write_text(json.dumps({"artifact_set_id": "set", "records": [record, {"source": {"path": "missing.c"}}]}))
                MODULE.fp(args)
                result = json.loads((root / "fp-manifest.json").read_text())
                self.assertEqual(result["members"][0]["context_id"], "ctx")
                self.assertEqual(result["members"][0]["profile"], profile if profile != "custom" else "source-preserving")
                self.assertEqual(result["counts"]["completed"], 1)
            record.update(status="failed", bitcode=None)
            args.manifest.write_text(json.dumps({"artifact_set_id": "set", "records": [record]}))
            MODULE.fp(args)
            self.assertEqual(json.loads((root / "fp-manifest.json").read_text())["counts"]["failed"], 1)
            other = SimpleNamespace(**{**vars(context), "context_id": "other"})
            compilation.load_compilation_plan = lambda request: SimpleNamespace(contexts=[context, other])
            MODULE.fp(args)
            record["context_id"] = "unknown"
            args.manifest.write_text(json.dumps({"artifact_set_id": "set", "records": [record]}))
            with self.assertRaisesRegex(ValueError, "无法唯一匹配"):
                MODULE.fp(args)

    def test_localization_and_cli_reject_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.c").write_text("int a;")
            db = root / "compile_commands.json"
            args = argparse.Namespace(compile_database=db, source_root=root, cache=root)
            for value in ({}, [None, {"file": "/missing.c"}],
                          [{"directory": "/other", "file": "/remote/a.c"}]):
                db.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    MODULE.localized_compile_database(args)
            db.write_text(json.dumps([{"directory": "/remote", "file": "/remote/a.c", "extra": 1},
                                       {"directory": "/ignored", "file": "/ignored/a.c"}]))
            localized = MODULE.localized_compile_database(args)
            self.assertEqual(json.loads(localized.read_text())[0]["extra"], 1)
            self.assertEqual(args.remote_source_root, "/remote")
            db.write_text(json.dumps([{"directory": "/remote/../../outside", "file": "/remote/a.c"}]))
            with self.assertRaisesRegex(ValueError, "越出"):
                MODULE.localized_compile_database(args)
        cli = MODULE.parser().parse_args(["floating", "--source-root", "/src", "--compile-database", "/db",
                "--output", "/out", "--run-id", "run", "--source-revision", "revision", "--build-run", "build", "--cache", "/cache"])
        self.assertEqual(cli.mode, "floating")
        self.assertEqual(cli.timeout, 3600)

    def test_localization_uses_complete_compile_database_without_bc_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "a.c").write_text("int a;", encoding="utf-8")
            (source / "b.c").write_text("int b;", encoding="utf-8")
            database = root / "compile_commands.json"
            database.write_text(json.dumps([
                {"directory": "/remote/repo", "file": "/remote/repo/a.c",
                 "arguments": ["cc", "-std=c89", "-c", "/remote/repo/a.c"]},
                {"directory": "/remote/repo", "file": "/remote/repo/b.c",
                 "arguments": ["cc", "-std=c99", "-c", "/remote/repo/b.c"]},
            ]), encoding="utf-8")
            cache = root / "cache"
            cache.mkdir()
            localized = MODULE.localized_compile_database(argparse.Namespace(
                compile_database=database, source_root=source, cache=cache))
            records = json.loads(localized.read_text(encoding="utf-8"))
            self.assertEqual([Path(item["file"]).name for item in records], ["a.c", "b.c"])
            self.assertIn("-std=c89", records[0]["arguments"])

    def test_ast_only_platform_preserves_legacy_standard_and_stable_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "legacy.c"
            source.write_text("int main(void){return 0;}", encoding="utf-8")
            records = [{"directory": str(root), "file": str(source),
                        "arguments": ["cc", "-std=gnu99", "-c", str(source)]}]
            first = MODULE.synthetic_platform(records, root)
            second = MODULE.synthetic_platform(records, root)
            self.assertEqual(first["artifact_set_id"], second["artifact_set_id"])
            self.assertEqual(first["records"][0]["standard"], "c99")
            self.assertEqual(first["records"][0]["dialect"], "gnu")
            self.assertEqual(first["records"][0]["standard_option"], "-std=gnu99")
            self.assertEqual(first["records"][0]["status"], "missing")

    def test_ast_only_platform_isolates_unknown_standard_and_preserves_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unknown = root / "unknown.c"
            default = root / "default.cpp"
            unknown.write_text("int unknown(void){return 0;}", encoding="utf-8")
            default.write_text("int main(){return 0;}", encoding="utf-8")
            records = [
                {"directory": str(root), "file": str(unknown),
                 "arguments": ["cc", "-std=vendor-c", "-c", str(unknown)]},
                {"directory": str(root), "file": str(default),
                 "arguments": ["c++", "-c", str(default)]},
            ]

            platform = MODULE.synthetic_platform(records, root)

            self.assertEqual(len(platform["records"]), 2)
            by_source = {item["source"]["path"]: item for item in platform["records"]}
            self.assertEqual(by_source["unknown.c"]["standard"], "unsupported")
            self.assertEqual(by_source["unknown.c"]["standard_option"], "-std=vendor-c")
            self.assertEqual(by_source["default.cpp"]["standard"], "compiler-default")
            self.assertEqual(by_source["default.cpp"]["standard_source"], "compiler-default")
            self.assertIsNone(by_source["default.cpp"]["standard_option"])

    def test_legacy_projects_preserve_ast_denominator_across_complete_partial_and_missing_bc(self):
        for mode, produced_count in (("complete", 4), ("partial", 2), ("missing", 0)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source_root = root / "source"
                source_root.mkdir()
                (source_root / "shared.h").write_text("/* project header */\n", encoding="utf-8")
                entries = []
                standards = (("legacy89.c", "c89"), ("legacy99.c", "c99"),
                             ("legacy98.cpp", "c++98"), ("legacy03.cpp", "c++03"))
                for name, standard in standards:
                    source = source_root / name
                    source.write_text("int legacy(void){return 0;}\n", encoding="utf-8")
                    entries.append({"directory": str(source_root), "file": str(source),
                                    "arguments": ["c++" if name.endswith("cpp") else "cc",
                                                  f"-std={standard}", "-c", str(source)]})
                compile_database = root / "compile_commands.json"
                remote_entries = [{**entry, "directory": "/remote/repo",
                                   "file": "/remote/repo/" + Path(entry["file"]).name,
                                   "arguments": [token.replace(str(source_root), "/remote/repo") for token in entry["arguments"]]}
                                  for entry in entries]
                compile_database.write_text(json.dumps(remote_entries), encoding="utf-8")
                artifact_root = root / "artifacts"
                artifact_root.mkdir()
                platform = MODULE.synthetic_platform(entries, source_root)
                for index, record in enumerate(platform["records"]):
                    if mode == "partial":
                        record.update(optimization="Og", debug="vendor-debug")
                    if index < produced_count:
                        bitcode = artifact_root / f"{record['record_id']}.bc"
                        bitcode.write_bytes(f"fixed-{mode}-{index}".encode())
                        record["status"] = "produced"
                        record["diagnostic"] = None
                        record["bitcode"] = {"path": bitcode.name, "sha256": MODULE.sha256(bitcode),
                                             "bytes": bitcode.stat().st_size}
                    elif mode == "partial":
                        record["status"] = "failed"
                manifest = None
                if mode != "missing":
                    manifest = root / "manifest.json"
                    manifest.write_text(json.dumps(platform), encoding="utf-8")
                workspace = root / "workspace"
                external_root = workspace / "external"
                cache = workspace / "cache"
                workspace.mkdir()
                cache.mkdir()
                output = workspace / "request.json"
                MODULE.memory(argparse.Namespace(
                    manifest=manifest, artifact_root=artifact_root, source_root=source_root,
                    compile_database=compile_database, output=output, run_id="run",
                    source_revision="revision", build_run="build", cache=cache,
                    timeout=60, max_frontend_output_bytes=1024 * 1024,
                    external_root=external_root, workspace=workspace,
                    cancel_file=workspace / "cancel", project_id="project", project_name="legacy"))

                unified = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(unified["schema_version"], 2)
                self.assertEqual(len(unified["source_requests"]), 4)
                requests = [json.loads((workspace / item["path"]).read_text(encoding="utf-8"))
                            for item in unified["source_requests"]]
                self.assertEqual({item["profile"]["standard"] for item in requests},
                                 {"c89", "c99", "c++98", "c++03"})
                self.assertTrue(all(item["schema_version"] == 2 for item in requests))
                self.assertTrue(all({"from": str(source_root.resolve()), "to": "."} in item["profile"]["path_map"]
                                    for item in requests))
                self.assertTrue(all({"from": "/remote/repo", "to": "."} in item["profile"]["path_map"] for item in requests))
                records = [json.loads(path.read_text(encoding="utf-8"))
                           for path in sorted((external_root / "records").glob("*.json"))]
                self.assertEqual(sum(item["status"] == "produced" for item in records), produced_count)
                self.assertEqual(len(records), 4)
                if mode == "partial":
                    self.assertTrue(all(item["optimization"] == "unknown" and item["debug"] == "unknown" for item in records))


if __name__ == "__main__":
    unittest.main()
