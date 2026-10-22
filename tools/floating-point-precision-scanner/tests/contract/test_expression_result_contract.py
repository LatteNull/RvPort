from __future__ import annotations

import pytest

from floating_point_precision_scanner.protocol import SchemaRegistry
from floating_point_precision_scanner.result_v2 import (
    EXTENSION_SUPPRESSIONS,
    project_result_v2,
)
from floating_point_precision_scanner.rules import EvidenceRef, RuleAssessment, RuleRun


def valid_expression_result() -> dict[str, object]:
    assessment_id = "a" * 64
    assessment = RuleAssessment(
        assessment_id,
        "fragile-fp-comparison",
        "1.0",
        "main.c",
        "matched",
        "rounding_sensitive_comparison",
        (EvidenceRef("source_fact", "b" * 64),),
    )
    finding = {
            "finding_id": "c" * 64,
            "finding_code": "fragile-fp-comparison",
            "rule_version": "1.0",
            "assessment_id": assessment_id,
            "category": "comparison-semantics",
            "severity": "medium",
            "confidence": "medium",
            "evidence_origin": "heuristic",
            "requires_human_confirmation": True,
            "location": {"path": "main.c", "line": 2, "column": 1},
            "related_locations": [],
            "affected_count": 1,
            "evidence": [{"kind": "source_fact", "ref": "b" * 64}],
            "source_profile_fingerprint": "d" * 64,
            "target_profile_fingerprint": "e" * 64,
            "source_build_context_fingerprint": None,
            "target_build_context_fingerprint": None,
            "aggregation_key": None,
            "title": "浮点比较需要人工确认",
            "title_en": "Floating-point comparison requires review",
            "message": "精确比较可能依赖舍入结果。",
            "message_en": "Exact comparison may depend on rounding.",
            "impact": "控制流可能变化。",
            "impact_en": "Control flow may change.",
            "suggestion": "使用项目批准的容差策略。",
            "suggestion_en": "Use a project-approved tolerance policy.",
            "test_suggestion": "测试边界、NaN 和 Inf。",
            "test_suggestion_en": "Test boundaries, NaN, and Inf.",
            "validation_plan": {
                "input_classes": ["rounding-boundary"],
                "error_metrics": ["ulp", "classification"],
                "threshold_source": "unknown",
                "repeat_strategy": "source/target across optimization modes",
            },
            "semantic": {"rationale": "rounding_sensitive_comparison"},
    }
    return project_result_v2(
        "fixture",
        "complete",
        1,
        1,
        0,
        0,
        [],
        [],
        {"fingerprint": "d" * 64},
        {"fingerprint": "e" * 64},
        rule_run=RuleRun((assessment,), (finding,), ()),
        enabled_rules=("fragile-fp-comparison",),
    )


def test_expression_result_fixture_is_valid() -> None:
    assert SchemaRegistry().validate("result", valid_expression_result()) == []


@pytest.mark.parametrize(
    "field",
    [
        "evidenceOrigin",
        "requiresHumanConfirmation",
        "titleEn",
        "messageEn",
        "suggestionEn",
        "testSuggestionEn",
        "validationPlan",
        "sourceBuildContextFingerprint",
    ],
)
def test_result_rejects_missing_required_finding_fields(field: str) -> None:
    document = valid_expression_result()
    del document["findings"][0]["conclusion"][field]  # type: ignore[index]
    assert SchemaRegistry().validate("result", document)[0].diagnostic_code == (
        "schema_validation_error"
    )


def test_result_rejects_confirmation_context_and_denominator_invariants() -> None:
    registry = SchemaRegistry()
    document = valid_expression_result()
    document["findings"][0]["conclusion"]["requiresHumanConfirmation"] = False  # type: ignore[index]
    assert registry.validate("result", document)[0].diagnostic_code == (
        "confirmation-policy-violation"
    )

    document = valid_expression_result()
    document["summary"]["findings"] = 0  # type: ignore[index]
    assert registry.validate("result", document)[0].diagnostic_code == "count-mismatch"


def test_result_rejects_suppression_without_bilingual_reason() -> None:
    document = valid_expression_result()
    suppressions = document["extensions"][EXTENSION_SUPPRESSIONS]  # type: ignore[index]
    suppressions["records"] = [
        {
            "id": "1" * 64,
            "findingId": "c" * 64,
            "findingCode": "fragile-fp-comparison",
            "path": "main.c",
            "startLine": 2,
            "endLine": 2,
            "reason": "reviewed",
            "source": "request",
            "status": "applied",
            "expiresOn": None,
        }
    ]
    document["summary"]["suppressed"] = 1  # type: ignore[index]
    assert SchemaRegistry().validate("result", document)[0].diagnostic_code == (
        "schema_validation_error"
    )
