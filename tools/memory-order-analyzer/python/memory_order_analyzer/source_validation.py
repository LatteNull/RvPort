"""Truth-preserving comparison of IR-only and explicit AST-assisted observations."""

from .contracts import AnalysisError, identity
from .source_contracts import counts, diagnostic, source_document, validate_source_document
from .validation_analysis import extension_decision
from .validation_contracts import validate_validation_document


LAYERS = ("profile_replay", "source_extraction", "entity_resolution", "entity_binding",
          "expression_binding", "overlay", "candidate_slices")


def _metric(hit, total):
    return {"hit": hit, "total": total, "value": None if total == 0 else hit / total}


def _mode_metrics(observations, truth):
    expected = {item["case_id"]: item for item in truth["cases"]}
    tp = fp = fn = exact = abstained = 0
    supported_tp = supported_fp = supported_fn = 0
    for item in observations:
        target = expected[item["case_id"]]["verdict"]
        actual = item["verdict"]
        target_risk, actual_risk = target == "risk", actual == "risk"
        item_tp = int(item.get("true_positive", target_risk and actual_risk))
        item_fp = int(item.get("false_positive", not target_risk and actual_risk))
        item_fn = int(item.get("false_negative", target_risk and not actual_risk))
        tp += item_tp
        fp += item_fp
        fn += item_fn
        exact += bool(item.get("matched", target == actual))
        abstained += bool(item.get("abstained", item["status"] != "complete" or actual == "unknown"))
        if item.get("supported", False):
            supported_tp += item_tp
            supported_fp += item_fp
            supported_fn += item_fn
    return {
        "cases": len(observations), "true_positive": tp, "false_positive": fp,
        "false_negative": fn, "exact_match": _metric(exact, len(observations)),
        "precision": _metric(tp, tp + fp), "recall": _metric(tp, tp + fn),
        "supported_precision": _metric(supported_tp, supported_tp + supported_fp),
        "supported_recall": _metric(supported_tp, supported_tp + supported_fn),
        "abstention": _metric(abstained, len(observations)),
    }


def _layers(observations):
    result = {}
    for name in LAYERS:
        values = [item.get("layers", {}).get(name) for item in observations]
        values = [item for item in values if item is not None]
        planned = sum(item["total"] for item in values)
        emitted = sum(item["hit"] for item in values)
        failed = planned - emitted
        status = "not_run" if not values else "complete" if failed == 0 and all(
            item["status"] == "complete" for item in values) else "partial"
        result[name] = {"status": status, "counts": counts(planned, planned, emitted, failed=failed)}
    return result


def build_ast_validation_report(suite, truth, observations, *, performance=None):
    validate_source_document(suite, "AstIrValidationSuite")
    validate_source_document(truth, "AstIrValidationTruth")
    if (truth["suite_id"], truth["suite_version"], truth["suite_digest"]) != (
            suite["suite_id"], suite["suite_version"], identity(suite)):
        raise AnalysisError("truth_stale", "AST/IR truth does not match the immutable suite")
    expected = {item["id"] for item in suite["cases"]}
    truth_cases = {item["case_id"] for item in truth["cases"]}
    if truth_cases != expected:
        raise AnalysisError("truth_stale", "AST/IR truth case denominator changed")
    seen = [(item["mode"], item["case_id"]) for item in observations]
    if len(seen) != len(set(seen)) or any(mode not in {"ir_only", "ast_assisted"} or case not in expected
                                          for mode, case in seen):
        raise AnalysisError("validation_observation", "Validation observations are duplicate or outside the suite")
    by_mode = {mode: sorted((item for item in observations if item["mode"] == mode),
                            key=lambda item: item["case_id"])
               for mode in ("ir_only", "ast_assisted")}
    modes = {mode: _mode_metrics(items, truth) for mode, items in by_mode.items()}
    ir = {item["case_id"]: item for item in by_mode["ir_only"]}
    ast = {item["case_id"]: item for item in by_mode["ast_assisted"]}
    truth_by_id = {item["case_id"]: item for item in truth["cases"]}
    common = sorted(set(ir) & set(ast))
    delta = {
        "new_hits": [case for case in common if ir[case]["verdict"] != truth_by_id[case]["verdict"]
                     and ast[case]["verdict"] == truth_by_id[case]["verdict"]],
        "new_false_positives": [case for case in common if ir[case]["verdict"] != "risk"
                                and ast[case]["verdict"] == "risk" and truth_by_id[case]["verdict"] != "risk"],
        "still_unknown": [case for case in common if ast[case]["verdict"] == "unknown"],
        "regressions": [case for case in common if ir[case]["verdict"] == truth_by_id[case]["verdict"]
                        and ast[case]["verdict"] != truth_by_id[case]["verdict"]],
    }
    layers = _layers(by_mode["ast_assisted"])
    missing = len(by_mode["ir_only"]) != len(expected) or len(by_mode["ast_assisted"]) != len(expected)
    partial = missing or any(item["status"] != "complete" for item in layers.values())
    frontier = []
    if missing:
        frontier.append(diagnostic("validation-denominator-incomplete", "验证分母不完整",
                                   "Validation denominator is incomplete"))
    return source_document(
        "AstAssistedValidationReport", suite_id=suite["suite_id"], suite_digest=identity(suite),
        truth_digest=identity(truth), status="partial" if partial else "complete", layers=layers,
        modes=modes, delta=delta, performance=performance or {}, diagnostics=[], frontier=frontier,
        safety="not_established", semantic_digest=None)


def build_ast_extension_decision(suite, report):
    """Quantify P5 extension choices after observing the additive AST layer."""
    validate_source_document(suite, "AstIrValidationSuite")
    validate_source_document(report, "AstAssistedValidationReport")
    cases = {item["id"]: item for item in suite["cases"]}
    unknown = set(report["delta"]["still_unknown"])

    def evidence(selected, *, cost, compatibility):
        selected = set(selected)
        blocked = selected & unknown
        return {"denominator": len(selected), "blocking_cases": len(blocked),
                "blocking_tus": sum(3 if cases[key]["layout"] == "three-tu" else 1
                                     for key in blocked),
                "blocking_candidates": len(blocked), "cost": cost,
                "compatibility": compatibility}

    multi = {key for key, item in cases.items() if item["layout"] == "three-tu"}
    pointer_features = {"cross-tu-wrapper", "pthread-handle", "pthread-callback",
                        "odr", "template", "comdat", "profile-conflict"}
    pointer = {key for key, item in cases.items() if set(item["features"]) & pointer_features}
    fence_rmw = {key for key, item in cases.items()
                 if set(item["features"]) & {"fence", "rmw", "cas"}}
    decision = extension_decision(identity(suite), identity(report), {
        "b1-cmake-scope": evidence(multi, cost="medium", compatibility="compatible"),
        "std-thread": evidence(set(), cost="unknown", compatibility="unknown"),
        "pointer-analysis": evidence(pointer, cost="high", compatibility="migration"),
        "fence-rmw": evidence(fence_rmw, cost="high", compatibility="migration"),
    })
    new_hits = len(report["delta"]["new_hits"])
    for item in decision["entries"]:
        item["detail"] += f"；AST 层新增命中 {new_hits}，仍 unknown {len(unknown)}"
        item["detail_en"] += f"; AST added {new_hits} hits and left {len(unknown)} unknown cases"
    return validate_validation_document(decision, "AnalysisExtensionDecision")
