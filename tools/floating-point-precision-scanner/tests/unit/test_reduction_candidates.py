from __future__ import annotations

import copy
from typing import Any

import pytest
from tests.helpers import RISCV, X86
from tests.unit.test_rules import _fact, _ir, _profile, _source

from floating_point_precision_scanner.canonical import semantic_digest
from floating_point_precision_scanner.profiles import TargetProfile
from floating_point_precision_scanner.reduction_candidates import (
    candidates,
    position_matches_source,
)
from floating_point_precision_scanner.rules import evaluate_rules
from floating_point_precision_scanner.suppression import Suppression, apply_suppressions

RULE = "reduction-reassociation"


def reduction(index: int, *, loop: int = 1, accumulator: int = 1, **payload: Any) -> dict[str, Any]:
    return _fact(
        index,
        kind="reduction",
        payload={
            "loop_id": f"{loop:064x}",
            "accumulator_id": f"{accumulator:064x}",
            "iteration_count": 100,
            "fixed_order": False,
            "compensation": None,
            **payload,
        },
    )


def linked(
    fact: dict[str, Any], *, profile: str = "build-faithful"
) -> tuple[dict[str, Any], dict[str, Any]]:
    ir = _ir(profile=profile, opcode="fadd", callee=None, flags=["reassoc"])
    ir["facts"][0].update(function=fact["function_symbol"], debug_location=fact["location"])
    evidence = {
        "artifact": ir["artifact"],
        "bindings": [
            {
                "binding_id": "b" * 64,
                "source_fact_id": fact["fact_id"],
                "ir_fact_id": ir["facts"][0]["fact_id"],
                "method": "derived-debug",
                "confidence": "strong",
                "relation": "reduction-lowering",
            }
        ],
        "ambiguities": [],
    }
    return ir, evidence


def evaluate(
    facts: list[dict[str, Any]],
    *,
    ir: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    policies: bool = False,
    budgets: dict[str, int] | None = None,
):
    profiles = [_profile(X86), _profile(RISCV)]
    if policies:
        for index, base in enumerate(profiles):
            document = copy.deepcopy(base.document)
            document["evaluation"]["value"]["reassociation"] = index == 0
            profiles[index] = TargetProfile(
                base.reference,
                base.target_triple,
                base.abi,
                base.compiler_version,
                semantic_digest(document),
                document,
            )
    return evaluate_rules(
        (RULE,), *profiles, [_source(facts=facts)], ir or [], evidence or [], budgets or {}
    )


@pytest.mark.parametrize("separation", ["loop", "function", "accumulator", "column"])
def test_independent_candidates_keep_their_own_evidence(separation: str) -> None:
    first, second = reduction(1), reduction(2)
    if separation == "function":
        second["function_id"], second["function_symbol"] = "d" * 64, "other"
    elif separation == "column":
        second["payload"]["accumulator_id"] = "d" * 64
        second["location"] = {**first["location"], "column": 10}
    else:
        second["payload"][f"{separation}_id"] = "d" * 64
    run = evaluate([first, second])
    assert run.counts["matched"] == 2
    assert len({item.scope for item in run.assessments}) == 2
    for finding in run.findings:
        own = first if finding["location"] == first["location"] else second
        assert finding["evidence"] == [{"kind": "source_fact", "ref": own["fact_id"]}]
        assert finding["related_locations"] == []
        assert finding["affected_count"] == 1
        assert finding["evidence_origin"] == "heuristic"


def test_one_recurrence_multiple_evidence_and_duplicates_are_not_multiple_risks() -> None:
    a, b = reduction(1), reduction(2)
    run = evaluate([a, b, copy.deepcopy(a)])
    assert len(run.findings) == 1
    assert run.findings[0]["affected_count"] == 1
    assert len(run.findings[0]["evidence"]) == 2
    assert len(run.findings[0]["related_locations"]) == 1
    assert evaluate([b, a]).findings == run.findings


def test_unknown_failed_nonmatch_and_match_are_isolated() -> None:
    run = evaluate(
        [
            reduction(1),
            reduction(2, loop=2, ambiguous=True),
            reduction(3, loop=3, iteration_count="invalid"),
            reduction(4, loop=4, compensation="kahan"),
        ]
    )
    assert {item.status for item in run.assessments} == {
        "matched",
        "unknown",
        "failed",
        "not_matched",
    }
    assert len(run.findings) == 1
    assert run.findings[0]["location"]["line"] == 2
    assert len(run.diagnostics) == 2
    assert evaluate([reduction(1), reduction(2, loop=2)]).findings[0]["finding_code"] == RULE


