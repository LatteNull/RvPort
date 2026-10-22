"""End-to-end compile-only P4 orchestration over an exact P3 request."""

import json
from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, canonical, identity, read_document
from .effect_contracts import read_effect_document
from .effect_inputs import EffectInputs
from .execution import OutputStore
from .model_threads import model_threads
from .pipeline import write_json
from .publication_cache import PublicationCache, graph_key, local_key
from .publication_contracts import MODEL_ID, read_publication_document
from .publication_graph import build_publication_graph
from .publication_report import build_publication_report
from .publication_worker import analyze_publication_facts
from .thread_contracts import read_thread_document
from .source_assistance import load_source_assistance, relevant_dependency_slice
from .source_contracts import counts as source_counts, dependency as source_dependency, diagnostic as source_diagnostic, source_document


def _resolve(owner, value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (Path(owner).resolve().parent / path).resolve()


def _only(directory, pattern, code):
    paths = sorted(Path(directory).glob(pattern))
    if len(paths) != 1:
        raise AnalysisError(code, f"Expected exactly one {pattern} artifact in {directory}")
    return paths[0]


def _summaries(directory):
    values = [read_effect_document(path, "EffectSummary")
              for path in sorted(Path(directory).glob("*.json"))]
    if not values:
        raise AnalysisError("effect_summary_missing", "P3 produced no P2 effect summaries")
    return {item["context_id"]: item for item in values}


def _standard(argv):
    values = []
    for index, value in enumerate(argv):
        if value.startswith("-std="):
            values.append(value[5:])
        elif value == "-std" and index + 1 < len(argv):
            values.append(argv[index + 1])
    return values[0] if len(set(values)) == 1 else None


def _profiles(inputs, artifact_store):
    accepted = {"c": {"c11", "gnu11", "c17", "gnu17", "c18", "gnu18"},
                "c++": {"c++17", "gnu++17", "c++20", "gnu++20"}}
    result = {}
    for key, artifact in inputs.artifacts.items():
        context_id = artifact["context_id"]
        if context_id is None:
            result[key] = None
            continue
        path = Path(artifact_store).resolve() / "contexts" / f"{context_id}.json"
        try:
            manifest = read_document(path, "TUManifest")
        except (AnalysisError, OSError):
            external = artifact.get("toolchain", {})
            language, standard = external.get("language"), external.get("standard")
            family = external.get("producer_attested", {}).get("family")
            module = inputs.modules[key]
            result[key] = (f"{family}:{language}:{standard}:{module['target']}:{module['layout']}"
                           if family and standard in accepted.get(language, set()) else None)
            continue
        language = manifest["language"]
        standard = _standard(manifest["effective_argv"])
        description = str(manifest.get("production", {}).get("description", "")).lower()
        driver = Path(manifest["effective_argv"][0]).name.lower() if manifest["effective_argv"] else ""
        family = ("clang" if "clang" in driver or "clang" in description else
                  "gcc" if driver in {"gcc", "g++", "c++"} or "gcc" in description else None)
        module = inputs.modules[key]
        result[key] = (f"{family}:{language}:{standard}:{module['target']}:{module['layout']}"
                       if family and standard in accepted.get(language, set()) else None)
    return result


def _check_deadline(started, request, stage):
    if monotonic() - started > request["budgets"]["request_seconds"]:
        raise AnalysisError("request_timeout", f"P4 request exceeded its wall-clock budget after {stage}")


def detect_publication_risks(request_path, artifact_store, output, worker, source_evidence=None):
    started = monotonic()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "detect-publication-risks requires a fresh output directory")
    request = read_publication_document(request_path, "PublicationRiskRequest")
    thread_request_path = _resolve(request_path, request["thread_request"])
    thread_request = read_thread_document(thread_request_path, "ThreadAnalysisRequest")
    if request["model_id"] != MODEL_ID:
        raise AnalysisError("publication_model", "Unsupported publication model")
    scope_path = _resolve(thread_request_path, thread_request["scope"])
    inputs = EffectInputs.load(scope_path, artifact_store)
    assistance = load_source_assistance(source_evidence, scope_id=inputs.scope_id) if source_evidence else None
    staging = OutputStore(output)

    thread_output = output / "threads"
    thread_report = (model_threads(thread_request_path, artifact_store, thread_output, worker,
                                   source_evidence) if source_evidence else
                     model_threads(thread_request_path, artifact_store, thread_output, worker))
    thread_graph = read_thread_document(_only(thread_output / "graphs", "*.json", "thread_graph_missing"),
                                        "ThreadContextGraph")
    order_facts = {}
    for path in sorted((thread_output / "execution-order").glob("*.json")):
        value = read_thread_document(path, "ExecutionOrderFacts")
        order_facts[value["origin"]["artifact_key"]] = value
    summaries = _summaries(thread_output / "effects" / "summaries")
    _check_deadline(started, request, "P3 dependency construction")

    cache = PublicationCache(Path(artifact_store) / "derived" / "single-publication-risks-v1")
    origins = {key: {
        "artifact_key": key, "module_hash": inputs.artifacts[key]["sha256"],
        "facts_hash": identity(inputs.modules[key]),
        "extractor_version": inputs.modules[key]["protocol"]["extractor_version"],
        "llvm_version": inputs.modules[key]["protocol"]["llvm_version"],
        "profile": inputs.artifacts[key]["profile"],
    } for key in sorted(inputs.scope["members"])}
    local_facts, local_keys = {}, {}
    for key, origin in origins.items():
        local_keys[key] = local_key(origin, request["budgets"], request["model_id"])
        cached = cache.load("local", local_keys[key], "PublicationLocalFacts")
        if cached is not None:
            local_facts[key] = cached
    failures = []
    if len(local_facts) != len(origins):
        entries = analyze_publication_facts(inputs, worker, staging, budgets=request["budgets"])
        for key, entry in entries.items():
            if key in local_facts:
                continue
            if entry["result"] is None:
                failures.append({"artifact_key": key, **entry["error"]})
                continue
            local_facts[key] = entry["result"]
            cache.publish("local", local_keys[key], entry["result"])
    for key, value in sorted(local_facts.items()):
        write_json(staging, value, f"publication-local/{key}.json")
    if not set(thread_request_root["artifact_key"] for thread_request_root in thread_request["roots"]) <= set(local_facts):
        raise AnalysisError("publication_local_failed", str(failures))
    _check_deadline(started, request, "publication-local analysis")

    dependency_ids = [identity(value) for value in
                      [thread_graph, *order_facts.values(), *local_facts.values(),
                       *summaries.values(), request, thread_request,
                       *([] if assistance is None else assistance.values())]]
    key = graph_key(request, thread_graph, dependency_ids)
    graph = cache.load("graphs", key, "SinglePublicationProtocolGraph")
    if graph is None:
        graph = build_publication_graph(inputs, request, thread_graph, local_facts, summaries,
                                        _profiles(inputs, artifact_store), order_facts, assistance)
        if failures:
            graph["status"] = "partial"
        cache.publish("graphs", key, graph)
    _check_deadline(started, request, "protocol construction")
    report = build_publication_report(inputs, request, graph, local_facts, thread_report)
    payload = canonical({"graph": graph, "report": report}).encode()
    if len(payload) > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "P4 graph and report exceed the request output budget")
    write_json(staging, request, "request.json")
    write_json(staging, thread_request, "thread-request.json")
    write_json(staging, graph, f"graphs/{identity(graph)}.json")
    if assistance is not None:
        slices = [{"id": item["id"], **relevant_dependency_slice(item, thread_graph, assistance)}
                  for item in graph["protocols"]]
        slices.sort(key=lambda item: item["id"])
        incomplete = [item for item in slices if item["status"] != "complete"]
        frontier = [source_diagnostic(
            "candidate-source-dependency-incomplete",
            f"发布候选 {item['id']} 的 AST 相关依赖不完整",
            f"AST-relevant dependencies are incomplete for publication candidate {item['id']}",
            source={"candidate_id": item["id"], "missing": item["missing"]}) for item in incomplete]
        slice_document = source_document(
            "AstAssistedCandidateSlices", scope_id=inputs.scope_id,
            status="complete" if not incomplete else "partial",
            dependencies=sorted([
                source_dependency("AstAssistedAnalysisReport", inputs.scope_id, assistance["report"]),
                source_dependency("CanonicalObjectOverlay", inputs.scope_id, assistance["overlay"]),
                source_dependency("SinglePublicationProtocolGraph", identity(graph), graph),
            ], key=lambda item: (item["kind"], item["id"])), slices=slices,
            counts={"candidates": source_counts(len(slices), emitted=len(slices) - len(incomplete),
                                                 failed=len(incomplete)),
                    "downstream_consumption": source_counts(
                        len(graph["protocols"]), emitted=len(slices) - len(incomplete),
                        failed=len(incomplete))},
            diagnostics=frontier, frontier=frontier, semantic_digest=None)
        write_json(staging, slice_document, "source-assistance/candidate-slices.json")
    write_json(staging, report, "report.json")
    return report
