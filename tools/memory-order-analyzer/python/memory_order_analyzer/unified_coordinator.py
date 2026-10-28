"""Deterministic project-level orchestration over external BC and source evidence."""

from contextlib import contextmanager
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import tempfile
from time import monotonic

from .analyze_degraded_source import analyze_degraded_source
from .contracts import AnalysisError, canonical, document, file_hash, identity, read_document
from .degraded_contracts import degraded_document, expected_degraded_protocol, failure_record, input_hash
from .execution import OutputStore
from .external_bitcode_ingestion import ingest_bundle
from .finding_contracts import provenance, validate_finding
from .finding_projection import project_pipeline_assessment, project_source_candidate
from .finding_locations import candidate_locations, assessment_locations
from .index_source_evidence import index_source_evidence
from .pipeline import write_json
from .root_contracts import expected_root_protocol, root_document
from .plan_execution_roots import plan_execution_roots
from .source_context import snapshot_source, source_projection, validate_project_path
from .source_contracts import expected_source_protocol, read_source_document, source_document
from .thread_contracts import expected_thread_protocol, thread_document
from .model_threads import model_threads
from .thread_entry_contracts import expected_thread_entry_protocol, thread_entry_document
from .thread_entry_profiles import c_api_profile, load_model_registry
from .discover_thread_entries import discover_thread_entries
from .unified_contracts import (
    diagnostic, read_unified_document, semantic_digest as unified_semantic_digest,
    unified_document, validate_unified_document,
)
from .unified_plan import build_plan, preflight_bundle
from .result_policy import admit_candidates, adapt_diagnostics, merge_diagnostics, stage_applicability, evidence_complete, bound_diagnostics
from .unified_adapters import (
    canonical_members,
    run_atomic, run_concurrent, run_cpp_lifecycle, run_demand, run_provenance,
    run_publication, run_raii,
)


