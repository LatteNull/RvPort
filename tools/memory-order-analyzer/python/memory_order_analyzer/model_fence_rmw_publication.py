"""Offline orchestration for the opt-in A6 bounded publication analyzer."""

from pathlib import Path

from .advanced_atomic_analysis import (
    build_communication_graph,
    build_overlay,
    build_report,
    classify_source_constructs,
    extract_local_facts,
)
from .advanced_atomic_cache import AdvancedAtomicCache, analysis_key
from .advanced_atomic_contracts import (
    read_advanced_atomic_document,
    validate_advanced_atomic_document,
    verify_input,
)
from .contracts import AnalysisError
from .execution import OutputStore
from .pipeline import write_json


def _load(reference, base):
    return verify_input(reference, base=base) if reference is not None else None


def _profile_values(value, result):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"compiler", "compiler_family", "driver_mode", "target",
                               "target_triple", "platform", "toolchain"} and isinstance(child, str):
                result.append((key, child.lower()))
            _profile_values(child, result)
    elif isinstance(value, list):
        for child in value:
            _profile_values(child, result)


def _reject_excluded_profiles(documents):
    values = []
    for document in documents:
        if document is not None:
            _profile_values(document, values)
    for key, value in values:
        if "clang-cl" in value or "msvc" in value or "windows" in value:
            raise AnalysisError("unsupported_profile", f"A6 excludes Windows/MSVC/clang-cl ({key}={value})")
        if key.lower() in {"compiler", "compiler_family"} and value not in {"gcc", "clang"}:
            raise AnalysisError("unsupported_profile", f"A6 supports only GCC/Clang ({key}={value})")


def model_fence_rmw_publication(request_path, artifact_store, output):
    request_path = Path(request_path).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "model-fence-rmw-publication requires a fresh output directory")
    request = read_advanced_atomic_document(request_path, "FenceRmwPublicationRequest")
    base = request_path.parent
    modules = [_load(item, base) for item in request["module_facts"]]
    modules = [validate_advanced_atomic_document(item, "AdvancedAtomicFunctionFacts")
               if item.get("kind") == "AdvancedAtomicFunctionFacts" else item
               for item in modules]
    sources = [_load(item, base) for item in request["source_facts"]]
    thread_graph = _load(request["thread_graph"], base)
    provenance_graph = _load(request["provenance_graph"], base)
    publication_graph = _load(request["publication_graph"], base)
    root_plan = _load(request["root_plan"], base)
    demand_graph = _load(request["demand_graph"], base)
    candidate_graph = _load(request["candidate_graph"], base)
    _reject_excluded_profiles([
        *modules, *sources, thread_graph, provenance_graph, publication_graph,
        root_plan, demand_graph, candidate_graph])
    store = OutputStore(output)
    cache = AdvancedAtomicCache(Path(artifact_store) / "derived" / "fence-rmw-publication-v1")
    key = analysis_key(request)
    graph = cache.load("graph", key, "BoundedAtomicCommunicationGraph")
    overlay = cache.load("overlay", key, "AdvancedPublicationProtocolOverlay") if graph else None
    hits = 2 if graph and overlay else 0
    misses = 0 if hits else 2
    source = classify_source_constructs(sources, scope_id=request["scope_id"],
                                        language_standard=request["language_standard"])
    local = extract_local_facts(
        modules, scope_id=request["scope_id"], language_standard=request["language_standard"],
        thread_graph=thread_graph, provenance_graph=provenance_graph, budgets=request["budgets"],
        demand_documents=(root_plan, demand_graph, candidate_graph), source_constructs=source)
    if graph is None:
        graph = build_communication_graph(
            local, scope_id=request["scope_id"], language_standard=request["language_standard"],
            budgets=request["budgets"], closed_scope=request["closed_scope"],
            thread_graph=thread_graph)
    if overlay is None:
        overlay = build_overlay(graph, publication_graph, thread_graph)
    if graph["status"] == "complete" and overlay["status"] == "complete":
        cache.publish("graph", key, graph)
        cache.publish("overlay", key, overlay)
    report = build_report(graph, overlay, cache_hits=hits, cache_misses=misses)
    write_json(store, source, "atomic-source-construct-facts.json")
    write_json(store, local, "advanced-atomic-local-facts.json")
    write_json(store, graph, "bounded-atomic-communication-graph.json")
    write_json(store, overlay, "advanced-publication-protocol-overlay.json")
    write_json(store, report, "fence-rmw-publication-report.json")
    return report
