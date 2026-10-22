"""Offline orchestration for the additive A3 std::thread lifecycle model."""

from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, identity, read_document
from .cpp_thread_analysis import build_lifecycle_graph, build_lifecycle_report, build_local_facts
from .cpp_thread_cache import CppThreadCache, cache_key
from .cpp_thread_contracts import read_cpp_thread_document
from .execution import OutputStore
from .pipeline import write_json
from .source_contracts import read_source_document


DIRECTORIES = {
    "SourceSemanticFacts": ("source-facts",),
    "LLVMSourceBindingFacts": ("llvm-binding-facts",),
    "ProgramEntityIndex": ("entity-index",),
    "SourceIRBinding": ("source-ir-binding",),
    "ThreadContextGraph": ("graphs",),
    "ModuleFacts": ("facts",),
    "CppThreadLibraryProfile": ("cpp-thread-profiles", "profiles"),
    "CppThreadLocalFacts": ("cpp-thread-local", "local-facts"),
}


def _read_kind(path, kind):
    if kind.startswith("CppThread"):
        return read_cpp_thread_document(path, kind)
    if kind in {"SourceSemanticFacts", "LLVMSourceBindingFacts", "ProgramEntityIndex", "SourceIRBinding"}:
        return read_source_document(path, kind)
    if kind == "ModuleFacts":
        return read_document(path, kind)
    if kind == "ThreadContextGraph":
        from .thread_contracts import read_thread_document
        return read_thread_document(path, kind)
    raise AnalysisError("invalid_reference", f"Unsupported A3 dependency kind: {kind}")


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
            raise AnalysisError("invalid_reference", f"A3 dependency digest changed: {path}")
        return value
    raise AnalysisError("invalid_reference", f"A3 dependency is missing: {reference['kind']}:{reference['id']}")


def model_cpp_thread_lifecycle(request_path, artifact_store, output, source_worker=None, ir_worker=None):
    del source_worker, ir_worker  # Existing workers produced explicit dependencies before A3 composition.
    started = monotonic()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "model-cpp-thread-lifecycle requires a fresh output directory")
    request = read_cpp_thread_document(request_path, "CppThreadLifecycleRequest")
    if len(request["members"]) > request["budgets"]["translation_units"]:
        raise AnalysisError("tu_budget", "A3 request exceeds the translation-unit budget")
    store = OutputStore(output)
    cache = CppThreadCache(Path(artifact_store) / "derived")
    resolved = {(item["kind"], item["id"]): _resolve_dependency(artifact_store, item)
                for item in [*request["dependencies"], *request["library_profiles"]]}
    profiles = [resolved[(item["kind"], item["id"])] for item in request["library_profiles"]]
    standards = [item["cxx_standard"] for item in profiles]
    if len(standards) != len(set(standards)):
        raise AnalysisError("profile_conflict", "A3 requires exactly one library profile per C++ standard")
    profiles_by_standard = {item["cxx_standard"]: item for item in profiles}
    entity_index = next((value for (kind, _), value in resolved.items() if kind == "ProgramEntityIndex"), None)
    source_binding = next((value for (kind, _), value in resolved.items() if kind == "SourceIRBinding"), None)
    thread_graph = next((value for (kind, _), value in resolved.items() if kind == "ThreadContextGraph"), None)
    modules = {key: value for (kind, key), value in resolved.items() if kind == "ModuleFacts"}
    precomputed = {item["physical_tu_id"]: item for (kind, _), item in resolved.items()
                   if kind == "CppThreadLocalFacts"}
    local_facts, hits, misses = [], 0, 0
    for member in request["members"]:
        tu = member["physical_tu_id"]
        if tu in precomputed:
            value = precomputed[tu]
        else:
            source_ref = member["source_facts"]
            source = resolved.get((source_ref["kind"], source_ref["id"])) if source_ref else None
            profile = profiles_by_standard.get(member["standard"]) if member["language"] == "c++" else None
            key = cache_key("local-facts", {"member": member, "source": source_ref,
                                             "profile": profile and profile["profile_id"]},
                            [item["digest"] for item in request["dependencies"]])
            value = cache.load("local-facts", key, "CppThreadLocalFacts")
            if value is None:
                value = build_local_facts(request["scope_id"], member, source, profile,
                                          modules=modules, entity_index=entity_index,
                                          source_binding=source_binding)
                cache.publish("local-facts", key, value); misses += 1
            else:
                hits += 1
        local_facts.append(value)
        write_json(store, value, f"local-facts/{tu}.json")
    if monotonic() - started > request["budgets"]["request_seconds"]:
        raise AnalysisError("request_timeout", "A3 local analysis exceeded its request budget")
    graph_key = cache_key("graph", request, [identity(item) for item in local_facts] +
                          ([identity(thread_graph)] if thread_graph else []))
    graph = cache.load("graphs", graph_key, "CppThreadLifecycleGraph")
    if graph is None:
        graph = build_lifecycle_graph(request, local_facts, profiles, thread_graph=thread_graph)
        cache.publish("graphs", graph_key, graph); misses += 1
    else:
        hits += 1
    report = build_lifecycle_report(request, graph, profiles, hits=hits, misses=misses)
    if len(str(report).encode("utf-8")) > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "A3 report exceeds the request output budget")
    write_json(store, request, "request.json")
    write_json(store, graph, f"graphs/{graph['semantic_digest']}.json")
    write_json(store, report, "report.json")
    return report
