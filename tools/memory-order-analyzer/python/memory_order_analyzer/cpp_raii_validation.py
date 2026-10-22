"""Adjudicated A4 truth comparison with separate language/vendor denominators."""

from .cpp_raii_contracts import cpp_raii_document, dependency, diagnostic, validate_cpp_raii_document


def _actual_sets(graph):
    if graph is None:
        return {name: set() for name in ("mutexes", "owners", "regions", "proofs")} | {
            "unknown": {"missing-result"}}
    return {
        "mutexes": {item["object_id"] for item in graph.get("mutexes", [])},
        "owners": {item["object_id"] for item in graph.get("owners", [])},
        "regions": {f"{item['owner_id']}:{item['thread_id']}" for item in graph.get("held_regions", [])},
        "proofs": {f"{item['proof_kind']}:{item['mutex_id']}" for item in graph.get("proofs", [])},
        "unknown": {item["code"] for item in [*graph.get("gaps", []), *graph.get("frontier", [])]},
    }


def compare_synchronization_truth(suite, truth, actuals, profiles=()):
    validate_cpp_raii_document(suite, "CppRaiiValidationSuite")
    validate_cpp_raii_document(truth, "CppRaiiValidationTruth")
    if suite["suite_version"] != truth["suite_version"]:
        raise ValueError("A4 validation suite and truth versions differ")
    expected_by_id = {item["case_id"]: item for item in truth["cases"]}
    if set(expected_by_id) != {item["id"] for item in suite["cases"]}:
        raise ValueError("A4 validation truth denominator differs from the suite")
    dimensions = ("mutexes", "owners", "regions", "proofs", "unknown")
    metrics = {name: 0 for name in ("expected", "actual", "exact", "tp", "fp", "fn",
                                     "unknown", "abstention")}
    languages = {name: {key: 0 for key in ("planned", "completed", "eligible", "failed",
                                            "unknown", "abstention")}
                 for name in ("c11", "c17", "c++17", "c++20")}
    diagnostics = []
    for case in suite["cases"]:
        standard = case["standard"]
        result = actuals.get(case["id"])
        languages[standard]["planned"] += 1
        if result is None or result.get("status") == "failed":
            languages[standard]["failed"] += 1
        else:
            languages[standard]["completed"] += 1
            if case.get("eligible", True):
                languages[standard]["eligible"] += 1
        actual = _actual_sets(result)
        expected = expected_by_id[case["id"]
        ]
        exact = True
        for dimension in dimensions:
            left, right = set(expected.get(dimension, [])), actual[dimension]
            metrics["expected"] += len(left)
            metrics["actual"] += len(right)
            metrics["tp"] += len(left & right)
            metrics["fp"] += len(right - left)
            metrics["fn"] += len(left - right)
            exact &= left == right
        metrics["exact"] += int(exact)
        abstained = result is None or result.get("status") != "complete" or bool(actual["unknown"])
        if abstained:
            metrics["unknown"] += 1
            metrics["abstention"] += 1
            languages[standard]["unknown"] += 1
            languages[standard]["abstention"] += 1
        if not exact:
            diagnostics.append(diagnostic(
                "truth-mismatch", f"RAII 同步真值不匹配：{case['id']}",
                f"RAII synchronization truth mismatch: {case['id']}",
                suggestion="分别检查 mutex、owner、thread、held-region、proof 与 unknown",
                suggestion_en="Inspect mutex, owner, thread, held-region, proof, and unknown separately",
                source={"case_id": case["id"]},
            ))
    status = "complete" if metrics["fp"] == 0 and metrics["fn"] == 0 else "partial"
    profile_refs = sorted((dependency("CppRaiiSynchronizationProfile", item["profile_id"], item)
                           for item in profiles), key=lambda item: (item["kind"], item["id"]))
    return cpp_raii_document(
        "CppRaiiValidationReport", suite_version=suite["suite_version"], status=status,
        profiles=profile_refs, metrics=metrics, languages=languages,
        diagnostics=diagnostics, semantic_digest=None,
    )
