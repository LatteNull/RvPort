"""Bounded transport and orchestration for A5 object provenance."""

from copy import deepcopy
import json
from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, canonical, file_hash, identity
from .execution import OutputStore, run
from .object_provenance import (
    build_graph, build_report, compose_evidence, exact_adapter, failed_report,
)
from .pipeline import write_json
from .provenance_cache import ProvenanceCache, cache_key
from .provenance_contracts import (
    diagnostic, expected_provenance_protocol, read_provenance_document, semantic_digest,
    validate_provenance_document,
)


_DEPENDENCY_DIRECTORIES = {
    "ProgramEntityIndex": ("entity-index",),
    "SourceIRBinding": ("source-ir-binding",),
    "EffectSummary": ("summaries",),
}


def _read_dependency(path, kind):
    if kind in {"ProgramEntityIndex", "SourceIRBinding"}:
        from .source_contracts import read_source_document
        return read_source_document(path, kind)
    if kind == "EffectSummary":
        from .effect_contracts import read_effect_document
        return read_effect_document(path, kind)
    raise AnalysisError("invalid_reference", f"Unsupported A5 dependency kind: {kind}")


def _resolve_dependency(store, reference):
    """Resolve only explicitly referenced A1/P2 evidence and recheck its digest."""
    root = Path(store).resolve()
    candidates = [root / directory / f"{reference['id']}.json"
                  for directory in _DEPENDENCY_DIRECTORIES.get(reference["kind"], ())]
    candidates.append(root / f"{reference['id']}.json")
    for path in candidates:
        if not path.is_file():
            continue
        value = _read_dependency(path, reference["kind"])
        if identity(value) != reference["digest"]:
            raise AnalysisError("invalid_reference", f"A5 dependency digest changed: {path}")
        return value
    raise AnalysisError("invalid_reference",
                        f"A5 dependency is missing: {reference['kind']}:{reference['id']}")


def check_worker(worker, cwd, *, runner=run):
    result = runner([str(worker), "--object-provenance-protocol"], str(cwd), timeout=10)
    try:
        valid = (result["status"] == "completed" and
                 canonical(json.loads(result["stdout"])) == canonical(expected_provenance_protocol()))
    except (ValueError, KeyError, TypeError, RecursionError):
        valid = False
    if not valid:
        raise AnalysisError("provenance_worker_protocol", "A5 worker LLVM/Clang/policy mismatch; rebuild the worker")
    return expected_provenance_protocol()


def _run_request(request, worker, directory, option, kind, *, runner=run):
    check_worker(worker, directory, runner=runner)
    name = f"a5-{kind}-{identity(request)}.json"
    path = Path(directory) / name
    path.write_text(canonical(request), encoding="utf-8")
    try:
        result = runner([str(worker), option, str(path)], str(directory),
                        timeout=request["budgets"]["worker_seconds"],
                        log_limit=request["budgets"]["worker_output_bytes"])
    finally:
        path.unlink(missing_ok=True)
    if result["status"] != "completed":
        raise AnalysisError(result.get("code") or "provenance_worker_failed",
                            "A5 worker failed: " + result.get("stderr", ""))
    try:
        value = json.loads(result["stdout"])
    except (ValueError, TypeError, RecursionError) as exc:
        raise AnalysisError("provenance_worker_output", "Invalid A5 worker JSON") from exc
    return value


def analyze_source_paths(request, worker, directory, *, runner=run):
    validate_provenance_document(request, "SourceObjectPathRequest")
    source = request["profile"]["source"]
    if file_hash(source["path"]) != source["sha256"]:
        raise AnalysisError("source_digest", "A5 source is missing or changed")
    value = _run_request(request, worker, directory, "--object-path-request",
                         "source-path", runner=runner)
    value["semantic_digest"] = None
    value["semantic_digest"] = semantic_digest(value)
    facts = validate_provenance_document(value, "SourceObjectPathFacts")
    expected = (request["profile"]["profile_id"], request["physical_tu_id"], source["sha256"])
    actual = (facts["profile_id"], facts["physical_tu_id"], facts["source_digest"])
    if actual != expected:
        raise AnalysisError("source_worker_identity", "A5 source result does not match its request")
    return facts


def _normalize_worker_objects(value):
    for entry in value.get("values", []):
        candidates = entry["domain"]["candidates"]
        for item in candidates:
            storage = item["object"]["storage"]
            if storage.get("kind") == "unknown":
                item["opposed"] = sorted(set(item.get("opposed", ())) | {"llvm-unknown-storage-kind"})
            storage["id"] = identity({key: field for key, field in storage.items() if key != "id"})
            obj = item["object"]
            obj["id"] = identity({"storage": obj["storage"], "path": obj["path"],
                                  "byte_range": obj["byte_range"]})
            item["guards"] = sorted(set(item["guards"]))
            item["proof"] = sorted(set(item["proof"]))
            item["opposed"] = sorted(set(item["opposed"]))
            item["dependencies"] = sorted(item["dependencies"], key=lambda dep: (dep["kind"], dep["id"]))
        candidates.sort(key=lambda item: item["object"]["id"])
        if entry["domain"]["state"] == "must" and (len(candidates) != 1 or candidates[0]["opposed"]):
            entry["domain"]["state"] = "may" if candidates else "unknown"
            entry["domain"]["reason"] = None if candidates else "worker-candidate-empty"
    value["values"].sort(key=lambda item: item["id"])
    return value


