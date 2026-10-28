from __future__ import annotations

import builtins
import copy
import json
import os
import runpy
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from tests.helpers import add_bitcode_artifact_set, ast_for, make_request

from floating_point_precision_scanner import CACHE_SCHEMA_VERSION, benchmark_runner
from floating_point_precision_scanner import application as application_module
from floating_point_precision_scanner import budget as budget_module
from floating_point_precision_scanner import rules as rules_module
from floating_point_precision_scanner.application import Scanner as ApplicationScanner
from floating_point_precision_scanner.benchmark import (
    BENCHMARK_TIERS,
    evaluate_benchmark,
)
from floating_point_precision_scanner.benchmark import (
    main as benchmark_main,
)
from floating_point_precision_scanner.budget import (
    BudgetCoordinator,
    BudgetExceeded,
    BudgetFrontier,
    ResourceSample,
)
from floating_point_precision_scanner.cache import (
    AnalysisCache,
    CacheConfig,
    cache_key,
)
from floating_point_precision_scanner.cli import main as cli_main
from floating_point_precision_scanner.diagnostics import diagnostic
from floating_point_precision_scanner.frontend import ClangFrontend
from floating_point_precision_scanner.protocol import SchemaRegistry, parse_request
from floating_point_precision_scanner.result_v2 import failure_result_v2
from floating_point_precision_scanner.suppression import Suppression, apply_suppressions
from floating_point_precision_scanner.validation import (
    QualityCounts,
    _observation_from_result,
    _score_case,
    evaluate_corpus,
)
from floating_point_precision_scanner.validation import main as validation_main

ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "tests" / "fixtures" / "validation"


class Clock:
    def __init__(self, *values: float) -> None:
        self.values = list(values)

    def __call__(self) -> float:
        return self.values.pop(0)


def test_budget_coordinator_tracks_deadline_resources_and_stable_frontier() -> None:
    samples = iter([ResourceSample(1.0, 100), ResourceSample(1.5, 200), ResourceSample(3.5, 500)])
    budget = BudgetCoordinator(
        {
            "wall_seconds": 10,
            "cpu_seconds": 1,
            "max_memory_bytes": 300,
            "max_files": 2,
        },
        clock=Clock(0, 2, 3, 4),
        sampler=lambda: next(samples),
    )
    assert budget.remaining_wall(20) == 8
    assert budget.consume("max_files", 2, scope="plan") == 2
    budget.check_resources("one")
    with pytest.raises(BudgetExceeded) as error:
        budget.check_resources("two", "frontier-1")
    assert error.value.item.budget == "cpu_seconds"
    snapshot = budget.snapshot()
    assert snapshot["logical_used"] == {"max_files": 2}
    assert snapshot["frontiers"][0]["frontier"] == "frontier-1"


def test_budget_coordinator_wall_and_logical_limits() -> None:
    budget = BudgetCoordinator(
        {"wall_seconds": 1, "max_files": 1},
        clock=Clock(0, 1),
        sampler=lambda: ResourceSample(0, 0),
    )
    with pytest.raises(BudgetExceeded, match="wall_seconds"):
        budget.remaining_wall(10)
    other = BudgetCoordinator(
        {"max_files": 1}, clock=Clock(0), sampler=lambda: ResourceSample(0, 0)
    )
    with pytest.raises(BudgetExceeded, match="max_files"):
        other.consume("max_files", 2, scope="plan", frontier="first")
    assert (
        other.record_frontier("max_files", scope="plan", frontier="first", used=2).to_dict()[
            "limit"
        ]
        == 1
    )


def test_budget_cpu_memory_sampling_and_remaining(monkeypatch: pytest.MonkeyPatch) -> None:
    assert budget_module.resource_limits_supported() is (os.name != "nt")
    class Usage:
        ru_maxrss = 4
        ru_utime = 1.0
        ru_stime = 0.5

    class Resource:
        RUSAGE_SELF = 1
        RUSAGE_CHILDREN = 2

        @staticmethod
        def getrusage(_kind: int) -> Usage:
            return Usage()

    original_import = builtins.__import__
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *args, **kwargs: Resource
        if name == "resource"
        else original_import(name, *args, **kwargs),
    )
    assert budget_module._sample_process() == ResourceSample(3.0, 4096)
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError())
        if name == "resource"
        else original_import(name, *args, **kwargs),
    )
    assert budget_module._sample_process().rss_bytes == 0

    samples = iter([ResourceSample(1, 1), ResourceSample(2, 1), ResourceSample(4, 500)])
    coordinator = BudgetCoordinator(
        {"cpu_seconds": 2, "max_memory_bytes": 100},
        clock=Clock(0),
        sampler=lambda: next(samples),
    )
    assert coordinator.remaining_cpu(10) == 1
    with pytest.raises(BudgetExceeded, match="cpu_seconds"):
        coordinator.remaining_cpu(10)
    without_cpu = BudgetCoordinator({}, clock=Clock(0), sampler=lambda: ResourceSample(0, 0))
    assert without_cpu.remaining_cpu(7) == 7

    memory = BudgetCoordinator(
        {"max_memory_bytes": 100},
        clock=Clock(0),
        sampler=iter([ResourceSample(0, 1), ResourceSample(0, 101)]).__next__,
    )
    with pytest.raises(BudgetExceeded, match="max_memory_bytes"):
        memory.check_resources("frontend", "a.c")

    wall = BudgetCoordinator(
        {"wall_seconds": 1}, clock=Clock(0, 1), sampler=lambda: ResourceSample(0, 0)
    )
    with pytest.raises(BudgetExceeded, match="wall_seconds"):
        wall.check_resources("request")


