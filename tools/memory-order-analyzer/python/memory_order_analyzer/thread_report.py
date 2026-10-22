"""Layered P3 report; model completeness never becomes a safety verdict."""

from .contracts import identity
from .thread_contracts import diagnostic, expected_thread_protocol, thread_document


def counts(items):
    values = {name: sum(item["status"] == name for item in items)
              for name in ("complete", "partial", "failed", "not_run")}
    total = len(items)
    return {"planned": total, **values,
            "complete_ratio": values["complete"] / total if total else None}


def aggregate(items):
    if not items:
        return "not_run"
    states = {item["status"] for item in items}
    if states == {"complete"}:
        return "complete"
    if states == {"failed"}:
        return "failed"
    return "partial"


def build_thread_report(inputs, request, graph, local_facts, order_facts, effect_report):
    members = []
    for key in sorted(inputs.scope["members"]):
        if key not in local_facts or key not in order_facts:
            status = "failed"
        else:
            states = {local_facts[key]["status"], order_facts[key]["status"]}
            status = "complete" if states == {"complete"} else "failed" if states == {"failed"} else "partial"
        members.append({"id": key, "status": status,
                        "reason": None if status == "complete" else "thread-local-facts-incomplete"})
    root_instances = [item for item in graph["instances"] if item["parent_id"] is None]
    contexts = {item["id"]: item for item in graph["contexts"]}
    roots = [{"id": item["id"], "status": contexts[item["context_id"]]["status"],
              "reason": contexts[item["context_id"]]["reason"]} for item in root_instances]
    context_items = [{"id": item["id"], "status": item["status"], "reason": item["reason"]}
                     for item in graph["contexts"]]
    source_states = {inputs.modules[key]["source_mapping"] for key in inputs.scope["members"]}
    source_mapping = ("complete" if source_states == {"complete"} else
                      "unavailable" if source_states == {"unavailable"} else "partial")
    effect_status = effect_report.get("interprocedural_analysis", "failed")
    thread_status = graph["status"]
    local_status = aggregate(members)
    exit_code = (1 if thread_status == "failed" or not roots else
                 0 if thread_status == local_status == effect_status == "complete" and source_mapping == "complete" else 2)
    graph_ref = {"kind": "ThreadContextGraph", "id": identity(graph), "digest": identity(graph)}
    dependencies = [graph_ref, *graph["dependencies"]]
    assumptions = ["posix-pthread-v1", "unchecked-api-results-are-may-success",
                   "p2-order-is-not-an-execution-order-proof"]
    return thread_document(
        "ThreadAnalysisReport", request_hash=identity(request), scope_id=inputs.scope_id,
        model_id=request["model_id"], budgets=request["budgets"], input_integrity="complete",
        effect_analysis=effect_status, local_thread_analysis=local_status,
        thread_modeling=thread_status, synchronization_analysis=thread_status,
        source_mapping=source_mapping, members=members, roots=roots, contexts=context_items,
        member_counts=counts(members), root_counts=counts(roots), context_counts=counts(context_items),
        graph=graph_ref, dependencies=dependencies, frontier=graph["frontier"],
        diagnostics=graph["diagnostics"], assumptions=assumptions,
        safety="not_evaluated", findings=None, exit_code=exit_code,
    )


def failed_thread_report(code, detail, *, budgets=None):
    budgets = budgets or expected_thread_protocol()["budgets"]
    empty = {"planned": 0, "complete": 0, "partial": 0, "failed": 0,
             "not_run": 0, "complete_ratio": None}
    detail = str(detail)
    item = diagnostic(
        code, f"线程分析请求失败：{detail}"[:1024],
        f"Thread analysis request failed: {detail}"[:1024],
        suggestion="修正请求或输入后使用新的输出目录重试",
        suggestion_en="Correct the request or inputs and retry with a fresh output directory",
    )
    return thread_document(
        "ThreadAnalysisReport", request_hash=None, scope_id=None,
        model_id="posix-pthread-v1", budgets=budgets,
        input_integrity="failed", effect_analysis="not_run", local_thread_analysis="not_run",
        thread_modeling="not_run", synchronization_analysis="not_run", source_mapping="not_run",
        members=[], roots=[], contexts=[], member_counts=empty, root_counts=empty,
        context_counts=empty, graph=None, dependencies=[], frontier=[item], diagnostics=[item],
        assumptions=[], safety="not_evaluated", findings=None, exit_code=1,
    )
