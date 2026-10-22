"""End-to-end P3 orchestration over explicit roots and an explicit scope."""

from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, canonical, identity
from .effect_contracts import effect_document, expected_analysis_protocol, read_effect_document
from .effect_inputs import EffectInputs
from .execution import OutputStore
from .pipeline import write_json
from .summarize import summarize
from .thread_cache import ThreadCache, graph_key
from .thread_contracts import diagnostic, read_thread_document, validate_thread_document
from .thread_graph import build_thread_graph
from .thread_models import adopt_all
from .thread_report import build_thread_report
from .thread_worker import analyze_thread_facts
from .source_assistance import load_source_assistance, resolve_function


def _resolve_scope(request_path, scope):
    path = Path(scope)
    return path.resolve() if path.is_absolute() else (Path(request_path).resolve().parent / path).resolve()


def _effect_summaries(directory):
    paths = sorted((Path(directory) / "summaries").glob("*.json"))
    if not paths:
        raise AnalysisError("effect_summary_missing", "P2 produced no root summaries")
    values = [read_effect_document(path, "EffectSummary") for path in paths]
    return {item["context_id"]: item for item in values}


def _check_deadline(started, request, stage):
    if monotonic() - started > request["budgets"]["request_seconds"]:
        raise AnalysisError("request_timeout", f"P3 request exceeded its wall-clock budget after {stage}")


def _p2_argument(value):
    """Translate the deliberately smaller P3 root domain into a P2 Value."""
    if value["kind"] == "integer":
        return {**value, "hex": value["hex"].upper()}
    if value["kind"] == "object":
        return {**value, "offset": None, "address_space": 0, "allocation": None}
    if value["kind"] == "null":
        return {"kind": "null", "address_space": 0}
    return value


def _callback_definition(inputs, target, source_binding=None):
    module = inputs.modules.get(target["artifact_key"])
    declared = next((item for item in module["functions"] if item["id"] == target["id"]), None) if module else None
    if declared is None:
        return None
    if not declared["declaration"]:
        return {"artifact_key": target["artifact_key"], "function_id": declared["id"]}
    if source_binding is not None:
        resolved = resolve_function(source_binding, target["artifact_key"], target["id"])
        return resolved["target"] if resolved["status"] == "resolved" else None
    name = declared.get("name")
    if not name or not inputs.scope.get("closed") or inputs.scope.get("external_boundaries"):
        return None
    candidates = [
        {"artifact_key": artifact, "function_id": function["id"]}
        for artifact, facts in inputs.modules.items()
        for function in facts["functions"]
        if not function["declaration"] and function.get("name") == name
        and function.get("linkage") in {"external", "internal"} and not function.get("comdat")
    ]
    return candidates[0] if len(candidates) == 1 else None


def _p2_roots(inputs, request, local_facts, source_binding=None):
    """Plan explicit P2 roots without falling back to all-defined mode.

    Thread roots are always included. Every locally adopted direct pthread_create
    callback is also included, so nested worker discovery has an EffectSummary
    available without analyzing unrelated ordinary definitions as roots.
    """
    roots = [{"artifact_key": item["artifact_key"], "function_id": item["function_id"],
              "arguments": [_p2_argument(value) for value in item["arguments"]]}
             for item in request["roots"]]
    adoptions, _ = adopt_all(local_facts)
    adopted = {canonical(item["call"]) for item in adoptions
               if item["kind"] == "adopted" and item["event"] == "create"}
    for facts in local_facts.values():
        for call in facts["calls"]:
            if canonical(call["source"]) not in adopted:
                continue
            target = _callback_definition(inputs, call["callback_targets"][0], source_binding)
            if target is None:
                continue
            source = call["arguments"][3]
            target["arguments"] = ([{"kind": "object", "source": source, "offset": None,
                                      "address_space": 0, "allocation": None}]
                                   if isinstance(source, dict) else
                                   [])
            roots.append(target)
    unique = {canonical(item): item for item in roots}
    return [unique[key] for key in sorted(unique)]


def model_threads(request_path, artifact_store, output, worker, source_evidence=None):
    started = monotonic()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "model-threads requires a fresh output directory")
    request = read_thread_document(request_path, "ThreadAnalysisRequest")
    scope_path = _resolve_scope(request_path, request["scope"])
    inputs = EffectInputs.load(scope_path, artifact_store)
    assistance = load_source_assistance(source_evidence, scope_id=inputs.scope_id) if source_evidence else None

    staging = OutputStore(output)
    entries = analyze_thread_facts(inputs, worker, staging, budgets=request["budgets"])
    _check_deadline(started, request, "local thread analysis")
    local_facts, order_facts, failures = {}, {}, []
    for key, entry in entries.items():
        if entry["result"] is None:
            failures.append({"artifact_key": key, **entry["error"]})
            continue
        local_facts[key] = entry["result"]["local"]
        order_facts[key] = entry["result"]["order"]
        write_json(staging, local_facts[key], f"thread-local/{key}.json")
        write_json(staging, order_facts[key], f"execution-order/{key}.json")
    root_artifacts = {root["artifact_key"] for root in request["roots"]}
    if not root_artifacts <= set(local_facts):
        raise AnalysisError("thread_local_failed", str(failures))

    effect_output = output / "effects"
    p2_budgets = expected_analysis_protocol()["budgets"]
    p2_request = effect_document("EffectAnalysisRequest", scope=str(scope_path), mode="roots",
                                 roots=_p2_roots(inputs, request, local_facts,
                                                 assistance["binding"] if assistance else None),
                                 budgets=p2_budgets)
    with staging.temporary() as temporary:
        p2_request_path = temporary / "effect-request.json"
        p2_request_path.write_text(canonical(p2_request), encoding="utf-8")
        effect_report = (summarize(p2_request_path, scope_path, artifact_store, effect_output, worker,
                                   source_evidence) if source_evidence else
                         summarize(p2_request_path, scope_path, artifact_store, effect_output, worker))
    _check_deadline(started, request, "effect analysis")
    summaries = _effect_summaries(effect_output)

    dependency_keys = [identity(item) for item in [*local_facts.values(), *order_facts.values(),
                                                    *summaries.values(), *failures,
                                                    *([] if assistance is None else assistance.values())]]
    cache = ThreadCache(Path(artifact_store) / "derived" / "thread-sync-contexts-v1")
    key = graph_key(request, dependency_keys)
    graph = cache.load("graphs", key, "ThreadContextGraph")
    if graph is None:
        graph = build_thread_graph(inputs, request, local_facts, order_facts, summaries, assistance)
        for failure in failures:
            item = diagnostic(
                "thread-local-member-failed", f"线程局部分析成员失败：{failure['artifact_key']}",
                f"Thread-local analysis member failed: {failure['artifact_key']}",
                suggestion="修复该 BC/输入后使用新的输出目录重试",
                suggestion_en="Repair the BC/input and retry with a fresh output directory",
            )
            graph["frontier"].append(item); graph["diagnostics"].append(item)
        if failures:
            graph["status"] = "partial"
        validate_thread_document(graph, "ThreadContextGraph")
        cache.publish("graphs", key, graph)
    _check_deadline(started, request, "thread graph construction")
    report = build_thread_report(inputs, request, graph, local_facts, order_facts, effect_report)
    if len(canonical({"graph": graph, "report": report}).encode()) > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "P3 graph and report exceed the request output budget")
    write_json(staging, request, "request.json")
    write_json(staging, graph, f"graphs/{identity(graph)}.json")
    write_json(staging, report, "report.json")
    return report