def test_analysis_cache_round_trip_modes_and_key_changes(tmp_path: Path) -> None:
    key = cache_key("source-facts", {"source": "a", "context": "c"})
    assert key != cache_key("source-facts", {"source": "b", "context": "c"})
    cache = AnalysisCache(CacheConfig("read-write", tmp_path / "cache", 4096))
    assert cache.read("source-facts", key) is None
    payload = {"kind": "facts", "value": 1}
    assert cache.write("source-facts", key, payload, dependencies={"source": "a"})
    assert cache.read("source-facts", key) == payload
    assert cache.stats.to_dict() == {"hit": 1, "miss": 1, "corrupt": 0, "write": 1}
    off = AnalysisCache(CacheConfig())
    assert off.read("source-facts", key) is None
    assert off.write("source-facts", key, payload, dependencies={}) is False
    assert off.stats.to_dict() == {"hit": 0, "miss": 0, "corrupt": 0, "write": 0}


def test_analysis_cache_rejects_corruption_escape_conflict_and_write_failure(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cache"
    cache = AnalysisCache(CacheConfig("read-write", root, 4096))
    key = cache_key("evidence", {"source": "a", "ir": "b"})
    cache.write("evidence", key, {"value": 1}, dependencies={})
    path = cache.path_for("evidence", key)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload_sha256"] = "0" * 64
    path.write_text(json.dumps(document), encoding="utf-8")
    assert cache.read("evidence", key) is None
    assert cache.stats.corrupt == 1
    with pytest.raises(ValueError, match="unsupported_cache_kind"):
        cache_key("finding", {})
    with pytest.raises(ValueError, match="invalid_cache_path"):
        AnalysisCache(CacheConfig()).path_for("source-facts", key)
    with pytest.raises(ValueError, match="invalid_cache_mode"):
        AnalysisCache(CacheConfig("bad", root))
    with pytest.raises(ValueError, match="cache_root_required"):
        AnalysisCache(CacheConfig("read-only"))
    tiny = AnalysisCache(CacheConfig("write-only", root / "tiny", 10))
    with pytest.raises(ValueError, match="cache_entry_too_large"):
        tiny.write("source-facts", key, {"long": "x" * 100}, dependencies={})
    broken = AnalysisCache(
        CacheConfig("write-only", root / "broken", 4096),
        sync=lambda _: (_ for _ in ()).throw(OSError("disk")),
    )
    with pytest.raises(OSError, match="disk"):
        broken.write("source-facts", key, {"value": 1}, dependencies={})
    assert list((root / "broken").rglob("*.tmp")) == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda document: [],
        lambda document: {**document, "kind": "wrong"},
        lambda document: {**document, "payload": []},
        lambda document: {**document, "payload_bytes": 999},
    ],
)
def test_analysis_cache_rejects_envelope_variants(tmp_path: Path, mutation: Any) -> None:
    cache = AnalysisCache(CacheConfig("read-write", tmp_path / "cache", 4096))
    key = cache_key("source-facts", {"source": "a"})
    assert cache.write("source-facts", key, {"value": 1}, dependencies={})
    path = cache.path_for("source-facts", key)
    document = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(mutation(document)), encoding="utf-8")
    assert cache.read("source-facts", key) is None
    assert cache.stats.corrupt == 1


def test_analysis_cache_rejects_large_read_symlink_and_publish_conflict(tmp_path: Path) -> None:
    key = cache_key("ir-facts", {"ir": "a"})
    root = tmp_path / "cache"
    writer = AnalysisCache(CacheConfig("write-only", root, 4096))
    writer.write("ir-facts", key, {"value": 1}, dependencies={})
    path = writer.path_for("ir-facts", key)
    assert AnalysisCache(CacheConfig("read-only", root, 1)).read("ir-facts", key) is None

    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    path.unlink()
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable")
    reader = AnalysisCache(CacheConfig("read-only", root, 4096))
    assert reader.read("ir-facts", key) is None and reader.stats.miss == 1
    path.unlink()

    first = AnalysisCache(CacheConfig("read-write", root, 4096))
    first.write("ir-facts", key, {"value": 1}, dependencies={})
    with pytest.raises(ValueError, match="cache_publish_conflict"):
        first.write("ir-facts", key, {"value": 2}, dependencies={})
    with pytest.raises(ValueError, match="invalid_cache_path"):
        first.path_for("ir-facts", "short")


