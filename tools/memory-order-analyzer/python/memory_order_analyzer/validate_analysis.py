"""Isolated P5 validation runner over immutable P1--P4 structured artifacts."""

from copy import deepcopy
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from .contracts import AnalysisError, canonical, file_hash, identity
from .publication_contracts import read_publication_document
from .validation_analysis import (
    aggregate_layers,
    aggregate_metrics,
    backend_bundle,
    bind_truth,
    compare_backend,
    compare_case,
    extension_decision,
    public_case_result,
    semantic_digest,
    safe_path,
)
from .validation_contracts import (
    diagnostic,
    read_validation_document,
    validation_document,
    write_validation_document,
)


ALLOWED_OPERATIONS = frozenset({"collect", "index", "summarize", "model-threads", "detect-publication-risks"})
TOKENS = ("${ARTIFACT_STORE}", "${WORKER}", "${SUITE_DIR}", "${CASE_DIR}", "${RUN_DIR}")


def _replace_tokens(value, replacements):
    for token in TOKENS:
        value = value.replace(token, replacements[token])
    return value


def _resource_snapshot():
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return {"cpu_seconds": usage.ru_utime + usage.ru_stime,
                "peak_rss_bytes": float(usage.ru_maxrss * (1024 if sys.platform != "darwin" else 1))}
    except (ImportError, AttributeError):
        return {"cpu_seconds": time.process_time(), "peak_rss_bytes": 0.0}


def _directory_bytes(path):
    return sum(item.stat().st_size for item in Path(path).rglob("*") if item.is_file())


def _default_run(argv, *, cwd, env, timeout, stdout, stderr):
    return subprocess.run(argv, cwd=cwd, env=env, timeout=timeout, stdout=stdout, stderr=stderr,
                          check=False).returncode


def _run_stages(case, suite_dir, run_dir, artifact_store, worker, timeout, runner):
    replacements = {
        "${ARTIFACT_STORE}": str(Path(artifact_store).resolve()),
        "${WORKER}": str(Path(worker).resolve()),
        "${SUITE_DIR}": str(Path(suite_dir).resolve()),
        "${CASE_DIR}": str(safe_path(suite_dir, case["source_root"])),
        "${RUN_DIR}": str(Path(run_dir).resolve()),
    }
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    stage_results = []
    for index, stage in enumerate(case["stages"]):
        if stage["operation"] not in ALLOWED_OPERATIONS:
            raise AnalysisError("stage_invalid", f"Operation is not allowed: {stage['operation']}")
        arguments = [_replace_tokens(item, replacements) for item in stage["arguments"]]
        argv = [sys.executable, "-m", "memory_order_analyzer", stage["operation"], *arguments]
        stdout_path, stderr_path = run_dir / f"stage-{index}.stdout", run_dir / f"stage-{index}.stderr"
        started = time.perf_counter()
        before = _resource_snapshot()
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
                code = runner(argv, cwd=run_dir, env=environment, timeout=timeout, stdout=stdout, stderr=stderr)
        except subprocess.TimeoutExpired:
            stage_results.append({"operation": stage["operation"], "status": "partial", "exit_code": None,
                                  "wall_seconds": time.perf_counter() - started, "cpu_seconds": 0.0,
                                  "peak_rss_bytes": 0.0, "reason": "timeout"})
            break
        after = _resource_snapshot()
        report_path = safe_path(run_dir, stage["report"])
        ok = code in stage["allowed_exit_codes"] and report_path.is_file()
        try:
            stage_report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        except (OSError, ValueError):
            stage_report = {}
        counts = stage_report.get("counts", {})
        cache_hits = int(counts.get("cache_hits", 0))
        cache_misses = max(0, int(counts.get("generated", 0)) - cache_hits)
        stage_results.append({
            "operation": stage["operation"], "status": "complete" if ok else "failed", "exit_code": code,
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": max(0.0, after["cpu_seconds"] - before["cpu_seconds"]),
            "peak_rss_bytes": after["peak_rss_bytes"], "reason": None if ok else "stage-failed",
            "cache_hits": cache_hits, "cache_misses": cache_misses,
        })
        if not ok:
            break
    return stage_results


def _observation_path(case, key, suite_dir, run_dir):
    relative = case[key]
    if relative is None:
        raise AnalysisError("observation_missing", f"Case {case['id']} has no {key}")
    run_candidate = safe_path(run_dir, relative)
    return run_candidate if run_candidate.is_file() else safe_path(suite_dir, relative)


