from __future__ import annotations

import copy
from typing import Any

from tests.helpers import RISCV, X86, make_request
from tests.unit.test_build_context_suppression import context_document
from tests.unit.test_rules import _fact, _ir, _profile, _source

from floating_point_precision_scanner.application import Scanner
from floating_point_precision_scanner.build_contexts import build_context
from floating_point_precision_scanner.canonical import semantic_digest
from floating_point_precision_scanner.compilation import normalize_fp_options
from floating_point_precision_scanner.profiles import ProfileRegistry, TargetProfile
from floating_point_precision_scanner.protocol import SchemaRegistry
from floating_point_precision_scanner.rules import RULE_BY_CODE, evaluate_rules


def run(
    code: str,
    facts: list[dict[str, Any]],
    *,
    options: dict[str, Any] | None = None,
    ir: list[dict[str, Any]] | None = None,
    source_context: Any = None,
    target_context: Any = None,
):
    return evaluate_rules(
        (code,),
        _profile(X86),
        _profile(RISCV),
        [_source(facts=facts, options=options)],
        ir or [],
        [],
        {},
        source_context,
        target_context,
    )


def build_contexts(
    source_name: str = "libm-a",
    target_name: str = "libm-b",
    *,
    semantic_difference: bool = True,
):
    source_profile = _profile(X86)
    target_profile = _profile(RISCV)
    source, errors = build_context(
        context_document(source_profile, implementation=source_name),
        profile_fingerprint=source_profile.fingerprint,
        target_triple=source_profile.target_triple,
        abi=source_profile.abi,
    )
    target_document = context_document(target_profile, implementation=target_name)
    if semantic_difference:
        target_document["libm"]["value"]["errno"] = False
    target, target_errors = build_context(
        target_document,
        profile_fingerprint=target_profile.fingerprint,
        target_triple=target_profile.target_triple,
        abi=target_profile.abi,
    )
    assert not errors and not target_errors and source is not None and target is not None
    return source, target


def test_floating_environment_match_restore_and_unknown() -> None:
    change = _fact(1, kind="environment", payload={"fenv_action": "changes_rounding"})
    summary = _fact(
        2,
        kind="function_summary",
        payload={"restores_environment": False, "unknown_effect": False},
    )
    matched = run("floating-environment", [change, summary])
    assert matched.assessments[0].status == "matched"
    assert matched.findings[0]["validation_plan"]["error_metrics"] == [
        "classification",
        "exceptions",
    ]
    restored = _fact(
        2,
        kind="function_summary",
        payload={"restores_environment": True, "unknown_effect": False},
    )
    strict = run(
        "floating-environment",
        [change, restored],
        options=normalize_fp_options(["-frounding-math"]),
    )
    assert strict.assessments[0].reason_code == "environment_restored"
    unknown = _fact(
        2,
        kind="function_summary",
        payload={"restores_environment": False, "unknown_effect": True},
    )
    assert run("floating-environment", [change, unknown]).assessments[0].status == "unknown"


def test_mixed_precision_conversion_boundaries() -> None:
    implicit = _fact(
        1,
        kind="conversion",
        type_name="float",
        payload={
            "implicit": True,
            "source_type": "double",
            "destination_type": "float",
        },
    )
    matched = run("mixed-precision-conversion", [implicit])
    assert matched.assessments[0].status == "matched"
    assert matched.findings[0]["semantic"]["conversions"][0]["source_precision"] == 53
    explicit = dict(implicit)
    explicit["payload"] = {**implicit["payload"], "implicit": False}
    assert run("mixed-precision-conversion", [explicit]).assessments[0].status == "not_matched"
    exact = _fact(
        2,
        kind="conversion",
        type_name="float",
        payload={
            "implicit": True,
            "source_type": "int",
            "destination_type": "float",
            "constant_value": "16777216",
        },
    )
    assert run("mixed-precision-conversion", [exact]).assessments[0].status == "not_matched"
    inexact = dict(exact)
    inexact["payload"] = {**exact["payload"], "constant_value": "16777217"}
    assert run("mixed-precision-conversion", [inexact]).assessments[0].status == "matched"
    missing = dict(implicit)
    missing["payload"] = {"implicit": True, "destination_type": "float"}
    assert run("mixed-precision-conversion", [missing]).assessments[0].status == "unknown"


def test_floating_constant_representability_boundaries() -> None:
    def conversion(value: str) -> dict[str, Any]:
        return _fact(
            1,
            kind="conversion",
            payload={
                "implicit": True,
                "source_type": "double",
                "destination_type": "float",
                "constant_value": value,
            },
        )

    for value in ("1.5", "0x1p+0", "nan"):
        assert run("mixed-precision-conversion", [conversion(value)]).assessments[0].status == (
            "not_matched"
        )
    for value in ("0.1", "1e400", "3.5e38", "not-a-number"):
        assert run("mixed-precision-conversion", [conversion(value)]).assessments[0].status == (
            "matched"
        )

    exact_double = conversion("1.5")
    exact_double["payload"] = {
        **exact_double["payload"],
        "source_type": "long double",
        "destination_type": "double",
    }
    assert run("mixed-precision-conversion", [exact_double]).assessments[0].status == "not_matched"