def analyze_llvm_provenance(request, worker, directory, *, runner=run):
    validate_provenance_document(request, "LLVMObjectProvenanceRequest")
    bitcode = request["bitcode"]
    if file_hash(bitcode["path"]) != bitcode["sha256"]:
        raise AnalysisError("bitcode_digest", "A5 bitcode is missing or changed")
    value = _run_request(request, worker, directory, "--object-provenance-request",
                         "llvm", runner=runner)
    _normalize_worker_objects(value)
    value["semantic_digest"] = None
    value["semantic_digest"] = semantic_digest(value)
    facts = validate_provenance_document(value, "LLVMObjectProvenanceFacts")
    expected = (request["artifact_key"], request["profile_id"], request["physical_tu_id"], bitcode["sha256"])
    actual = (facts["artifact_key"], facts["profile_id"], facts["physical_tu_id"], facts["bitcode_digest"])
    if actual != expected:
        raise AnalysisError("llvm_worker_identity", "A5 LLVM result does not match its request")
    return facts


def analyze_object_provenance(request_path, artifact_store, output, source_worker, ir_worker,
                              *, runner=run, clock=monotonic):
    started = clock()
    request = read_provenance_document(request_path, "BoundedObjectProvenanceRequest")
    store, cache = OutputStore(output), ProvenanceCache(artifact_store)
    resolved = [_resolve_dependency(artifact_store, item) for item in request["dependencies"]]
    entity_indexes = [item for item in resolved if item["kind"] == "ProgramEntityIndex"]
    source_bindings = [item for item in resolved if item["kind"] == "SourceIRBinding"]
    effect_summaries = [item for item in resolved if item["kind"] == "EffectSummary"]
    source_facts, llvm_facts, failures, hits, misses = [], [], [], 0, 0
    for member in request["members"]:
        for field, kind, worker, analyze in (
                ("source_request", "SourceObjectPathFacts", source_worker, analyze_source_paths),
                ("llvm_request", "LLVMObjectProvenanceFacts", ir_worker, analyze_llvm_provenance)):
            if member[field] is None:
                continue
            try:
                subrequest = read_provenance_document(
                    member[field], "SourceObjectPathRequest" if field == "source_request" else
                    "LLVMObjectProvenanceRequest")
                key = cache_key("source" if field == "source_request" else "llvm", subrequest)
                value = cache.load("facts", key, kind)
                if value is None:
                    value = analyze(subrequest, worker, output, runner=runner)
                    if value["status"] != "failed":
                        cache.publish("facts", key, value)
                    misses += 1
                else:
                    hits += 1
                (source_facts if field == "source_request" else llvm_facts).append(value)
            except (AnalysisError, OSError, ValueError) as exc:
                failures.append({
                    "physical_tu_id": member["physical_tu_id"],
                    "layer": "source" if field == "source_request" else "llvm",
                    "diagnostic": diagnostic(
                        "object-provenance-member-failed",
                        f"翻译单元 {member['physical_tu_id']} 的 {field} 阶段失败",
                        f"The {field} stage failed for translation unit {member['physical_tu_id']}",
                        suggestion="修复该翻译单元输入后重试；现有单侧证据仅用于 partial/unknown",
                        suggestion_en="Repair the translation-unit input and retry; remaining one-sided evidence is partial/unknown",
                        source={"physical_tu_id": member["physical_tu_id"],
                                "layer": "source" if field == "source_request" else "llvm",
                                "reason": str(exc)}),
                })
    domains, relations, frontier = compose_evidence(
        source_facts, llvm_facts, request["budgets"], scope_id=request["scope_id"],
        entity_indexes=entity_indexes, source_bindings=source_bindings,
        effect_summaries=effect_summaries)
    frontier.extend(item["diagnostic"] for item in failures)
    elapsed = clock() - started
    if elapsed > request["budgets"]["request_seconds"]:
        frontier.append(diagnostic(
            "object-provenance-request-time-budget-exhausted",
            "对象来源请求时间预算已耗尽", "Object-provenance request time budget exhausted",
            suggestion="提高 request_seconds 预算或缩小显式 scope 后重试",
            suggestion_en="Increase request_seconds or retry with a smaller explicit scope",
            source={"hit_seconds": elapsed, "limit_seconds": request["budgets"]["request_seconds"]}))
    adapters = []
    for key, domain in domains:
        if "mutex" in key:
            adapters.append(exact_adapter(key, domain, consumer="A4"))
        if "payload" in key or "flag" in key:
            adapters.append(exact_adapter(key, domain, consumer="P4"))
    graph_key = cache_key(
        "graph", request,
        [item["semantic_digest"] for item in [*source_facts, *llvm_facts]] +
        [identity(item) for item in failures])
    graph = cache.load("graphs", graph_key, "BoundedObjectProvenanceGraph")
    if graph is None:
        graph = build_graph(request, source_facts, llvm_facts, domains=domains,
                            relations=relations, adapters=adapters, extra_frontier=frontier,
                            failures=failures)
        if graph["status"] != "failed":
            cache.publish("graphs", graph_key, graph)
        misses += 1
    else:
        hits += 1
    report = build_report(request, graph, hits=hits, misses=misses)
    if len(canonical(report).encode("utf-8")) > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "A5 report exceeds request_output_bytes")
    write_json(store, request, "request.json")
    for facts in source_facts:
        write_json(store, facts, f"source-path-facts/{facts['physical_tu_id']}.json")
    for facts in llvm_facts:
        write_json(store, facts, f"llvm-provenance-facts/{facts['physical_tu_id']}.json")
    write_json(store, graph, f"graphs/{graph['semantic_digest']}.json")
    write_json(store, report, "report.json")
    return report
