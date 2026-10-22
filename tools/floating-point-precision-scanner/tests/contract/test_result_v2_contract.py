from __future__ import annotations

import copy
from typing import Any

import pytest
from tests.contract.test_expression_result_contract import valid_expression_result

from floating_point_precision_scanner.canonical import stable_id
from floating_point_precision_scanner.diagnostics import diagnostic
from floating_point_precision_scanner.output import serialize_json
from floating_point_precision_scanner.protocol import SchemaRegistry
from floating_point_precision_scanner.result_v2 import (
    EXTENSION_ANALYSIS,
    EXTENSION_SUPPRESSIONS,
    _camelize,
    _catalog,
    _finding,
    _occurrences,
    _safe_location,
    _typed_reference,
    failure_result_v2,
    project_result_v2,
    refresh_semantic_digest,
    truncate_result_v2,
    validate_result_invariants,
)
from floating_point_precision_scanner.rules import (
    RULE_BY_CODE,
    EvidenceRef,
    RuleAssessment,
    RuleRun,
)
from floating_point_precision_scanner.step_descriptions import StepDescriptions


def test_descriptions_do_not_change_finding_or_graph_identity():
    finding = _ten_rule_run().findings[0]
    old = _finding(finding)
    identity = finding["evidence"][0]["ref"]
    descriptions = StepDescriptions(
        facts=[{"facts": [{"fact_id": identity, "fact_kind": "reduction"}]}]
    )
    new = _finding(finding, descriptions)
    assert new["id"] == old["id"]
    assert new["occurrences"] == old["occurrences"]
    assert new["conclusion"]["severity"] == old["conclusion"]["severity"]
    assert new["evidenceChain"]["edges"] == old["evidenceChain"]["edges"]
    assert new["evidenceChain"]["primaryPath"] == old["evidenceChain"]["primaryPath"]
    assert [s["id"] for s in new["evidenceChain"]["steps"]] == [
        s["id"] for s in old["evidenceChain"]["steps"]
    ]
    assert new["evidenceChain"]["steps"] != old["evidenceChain"]["steps"]


def _ten_rule_run() -> RuleRun:
    assessments: list[RuleAssessment] = []
    findings: list[dict[str, Any]] = []
    for index, descriptor in enumerate(RULE_BY_CODE.values(), start=1):
        assessment_id = f"{index + 100:064x}"
        source_id = f"{index + 200:064x}"
        evidence = [EvidenceRef("source_fact", source_id)]
        if index > 1:
            evidence.extend(
                (
                    EvidenceRef("binding", f"{index + 300:064x}"),
                    EvidenceRef("ir_fact", f"{index + 400:064x}"),
                )
            )
        assessments.append(
            RuleAssessment(
                assessment_id,
                descriptor.code,
                descriptor.version,
                "main.c",
                "matched",
                "fixture-match",
                tuple(evidence),
            )
        )
        heuristic = descriptor.evidence_mode == "heuristic-capable"
        findings.append(
            {
                "finding_id": f"{index:064x}",
                "finding_code": descriptor.code,
                "rule_version": descriptor.version,
                "assessment_id": assessment_id,
                "category": descriptor.category,
                "severity": "medium",
                "confidence": "medium" if heuristic else "high",
                "evidence_origin": "heuristic" if heuristic else "deterministic",
                "requires_human_confirmation": True,
                "location": {"path": "main.c", "line": index, "column": 1},
                "related_locations": [],
                "affected_count": 1,
                "evidence": [item.to_dict() for item in evidence],
                "source_profile_fingerprint": "d" * 64,
                "target_profile_fingerprint": "e" * 64,
                "source_build_context_fingerprint": None,
                "target_build_context_fingerprint": None,
                "aggregation_key": None,
                "title": f"{descriptor.code} 风险",
                "title_en": f"{descriptor.code} risk",
                "message": "检测到可审计的浮点迁移风险。",
                "message_en": "An auditable floating-point migration risk was detected.",
                "impact": "目标架构上的数值行为可能变化。",
                "impact_en": "Numeric behavior may change on the target architecture.",
                "suggestion": "请审查证据并执行迁移验证。",
                "suggestion_en": "Review the evidence and run migration validation.",
                "test_suggestion": "覆盖边界值、NaN、Inf 和舍入边界。",
                "test_suggestion_en": "Cover boundaries, NaN, Inf, and rounding edges.",
                "validation_plan": {
                    "input_classes": ["rounding-boundary"],
                    "error_metrics": ["ulp"],
                    "threshold_source": "unknown",
                    "repeat_strategy": "compare source and target profiles",
                },
                "semantic": {"validation_key": f"fixture:{descriptor.code}"},
            }
        )
    return RuleRun(tuple(assessments), tuple(findings), ())


