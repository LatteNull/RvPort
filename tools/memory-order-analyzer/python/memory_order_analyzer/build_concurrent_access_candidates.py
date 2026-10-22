"""Offline orchestration for the additive R2 concurrent-access candidate graph."""

from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, identity
from .execution import OutputStore
from .pipeline import write_json
from .concurrent_access_analysis import (
    build_candidate_graph, build_execution_overlay, build_projection, build_protection_overlay,
    build_report, pair_accesses,
)
from .concurrent_access_cache import ConcurrentAccessCache, cache_key
from .concurrent_access_contracts import (
    concurrent_access_document, diagnostic, read_concurrent_access_document,
    validate_compatibility, validate_reference_closure,
)


def _read_kind(path, kind):
    if kind.startswith("ConcurrentAccess") or kind in {"ExecutionInstanceBindingOverlay", "AccessProtectionOverlay"}:
        return read_concurrent_access_document(path, kind)
    if kind in {"RootDrivenAnalysisPlan", "ExecutionRootIndex"}:
        from .root_contracts import read_root_document
        return read_root_document(path, kind)
    if kind in {"ThreadEntryRootOverlay", "ThreadEntrySiteIndex"}:
        from .thread_entry_contracts import read_thread_entry_document
        return read_thread_entry_document(path, kind)
    if kind == "EffectSummary":
        from .effect_contracts import read_effect_document
        return read_effect_document(path, kind)
    if kind == "ThreadContextGraph":
        from .thread_contracts import read_thread_document
        return read_thread_document(path, kind)
    if kind == "CppThreadLifecycleGraph":
        from .cpp_thread_contracts import read_cpp_thread_document
        return read_cpp_thread_document(path, kind)
    if kind == "CppRaiiSynchronizationGraph":
        from .cpp_raii_contracts import read_cpp_raii_document
        return read_cpp_raii_document(path, kind)
    if kind == "BoundedObjectProvenanceGraph":
        from .provenance_contracts import read_provenance_document
        return read_provenance_document(path, kind)
    raise AnalysisError("invalid_reference", f"Unsupported R2 dependency kind: {kind}")


def _resolve_dependency(store, reference):
    root = Path(store).resolve()
    path = (root / reference["path"]).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AnalysisError("invalid_reference", "R2 evidence path escapes the artifact store") from exc
    if not path.is_file():
        raise AnalysisError("invalid_reference",
                            f"R2 dependency is missing: {reference['kind']}:{reference['id']}")
    value = _read_kind(path, reference["kind"])
    if value.get("schema_version") != reference["schema_version"]:
        raise AnalysisError("invalid_reference", f"R2 dependency schema changed: {path}")
    if value.get("policy_id") != reference["producer"]:
        raise AnalysisError("invalid_reference", f"R2 dependency producer changed: {path}")
    if identity(value) != reference["digest"]:
        raise AnalysisError("invalid_reference", f"R2 dependency digest changed: {path}")
    return value


def _only(resolved, kind, *, required=False):
    values = [value for (candidate, _), value in resolved.items() if candidate == kind]
    if required and len(values) != 1:
        raise AnalysisError("invalid_reference", f"R2 requires exactly one {kind}")
    return values[0] if values else None


def _downgrade(value, item):
    fields = {key: content for key, content in value.items()
              if key not in {"schema_version", "kind", "analysis_version", "policy_id", "semantic_digest"}}
    fields["status"] = "partial"
    fields["frontier"] = [*fields.get("frontier", []), item]
    fields["diagnostics"] = [*fields.get("diagnostics", []), item]
    fields["semantic_digest"] = None
    return concurrent_access_document(value["kind"], **fields)