def _reviewed_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    corpus = json.loads((VALIDATION / "reviewed-corpus-v1.json").read_text(encoding="utf-8"))
    observed = json.loads((VALIDATION / "reviewed-observed-v1.json").read_text(encoding="utf-8"))[
        "observations"
    ]
    return corpus, observed


def test_reviewed_corpus_schema_metrics_and_cli(tmp_path: Path) -> None:
    corpus, observed = _reviewed_documents()
    assert SchemaRegistry().validate("validation_corpus", corpus) == []
    report = evaluate_corpus(corpus, observed)
    assert report["gates"] == {
        "rule_quality": True,
        "exact_match": True,
        "lifecycle_exact": True,
        "corpus_complete": True,
        "passed": True,
    }
    assert len(report["per_rule"]) == 10
    assert all(item["strict_precision"] == 1 for item in report["per_rule"].values())
    assert SchemaRegistry().validate("validation_result", report) == []
    output = tmp_path / "validation.json"
    assert (
        validation_main(
            [
                "--corpus",
                str(VALIDATION / "reviewed-corpus-v1.json"),
                "--observed",
                str(VALIDATION / "reviewed-observed-v1.json"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["gates"]["passed"]
    cli_output = tmp_path / "cli-validation.json"
    assert (
        cli_main(
            [
                "validate-corpus",
                "--corpus",
                str(VALIDATION / "reviewed-corpus-v1.json"),
                "--observed",
                str(VALIDATION / "reviewed-observed-v1.json"),
                "--output",
                str(cli_output),
            ]
        )
        == 0
    )


def test_validation_consumes_result_v2_findings_and_assessments() -> None:
    from tests.contract.test_expression_result_contract import valid_expression_result

    result = valid_expression_result()
    result["findings"][0]["conclusion"]["semantic"]["validationKey"] = "comparison:1"
    observation = _observation_from_result(result, "fragile-fp-comparison")
    assert observation == {
        "status": "matched",
        "finding_keys": ["comparison:1"],
        "diagnostic_codes": [],
        "suppression_ids": [],
        "assessment_statuses": ["matched"],
        "affected_counts": [1],
        "scan_status": "complete",
        "suppression_count": 0,
    }
    corpus = {
        "cases": [
            {
                "case_id": "v2-case",
                "rule_code": "fragile-fp-comparison",
                "expected_status": "matched",
                "finding_keys": ["comparison:1"],
                "diagnostic_codes": [],
                "suppression_ids": [],
            }
        ]
    }
    report = evaluate_corpus(corpus, {"v2-case": result})
    assert report["overall"]["exact_match"] == 1


def test_validation_normalizes_v2_observation_boundaries() -> None:
    analysis = "org.rvport.floating-point-scanner.analysis"
    suppressions = "org.rvport.floating-point-scanner.suppressions"
    result = {
        "extensions": {
            analysis: {
                "assessments": [
                    "ignored",
                    {
                        "ruleCode": "fragile-fp-comparison",
                        "status": "notMatched",
                    },
                ]
            },
            suppressions: {"records": ["ignored", {"id": "suppression-1"}]},
        },
        "findings": [
            "ignored",
            {"conclusion": None},
            {"conclusion": {"findingCode": "another-rule"}},
            {
                "id": "finding-fallback",
                "conclusion": {
                    "findingCode": "fragile-fp-comparison",
                    "semantic": None,
                },
            },
        ],
        "diagnostics": ["ignored", {"code": "example-diagnostic"}],
    }
    assert _observation_from_result(result, "fragile-fp-comparison") == {
        "status": "not_matched",
        "finding_keys": ["finding-fallback"],
        "diagnostic_codes": ["example-diagnostic"],
        "suppression_ids": ["suppression-1"],
        "assessment_statuses": ["not_matched"],
        "affected_counts": [1],
        "scan_status": None,
        "suppression_count": 2,
    }


def test_validation_penalizes_abstention_and_rejects_bad_corpus() -> None:
    corpus, observed = _reviewed_documents()
    positive = next(item for item in corpus["cases"] if item["expected_status"] == "matched")
    changed = copy.deepcopy(observed)
    changed[positive["case_id"]] = {
        "status": "unknown",
        "finding_keys": [],
        "diagnostic_codes": [],
        "suppression_ids": [],
    }
    report = evaluate_corpus(corpus, changed)
    metrics = report["per_rule"][positive["rule_code"]]
    assert metrics["fn"] == 1 and metrics["abstention"] == 1
    assert report["gates"]["passed"] is False
    duplicate = copy.deepcopy(corpus)
    duplicate["cases"].append(copy.deepcopy(duplicate["cases"][0]))
    with pytest.raises(ValueError, match="duplicate_validation_case"):
        evaluate_corpus(duplicate, observed)
    incomplete = copy.deepcopy(corpus)
    incomplete["cases"] = incomplete["cases"][:1]
    assert evaluate_corpus(incomplete, observed)["gates"]["corpus_complete"] is False
    incomplete["cases"][0]["rule_code"] = "unknown-rule"
    with pytest.raises(ValueError, match="unknown_validation_rule"):
        evaluate_corpus(incomplete, observed)
    with pytest.raises(ValueError, match="validation_corpus_has_no_cases"):
        evaluate_corpus({"cases": []}, {})


def test_validation_metrics_edge_cases_and_cli_errors(tmp_path: Path) -> None:
    assert QualityCounts().metrics() == {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "abstention": 0,
        "exact": 0,
        "total": 0,
        "strict_precision": None,
        "strict_recall": None,
        "supported_precision": None,
        "supported_recall": None,
        "exact_match": None,
    }
    unsupported = _score_case(
        {"expected_status": "unknown", "unsupported": True},
        {"status": "matched", "finding_keys": ["extra"]},
    )
    assert unsupported.false_positive == 2 and unsupported.supported_false_positive == 0
    empty_positive = _score_case(
        {"expected_status": "matched", "finding_keys": []}, {"status": "unknown"}
    )
    assert empty_positive.false_negative == 1
    negative = _score_case(
        {"expected_status": "not_matched", "finding_keys": ["same"]},
        {"status": "matched", "finding_keys": ["same"]},
    )
    assert negative.false_positive == 1

    corpus, observed = _reviewed_documents()
    lifecycle = next(item for item in corpus["cases"] if item.get("lifecycle"))
    changed = copy.deepcopy(observed)
    changed[lifecycle["case_id"]] = {"status": "missing"}
    assert evaluate_corpus(corpus, changed)["gates"]["lifecycle_exact"] is False
    invalid_case = copy.deepcopy(corpus)
    invalid_case["cases"][0] = "bad"
    with pytest.raises(ValueError, match="invalid_validation_case"):
        evaluate_corpus(invalid_case, observed)

    corpus_path = tmp_path / "corpus.json"
    observed_path = tmp_path / "observed.json"
    output = tmp_path / "out.json"
    corpus_path.write_text("[]", encoding="utf-8")
    observed_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="validation_document_must_be_object"):
        validation_main(
            [
                "--corpus",
                str(corpus_path),
                "--observed",
                str(observed_path),
                "--output",
                str(output),
            ]
        )
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    with pytest.raises(ValueError, match="validation_observations_missing"):
        validation_main(
            [
                "--corpus",
                str(corpus_path),
                "--observed",
                str(observed_path),
                "--output",
                str(output),
            ]
        )
    bad_corpus = copy.deepcopy(corpus)
    bad_corpus.pop("schema_version")
    corpus_path.write_text(json.dumps(bad_corpus), encoding="utf-8")
    observed_path.write_text(json.dumps({"observations": observed}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_validation_error"):
        validation_main(
            [
                "--corpus",
                str(corpus_path),
                "--observed",
                str(observed_path),
                "--output",
                str(output),
            ]
        )


def _samples(wall: float, cpu: float, rss: float, result: float) -> list[dict[str, float]]:
    return [
        {
            "wall_seconds": wall,
            "cpu_seconds": cpu,
            "rss_bytes": rss,
            "result_bytes": result,
        }
        for _ in range(3)
    ]


def test_benchmark_absolute_hot_regression_and_environment_gates(tmp_path: Path) -> None:
    cold = _samples(10, 20, 1000, 1000)
    hot = _samples(5, 10, 1000, 1000)
    report = evaluate_benchmark(
        "S",
        cold,
        hot,
        baseline={"wall_seconds": 10, "cpu_seconds": 20, "rss_bytes": 1000},
    )
    assert report["gates"]["passed"]
    assert not evaluate_benchmark("S", cold, cold)["gates"]["hot_ratio"]
    zero_wall = _samples(0, 20, 1000, 1000)
    assert not evaluate_benchmark("S", zero_wall, hot)["gates"]["hot_ratio"]
    assert not evaluate_benchmark("S", cold, hot, environment_applicable=False)["gates"]["passed"]
    assert not evaluate_benchmark("S", cold, hot, semantic_equal=False)["gates"]["passed"]
    assert not evaluate_benchmark(
        "S",
        cold,
        hot,
        baseline={"wall_seconds": 1, "cpu_seconds": 1, "rss_bytes": 1},
    )["gates"]["regression"]
    too_slow = _samples(BENCHMARK_TIERS["S"]["wall_seconds"] + 1, 20, 1000, 1000)
    assert not evaluate_benchmark("S", too_slow, hot)["gates"]["absolute"]
    with pytest.raises(ValueError, match="unknown_benchmark_tier"):
        evaluate_benchmark("X", cold, hot)
    with pytest.raises(ValueError, match="benchmark_requires_three_samples"):
        evaluate_benchmark("S", cold[:2], hot)
    with pytest.raises(ValueError, match="invalid_benchmark_sample"):
        evaluate_benchmark("S", _samples(-1, 1, 1, 1), hot)

    tiers: dict[str, Any] = {}
    for tier in BENCHMARK_TIERS:
        tiers[tier] = {
            "cold": cold,
            "hot": hot,
            "baseline": {"wall_seconds": 10, "cpu_seconds": 20, "rss_bytes": 1000},
            "environment_applicable": True,
            "semantic_equal": True,
        }
    source = tmp_path / "samples.json"
    output = tmp_path / "benchmark.json"
    source.write_text(json.dumps({"tiers": tiers}), encoding="utf-8")
    assert benchmark_main(["--input", str(source), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["passed"]

    for document, message in [
        ([], "benchmark_input_must_be_object"),
        ({}, "benchmark_tiers_missing"),
        ({"tiers": {}}, "benchmark_tier_missing"),
        ({"tiers": {"S": {}}}, "benchmark_samples_missing"),
    ]:
        source.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            benchmark_main(["--input", str(source), "--output", str(output)])

    for item in tiers.values():
        item["environment_applicable"] = False
    source.write_text(json.dumps({"tiers": tiers}), encoding="utf-8")
    assert benchmark_main(["--input", str(source), "--output", str(output)]) == 1

    for item in tiers.values():
        item["environment_applicable"] = True
    source.write_text(json.dumps({"tiers": tiers}), encoding="utf-8")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sys, "argv", ["benchmark", "--input", str(source), "--output", str(output)])
    try:
        with (
            pytest.raises(SystemExit) as error,
            pytest.warns(RuntimeWarning, match="found in sys.modules"),
        ):
            runpy.run_module("floating_point_precision_scanner.benchmark", run_name="__main__")
        assert error.value.code == 0
    finally:
        monkeypatch.undo()


def test_benchmark_runner_generates_workload_and_uses_semantic_projection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    limits = copy.deepcopy(BENCHMARK_TIERS["S"])
    monkeypatch.setitem(
        BENCHMARK_TIERS,
        "S",
        {
            **limits,
            "translation_units": 2,
            "source_lines": 4,
        },
    )
    request = benchmark_runner._create_workload(tmp_path, "S")
    assert len(request["input"]["translation_units"]) == 2
    assert (tmp_path / "unit-0000.c").read_text(encoding="utf-8").count("\n") == 2
    result = failure_result_v2("benchmark", "complete", [])
    projection = benchmark_runner._semantic_projection(
        result
    )
    assert projection == {
        "schemaVersion": "2.0",
        "status": "complete",
        "semanticDigest": result["scan"]["semanticDigest"],
    }


def test_benchmark_runner_orchestration_and_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(benchmark_runner, "_environment_applicable", lambda: True)

    def fake_workload(root: Path, tier: str) -> dict[str, Any]:
        (root / ".cache").mkdir()
        return {"cache": {"root": str(root / ".cache")}, "tier": tier}

    samples = iter(
        [
            (
                {
                    "wall_seconds": 10.0 if index < 3 else 5.0,
                    "cpu_seconds": 20.0 if index < 3 else 10.0,
                    "rss_bytes": 1000.0,
                    "result_bytes": 1000.0,
                },
                "same",
            )
            for index in range(7)
        ]
    )
    monkeypatch.setattr(benchmark_runner, "_create_workload", fake_workload)
    monkeypatch.setattr(benchmark_runner, "_run_once", lambda *_: next(samples))
    report = benchmark_runner.run_benchmarks(Path("clang"), tiers=("S",))
    assert report["passed"] and report["tiers"][0]["semantic_equal"]
    assert len(report["tiers"][0]["workload_digest"]) == 64

    output = tmp_path / "runner.json"
    monkeypatch.setattr(
        benchmark_runner,
        "run_benchmarks",
        lambda *_args, **_kwargs: {"passed": True, "tiers": []},
    )
    assert benchmark_runner.main(["--tiers", "S", "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["passed"]

    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"S": {"wall_seconds": 10}}), encoding="utf-8")
    monkeypatch.setattr(
        benchmark_runner,
        "run_benchmarks",
        lambda *_args, **_kwargs: {"passed": False, "tiers": []},
    )
    assert (
        benchmark_runner.main(
            ["--tiers", "S", "--baseline", str(baseline), "--output", str(output)]
        )
        == 1
    )


def test_benchmark_runner_resources_environment_and_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert not benchmark_runner._environment_applicable(system=lambda: "Windows")
    assert not benchmark_runner._environment_applicable(
        system=lambda: "Linux", machine=lambda: "x86_64", cpu_count=lambda: 1
    )
    low_memory = tmp_path / "memory.max"
    low_memory.write_text("1", encoding="utf-8")
    assert not benchmark_runner._environment_applicable(
        system=lambda: "Linux",
        machine=lambda: "amd64",
        cpu_count=lambda: 4,
        memory_limit=low_memory,
    )
    low_memory.write_text("max", encoding="utf-8")
    assert benchmark_runner._environment_applicable(
        system=lambda: "Linux",
        machine=lambda: "amd64",
        cpu_count=lambda: 4,
        memory_limit=low_memory,
    )
    assert benchmark_runner._environment_applicable(
        system=lambda: "Linux",
        machine=lambda: "amd64",
        cpu_count=lambda: 4,
        memory_limit=tmp_path / "missing-memory.max",
    )
    with pytest.raises(ValueError, match="benchmark_result_scan_missing"):
        benchmark_runner._semantic_projection({"metadata": "absent"})

    samples = iter([(1.0, 2), (2.0, 3)])
    monkeypatch.setattr(benchmark_runner, "_resource_sample", lambda: next(samples))
    monkeypatch.setattr(benchmark_runner.time, "perf_counter", Clock(5, 7))

    class Scanner:
        @staticmethod
        def scan(_request: Mapping[str, Any]) -> dict[str, Any]:
            return failure_result_v2("benchmark", "complete", [])

    sample, digest = benchmark_runner._run_once(Scanner(), {})  # type: ignore[arg-type]
    assert sample == {
        "wall_seconds": 2,
        "cpu_seconds": 1,
        "rss_bytes": 3.0,
        "result_bytes": sample["result_bytes"],
    }
    assert len(digest) == 64

    class FailedScanner:
        @staticmethod
        def scan(_request: Mapping[str, Any]) -> dict[str, Any]:
            return failure_result_v2("benchmark", "partial", [])

    samples = iter([(1.0, 2), (2.0, 3)])
    monkeypatch.setattr(benchmark_runner, "_resource_sample", lambda: next(samples))
    monkeypatch.setattr(benchmark_runner.time, "perf_counter", Clock(5, 7))
    with pytest.raises(RuntimeError, match="benchmark_scan_partial"):
        benchmark_runner._run_once(FailedScanner(), {})  # type: ignore[arg-type]


def test_benchmark_runner_resource_sampler_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    class Usage:
        ru_utime = 1.0
        ru_stime = 0.5
        ru_maxrss = 4

    class Resource:
        RUSAGE_SELF = 1
        RUSAGE_CHILDREN = 2

        @staticmethod
        def getrusage(_kind: int) -> Usage:
            return Usage()

    original_import = builtins.__import__
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *args, **kwargs: Resource
        if name == "resource"
        else original_import(name, *args, **kwargs),
    )
    assert benchmark_runner._resource_sample() == (3.0, 4096)
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError())
        if name == "resource"
        else original_import(name, *args, **kwargs),
    )
    assert benchmark_runner._resource_sample()[1] == 0


def test_benchmark_runner_module_entrypoint_without_tiers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "entrypoint.json"
    monkeypatch.setattr(sys, "argv", ["benchmark-runner", "--output", str(output)])
    original = dict(benchmark_runner.BENCHMARK_TIERS)
    benchmark_runner.BENCHMARK_TIERS.clear()
    try:
        with (
            pytest.raises(SystemExit) as error,
            pytest.warns(RuntimeWarning, match="found in sys.modules"),
        ):
            runpy.run_module(
                "floating_point_precision_scanner.benchmark_runner", run_name="__main__"
            )
        assert error.value.code == 0
    finally:
        benchmark_runner.BENCHMARK_TIERS.update(original)


def test_application_hardening_cache_file_budget_and_diagnostic_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.unit.test_application_cli import FakeFrontend

    invalid = make_request(tmp_path / "invalid")
    invalid["input"] = {"compile_commands": "missing.json"}
    result = ApplicationScanner(FakeFrontend()).scan(invalid)
    assert result["scan"]["status"] == "invalid_request"

    limited_root = tmp_path / "limited"
    limited_root.mkdir()
    for name in ("one.c", "two.c"):
        (limited_root / name).write_text("double value;\n", encoding="utf-8")
    units = [
        {
            "file": name,
            "directory": str(limited_root),
            "arguments": ["clang", "-c", name],
        }
        for name in ("one.c", "two.c")
    ]
    limited = make_request(limited_root, units)
    limited["schema_version"] = "1.4"
    limited["budgets"] = {"max_files": 1}
    result = ApplicationScanner(FakeFrontend()).scan(limited)
    assert result["scan"]["status"] == "failed"
    assert result["diagnostics"][0]["code"] == "budget_exceeded"

    cached = make_request(tmp_path / "cached")
    cached["schema_version"] = "1.4"
    cached["cache"] = {
        "mode": "read-write",
        "root": str(tmp_path / "cached" / ".cache"),
    }
    frontend = FakeFrontend()
    first = ApplicationScanner(frontend).scan(cached)
    second = ApplicationScanner(frontend).scan(cached)
    assert first["scan"]["status"] == second["scan"]["status"] == "complete"
    assert first["scan"]["semanticDigest"] == second["scan"]["semanticDigest"]
    assert len(frontend.calls) == 1
    runtime = second["extensions"]["org.rvport.floating-point-scanner.runtime"]
    assert runtime["cache"]["hit"] == 1

    cache_file = next((tmp_path / "cached" / ".cache").rglob("*.json"))
    cache_file.write_text("not-json", encoding="utf-8")
    corrupted = ApplicationScanner(frontend).scan(cached)
    runtime = corrupted["extensions"]["org.rvport.floating-point-scanner.runtime"]
    assert runtime["cache"]["corrupt"] >= 1
    assert any(
        item["code"] == "cache_entry_corrupt" for item in corrupted["diagnostics"]
    )

    monkeypatch.setattr(
        application_module.AnalysisCache,
        "write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")),
    )
    failed_publish = make_request(tmp_path / "publish")
    failed_publish["schema_version"] = "1.4"
    failed_publish["cache"] = {
        "mode": "write-only",
        "root": str(tmp_path / "publish" / ".cache"),
    }
    result = ApplicationScanner(FakeFrontend()).scan(failed_publish)
    assert any(item["code"] == "cache_publish_failed" for item in result["diagnostics"])

    diagnostics = [diagnostic(str(index), "test", "中", "en") for index in range(3)]
    result = ApplicationScanner._result(
        "request",
        "partial",
        0,
        0,
        0,
        0,
        [],
        diagnostics,
        {},
        {},
        diagnostic_limit=2,
    )
    assert result["diagnostics"][-1]["code"] == "diagnostic_budget_exceeded"


