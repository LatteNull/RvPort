"""Four-profile truth comparison for degraded source analysis."""

from .contracts import AnalysisError, identity
from .degraded_contracts import degraded_document, diagnostic


PROFILES = ("c11", "c17", "c++17", "c++20")


def _ratio(hit, total):
    return {"hit": hit, "total": total, "value": None if total == 0 else hit / total}


def _metrics(cases, truth, observations):
    planned, completed = len(cases), 0
    eligible = tp = fp = fn = exact = abstained = 0
    modes = {name: 0 for name in ("ast-ir", "ir-only", "ast-only", "failed", "mixed")}
    source_candidates = formal_candidates = 0
    for case in cases:
        observed = observations.get(case["id"])
        if observed is None:
            continue
        completed += 1
        mode = observed.get("mode", "failed")
        modes[mode] = modes.get(mode, 0) + 1
        source_candidates += observed.get("source_candidates", 0)
        formal_candidates += observed.get("formal_candidates", 0)
        expected = truth[case["id"]]
        if not case["eligible"]:
            continue
        eligible += 1
        verdict = observed.get("formal", "unknown")
        if verdict == expected["formal"] and mode == expected["mode"]:
            exact += 1
        if expected["formal"] == "risk" and verdict == "risk":
            tp += 1
        elif expected["formal"] != "risk" and verdict == "risk":
            fp += 1
        elif expected["formal"] == "risk" and verdict != "risk":
            fn += 1
        if verdict in {"unknown", "failed"}:
            abstained += 1
    return {
        "planned": planned, "completed": completed, "eligible": eligible, "modes": modes,
        "source_candidates": source_candidates, "formal_candidates": formal_candidates,
        "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "exact_match": _ratio(exact, eligible), "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn), "abstention": _ratio(abstained, eligible),
    }


def validate_degraded_suite(suite, truth, observations, *, performance=None):
    if suite["suite_id"] != truth["suite_id"] or truth["suite_digest"] != identity(suite):
        raise AnalysisError("truth_stale", "Degraded validation truth does not match the suite")
    truth_cases = truth.get("cases", [])
    ids = [item.get("case_id") for item in truth_cases]
    if ids != sorted(set(ids)) or set(ids) != {item["id"] for item in suite["cases"]}:
        raise AnalysisError("validation_denominator", "Truth cases must uniquely match the suite")
    expected = {}
    for item in truth_cases:
        if item.get("mode") not in {"ast-ir", "ir-only", "ast-only", "failed", "mixed"} or item.get("formal") not in {"risk", "no-risk", "unknown", "failed"}:
            raise AnalysisError("validation_truth", "Truth cases require independent mode and formal expectations")
        expected[item["case_id"]] = item
    profiles = {profile: _metrics([item for item in suite["cases"] if item["standard"] == profile], expected, observations)
                for profile in PROFILES}
    aggregate = _metrics(suite["cases"], expected, observations)
    missing = [profile for profile, value in profiles.items() if value["planned"] == 0 or value["completed"] < value["planned"]]
    diagnostics = []
    if missing:
        diagnostics.append(diagnostic(
            "profile-incomplete", "一个或多个语言 profile 未完成独立验证", "One or more language profiles did not complete independent validation",
            suggestion="补齐 C11、C17、C++17 和 C++20 的独立分母", suggestion_en="Complete the independent C11, C17, C++17, and C++20 denominators",
            source={"profiles": missing}))
    status = "complete" if not missing else "partial"
    return degraded_document(
        "DegradedValidationReport", suite_id=suite["suite_id"], suite_digest=identity(suite),
        truth_digest=identity(truth), status=status, profiles=profiles, aggregate=aggregate,
        performance=performance or {}, diagnostics=diagnostics, frontier=list(diagnostics),
        safety="not-established", semantic_digest=None)
