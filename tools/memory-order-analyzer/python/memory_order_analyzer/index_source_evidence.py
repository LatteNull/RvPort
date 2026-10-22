"""End-to-end AST-assisted indexing over explicit request dependencies."""

from pathlib import Path
from time import monotonic

from .contracts import AnalysisError, identity, read_document
from .execution import OutputStore
from .pipeline import write_json
from .source_binding import build_source_ir_binding
from .source_cache import SourceEvidenceCache, cache_key
from .source_contracts import counts, dependency, diagnostic, read_source_document, source_document
from .source_index import build_entity_index
from .source_overlay import build_overlay
from .source_worker import analyze_ir_binding, analyze_source


def _resolve(parent, value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (Path(parent).resolve().parent / path).resolve()


def _layer(status, planned, emitted, failed=0):
    return {"status": status, "counts": counts(planned, emitted + failed, emitted, failed=failed)}


def failed_source_report(code, detail, detail_en=None, *, scope_id="unavailable"):
    item = diagnostic(code, detail, detail_en or detail,
                      suggestion="修复请求或依赖后使用新的输出目录重试",
                      suggestion_en="Repair the request or dependencies and retry with a fresh output directory")
    return source_document("AstAssistedAnalysisReport", scope_id=scope_id, status="failed", exit_code=1,
                           dependencies=[], layers={}, outputs=[], cache={"hits": 0, "misses": 0},
                           diagnostics=[item], frontier=[item], semantic_digest=None)


def index_source_evidence(request_path, artifact_store, output, worker, *, runner=analyze_source,
                          ir_runner=analyze_ir_binding):
    started = monotonic()
    output = Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "index-source-evidence requires a fresh output directory")
    request = read_source_document(request_path, "AstAssistedAnalysisRequest")
    if len(request["source_requests"]) > request["budgets"]["translation_units"]:
        raise AnalysisError("tu_budget", "Source request plan exceeds translation-unit budget")
    source_requests = [read_source_document(_resolve(request_path, path), "SourceSemanticRequest") for path in request["source_requests"]]
    members = [item["physical_tu_id"] for item in source_requests]
    if members != sorted(set(members)):
        raise AnalysisError("scope_invalid", "Source requests must be unique and sorted by physical TU")
    store = OutputStore(output)
    cache = SourceEvidenceCache(Path(artifact_store) / "derived" / "ast-cross-tu-evidence-v1")
    facts, failures, hits, misses = {}, [], 0, 0
    for item in source_requests:
        key = cache_key("source-facts", item)
        cached = cache.load("source-facts", key, "SourceSemanticFacts")
        if cached is not None:
            if cached["profile_id"] != item["profile"]["profile_id"] or cached["source_digest"] != item["profile"]["source"]["sha256"]:
                raise AnalysisError("source_cache_invalid", "Cached source facts use stale profile/source identities")
            facts[item["physical_tu_id"]] = cached; hits += 1
            continue
        misses += 1
        try:
            with store.temporary() as temporary:
                value = runner(item, worker, temporary)
            cache.publish("source-facts", key, value)
            facts[item["physical_tu_id"]] = value
        except (AnalysisError, OSError, ValueError) as exc:
            failures.append(diagnostic("source-member-failed", f"源语义成员失败：{item['physical_tu_id']}",
                                       f"Source semantic member failed: {item['physical_tu_id']}",
                                       source={"physical_tu_id": item["physical_tu_id"], "reason": str(exc)}))
    if not facts:
        raise AnalysisError("source_unavailable", "All planned source semantic members failed")
    ir_requests = [read_source_document(_resolve(request_path, path), "LLVMSourceBindingRequest")
                   for path in request.get("ir_requests", [])]
    ir_artifacts = [item["artifact_key"] for item in ir_requests]
    if ir_artifacts != sorted(set(ir_artifacts)):
        raise AnalysisError("scope_invalid", "LLVM binding requests must be unique and sorted by artifact")
    source_identities = {(item["physical_tu_id"], item["profile"]["profile_id"]) for item in source_requests}
    if any((item["physical_tu_id"], item["profile_id"]) not in source_identities for item in ir_requests):
        raise AnalysisError("profile_conflict", "LLVM binding request does not match a scoped source profile/TU")
    ir_facts = {}
    for item in ir_requests:
        key = cache_key("llvm-binding-facts", item)
        cached = cache.load("llvm-binding-facts", key, "LLVMSourceBindingFacts")
        if cached is not None:
            ir_facts[item["artifact_key"]] = cached; hits += 1
            continue
        misses += 1
        try:
            with store.temporary() as temporary:
                value = ir_runner(item, worker, temporary)
            cache.publish("llvm-binding-facts", key, value)
            ir_facts[item["artifact_key"]] = value
        except (AnalysisError, OSError, ValueError) as exc:
            failures.append(diagnostic("ir-binding-member-failed", f"LLVM 绑定成员失败：{item['artifact_key']}",
                                       f"LLVM binding member failed: {item['artifact_key']}",
                                       source={"artifact_key": item["artifact_key"], "reason": str(exc)}))
    profiles = {item["physical_tu_id"]: item["profile"] for item in source_requests if item["physical_tu_id"] in facts}
    index_request = source_document("ProgramEntityIndexRequest", scope_id=request["scope_id"],
                                    members=sorted(facts), dependencies=sorted((dependency("SourceSemanticFacts", key, facts[key]) for key in facts), key=lambda item: (item["kind"], item["id"])), budgets=request["budgets"])
    index_key = cache_key("entity-index", index_request, [identity(facts[key]) for key in sorted(facts)])
    index = cache.load("entity-index", index_key, "ProgramEntityIndex", dependencies=index_request["dependencies"])
    if index is None:
        index = build_entity_index(index_request, facts, profiles); cache.publish("entity-index", index_key, index); misses += 1
    else:
        hits += 1
    modules = {}
    for reference in request["module_facts"]:
        value = read_document(Path(artifact_store) / "facts" / f"{reference['id']}.json", "ModuleFacts")
        if reference["digest"] != identity(value):
            raise AnalysisError("invalid_reference", f"ModuleFacts dependency changed: {reference['id']}")
        modules[reference["id"]] = value
    binding_request = source_document("SourceIRBindingRequest", scope_id=request["scope_id"],
                                      entity_index=dependency("ProgramEntityIndex", index["scope_id"], index),
                                      source_facts=sorted((dependency("SourceSemanticFacts", key, facts[key]) for key in facts), key=lambda item: (item["kind"], item["id"])),
                                      module_facts=request["module_facts"],
                                      ir_facts=sorted((dependency("LLVMSourceBindingFacts", key, ir_facts[key])
                                                       for key in ir_facts), key=lambda item: (item["kind"], item["id"])),
                                      budgets=request["budgets"])
    binding_key = cache_key("source-ir-binding", binding_request, [identity(index), *(identity(item) for item in facts.values()), *(identity(item) for item in modules.values()), *(identity(item) for item in ir_facts.values())])
    expected_binding_dependencies = sorted([
        binding_request["entity_index"], *binding_request["source_facts"],
        *binding_request["module_facts"], *binding_request["ir_facts"]],
        key=lambda item: (item["kind"], item["id"]))
    binding = cache.load("source-ir-binding", binding_key, "SourceIRBinding",
                         dependencies=expected_binding_dependencies)
    if binding is None:
        binding = build_source_ir_binding(binding_request, index, facts, modules, ir_facts); cache.publish("source-ir-binding", binding_key, binding); misses += 1
    else:
        hits += 1
    overlay_key = cache_key("canonical-overlay", {"scope_id": request["scope_id"], "budget": request["budgets"]["dependency_items"]}, [identity(index), identity(binding)])
    expected_overlay_dependencies = sorted([
        dependency("ProgramEntityIndex", index["scope_id"], index),
        dependency("SourceIRBinding", binding["scope_id"], binding)],
        key=lambda item: (item["kind"], item["id"]))
    overlay = cache.load("canonical-overlay", overlay_key, "CanonicalObjectOverlay",
                         dependencies=expected_overlay_dependencies)
    if overlay is None:
        overlay = build_overlay(request["scope_id"], index, binding, item_budget=request["budgets"]["dependency_items"]); cache.publish("canonical-overlay", overlay_key, overlay); misses += 1
    else:
        hits += 1
    elapsed = monotonic() - started
    if elapsed > request["budgets"]["request_seconds"]:
        failures.append(diagnostic("request-timeout", "AST 辅助请求超过时间预算", "AST-assisted request exceeded its time budget"))
    for key, value in sorted(facts.items()):
        write_json(store, value, f"source-facts/{key}.json")
    for key, value in sorted(ir_facts.items()):
        write_json(store, value, f"llvm-binding-facts/{key}.json")
    write_json(store, index, "entity-index.json"); write_json(store, binding, "source-ir-binding.json"); write_json(store, overlay, "canonical-object-overlay.json")
    outputs = sorted([dependency("ProgramEntityIndex", index["scope_id"], index), dependency("SourceIRBinding", binding["scope_id"], binding), dependency("CanonicalObjectOverlay", overlay["scope_id"], overlay)], key=lambda item: item["kind"])
    status = "complete" if not failures and all(value["status"] == "complete" for value in [*facts.values(), index, binding, overlay]) else "partial"
    layers = {
        "input_profile": _layer("complete" if len(facts) == len(source_requests) else "partial", len(source_requests), len(facts), len(source_requests) - len(facts)),
        "source_extraction": _layer("complete" if all(value["status"] == "complete" for value in facts.values()) and not failures else "partial", len(source_requests), len(facts), len(source_requests) - len(facts)),
        "llvm_binding_facts": _layer("complete" if len(ir_facts) == len(ir_requests) else "partial" if ir_requests else "not_run",
                                      len(ir_requests), len(ir_facts), len(ir_requests) - len(ir_facts)),
        "entity_resolution": {"status": index["status"], "counts": index["counts"]["groups"]},
        "entity_binding": {"status": binding["status"], "counts": binding["counts"]["bindings"]},
        "expression_binding": {"status": binding["status"], "counts": counts(len(binding["expression_bindings"]), emitted=len(binding["expression_bindings"]))},
        "overlay": {"status": overlay["status"], "counts": overlay["counts"]["objects"]},
        "downstream_consumption": _layer("not_run", 0, 0),
    }
    report = source_document("AstAssistedAnalysisReport", scope_id=request["scope_id"], status=status,
                             exit_code=0 if status == "complete" else 2,
                             dependencies=sorted([dependency("AstAssistedAnalysisRequest", request["scope_id"], request), *request["module_facts"]], key=lambda item: (item["kind"], item["id"])),
                             layers=layers, outputs=outputs, cache={"hits": hits, "misses": misses},
                             diagnostics=failures, frontier=[*failures, *index["frontier"], *binding["frontier"], *overlay["frontier"]], semantic_digest=None)
    if len(str(report).encode()) > request["budgets"]["request_output_bytes"]:
        raise AnalysisError("request_output_limit", "AST-assisted report exceeds output budget")
    write_json(store, request, "request.json"); write_json(store, report, "report.json")
    return report
