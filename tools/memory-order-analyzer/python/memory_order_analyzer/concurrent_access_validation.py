"""Offline adjudicated truth and provenance checks for R2."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter, process_time
import tracemalloc

from .contracts import AnalysisError, file_hash
from .concurrent_access_analysis import pair_accesses
from .concurrent_access_contracts import expected_concurrent_access_protocol


LANGUAGES = ("c11", "c17", "c++17", "c++20")


def collect_scale_metrics(access_count=1000):
    """Measure the fixed disjoint-object corpus; observations are not semantic identity."""
    budgets = deepcopy(expected_concurrent_access_protocol()["budgets"])
    accesses, instances = [], []
    for number in range(access_count):
        access_id, instance_id = f"access-{number:06d}", f"instance-{number:06d}"
        storage_id = f"storage-{number:06d}"
        accesses.append({"id": access_id, "execution_instance_id": instance_id,
                         "operation": "write", "atomic": False, "guards": [],
                         "object_domain": {"state": "must", "reason": None, "candidates": [{
                             "object": {"id": storage_id, "storage": {"id": storage_id,
                             "kind": "global", "address_space": 0}, "path": [],
                             "byte_range": {"offset": 0, "size": 4}},
                             "guards": [], "proof": [], "opposed": []}]},
                         "evidence": [access_id]})
        instances.append({"id": instance_id, "cardinality": "single"})
    request = {"budgets": budgets}
    projection = {"accesses": accesses}
    execution = {"instances": instances, "mhp": []}
    tracemalloc.start(); wall_start, cpu_start = perf_counter(), process_time()
    result = pair_accesses(request, projection, execution)
    cpu_seconds, wall_seconds = process_time() - cpu_start, perf_counter() - wall_start
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    return {"accesses": access_count, **result["counts"],
            "candidates": len(result["candidates"]), "frontier": len(result["frontier"]),
            "cpu_seconds": cpu_seconds, "wall_seconds": wall_seconds,
            "peak_bytes": peak,
            "output_bytes": len(json.dumps(result, sort_keys=True).encode("utf-8"))}


def validate_fixture_provenance(root, manifest):
    root = root.resolve()
    seen = set()
    for item in manifest.get("fixtures", []):
        case_id = item.get("case_id")
        if not case_id or case_id in seen:
            raise AnalysisError("fixture_provenance", "R2 fixture case ids must be non-empty and unique")
        seen.add(case_id)
        path = (root / item["path"]).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise AnalysisError("fixture_provenance", "R2 fixture path escapes its corpus") from exc
        if not path.is_file() or file_hash(path) != item["sha256"]:
            raise AnalysisError("fixture_provenance", f"R2 fixture digest changed: {item['path']}")
        if item.get("imported_from") and not item.get("rewrite_reason"):
            raise AnalysisError("fixture_provenance", "Imported R2 fixtures require a rewrite reason")
    return True


def compare_truth(suite, truth, actuals):
    expected = {item["case_id"]: item for item in truth["cases"]}
    metrics = {"planned": len(suite["cases"]), "completed": 0, "failed": 0,
               "tp": 0, "fp": 0, "fn": 0, "abstention": 0,
               "protected": 0, "excluded": 0, "frontier": 0}
    languages = {name: {key: 0 for key in metrics} for name in LANGUAGES}
    diagnostics, cases = [], []
    for case in suite["cases"]:
        case_id, language = case["case_id"], case["standard"]
        languages[language]["planned"] += 1
        actual = actuals.get(case_id)
        wanted = expected[case_id]
        if actual is None:
            metrics["failed"] += 1; languages[language]["failed"] += 1
            metrics["abstention"] += 1; languages[language]["abstention"] += 1
            diagnostics.append({"code": "truth-actual-missing", "case_id": case_id,
                                "expected": deepcopy(wanted), "actual": None})
            cases.append({"case_id": case_id, "standard": language, "exact": False,
                          "expected": deepcopy(wanted), "actual": None})
            continue
        expected_status = wanted.get("status", "complete")
        if actual.get("status") == "failed":
            metrics["failed"] += 1; languages[language]["failed"] += 1
            metrics["abstention"] += 1; languages[language]["abstention"] += 1
            exact = expected_status == "failed"
            if not exact:
                diagnostics.append({"code": "truth-status-mismatch", "case_id": case_id,
                                    "expected": deepcopy(wanted), "actual": deepcopy(actual)})
            cases.append({"case_id": case_id, "standard": language, "exact": exact,
                          "expected": deepcopy(wanted), "actual": deepcopy(actual)})
            continue
        metrics["completed"] += 1; languages[language]["completed"] += 1
        expected_pairs = set(wanted.get("candidate_pairs", []))
        actual_pairs = set(actual.get("candidate_pairs", []))
        tp, fp, fn = (len(expected_pairs & actual_pairs), len(actual_pairs - expected_pairs),
                      len(expected_pairs - actual_pairs))
        for key, value in (("tp", tp), ("fp", fp), ("fn", fn)):
            metrics[key] += value; languages[language][key] += value
        for key in ("protected", "excluded", "frontier"):
            value = len(actual.get(key, []))
            metrics[key] += value; languages[language][key] += value
        abstained = bool(actual.get("frontier")) or actual.get("status") != "complete"
        if abstained:
            metrics["abstention"] += 1; languages[language]["abstention"] += 1
        exact = not (fp or fn) and expected_status == actual.get("status") and \
            set(wanted.get("protected", [])) == set(actual.get("protected", [])) and \
            set(wanted.get("excluded", [])) == set(actual.get("excluded", [])) and \
            set(wanted.get("frontier", [])) == set(actual.get("frontier", []))
        cases.append({"case_id": case_id, "standard": language, "exact": exact,
                      "expected": deepcopy(wanted), "actual": deepcopy(actual)})
        if not exact:
            diagnostics.append({"code": "truth-mismatch", "case_id": case_id,
                                "expected": deepcopy(wanted), "actual": deepcopy(actual)})
    return {"schema_version": 1, "kind": "ConcurrentAccessValidationReport",
            "status": "complete" if metrics["completed"] + metrics["failed"] == metrics["planned"]
            and not diagnostics else "partial",
            "metrics": metrics, "languages": languages, "diagnostics": diagnostics,
            "cases": cases, "safety": "not_evaluated", "findings": None}


def run_validation(fixture_root, output):
    fixture_root, output = Path(fixture_root).resolve(), Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "R2 validation output must be a new file")
    def load(name):
        try:
            return json.loads((fixture_root / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AnalysisError("validation_input", f"Invalid R2 validation input: {name}") from exc
    manifest, suite, truth, actual = (load("provenance.json"), load("validation-suite.json"),
                                      load("validation-truth.json"), load("validation-actual.json"))
    validate_fixture_provenance(fixture_root, manifest)
    report = compare_truth(suite, truth, actual["cases"])
    report["scale"] = collect_scale_metrics()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="运行 R2 四语言离线 truth 验证")
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_validation(args.fixture_root, args.output)
    except AnalysisError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
