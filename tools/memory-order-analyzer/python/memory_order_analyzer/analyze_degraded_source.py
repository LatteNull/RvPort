"""Offline orchestration for source-first degraded analysis."""

from collections import defaultdict
import json
from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, file_hash, identity, read_document
from .degraded_analysis import (
    adapt_formal_assessments, build_availability, build_report, build_synchronization_gaps,
    generate_source_candidates, source_facts_usable,
)
from .degraded_cache import DegradedAnalysisCache, cache_key as degraded_cache_key
from .degraded_contracts import (
    degraded_document, dependency, diagnostic, expected_degraded_protocol, failure_record,
    read_degraded_document, stage_counts,
)
from .execution import OutputStore
from .pipeline import write_json
from .publication_contracts import read_publication_document
from .source_cache import SourceEvidenceCache, cache_key as source_cache_key
from .source_contracts import read_source_document
from .source_worker import analyze_ir_binding, analyze_source
from .thread_contracts import read_thread_document


def _resolve(parent, path):
    value = Path(path)
    return value.resolve() if value.is_absolute() else (Path(parent).resolve().parent / value).resolve()


def _read_hashed(parent, reference, reader, kind):
    path = _resolve(parent, reference["path"])
    if not path.is_file() or file_hash(path) != reference["sha256"]:
        raise AnalysisError("invalid_reference", f"Explicit dependency is missing or changed: {path}")
    return reader(path, kind)


def _failure(tu, stage, exc, limit):
    code = exc.code if isinstance(exc, AnalysisError) else "io_failed"
    detail = exc.detail if isinstance(exc, AnalysisError) else str(exc)
    return failure_record(tu, stage, code, detail, limit=limit)


def _formal_products(request_path, request):
    products = request["products"]
    thread_graph = (_read_hashed(request_path, products["thread_graph"], read_thread_document, "ThreadContextGraph")
                    if products["thread_graph"] else None)
    publication_graph = (_read_hashed(request_path, products["publication_graph"], read_publication_document, "SinglePublicationProtocolGraph")
                         if products["publication_graph"] else None)
    publication_report = (_read_hashed(request_path, products["publication_report"], read_publication_document, "PublicationRiskReport")
                          if products["publication_report"] else None)
    if publication_report and publication_graph:
        reference = publication_report.get("graph")
        if reference is None or reference["digest"] != identity(publication_graph):
            raise AnalysisError("invalid_reference", "Publication report and graph do not match")
    return thread_graph, publication_graph, publication_report


def failed_degraded_report(code, detail, detail_en=None, *, scope_id=None):
    item = diagnostic(code, f"降级源码分析失败：{detail}"[:4096],
                      f"Degraded source analysis failed: {detail_en or detail}"[:4096],
                      suggestion="修复显式请求或依赖后使用新的输出目录重试",
                      suggestion_en="Repair the explicit request or dependencies and retry in a fresh output directory")
    return degraded_document(
        "DegradedSourceAnalysisReport", scope_id=scope_id, request_hash=None, status="failed",
        mode="failed", exit_code=1, safety="not-established", stages={},
        mode_counts={"ast-ir": 0, "ir-only": 0, "ast-only": 0, "failed": 0},
        availabilities=[], source_candidates=[], synchronization_gaps=[], formal_assessments=[],
        dependencies=[], diagnostics=[item], frontier=[item], cache={"hits": 0, "misses": 0},
        semantic_digest=None)


