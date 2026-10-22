"""Offline R1 orchestration over explicit, content-addressed P1/A1/P2/P3/A3 evidence."""

import json
from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, canonical, identity, read_document
from .execution import OutputStore
from .pipeline import write_json
from .root_analysis import (
    align_creation_sites, build_analysis_plan, build_root_report, discover_execution_roots,
)
from .root_cache import RootAnalysisCache, cache_key
from .root_contracts import dependency, read_root_document


SUPPORTED = {
    "ModuleFacts", "SourceSemanticFacts", "ProgramEntityIndex", "SourceIRBinding",
    "ThreadLocalFacts", "ExecutionOrderFacts", "EffectSummary", "ThreadContextGraph",
    "CppThreadLocalFacts", "CppThreadLifecycleGraph",
}


def _read_evidence(path, kind):
    if kind == "ModuleFacts":
        return read_document(path, kind)
    if kind in {"SourceSemanticFacts", "ProgramEntityIndex", "SourceIRBinding"}:
        from .source_contracts import read_source_document
        return read_source_document(path, kind)
    if kind in {"ThreadLocalFacts", "ExecutionOrderFacts", "ThreadContextGraph"}:
        from .thread_contracts import read_thread_document
        return read_thread_document(path, kind)
    if kind == "EffectSummary":
        from .effect_contracts import read_effect_document
        return read_effect_document(path, kind)
    if kind in {"CppThreadLocalFacts", "CppThreadLifecycleGraph"}:
        from .cpp_thread_contracts import read_cpp_thread_document
        return read_cpp_thread_document(path, kind)
    raise AnalysisError("invalid_reference", f"Unsupported R1 evidence kind: {kind}")


def _resolve_input(store, item):
    if item["kind"] not in SUPPORTED:
        raise AnalysisError("invalid_reference", f"Unsupported R1 evidence kind: {item['kind']}")
    root = Path(store).resolve()
    path = (root / item["path"]).resolve()
    if root not in path.parents or not path.is_file():
        raise AnalysisError("invalid_reference", f"R1 evidence path is missing or escapes the store: {item['path']}")
    value = _read_evidence(path, item["kind"])
    if identity(value) != item["digest"]:
        raise AnalysisError("invalid_reference", f"R1 evidence digest changed: {item['path']}")
    actual_id = {
        "ModuleFacts": value.get("artifact_key"),
        "SourceSemanticFacts": value.get("physical_tu_id"),
        "ProgramEntityIndex": value.get("scope_id"),
        "SourceIRBinding": value.get("scope_id"),
        "ThreadLocalFacts": value.get("origin", {}).get("artifact_key"),
        "ExecutionOrderFacts": value.get("origin", {}).get("artifact_key"),
        "EffectSummary": value.get("context_id"),
        "ThreadContextGraph": value.get("scope_id"),
        "CppThreadLocalFacts": value.get("physical_tu_id"),
        "CppThreadLifecycleGraph": value.get("scope_id"),
    }[item["kind"]]
    if actual_id != item["id"]:
        raise AnalysisError("invalid_reference", f"R1 evidence id disagrees with document: {item['path']}")
    return value


def load_root_evidence(request, artifact_store):
    result = {"by_member": {}, "dependencies": []}
    for member in request["members"]:
        values = {}
        for item in member["evidence"]:
            value = _resolve_input(artifact_store, item)
            values[item["kind"]] = value
            result.setdefault(item["kind"], {})[item["id"]] = value
            result["dependencies"].append(dependency(item["kind"], item["id"], value))
        result["by_member"][member["physical_tu_id"]] = values
    for item in request["global_evidence"]:
        value = _resolve_input(artifact_store, item)
        result.setdefault(item["kind"], {})[item["id"]] = value
        result["dependencies"].append(dependency(item["kind"], item["id"], value))
    result["dependencies"] = sorted(result["dependencies"], key=lambda item: (item["kind"], item["id"]))
    return result


def plan_execution_roots(request_path, artifact_store, output, source_worker=None, ir_worker=None,
                         *, clock=monotonic):
    del source_worker, ir_worker  # R1 composes already-versioned evidence; no new worker protocol is required.
    started = clock()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "plan-execution-roots requires a fresh output directory")
    request = read_root_document(request_path, "ExecutionRootDiscoveryRequest")
    evidence = load_root_evidence(request, artifact_store)
    dependency_digests = [item["digest"] for item in evidence["dependencies"]]
    cache = RootAnalysisCache(Path(artifact_store) / "derived")
    hits = misses = 0

    sites_key = cache_key("thread-creation-sites", request, dependency_digests)
    sites = cache.load("thread-creation-sites", sites_key, "ThreadCreationSiteIndex")
    if sites is None:
        sites = align_creation_sites(request, evidence)
        cache.publish("thread-creation-sites", sites_key, sites); misses += 1
    else:
        hits += 1

    roots_key = cache_key("execution-roots", request, [sites["semantic_digest"], *dependency_digests])
    roots = cache.load("execution-roots", roots_key, "ExecutionRootIndex")
    if roots is None:
        roots = discover_execution_roots(request, sites, evidence)
        cache.publish("execution-roots", roots_key, roots); misses += 1
    else:
        hits += 1

    plan_key = cache_key("plans", request, [sites["semantic_digest"], roots["semantic_digest"],
                                             *dependency_digests])
    plan = cache.load("plans", plan_key, "RootDrivenAnalysisPlan")
    if plan is None:
        plan = build_analysis_plan(request, sites, roots, evidence)
        cache.publish("plans", plan_key, plan); misses += 1
    else:
        hits += 1
    if clock() - started > request["budgets"]["request_seconds"]:
        raise AnalysisError("request_timeout", "R1 request exceeded its wall-clock budget")
    report = build_root_report(request, sites, roots, plan, hits=hits, misses=misses)
    if len(canonical({"sites": sites, "roots": roots, "plan": plan, "report": report}).encode("utf-8")) > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "R1 output exceeds request_output_bytes")
    store = OutputStore(output)
    write_json(store, request, "request.json")
    write_json(store, sites, "thread-creation-sites/index.json")
    write_json(store, roots, "execution-roots/index.json")
    write_json(store, plan, f"plans/{plan['semantic_digest']}.json")
    for item in plan["p2_requests"]:
        write_json(store, item, f"effects/requests/{item['id']}.json")
    for item in plan["p3_requests"]:
        write_json(store, item, f"threads/requests/{item['id']}.json")
    write_json(store, report, "report.json")
    return report