def test_location_budget_is_visible_in_projected_conclusion() -> None:
    finding = copy.deepcopy(_ten_rule_run().findings[0])
    assert _finding(finding)["conclusion"]["status"] == "complete"
    finding["semantic"].update(location_budget_exceeded=True, total_locations=12)
    projected = _finding(finding)
    assert projected["conclusion"]["status"] == "partial"
    assert projected["conclusion"]["semantic"]["totalLocations"] == 12
    step = next(s for s in projected["evidenceChain"]["steps"] if s["kind"] == "conclusion")
    assert step["status"] == "partial"
    assert "位置输出达到预算" in step["reason"]
    assert {"reasonCode": "location_budget_exceeded"} in projected["evidenceChain"]["breaks"]
    assert projected["fact"]["primaryLocation"] == {"file": "main.c", "line": 1, "column": 1}


def test_minimal_terminal_results_and_projector_boundaries() -> None:
    registry = SchemaRegistry()
    for status in ("complete", "partial", "invalid_request", "failed", "internal_error"):
        result = failure_result_v2(
            f"terminal-{status}",
            status,
            [] if status == "complete" else [diagnostic(status, "test", "诊断", "Diagnostic")],
        )
        assert result["scan"]["status"] == status
        assert registry.validate("result", result) == []

    result = project_result_v2(
        "boundary",
        "partial",
        0,
        0,
        0,
        0,
        [],
        [diagnostic(str(index), "test", "诊断", "Diagnostic") for index in range(3)],
        {},
        {},
        diagnostic_limit=2,
    )
    assert result["diagnostics"][-1]["code"] == "diagnostic_budget_exceeded"
    before = result["scan"]["semanticDigest"]
    result["project"]["reasonCodes"].append("changed")
    refresh_semantic_digest(result)
    assert result["scan"]["semanticDigest"] != before


def test_named_minimal_contract_fixtures_are_independently_valid() -> None:
    normal = valid_expression_result()
    aggregate = copy.deepcopy(normal)
    occurrence = copy.deepcopy(aggregate["findings"][0]["occurrences"][0])
    occurrence["id"] = stable_id("fixture-occurrence", {"index": 2})
    occurrence["kind"] = "related"
    occurrence["location"] = {"file": "other.c", "line": 8, "column": 3}
    aggregate["findings"][0]["occurrences"].append(occurrence)
    aggregate["findings"][0]["conclusion"]["affectedCount"] = 2
    aggregate["findings"][0]["conclusion"]["aggregationKey"] = "comparison-group"
    refresh_semantic_digest(aggregate)

    suppressed = failure_result_v2("suppressed", "complete", [])
    suppressed["extensions"][EXTENSION_SUPPRESSIONS]["policyAsOf"] = "2026-09-28"
    suppressed["extensions"][EXTENSION_SUPPRESSIONS]["records"] = [
        {
            "id": "suppression-1",
            "findingId": None,
            "findingCode": "fragile-fp-comparison",
            "path": "main.c",
            "startLine": 1,
            "endLine": 1,
            "reason": "已由项目策略审查。",
            "reasonEn": "Reviewed by project policy.",
            "source": "request",
            "status": "applied",
            "expiresOn": None,
        }
    ]
    suppressed["summary"]["suppressed"] = 1
    refresh_semantic_digest(suppressed)

    fixtures = {
        "normal": normal,
        "facts-only": failure_result_v2("facts-only", "complete", []),
        "aggregate": aggregate,
        "heuristic": copy.deepcopy(normal),
        "suppressed": suppressed,
        "partial": failure_result_v2(
            "partial", "partial", [diagnostic("partial", "fixture", "部分", "Partial")]
        ),
        "invalid-request": failure_result_v2(
            "invalid", "invalid_request", [diagnostic("invalid", "fixture", "无效", "Invalid")]
        ),
        "failed": failure_result_v2(
            "failed", "failed", [diagnostic("failed", "fixture", "失败", "Failed")]
        ),
        "internal-error": failure_result_v2(
            "internal",
            "internal_error",
            [diagnostic("internal", "fixture", "内部错误", "Internal error")],
        ),
    }
    registry = SchemaRegistry()
    assert set(fixtures) == {
        "normal",
        "facts-only",
        "aggregate",
        "heuristic",
        "suppressed",
        "partial",
        "invalid-request",
        "failed",
        "internal-error",
    }
    for document in fixtures.values():
        assert registry.validate("result", document) == []


