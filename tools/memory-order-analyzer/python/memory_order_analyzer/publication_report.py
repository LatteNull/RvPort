"""P4 layered report and failure report with conservative exit precedence."""

from copy import deepcopy

from .contracts import identity
from .publication_contracts import (
    MODEL_ID,
    diagnostic,
    expected_publication_protocol,
    layer_counts,
    outcome_counts,
    publication_document,
)


def _aggregate(items):
    if not items:
        return "not_run"
    states = {item["status"] for item in items}
    if states == {"complete"}:
        return "complete"
    if states == {"failed"}:
        return "failed"
    return "partial"


def build_publication_report(inputs, request, graph, local_facts, thread_report):
    members = []
    for key in sorted(inputs.scope["members"]):
        local = local_facts.get(key)
        status = local["status"] if local else "failed"
        members.append({"id": key, "status": status,
                        "reason": None if status == "complete" else "publication-local-incomplete"})
    source_states = {inputs.modules[key]["source_mapping"] for key in inputs.scope["members"]}
    source_mapping = ("complete" if source_states == {"complete"} else
                      "unavailable" if source_states == {"unavailable"} else "partial")
    local_status = _aggregate(members)
    p3_status = thread_report["thread_modeling"]
    graph_status = graph["status"]
    findings = [deepcopy(item) for item in graph["assessments"] if item["status"] == "finding"]
    stages = ["complete", "complete", "complete", p3_status, local_status, graph_status, graph_status]
    if "failed" in stages:
        exit_code, verdict = 1, "failed"
    elif any(value != "complete" for value in stages):
        exit_code, verdict = 2, "inconclusive"
    elif findings:
        exit_code, verdict = 3, "risks_found"
    else:
        exit_code, verdict = 0, "no_supported_risk_found"
    graph_ref = {"kind": "SinglePublicationProtocolGraph", "id": identity(graph), "digest": identity(graph)}
    return publication_document(
        "PublicationRiskReport", model_id=MODEL_ID, request_hash=identity(request),
        scope_id=inputs.scope_id, budgets=request["budgets"], input_integrity=stages[0],
        p1_analysis=stages[1], p2_analysis=stages[2], p3_analysis=stages[3],
        publication_local_analysis=stages[4], candidate_modeling=stages[5],
        risk_evaluation=stages[6], source_mapping=source_mapping,
        members=members, member_counts=layer_counts(members), outcome_counts=outcome_counts(
            graph["protocols"], graph["assessments"]), graph=graph_ref,
        dependencies=[graph_ref, *deepcopy(graph["dependencies"])],
        frontier=deepcopy(graph["frontier"]), diagnostics=deepcopy(graph["diagnostics"]),
        assumptions=["c-cpp-single-publication-v1", "posix-pthread-v1",
                     "conditional-success-observations", "not-a-whole-program-safety-proof"],
        safety="not_established", verdict=verdict, findings=findings, exit_code=exit_code)


def failed_publication_report(code, detail, *, budgets=None):
    budgets = budgets or expected_publication_protocol()["budgets"]
    item = diagnostic(
        code, f"一次性发布风险分析失败：{detail}"[:1024],
        f"Single-publication risk analysis failed: {detail}"[:1024],
        suggestion="修正请求或输入后使用新的输出目录重试",
        suggestion_en="Correct the request or inputs and retry with a fresh output directory")
    return publication_document(
        "PublicationRiskReport", model_id=MODEL_ID, request_hash=None, scope_id=None,
        budgets=budgets, input_integrity="failed", p1_analysis="not_run",
        p2_analysis="not_run", p3_analysis="not_run", publication_local_analysis="not_run",
        candidate_modeling="not_run", risk_evaluation="not_run", source_mapping="not_run",
        members=[], member_counts=layer_counts([]), outcome_counts=outcome_counts([], []),
        graph=None, dependencies=[], frontier=[item], diagnostics=[item], assumptions=[],
        safety="not_established", verdict="failed", findings=[], exit_code=1)
