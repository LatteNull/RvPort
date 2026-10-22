"""Bundle preflight, stage registry, and deterministic per-scope DAG planning."""

from copy import deepcopy
from pathlib import Path

from .contracts import AnalysisError, file_hash, identity
from .external_bitcode_contracts import read_external_document
from .external_bitcode_ingestion import safe_bundle_file
from .unified_contracts import diagnostic, unified_document


STAGES = (
    {"name": "ingest", "version": "external-bitcode-v1", "inputs": ("ExternalBitcodeBundleManifest",),
     "outputs": ("BCArtifact", "ModuleFacts"), "dependencies": (), "budget": "artifact_bytes",
     "cache": "complete-only", "failure": "isolate"},
    {"name": "source-evidence", "version": "source-evidence-v1", "inputs": ("SourceSemanticRequest",),
     "outputs": ("SourceSemanticFacts", "SourceIRBinding"), "dependencies": (), "budget": "stage_output_bytes",
     "cache": "complete-only", "failure": "isolate"},
    {"name": "evidence-availability", "version": "degraded-source-v1",
     "inputs": ("BCArtifact", "ModuleFacts", "SourceSemanticFacts"),
     "outputs": ("DegradedSourceAnalysisReport",), "dependencies": ("ingest", "source-evidence"),
     "budget": "translation_units", "cache": "complete-only", "failure": "isolate"},
    {"name": "execution-root", "version": "execution-root-v1",
     "inputs": ("ModuleFacts", "SourceSemanticFacts", "SourceIRBinding"),
     "outputs": ("ExecutionRootIndex", "RootDrivenAnalysisPlan"),
     "dependencies": ("evidence-availability",), "budget": "worklist_items",
     "cache": "complete-only", "failure": "stop-scope"},
    {"name": "thread-entry", "version": "thread-entry-v1",
     "inputs": ("ExecutionRootIndex", "SourceSemanticFacts", "ModuleFacts"),
     "outputs": ("ThreadEntrySiteIndex", "ThreadEntryRootOverlay"),
     "dependencies": ("execution-root",), "budget": "worklist_items",
     "cache": "complete-only", "failure": "isolate"},
    {"name": "demand-analysis", "version": "demand-driven-v1",
     "inputs": ("RootDrivenAnalysisPlan", "ThreadEntryRootOverlay", "ModuleFacts"),
     "outputs": ("AnalysisDemandGraph", "FunctionSemanticFacts", "FunctionEffectFacts", "FunctionThreadFacts"),
     "dependencies": ("execution-root", "thread-entry"), "budget": "worklist_items",
     "cache": "complete-only", "failure": "isolate"},
    {"name": "effect-summary", "version": "effect-summary-v1",
     "inputs": ("FunctionSemanticFacts", "FunctionEffectFacts"), "outputs": ("EffectSummary",),
     "dependencies": ("demand-analysis",), "budget": "worklist_items",
     "cache": "complete-only", "failure": "isolate"},
    {"name": "thread-context", "version": "thread-context-v1",
     "inputs": ("FunctionThreadFacts", "EffectSummary"), "outputs": ("ThreadContextGraph",),
     "dependencies": ("effect-summary",), "budget": "worklist_items",
     "cache": "complete-only", "failure": "isolate"},
    {"name": "cpp-thread-lifecycle", "version": "cpp-thread-lifecycle-v1",
     "inputs": ("ThreadEntryRootOverlay", "ThreadContextGraph"), "outputs": ("CppThreadLifecycleOverlay",),
     "dependencies": ("thread-entry", "thread-context"), "budget": "worklist_items",
     "cache": "complete-only", "failure": "isolate", "language": "c++"},
    {"name": "raii-synchronization", "version": "cpp-raii-v1",
     "inputs": ("ThreadContextGraph", "CppThreadLifecycleOverlay"), "outputs": ("RaiiSynchronizationOverlay",),
     "dependencies": ("thread-context", "cpp-thread-lifecycle"), "budget": "worklist_items",
     "cache": "complete-only", "failure": "isolate", "language": "c++"},
    {"name": "object-provenance", "version": "bounded-object-provenance-v1",
     "inputs": ("FunctionSemanticFacts", "SourceSemanticFacts"), "outputs": ("BoundedObjectProvenanceGraph",),
     "dependencies": ("demand-analysis",), "budget": "worklist_items",
     "cache": "complete-only", "failure": "isolate"},
    {"name": "concurrent-access", "version": "concurrent-access-v1",
     "inputs": ("EffectSummary", "ThreadContextGraph", "BoundedObjectProvenanceGraph", "RaiiSynchronizationOverlay"),
     "outputs": ("ConcurrentAccessCandidateGraph",),
     "dependencies": ("effect-summary", "thread-context", "raii-synchronization", "object-provenance"),
     "budget": "worklist_items", "cache": "complete-only", "failure": "isolate"},
    {"name": "publication-risk", "version": "publication-risk-v1",
     "inputs": ("ConcurrentAccessCandidateGraph", "ThreadContextGraph"), "outputs": ("PublicationRiskReport",),
     "dependencies": ("concurrent-access",), "budget": "findings",
     "cache": "complete-only", "failure": "isolate"},
    {"name": "advanced-atomic", "version": "fence-rmw-publication-v1",
     "inputs": ("ConcurrentAccessCandidateGraph", "PublicationRiskReport"),
     "outputs": ("FenceRmwPublicationReport",), "dependencies": ("concurrent-access", "publication-risk"),
     "budget": "findings", "cache": "complete-only", "failure": "isolate"},
    {"name": "projection", "version": "memory-order-finding-v2",
     "inputs": ("PublicationRiskReport", "FenceRmwPublicationReport", "ConcurrentAccessCandidateGraph"),
     "outputs": ("MemoryOrderFindingProjection",),
     "dependencies": ("publication-risk", "advanced-atomic"), "budget": "findings",
     "cache": "disabled", "failure": "stop-scope"},
)


