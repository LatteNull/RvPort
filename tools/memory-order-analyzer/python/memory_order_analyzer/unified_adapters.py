"""Read-only adapters from the unified coordinator to existing P/A/R analyses."""

from copy import deepcopy
import json
from pathlib import Path

from .advanced_atomic_contracts import advanced_atomic_document, expected_advanced_atomic_protocol
from .analyze_demanded_functions import analyze_demanded_functions
from .analyze_object_provenance import analyze_object_provenance
from .build_concurrent_access_candidates import build_concurrent_access_candidates
from .concurrent_access_contracts import concurrent_access_document, expected_concurrent_access_protocol
from .contracts import AnalysisError, canonical, file_hash, identity, read_document
from .cpp_raii_contracts import cpp_raii_document, expected_cpp_raii_protocol, read_cpp_raii_document
from .cpp_thread_contracts import cpp_thread_document, expected_cpp_thread_protocol, read_cpp_thread_document
from .demand_contracts import demand_document, expected_demand_protocol
from .detect_publication import detect_publication_risks
from .execution import OutputStore
from .model_cpp_raii_synchronization import model_cpp_raii_synchronization
from .model_cpp_thread_lifecycle import model_cpp_thread_lifecycle
from .model_fence_rmw_publication import model_fence_rmw_publication
from .pipeline import write_json
from .provenance_contracts import expected_provenance_protocol, provenance_document
from .publication_contracts import expected_publication_protocol, publication_document
from .source_contracts import read_source_document
from .thread_contracts import read_thread_document


ROOT = Path(__file__).resolve().parents[2]


def canonical_members(items, key):
    """Normalize a protocol identity without discarding conflicting evidence."""
    unique = {}
    for item in items:
        identifier = key(item)
        if identifier in unique and canonical(unique[identifier]) != canonical(item):
            raise AnalysisError("profile_conflict", f"Conflicting protocol member: {identifier}")
        unique[identifier] = item
    return [unique[identifier] for identifier in sorted(unique)]


def dependency(kind, identifier, value):
    return {"kind": kind, "id": str(identifier), "digest": identity(value)}


def evidence(kind, identifier, value, path):
    return {"kind": kind, "id": str(identifier), "digest": identity(value),
            "path": str(path).replace("\\", "/"), "schema_version": value.get("schema_version", 1),
            "producer": value.get("policy_id", "unknown")}


def hashed_input(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": file_hash(path)}


def _copy(store, source, relative):
    destination = store.path(relative)
    if destination.exists():
        if file_hash(destination) != file_hash(source):
            raise AnalysisError("artifact_conflict", f"Adapter output conflict: {relative}")
        return destination
    with store.temporary() as temporary:
        staged = temporary / "artifact"
        staged.write_bytes(Path(source).read_bytes())
        return store.publish(staged, relative)


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError("adapter_input", f"Invalid adapter input: {path}") from exc


def _write_request(path, request):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(request) + "\n", encoding="utf-8")
    return path


def _abi(record):
    value = record["target"]["abi"]
    return str(value.get("name") or value.get("cxx_abi") or canonical(value))


def _source_fact(data, record):
    path = data / f"source-facts/{record['physical_tu_id']}.json"
    return read_source_document(path, "SourceSemanticFacts") if path.is_file() else None


def _module(data, mapping):
    return read_document(data / f"facts/{mapping['artifact_key']}.json", "ModuleFacts")


def _profile_id(record, source_inputs):
    entry = source_inputs.get(record["record_id"])
    return (entry["request"]["profile"]["profile_id"] if entry else
            identity({"compile": record["compile_record_digest"], "target": record["target"],
                      "language": record["language"], "standard": record["standard"]}))