def test_application_clang_budget_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class StubClang(ClangFrontend):
        def __init__(self) -> None:
            super().__init__(tmp_path / "clang", timeout=5, output_limit=1024)

        def verify(self, **_kwargs: Any) -> None:
            return None

        def ast(self, context: Any, **_kwargs: Any) -> dict[str, Any]:
            return ast_for(context.absolute_file)

    request = make_request(tmp_path / "clang")
    request["schema_version"] = "1.4"
    request["budgets"] = {
        "wall_seconds": 10,
        "cpu_seconds": 10,
        "max_memory_bytes": 1024**3,
        "max_frontend_output_bytes": 2048,
    }
    monkeypatch.setattr(application_module, "resource_limits_supported", lambda: False)
    unsupported = ApplicationScanner(StubClang()).scan(request)
    assert unsupported["scan"]["status"] == "failed"
    assert unsupported["diagnostics"][0]["code"] == "resource_budget_unsupported"
    monkeypatch.setattr(application_module, "resource_limits_supported", lambda: True)
    assert ApplicationScanner(StubClang()).scan(request)["scan"]["status"] == "complete"

    class ExhaustedBudget(BudgetCoordinator):
        def check_resources(self, scope: str, frontier: str | None = None) -> None:
            raise BudgetExceeded(BudgetFrontier("wall_seconds", 1, 1, scope, frontier))

    monkeypatch.setattr(application_module, "BudgetCoordinator", ExhaustedBudget)
    result = ApplicationScanner(StubClang()).scan(request)
    assert result["scan"]["status"] == "failed"
    assert result["diagnostics"][0]["code"] == "budget_exceeded"