def _read_observation(case, suite_dir, run_dir):
    report_path = _observation_path(case, "observation_report", suite_dir, run_dir)
    graph_path = _observation_path(case, "observation_graph", suite_dir, run_dir)
    report = read_publication_document(report_path, "PublicationRiskReport")
    graph = read_publication_document(graph_path, "SinglePublicationProtocolGraph")
    if report["graph"] is None or report["graph"]["digest"] != identity(graph):
        raise AnalysisError("dependency_replaced", f"P4 report/graph binding failed for {case['id']}")
    if report["request_hash"] != graph["request_hash"] or report["scope_id"] != graph["scope_id"]:
        raise AnalysisError("dependency_replaced", f"P4 scope/request binding failed for {case['id']}")
    return report, graph


def _case_layers(report, stages, truth_ok=True):
    stage_status = {item["operation"]: item["status"] for item in stages}
    return {
        "request_input": "complete",
        "compile": stage_status.get("collect", "complete"),
        "p1": report.get("p1_analysis", "failed"),
        "p2": report.get("p2_analysis", "failed"),
        "p3": report.get("p3_analysis", "failed"),
        "p4": report.get("risk_evaluation", "failed"),
        "truth": "complete" if truth_ok else "failed",
        "sampling": "complete",
        "performance": "complete",
    }


def _load_backends(case, suite_dir, requested, truth, result):
    bundles, comparisons = [], []
    entries = [item for item in case["sources"] if item["role"] == "backend-output"]
    for backend in requested:
        match = next((item for item in entries if Path(item["path"]).stem.startswith(backend)), None)
        if match is None:
            placeholder = backend_bundle(
                backend, case["id"], truth["input_digest"], version="unavailable", license_id="unknown",
                command=[], applicability="applicable", status="unavailable",
                diagnostics=[diagnostic("backend_unavailable", "请求的后端不可用", "Requested backend is unavailable")],
            )
            bundles.append(placeholder)
        else:
            if file_hash(safe_path(suite_dir, match["path"])) != match["sha256"]:
                raise AnalysisError("dependency_replaced", f"Backend bundle changed: {match['path']}")
            bundles.append(read_validation_document(safe_path(suite_dir, match["path"]), "BackendEvidenceBundle"))
        comparisons.append(compare_backend(truth, result, bundles[-1]))
    status = "complete" if all(item["status"] == "complete" for item in bundles) else "partial" if bundles else "complete"
    return bundles, comparisons, status


def _validate_request_dependencies(request_path, request):
    suite_path = Path(request["suite"])
    if not suite_path.is_absolute():
        suite_path = Path(request_path).resolve().parent / suite_path
    suite_path = suite_path.resolve()
    if not suite_path.is_file() or file_hash(suite_path) != request["suite_sha256"]:
        raise AnalysisError("dependency_replaced", "Validation suite is missing or its hash changed")
    suite = read_validation_document(suite_path, "ValidationSuiteManifest")
    return suite_path, suite