def test_all_ten_rules_use_one_stable_v2_projection() -> None:
    run = _ten_rule_run()
    codes = tuple(RULE_BY_CODE)
    result = project_result_v2(
        "ten-rules",
        "complete",
        1,
        1,
        0,
        0,
        [],
        [],
        {"fingerprint": "d" * 64},
        {"fingerprint": "e" * 64},
        rule_run=run,
        enabled_rules=codes,
        request_schema_version="1.4",
    )
    assert SchemaRegistry().validate("result", result) == []
    assert {item["conclusion"]["findingCode"] for item in result["findings"]} == set(codes)
    for finding in result["findings"]:
        conclusion = finding["conclusion"]
        assert conclusion["validationPlan"]["thresholdSource"] == "unknown"
        assert conclusion["requiresHumanConfirmation"] is True
        reference_kinds = {
            reference["kind"]
            for step in finding["evidenceChain"]["steps"]
            for reference in step["references"]
        }
        assert "sourceFact" in reference_kinds
        if conclusion["findingCode"] != codes[0]:
            assert {"binding", "irFact"} <= reference_kinds

    reversed_result = project_result_v2(
        "ten-rules",
        "complete",
        1,
        1,
        0,
        0,
        [],
        [],
        {"fingerprint": "d" * 64},
        {"fingerprint": "e" * 64},
        rule_run=RuleRun(tuple(reversed(run.assessments)), tuple(reversed(run.findings)), ()),
        enabled_rules=tuple(reversed(codes)),
        request_schema_version="1.4",
    )
    assert reversed_result["findings"] == result["findings"]
    assert (
        reversed_result["extensions"][EXTENSION_ANALYSIS]
        == result["extensions"][EXTENSION_ANALYSIS]
    )
    assert reversed_result["scan"]["semanticDigest"] == result["scan"]["semanticDigest"]


def test_project_translation_unit_denominator_makes_partial_source_unknown_exclusive() -> None:
    result = project_result_v2(
        "partial-source",
        "partial",
        1,
        1,
        0,
        1,
        [],
        [],
        {},
        {},
        layers={
            "source": {"planned": 1, "completed": 1, "failed": 0, "unknown": 1},
        },
    )
    assert result["project"]["filesAnalyzed"] == 1
    assert result["project"]["translationUnits"] == {
        "planned": 1,
        "completed": 0,
        "failed": 0,
        "unknown": 1,
    }
    assert result["summary"]["layers"]["source"] == {
        "planned": 1,
        "completed": 1,
        "failed": 0,
        "unknown": 1,
    }
    assert SchemaRegistry().validate("result", result) == []


