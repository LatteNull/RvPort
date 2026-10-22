"""Offline orchestration for versioned thread-entry discovery artifacts."""

from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, canonical, identity, read_document
from .execution import OutputStore
from .pipeline import write_json
from .thread_entry_analysis import build_local_facts, build_report, build_root_overlay, build_site_index
from .thread_entry_cache import ThreadEntryCache, cache_key
from .thread_entry_contracts import (
    dependency, diagnostic, read_thread_entry_document, semantic_digest,
    validate_thread_entry_document,
)


SUPPORTED = {
    "ModuleFacts", "SourceSemanticFacts", "SourceIRBinding", "ThreadLocalFacts",
    "CppThreadLocalFacts", "ExecutionRootIndex", "RootDrivenAnalysisPlan",
}


def _read_evidence(path, kind):
    if kind == "ModuleFacts":
        return read_document(path, kind)
    if kind in {"SourceSemanticFacts", "SourceIRBinding"}:
        from .source_contracts import read_source_document
        return read_source_document(path, kind)
    if kind == "ThreadLocalFacts":
        from .thread_contracts import read_thread_document
        return read_thread_document(path, kind)
    if kind == "CppThreadLocalFacts":
        from .cpp_thread_contracts import read_cpp_thread_document
        return read_cpp_thread_document(path, kind)
    if kind in {"ExecutionRootIndex", "RootDrivenAnalysisPlan"}:
        from .root_contracts import read_root_document
        return read_root_document(path, kind)
    raise AnalysisError("invalid_reference", f"Unsupported thread-entry evidence kind: {kind}")


def _evidence_id(value, kind):
    return {
        "ModuleFacts": value.get("artifact_key"),
        "SourceSemanticFacts": value.get("physical_tu_id"),
        "SourceIRBinding": value.get("scope_id"),
        "ThreadLocalFacts": value.get("origin", {}).get("artifact_key"),
        "CppThreadLocalFacts": value.get("physical_tu_id"),
        "ExecutionRootIndex": value.get("scope_id"),
        "RootDrivenAnalysisPlan": value.get("scope_id"),
    }[kind]


def _resolve_input(store, item):
    if item["kind"] not in SUPPORTED:
        raise AnalysisError("invalid_reference", f"Unsupported thread-entry evidence kind: {item['kind']}")
    root = Path(store).resolve()
    path = (root / item["path"]).resolve()
    if root not in path.parents or not path.is_file():
        raise AnalysisError("invalid_reference", f"Thread-entry evidence path is missing or escapes the store: {item['path']}")
    value = _read_evidence(path, item["kind"])
    if identity(value) != item["digest"]:
        raise AnalysisError("invalid_reference", f"Thread-entry evidence digest changed: {item['path']}")
    if _evidence_id(value, item["kind"]) != item["id"]:
        raise AnalysisError("invalid_reference", f"Thread-entry evidence id disagrees with document: {item['path']}")
    return value


def load_evidence(request, artifact_store):
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


def discover_thread_entries(request_path, artifact_store, output, source_worker=None, ir_worker=None,
                            *, clock=monotonic):
    del source_worker, ir_worker  # v1 composes explicit versioned evidence and never launches builds.
    started = clock()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "discover-thread-entries requires a fresh output directory")
    request = read_thread_entry_document(request_path, "ThreadEntryDiscoveryRequest")
    evidence = load_evidence(request, artifact_store)
    dependency_digests = [item["digest"] for item in evidence["dependencies"]]
    cache = ThreadEntryCache(Path(artifact_store) / "derived")
    hits = misses = 0
    local_facts = []
    for member in request["members"]:
        key = cache_key("local", {"request": request, "member": member}, dependency_digests)
        facts = cache.load("local", key, "ThreadEntryLocalFacts")
        if facts is None:
            facts = build_local_facts(request, member, evidence)
            if facts["status"] == "complete":
                cache.publish("local", key, facts)
            misses += 1
        else:
            hits += 1
        local_facts.append(facts)
    local_facts.sort(key=lambda item: item["physical_tu_id"])

    sites_key = cache_key("sites", request, [*(item["semantic_digest"] for item in local_facts), *dependency_digests])
    sites = cache.load("sites", sites_key, "ThreadEntrySiteIndex")
    if sites is None:
        sites = build_site_index(request, local_facts)
        if sites["status"] == "complete":
            cache.publish("sites", sites_key, sites)
        misses += 1
    else:
        hits += 1

    base_roots = evidence.get("ExecutionRootIndex", {}).get(request["scope_id"])
    base_plan = evidence.get("RootDrivenAnalysisPlan", {}).get(request["scope_id"])
    overlay_key = cache_key("overlay", request, [sites["semantic_digest"],
                                                   identity(base_roots) if base_roots else "none",
                                                   identity(base_plan) if base_plan else "none"])
    overlay = cache.load("overlay", overlay_key, "ThreadEntryRootOverlay")
    if overlay is None:
        overlay = build_root_overlay(request, sites, base_roots, base_plan)
        if overlay["status"] == "complete":
            cache.publish("overlay", overlay_key, overlay)
        misses += 1
    else:
        hits += 1
    elapsed = clock() - started
    if elapsed > request["budgets"]["request_seconds"]:
        overlay["status"] = "partial"
        overlay["frontier"].append(diagnostic(
            "request-time-budget-exhausted", "线程入口请求超过 wall-clock 预算",
            "The thread-entry request exceeded its wall-clock budget",
            source={"hit": elapsed, "limit": request["budgets"]["request_seconds"]}))
        overlay["semantic_digest"] = semantic_digest(overlay)
        validate_thread_entry_document(overlay, "ThreadEntryRootOverlay")
    report = build_report(request, local_facts, sites, overlay, hits=hits, misses=misses)
    bundle = {"local": local_facts, "sites": sites, "overlay": overlay, "report": report}
    if len(canonical(bundle).encode("utf-8")) > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "Thread-entry output exceeds request_output_bytes")

    store = OutputStore(output)
    write_json(store, request, "request.json")
    for facts in local_facts:
        write_json(store, facts, f"local/{facts['physical_tu_id']}.json")
    write_json(store, sites, "sites/index.json")
    write_json(store, overlay, "roots/overlay.json")
    write_json(store, report, "report.json")
    return report