def build_concurrent_access_candidates(request_path, artifact_store, output, *, clock=monotonic):
    started = clock()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "build-concurrent-access-candidates requires a fresh output directory")
    request = read_concurrent_access_document(request_path, "ConcurrentAccessCandidateRequest")
    resolved = {(item["kind"], item["id"]): _resolve_dependency(artifact_store, item)
                for item in request["evidence"]}
    validate_compatibility(request, resolved.values())
    # Validate cycles among explicitly resolved R2-style dependencies without requiring the
    # artifact store to duplicate every transitive upstream object.
    synthetic = {("ConcurrentAccessCandidateRequest", request["scope_id"]): request, **resolved}
    validate_reference_closure(("ConcurrentAccessCandidateRequest", request["scope_id"]), synthetic)

    plan = _only(resolved, "RootDrivenAnalysisPlan", required=True)
    root_overlay = _only(resolved, "ThreadEntryRootOverlay", required=True)
    root_indexes = [value for (kind, _), value in resolved.items() if kind == "ExecutionRootIndex"]
    summaries = [value for (kind, _), value in resolved.items() if kind == "EffectSummary"]
    thread_graphs = [value for (kind, _), value in resolved.items() if kind == "ThreadContextGraph"]
    lifecycle_graphs = [value for (kind, _), value in resolved.items() if kind == "CppThreadLifecycleGraph"]
    raii_graphs = [value for (kind, _), value in resolved.items() if kind == "CppRaiiSynchronizationGraph"]
    provenance_graph = _only(resolved, "BoundedObjectProvenanceGraph")
    dependency_digests = [item["digest"] for item in request["evidence"]]
    cache = ConcurrentAccessCache(Path(artifact_store) / "derived")
    hits = misses = 0

    execution_key = cache_key("execution-instances", request, dependency_digests)
    execution = cache.load("execution-instances", execution_key, "ExecutionInstanceBindingOverlay")
    if execution is None:
        execution = build_execution_overlay(request, plan, root_overlay, root_indexes=root_indexes,
                                            thread_graphs=thread_graphs,
                                            lifecycle_graphs=lifecycle_graphs)
        if execution["status"] == "complete":
            cache.publish("execution-instances", execution_key, execution)
        misses += 1
    else:
        hits += 1

    projection_key = cache_key("projection", request, [*dependency_digests, identity(execution)])
    projection = cache.load("projection", projection_key, "ConcurrentAccessProjectionFacts")
    if projection is None:
        projection = build_projection(request, plan, root_overlay, summaries, execution,
                                      thread_graphs=thread_graphs,
                                      provenance_graph=provenance_graph)
        if projection["status"] == "complete":
            cache.publish("projection", projection_key, projection)
        misses += 1
    else:
        hits += 1

    if clock() - started > request["budgets"]["request_seconds"]:
        projection = _downgrade(projection, diagnostic(
            "request-time-budget-exhausted", "R2 请求时间预算已耗尽",
            "The R2 request-time budget is exhausted",
            source={"limit": request["budgets"]["request_seconds"]}))

    pairs = pair_accesses(request, projection, execution)
    protection_key = cache_key("protection", request,
                               [*dependency_digests, identity(projection), identity(execution),
                                identity(pairs)])
    protection = cache.load("protection", protection_key, "AccessProtectionOverlay")
    if protection is None:
        protection = build_protection_overlay(request, projection, execution, pairs,
                                              raii_graphs=raii_graphs)
        if protection["status"] == "complete":
            cache.publish("protection", protection_key, protection)
        misses += 1
    else:
        hits += 1

    graph_key = cache_key("graphs", request,
                          [*dependency_digests, identity(projection), identity(execution),
                           identity(protection), identity(pairs)])
    graph = cache.load("graphs", graph_key, "ConcurrentAccessCandidateGraph")
    if graph is None:
        graph = build_candidate_graph(request, projection, execution, protection, pairs)
        if graph["status"] == "complete":
            cache.publish("graphs", graph_key, graph)
        misses += 1
    else:
        hits += 1
    report = build_report(request, graph, hits=hits, misses=misses)
    report_bytes = len(str(report).encode("utf-8"))
    if report_bytes > request["budgets"]["request_output_bytes"]:
        graph = _downgrade(graph, diagnostic(
            "request-output-budget-exhausted", "R2 输出预算已耗尽；保留强制报告信封",
            "The R2 output budget is exhausted; the mandatory report envelope is retained",
            source={"hit": report_bytes, "limit": request["budgets"]["request_output_bytes"]}))
        report = build_report(request, graph, hits=hits, misses=misses)

    store = OutputStore(output)
    write_json(store, request, "request.json")
    write_json(store, projection, f"projection/{projection['semantic_digest']}.json")
    write_json(store, execution, "execution-instance-binding.json")
    write_json(store, protection, "access-protection.json")
    write_json(store, graph, "candidate-graph.json")
    write_json(store, report, "report.json")
    return report