def test_projection_sanitizes_locations_and_camelizes_audit_values() -> None:
    assert _safe_location(None) is None
    assert _safe_location({}) is None
    assert _safe_location({"path": "C:/secret/main.c", "line": 0, "column": 0}) == {
        "file": "<external_path>",
        "line": 1,
        "column": 1,
    }
    macro = _safe_location(
        {
            "spelling": {"path": "include/value.h", "line": 3, "column": 4},
            "expansion": {"path": "src/main.c", "line": 8, "column": 2},
        }
    )
    assert macro == {"file": "src/main.c", "line": 8, "column": 2, "origin": "macroExpansion"}
    assert _camelize({"logical_used": {"source_fact": 1}, "items": (1, 2)}) == {
        "logicalUsed": {"sourceFact": 1},
        "items": [1, 2],
    }
    reference = _typed_reference({"kind": "unknown_kind", "ref": "short"})
    assert reference["kind"] == "unknown_kind"
    assert reference["producer"] == "floating-point-precision-scanner"
    assert len(reference["digest"]) == 64
    occurrences = _occurrences(
        {
            "finding_id": "f" * 64,
            "location": {"path": "main.c", "line": 1, "column": 1},
            "related_locations": [
                {"path": "main.c", "line": 1, "column": 1},
                {"path": "other.c", "line": 2, "column": 3},
            ],
            "evidence": [],
        }
    )
    assert len(occurrences) == 2
    catalog = _catalog([], [{"id": "assessment", "evidence": ["ignored"]}])
    assert catalog[0]["id"] == "assessment"


def test_contract_validator_rejects_reference_and_identity_errors() -> None:
    base = valid_expression_result()
    finding = base["findings"][0]
    chain = finding["evidenceChain"]
    occurrence = finding["occurrences"][0]

    cases: list[tuple[dict[str, object], str]] = []

    value = copy.deepcopy(base)
    value["extensions"]["unknown.namespace"] = {}
    cases.append((value, "unregistered-extension"))

    value = copy.deepcopy(base)
    value["findings"].append(copy.deepcopy(value["findings"][0]))
    value["summary"]["findings"] = 2
    cases.append((value, "duplicate-id"))

    value = copy.deepcopy(base)
    value["findings"][0]["occurrences"].append(copy.deepcopy(occurrence))
    cases.append((value, "duplicate-id"))

    value = copy.deepcopy(base)
    value["findings"][0]["primaryOccurrenceId"] = "0" * 64
    cases.append((value, "dangling-primary-occurrence"))

    value = copy.deepcopy(base)
    value["findings"][0]["evidenceChain"]["rootStepId"] = "0" * 64
    cases.append((value, "dangling-step-reference"))

    value = copy.deepcopy(base)
    value["findings"][0]["evidenceChain"]["primaryPath"] = []
    cases.append((value, "invalid-primary-path"))

    value = copy.deepcopy(base)
    value["findings"][0]["evidenceChain"]["primaryPath"] = [
        chain["primaryPath"][0],
        chain["primaryPath"][0],
    ]
    cases.append((value, "invalid-primary-path"))

    value = copy.deepcopy(base)
    value["findings"][0]["evidenceChain"]["impactStepIds"] = ["0" * 64]
    cases.append((value, "dangling-impact-reference"))

    value = copy.deepcopy(base)
    value["findings"][0]["evidenceChain"]["edges"][0]["toStepId"] = "0" * 64
    cases.append((value, "dangling-edge-reference"))

    value = copy.deepcopy(base)
    value["findings"][0]["evidenceChain"]["edges"].append(
        copy.deepcopy(value["findings"][0]["evidenceChain"]["edges"][0])
    )
    cases.append((value, "duplicate-id"))

    value = copy.deepcopy(base)
    value["findings"][0]["evidenceChain"]["breaks"] = [{"reasonCode": "missing-ir"}]
    value["findings"][0]["evidenceChain"]["status"] = "complete"
    cases.append((value, "complete-chain-has-break"))

    value = copy.deepcopy(base)
    value["findings"][0]["evidenceChain"]["status"] = "partial"
    value["findings"][0]["evidenceChain"]["breaks"] = []
    cases.append((value, "incomplete-chain-missing-break"))

    value = copy.deepcopy(base)
    reference_step = next(
        step for step in value["findings"][0]["evidenceChain"]["steps"] if step["references"]
    )
    reference_step["references"][0]["id"] = "missing"
    cases.append((value, "dangling-external-reference"))

    value = copy.deepcopy(base)
    value["findings"][0]["fact"]["provenance"][0]["id"] = "missing"
    cases.append((value, "dangling-external-reference"))

    value = copy.deepcopy(base)
    value["findings"][0]["occurrences"][0]["location"]["file"] = "../secret.c"
    cases.append((value, "unsafe-path"))

    for document, expected in cases:
        assert expected in validate_result_invariants(document)


