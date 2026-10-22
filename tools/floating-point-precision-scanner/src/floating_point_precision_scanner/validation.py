"""Reviewed corpus 的确定性质量统计与门禁。"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import REQUEST_SCHEMA_VERSION, RESULT_SCHEMA_VERSION, TOOL_VERSION
from .canonical import semantic_digest
from .result_v2 import EXTENSION_ANALYSIS, EXTENSION_SUPPRESSIONS
from .rules import RULE_BY_CODE

VALIDATION_SCHEMA_VERSION = "1.0"


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


@dataclass(frozen=True, slots=True)
class QualityCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    abstention: int = 0
    exact: int = 0
    total: int = 0
    supported_true_positive: int = 0
    supported_false_positive: int = 0
    supported_false_negative: int = 0

    def metrics(self) -> dict[str, Any]:
        return {
            "tp": self.true_positive,
            "fp": self.false_positive,
            "fn": self.false_negative,
            "abstention": self.abstention,
            "exact": self.exact,
            "total": self.total,
            "strict_precision": _ratio(
                self.true_positive, self.true_positive + self.false_positive
            ),
            "strict_recall": _ratio(self.true_positive, self.true_positive + self.false_negative),
            "supported_precision": _ratio(
                self.supported_true_positive,
                self.supported_true_positive + self.supported_false_positive,
            ),
            "supported_recall": _ratio(
                self.supported_true_positive,
                self.supported_true_positive + self.supported_false_negative,
            ),
            "exact_match": _ratio(self.exact, self.total),
        }


def _score_case(oracle: Mapping[str, Any], actual: Mapping[str, Any]) -> QualityCounts:
    expected = str(oracle["expected_status"])
    actual_status = str(actual.get("status", "missing"))
    expected_keys = frozenset(str(item) for item in oracle.get("finding_keys", []))
    actual_keys = frozenset(str(item) for item in actual.get("finding_keys", []))
    unsupported = bool(oracle.get("unsupported", False))
    abstained = actual_status in {"unknown", "skipped", "failed", "missing"}
    tp = len(expected_keys & actual_keys) if expected == "matched" else 0
    fp = len(actual_keys - expected_keys)
    if expected == "not_matched":
        fp += len(actual_keys & expected_keys)
    if unsupported and actual_status == "matched":
        fp += max(1, len(actual_keys))
    fn = len(expected_keys - actual_keys) if expected == "matched" else 0
    if expected == "matched" and abstained and not expected_keys:
        fn += 1
    diagnostics_exact = frozenset(actual.get("diagnostic_codes", [])) == frozenset(
        oracle.get("diagnostic_codes", [])
    )
    suppressions_exact = frozenset(actual.get("suppression_ids", [])) == frozenset(
        oracle.get("suppression_ids", [])
    )
    exact = int(
        expected == actual_status
        and expected_keys == actual_keys
        and diagnostics_exact
        and suppressions_exact
    )
    if unsupported:
        supported_tp = supported_fp = supported_fn = 0
    else:
        supported_tp, supported_fp, supported_fn = tp, fp, fn
    return QualityCounts(
        tp,
        fp,
        fn,
        int(abstained and expected == "matched"),
        exact,
        1,
        supported_tp,
        supported_fp,
        supported_fn,
    )


def _observation_from_result(result: Mapping[str, Any], rule_code: str) -> dict[str, Any]:
    """从结果 v2 提取 reviewed corpus 需要的最小 oracle 观察值。"""
    extensions = result.get("extensions")
    analysis = extensions.get(EXTENSION_ANALYSIS) if isinstance(extensions, Mapping) else None
    assessments = analysis.get("assessments", []) if isinstance(analysis, Mapping) else []
    matching = [
        item
        for item in assessments
        if isinstance(item, Mapping) and item.get("ruleCode") == rule_code
    ]
    status = str(matching[0].get("status", "missing")) if matching else "missing"
    if status == "notMatched":
        status = "not_matched"
    findings = result.get("findings", [])
    finding_keys: list[str] = []
    for item in findings if isinstance(findings, list) else []:
        if not isinstance(item, Mapping):
            continue
        conclusion = item.get("conclusion")
        if not isinstance(conclusion, Mapping) or conclusion.get("findingCode") != rule_code:
            continue
        semantic = conclusion.get("semantic")
        validation_key = (
            semantic.get("validationKey") if isinstance(semantic, Mapping) else None
        )
        finding_keys.append(str(validation_key or item.get("id")))
    diagnostics = result.get("diagnostics", [])
    suppression_extension = (
        extensions.get(EXTENSION_SUPPRESSIONS) if isinstance(extensions, Mapping) else None
    )
    suppressions = (
        suppression_extension.get("records", [])
        if isinstance(suppression_extension, Mapping)
        else []
    )
    return {
        "status": status,
        "finding_keys": sorted(finding_keys),
        "diagnostic_codes": sorted(
            str(item.get("code")) for item in diagnostics if isinstance(item, Mapping)
        ),
        "suppression_ids": sorted(
            str(item.get("id")) for item in suppressions if isinstance(item, Mapping)
        ),
    }


def _sum_counts(values: Sequence[QualityCounts]) -> QualityCounts:
    return QualityCounts(
        *(
            sum(getattr(value, field) for value in values)
            for field in QualityCounts.__dataclass_fields__
        )
    )


def evaluate_corpus(
    corpus: Mapping[str, Any],
    observed: Mapping[str, Mapping[str, Any]],
    *,
    minimum_rule_quality: float = 0.90,
    minimum_exact_match: float = 0.95,
) -> dict[str, Any]:
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("validation_corpus_has_no_cases")
    by_rule: dict[str, list[QualityCounts]] = defaultdict(list)
    class_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"positive": 0, "negative": 0, "unknown": 0}
    )
    case_results: list[dict[str, Any]] = []
    seen: set[str] = set()
    lifecycle_exact = True
    if any(not isinstance(item, Mapping) for item in cases):
        raise ValueError("invalid_validation_case")
    for raw in sorted(cases, key=lambda item: str(item.get("case_id", ""))):
        case_id = str(raw["case_id"])
        if case_id in seen:
            raise ValueError("duplicate_validation_case")
        seen.add(case_id)
        rule = str(raw["rule_code"])
        if rule not in RULE_BY_CODE:
            raise ValueError("unknown_validation_rule")
        actual = observed.get(case_id, {})
        if actual.get("schemaVersion") == RESULT_SCHEMA_VERSION:
            actual = _observation_from_result(actual, rule)
        score = _score_case(raw, actual)
        expected_status = str(raw["expected_status"])
        if expected_status == "matched":
            class_counts[rule]["positive"] += 1
        elif expected_status == "not_matched":
            class_counts[rule]["negative"] += 1
        elif bool(raw.get("unsupported", False)):
            class_counts[rule]["unknown"] += 1
        by_rule[rule].append(score)
        lifecycle = bool(raw.get("lifecycle", False))
        if lifecycle and not score.exact:
            lifecycle_exact = False
        case_results.append({"case_id": case_id, "rule_code": rule, "exact": bool(score.exact)})
    per_rule = {rule: _sum_counts(values).metrics() for rule, values in sorted(by_rule.items())}
    overall_counts = _sum_counts([item for values in by_rule.values() for item in values])
    overall = overall_counts.metrics()
    corpus_complete = set(class_counts) == set(RULE_BY_CODE) and all(
        counts["positive"] >= 6 and counts["negative"] >= 6 and counts["unknown"] >= 3
        for counts in class_counts.values()
    )
    rule_gate = all(
        metrics["strict_precision"] is not None
        and metrics["strict_precision"] >= minimum_rule_quality
        and metrics["strict_recall"] is not None
        and metrics["strict_recall"] >= minimum_rule_quality
        for metrics in per_rule.values()
    )
    exact_gate = (
        overall["exact_match"] is not None and overall["exact_match"] >= minimum_exact_match
    )
    report = {
        "kind": "FloatingPointScannerValidationResult",
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "corpus_digest": semantic_digest(corpus),
        "oracle_digest": semantic_digest(
            [
                {
                    "case_id": item.get("case_id"),
                    "expected_status": item.get("expected_status"),
                    "finding_keys": item.get("finding_keys", []),
                    "diagnostic_codes": item.get("diagnostic_codes", []),
                    "suppression_ids": item.get("suppression_ids", []),
                }
                for item in cases
                if isinstance(item, Mapping)
            ]
        ),
        "tool_version": TOOL_VERSION,
        "request_schema_version": REQUEST_SCHEMA_VERSION,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "case_results": case_results,
        "per_rule": per_rule,
        "overall": overall,
        "gates": {
            "rule_quality": rule_gate,
            "exact_match": exact_gate,
            "lifecycle_exact": lifecycle_exact,
            "corpus_complete": corpus_complete,
            "passed": rule_gate and exact_gate and lifecycle_exact and corpus_complete,
        },
    }
    report["semantic_digest"] = semantic_digest(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--observed", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    observed_document = json.loads(Path(args.observed).read_text(encoding="utf-8"))
    if not isinstance(corpus, Mapping) or not isinstance(observed_document, Mapping):
        raise ValueError("validation_document_must_be_object")
    observations = observed_document.get("observations")
    if not isinstance(observations, Mapping):
        raise ValueError("validation_observations_missing")
    from .output import write_atomic
    from .protocol import SchemaRegistry

    errors = SchemaRegistry().validate("validation_corpus", corpus)
    if errors:
        raise ValueError(errors[0].diagnostic_code)
    report = evaluate_corpus(
        corpus,
        {str(key): value for key, value in observations.items() if isinstance(value, Mapping)},
    )
    write_atomic(report, Path(args.output))
    return 0 if report["gates"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
