"""End-to-end P2 command orchestration over an explicit scope snapshot."""

from pathlib import Path

from .contracts import AnalysisError, identity
from .effect_adoption import derive_adoptions
from .effect_contracts import expected_analysis_protocol, read_effect_document
from .effect_inputs import EffectInputs
from .effect_report import build_report
from .effect_scheduler import run_scheduler
from .effect_worker import analyze_metadata
from .execution import OutputStore
from .pipeline import write_json
from .source_assistance import load_source_assistance


def summarize(request_path, scope_path, artifact_store, output, worker, source_evidence=None):
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "Summarize requires a fresh output directory")
    request = read_effect_document(request_path, "EffectAnalysisRequest")
    if Path(request["scope"]).resolve() != Path(scope_path).resolve():
        raise AnalysisError("scope_mismatch", "Request scope and --scope identify different manifests")
    inputs = EffectInputs.load(scope_path, artifact_store)
    assistance = load_source_assistance(source_evidence, scope_id=inputs.scope_id) if source_evidence else None
    store = OutputStore(output)
    entries = analyze_metadata(inputs, worker, store, budgets=request["budgets"])
    local_facts, failures = {}, []
    for key, entry in entries.items():
        if entry["result"] is None:
            failures.append({"context_id": None, **entry["error"]})
        else:
            local_facts[key] = entry["result"]
            write_json(store, entry["result"], f"local/{key}.json")
    if set(local_facts) != set(inputs.scope["members"]):
        raise AnalysisError("local_analysis_failed", str(failures))
    adoptions = derive_adoptions(inputs, local_facts,
                                 assistance["binding"] if assistance else None)
    schedule = run_scheduler(inputs, request, local_facts, adoptions, worker, store,
                             cache_root=Path(artifact_store) / "derived" / "scoped-effects-v1")
    schedule["failures"].extend(failures)
    for summary in schedule["roots"]:
        write_json(store, summary, f"summaries/{identity(summary)}.json")
    report = build_report(inputs, request, local_facts, schedule, adoptions)
    write_json(store, request, "request.json")
    write_json(store, report, "report.json")
    return report


def failed_report(code, detail, *, budgets=None):
    from .effect_contracts import effect_document
    budgets = budgets or expected_analysis_protocol()["budgets"]
    empty = {"planned": 0, "complete": 0, "partial": 0, "failed": 0,
             "not_run": 0, "complete_ratio": None}
    diagnostic = {"code": code, "detail": detail, "source": None, "context_id": None}
    return effect_document("EffectAnalysisReport", request_hash=None, scope_id=None, budgets=budgets,
        input_integrity="failed", raw_fact_extraction="not_run", local_analysis="not_run",
        interprocedural_analysis="not_run", source_mapping="not_run", members=[], roots=[], contexts=[],
        member_counts=empty, root_counts=empty, context_counts=empty, frontier=[diagnostic],
        summaries=[], resolutions=[], diagnostics=[diagnostic], local_dependencies=[], assumptions=[],
        safety="not_evaluated", findings=None, exit_code=1)