def test_contract_validator_rejects_diagnostic_counts_and_bilingual_errors() -> None:
    base = valid_expression_result()

    value = copy.deepcopy(base)
    value["findings"][0]["conclusion"]["messageEn"] = ""
    assert "missing-bilingual-field" in validate_result_invariants(value)

    value = copy.deepcopy(base)
    value["diagnostics"] = [
        {
            "id": "9" * 64,
            "code": "linked",
            "stage": "test",
            "severity": "error",
            "message": "诊断",
            "messageEn": "Diagnostic",
            "suggestion": "建议",
            "suggestionEn": "Suggestion",
            "retryable": False,
            "count": 1,
            "location": None,
            "translationUnitId": None,
            "findingIds": ["0" * 64],
        }
    ]
    value["summary"]["diagnostics"] = 1
    assert "dangling-diagnostic-reference" in validate_result_invariants(value)

    value["diagnostics"][0]["suggestionEn"] = ""
    assert "missing-bilingual-field" in validate_result_invariants(value)

    value = copy.deepcopy(base)
    value["summary"]["assessments"]["matched"] = 0
    assert "count-mismatch" in validate_result_invariants(value)

    value = copy.deepcopy(base)
    value["project"]["translationUnits"] = {
        "planned": 1,
        "completed": 1,
        "failed": 1,
        "unknown": 0,
    }
    assert "count-mismatch" in validate_result_invariants(value)

    value = copy.deepcopy(base)
    value["extensions"][EXTENSION_SUPPRESSIONS]["records"] = [
        {
            "id": "suppression",
            "findingId": None,
            "findingCode": "fragile-fp-comparison",
            "path": "main.c",
            "startLine": None,
            "endLine": None,
            "reason": "原因",
            "reasonEn": "Reason",
            "source": "request",
            "status": "applied",
            "expiresOn": None,
        }
    ]
    assert "count-mismatch" in validate_result_invariants(value)


def test_schema_rejects_legacy_and_unknown_extension_payloads() -> None:
    registry = SchemaRegistry()
    legacy = {"schema_version": "1.4", "status": "complete"}
    assert registry.validate("result", legacy)[0].diagnostic_code == ("unsupported-result-version")

    value = valid_expression_result()
    value["extensions"][EXTENSION_ANALYSIS]["unexpected"] = True
    assert registry.validate("result", value)[0].diagnostic_code == "schema_validation_error"


@pytest.mark.parametrize(
    "field,limit", [("title", 512), ("titleEn", 512), ("reason", 4096), ("reasonEn", 4096)]
)
def test_evidence_descriptions_require_nonblank_bounded_strings(field, limit):
    value = valid_expression_result()
    step = value["findings"][0]["evidenceChain"]["steps"][0]
    for invalid in [None, "", "  ", "中" * (limit + 1)]:
        step[field] = invalid
        assert SchemaRegistry().validate("result", value)
    step[field] = "中" * limit
    assert SchemaRegistry().validate("result", value) == []
    del step[field]
    assert SchemaRegistry().validate("result", value)


