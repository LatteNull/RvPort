"""P5 isolated runner, dependency binding, budgets and exit semantics."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest
import memory_order_analyzer.validate_analysis as runner_module

from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash, identity
from memory_order_analyzer.publication_contracts import (
    expected_publication_protocol,
    layer_counts,
    outcome_counts,
    publication_document,
)
from memory_order_analyzer.validate_analysis import (
    _directory_bytes,
    _default_run,
    _load_backends,
    _observation_path,
    _replace_tokens,
    _resource_snapshot,
    _run_stages,
    validate_analysis,
)
from memory_order_analyzer.validation_analysis import case_input_digest
from memory_order_analyzer.validation_contracts import (
    expected_validation_protocol,
    read_validation_document,
    validation_document,
)


H = "a" * 64


def p4_graph(scope=H, request_hash="b" * 64):
    return publication_document(
        "SinglePublicationProtocolGraph", model_id="c-cpp-single-publication-v1", scope_id=scope,
        request_hash=request_hash, thread_graph_digest="c" * 64,
        budgets=deepcopy(expected_publication_protocol()["budgets"]), dependencies=[],
        successful_observations=[], protocols=[], assessments=[], counts=outcome_counts([], []),
        frontier=[], diagnostics=[], status="complete")


def p4_report(graph, *, verdict="no_supported_risk_found", risk="complete"):
    member = {"id": H, "status": "complete", "reason": None}
    dependency = {"kind": "SinglePublicationProtocolGraph", "id": graph["scope_id"], "digest": identity(graph)}
    return publication_document(
        "PublicationRiskReport", model_id="c-cpp-single-publication-v1",
        request_hash=graph["request_hash"], scope_id=graph["scope_id"],
        budgets=deepcopy(expected_publication_protocol()["budgets"]), input_integrity="complete",
        p1_analysis="complete", p2_analysis="complete", p3_analysis="complete",
        publication_local_analysis="complete", candidate_modeling="complete", risk_evaluation=risk,
        source_mapping="complete", members=[member], member_counts=layer_counts([member]),
        outcome_counts=outcome_counts([], []), graph=dependency, dependencies=[dependency],
        frontier=[], diagnostics=[], assumptions=[], safety="not_established", verdict=verdict,
        findings=[], exit_code=0 if verdict == "no_supported_risk_found" and risk == "complete" else 2)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")
    return file_hash(path)


def make_workspace(tmp_path, *, required=(), run_modes=("cold", "warm"), backends=(), stage=None):
    suite_dir = tmp_path / "suite"; case_dir = suite_dir / "cases/basic"; case_dir.mkdir(parents=True)
    source = case_dir / "main.c"; source.write_text("#include <stdatomic.h>\nint main(void){return 0;}\n")
    database = case_dir / "compile_commands.json"; database.write_text("[]\n")
    scope = case_dir / "scope.json"; scope.write_text("{}\n")
    graph = p4_graph(); graph_hash = write_json(case_dir / "graph.json", graph)
    report = p4_report(graph); report_hash = write_json(case_dir / "report.json", report)
    case = {
        "id": "basic", "profile_id": "c11-clang", "category": "risk" if required else "correct",
        "layout": "single-tu", "source_root": "cases/basic",
        "sources": [{"path": "cases/basic/main.c", "sha256": file_hash(source), "role": "source"}],
        "compile_commands": {"path": "cases/basic/compile_commands.json", "sha256": file_hash(database), "role": "compile-database"},
        "scope": {"path": "cases/basic/scope.json", "sha256": file_hash(scope), "role": "scope"},
        "roots": ["main"], "truth": {"path": "cases/basic/truth.json", "sha256": H, "role": "truth"},
        "stages": [stage] if stage else [], "observation_report": "cases/basic/report.json",
        "observation_graph": "cases/basic/graph.json",
    }
    suite_stub = {"suite_id": "offline", "suite_version": 1}
    digest = case_input_digest(suite_dir, case)
    assertion = lambda code: {"code": code, "object": None, "thread_relation": None, "evidence_relation": None}
    truth = validation_document(
        "TruthAnnotation", suite_id="offline", suite_version=1, case_id="basic", truth_version=1,
        input_digest=digest,
        expected={"required_findings": [assertion(code) for code in required], "forbidden_findings": [],
                  "verdicts": ["risk"] if required else ["discharged"], "statuses": ["complete"], "unknown_codes": []},
        relations=[], review={"status": "reviewed", "reviewer": "unit", "method": "manual",
                              "reviewed_on": "2026-09-18", "basis": "人工审阅", "basis_en": "Manual review"})
    case["truth"]["sha256"] = write_json(case_dir / "truth.json", truth)
    profile = {"id": "c11-clang", "language": "c", "standard": "c11", "compiler": "clang",
               "compiler_version": "21.1.8", "target": "x86_64-linux-gnu", "data_layout": "e-p:64:64",
               "optimization": "O0", "debug": True, "compile_arguments": ["-std=c11"]}
    suite = validation_document("ValidationSuiteManifest", suite_id="offline", suite_version=1,
                                title="离线", title_en="Offline", profiles=[profile], cases=[case],
                                real_project_profile=None)
    suite_path = suite_dir / "suite.json"; suite_hash = write_json(suite_path, suite)
    request = validation_document(
        "AnalysisValidationRequest", suite=str(suite_path), suite_sha256=suite_hash,
        case_ids=["basic"], run_modes=list(run_modes), requested_backends=list(backends),
        real_project_profile=None, sampling_seed=1, budgets=deepcopy(expected_validation_protocol()["budgets"]))
    request_path = tmp_path / "request.json"; write_json(request_path, request)
    return request_path, suite_path, case, report_hash, graph_hash


def test_complete_match_cold_warm_outputs_and_read_only_inputs(tmp_path):
    request, suite, _, report_hash, graph_hash = make_workspace(tmp_path)
    output = tmp_path / "output"
    result = validate_analysis(request, tmp_path / "artifacts", output, tmp_path / "worker")
    assert result["exit_code"] == 0 and result["verdict"] == "matched"
    assert result["safety"] == "not_established" and result["metrics"]["exact_match"]["value"] == 1
    assert len(set(result["cases"][0]["semantic_digests"].values())) == 1
    assert read_validation_document(output / "report.json", "AnalysisValidationReport") == result
    assert read_validation_document(output / "decision.json", "AnalysisExtensionDecision")["entries"]
    assert file_hash(suite.parent / "cases/basic/report.json") == report_hash
    assert file_hash(suite.parent / "cases/basic/graph.json") == graph_hash
    assert _directory_bytes(output) > 0 and _resource_snapshot()["cpu_seconds"] >= 0


def test_complete_mismatch_exit_three_and_partial_backend_precedence(tmp_path):
    request, _, _, _, _ = make_workspace(tmp_path / "mismatch", required=["missing-risk"])
    mismatch = validate_analysis(request, tmp_path / "store", tmp_path / "mismatch-output", tmp_path / "worker")
    assert mismatch["exit_code"] == 3 and mismatch["verdict"] == "mismatch"
    request, _, _, _, _ = make_workspace(tmp_path / "partial", required=["missing-risk"], backends=["genmc"])
    partial = validate_analysis(request, tmp_path / "store", tmp_path / "partial-output", tmp_path / "worker")
    assert partial["exit_code"] == 2 and partial["verdict"] == "inconclusive"
    assert partial["layers"]["backend"]["status"] == "partial"


def test_invalid_request_dependencies_selection_budget_and_output(tmp_path):
    request_path, suite_path, _, _, _ = make_workspace(tmp_path)
    occupied = tmp_path / "occupied"; occupied.mkdir(); (occupied / "x").write_text("x")
    with pytest.raises(AnalysisError, match="new or empty"):
        validate_analysis(request_path, tmp_path, occupied, tmp_path / "worker")
    request = read_validation_document(request_path, "AnalysisValidationRequest")
    request["suite_sha256"] = H; write_json(request_path, request)
    with pytest.raises(AnalysisError, match="hash changed"):
        validate_analysis(request_path, tmp_path, tmp_path / "bad-hash", tmp_path / "worker")
    request["suite_sha256"] = file_hash(suite_path); request["case_ids"] = ["missing"]; write_json(request_path, request)
    with pytest.raises(AnalysisError, match="unknown case"):
        validate_analysis(request_path, tmp_path, tmp_path / "unknown", tmp_path / "worker")
    request["case_ids"] = ["basic"]; request["budgets"]["max_cases"] = 1; write_json(request_path, request)
    # Schema maximum/semantic budget path is separately exercised by selecting two cases in contract tests.
    assert validate_analysis(request_path, tmp_path, tmp_path / "valid", tmp_path / "worker")["exit_code"] == 0


def test_relative_suite_request_timeout_output_budget_and_cold_warm_difference(tmp_path, monkeypatch):
    request_path, suite_path, _, _, _ = make_workspace(tmp_path / "relative", run_modes=("cold", "warm"))
    request = read_validation_document(request_path, "AnalysisValidationRequest")
    request["suite"] = str(suite_path.relative_to(request_path.parent)); write_json(request_path, request)
    original_digest = runner_module.semantic_digest
    digests = iter(("1" * 64, "2" * 64))
    monkeypatch.setattr(runner_module, "semantic_digest", lambda *a, **k: next(digests))
    result = validate_analysis(request_path, tmp_path, tmp_path / "different", tmp_path / "worker")
    assert result["exit_code"] == 2 and result["cases"][0]["diagnostics"][0]["code"] == "cold_warm_mismatch"
    monkeypatch.setattr(runner_module, "semantic_digest", original_digest)

    request_path, _, _, _, _ = make_workspace(tmp_path / "budget", run_modes=("cold",))
    request = read_validation_document(request_path, "AnalysisValidationRequest")
    request["budgets"]["output_bytes"] = 1; write_json(request_path, request)
    result = validate_analysis(request_path, tmp_path, tmp_path / "budget-output", tmp_path / "worker")
    assert result["exit_code"] == 2 and result["frontier"][0]["code"] == "output_budget"

    request_path, _, _, _, _ = make_workspace(tmp_path / "timeout", run_modes=("cold",))
    ticks = iter((0.0, 99999.0, 99999.0))
    monkeypatch.setattr(runner_module.time, "perf_counter", lambda: next(ticks))
    result = validate_analysis(request_path, tmp_path, tmp_path / "timeout-output", tmp_path / "worker")
    assert result["exit_code"] == 2 and result["frontier"][0]["code"] == "request_timeout"


def test_stage_token_isolation_success_failure_and_timeout(tmp_path):
    case = {"id": "stage", "source_root": "case", "stages": [{
        "operation": "collect", "arguments": ["--output", "${RUN_DIR}/out", "--database", "${CASE_DIR}/db.json"],
        "report": "out/report.json", "allowed_exit_codes": [0]}]}
    (tmp_path / "suite/case").mkdir(parents=True); run = tmp_path / "run"; run.mkdir()
    seen = []
    def success(argv, *, cwd, **kwargs):
        seen.append(argv); (Path(cwd) / "out").mkdir(); (Path(cwd) / "out/report.json").write_text('{"counts":{"cache_hits":2,"generated":3}}')
        return 0
    result = _run_stages(case, tmp_path / "suite", run, tmp_path / "store", tmp_path / "worker", 1, success)
    assert result[0]["status"] == "complete" and any(str(run) in argument for argument in seen[0])
    assert (result[0]["cache_hits"], result[0]["cache_misses"]) == (2, 1)
    run2 = tmp_path / "run2"; run2.mkdir()
    assert _run_stages(case, tmp_path / "suite", run2, tmp_path, tmp_path / "worker", 1,
                       lambda *a, **k: 9)[0]["status"] == "failed"
    run3 = tmp_path / "run3"; run3.mkdir()
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)
    timed = _run_stages(case, tmp_path / "suite", run3, tmp_path, tmp_path / "worker", 1, timeout)
    assert timed[0]["status"] == "partial" and timed[0]["reason"] == "timeout"
    invalid = deepcopy(case); invalid["stages"][0]["operation"] = "cmake"
    with pytest.raises(AnalysisError, match="not allowed"):
        _run_stages(invalid, tmp_path / "suite", run3, tmp_path, tmp_path / "worker", 1, timeout)
    assert _replace_tokens("${WORKER}:${ARTIFACT_STORE}", {token: token.lower() for token in
                           ("${ARTIFACT_STORE}", "${WORKER}", "${SUITE_DIR}", "${CASE_DIR}", "${RUN_DIR}")}) == "${worker}:${artifact_store}"
    stdout, stderr = tmp_path / "direct.out", tmp_path / "direct.err"
    with stdout.open("w") as out, stderr.open("w") as err:
        assert _default_run(["sh", "-c", "exit 0"], cwd=tmp_path, env={}, timeout=1, stdout=out, stderr=err) == 0


def test_stage_clock_and_resource_collection_are_deterministic(tmp_path, monkeypatch):
    case = {"id": "stage", "source_root": "case", "stages": [{
        "operation": "collect", "arguments": [], "report": "report.json", "allowed_exit_codes": [0]}]}
    (tmp_path / "suite/case").mkdir(parents=True)
    run = tmp_path / "run"; run.mkdir()
    ticks = iter((10.0, 12.5))
    resources = iter(({"cpu_seconds": 3.0, "peak_rss_bytes": 100.0},
                      {"cpu_seconds": 3.75, "peak_rss_bytes": 256.0}))
    monkeypatch.setattr(runner_module.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(runner_module, "_resource_snapshot", lambda: next(resources))

    def success(*args, cwd, **kwargs):
        Path(cwd, "report.json").write_text('{"counts":{"cache_hits":1,"generated":1}}')
        return 0

    result = _run_stages(case, tmp_path / "suite", run, tmp_path / "store", tmp_path / "worker", 9, success)
    assert result == [{
        "operation": "collect", "status": "complete", "exit_code": 0,
        "wall_seconds": 2.5, "cpu_seconds": 0.75, "peak_rss_bytes": 256.0,
        "reason": None, "cache_hits": 1, "cache_misses": 0,
    }]


def test_observation_dependency_replacement_and_missing(tmp_path):
    request, suite_path, case, _, _ = make_workspace(tmp_path)
    case_dir = suite_path.parent / "cases/basic"
    graph = json.loads((case_dir / "graph.json").read_text()); graph["diagnostics"] = []
    graph["thread_graph_digest"] = "d" * 64; write_json(case_dir / "graph.json", graph)
    with pytest.raises(AnalysisError, match="binding failed"):
        validate_analysis(request, tmp_path, tmp_path / "replaced", tmp_path / "worker")
    request, suite_path, case, _, _ = make_workspace(tmp_path / "scope-replaced")
    report_path = suite_path.parent / case["observation_report"]
    value = json.loads(report_path.read_text()); value["scope_id"] = "f" * 64; write_json(report_path, value)
    with pytest.raises(AnalysisError, match="scope/request binding"):
        validate_analysis(request, tmp_path, tmp_path / "scope-output", tmp_path / "worker")
    with pytest.raises(AnalysisError, match="has no observation"):
        _observation_path({"id": "x", "observation_report": None}, "observation_report", suite_path.parent, tmp_path)


def test_backend_bundle_replay_and_digest_rejection(tmp_path):
    request, suite_path, case, _, _ = make_workspace(tmp_path)
    truth = read_validation_document(suite_path.parent / case["truth"]["path"], "TruthAnnotation")
    result = {"matched": True, "_counts": {"tp": 0}}
    bundles, comparisons, status = _load_backends(case, suite_path.parent, ["genmc"], truth, result)
    assert status == "partial" and comparisons == ["inconclusive"] and bundles[0]["status"] == "unavailable"
    bundle = validation_document(
        "BackendEvidenceBundle", backend="genmc", backend_version="0.8", license="GPL-3.0",
        case_id="basic", applicability="applicable", status="complete", command=["genmc"],
        input_digest=truth["input_digest"], raw_output_hashes=[], observation={"risk": False},
        captured_on="2026-09-18", diagnostics=[])
    path = suite_path.parent / "cases/basic/genmc-bundle.json"; digest = write_json(path, bundle)
    replay_case = deepcopy(case)
    replay_case["sources"].append({"path": "cases/basic/genmc-bundle.json", "sha256": digest, "role": "backend-output"})
    bundles, comparisons, status = _load_backends(replay_case, suite_path.parent, ["genmc"], truth, result)
    assert status == "complete" and comparisons == ["agree"] and bundles == [bundle]
    replay_case["sources"][-1]["sha256"] = H
    with pytest.raises(AnalysisError, match="Backend bundle changed"):
        _load_backends(replay_case, suite_path.parent, ["genmc"], truth, result)