def test_fragile_comparison_deterministic_and_heuristic() -> None:
    nan = _fact(
        1,
        kind="comparison",
        payload={"opcode": "==", "nan_comparison": True, "use_context": "IfStmt"},
    )
    deterministic = run("fragile-fp-comparison", [nan])
    assert deterministic.findings[0]["evidence_origin"] == "deterministic"
    exact = _fact(
        2,
        kind="comparison",
        payload={
            "opcode": "==",
            "zero_comparison": False,
            "same_origin": False,
            "nan_guard": False,
            "use_context": "IfStmt",
        },
    )
    heuristic = run("fragile-fp-comparison", [exact])
    assert heuristic.findings[0]["evidence_origin"] == "heuristic"
    assert heuristic.findings[0]["confidence"] == "medium"
    assert heuristic.findings[0]["requires_human_confirmation"] is True
    assert heuristic.findings[0]["validation_plan"]["threshold_source"] == "unknown"
    zero = dict(exact)
    zero["payload"] = {**exact["payload"], "zero_comparison": True}
    assert run("fragile-fp-comparison", [zero]).assessments[0].status == "not_matched"


def test_reduction_heuristic_ir_verified_compensated_and_ambiguous() -> None:
    reduction = _fact(
        1,
        kind="reduction",
        payload={"iteration_count": 100, "fixed_order": False, "compensation": None},
    )
    heuristic = run("reduction-reassociation", [reduction])
    assert heuristic.findings[0]["evidence_origin"] == "heuristic"
    ir = _ir(opcode="call", callee="llvm.vector.reduce.fadd.v4f32")
    ir["facts"][0]["reduction_group"] = {
        "kind": "vector-reduction",
        "group_id": "c" * 64,
    }
    verified = run("reduction-reassociation", [reduction], ir=[ir])
    assert verified.findings[0]["evidence_origin"] == "deterministic"
    compensated = dict(reduction)
    compensated["payload"] = {**reduction["payload"], "compensation": "kahan"}
    assert run("reduction-reassociation", [compensated]).assessments[0].status == "not_matched"
    invalidated = run("reduction-reassociation", [compensated], ir=[ir])
    assert invalidated.assessments[0].status == "matched"
    assert invalidated.findings[0]["semantic"]["compensation_invalidated"] is True
    ambiguous = dict(reduction)
    ambiguous["payload"] = {**reduction["payload"], "ambiguous": True}
    assert run("reduction-reassociation", [ambiguous]).assessments[0].status == "unknown"


def test_math_library_requires_context_and_compares_semantics() -> None:
    call = _fact(
        1,
        kind="call",
        payload={"math_family": "sin", "argument_domain": "unknown"},
    )
    assert run("math-library-variance", [call]).assessments[0].status == "unknown"
    source, target = build_contexts()
    matched = run("math-library-variance", [call], source_context=source, target_context=target)
    assert matched.assessments[0].status == "matched"
    assert matched.findings[0]["source_build_context_fingerprint"] == source.fingerprint
    same_source, same_target = build_contexts("same", "same", semantic_difference=False)
    assert (
        run(
            "math-library-variance",
            [call],
            source_context=same_source,
            target_context=same_target,
        )
        .assessments[0]
        .status
        == "not_matched"
    )


def test_architecture_api_resolution_guards_and_unknown() -> None:
    api = _fact(
        1,
        kind="api",
        payload={
            "resolved": True,
            "callee": "_mm_add_ps",
            "required_target_features": ["sse"],
            "active_target_guard": None,
            "portable_target_implementation": False,
        },
    )
    matched = run("architecture-specific-fp-api", [api])
    assert matched.assessments[0].status == "matched"
    guarded = dict(api)
    guarded["payload"] = {
        **api["payload"],
        "active_target_guard": "__x86_64__",
        "portable_target_implementation": True,
    }
    assert run("architecture-specific-fp-api", [guarded]).assessments[0].status == "not_matched"
    unresolved = dict(api)
    unresolved["payload"] = {**api["payload"], "resolved": False}
    assert run("architecture-specific-fp-api", [unresolved]).assessments[0].status == "unknown"
    macro_ambiguous = dict(api)
    macro_ambiguous["payload"] = {**api["payload"], "provenance_ambiguous": True}
    assert run("architecture-specific-fp-api", [macro_ambiguous]).assessments[0].status == (
        "unknown"
    )