def run_demand(scope, data, store, module_by_record, source_inputs, output, worker):
    plan_path = data / f"root-plans/{scope['target_id']}.json"
    overlay_path = data / f"thread-entry-roots/{scope['target_id']}.json"
    if not plan_path.is_file() or not overlay_path.is_file():
        raise AnalysisError("adapter_dependency_incomplete", "R3 requires root plan and thread-entry overlay")
    plan, overlay = _json(plan_path), _json(overlay_path)
    members = []
    for record in scope["records"]:
        mapping = module_by_record.get(record["record_id"])
        if not mapping:
            continue
        source = _source_fact(data, record)
        source_entry = source_inputs.get(record["record_id"])
        compiler = (source_entry["request"]["profile"]["compiler"]["family"] if source_entry else
                    "clang" if record["producer"]["family"] == "clang" else None)
        if compiler is None:
            continue
        members.append({"physical_tu_id": record["physical_tu_id"],
                        "artifact_key": mapping["artifact_key"], "bc_digest": record["bitcode"]["sha256"],
                        "profile_id": _profile_id(record, source_inputs),
                        "compiler": compiler, "language": record["language"],
                        "standard": record["standard"], "target": record["target"]["triple"],
                        "data_layout": record["target"]["data_layout"], "abi": _abi(record),
                        "evidence_mode": "ast+ir" if source else "ir-only"})
    if not members:
        raise AnalysisError("adapter_dependency_incomplete", "R3 requires at least one attested IR member")
    request = demand_document(
        "DemandDrivenAnalysisRequest", scope_id=scope["target_id"],
        closed_scope=scope["closed"] and not scope["external_boundaries"],
        target=scope["target_triple"], data_layout=scope["records"][0]["target"]["data_layout"],
        abi=_abi(scope["records"][0]), members=canonical_members(members, lambda item: item["physical_tu_id"]),
        evidence=sorted([
            evidence("RootDrivenAnalysisPlan", scope["target_id"], plan,
                     f"root-plans/{scope['target_id']}.json"),
            evidence("ThreadEntryRootOverlay", scope["target_id"], overlay,
                     f"thread-entry-roots/{scope['target_id']}.json"),
        ], key=lambda item: (item["kind"], item["id"])), layers=["effect", "semantic", "thread"],
        budgets=expected_demand_protocol()["budgets"], semantic_digest=None)
    request_path = _write_request(data / f"requests/{scope['target_id']}/demand.json", request)
    report = analyze_demanded_functions(request_path, data, output, worker)
    for name, relative in (("demand-graph.json", f"demand-graphs/{scope['target_id']}.json"),
                           ("worker-manifest.json", f"worker-manifests/{scope['target_id']}.json"),
                           ("views/effects.json", f"demand-views/{scope['target_id']}-effects.json"),
                           ("views/threads.json", f"demand-views/{scope['target_id']}-threads.json"),
                           ("views/concurrent-access.json", f"demand-views/{scope['target_id']}-concurrent-access.json")):
        path = output / name
        if path.is_file():
            _copy(store, path, relative)
    return report


def _infer_vendor(facts):
    names = [str(item.get("qualified_name") or item.get("canonical_type") or "")
             for item in (facts or {}).get("nodes", [])]
    if any("std::__1::" in item for item in names):
        return "libc++"
    if any("std::" in item for item in names):
        return "libstdc++"
    return None


def _profiles(directory, reader, kind, scope, data):
    result = []
    for standard in sorted({item["standard"] for item in scope["records"] if item["language"] == "c++"}):
        records = [item for item in scope["records"] if item["standard"] == standard]
        vendors = {_infer_vendor(_source_fact(data, item)) for item in records}
        candidates, differences = [], []
        for path in sorted((ROOT / directory).glob("*.json")):
            value = reader(path, kind)
            mismatch = []
            for record in records:
                expected = {"status": "verified", "cxx_standard": standard,
                            "target": record["target"]["triple"],
                            "data_layout": record["target"]["data_layout"],
                            "cxx_abi": record["target"]["abi"].get("cxx_abi")}
                mismatch.extend(key for key, wanted in expected.items()
                                if wanted is None or value.get(key) != wanted)
            if len(vendors) != 1 or value["vendor"] not in vendors:
                mismatch.append("vendor")
            if not mismatch:
                candidates.append((path, value))
            else:
                differences.append({"profile": value["profile_id"], "mismatches": sorted(set(mismatch))})
        if len(candidates) != 1:
            code = "library_profile_missing" if not candidates else "library_profile_ambiguous"
            raise AnalysisError(code, f"No unique verified {kind} for {standard}: " + canonical({
                "matches": [item[1]["profile_id"] for item in candidates], "differences": differences}))
        result.append(candidates[0])
    return result


