"""Layered P2 reporting.  Completeness never becomes a safety verdict."""

from .contracts import identity
from .effect_contracts import effect_document


def counts(items):
    values = {name: sum(item["status"] == name for item in items)
              for name in ("complete", "partial", "failed", "not_run")}
    total = len(items)
    return {"planned": total, **values,
            "complete_ratio": values["complete"] / total if total else None}


def aggregate_status(items):
    statuses = {item["status"] for item in items}
    if not items:
        return "not_run"
    if statuses == {"complete"}:
        return "complete"
    if statuses == {"failed"}:
        return "failed"
    return "partial"


def _raw_evidence(inputs, local_facts, schedule):
    """Retain P1 diagnostics and explain only supported ABI call diagnostics."""
    diagnostics, resolutions = [], []
    local_calls = {(key, item["source"]["id"]): item for key, facts in local_facts.items()
                   for item in facts["calls"]}
    contexts = {}
    for summary in schedule["contexts"].values():
        root = summary["root"]
        contexts.setdefault((root["artifact_key"], root["function_id"]), []).append(summary)
    for key in sorted(inputs.scope["members"]):
        module = inputs.modules[key]
        calls = {item["id"]: item for item in module["calls"]}
        for raw in module.get("extraction", {}).get("diagnostics", []):
            call = calls.get(raw["id"])
            source = ({"artifact_key": key, "function_id": call["function"], "id": raw["id"]}
                      if call else None)
            diagnostics.append({"code": raw["reason"], "detail": "P1 raw diagnostic retained",
                                "source": source, "context_id": None})
            local = local_calls.get((key, raw["id"]))
            if raw["reason"] != "uninterpreted_abi_attributes" or not call or not local or \
                    local["interface"]["status"] != "supported":
                continue
            for summary in contexts.get((key, call["function"]), []):
                resolutions.append({"facts_hash": identity(module), "source": source,
                    "reason": raw["reason"], "context_id": summary["context_id"],
                    "invocation_id": summary["root_invocation_id"],
                    "rule": "supported-c-call-interface-v1", "evidence": [source], "status": "explained"})
    return diagnostics, resolutions


def build_report(inputs, request, local_facts, schedule, adoptions):
    members = [{"id": key, "status": local_facts[key]["status"],
                "reason": None if local_facts[key]["status"] == "complete" else "local-supplement-is-conservative"}
               for key in sorted(inputs.scope["members"])]
    roots = [{"id": item["context_id"], "status": item["status"],
              "reason": None if item["status"] == "complete" else "unexpanded-or-unknown-frontier"}
             for item in schedule["roots"]]
    contexts = [{"id": key, "status": item["status"],
                 "reason": None if item["status"] == "complete" else "unexpanded-or-unknown-frontier"}
                for key, item in sorted(schedule["contexts"].items())]
    diagnostics = [diagnostic for item in schedule["roots"] for diagnostic in item["diagnostics"]]
    diagnostics += [{"code": item["code"], "detail": item["detail"], "source": None, "context_id": item.get("context_id")}
                    for item in schedule["failures"]]
    frontier = [item for item in diagnostics if item["code"] not in {"local_evaluation_pending"}]
    raw_diagnostics, resolutions = _raw_evidence(inputs, local_facts, schedule)
    diagnostics += raw_diagnostics
    root_status = aggregate_status(roots)
    source_states = {inputs.modules[key]["source_mapping"] for key in inputs.scope["members"]}
    source_mapping = "complete" if source_states == {"complete"} else "unavailable" if source_states == {"unavailable"} else "partial"
    exit_code = (1 if root_status in {"failed", "not_run"} else
                 0 if root_status == "complete" and source_mapping == "complete" else 2)
    raw_items = [{"status": inputs.modules[key].get("extraction", {}).get("status", "complete")}
                 for key in inputs.scope["members"]]
    dependencies = [{"context_id": item["context_id"], "digest": identity(item)} for item in schedule["roots"]]
    local_dependencies = [{"artifact_key": key, "digest": identity(local_facts[key])} for key in sorted(local_facts)]
    assumptions = sorted({assumption for item in adoptions for assumption in item["assumptions"]})
    return effect_document("EffectAnalysisReport", request_hash=identity(request), scope_id=inputs.scope_id,
        budgets=request["budgets"], input_integrity="complete", raw_fact_extraction=aggregate_status(raw_items),
        local_analysis=aggregate_status(members), interprocedural_analysis=root_status,
        source_mapping=source_mapping, members=members, roots=roots, contexts=contexts,
        member_counts=counts(members), root_counts=counts(roots), context_counts=counts(contexts),
        frontier=frontier, summaries=dependencies, resolutions=resolutions, diagnostics=diagnostics,
        assumptions=assumptions, safety="not_evaluated", findings=None, exit_code=exit_code,
        local_dependencies=local_dependencies)