def test_expression_rules_cover_empty_candidate_and_profile_edge_paths() -> None:
    for code in (
        "floating-environment",
        "mixed-precision-conversion",
        "fragile-fp-comparison",
        "reduction-reassociation",
        "math-library-variance",
        "architecture-specific-fp-api",
    ):
        assert run(code, []).assessments[0].status == "not_matched"
    assert RULE_BY_CODE["fma-contraction"].requires_build_faithful_ir is True
    assert RULE_BY_CODE["floating-environment"].requires_build_faithful_ir is False

    source = _profile(X86)
    document = dict(source.document)
    document["environment"] = {"status": "unknown"}
    unknown_environment = TargetProfile(
        source.reference,
        source.target_triple,
        source.abi,
        source.compiler_version,
        semantic_digest(document),
        document,
    )
    environment = _fact(1, kind="environment", payload={"fenv_action": "reads_environment"})
    result = evaluate_rules(
        ("floating-environment",),
        unknown_environment,
        _profile(RISCV),
        [_source(facts=[environment])],
        [],
        [],
        {},
    )
    assert result.assessments[0].reason_code == "profile_field_unknown"
    compatible = run("floating-environment", [environment])
    assert compatible.assessments[0].reason_code == "environment_semantics_compatible"


def test_mixed_precision_unknown_integer_and_long_double_boundaries() -> None:
    unknown_target = _fact(
        1,
        kind="conversion",
        payload={"implicit": True, "source_type": "double", "destination_type": "decimal"},
    )
    assert run("mixed-precision-conversion", [unknown_target]).assessments[0].status == "unknown"
    unknown_source = _fact(
        2,
        kind="conversion",
        payload={"implicit": True, "source_type": "size_type", "destination_type": "float"},
    )
    assert run("mixed-precision-conversion", [unknown_source]).assessments[0].status == "unknown"
    fractional = _fact(
        3,
        kind="conversion",
        payload={
            "implicit": True,
            "source_type": "int",
            "destination_type": "float",
            "constant_value": "1.5",
        },
    )
    invalid = _fact(
        4,
        kind="conversion",
        payload={
            "implicit": True,
            "source_type": "int",
            "destination_type": "float",
            "constant_value": "not-a-number",
        },
    )
    zero = _fact(
        5,
        kind="conversion",
        payload={
            "implicit": True,
            "source_type": "int",
            "destination_type": "float",
            "constant_value": "0",
            "integer_width": 16,
        },
    )
    long_double = _fact(
        6,
        kind="conversion",
        payload={
            "implicit": True,
            "source_type": "const long double",
            "destination_type": "float",
        },
    )
    result = run("mixed-precision-conversion", [fractional, invalid, zero, long_double])
    assert result.counts["matched"] == 3
    assert result.counts["not_matched"] == 1
    assert len(result.findings) == 3
    assert all(len(item["semantic"]["conversions"]) == 1 for item in result.findings)


def test_mixed_precision_preserves_matched_and_unknown_candidates_in_same_tu() -> None:
    matched = _fact(
        10,
        kind="conversion",
        payload={
            "implicit": True,
            "source_type": "double",
            "destination_type": "float",
            "endpoint_status": "known",
        },
    )
    unknown = _fact(
        11,
        kind="conversion",
        payload={
            "implicit": True,
            "source_type": None,
            "destination_type": "float",
            "endpoint_status": "unknown",
        },
    )

    result = run("mixed-precision-conversion", [matched, unknown])

    assert result.counts["matched"] == 1
    assert result.counts["unknown"] == 1
    assert len(result.findings) == 1
    assert result.findings[0]["evidence"] == [
        {"kind": "source_fact", "ref": matched["fact_id"]}
    ]


def test_expression_rule_unknown_use_and_non_riscv_target() -> None:
    comparison = _fact(
        1,
        kind="comparison",
        payload={"opcode": "==", "zero_comparison": False, "use_context": None},
    )
    assert run("fragile-fp-comparison", [comparison]).assessments[0].reason_code == (
        "comparison_use_unknown"
    )
    api = _fact(
        2,
        kind="api",
        payload={"resolved": True, "callee": "_mm_add_ps", "required_target_features": ["sse"]},
    )
    result = evaluate_rules(
        ("architecture-specific-fp-api",),
        _profile(X86),
        _profile(X86),
        [_source(facts=[api])],
        [],
        [],
        {},
    )
    assert result.assessments[0].reason_code == "target_supports_source_api"