def _base_dependencies(scope, data, module_by_record):
    dependencies, members = [], []
    for record in scope["records"]:
        source = _source_fact(data, record)
        source_ref = dependency("SourceSemanticFacts", record["physical_tu_id"], source) if source else None
        mapping = module_by_record.get(record["record_id"])
        module = _module(data, mapping) if mapping else None
        module_ref = dependency("ModuleFacts", mapping["artifact_key"], module) if module else None
        for item in (source_ref, module_ref):
            if item:
                dependencies.append(item)
        members.append({"physical_tu_id": record["physical_tu_id"], "language": record["language"],
                        "standard": record["standard"], "source": source, "source_ref": source_ref,
                        "module": module, "module_ref": module_ref, "mapping": mapping})
    for kind, relative in (("ProgramEntityIndex", f"entity-index/{scope['target_id']}.json"),
                           ("SourceIRBinding", f"source-ir-binding/{scope['target_id']}.json"),
                           ("ThreadContextGraph", f"graphs/{scope['target_id']}.json")):
        path = data / relative
        if path.is_file():
            value = _json(path)
            dependencies.append(dependency(kind, scope["target_id"], value))
    unique = {(item["kind"], item["id"]): item for item in dependencies}
    return sorted(unique.values(), key=lambda item: (item["kind"], item["id"])), members


def run_cpp_lifecycle(scope, data, store, module_by_record, source_inputs, output):
    del source_inputs
    if not any(item["language"] == "c++" for item in scope["records"]):
        return None
    dependencies, base_members = _base_dependencies(scope, data, module_by_record)
    profiles = _profiles("cpp-thread-profiles", read_cpp_thread_document,
                         "CppThreadLibraryProfile", scope, data)
    profile_refs = []
    for path, value in profiles:
        _copy(store, path, f"cpp-thread-profiles/{value['profile_id']}.json")
        profile_refs.append(dependency("CppThreadLibraryProfile", value["profile_id"], value))
    members = []
    for item in base_members:
        ir_ref = None
        if item["mapping"]:
            path = data / f"llvm-binding-facts/{item['mapping']['artifact_key']}.json"
            if path.is_file():
                value = read_source_document(path, "LLVMSourceBindingFacts")
                ir_ref = dependency("LLVMSourceBindingFacts", item["mapping"]["artifact_key"], value)
                dependencies.append(ir_ref)
        members.append({"physical_tu_id": item["physical_tu_id"],
                        "profile_id": (item["source"]["profile_id"] if item["source"] else
                                       identity({"tu": item["physical_tu_id"]})),
                        "language": item["language"], "standard": item["standard"],
                        "source_facts": item["source_ref"], "ir_facts": ir_ref})
    roots = _json(data / f"execution-roots/{scope['target_id']}.json")["roots"]
    request = cpp_thread_document(
        "CppThreadLifecycleRequest", scope_id=scope["target_id"],
        roots=sorted(item["id"] for item in roots) or ["scope-root"],
        members=sorted(members, key=lambda item: item["physical_tu_id"]),
        dependencies=sorted({(item["kind"], item["id"]): item for item in dependencies}.values(),
                            key=lambda item: (item["kind"], item["id"])),
        library_profiles=sorted(profile_refs, key=lambda item: (item["kind"], item["id"])),
        budgets=expected_cpp_thread_protocol()["budgets"], semantic_digest=None)
    request_path = _write_request(data / f"requests/{scope['target_id']}/cpp-thread.json", request)
    report = model_cpp_thread_lifecycle(request_path, data, output)
    graph_path = next((output / "graphs").glob("*.json"))
    _copy(store, graph_path, f"cpp-thread-graphs/{scope['target_id']}.json")
    return report