def stage_registry():
    return deepcopy(STAGES)


def _record_reference(root, reference):
    path = safe_bundle_file(root, reference["path"])
    if file_hash(path) != reference["sha256"]:
        raise AnalysisError("hash_mismatch", f"External record digest mismatch: {reference['path']}")
    return read_external_document(path, "ExternalBitcodeArtifactRecord")


def preflight_bundle(request, request_root):
    """Resolve declared inputs only; never discover files or invoke a build tool."""
    manifest_path = safe_bundle_file(request_root, request["bundle"]["path"])
    if file_hash(manifest_path) != request["bundle"]["sha256"]:
        raise AnalysisError("hash_mismatch", "Unified request bundle digest mismatch")
    manifest = read_external_document(manifest_path, "ExternalBitcodeBundleManifest")
    records = [_record_reference(manifest_path.parent, item) for item in manifest["records"]]
    by_id = {item["record_id"]: item for item in records}
    if len(by_id) != len(records):
        raise AnalysisError("invalid_reference", "External bundle contains duplicate record IDs")
    available = {item["target_id"]: item for item in manifest["scopes"]}
    selection = request["scope_selection"]
    selected_ids = sorted(available) if selection["mode"] == "all" else selection["scope_ids"]
    missing = sorted(set(selected_ids) - set(available))
    if missing:
        raise AnalysisError("invalid_reference", f"Requested scopes are absent from bundle: {missing}")
    if len(selected_ids) > request["budgets"]["scopes"]:
        raise AnalysisError("budget_exceeded", "Selected scope count exceeds the request budget")
    selected = []
    planned_tus = 0
    for identifier in selected_ids:
        scope = deepcopy(available[identifier])
        scope_records = [by_id[item] for item in scope["record_ids"]]
        unsupported_targets = sorted({item["target"]["triple"] for item in scope_records
                                      if any(marker in item["target"]["triple"].lower()
                                             for marker in ("windows", "mingw", "msvc"))})
        if unsupported_targets:
            raise AnalysisError("target_unsupported", f"Windows/MSVC targets are unsupported: {unsupported_targets}")
        if any(item["target"]["triple"] != scope["target_triple"] for item in scope_records):
            raise AnalysisError("profile_conflict", f"Scope target differs from member record: {identifier}")
        configurations = {(item["target"]["data_layout"], str(sorted(item["target"]["abi"].items())))
                          for item in scope_records}
        if len(configurations) != 1:
            raise AnalysisError("profile_conflict", f"Scope mixes DataLayout or ABI configurations: {identifier}")
        profiles = {(item["language"], item["standard"], item["target"]["data_layout"],
                     item["target"]["abi"].get("name"), item["producer"]["llvm_version"])
                    for item in scope_records}
        scope["records"] = scope_records
        scope["profiles"] = sorted((list(item) for item in profiles), key=str)
        selected.append(scope)
        planned_tus += len(scope_records)
    if planned_tus > request["budgets"]["translation_units"]:
        raise AnalysisError("budget_exceeded", "Selected translation units exceed the request budget")
    # resolved_path is execution-only state and must never pollute the versioned request.
    source_refs = {item["record_id"]: deepcopy(item) for item in request["source_requests"]}
    unknown_sources = sorted(set(source_refs) - by_id.keys())
    if unknown_sources:
        raise AnalysisError("invalid_reference", f"Source request refers to an unknown record: {unknown_sources}")
    for item in source_refs.values():
        path = safe_bundle_file(request_root, item["path"])
        if file_hash(path) != item["sha256"]:
            raise AnalysisError("hash_mismatch", f"Source request digest mismatch: {item['record_id']}")
        item["resolved_path"] = path
    return {"manifest": manifest, "manifest_path": manifest_path, "records": by_id,
            "scopes": selected, "source_requests": source_refs}