def validate_analysis(request_path, artifact_store, output, worker, *, runner=_default_run):
    request_path, output = Path(request_path).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise AnalysisError("output_exists", "Validation output must be a new or empty directory")
    output.mkdir(parents=True, exist_ok=True)
    request = read_validation_document(request_path, "AnalysisValidationRequest")
    suite_path, suite = _validate_request_dependencies(request_path, request)
    suite_dir = suite_path.parent
    by_id = {case["id"]: case for case in suite["cases"]}
    selected_ids = request["case_ids"] or sorted(by_id)
    if any(identifier not in by_id for identifier in selected_ids):
        raise AnalysisError("invalid_reference", "Validation request names an unknown case")
    if len(selected_ids) > request["budgets"]["max_cases"]:
        raise AnalysisError("budget_exhausted", "Selected validation cases exceed max_cases")
    request_hash, suite_digest = identity(request), identity(suite)
    write_validation_document(output / "request.json", request, "AnalysisValidationRequest")
    started_request = time.perf_counter()
    worker_path = Path(worker)
    performance = {"cases": [], "environment_fingerprint": identity({
        "python": sys.version, "platform": platform.platform(),
        "worker_sha256": file_hash(worker_path) if worker_path.is_file() else None,
    })}
    results, case_layers, all_backends = [], [], []
    report_diagnostics, frontier = [], []
    for case_id in selected_ids:
        if time.perf_counter() - started_request > request["budgets"]["request_seconds"]:
            frontier.append(diagnostic("request_timeout", "验证请求超过时间预算", "Validation request exceeded its time budget"))
            break
        case = by_id[case_id]
        truth_path = safe_path(suite_dir, case["truth"]["path"])
        truth = bind_truth(suite_dir, suite, case, read_validation_document(truth_path, "TruthAnnotation"))
        mode_results, mode_reports, layers = [], [], None
        for mode in request["run_modes"]:
            run_dir = output / "cases" / case_id / mode
            run_dir.mkdir(parents=True, exist_ok=False)
            stages = _run_stages(case, suite_dir, run_dir, artifact_store, worker,
                                 request["budgets"]["case_seconds"], runner)
            report, graph = _read_observation(case, suite_dir, run_dir)
            compared = compare_case(case, truth, report, graph)
            compared["semantic_digests"][mode] = semantic_digest(
                {"report": report, "graph": graph},
                roots=(("${RUN_DIR}", run_dir), ("${SUITE_DIR}", suite_dir), ("${ARTIFACT_STORE}", artifact_store)),
            )
            compared["resources"] = {
                "wall_seconds": sum(item["wall_seconds"] for item in stages),
                "cpu_seconds": sum(item["cpu_seconds"] for item in stages),
                "peak_rss_bytes": max((item["peak_rss_bytes"] for item in stages), default=0.0),
                "output_bytes": float(_directory_bytes(run_dir)),
            }
            mode_results.append(compared)
            mode_reports.append({"mode": mode, "stages": stages, "resources": compared["resources"],
                                 "semantic_digest": compared["semantic_digests"][mode]})
            layers = _case_layers(report, stages)
        result = mode_results[0]
        for other in mode_results[1:]:
            result["semantic_digests"].update(other["semantic_digests"])
            if set(result["semantic_digests"].values()) != {next(iter(result["semantic_digests"].values()))}:
                result["status"] = "partial"
                result["matched"] = False
                result["diagnostics"].append(diagnostic(
                    "cold_warm_mismatch", "cold/warm 语义摘要不一致", "Cold/warm semantic digests differ"))
                layers["performance"] = "partial"
        bundles, comparisons, backend_status = _load_backends(
            case, suite_dir, request["requested_backends"], truth, result)
        layers["backend"] = backend_status
        all_backends.extend(bundles)
        performance["cases"].append({"case_id": case_id, "runs": mode_reports,
                                     "backend_comparisons": comparisons})
        results.append(result)
        case_layers.append(layers)
    requested_backend = bool(request["requested_backends"])
    layers = aggregate_layers(case_layers, requested_backend)
    metrics = aggregate_metrics(results)
    mismatch = any(not item["matched"] for item in results)
    incomplete = len(results) != len(selected_ids) or any(layer["status"] != "complete" for layer in layers.values())
    if _directory_bytes(output) > request["budgets"]["output_bytes"]:
        incomplete = True
        layers["performance"] = {"status": "partial", "hit": 0, "total": max(1, len(results))}
        frontier.append(diagnostic("output_budget", "验证输出超过字节预算", "Validation output exceeded its byte budget"))
    exit_code = 2 if incomplete else 3 if mismatch else 0
    verdict = "inconclusive" if incomplete else "mismatch" if mismatch else "matched"
    report = validation_document(
        "AnalysisValidationReport", request_hash=request_hash, suite_digest=suite_digest,
        layers=layers, cases=[public_case_result(item) for item in results], metrics=metrics,
        performance=performance, backend_dependencies=[identity(item) for item in all_backends],
        diagnostics=report_diagnostics, frontier=frontier, safety="not_established",
        verdict=verdict, exit_code=exit_code,
    )
    write_validation_document(output / "report.json", report, "AnalysisValidationReport")
    for bundle in all_backends:
        write_validation_document(output / "backends" / f"{bundle['backend']}-{bundle['case_id']}.json",
                                  bundle, "BackendEvidenceBundle")
    evidence = {name: {} for name in ("b1-cmake-scope", "std-thread", "pointer-analysis", "fence-rmw")}
    for item in report["frontier"] + report["diagnostics"]:
        for name in evidence:
            if name in item["code"]:
                evidence[name]["blocking_cases"] = evidence[name].get("blocking_cases", 0) + 1
    for item in evidence.values():
        item["denominator"] = len(results)
    decision = extension_decision(request_hash, identity(report), evidence)
    write_validation_document(output / "decision.json", decision, "AnalysisExtensionDecision")
    return report