def run_raii(scope, data, store, module_by_record, output):
    if not any(item["language"] == "c++" for item in scope["records"]):
        return None
    dependencies, base_members = _base_dependencies(scope, data, module_by_record)
    lifecycle_path = data / f"cpp-thread-graphs/{scope['target_id']}.json"
    if lifecycle_path.is_file():
        value = _json(lifecycle_path)
        dependencies.append(dependency("CppThreadLifecycleGraph", scope["target_id"], value))
    profiles = _profiles("cpp-raii-profiles", read_cpp_raii_document,
                         "CppRaiiSynchronizationProfile", scope, data)
    profile_refs = []
    for path, value in profiles:
        _copy(store, path, f"cpp-raii-profiles/{value['profile_id']}.json")
        profile_refs.append(dependency("CppRaiiSynchronizationProfile", value["profile_id"], value))
    members = [{"physical_tu_id": item["physical_tu_id"],
                "profile_id": item["source"]["profile_id"] if item["source"] else identity({"tu": item["physical_tu_id"]}),
                "language": item["language"], "standard": item["standard"],
                "source_facts": item["source_ref"], "ir_facts": item["module_ref"]}
               for item in base_members]
    roots = _json(data / f"execution-roots/{scope['target_id']}.json")["roots"]
    request = cpp_raii_document(
        "CppRaiiSynchronizationRequest", scope_id=scope["target_id"],
        roots=sorted(item["id"] for item in roots) or ["scope-root"],
        members=sorted(members, key=lambda item: item["physical_tu_id"]),
        dependencies=sorted({(item["kind"], item["id"]): item for item in dependencies}.values(),
                            key=lambda item: (item["kind"], item["id"])),
        synchronization_profiles=sorted(profile_refs, key=lambda item: (item["kind"], item["id"])),
        budgets=expected_cpp_raii_protocol()["budgets"], semantic_digest=None)
    request_path = _write_request(data / f"requests/{scope['target_id']}/raii.json", request)
    report = model_cpp_raii_synchronization(request_path, data, output)
    graph_path = next((output / "graphs").glob("*.json"))
    _copy(store, graph_path, f"raii-graphs/{scope['target_id']}.json")
    return report


def run_provenance(scope, data, store, module_by_record, source_inputs, output,
                   source_worker, ir_worker):
    dependencies = []
    for kind, relative in (("ProgramEntityIndex", f"entity-index/{scope['target_id']}.json"),
                           ("SourceIRBinding", f"source-ir-binding/{scope['target_id']}.json")):
        path = data / relative
        if path.is_file():
            dependencies.append(dependency(kind, scope["target_id"], _json(path)))
    for path in sorted((data / "summaries").glob("*.json")) if (data / "summaries").is_dir() else []:
        value = _json(path)
        dependencies.append(dependency("EffectSummary", value["context_id"], value))
    members = []
    request_dir = data / f"requests/{scope['target_id']}/provenance"
    request_dir.mkdir(parents=True, exist_ok=True)
    for record in scope["records"]:
        source_entry = source_inputs.get(record["record_id"])
        source_path = llvm_path = None
        profile_id = _profile_id(record, source_inputs)
        if source_entry:
            source_request = provenance_document(
                "SourceObjectPathRequest", profile=source_entry["request"]["profile"],
                physical_tu_id=record["physical_tu_id"],
                source_path=source_entry["request"]["source_path"],
                budgets=expected_provenance_protocol()["budgets"], semantic_digest=None)
            source_path = request_dir / f"source-{record['record_id']}.json"
            source_path.write_text(canonical(source_request) + "\n", encoding="utf-8")
        mapping = module_by_record.get(record["record_id"])
        if mapping:
            llvm_request = provenance_document(
                "LLVMObjectProvenanceRequest", artifact_key=mapping["artifact_key"],
                profile_id=profile_id, physical_tu_id=record["physical_tu_id"],
                bitcode={"path": str(data / f"artifacts/{mapping['artifact_key']}.bc"),
                         "sha256": record["bitcode"]["sha256"]},
                dependencies=deepcopy(dependencies), budgets=expected_provenance_protocol()["budgets"],
                semantic_digest=None)
            llvm_path = request_dir / f"llvm-{record['record_id']}.json"
            llvm_path.write_text(canonical(llvm_request) + "\n", encoding="utf-8")
        if source_path is None and llvm_path is None:
            raise AnalysisError("adapter_dependency_incomplete",
                                f"A5 requires AST or LLVM evidence for {record['physical_tu_id']}")
        members.append({"physical_tu_id": record["physical_tu_id"], "profile_id": profile_id,
                        "language": record["language"], "standard": record["standard"],
                        "source_request": str(source_path) if source_path else None,
                        "llvm_request": str(llvm_path) if llvm_path else None})
    roots = _json(data / f"execution-roots/{scope['target_id']}.json")["roots"]
    request = provenance_document(
        "BoundedObjectProvenanceRequest", scope_id=scope["target_id"],
        roots=sorted(item["id"] for item in roots),
        members=sorted(members, key=lambda item: item["physical_tu_id"]),
        dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
        budgets=expected_provenance_protocol()["budgets"], semantic_digest=None)
    request_path = _write_request(data / f"requests/{scope['target_id']}/object-provenance.json", request)
    report = analyze_object_provenance(request_path, data, output, source_worker, ir_worker)
    graph_path = next((output / "graphs").glob("*.json"))
    _copy(store, graph_path, f"provenance-graphs/{scope['target_id']}.json")
    return report