def test_unrelated_ir_does_not_upgrade_or_invalidate_other_candidates() -> None:
    a, b, compensated = (
        reduction(1),
        reduction(2, loop=2),
        reduction(3, loop=3, compensation="kahan"),
    )
    ir, evidence = linked(a)
    run = evaluate([a, b, compensated], ir=[ir], evidence=[evidence], policies=True)
    by_line = {f["location"]["line"]: f for f in run.findings}
    assert by_line[2]["evidence_origin"] == "deterministic"
    assert by_line[3]["evidence_origin"] == "heuristic"
    assert by_line[3]["requires_human_confirmation"] is True
    assert by_line[3]["evidence"] == [{"kind": "source_fact", "ref": b["fact_id"]}]
    assert len(run.findings) == 2
    assert evaluate([b], ir=[ir], evidence=[evidence], policies=True).findings == (by_line[3],)


@pytest.mark.parametrize(
    "bad",
    [
        "ambiguity",
        "missing_ir",
        "missing_id",
        "weak",
        "shared",
        "function",
        "column",
        "opcode",
        "missing_debug",
    ],
)
def test_unreliable_binding_is_local_unknown(bad: str) -> None:
    a, b = reduction(1), reduction(2, loop=2)
    ir, evidence = linked(a)
    binding = evidence["bindings"][0]
    if bad == "ambiguity":
        evidence["ambiguities"] = [{"source_fact_ids": [a["fact_id"]]}]
    elif bad == "missing_ir":
        binding["ir_fact_id"] = "missing"
    elif bad == "missing_id":
        binding.pop("binding_id")
    elif bad == "weak":
        binding["confidence"] = "weak"
    elif bad == "shared":
        evidence["bindings"].append({**binding, "source_fact_id": "unrelated"})
    elif bad == "function":
        ir["facts"][0]["function"] = "other"
    elif bad == "column":
        ir["facts"][0]["debug_location"] = {**a["location"], "column": 3}
    elif bad == "opcode":
        ir["facts"][0]["opcode"] = "fptrunc"
    else:
        ir["facts"][0].pop("debug_location")
    run = evaluate([a, b], ir=[ir], evidence=[evidence], policies=True)
    assert run.counts["unknown"] == 1
    assert len(run.findings) == 1
    assert run.findings[0]["location"] == b["location"]


@pytest.mark.parametrize(
    "profile,policies", [("source-preserving", True), ("build-faithful", False)]
)
def test_ir_without_build_profile_and_policy_proof_stays_heuristic(
    profile: str, policies: bool
) -> None:
    a = reduction(1)
    ir, evidence = linked(a, profile=profile)
    result = evaluate([a], ir=[ir], evidence=[evidence], policies=policies)
    assert result.findings[0]["confidence"] == "medium"
    assert result.findings[0]["evidence_origin"] == "heuristic"


def test_explicit_binding_unknown_location_and_compensation() -> None:
    a = reduction(1, compensation="kahan")
    a["location"] = None
    ir, evidence = linked(a)
    evidence["bindings"][0].update(method="explicit-sidecar", confidence="exact")
    ir["facts"][0].pop("function")
    result = evaluate([a], ir=[ir], evidence=[evidence], policies=True)
    assert result.findings[0]["location"] is None
    assert result.findings[0]["semantic"]["compensation_invalidated"] is True
    ir["facts"][0]["fast_math_flags"] = []
    assert evaluate([a], ir=[ir], evidence=[evidence]).assessments[0].status == "not_matched"


@pytest.mark.parametrize(
    "payload", [{"iteration_count": 0}, {"iteration_count": 1}, {"fixed_order": True}]
)
def test_single_or_fixed_order_not_reported(payload: dict[str, Any]) -> None:
    assert evaluate([reduction(1, **payload)]).findings == ()


def test_unknown_iteration_identity_and_no_candidates() -> None:
    assert evaluate([]).assessments[0].reason_code == "no_reduction"
    assert evaluate([reduction(1, iteration_count=None)]).counts["matched"] == 1
    missing = reduction(1, loop_id=None, iteration_count=None)
    assert evaluate([missing]).assessments[0].reason_code == "reduction_identity_unknown"
    assert candidates([_fact(1), {**missing, "payload": None}], "ctx")