def test_application_bitcode_cache_hits_and_publish_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.unit.test_application_bitcode import Frontend, Worker

    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "hot"))
    request["schema_version"] = "1.4"
    request["cache"] = {
        "mode": "read-write",
        "root": str(tmp_path / "hot" / ".cache"),
    }
    worker = Worker()
    scanner = ApplicationScanner(Frontend(), ir_worker=worker)  # type: ignore[arg-type]
    cold = scanner.scan(request)
    assert cold["scan"]["status"] == "complete"
    hot = scanner.scan(request)
    assert hot["scan"]["status"] == "complete"
    assert cold["scan"]["semanticDigest"] == hot["scan"]["semanticDigest"]
    assert worker.calls == 1
    runtime = hot["extensions"]["org.rvport.floating-point-scanner.runtime"]
    assert runtime["cache"]["hit"] == 3
    cache_root = tmp_path / "hot" / ".cache"
    next((cache_root / "ir-facts").rglob("*.json")).write_text("bad", encoding="utf-8")
    next((cache_root / "evidence").rglob("*.json")).write_text("bad", encoding="utf-8")
    recovered = scanner.scan(request)
    assert recovered["scan"]["status"] == "complete"
    runtime = recovered["extensions"]["org.rvport.floating-point-scanner.runtime"]
    assert runtime["cache"]["corrupt"] >= 2
    assert any(
        item["code"] == "cache_entry_corrupt" for item in recovered["diagnostics"]
    )

    failed_request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "failed"))
    failed_request["schema_version"] = "1.4"
    failed_request["cache"] = {
        "mode": "write-only",
        "root": str(tmp_path / "failed" / ".cache"),
    }
    monkeypatch.setattr(
        application_module.AnalysisCache,
        "write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")),
    )
    failed = ApplicationScanner(Frontend(), ir_worker=Worker()).scan(  # type: ignore[arg-type]
        failed_request
    )
    assert failed["scan"]["status"] == "complete"
    assert (
        sum(
            item["count"]
            for item in failed["diagnostics"]
            if item["code"] == "cache_publish_failed"
        )
        == 3
    )


