"""Offline orchestration for the additive A4 C++ RAII synchronization model."""

from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, identity, read_document
from .cpp_raii_analysis import build_local_facts, build_synchronization_graph, build_synchronization_report
from .cpp_raii_cache import CppRaiiCache, cache_key
from .cpp_raii_contracts import read_cpp_raii_document
from .execution import OutputStore
from .pipeline import write_json


DIRECTORIES = {
    "SourceSemanticFacts": ("source-facts",),
    "ModuleFacts": ("facts",),
    "ProgramEntityIndex": ("entity-index",),
    "SourceIRBinding": ("source-ir-binding",),
    "ThreadContextGraph": ("graphs",),
    "CppThreadLifecycleGraph": ("cpp-thread-graphs", "graphs"),
    "DegradedSourceReport": ("degraded-reports",),
    "SinglePublicationProtocolGraph": ("publication-graphs", "graphs"),
    "CppRaiiSynchronizationProfile": ("cpp-raii-profiles", "profiles"),
    "CppRaiiLocalFacts": ("cpp-raii-local", "local-facts"),
}


def _read_kind(path, kind):
    if kind.startswith("CppRaii"):
        return read_cpp_raii_document(path, kind)
    if kind in {"SourceSemanticFacts", "ProgramEntityIndex", "SourceIRBinding"}:
        from .source_contracts import read_source_document
        return read_source_document(path, kind)
    if kind == "ThreadContextGraph":
        from .thread_contracts import read_thread_document
        return read_thread_document(path, kind)
    if kind == "CppThreadLifecycleGraph":
        from .cpp_thread_contracts import read_cpp_thread_document
        return read_cpp_thread_document(path, kind)
    if kind.startswith("Degraded"):
        from .degraded_contracts import read_degraded_document
        return read_degraded_document(path, kind)
    if kind.startswith("SinglePublication"):
        from .publication_contracts import read_publication_document
        return read_publication_document(path, kind)
    if kind == "ModuleFacts":
        return read_document(path, kind)
    raise AnalysisError("invalid_reference", f"Unsupported A4 dependency kind: {kind}")


def _resolve_dependency(store, reference):
    store = Path(store).resolve()
    candidates = [store / directory / f"{reference['id']}.json"
                  for directory in DIRECTORIES.get(reference["kind"], ())]
    candidates.append(store / f"{reference['id']}.json")
    for path in candidates:
        if not path.is_file():
            continue
        value = _read_kind(path, reference["kind"])
        if reference["digest"] != identity(value):
            raise AnalysisError("invalid_reference", f"A4 dependency digest changed: {path}")
        return value
    raise AnalysisError("invalid_reference", f"A4 dependency is missing: {reference['kind']}:{reference['id']}")


def model_cpp_raii_synchronization(request_path, artifact_store, output,
                                   source_worker=None, ir_worker=None):
    del source_worker, ir_worker
    started = monotonic()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "model-cpp-raii-synchronization requires a fresh output directory")
    request = read_cpp_raii_document(request_path, "CppRaiiSynchronizationRequest")
    if len(request["members"]) > request["budgets"]["translation_units"]:
        raise AnalysisError("tu_budget", "A4 request exceeds the translation-unit budget")
    store = OutputStore(output)
    cache = CppRaiiCache(Path(artifact_store) / "derived")
    references = [*request["dependencies"], *request["synchronization_profiles"]]
    resolved = {(item["kind"], item["id"]): _resolve_dependency(artifact_store, item)
                for item in references}
    profiles = [resolved[(item["kind"], item["id"])] for item in request["synchronization_profiles"]]
    profile_by_standard = {}
    for profile in profiles:
        standard = profile["cxx_standard"]
        if standard in profile_by_standard:
            raise AnalysisError("profile_conflict", "A4 requires exactly one synchronization profile per C++ standard")
        profile_by_standard[standard] = profile
    modules = {key: value for (kind, key), value in resolved.items() if kind == "ModuleFacts"}
    precomputed = {item["physical_tu_id"]: item for (kind, _), item in resolved.items()
                   if kind == "CppRaiiLocalFacts"}
    local_facts, hits, misses = [], 0, 0
    dependency_digests = [item["digest"] for item in references]
    for member in request["members"]:
        tu = member["physical_tu_id"]
        if tu in precomputed:
            value = precomputed[tu]
        else:
            source_ref = member["source_facts"]
            source = resolved.get((source_ref["kind"], source_ref["id"])) if source_ref else None
            profile = profile_by_standard.get(member["standard"]) if member["language"] == "c++" else None
            key = cache_key("local-facts", {"member": member, "source": source_ref,
                                             "profile": profile and profile["profile_id"],
                                             "budgets": request["budgets"]}, dependency_digests)
            value = cache.load("local-facts", key, "CppRaiiLocalFacts")
            if value is None:
                value = build_local_facts(request["scope_id"], member, source, profile, modules=modules)
                if value["status"] == "complete":
                    cache.publish("local-facts", key, value)
                misses += 1
            else:
                hits += 1
        local_facts.append(value)
        write_json(store, value, f"local-facts/{tu}.json")
    if monotonic() - started > request["budgets"]["request_seconds"]:
        raise AnalysisError("request_timeout", "A4 local analysis exceeded its request budget")
    def first(kind):
        return next((value for (candidate, _), value in resolved.items() if candidate == kind), None)
    adapters = {
        "thread_graph": first("ThreadContextGraph"),
        "lifecycle_graph": first("CppThreadLifecycleGraph"),
        "degraded_report": first("DegradedSourceReport"),
        "publication_graph": first("SinglePublicationProtocolGraph"),
    }
    key = cache_key("graph", request, [identity(item) for item in local_facts] +
                    [identity(item) for item in adapters.values() if item])
    graph = cache.load("graphs", key, "CppRaiiSynchronizationGraph")
    if graph is None:
        graph = build_synchronization_graph(request, local_facts, profiles, **adapters)
        if graph["status"] == "complete":
            cache.publish("graphs", key, graph)
        misses += 1
    else:
        hits += 1
    report = build_synchronization_report(request, graph, profiles, hits=hits, misses=misses)
    if len(str(report).encode("utf-8")) > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "A4 report exceeds the request output budget")
    write_json(store, request, "request.json")
    write_json(store, graph, f"graphs/{graph['semantic_digest']}.json")
    write_json(store, report, "report.json")
    return report