def _r2_evidence(scope, data):
    result = []
    single = (
        ("RootDrivenAnalysisPlan", f"root-plans/{scope['target_id']}.json"),
        ("ThreadEntryRootOverlay", f"thread-entry-roots/{scope['target_id']}.json"),
        ("ExecutionRootIndex", f"execution-roots/{scope['target_id']}.json"),
        ("ThreadContextGraph", f"graphs/{scope['target_id']}.json"),
        ("CppThreadLifecycleGraph", f"cpp-thread-graphs/{scope['target_id']}.json"),
        ("CppRaiiSynchronizationGraph", f"raii-graphs/{scope['target_id']}.json"),
        ("BoundedObjectProvenanceGraph", f"provenance-graphs/{scope['target_id']}.json"),
    )
    for kind, relative in single:
        path = data / relative
        if path.is_file():
            result.append(evidence(kind, scope["target_id"], _json(path), relative))
    for path in sorted((data / "summaries").glob("*.json")) if (data / "summaries").is_dir() else []:
        value = _json(path)
        result.append(evidence("EffectSummary", value["context_id"], value,
                               path.relative_to(data).as_posix()))
    return sorted(result, key=lambda item: (item["kind"], item["id"]))


def run_concurrent(scope, data, module_by_record, source_inputs, output):
    refs = _r2_evidence(scope, data)
    required = {item["kind"] for item in refs}
    if not {"RootDrivenAnalysisPlan", "ThreadEntryRootOverlay", "EffectSummary"} <= required:
        raise AnalysisError("adapter_dependency_incomplete", "R2 requires root plan, thread-entry overlay and EffectSummary")
    binding = _json(data / f"source-ir-binding/{scope['target_id']}.json") if (data / f"source-ir-binding/{scope['target_id']}.json").is_file() else None
    members = []
    for record in scope["records"]:
        mapping = module_by_record.get(record["record_id"])
        source = _source_fact(data, record)
        members.append({"physical_tu_id": record["physical_tu_id"],
                        "profile_id": _profile_id(record, source_inputs), "language": record["language"],
                        "standard": record["standard"],
                        "source_digest": source.get("source_digest") if source else None,
                        "bc_digest": record["bitcode"]["sha256"] if mapping else None,
                        "source_ir_binding_digest": binding.get("semantic_digest") if binding else None})
    request = concurrent_access_document(
        "ConcurrentAccessCandidateRequest", scope_id=scope["target_id"],
        closed_scope=scope["closed"] and not scope["external_boundaries"],
        target=scope["target_triple"], data_layout=scope["records"][0]["target"]["data_layout"],
        abi=_abi(scope["records"][0]), members=sorted(members, key=lambda item: item["physical_tu_id"]),
        evidence=refs, budgets=expected_concurrent_access_protocol()["budgets"], semantic_digest=None)
    request_path = _write_request(data / f"requests/{scope['target_id']}/concurrent.json", request)
    report = build_concurrent_access_candidates(request_path, data, output)
    return report