def preliminary_tu_modes(request, bundle_index, scope):
    result = []
    for record in scope["records"]:
        has_ir = record["status"] == "produced"
        has_ast = (request["source_assistance"] != "disabled" and
                   record["record_id"] in bundle_index["source_requests"])
        mode = "ast-ir" if has_ast and has_ir else "ast-only" if has_ast else "ir-only" if has_ir else "failed"
        missing = [name for name, present in (("ast", has_ast), ("ir", has_ir)) if not present]
        result.append({"record_id": record["record_id"], "physical_tu_id": record["physical_tu_id"],
                       "mode": mode, "status": "complete" if mode == "ast-ir" else "failed" if mode == "failed" else "partial",
                       "available_evidence": [name for name in ("ast", "ir") if name not in missing],
                       "missing_evidence": missing})
    return sorted(result, key=lambda item: item["record_id"])


def _stage_id(request_digest, bundle_id, scope_id, descriptor):
    return identity({"request": request_digest, "bundle": bundle_id, "scope": scope_id,
                     "stage": descriptor["name"], "version": descriptor["version"],
                     "inputs": descriptor["inputs"], "outputs": descriptor["outputs"]})


def build_plan(request, bundle_index):
    stages, frontier = [], []
    bundle_id = bundle_index["manifest"]["bundle_id"]
    request_digest = request["semantic_digest"]
    for scope in bundle_index["scopes"]:
        languages = {item["language"] for item in scope["records"]}
        identifiers = {item["name"]: _stage_id(request_digest, bundle_id, scope["target_id"], item)
                       for item in STAGES}
        for descriptor in STAGES:
            applicable = descriptor.get("language") is None or descriptor["language"] in languages
            dependencies = sorted(identifiers[item] for item in descriptor["dependencies"])
            stages.append({"id": identifiers[descriptor["name"]], "scope_id": scope["target_id"],
                           "stage": descriptor["name"], "version": descriptor["version"],
                           "producer": f"org.rvport.memory-order-analyzer.{descriptor['name']}",
                           "inputs": sorted(descriptor["inputs"]), "outputs": sorted(descriptor["outputs"]),
                           "dependencies": dependencies,
                           "status": "planned" if applicable else "skipped-not-applicable",
                           "applicability": "applicable" if applicable else "scope-has-no-cpp-tu",
                           "budget_key": descriptor["budget"], "cache_policy": descriptor["cache"],
                           "failure_policy": descriptor["failure"]})
        if not scope["closed"] or scope["external_boundaries"]:
            frontier.append(diagnostic("open_scope", "Scope 未闭合，分析完整性受限",
                                       "Scope is open; analysis completeness is limited",
                                       stage="ingest", scope_id=scope["target_id"],
                                       references=scope["record_ids"]))
    stages.sort(key=lambda item: item["id"])
    edges = sorted(({"from": dependency, "to": item["id"]}
                    for item in stages for dependency in item["dependencies"]),
                   key=lambda item: (item["from"], item["to"]))
    if len(stages) > request["budgets"]["stages"]:
        raise AnalysisError("budget_exceeded", "Planned stages exceed the stage budget")
    return unified_document("UnifiedAnalysisPlan", request_digest=request_digest, bundle_id=bundle_id,
                            selected_scopes=sorted(item["target_id"] for item in bundle_index["scopes"]),
                            stages=stages, edges=edges, diagnostics=[], frontier=frontier)