def test_protocol_invariant_cache_and_rule_helper_branches(tmp_path: Path) -> None:
    registry = SchemaRegistry()
    assert registry._result_invariants({})[0].diagnostic_code == "unsupported-result-version"
    base = failure_result_v2("request", "complete", [])
    base["summary"]["findings"] = 1
    assert registry._result_invariants(base)[0].diagnostic_code == "count-mismatch"

    legacy = make_request(tmp_path / "legacy")
    legacy["cache"] = {"mode": "off"}
    assert parse_request(legacy, registry)[1][0].diagnostic_code == "cache_version_unsupported"

    assert rules_module._integer_constant_exact("not-a-number", 24) is None
    assert rules_module._integer_constant_exact("4.0", 2) is True
    assert rules_module._integer_constant_exact("0", 1) is True
    assert rules_module._floating_constant_exact("nan", 24) is True
    assert rules_module._floating_constant_exact("bad", 24) is None
    assert rules_module._floating_constant_exact("1e1000", 24) is False
    assert rules_module._floating_constant_exact("1.0", 64) is None


def test_schema_14_cache_and_suppression_expiry(tmp_path: Path) -> None:
    request = make_request(tmp_path)
    request.update(
        schema_version="1.4",
        policy_as_of="2026-10-01",
        cache={"mode": "read-write", "root": str(tmp_path / ".cache")},
        suppressions=[
            {
                "code": "fragile-fp-comparison",
                "path": "src/*.c",
                "reason": "reviewed",
                "expires_on": "2026-09-30",
            }
        ],
    )
    parsed, errors = parse_request(request, SchemaRegistry())
    assert errors == [] and parsed is not None
    assert parsed.cache.mode == "read-write"
    assert parsed.suppressions[0].expires_on == "2026-09-30"

    finding = {
        "finding_id": "a" * 64,
        "finding_code": "fragile-fp-comparison",
        "location": {"path": "src/value.c", "line": 1},
    }
    visible, records = apply_suppressions(
        [finding], parsed.suppressions, policy_as_of=parsed.policy_as_of
    )
    assert visible == (finding,) and records[0]["status"] == "expired"
    visible, records = apply_suppressions(
        [finding],
        [Suppression("fragile-fp-comparison", "src/*.c", "reviewed", expires_on="2026-10-01")],
        policy_as_of="2026-10-01",
    )
    assert visible == () and records[0]["status"] == "applied"
    _, unmatched = apply_suppressions(
        [], [Suppression("fragile-fp-comparison", "src/*.c", "reviewed")]
    )
    assert unmatched[0]["finding_id"] is None and unmatched[0]["status"] == "unmatched"

    missing_policy = copy.deepcopy(request)
    missing_policy.pop("policy_as_of")
    assert parse_request(missing_policy, SchemaRegistry())[1][0].diagnostic_code == (
        "invalid_suppression"
    )
    outside = copy.deepcopy(request)
    outside["cache"]["root"] = str(tmp_path.parent / "outside")
    assert parse_request(outside, SchemaRegistry())[1][0].diagnostic_code == (
        "cache_root_outside_project"
    )
    legacy = copy.deepcopy(request)
    legacy["schema_version"] = "1.3"
    assert parse_request(legacy, SchemaRegistry())[1][0].diagnostic_code == ("invalid_suppression")
    assert CACHE_SCHEMA_VERSION == "1.0"