def analyze_degraded_source(request_path, artifact_store, output, source_worker, ir_worker, *,
                            source_runner=analyze_source, ir_runner=analyze_ir_binding):
    started = monotonic()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "analyze-degraded-source requires a fresh output directory")
    request = read_degraded_document(request_path, "DegradedSourceAnalysisRequest")
    budgets = request["budgets"]
    store = OutputStore(output)
    source_cache = SourceEvidenceCache(Path(artifact_store) / "derived" / "ast-cross-tu-evidence-v1")
    cache = DegradedAnalysisCache(Path(artifact_store) / "derived" / "degraded-source-analysis-v1")

    source_requests = [_read_hashed(request_path, item, read_source_document, "SourceSemanticRequest")
                       for item in request["source_requests"]]
    if len(source_requests) > budgets["translation_units"]:
        raise AnalysisError("tu_budget", "Source request plan exceeds translation-unit budget")
    physical_ids = [item["physical_tu_id"] for item in source_requests]
    if physical_ids != sorted(set(physical_ids)):
        raise AnalysisError("scope_invalid", "Source requests must be unique and sorted by physical TU")
    source_by_tu, failures, hits, misses = {}, list(request["declared_failures"]), 0, 0
    for item in source_requests:
        key = source_cache_key("source-facts", item)
        cached = source_cache.load("source-facts", key, "SourceSemanticFacts")
        if cached is not None:
            source_by_tu[item["physical_tu_id"]] = cached; hits += 1
            continue
        misses += 1
        try:
            with store.temporary() as temporary:
                value = source_runner(item, source_worker, temporary)
            if not source_facts_usable(value):
                raise AnalysisError("frontend_invalid", "Source facts are unusable after fatal Clang diagnostics")
            source_cache.publish("source-facts", key, value)
            source_by_tu[item["physical_tu_id"]] = value
        except (AnalysisError, OSError, ValueError) as exc:
            failures.append(_failure(item["physical_tu_id"], "source", exc, budgets["diagnostic_bytes"]))

    ir_requests = [_read_hashed(request_path, item, read_source_document, "LLVMSourceBindingRequest")
                   for item in request["ir_requests"]]
    if [item["artifact_key"] for item in ir_requests] != sorted(set(item["artifact_key"] for item in ir_requests)):
        raise AnalysisError("scope_invalid", "IR requests must be unique and sorted by artifact")
    known_profiles = {(item["physical_tu_id"], item["profile"]["profile_id"]) for item in source_requests}
    if any((item["physical_tu_id"], item["profile_id"]) not in known_profiles for item in ir_requests):
        raise AnalysisError("profile_conflict", "IR request does not match a scoped source profile/TU")
    ir_by_tu, artifact_to_tu = defaultdict(list), {}
    for item in ir_requests:
        artifact_to_tu[item["artifact_key"]] = item["physical_tu_id"]
        key = source_cache_key("llvm-binding-facts", item)
        cached = source_cache.load("llvm-binding-facts", key, "LLVMSourceBindingFacts")
        if cached is not None:
            ir_by_tu[item["physical_tu_id"]].append(cached); hits += 1
            continue
        misses += 1
        try:
            with store.temporary() as temporary:
                value = ir_runner(item, ir_worker, temporary)
            source_cache.publish("llvm-binding-facts", key, value)
            ir_by_tu[item["physical_tu_id"]].append(value)
        except (AnalysisError, OSError, ValueError) as exc:
            failures.append(_failure(item["physical_tu_id"], "bc", exc, budgets["diagnostic_bytes"]))

    modules, module_refs_by_tu = {}, defaultdict(list)
    for reference in request["module_facts"]:
        value = read_document(Path(artifact_store) / "facts" / f"{reference['id']}.json", "ModuleFacts")
        if reference["digest"] != identity(value):
            raise AnalysisError("invalid_reference", f"ModuleFacts dependency changed: {reference['id']}")
        modules[reference["id"]] = value
        tu = artifact_to_tu.get(reference["id"])
        if tu:
            module_refs_by_tu[tu].append(reference)

    thread_graph, publication_graph, publication_report = _formal_products(request_path, request)
    del publication_report
    per_tu_failures = defaultdict(list)
    for item in failures:
        per_tu_failures[item["physical_tu_id"]].append(item)
    availabilities = []
    for source_request in source_requests:
        tu = source_request["physical_tu_id"]
        value = build_availability(request["scope_id"], source_request, source_by_tu.get(tu),
                                   ir_by_tu.get(tu, []), sorted(module_refs_by_tu.get(tu, []), key=lambda item: (item["kind"], item["id"])),
                                   per_tu_failures.get(tu, []))
        key = degraded_cache_key("availability", {"request": source_request, "failures": per_tu_failures.get(tu, [])}, [item["digest"] for item in value["dependencies"]])
        cached = cache.load("availability", key, "TUEvidenceAvailability", dependencies=value["dependencies"])
        if cached is None:
            cache.publish("availability", key, value); misses += 1
        else:
            value = cached; hits += 1
        availabilities.append(value)

    candidates, candidate_cut = [], False
    availability_by_tu = {item["physical_tu_id"]: item for item in availabilities}
    remaining = budgets["source_candidates"]
    for tu, facts in sorted(source_by_tu.items()):
        values, cut = generate_source_candidates(request["scope_id"], facts, availability_by_tu[tu], limit=remaining)
        candidates.extend(values); remaining -= len(values); candidate_cut |= cut
        if remaining == 0:
            candidate_cut = True; break
    gaps = build_synchronization_gaps(request["scope_id"], candidates, thread_graph, artifact_to_tu)
    assessments = publication_graph.get("assessments", []) if publication_graph else []
    formal = adapt_formal_assessments(assessments, availabilities, gaps, artifact_to_tu,
                                      slice_limit=budgets["slice_items"])
    if candidate_cut:
        failures.append(failure_record("scope", "source", "source_candidate_budget",
                                       "Source candidate enumeration exceeded its explicit budget",
                                       failure_class="worker-budget", stability="deterministic",
                                       limit=budgets["diagnostic_bytes"]))

    planned = len(source_requests)
    stage_values = {}
    for stage in ("source", "bc", "p1", "p2", "p3", "p4"):
        stage_failures = [item for item in failures if item["stage"] == stage and item["physical_tu_id"] in physical_ids]
        product_planned = 1 if request["products"].get(
            "thread_graph" if stage == "p3" else "publication_graph") else 0
        planned_stage = planned if stage in {"source", "bc", "p1"} else max(product_planned, len(stage_failures))
        budget_failures = sum(item["failure_class"] == "worker-budget" for item in stage_failures)
        completed = (sum(item["products"][next(i for i, state in enumerate(item["products"]) if state["stage"] == stage)]["status"] == "complete" for item in availabilities)
                     if stage in {"source", "bc", "p1"} else planned_stage - len(stage_failures))
        completed = max(0, min(planned_stage, completed))
        stage_values[stage] = stage_counts(planned_stage, completed, len(stage_failures) - budget_failures, budget_failures)
    stage_values["source_candidates"] = stage_counts(
        len(candidates) + (1 if candidate_cut else 0), len(candidates), 0, 1 if candidate_cut else 0)

    dependencies = [dependency("DegradedSourceAnalysisRequest", request["scope_id"], request), *request["module_facts"]]
    if thread_graph:
        dependencies.append(dependency("ThreadContextGraph", identity(thread_graph), thread_graph))
    if publication_graph:
        dependencies.append(dependency("SinglePublicationProtocolGraph", identity(publication_graph), publication_graph))
    dependencies = list({(item["kind"], item["id"]): item for item in dependencies}.values())
    report = build_report(request["scope_id"], request, availabilities, candidates, gaps, formal,
                          sorted(failures, key=lambda item: item["id"]), stage_values, dependencies,
                          cache_hits=hits, cache_misses=misses)
    if monotonic() - started > budgets["request_seconds"]:
        raise AnalysisError("request_timeout", "Degraded source analysis exceeded its request budget")
    if len(json.dumps(report, ensure_ascii=False).encode()) > budgets["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "Degraded source-analysis report exceeds its output budget")

    for item in source_by_tu.values():
        write_json(store, item, f"source-facts/{item['physical_tu_id']}.json")
    for values in ir_by_tu.values():
        for item in values:
            write_json(store, item, f"llvm-binding-facts/{item['artifact_key']}.json")
    for item in availabilities:
        write_json(store, item, f"availability/{item['physical_tu_id']}.json")
    for item in candidates:
        write_json(store, item, f"source-candidates/{item['id']}.json")
    for item in gaps:
        write_json(store, item, f"synchronization-gaps/{item['id']}.json")
    write_json(store, request, "request.json"); write_json(store, report, "report.json")
    return report