def run_publication(scope, data, output, worker, thread_request=None):
    if thread_request is None:
        raise AnalysisError("adapter_dependency_incomplete", "P4 requires a P3 thread request")
    path = Path(thread_request).resolve()
    if not path.is_relative_to((data / f"requests/{scope['target_id']}").resolve()):
        raise AnalysisError("invalid_reference", "P3 request must belong to the current scope")
    read_thread_document(path, "ThreadAnalysisRequest")
    request = publication_document(
        "PublicationRiskRequest", thread_request=str(path),
        model_id="c-cpp-single-publication-v1", budgets=expected_publication_protocol()["budgets"])
    request_path = _write_request(data / f"requests/{scope['target_id']}/publication.json", request)
    source = data / "source" / scope["target_id"]
    return detect_publication_risks(request_path, data, output, worker, source if source.is_dir() else None)


def run_atomic(scope, data, output_root):
    reports = []
    mappings = {item["record_id"]: item for item in _json(data / "report.json")["record_artifacts"]}
    optional = {
        "thread_graph": data / f"graphs/{scope['target_id']}.json",
        "provenance_graph": data / f"provenance-graphs/{scope['target_id']}.json",
        "publication_graph": data / f"analysis/{scope['target_id']}/publication/graphs",
        "root_plan": data / f"root-plans/{scope['target_id']}.json",
        "demand_graph": data / f"demand-graphs/{scope['target_id']}.json",
        "candidate_graph": data / f"analysis/{scope['target_id']}/concurrent/candidate-graph.json",
    }
    publication_graphs = list(optional["publication_graph"].glob("*.json")) if optional["publication_graph"].is_dir() else []
    optional["publication_graph"] = publication_graphs[0] if publication_graphs else Path("missing")
    values = {key: hashed_input(path) if path.is_file() else None for key, path in optional.items()}
    for standard in sorted({item["standard"] for item in scope["records"]}):
        records = [item for item in scope["records"] if item["standard"] == standard]
        module_paths = {data / f"facts/{mapping['artifact_key']}.json" for record in records
                        if (mapping := mappings.get(record["record_id"])) and mapping["artifact_key"]}
        source_paths = {data / f"source-facts/{record['physical_tu_id']}.json" for record in records}
        module_inputs = [hashed_input(path) for path in sorted(module_paths) if path.is_file()]
        source_inputs = [hashed_input(path) for path in sorted(source_paths) if path.is_file()]
        if standard in {"compiler-default", "c89", "c99", "c++98", "c++03"} or not (module_inputs or source_inputs):
            reports.append({"status": "partial", "language_standard": standard, "findings": [],
                            "diagnostics": [{"code": "atomic-standard-unresolved" if standard == "compiler-default"
                                             else "atomic-evidence-unsupported",
                                             "detail": f"标准 {standard} 缺少可验证的 ISO 原子语义或输入证据",
                                             "detail_en": f"Standard {standard} lacks verified ISO atomic semantics or input evidence"}]})
            continue
        try:
            request = advanced_atomic_document(
                "FenceRmwPublicationRequest", model_id="bounded-advanced-atomic-publication-v1",
                scope_id=scope["target_id"], language_standard=standard,
                closed_scope=scope["closed"] and not scope["external_boundaries"],
                module_facts=module_inputs, source_facts=source_inputs,
                budgets=expected_advanced_atomic_protocol()["budgets"], **values)
            request_path = _write_request(
                data / f"requests/{scope['target_id']}/atomic-{standard.replace('+', 'p')}.json", request)
            output = output_root / standard.replace("+", "p")
            reports.append(model_fence_rmw_publication(request_path, data, output))
        except (AnalysisError, OSError, ValueError) as exc:
            reports.append({"status": "partial", "language_standard": standard, "findings": [],
                            "diagnostics": [{"code": getattr(exc, "code", "atomic-group-failed"),
                                             "detail": f"原子标准组 {standard} 分析失败",
                                             "detail_en": f"Atomic group {standard} failed: {exc}"}]})
    return reports