def test_matched_finding_without_valid_location_is_still_stable() -> None:
    fact = _fact(1)
    fact["location"] = {"expansion": "invalid"}
    result = run(
        "unsafe-fp-optimization",
        [fact],
        options=normalize_fp_options(["-ffast-math"]),
    )
    assert result.findings[0]["location"] == {"expansion": "invalid"}
    empty = run(
        "unsafe-fp-optimization",
        [],
        options=normalize_fp_options(["-ffast-math"]),
    )
    assert empty.findings[0]["location"] is None


class _ExpressionFrontend:
    def verify(self) -> None:
        return None

    def ast(self, context: Any) -> dict[str, Any]:
        path = str(context.absolute_file)
        return {
            "kind": "TranslationUnitDecl",
            "inner": [
                {
                    "kind": "ImplicitCastExpr",
                    "castKind": "FloatingCast",
                    "type": {"qualType": "float"},
                    "loc": {"file": path, "line": 1, "col": 1},
                    "inner": [{"kind": "DeclRefExpr", "type": {"qualType": "double"}}],
                },
                {
                    "kind": "IfStmt",
                    "inner": [
                        {
                            "kind": "BinaryOperator",
                            "opcode": "==",
                            "type": {"qualType": "bool"},
                            "loc": {"file": path, "line": 2, "col": 1},
                            "inner": [
                                {"kind": "DeclRefExpr", "type": {"qualType": "double"}},
                                {
                                    "kind": "FloatingLiteral",
                                    "value": "1.0",
                                    "type": {"qualType": "double"},
                                },
                            ],
                        }
                    ],
                },
                {
                    "kind": "CompoundAssignOperator",
                    "opcode": "+=",
                    "type": {"qualType": "double"},
                    "iterationCount": 100,
                    "loc": {"file": path, "line": 3, "col": 1},
                },
                {
                    "kind": "CallExpr",
                    "type": {"qualType": "double"},
                    "argumentDomain": "boundary",
                    "loc": {"file": path, "line": 4, "col": 1},
                    "inner": [
                        {
                            "kind": "DeclRefExpr",
                            "referencedDecl": {"name": "sin", "id": "sin-decl"},
                        }
                    ],
                },
                {
                    "kind": "CallExpr",
                    "type": {"qualType": "__m128"},
                    "intrinsicFamily": "x86-sse",
                    "requiredTargetFeatures": ["sse"],
                    "loc": {"file": path, "line": 5, "col": 1},
                    "inner": [
                        {
                            "kind": "DeclRefExpr",
                            "referencedDecl": {
                                "name": "_mm_add_ps",
                                "id": "x86-decl",
                                "builtinId": 42,
                                "header": "immintrin.h",
                            },
                        }
                    ],
                },
            ],
        }


def test_schema_13_application_runs_ten_rules_and_audits_suppression(tmp_path) -> None:
    profiles = ProfileRegistry()
    request = make_request(tmp_path)
    request["schema_version"] = "1.3"
    request.pop("rules")
    request["build_contexts"] = {
        "source": context_document(profiles.get(X86), implementation="libm-a"),
        "target": context_document(profiles.get(RISCV), implementation="libm-b"),
    }
    request["build_contexts"]["target"]["libm"]["value"]["errno"] = False
    request["suppressions"] = [
        {
            "code": "mixed-precision-conversion",
            "path": "main.c",
            "reason": "project range proof",
            "start_line": 1,
            "end_line": 1,
        }
    ]
    result = Scanner(_ExpressionFrontend(), profiles=profiles).scan(request)  # type: ignore[arg-type]
    assert result["scan"]["status"] == "complete"
    analysis = result["extensions"]["org.rvport.floating-point-scanner.analysis"]
    assert analysis["analysisScope"] == "migrationRisks"
    assert len(analysis["enabledRules"]) == 10
    assert result["summary"]["suppressed"] == 1
    suppressions = result["extensions"]["org.rvport.floating-point-scanner.suppressions"]
    assert len(suppressions["records"]) == 1
    assert {item["conclusion"]["findingCode"] for item in result["findings"]} == {
        "fragile-fp-comparison",
        "reduction-reassociation",
        "math-library-variance",
        "architecture-specific-fp-api",
    }
    assert SchemaRegistry().validate("result", result) == []

    limited_request = copy.deepcopy(request)
    limited_request["budgets"] = {"max_suppression_records": 1}
    limited_request["suppressions"].append(
        {
            "code": "fragile-fp-comparison",
            "path": "main.c",
            "reason": "reviewed comparison",
            "start_line": 2,
            "end_line": 2,
        }
    )
    limited = Scanner(_ExpressionFrontend(), profiles=profiles).scan(limited_request)  # type: ignore[arg-type]
    assert limited["summary"]["suppressed"] == 1
    assert "mixed-precision-conversion" in {
        item["conclusion"]["findingCode"] for item in limited["findings"]
    }
    assert any(
        item["code"] == "suppression_budget_exceeded" for item in limited["diagnostics"]
    )