@pytest.mark.parametrize("budget", ["max_rule_candidates", "max_rule_assessments"])
def test_budget_stops_before_evaluating_next_candidate(
    budget: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_point_precision_scanner import rules

    original = rules._reduction_candidate
    visited: list[str] = []

    def track(context: Any, candidate: Any, scope: str):
        visited.append(candidate.identity)
        return original(context, candidate, scope)

    monkeypatch.setattr(rules, "_reduction_candidate", track)
    facts = [reduction(i, loop=i) for i in range(1, 4)]
    run = evaluate(facts, budgets={budget: 1})
    assert len(visited) == 1
    assert run.counts["matched"] == 1 and run.counts["unknown"] == 1
    assert run.assessments[-1].frontier or run.assessments[0].frontier
    assert evaluate(facts, budgets={budget: 3}).counts["unknown"] == 0
    assert evaluate(facts, budgets={budget: 0}).counts["matched"] == 0
    empty = evaluate([], budgets={budget: 0})
    assert empty.assessments[0].status == "unknown"
    assert empty.assessments[0].reason_code == "budget_exceeded"


def test_reference_budget_and_single_point_suppression() -> None:
    a, b = reduction(1), reduction(2, loop=2)
    ir, evidence = linked(a)
    run = evaluate([a, b], ir=[ir], evidence=[evidence], budgets={"max_rule_evidence_refs": 1})
    assert run.counts["unknown"] == 1
    assert run.findings[0]["location"] == b["location"]
    run = evaluate([a, b])
    visible, suppressed = apply_suppressions(
        run.findings, [Suppression(RULE, "main.c", "reviewed", 2, 2, "request")]
    )
    assert len(visible) == len(suppressed) == 1
    assert visible[0]["location"] == b["location"]
    assert visible[0]["finding_id"] in {f["finding_id"] for f in run.findings}
    visible, suppressed = apply_suppressions(
        run.findings, [Suppression(RULE, "main.c", "reviewed", 2, 3, "request")]
    )
    assert not visible and len(suppressed) == 2


def test_unresolved_accumulator_and_mixed_recurrence_are_local_unknown() -> None:
    run = evaluate(
        [
            reduction(1, accumulator_id=None),
            reduction(2, loop=2, operation="+="),
            reduction(3, loop=2, operation="*="),
            reduction(4, loop=3),
        ]
    )
    assert run.counts["unknown"] == 2
    assert run.counts["matched"] == 1
    assert run.findings[0]["location"]["line"] == 5


def test_real_binding_identity_excludes_unrelated_bundle_changes() -> None:
    from floating_point_precision_scanner.evidence import _binding

    a, other = reduction(1), reduction(2, loop=2)
    ir, evidence = linked(a)
    first = _binding(
        a["fact_id"],
        ir["facts"][0]["fact_id"],
        "derived-debug",
        "strong",
        "direct",
        "1" * 64,
        "2" * 64,
        "reduction-lowering",
    )
    second = _binding(
        a["fact_id"],
        ir["facts"][0]["fact_id"],
        "derived-debug",
        "strong",
        "direct",
        "3" * 64,
        "4" * 64,
        "reduction-lowering",
    )
    assert first["binding_id"] == second["binding_id"]
    assert first["source_fact_bundle_digest"] != second["source_fact_bundle_digest"]
    evidence["bindings"] = [first]
    original = evaluate([a], ir=[ir], evidence=[evidence], policies=True).findings[0]
    evidence["bindings"] = [second]
    expanded = evaluate([a, other], ir=[ir], evidence=[evidence], policies=True)
    assert original in expanded.findings


def test_expression_ranges_and_operation_bindings() -> None:
    from floating_point_precision_scanner.evidence import _compatible

    a = reduction(1, operation="+=")
    a["source_range"] = {"begin": a["location"], "end": {**a["location"], "column": 20}}
    assert position_matches_source(a, {**a["location"], "column": 10})
    assert not position_matches_source(a, {**a["location"], "column": 21})
    assert not position_matches_source(a, {**a["location"], "path": "other.c"})
    a["source_range"].pop("end")
    assert not position_matches_source(a, {**a["location"], "column": 10})
    assert not _compatible(a, {"opcode": "fmul"})
    assert not _compatible(a, {"opcode": "call", "callee": "unrelated"})
    assert _compatible(a, {"opcode": "call", "callee": "llvm.vector.reduce.fadd.v4f64"})
    assert _compatible(a, {"opcode": "phi"})


def test_macro_expansions_keep_separate_candidate_identities() -> None:
    first, second = reduction(1), reduction(2, loop=2)
    for fact in (first, second):
        fact["location"] = {
            "expansion": fact["location"],
            "spelling": {"path": "macros.h", "line": 1, "column": 1},
        }
    run = evaluate([first, second])
    assert len(run.findings) == 2
    assert len({finding["finding_id"] for finding in run.findings}) == 2
    assert evaluate([second, first]).findings == run.findings
