"""Pinned TinyCThread compile-only P1--P4 cold/warm scale evidence."""

import json
import os
from pathlib import Path
import time

from memory_order_analyzer import cli
from memory_order_analyzer.contracts import canonical, document, identity
from memory_order_analyzer.publication_contracts import expected_publication_protocol, publication_document
from memory_order_analyzer.thread_contracts import expected_thread_protocol, thread_document
from memory_order_analyzer.validation_analysis import materialize_compile_database, semantic_digest, validate_real_project_profile
from memory_order_analyzer.validate_analysis import _directory_bytes, _resource_snapshot
from test_publication_risks import source_evidence
from test_offline import collect


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "tests/fixtures/validation/real-project/tinycthread-profile.json"
WORKER = os.environ.get("MOA_WORKER", "/output/build/moa-worker")


def test_tinycthread_profile_cold_warm_without_cmake_link_or_execution(tmp_path):
    profile = validate_real_project_profile(PROFILE)
    assert profile["status"] == "complete" and profile["configurations"] == ["clang-21", "gcc"]
    database = materialize_compile_database(PROFILE, tmp_path / "profile-compile-commands.json")
    database_records = json.loads(Path(database["path"]).read_text())
    fixture_root = PROFILE.parent / "tinycthread"
    source_text = (fixture_root / "source/tinycthread.c").read_text()
    include = str(fixture_root / "source")
    started = time.perf_counter()
    collect_report, artifacts, modules, database_path = collect(tmp_path, {
        "tinycthread-clang.c": {"content": source_text, "driver": "clang", "standard": "c17", "flags": ["-I", include]},
        "tinycthread-gcc.c": {"content": source_text, "driver": "gcc", "standard": "c17", "flags": ["-I", include]},
    })
    artifact_store = tmp_path / "out"
    collect_seconds = time.perf_counter() - started
    assert collect_report["build_status"] == "complete", collect_report["failures"]
    assert collect_report["counts"]["original_records"] == 2 and collect_report["counts"]["planned_tus"] == 2
    runs, ast_runs = [], []
    records_by_digest = {identity(item): item for item in json.loads(Path(database_path).read_text())}
    for key in collect_report["artifacts"]:
        module = modules[key]
        artifact = artifacts[key]
        configuration = Path(records_by_digest[artifact["toolchain"]["compile_record_digest"]]["arguments"][0]).name
        scope = document("ScopeManifest", target_id=f"tinycthread-{configuration}", members=[key],
                         evidence="P5 pinned TinyCThread compile-only per-configuration scope", closed=True,
                         external_boundaries=["pthread", "libc"])
        scope_path = tmp_path / f"scope-{configuration}.json"; scope_path.write_text(canonical(scope))
        root = next(function for function in module["functions"] if function["name"] == "thrd_create")
        thread_request = thread_document(
            "ThreadAnalysisRequest", scope=str(scope_path),
            roots=[{"artifact_key": key, "function_id": root["id"], "arguments": []}],
            model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
        thread_path = tmp_path / f"thread-{configuration}.json"; thread_path.write_text(canonical(thread_request))
        publication = publication_document(
            "PublicationRiskRequest", thread_request=str(thread_path),
            model_id="c-cpp-single-publication-v1", budgets=expected_publication_protocol()["budgets"])
        request_path = tmp_path / f"publication-{configuration}.json"; request_path.write_text(canonical(publication))
        configuration_runs = []
        for mode in ("cold", "warm"):
            output = tmp_path / f"{configuration}-{mode}"
            started = time.perf_counter()
            before_resource = _resource_snapshot()
            cache_before = len(list(artifact_store.glob("derived/**/*.json")))
            code = cli.main(["detect-publication-risks", "--request", str(request_path),
                             "--artifact-store", str(artifact_store), "--output", str(output),
                             "--worker", WORKER])
            elapsed = time.perf_counter() - started
            after_resource = _resource_snapshot()
            report = json.loads((output / "report.json").read_text())
            graph = json.loads(next((output / "graphs").glob("*.json")).read_text())
            assert code in {0, 2, 3} and report["safety"] == "not_established"
            configuration_runs.append({"configuration": configuration, "mode": mode, "wall_seconds": elapsed,
                                       "cpu_seconds": max(0.0, after_resource["cpu_seconds"] - before_resource["cpu_seconds"]),
                                       "peak_rss_bytes": after_resource["peak_rss_bytes"],
                                       "output_bytes": _directory_bytes(output),
                                       "cache_files_before": cache_before,
                                       "cache_files_after": len(list(artifact_store.glob("derived/**/*.json"))),
                                       "semantic_digest": semantic_digest({"report": report, "graph": graph},
                                                                          roots=(("${RUN}", output), ("${ROOT}", tmp_path)))})
        assert configuration_runs[0]["semantic_digest"] == configuration_runs[1]["semantic_digest"]
        runs.extend(configuration_runs)
        _, ast_cold, ast_warm, measurements = source_evidence(
            tmp_path, database_path, scope, {key: artifact}, {key: module},
            artifact_store=artifact_store, prefix=f"{configuration}-ast")
        assert ast_cold["semantic_digest"] == ast_warm["semantic_digest"]
        assert measurements[1]["cache"]["hits"] > measurements[0]["cache"]["hits"]
        ast_runs.extend({"configuration": configuration, **item} for item in measurements)
    evidence = {"profile": profile, "collect_wall_seconds": collect_seconds, "runs": runs,
                "ast_assisted_runs": ast_runs,
                "executed_cmake": False, "linked_target": False, "executed_target": False}
    (tmp_path / "scale-evidence.json").write_text(canonical(evidence) + "\n")
