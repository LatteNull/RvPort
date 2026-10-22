"""Offline, adjudicated A3 lifecycle truth comparison with separate language denominators."""

from .cpp_thread_contracts import cpp_thread_document, diagnostic, validate_cpp_thread_document


def _actual_sets(graph):
    if graph is None:
        return {"callables": set(), "instances": set(), "relations": set(), "unknown": {"missing-result"}}
    unknown = {item["code"] for item in [*graph.get("gaps", []), *graph.get("frontier", [])]}
    return {
        "callables": {item["callable_id"] for item in graph.get("contexts", [])},
        "instances": {item["id"] for item in graph.get("instances", [])},
        "relations": {f"{item['relation']}:{item['from']}:{item['to']}" for item in graph.get("relations", [])},
        "unknown": unknown,
    }


def compare_lifecycle_truth(suite, truth, actuals, profiles=()):
    validate_cpp_thread_document(suite, "CppThreadValidationSuite")
    validate_cpp_thread_document(truth, "CppThreadValidationTruth")
    if suite["suite_version"] != truth["suite_version"]:
        raise ValueError("A3 validation suite and truth versions differ")
    truth_by_id = {item["case_id"]: item for item in truth["cases"]}
    if set(truth_by_id) != {item["id"] for item in suite["cases"]}:
        raise ValueError("A3 validation truth denominator differs from the suite")
    metrics = {name: 0 for name in ("expected", "actual", "exact", "fp", "fn", "unknown", "abstention")}
    languages = {name: {key: 0 for key in ("planned", "completed", "failed", "unknown", "abstention")}
                 for name in ("c11", "c17", "c++17", "c++20")}
    diagnostics = []
    for case in suite["cases"]:
        standard = case["standard"]
        languages[standard]["planned"] += 1
        graph = actuals.get(case["id"])
        if graph is None or graph.get("status") == "failed":
            languages[standard]["failed"] += 1
        else:
            languages[standard]["completed"] += 1
        actual = _actual_sets(graph)
        expected = truth_by_id[case["id"]]
        case_exact = True
        for dimension in ("callables", "instances", "relations", "unknown"):
            left, right = set(expected[dimension]), actual[dimension]
            metrics["expected"] += len(left); metrics["actual"] += len(right)
            metrics["fp"] += len(right - left); metrics["fn"] += len(left - right)
            case_exact &= left == right
        metrics["exact"] += case_exact
        is_unknown = bool(actual["unknown"]) or graph is None or graph.get("status") != "complete"
        if is_unknown:
            metrics["unknown"] += 1; metrics["abstention"] += 1
            languages[standard]["unknown"] += 1; languages[standard]["abstention"] += 1
        if not case_exact:
            diagnostics.append(diagnostic(
                "truth-mismatch", f"生命周期真值不匹配：{case['id']}",
                f"Lifecycle truth mismatch: {case['id']}",
                suggestion="检查 callable、instance、relation 与 unknown 的独立差异",
                suggestion_en="Inspect callable, instance, relation, and unknown differences independently",
                source={"case_id": case["id"]}))
    status = "complete" if metrics["fp"] == 0 and metrics["fn"] == 0 else "partial"
    return cpp_thread_document(
        "CppThreadValidationReport", suite_version=suite["suite_version"], status=status,
        profiles=list(profiles), metrics=metrics, languages=languages,
        diagnostics=diagnostics, semantic_digest=None)