@pytest.mark.parametrize(
    "extension",
    [
        "org.rvport.floating-point-scanner.analysis",
        "org.rvport.floating-point-scanner.profiles",
        "org.rvport.floating-point-scanner.artifacts",
        "org.rvport.floating-point-scanner.suppressions",
        "org.rvport.floating-point-scanner.runtime",
    ],
)
def test_registered_extensions_require_their_version(extension: str) -> None:
    value = valid_expression_result()
    del value["extensions"][extension]["schemaVersion"]
    assert SchemaRegistry().validate("result", value)[0].diagnostic_code == (
        "schema_validation_error"
    )


def test_extension_collection_size_boundary_is_enforced() -> None:
    value = valid_expression_result()
    analysis = value["extensions"][EXTENSION_ANALYSIS]
    analysis["enabledRules"] = [f"rule-{index}" for index in range(65)]
    assert SchemaRegistry().validate("result", value)[0].diagnostic_code == (
        "schema_validation_error"
    )


def test_semantic_digest_ignores_display_text_cache_heat_and_suppression_reason() -> None:
    value = valid_expression_result()
    value["extensions"][EXTENSION_SUPPRESSIONS]["records"] = [
        {
            "id": "suppression",
            "findingId": None,
            "findingCode": "fragile-fp-comparison",
            "path": "main.c",
            "startLine": None,
            "endLine": None,
            "reason": "初始原因",
            "reasonEn": "Initial reason",
            "source": "request",
            "status": "unmatched",
            "expiresOn": None,
        }
    ]
    refresh_semantic_digest(value)
    original = value["scan"]["semanticDigest"]
    conclusion = value["findings"][0]["conclusion"]
    conclusion["title"] = "更新后的标题"
    conclusion["titleEn"] = "Updated title"
    runtime = value["extensions"]["org.rvport.floating-point-scanner.runtime"]
    runtime["cache"]["hit"] = 99
    record = value["extensions"][EXTENSION_SUPPRESSIONS]["records"][0]
    record["reason"] = "更新原因"
    record["reasonEn"] = "Updated reason"
    refresh_semantic_digest(value)
    assert value["scan"]["semanticDigest"] == original


def test_result_size_budget_truncates_only_complete_findings() -> None:
    value = valid_expression_result()
    unchanged = truncate_result_v2(value, len(serialize_json(value)) + 1)
    assert unchanged == value
    assert truncate_result_v2(value, 1) is None

    truncated = truncate_result_v2(value, len(serialize_json(value)) - 1)
    assert truncated is not None
    assert truncated["scan"]["status"] == "partial"
    assert truncated["findings"] == []
    assert truncated["summary"]["findings"] == 0
    assert truncated["diagnostics"][0]["code"] == "result_budget_truncated"
    assert SchemaRegistry().validate("result", truncated) == []


@pytest.mark.parametrize("value", [{"findings": {}}, {"diagnostics": {}}, {"extensions": []}])
def test_invariant_validator_leaves_shape_errors_to_json_schema(value: dict[str, object]) -> None:
    document = failure_result_v2("shape", "complete", [])
    document.update(value)
    assert validate_result_invariants(document) == []


def test_invariant_validator_tolerates_malformed_children_until_schema_validation() -> None:
    base = valid_expression_result()
    base["findings"].append("ignored")
    base["diagnostics"].append("ignored")
    base["extensions"][EXTENSION_ANALYSIS]["objects"].append("ignored")
    base["summary"]["findings"] = 2
    base["summary"]["diagnostics"] = 1
    assert validate_result_invariants(base) == []

    value = valid_expression_result()
    value["extensions"][EXTENSION_ANALYSIS] = []
    value["extensions"][EXTENSION_SUPPRESSIONS] = []
    value["summary"] = []
    value["project"] = []
    assert validate_result_invariants(value) == ["dangling-external-reference"]

    value = valid_expression_result()
    value["project"]["translationUnits"] = []
    value["findings"][0]["conclusion"] = []
    value["findings"][0]["occurrences"].append("ignored")
    value["findings"][0]["evidenceChain"]["steps"].append("ignored")
    assert "duplicate-id" in validate_result_invariants(value)