@contextmanager
def atomic_analysis_output(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise AnalysisError("output_exists", "Unified analysis requires a fresh output directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        yield temporary
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _copy_once(store, source, relative):
    destination = store.path(relative)
    if destination.exists():
        if file_hash(source) != file_hash(destination):
            raise AnalysisError("artifact_conflict", f"Artifact destination already contains different content: {relative}")
        return destination
    with store.temporary() as temporary:
        staged = temporary / "artifact"
        try:
            os.link(Path(source).resolve(), staged)
        except OSError:
            shutil.copyfile(source, staged)
        try:
            return store.publish(staged, relative)
        except AnalysisError as exc:
            # Two disjoint Scope workers may publish the same immutable input.
            # Accept only a byte-identical winner of that race.
            if exc.code != "output_exists" or not destination.is_file() or file_hash(destination) != file_hash(source):
                raise
            return destination


def _reference(kind, identifier, value, path, producer):
    return {"kind": kind, "id": str(identifier), "producer": producer, "schema_version": 1,
            "digest": identity(value), "path": str(path).replace("\\", "/")}


def _json_document(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError("adapter_input", f"Invalid adapter document: {path}") from exc


def _stage_result(stage, status, outputs=(), diagnostics=(), frontier=(), cache="miss"):
    return {"stage_id": stage["id"], "stage": stage["stage"], "status": status,
            "cache": cache, "outputs": sorted(deepcopy(list(outputs)), key=lambda item: (item["kind"], item["id"])),
            "diagnostics": deepcopy(list(diagnostics)), "frontier": deepcopy(list(frontier))}


def _attach_stage_outputs(results, planned, root, scope_tokens):
    """Attach typed immutable artifacts without exposing stage ordering to callers."""
    references = _artifact_index(root)
    tokens = tuple(str(item) for item in scope_tokens if item)
    shared = {"ExternalBitcodeIngestionReport"}
    for result in results:
        expected = set(planned[result["stage"]]["outputs"])
        result["outputs"] = [item for item in references
                             if item["kind"] in expected and
                             (item["kind"] in shared or any(token in item["path"] for token in tokens))]
    return results


def _tree_bytes(root):
    return sum(path.stat().st_size for path in Path(root).rglob("*") if path.is_file())


def _published_paths(root):
    """任务目录及原子写入临时文件尚未发布，不能参与并发索引或缓存。"""
    root = Path(root)
    return sorted(path for path in root.rglob("*")
                  if not any(part.startswith(".task-") or (part.startswith(".") and part.endswith(".tmp"))
                             for part in path.relative_to(root).parts)
                  and path.is_file())


def _artifact_index(root):
    """Index immutable published output without making the report self-referential."""
    root = Path(root)
    references = []
    for path in _published_paths(root):
        relative = path.relative_to(root).as_posix()
        if relative in {"report.json", "artifacts.json"}:
            continue
        value = None
        if path.suffix == ".json":
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError, RecursionError):
                value = None
        digest = identity(value) if isinstance(value, dict) else file_hash(path)
        kind = (value or {}).get("kind") if isinstance(value, dict) else None
        kind = kind or ("SourceSnapshot" if relative.startswith("source-snapshots/") else "BinaryArtifact")
        identifier = identity({"kind": kind, "path": relative, "digest": digest})
        producer = ((value or {}).get("policy_id") if isinstance(value, dict) else None) or \
                   "org.rvport.memory-order-analyzer.coordinator"
        references.append({"kind": kind, "id": identifier, "producer": producer,
                           "schema_version": int((value or {}).get("schema_version", 1)) if isinstance(value, dict) else 1,
                           "digest": digest, "path": relative})
    return sorted(references, key=lambda item: (item["kind"], item["id"]))


def _cache_payload(record, formal, candidates, bounded):
    return {"record": deepcopy(record), "findings": deepcopy(formal),
            "source_candidates": deepcopy(candidates),
            "discharged_assessments": deepcopy(bounded)}


def _validate_cache_payload(value):
    if not isinstance(value, dict) or set(value) != {
            "record", "findings", "source_candidates", "discharged_assessments"}:
        raise AnalysisError("cache_corrupt", "Unified Scope cache payload has an invalid shape")
    validate_unified_document(value["record"], "ScopeAnalysisExecutionRecord")
    for collection in ("findings", "source_candidates", "discharged_assessments"):
        for item in value[collection]:
            validate_finding(item)
    return value


def _source_point(source):
    if not isinstance(source, dict):
        return None, None
    for prefix in ("expansion", "spelling", "location"):
        point = source.get(prefix)
        if isinstance(point, dict) and isinstance(point.get("line"), int):
            end = source.get(f"{prefix}_end")
            return point, end if isinstance(end, dict) else None
    if isinstance(source.get("line"), int):
        return source, None
    return None, None


def _candidate_location(candidate, source_facts, scope, snapshots, output_root, request):
    locations = candidate_locations(candidate, source_facts, scope, snapshots, output_root, request)
    return locations[0]["location"] if locations else None


def _source_request(path):
    return read_source_document(path, "SourceSemanticRequest")


def _profile_id(record, source_request=None):
    return (source_request["profile"]["profile_id"] if source_request else
            identity({"record": record["record_id"], "compile": record["compile_record_digest"],
                      "language": record["language"], "standard": record["standard"],
                      "target": record["target"]}))


def _mode(record, *, source_usable, ir_usable):
    available = [name for name, present in (("ast", source_usable), ("ir", ir_usable)) if present]
    missing = [name for name in ("ast", "ir") if name not in available]
    name = "ast-ir" if len(available) == 2 else "ast-only" if available == ["ast"] else "ir-only" if available == ["ir"] else "failed"
    return {"record_id": record["record_id"], "physical_tu_id": record["physical_tu_id"], "mode": name,
            "status": "complete" if name == "ast-ir" else "failed" if name == "failed" else "partial",
            "available_evidence": available, "missing_evidence": missing}


class AnalysisCoordinator:
    def __init__(self, request_path, output, *, ir_worker="/output/build/moa-worker",
                 source_worker="/output/build/memory-order-source-worker", cache_path=None,
                 clock=monotonic, ingest=ingest_bundle):
        self.request_path = Path(request_path).resolve()
        self.output = Path(output).resolve()
        self.ir_worker = ir_worker
        self.source_worker = source_worker
        self.cache_path = Path(cache_path).resolve() if cache_path else None
        self.clock = clock
        self.ingest = ingest
        self.started = None

    def _cancelled(self, request):
        return bool(request["cancel_file"] and Path(request["cancel_file"]).is_file())

    def _deadline(self, request):
        return self.clock() - self.started > request["budgets"]["deadline_seconds"]

    def _check_stop(self, request, stage, scope_id=None):
        if self._cancelled(request):
            raise AnalysisError("analysis_cancelled", f"Analysis was cancelled before {stage}")
        if self._deadline(request):
            raise AnalysisError("analysis_deadline", f"Analysis deadline expired before {stage}")

    @staticmethod
    def _propagate_stop(exc):
        if isinstance(exc, AnalysisError) and exc.code in {"analysis_cancelled", "analysis_deadline"}:
            raise exc

    def _scope_cache_key(self, request, bundle, scope, plan):
        stages = [item for item in plan["stages"] if item["scope_id"] == scope["target_id"]]
        return identity({"namespace": "unified-project-analysis-results-v3", "request": request["semantic_digest"],
                         "source_projection_revision": 2,
                         "bundle": bundle["manifest"]["bundle_id"], "scope": scope["target_id"],
                         "records": [(item["record_id"], (item.get("bitcode") or {}).get("sha256"),
                                      item.get("compile_record_digest")) for item in scope["records"]],
                         "stages": [(item["stage"], item["version"], item["id"]) for item in stages]})

    def _scope_cache_file(self, key):
        return self.cache_path / "unified-project-analysis-results-v3" / key[:2] / f"{key}.json"

    def _load_scope_cache(self, request, bundle, scope, plan, data_root):
        if (self.cache_path is None or request["cache"]["mode"] == "disabled" or
                not request["cache"]["resume"]):
            return None, None
        key = self._scope_cache_key(request, bundle, scope, plan)
        path = self._scope_cache_file(key)
        if not path.is_file():
            return None, None
        try:
            envelope = _json_document(path)
            payload = envelope["payload"]
            if (envelope.get("namespace") != "unified-project-analysis-results-v3" or
                    envelope.get("key") != key or envelope.get("status") != "complete" or
                    envelope.get("payload_digest") != identity(payload)):
                raise AnalysisError("cache_corrupt", "Unified Scope cache envelope is invalid")
            artifact_root = path.with_suffix(".artifacts")
            for item in envelope.get("artifacts", []):
                validate_project_path(item["path"])
                cached = artifact_root / item["path"]
                if not cached.is_file() or file_hash(cached) != item["sha256"]:
                    raise AnalysisError("cache_corrupt", "Unified Scope cache artifact is missing or corrupt")
            target_store = OutputStore(data_root)
            for item in envelope.get("artifacts", []):
                cached = artifact_root / item["path"]
                destination = target_store.path(item["path"])
                if destination.exists():
                    if not destination.is_file() or file_hash(destination) != item["sha256"]:
                        raise AnalysisError("cache_conflict", "Cached Scope artifact conflicts with current input")
                else:
                    _copy_once(target_store, cached, item["path"])
            _validate_cache_payload(payload)
            if payload["record"]["status"] != "complete":
                raise AnalysisError("cache_incomplete", "Only complete Scope results may be resumed")
            warmed = deepcopy(payload)
            for stage in warmed["record"]["stages"]:
                if stage["cache"] != "disabled":
                    stage["cache"] = "hit"
            warmed["record"]["semantic_digest"] = unified_semantic_digest(warmed["record"])
            validate_unified_document(warmed["record"], "ScopeAnalysisExecutionRecord")
            return warmed, None
        except (AnalysisError, OSError, ValueError, KeyError, TypeError) as exc:
            return None, diagnostic("cache-corrupt", "统一 Scope 缓存损坏，已拒绝复用",
                                    f"Unified Scope cache is corrupt and was rejected: {exc}",
                                    stage="cache", scope_id=scope["target_id"])

    def _store_scope_cache(self, request, bundle, scope, plan, payload, data_root):
        if self.cache_path is None or request["cache"]["mode"] != "read-write":
            return
        _validate_cache_payload(payload)
        if payload["record"]["status"] != "complete":
            return
        key = self._scope_cache_key(request, bundle, scope, plan)
        path = self._scope_cache_file(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact_root = path.with_suffix(".artifacts")
        temporary_artifacts = path.with_suffix(f".{os.getpid()}.artifacts.tmp")
        if temporary_artifacts.exists():
            shutil.rmtree(temporary_artifacts)
        temporary_artifacts.mkdir(parents=True)
        artifacts = []
        for source in _published_paths(data_root):
            relative = source.relative_to(data_root).as_posix()
            destination = temporary_artifacts / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            artifacts.append({"path": relative, "sha256": file_hash(destination)})
        if artifact_root.exists():
            shutil.rmtree(artifact_root)
        os.replace(temporary_artifacts, artifact_root)
        envelope = {"namespace": "unified-project-analysis-results-v3", "key": key, "status": "complete",
                    "payload": deepcopy(payload), "payload_digest": identity(payload),
                    "artifacts": artifacts}
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(canonical(envelope) + "\n", encoding="utf-8")
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _write_request_inputs(self, request, bundle, data, store):
        sources = {}
        for record_id, reference in bundle["source_requests"].items():
            source_request = _source_request(reference["resolved_path"])
            record = bundle["records"][record_id]
            compiler = source_request["profile"]["compiler"]
            driver = Path(compiler["path"]).name.lower()
            if (compiler["family"] not in {"gcc", "clang"} or
                    driver in {"cl", "cl.exe", "clang-cl", "clang-cl.exe"}):
                raise AnalysisError("compiler_unsupported", "Windows, MSVC and clang-cl profiles are unsupported")
            if source_request["physical_tu_id"] != record["physical_tu_id"]:
                raise AnalysisError("profile_conflict", f"Source request TU differs from bundle record: {record_id}")
            expected = record.get("source", {}).get("sha256") if record.get("source") else None
            if expected and source_request["profile"]["source"]["sha256"] != expected:
                raise AnalysisError("source_digest_mismatch", f"Source request differs from bundle lineage: {record_id}")
            relative = f"inputs/source-requests/{record['physical_tu_id']}.json"
            write_json(store, source_request, relative)
            profile = source_request["profile"]
            context = document(
                "TUManifest", context_id=record["physical_tu_id"], source=profile["source"]["path"],
                directory=profile["working_directory"], original={}, effective_argv=profile["argv"],
                production={"description": f"{profile['compiler']['family']} {profile['compiler']['version']}"},
                analysis={"path": profile["compiler"]["path"], "version": profile["replay"]["clang_version"]},
                adaptations=[], response_files={}, environment={}, language=profile["language"], abi=profile["abi"])
            write_json(store, context, f"contexts/{record['physical_tu_id']}.json")
            sources[record_id] = {"request": source_request, "path": data / relative}
        return sources

    def _snapshot_sources(self, bundle, store):
        snapshots, failures = {}, {}
        root = bundle["manifest_path"].parent
        profiles = {identifier: _source_request(reference["resolved_path"])["profile"]
                    for identifier, reference in bundle.get("source_requests", {}).items()}
        roots = set()
        for profile in profiles.values():
            for mapping in profile.get("path_map", []):
                candidate = Path(mapping["from"])
                if mapping["to"] == "." and candidate.is_absolute() and candidate.is_dir():
                    if Path(profile["source"]["path"]).is_relative_to(candidate):
                        roots.add(candidate.resolve())
        # A single declared project root is required; never merge ambiguous roots by basename.
        if len(roots) == 1:
            root = roots.pop()
        for record_id, record in bundle["records"].items():
            source = record.get("source")
            if source is None:
                continue
            try:
                path = source["path"]
                profile = profiles.get(record_id)
                if profile:
                    actual = Path(profile["source"]["path"])
                    if actual.is_relative_to(root):
                        path = actual.relative_to(root).as_posix()
                snapshots[record_id] = snapshot_source(store, root, path, source["sha256"])
            except AnalysisError as exc:
                failures[record_id] = exc
        # Capture project headers before analysis, not when a later finding is rendered.
        remaining = 64 * 1024 * 1024
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() not in {".h", ".hpp", ".hh", ".hxx", ".inc", ".inl"} or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            try:
                from .source_context import resolve_source
                safe = resolve_source(root, relative)
                size = safe.stat().st_size
                if size > 8 * 1024 * 1024 or size > remaining:
                    raise AnalysisError("snapshot_budget", "Project header snapshot budget exceeded")
                snapshots["header:" + relative] = snapshot_source(store, root, relative, file_hash(safe))
                remaining -= size
            except AnalysisError as exc:
                failures["header:" + relative] = exc
        return snapshots, failures

    def _ingestion_maps(self, report):
        return {item["record_id"]: item for item in report["record_artifacts"]}

    def _scope_source_analysis(self, request, bundle, scope, data, store, source_inputs, module_by_record):
        selected = sorted(
            (item for item in scope["records"] if item["record_id"] in source_inputs),
            key=lambda item: (item["physical_tu_id"], item["record_id"]),
        )
        if request["source_assistance"] == "disabled" or not selected:
            return None, None, {}, {}
        aggregate_dir = data / "source" / scope["target_id"]
        request_dir = data / "requests" / scope["target_id"]
        request_dir.mkdir(parents=True, exist_ok=True)
        source_entries = canonical_members(
            [source_inputs[item["record_id"]]["request"] for item in selected],
            lambda item: item["physical_tu_id"])
        source_paths = []
        for entry in source_entries:
            path = request_dir / f"source-{entry['physical_tu_id']}.json"
            path.write_text(canonical(entry) + "\n", encoding="utf-8")
            source_paths.append(str(path))
        modules = []
        ir_requests = []
        for record in selected:
            mapping = module_by_record.get(record["record_id"])
            if not mapping:
                continue
            facts = read_document(data / f"facts/{mapping['artifact_key']}.json", "ModuleFacts")
            modules.append({"kind": "ModuleFacts", "id": mapping["artifact_key"], "digest": identity(facts)})
            source_request = source_inputs[record["record_id"]]["request"]
            ir_request = source_document(
                "LLVMSourceBindingRequest", artifact_key=mapping["artifact_key"],
                profile_id=source_request["profile"]["profile_id"], physical_tu_id=record["physical_tu_id"],
                bitcode={"path": str(data / f"artifacts/{mapping['artifact_key']}.bc"),
                         "sha256": record["bitcode"]["sha256"]},
                budgets=expected_source_protocol()["budgets"])
            ir_requests.append(ir_request)
        ir_paths = []
        for entry in canonical_members(ir_requests, lambda item: item["artifact_key"]):
            ir_path = request_dir / f"ir-{entry['artifact_key']}.json"
            ir_path.write_text(canonical(entry) + "\n", encoding="utf-8")
            ir_paths.append(str(ir_path))
        modules = canonical_members(modules, lambda item: (item["kind"], item["id"]))
        aggregate = source_document(
            "AstAssistedAnalysisRequest", scope_id=scope["target_id"],
            source_requests=source_paths, ir_requests=ir_paths,
            module_facts=sorted(modules, key=lambda item: (item["kind"], item["id"])),
            budgets=expected_source_protocol()["budgets"])
        aggregate_path = request_dir / "ast-assisted.json"
        aggregate_path.write_text(canonical(aggregate) + "\n", encoding="utf-8")
        source_report = index_source_evidence(aggregate_path, data, aggregate_dir, self.source_worker)

        declared = []
        for record in scope["records"]:
            if record["record_id"] not in source_inputs:
                declared.append(failure_record(record["physical_tu_id"], "source", "source-request-missing",
                                               "No trusted SourceSemanticRequest was declared",
                                               failure_class="external-artifact-missing", stability="deterministic",
                                               limit=expected_degraded_protocol()["budgets"]["diagnostic_bytes"]))
        source_request_hashes = sorted(
            (input_hash(Path(item)) for item in source_paths),
            key=lambda item: (item["path"], item["sha256"]),
        )
        ir_request_hashes = sorted(
            (input_hash(Path(item)) for item in ir_paths),
            key=lambda item: (item["path"], item["sha256"]),
        )
        degraded = degraded_document(
            "DegradedSourceAnalysisRequest", scope_id=scope["target_id"],
            source_requests=source_request_hashes,
            ir_requests=ir_request_hashes,
            module_facts=sorted(modules, key=lambda item: (item["kind"], item["id"])),
            declared_failures=sorted(declared, key=lambda item: item["id"]),
            products={"thread_graph": None, "publication_graph": None, "publication_report": None},
            budgets=expected_degraded_protocol()["budgets"])
        degraded_path = request_dir / "degraded.json"
        degraded_path.write_text(canonical(degraded) + "\n", encoding="utf-8")
        degraded_dir = data / "degraded" / scope["target_id"]
        degraded_report = analyze_degraded_source(degraded_path, data, degraded_dir,
                                                  self.source_worker, self.source_worker)
        source_facts = {}
        for record in selected:
            path = aggregate_dir / f"source-facts/{record['physical_tu_id']}.json"
            if path.is_file():
                facts = read_source_document(path, "SourceSemanticFacts")
                source_facts[record["record_id"]] = facts
                _copy_once(store, path, f"source-facts/{record['physical_tu_id']}.json")
            mapping = module_by_record.get(record["record_id"])
            if mapping:
                ir_path = aggregate_dir / f"llvm-binding-facts/{mapping['artifact_key']}.json"
                if ir_path.is_file():
                    _copy_once(store, ir_path, f"llvm-binding-facts/{mapping['artifact_key']}.json")
        globals_ = {}
        for name, kind in (("entity-index.json", "ProgramEntityIndex"),
                           ("source-ir-binding.json", "SourceIRBinding"),
                           ("canonical-object-overlay.json", "CanonicalObjectOverlay")):
            path = aggregate_dir / name
            if path.is_file():
                value = read_source_document(path, kind)
                relative = {"ProgramEntityIndex": f"entity-index/{scope['target_id']}.json",
                            "SourceIRBinding": f"source-ir-binding/{scope['target_id']}.json",
                            "CanonicalObjectOverlay": f"canonical-object-overlay/{scope['target_id']}.json"}[kind]
                _copy_once(store, path, relative)
                globals_[kind] = value
        return source_report, degraded_report, source_facts, globals_

    def _root_request(self, request, scope, data, module_by_record, source_inputs, source_facts,
                      globals_, extra_member=None, extra_global=None):
        members = []
        for record in scope["records"]:
            evidence = []
            mapping = module_by_record.get(record["record_id"])
            if mapping:
                facts = read_document(data / f"facts/{mapping['artifact_key']}.json", "ModuleFacts")
                evidence.append({"kind": "ModuleFacts", "id": mapping["artifact_key"],
                                 "digest": identity(facts), "path": f"facts/{mapping['artifact_key']}.json"})
            source = source_facts.get(record["record_id"])
            if source:
                evidence.append({"kind": "SourceSemanticFacts", "id": record["physical_tu_id"],
                                 "digest": identity(source), "path": f"source-facts/{record['physical_tu_id']}.json"})
            evidence.extend(deepcopy((extra_member or {}).get(record["record_id"], [])))
            if not evidence:
                continue
            members.append({"physical_tu_id": record["physical_tu_id"],
                            "profile_id": _profile_id(record, source_inputs.get(record["record_id"], {}).get("request")),
                            "language": record["language"], "standard": record["standard"],
                            "evidence": sorted(evidence, key=lambda item: (item["kind"], item["id"]))})
        global_evidence = []
        for kind, value in globals_.items():
            if kind not in {"ProgramEntityIndex", "SourceIRBinding"}:
                continue
            relative = f"entity-index/{scope['target_id']}.json" if kind == "ProgramEntityIndex" else f"source-ir-binding/{scope['target_id']}.json"
            global_evidence.append({"kind": kind, "id": scope["target_id"], "digest": identity(value), "path": relative})
        global_evidence.extend(deepcopy(extra_global or []))
        explicit = []
        for root in request["explicit_roots"]:
            if root.get("artifact_key") and root.get("function_id"):
                kind = {"program-entry": "program", "library-export": "exported",
                        "framework-thread": "framework"}[root["kind"]]
                explicit.append({"id": identity(root), "kind": kind,
                                 "entry": {"artifact_key": root["artifact_key"], "function_id": root["function_id"]},
                                 "source_entity_id": None, "arguments": []})
        return root_document(
            "ExecutionRootDiscoveryRequest", scope_id=scope["target_id"],
            closed_scope=scope["closed"] and not scope["external_boundaries"], discover_main=True,
            members=sorted(members, key=lambda item: item["physical_tu_id"]),
            global_evidence=sorted(global_evidence, key=lambda item: (item["kind"], item["id"])),
            explicit_roots=sorted(explicit, key=lambda item: item["id"]),
            budgets=expected_root_protocol()["budgets"], semantic_digest=None)

    def _run_roots_and_threads(self, request, scope, data, store, module_by_record,
                               source_inputs, source_facts, globals_):
        base = data / "analysis" / scope["target_id"]
        request_dir = data / "requests" / scope["target_id"]
        request_dir.mkdir(parents=True, exist_ok=True)
        member_extra, global_extra = {}, []
        previous_roots = None
        final_root_dir = final_thread_dir = None
        final_thread_request = None
        frontier = []
        for iteration in range(min(16, request["budgets"]["worklist_items"])):
            self._check_stop(request, "execution-root", scope["target_id"])
            root_request = self._root_request(request, scope, data, module_by_record, source_inputs,
                                              source_facts, globals_, member_extra, global_extra)
            root_request_path = request_dir / f"root-{iteration}.json"
            root_request_path.write_text(canonical(root_request) + "\n", encoding="utf-8")
            root_dir = base / f"roots-{iteration}"
            plan_execution_roots(root_request_path, data, root_dir)
            roots = json.loads((root_dir / "execution-roots/index.json").read_text(encoding="utf-8"))
            plan_paths = sorted((root_dir / "plans").glob("*.json"))
            plan_value = json.loads(plan_paths[0].read_text(encoding="utf-8"))
            root_entries = sorted((item["entry"], tuple(canonical(arg) for arg in item["arguments"]))
                                  for item in roots["roots"] if item["status"] == "complete" and item.get("entry"))
            final_root_dir = root_dir
            if not root_entries or root_entries == previous_roots:
                break
            previous_roots = root_entries
            thread_request = thread_document(
                "ThreadAnalysisRequest", scope=str(data / f"scopes/{scope['target_id']}.json"),
                roots=[{"artifact_key": entry["artifact_key"], "function_id": entry["function_id"],
                        "arguments": [json.loads(item) for item in arguments]}
                       for entry, arguments in root_entries],
                model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
            thread_path = request_dir / f"thread-{iteration}.json"
            thread_path.write_text(canonical(thread_request) + "\n", encoding="utf-8")
            thread_dir = base / f"threads-{iteration}"
            source_dir = data / "source" / scope["target_id"]
            model_threads(thread_path, data, thread_dir, self.ir_worker,
                          source_dir if source_dir.is_dir() else None)
            final_thread_dir = thread_dir
            final_thread_request = thread_path
            member_extra = {}
            for record in scope["records"]:
                mapping = module_by_record.get(record["record_id"])
                if not mapping:
                    continue
                artifact = mapping["artifact_key"]
                local_path = thread_dir / f"thread-local/{artifact}.json"
                order_path = thread_dir / f"execution-order/{artifact}.json"
                refs = []
                for path, kind, relative in ((local_path, "ThreadLocalFacts", f"thread-local/{artifact}.json"),
                                             (order_path, "ExecutionOrderFacts", f"execution-order/{artifact}.json")):
                    if path.is_file():
                        value = json.loads(path.read_text(encoding="utf-8"))
                        _copy_once(store, path, relative)
                        refs.append({"kind": kind, "id": artifact, "digest": identity(value), "path": relative})
                member_extra[record["record_id"]] = refs
            graph_path = next((thread_dir / "graphs").glob("*.json"))
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            _copy_once(store, graph_path, f"graphs/{scope['target_id']}.json")
            global_extra = [{"kind": "ThreadContextGraph", "id": scope["target_id"],
                             "digest": identity(graph), "path": f"graphs/{scope['target_id']}.json"}]
            for summary_path in (thread_dir / "effects/summaries").glob("*.json"):
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                relative = f"summaries/{summary['context_id']}.json"
                _copy_once(store, summary_path, relative)
                global_extra.append({"kind": "EffectSummary", "id": summary["context_id"],
                                     "digest": identity(summary), "path": relative})
        else:
            frontier.append(diagnostic("demand-worklist-budget", "执行根工作列表预算耗尽",
                                       "Execution-root worklist budget was exhausted",
                                       stage="execution-root", scope_id=scope["target_id"]))
        if final_root_dir:
            _copy_once(store, final_root_dir / "execution-roots/index.json",
                       f"execution-roots/{scope['target_id']}.json")
            _copy_once(store, final_root_dir / "thread-creation-sites/index.json",
                       f"thread-creation-sites/{scope['target_id']}.json")
            plan_path = next((final_root_dir / "plans").glob("*.json"))
            _copy_once(store, plan_path, f"root-plans/{scope['target_id']}.json")
        return final_root_dir, final_thread_dir, member_extra, global_extra, frontier, final_thread_request

    def _run_thread_entry(self, request, scope, data, store, module_by_record, source_inputs,
                          source_facts, globals_, root_dir, member_extra):
        if root_dir is None:
            return None
        members, models = [], []
        layout = next((record["target"]["data_layout"] for record in scope["records"]), "")
        for family in ("pthread", "c11-thread"):
            if any(item["language"] == "c" for item in scope["records"]):
                models.append(c_api_profile(family, scope["target_triple"], layout))
        for model in load_model_registry():
            if (model["target"] == scope["target_triple"] and model["data_layout"] == layout and
                    any(item["language"] == "c++" and item["standard"] in model["standards"] for item in scope["records"])):
                models.append(model)
        for record in scope["records"]:
            evidence = []
            mapping = module_by_record.get(record["record_id"])
            if mapping:
                value = read_document(data / f"facts/{mapping['artifact_key']}.json", "ModuleFacts")
                evidence.append({"kind": "ModuleFacts", "id": mapping["artifact_key"],
                                 "digest": identity(value), "path": f"facts/{mapping['artifact_key']}.json"})
            source = source_facts.get(record["record_id"])
            if source:
                evidence.append({"kind": "SourceSemanticFacts", "id": record["physical_tu_id"],
                                 "digest": identity(source), "path": f"source-facts/{record['physical_tu_id']}.json"})
            evidence.extend(item for item in member_extra.get(record["record_id"], []) if item["kind"] == "ThreadLocalFacts")
            if evidence:
                members.append({"physical_tu_id": record["physical_tu_id"],
                                "profile_id": _profile_id(record, source_inputs.get(record["record_id"], {}).get("request")),
                                "language": record["language"], "standard": record["standard"],
                                "evidence": sorted(evidence, key=lambda item: (item["kind"], item["id"]))})
        global_evidence = []
        binding = globals_.get("SourceIRBinding")
        if binding:
            global_evidence.append({"kind": "SourceIRBinding", "id": scope["target_id"],
                                    "digest": identity(binding), "path": f"source-ir-binding/{scope['target_id']}.json"})
        roots = json.loads((root_dir / "execution-roots/index.json").read_text(encoding="utf-8"))
        plan_path = next((root_dir / "plans").glob("*.json"))
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        global_evidence.extend([
            {"kind": "ExecutionRootIndex", "id": scope["target_id"], "digest": identity(roots),
             "path": f"execution-roots/{scope['target_id']}.json"},
            {"kind": "RootDrivenAnalysisPlan", "id": scope["target_id"], "digest": identity(plan),
             "path": f"root-plans/{scope['target_id']}.json"},
        ])
        entry_request = thread_entry_document(
            "ThreadEntryDiscoveryRequest", scope_id=scope["target_id"],
            closed_scope=scope["closed"] and not scope["external_boundaries"],
            members=sorted(members, key=lambda item: item["physical_tu_id"]),
            global_evidence=sorted(global_evidence, key=lambda item: (item["kind"], item["id"])),
            model_profiles=sorted(models, key=lambda item: item["id"]), framework_descriptors=[],
            budgets=expected_thread_entry_protocol()["budgets"], semantic_digest=None)
        request_path = data / f"requests/{scope['target_id']}/thread-entry.json"
        request_path.write_text(canonical(entry_request) + "\n", encoding="utf-8")
        output = data / "analysis" / scope["target_id"] / "thread-entry"
        report = discover_thread_entries(request_path, data, output)
        _copy_once(store, output / "sites/index.json", f"thread-entry-sites/{scope['target_id']}.json")
        _copy_once(store, output / "roots/overlay.json", f"thread-entry-roots/{scope['target_id']}.json")
        return report

    def _scope(self, request, plan, bundle, scope, data, store, ingestion, source_inputs,
               snapshots=None, output_root=None):
        scope_id = scope["target_id"]
        planned = {item["stage"]: item for item in plan["stages"] if item["scope_id"] == scope_id}
        stage_results, diagnostics, frontier = [], [], []
        mappings = self._ingestion_maps(ingestion)
        module_by_record = {key: value for key, value in mappings.items()
                            if value["status"] == "published" and value["facts_status"] in {"complete", "partial"}}
        ingest_missing = [item for item in scope["records"] if item["record_id"] not in module_by_record]
        ingest_frontier = [diagnostic("bc-unavailable", "外部 BC 不可用", "External bitcode is unavailable",
                                      stage="ingest", scope_id=scope_id, references=[item["record_id"]])
                           for item in ingest_missing]
        scope_record_ids = {item["record_id"] for item in scope["records"]}
        ingest_frontier.extend(adapt_diagnostics(
            [item for item in ingestion.get("diagnostics", [])
             if item.get("record_id") in scope_record_ids or
             scope_record_ids.intersection(item.get("references", []))], stage="ingest", scope_id=scope_id))
        for item in scope["records"]:
            if module_by_record.get(item["record_id"], {}).get("facts_status") == "partial":
                ingest_frontier.append(diagnostic("facts_partial", "LLVM 事实提取不完整",
                    "LLVM fact extraction is partial", stage="ingest", scope_id=scope_id,
                    references=[item["record_id"]]))
        ingest_frontier = merge_diagnostics(ingest_frontier)
        stage_results.append(_stage_result(planned["ingest"], "partial" if ingest_frontier else "complete",
                                           frontier=ingest_frontier))
        frontier.extend(ingest_frontier)
        self._check_stop(request, "source-evidence", scope_id)
        source_report = degraded_report = None
        source_facts, globals_ = {}, {}
        try:
            source_report, degraded_report, source_facts, globals_ = self._scope_source_analysis(
                request, bundle, scope, data, store, source_inputs, module_by_record)
            if source_report is None:
                source_status = "skipped-not-applicable" if request["source_assistance"] == "disabled" else "partial"
                source_frontier = ([] if request["source_assistance"] == "disabled" else
                                   [diagnostic("source-unavailable", "未提供可信源码请求", "No trusted source request was supplied",
                                               stage="source-evidence", scope_id=scope_id)])
            else:
                source_status = source_report["status"]
                source_frontier = adapt_diagnostics(source_report["frontier"], stage="source-evidence", scope_id=scope_id)
                diagnostics.extend(adapt_diagnostics(source_report.get("diagnostics", []),
                                                      stage="source-evidence", scope_id=scope_id))
                if degraded_report:
                    diagnostics.extend(adapt_diagnostics(degraded_report.get("diagnostics", []),
                                                          stage="source-evidence", scope_id=scope_id))
        except (AnalysisError, OSError, ValueError) as exc:
            self._propagate_stop(exc)
            source_status = "failed"
            source_frontier = [diagnostic(getattr(exc, "code", "source-failed"),
                                          "源码证据阶段失败", f"Source evidence stage failed: {exc}",
                                          stage="source-evidence", scope_id=scope_id)]
            if request["source_assistance"] == "required":
                frontier.extend(source_frontier)
        stage_results.append(_stage_result(planned["source-evidence"], source_status, frontier=source_frontier))
        frontier.extend(source_frontier)

        tu_modes = [_mode(record, source_usable=record["record_id"] in source_facts,
                          ir_usable=record["record_id"] in module_by_record) for record in scope["records"]]
        for mode in tu_modes:
            if module_by_record.get(mode["record_id"], {}).get("facts_status") == "partial":
                mode["status"] = "partial"
                mode["missing_evidence"] = sorted(set(mode["missing_evidence"] + ["complete-ir-facts"]))
        availability_frontier = []
        if any(item["status"] != "complete" for item in tu_modes):
            availability_frontier.append(diagnostic("tu-evidence-partial", "部分翻译单元证据不完整",
                                                    "Some translation units have incomplete evidence",
                                                    stage="evidence-availability", scope_id=scope_id,
                                                    references=[item["record_id"] for item in tu_modes if item["status"] != "complete"]))
        stage_results.append(_stage_result(planned["evidence-availability"],
                                           "partial" if availability_frontier else "complete",
                                           frontier=availability_frontier))
        frontier.extend(availability_frontier)

        root_dir = thread_dir = thread_request_path = None
        member_extra, global_extra = {}, []
        try:
            root_dir, thread_dir, member_extra, global_extra, root_frontier, thread_request_path = self._run_roots_and_threads(
                request, scope, data, store, module_by_record, source_inputs, source_facts, globals_)
            root_status = "partial" if root_frontier or root_dir is None else "complete"
        except (AnalysisError, OSError, ValueError) as exc:
            self._propagate_stop(exc)
            root_status = "failed"
            root_frontier = [diagnostic(getattr(exc, "code", "root-failed"), "执行根分析失败",
                                        f"Execution-root analysis failed: {exc}", stage="execution-root", scope_id=scope_id)]
        stage_results.append(_stage_result(planned["execution-root"], root_status, frontier=root_frontier))
        frontier.extend(root_frontier)

        try:
            entry_report = self._run_thread_entry(request, scope, data, store, module_by_record,
                                                  source_inputs, source_facts, globals_, root_dir, member_extra)
            entry_status = entry_report["status"] if entry_report else "failed"
            entry_frontier = ([] if entry_report and entry_status == "complete" else
                              [diagnostic("thread-entry-incomplete", "线程入口证据不完整",
                                          "Thread-entry evidence is incomplete", stage="thread-entry", scope_id=scope_id)])
        except (AnalysisError, OSError, ValueError) as exc:
            self._propagate_stop(exc)
            entry_status = "failed"
            entry_frontier = [diagnostic(getattr(exc, "code", "thread-entry-failed"), "线程入口分析失败",
                                         f"Thread-entry analysis failed: {exc}", stage="thread-entry", scope_id=scope_id)]
        stage_results.append(_stage_result(planned["thread-entry"], entry_status, frontier=entry_frontier))
        frontier.extend(entry_frontier)

        downstream = {}

        def invoke(name, function, *args):
            stage = planned[name]
            if stage["status"] == "skipped-not-applicable" or stage_applicability(name, scope["records"], source_facts) is False:
                stage_results.append(_stage_result(stage, "skipped-not-applicable", cache="disabled"))
                return None
            self._check_stop(request, name, scope_id)
            try:
                value = function(*args)
                if isinstance(value, list):
                    statuses = {item.get("status", "partial") for item in value}
                    status = "complete" if statuses <= {"complete"} else "failed" if statuses == {"failed"} else "partial"
                elif value is None:
                    status = "skipped-not-applicable"
                else:
                    status = value.get("status") or value.get("thread_modeling") or "partial"
                status = status if status == "skipped-not-applicable" else "complete" if status in {"complete", "resolved"} else "failed" if status == "failed" else "partial"
                reports = value if isinstance(value, list) else [value] if value else []
                details = adapt_diagnostics([item for report in reports for item in
                    [*report.get("diagnostics", []), *report.get("frontier", [])]], stage=name, scope_id=scope_id)
                diagnostics.extend(details)
                stage_frontier = [] if status in {"complete", "skipped-not-applicable"} else details or [diagnostic(
                    "adapter-result-incomplete", "适配器结果不完整", "Adapter result is incomplete",
                    stage=name, scope_id=scope_id)]
                stage_results.append(_stage_result(stage, status, frontier=stage_frontier))
                frontier.extend(stage_frontier)
                downstream[name] = value
                return value
            except (AnalysisError, OSError, ValueError) as exc:
                self._propagate_stop(exc)
                item = diagnostic(getattr(exc, "code", "adapter-failed"), "统一适配器执行失败",
                                  f"Unified adapter failed: {exc}",
                                  suggestion="补齐相关 Scope 的 AST/IR 证据或修复上游阶段",
                                  suggestion_en="Provide the scope's AST/IR evidence or repair the upstream stage",
                                  stage=name, scope_id=scope_id)
                stage_results.append(_stage_result(stage, "unknown", frontier=[item], cache="disabled"))
                frontier.append(item)
                return None

        demand_dir = data / "analysis" / scope_id / "demand"
        invoke("demand-analysis", run_demand, scope, data, store, module_by_record,
               source_inputs, demand_dir, self.ir_worker)

        effect_paths = sorted((thread_dir / "effects/summaries").glob("*.json")) if thread_dir else []
        effect_documents = [_json_document(path) for path in effect_paths]
        effect_complete = evidence_complete(effect_documents)
        diagnostics.extend(adapt_diagnostics([item for value in effect_documents for item in
            [*value.get("diagnostics", []), *value.get("frontier", [])]], stage="effect-summary", scope_id=scope_id))
        effect_item = ([] if effect_complete else [diagnostic(
            "effect-summary-unavailable", "效果摘要不可用", "Effect summaries are unavailable",
            stage="effect-summary", scope_id=scope_id)])
        stage_results.append(_stage_result(planned["effect-summary"],
                                           "complete" if effect_complete else "unknown",
                                           frontier=effect_item, cache="disabled" if not effect_complete else "miss"))
        frontier.extend(effect_item)
        graph_path = data / f"graphs/{scope_id}.json"
        graph_document = _json_document(graph_path) if graph_path.is_file() else None
        graph_complete = evidence_complete([graph_document] if graph_document is not None else [])
        if graph_document:
            diagnostics.extend(adapt_diagnostics([*graph_document.get("diagnostics", []),
                *graph_document.get("frontier", [])], stage="thread-context", scope_id=scope_id))
        graph_item = ([] if graph_complete else [diagnostic(
            "thread-context-unavailable", "线程上下文图不可用", "Thread-context graph is unavailable",
            stage="thread-context", scope_id=scope_id)])
        stage_results.append(_stage_result(planned["thread-context"],
                                           "complete" if graph_complete else "unknown",
                                           frontier=graph_item, cache="disabled" if not graph_complete else "miss"))
        frontier.extend(graph_item)

        invoke("cpp-thread-lifecycle", run_cpp_lifecycle, scope, data, store, module_by_record,
               source_inputs, data / "analysis" / scope_id / "cpp-thread")
        invoke("raii-synchronization", run_raii, scope, data, store, module_by_record,
               data / "analysis" / scope_id / "raii")
        invoke("object-provenance", run_provenance, scope, data, store, module_by_record,
               source_inputs, data / "analysis" / scope_id / "provenance",
               self.source_worker, self.ir_worker)
        concurrent_report = invoke("concurrent-access", run_concurrent, scope, data,
                                   module_by_record, source_inputs,
                                   data / "analysis" / scope_id / "concurrent")
        publication_report = invoke("publication-risk", run_publication, scope, data,
                                    data / "analysis" / scope_id / "publication", self.ir_worker, thread_request_path)
        atomic_reports = invoke("advanced-atomic", run_atomic, scope, data,
                                data / "analysis" / scope_id / "advanced-atomic")

        candidates, formal, bounded = [], [], []
        location_scope = {**scope, "records": [
            {**record, "source_path_map": source_inputs.get(record["record_id"], {})
             .get("request", {}).get("profile", {}).get("path_map", [])}
            for record in scope["records"]]}
        if degraded_report:
            candidate_dir = data / "degraded" / scope_id / "source-candidates"
            raw_candidates = []
            for reference in degraded_report.get("source_candidates", []):
                candidate_path = candidate_dir / f"{reference['id']}.json"
                candidate = _json_document(candidate_path) if candidate_path.is_file() else reference
                raw_candidates.append(candidate)
            accepted, admission = admit_candidates(raw_candidates)
            write_json(store, admission, f"candidate-admission/{scope_id}.json")
            for candidate in accepted:
                prov = [provenance("DegradedSourceCandidate", candidate["id"],
                                   "org.rvport.memory-order-analyzer.degraded-source", 1,
                                   candidate.get("semantic_digest") or identity(candidate))]
                locations = candidate_locations(candidate, source_facts, location_scope, snapshots or {},
                                                output_root or data.parent, request, bundle["manifest_path"].parent)
                candidates.append(project_source_candidate(scope_id, candidate, prov, locations=locations))
        layer_refs = {}
        layer_paths = {
            "root": data / f"execution-roots/{scope_id}.json",
            "thread_instance": data / f"graphs/{scope_id}.json",
            "mhp": data / f"graphs/{scope_id}.json",
            "access": data / f"analysis/{scope_id}/concurrent/candidate-graph.json",
            "object": data / f"provenance-graphs/{scope_id}.json",
            "synchronization": data / f"analysis/{scope_id}/concurrent/access-protection.json",
            "thread_creation": data / f"thread-entry-sites/{scope_id}.json",
            "callback": data / f"thread-entry-sites/{scope_id}.json",
        }
        for layer, path in layer_paths.items():
            if path.is_file():
                value = _json_document(path)
                layer_refs[layer] = {"kind": value.get("kind"), "id": value.get("semantic_digest") or identity(value)}
        projection_gaps = []

        def project_with_locations(assessment, prov, **kwargs):
            locations = assessment_locations(assessment, location_scope, module_by_record, data,
                                             snapshots or {}, output_root or data.parent, request, _json_document,
                                             bundle["manifest_path"].parent)
            return project_pipeline_assessment(scope_id, assessment, prov, locations=locations, **kwargs)

        def adopt_projection(projected, expected, collection):
            if projected["conclusion"]["verdict"] == expected:
                collection.append(projected)
                return
            projection_gaps.append(diagnostic(
                "projection-evidence-incomplete", "上游结论因证据层缺失而降级",
                "An upstream assessment was downgraded because an evidence layer is missing",
                stage="projection", scope_id=scope_id, references=[projected["id"]]))
            candidates.append(projected)

        if publication_report:
            prov = [provenance("PublicationRiskReport", scope_id,
                               "org.rvport.memory-order-analyzer.publication-risk", 1,
                               publication_report.get("semantic_digest") or identity(publication_report))]
            for assessment in publication_report.get("findings", []):
                adopt_projection(project_with_locations(assessment, prov,
                                                              category="formal", layers=layer_refs),
                                 "risk", formal)
            graph_dir = data / f"analysis/{scope_id}/publication/graphs"
            graph_paths = list(graph_dir.glob("*.json")) if graph_dir.is_dir() else []
            if graph_paths:
                graph_value = _json_document(graph_paths[0])
                for assessment in graph_value.get("assessments", []):
                    if assessment.get("status") == "discharged":
                        adopt_projection(project_with_locations(assessment, prov,
                                                                      category="discharged", layers=layer_refs),
                                         "discharged-within-bounded-model", bounded)
        for index, atomic_report in enumerate(atomic_reports or []):
            atomic_layers = {**layer_refs, "atomic": {"report": index}, "reads_from": {"report": index},
                             "modification_order": {"report": index}, "release_sequence": {"report": index}}
            prov = [provenance("FenceRmwPublicationReport", f"{scope_id}:{index}",
                               "org.rvport.memory-order-analyzer.fence-rmw-publication", 1,
                               atomic_report.get("semantic_digest") or identity(atomic_report))]
            for assessment in atomic_report.get("findings", []):
                adopt_projection(project_with_locations(assessment, prov,
                                                              category="formal", layers=atomic_layers, atomic=True),
                                 "risk", formal)
            overlay_path = data / f"analysis/{scope_id}/advanced-atomic"
            standard = atomic_report.get("language_standard")
            if standard:
                overlay_file = overlay_path / standard.replace("+", "p") / "advanced-publication-protocol-overlay.json"
                if overlay_file.is_file():
                    for assessment in _json_document(overlay_file).get("protocols", []):
                        if assessment.get("assessment") == "discharged-within-bounded-model":
                            adopt_projection(project_with_locations(
                                assessment, prov, category="discharged",
                                layers=atomic_layers, atomic=True),
                                "discharged-within-bounded-model", bounded)
        frontier.extend(projection_gaps)
        projection_status = "complete" if not projection_gaps and (formal or bounded or not frontier) else "unknown"
        projection_frontier = [] if projection_status == "complete" else [diagnostic(
            "projection-incomplete", "Finding 投影缺少完整上游证据", "Finding projection lacks complete upstream evidence",
            stage="projection", scope_id=scope_id)]
        stage_results.append(_stage_result(planned["projection"], projection_status,
                                           frontier=projection_frontier, cache="disabled"))
        frontier.extend(projection_frontier)
        scope_tokens = [scope_id, *[item["physical_tu_id"] for item in scope["records"]],
                        *[item["artifact_key"] for item in module_by_record.values()]]
        _attach_stage_outputs(stage_results, planned, data, scope_tokens)
        status = "failed" if all(item["mode"] == "failed" for item in tu_modes) else "partial" if frontier else "complete"
        record = unified_document(
            "ScopeAnalysisExecutionRecord", scope_id=scope_id, status=status,
            tu_modes=tu_modes, stages=sorted(stage_results, key=lambda item: item["stage_id"]),
            counts={"translation_units": len(tu_modes), "complete_tus": sum(item["status"] == "complete" for item in tu_modes),
                    "formal_findings": len(formal), "source_candidates": len(candidates),
                    "discharged_assessments": len(bounded),
                    "frontier": len(frontier)}, diagnostics=merge_diagnostics([*diagnostics, *frontier]),
            frontier=sorted(frontier, key=lambda item: (item["stage"] or "", item["code"])))
        return record, formal, candidates, bounded

    def _failed_scope(self, request, bundle, scope, exc, ingestion=None):
        code = getattr(exc, "code", "worker-crash")
        detail = getattr(exc, "detail", str(exc))
        stopped = code in {"analysis_cancelled", "analysis_deadline"}
        status = "cancelled" if code == "analysis_cancelled" else "partial" if stopped else "failed"
        published = self._ingestion_maps(ingestion) if ingestion else {}
        modes = [_mode(
            value,
            source_usable=(request["source_assistance"] != "disabled" and
                           value["record_id"] in bundle["source_requests"]),
            ir_usable=(value["record_id"] in published),
        ) for value in scope["records"]]
        item = diagnostic(code, "Scope 分析中止" if stopped else "Scope 分析失败",
                          f"Scope analysis stopped: {detail}" if stopped else f"Scope analysis failed: {detail}",
                          stage="coordinator", scope_id=scope["target_id"])
        return unified_document(
            "ScopeAnalysisExecutionRecord", scope_id=scope["target_id"], status=status,
            tu_modes=modes, stages=[], counts={"translation_units": len(modes),
            "complete_tus": sum(value["status"] == "complete" for value in modes),
            "formal_findings": 0, "source_candidates": 0, "discharged_assessments": 0,
            "frontier": 1}, diagnostics=[item], frontier=[item])

    def _execute_scopes(self, request, plan, bundle, data, ingestion, source_inputs,
                        snapshots, output_root):
        """Run at most two disjoint Scope jobs and publish results deterministically."""
        scopes = sorted(bundle["scopes"], key=lambda item: item["target_id"])
        results, diagnostics = {}, []

        def analyze(scope):
            self._check_stop(request, "scope", scope["target_id"])
            cached, cache_diagnostic = self._load_scope_cache(request, bundle, scope, plan, data)
            if cache_diagnostic:
                diagnostics.append(cache_diagnostic)
            if cached is not None:
                return cached
            record, formal, source_only, bounded = self._scope(
                request, plan, bundle, scope, data, OutputStore(data), ingestion, source_inputs,
                snapshots, output_root)
            payload = _cache_payload(record, formal, source_only, bounded)
            return payload

        workers = min(2, len(scopes))
        with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="moa-scope") as executor:
            pending_scopes = iter(scopes)
            running = {}
            for _ in range(workers):
                scope = next(pending_scopes, None)
                if scope is not None:
                    running[executor.submit(analyze, scope)] = scope
            while running:
                done, _ = wait(running, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda item: running[item]["target_id"]):
                    scope = running.pop(future)
                    try:
                        results[scope["target_id"]] = future.result()
                    except Exception as exc:  # Scope boundary intentionally isolates worker crashes.
                        results[scope["target_id"]] = _cache_payload(
                            self._failed_scope(request, bundle, scope, exc, ingestion), [], [], [])
                    if not self._cancelled(request) and not self._deadline(request):
                        following = next(pending_scopes, None)
                        if following is not None:
                            running[executor.submit(analyze, following)] = following
            stop = (AnalysisError("analysis_cancelled", "Analysis was cancelled") if self._cancelled(request) else
                    AnalysisError("analysis_deadline", "Analysis deadline expired") if self._deadline(request) else None)
            for scope in pending_scopes:
                results[scope["target_id"]] = _cache_payload(
                    self._failed_scope(request, bundle, scope, stop, ingestion), [], [], [])
        if all(results[item["target_id"]]["record"]["status"] == "complete" for item in scopes):
            for scope in scopes:
                payload = results[scope["target_id"]]
                self._store_scope_cache(request, bundle, scope, plan, payload, data)
        return [results[item["target_id"]] for item in scopes], diagnostics

    def run(self):
        self.started = self.clock()
        request = read_unified_document(self.request_path, "UnifiedMemoryOrderAnalysisRequest")
        bundle = preflight_bundle(request, self.request_path.parent)
        plan = build_plan(request, bundle)
        with atomic_analysis_output(self.output) as workspace:
            data, store = workspace / "data", OutputStore(workspace)
            write_json(store, request, "request.json")
            write_json(store, plan, "plan.json")
            ingestion = None
            try:
                self._check_stop(request, "ingest")
                ingestion = self.ingest(bundle["manifest_path"], data, self.ir_worker,
                                        cache_path=self.cache_path)
                source_inputs = self._write_request_inputs(request, bundle, data, OutputStore(data))
                snapshots, snapshot_failures = self._snapshot_sources(bundle, store)
                payloads, run_diagnostics = self._execute_scopes(
                    request, plan, bundle, data, ingestion, source_inputs, snapshots, workspace)
            except AnalysisError as exc:
                if exc.code not in {"analysis_cancelled", "analysis_deadline"}:
                    raise
                source_inputs, snapshots, snapshot_failures, run_diagnostics = {}, {}, {}, []
                payloads = [_cache_payload(self._failed_scope(request, bundle, scope, exc, ingestion), [], [], [])
                            for scope in bundle["scopes"]]

            records, findings, candidates, discharged = [], [], [], []
            for scope, payload in zip(sorted(bundle["scopes"], key=lambda item: item["target_id"]), payloads):
                record = payload["record"]
                findings.extend(payload["findings"]); candidates.extend(payload["source_candidates"])
                discharged.extend(payload["discharged_assessments"])
                relative = f"scopes/{scope['target_id']}/execution.json"
                write_json(store, record, relative)
                records.append(_reference("ScopeAnalysisExecutionRecord", scope["target_id"], record, relative,
                                          "org.rvport.memory-order-analyzer.coordinator"))
            limit = request["budgets"]["findings"]
            overflow = len(findings) + len(candidates) + len(discharged) > limit
            remaining = limit
            findings, remaining = sorted(findings, key=lambda item: item["id"])[:remaining], max(0, remaining - len(findings))
            candidates, remaining = sorted(candidates, key=lambda item: item["id"])[:remaining], max(0, remaining - len(candidates))
            discharged = sorted(discharged, key=lambda item: item["id"])[:remaining]
            for collection, directory in ((findings, "findings"), (candidates, "source-candidates"),
                                          (discharged, "discharged-assessments")):
                for item in collection:
                    write_json(store, item, f"{directory}/{item['id'].replace(':', '_')}.json")
            scope_values = [payload["record"] for payload in payloads]
            frontier = [item for value in scope_values for item in value["frontier"]]
            for record_id, exc in snapshot_failures.items():
                frontier.append(diagnostic(exc.code, "源码快照不可用", f"Source snapshot unavailable: {exc.detail}",
                                           stage="projection", references=[record_id]))
            if overflow:
                frontier.append(diagnostic("finding-budget-exhausted", "Finding 输出预算耗尽",
                                           "The Finding output budget was exhausted", stage="projection"))
            oversized = [item for item in workspace.rglob("*") if item.is_file() and
                         item.stat().st_size > request["budgets"]["artifact_bytes"]]
            if oversized or _tree_bytes(workspace) > request["budgets"]["request_output_bytes"]:
                frontier.append(diagnostic("output-budget-exhausted", "统一输出预算耗尽",
                                           "The unified output budget was exhausted", stage="coordinator",
                                           references=[item.relative_to(workspace).as_posix() for item in oversized]))
            frontier = sorted(frontier, key=lambda item: (item["scope_id"] or "", item["stage"] or "", item["code"]))
            all_diagnostics = merge_diagnostics([*run_diagnostics, *frontier,
                *[item for value in scope_values for item in value["diagnostics"]]])
            stopped_codes = {item["code"] for item in frontier}
            full_frontier_count = len(frontier)
            diagnostic_limit = request["budgets"]["frontier_items"]
            audit_path = "diagnostics/full.json"
            if max(len(all_diagnostics), len(frontier)) > diagnostic_limit:
                write_json(store, {"diagnostics": all_diagnostics, "frontier": frontier}, audit_path)
            frontier = bound_diagnostics(frontier, diagnostic_limit, audit_path)
            visible_diagnostics = bound_diagnostics(all_diagnostics, diagnostic_limit, audit_path)
            if len(all_diagnostics) > diagnostic_limit and len(frontier) < diagnostic_limit:
                frontier.append(visible_diagnostics[-1])
            unsupported = [item for item in frontier if "unsupported" in item["code"]]
            if "analysis_cancelled" in stopped_codes or self._cancelled(request):
                status = "cancelled"
            elif "analysis_deadline" in stopped_codes:
                status = "partial"
            elif all(value["status"] == "failed" for value in scope_values):
                status = "failed"
            elif any(value["status"] != "complete" for value in scope_values) or frontier:
                status = "partial"
            else:
                status = "complete"
            verdict = ("failed" if status == "failed" else
                       "inconclusive" if status in {"partial", "cancelled"} or candidates or frontier else
                       "risk" if findings else "no-finding-within-supported-model")
            exit_code = {"failed": 1, "risk": 3, "inconclusive": 2,
                         "no-finding-within-supported-model": 0}[verdict]
            artifact_entries = _artifact_index(workspace)
            artifact_index = {"schema_version": 1, "kind": "UnifiedArtifactIndex",
                              "entries": artifact_entries, "semantic_digest": identity(artifact_entries)}
            write_json(store, artifact_index, "artifacts.json")
            artifact_entries.append(_reference(
                "UnifiedArtifactIndex", bundle["manifest"]["bundle_id"], artifact_index, "artifacts.json",
                "org.rvport.memory-order-analyzer.coordinator"))
            artifact_entries.sort(key=lambda item: (item["kind"], item["id"]))
            report = unified_document(
                "UnifiedMemoryOrderAnalysisReport", project=request["project"],
                request_digest=request["semantic_digest"], bundle_id=bundle["manifest"]["bundle_id"],
                status=status, verdict=verdict, exit_code=exit_code,
                scope_records=sorted(records, key=lambda item: item["id"]),
                summary={"scopes": len(scope_values),
                         "translation_units": sum(len(value["tu_modes"]) for value in scope_values),
                         "formal_findings": len(findings), "source_candidates": len(candidates),
                         "discharged_assessments": len(discharged), "unsupported": len(unsupported),
                         "diagnostics_total": len(all_diagnostics), "frontier_total": full_frontier_count,
                         "frontier": len(frontier), "abstention": sum(value["status"] != "complete" for value in scope_values),
                         "snapshots": len(snapshots)},
                findings=findings, source_candidates=candidates, discharged_assessments=discharged,
                unsupported=unsupported, frontier=frontier,
                diagnostics=visible_diagnostics,
                artifacts=artifact_entries)
            write_json(store, report, "report.json")
        return report


def analyze_project(request_path, output, *, ir_worker="/output/build/moa-worker",
                    source_worker="/output/build/memory-order-source-worker", cache_path=None):
    return AnalysisCoordinator(request_path, output, ir_worker=ir_worker,
                               source_worker=source_worker, cache_path=cache_path).run()
