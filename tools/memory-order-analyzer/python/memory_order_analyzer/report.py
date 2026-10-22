"""Infrastructure completeness is separate from any safety evaluation."""

from .contracts import document


def ratio(hit, total):
    return hit / total if total else None


def make_report(operation, *, planned=0, records=0, artifacts=(), facts=(), failures=(), cached=0, scope=None, ready=None):
    success = len(artifacts)
    events = [event for module in facts for event in module["events"]]
    located = sum(bool(event["source"]["inline_chain"]) for event in events)
    mappings = [module["source_mapping"] for module in facts]
    source = "unavailable" if not mappings or all(s == "unavailable" for s in mappings) else "complete" if all(s == "complete" for s in mappings) else "partial"
    build = "not_applicable" if operation != "collect" else "complete" if success == planned and planned else "partial" if success else "failed"
    ir = "complete" if len(facts) == planned and planned else "partial" if facts else "failed"
    scope_status = "unknown" if scope is None else "partial" if scope["unknown"] or scope["diagnostics"] else "declared"
    degraded = bool(failures) or source != "complete" or any(a["provenance"] == "unknown" for a in artifacts)
    complete_facts = sum(m["extraction"]["status"] == "complete" for m in facts)
    partial_facts = len(facts) - complete_facts
    degraded |= partial_facts > 0
    fact_summary = {"status": "not_run" if operation == "doctor" else "failed" if not facts else "partial" if partial_facts or failures or len(facts) != planned else "complete",
                    "planned": planned, "complete": complete_facts, "partial": partial_facts,
                    "failed": max(0, planned - len(facts)), "complete_ratio": ratio(complete_facts, planned),
                    "diagnostics": [{"artifact_key": m["artifact_key"], **d} for m in facts for d in m["extraction"]["diagnostics"]] + list(failures)}
    if scope is not None:
        degraded |= scope_status == "partial"
    exit_code = 1 if not success else 2 if degraded else 0
    if operation == "doctor":
        exit_code = 0 if ready else 1
    stage_state = "timed_out" if failures and all(f.get("code") == "timed_out" for f in failures) else "unsupported" if failures and all(f.get("code", "").endswith("_unsupported") for f in failures) else "failed" if exit_code == 1 else "completed"
    stages = {operation: stage_state, "build": "not_run" if build == "not_applicable" else "failed" if build == "failed" else "completed",
              "ir": "failed" if ir == "failed" else "completed", "source": "not_run" if not facts else "completed",
              "scope": "not_run" if scope is None else "completed", "semantic_analysis": "not_run"}
    if operation == "doctor":
        stages["ir"] = "not_run"
    return document("RunReport", operation=operation, build_status=build, ir_status=ir, source_mapping=source,
                    scope_status=scope_status, stages=stages,
                    counts={"original_records": records, "planned_tus": planned, "generated": success if operation == "collect" else 0,
                            "verified": len(facts), "failed": len(failures), "cache_hits": cached,
                            "unknown_calls": sum(call["kind"] == "indirect" for module in facts for call in module["calls"]),
                            "events": len(events), "located_events": located, "located_ratio": ratio(located, len(events)),
                            "success_ratio": ratio(success, planned)}, failures=list(failures),
                    artifacts=[a["artifact_key"] for a in artifacts], semantic_analysis="not_run", safety="not_evaluated",
                    findings=None, exit_code=exit_code, fact_extraction=fact_summary,
                    artifact_migrations=[{"from": a["toolchain"]["migration_from"], "to": a["artifact_key"]}
                                         for a in artifacts if "migration_from" in a["toolchain"]])
