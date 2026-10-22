"""Validate and publish externally produced raw LLVM bitcode without producing IR."""

from copy import deepcopy
from pathlib import Path
import shutil
import stat

from .contracts import AnalysisError, document, file_hash, identity, read_document
from .execution import OutputStore, run
from .external_bitcode_contracts import (
    diagnostic, external_document, expected_external_bitcode_protocol,
    read_external_document,
)
from .pipeline import read_facts, write_json
from .protocol import expected_protocol


LLVM_MAGIC = b"BC\xc0\xde"
CONTAINER_MAGICS = (b"\x7fELF", b"MZ", b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
                    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe")


def safe_bundle_file(root, relative, *, allow_missing=False):
    root = Path(root).resolve()
    value = Path(relative)
    if value.is_absolute() or not value.parts or any(part in ("", ".", "..") for part in value.parts):
        raise AnalysisError("path_unsafe", f"Bundle path must be a normalized relative path: {relative}")
    current = root
    for part in value.parts:
        current = current / part
        if current.is_symlink():
            raise AnalysisError("path_unsafe", f"Bundle path contains a symbolic link: {relative}")
    resolved = (root / value).resolve()
    if root not in resolved.parents:
        raise AnalysisError("path_unsafe", f"Bundle path escapes its root: {relative}")
    if allow_missing and not resolved.exists():
        return resolved
    try:
        mode = resolved.stat().st_mode
    except OSError as exc:
        raise AnalysisError("artifact_missing", str(resolved)) from exc
    if not stat.S_ISREG(mode) or resolved.stat().st_size == 0:
        raise AnalysisError("artifact_missing", f"Bundle member is not a nonempty regular file: {relative}")
    return resolved


def classify_bitcode(path):
    with Path(path).open("rb") as stream:
        prefix = stream.read(32)
    if prefix.startswith(LLVM_MAGIC):
        return "raw-llvm-bitcode"
    if any(prefix.startswith(magic) for magic in CONTAINER_MAGICS):
        raise AnalysisError("artifact_format_unsupported", "Object/container and GCC LTO inputs are not raw LLVM bitcode")
    if prefix.lstrip().startswith((b"; ModuleID", b"source_filename", b"target ")):
        raise AnalysisError("artifact_format_unsupported", "Textual LLVM IR is not accepted; provide raw .bc")
    if len(prefix) < len(LLVM_MAGIC):
        raise AnalysisError("artifact_format_unsupported", "Truncated bitcode input")
    raise AnalysisError("artifact_format_unsupported", "Input does not have raw LLVM bitcode magic")


def stable_copy(source, temporary, expected_hash, max_bytes):
    source, temporary = Path(source), Path(temporary)
    before = source.stat()
    if before.st_size > max_bytes:
        raise AnalysisError("budget_exceeded", f"Artifact exceeds max_artifact_bytes: {before.st_size}")
    import hashlib
    digest = hashlib.sha256()
    copied = 0
    with source.open("rb") as incoming, temporary.open("xb") as outgoing:
        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
            copied += len(chunk)
            if copied > max_bytes:
                raise AnalysisError("budget_exceeded", "Artifact grew beyond max_artifact_bytes")
            digest.update(chunk)
            outgoing.write(chunk)
    after = source.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise AnalysisError("inputs_changed", f"External artifact changed while reading: {source}")
    actual = digest.hexdigest()
    if actual != expected_hash or copied != before.st_size:
        raise AnalysisError("hash_mismatch", f"External artifact digest/size mismatch: {source}")
    return actual, copied


def artifact_identity(record, digest):
    protocol = expected_external_bitcode_protocol()
    semantic_record = deepcopy(record)
    semantic_record.pop("semantic_digest", None)
    if semantic_record.get("bitcode"):
        semantic_record["bitcode"] = {**semantic_record["bitcode"], "path": None}
    return identity({"bitcode": digest, "record": semantic_record,
                     "facts_protocol": expected_protocol(), "ingestion_protocol": protocol})


def _cache_key(artifact_key, context):
    return identity({"namespace": expected_external_bitcode_protocol()["cache_namespace"],
                     "artifact_key": artifact_key, "context": context})


def _cache_paths(cache, cache_key):
    root = f"external/{cache_key}"
    return (cache.path(f"{root}/artifact.json"), cache.path(f"{root}/facts.json"),
            cache.path(f"{root}/module.bc"))


def _copy_cached(cache, store, cache_key, artifact_key):
    artifact_path, facts_path, module_path = _cache_paths(cache, cache_key)
    try:
        artifact = read_document(artifact_path, "BCArtifact")
        facts = read_document(facts_path, "ModuleFacts")
    except (AnalysisError, OSError) as exc:
        raise AnalysisError("cache_corrupt", f"Unreadable external ingestion cache entry: {cache_key}") from exc
    source = Path(artifact["path"])
    if (source.resolve() != module_path.resolve()
            or artifact["artifact_key"] != artifact_key
            or facts["artifact_key"] != artifact_key
            or facts["module_hash"] != artifact["sha256"]
            or facts["extraction"].get("status") != "complete"
            or artifact["toolchain"].get("extraction") != expected_protocol()
            or artifact["toolchain"].get("ingestion") != expected_external_bitcode_protocol()
            or artifact["toolchain"].get("ingestion_cache_identity") != cache_key
            or not source.is_file() or file_hash(source) != artifact["sha256"]):
        raise AnalysisError("cache_corrupt", f"Invalid external ingestion cache entry: {cache_key}")
    with store.temporary() as temporary:
        staged = temporary / "module.bc"
        shutil.copyfile(source, staged)
        destination = store.publish(staged, f"artifacts/{artifact_key}.bc")
    artifact = {**artifact, "path": str(destination),
                "toolchain": {key: value for key, value in artifact["toolchain"].items()
                              if key != "ingestion_cache_identity"}}
    write_json(store, artifact, f"artifacts/{artifact_key}.json")
    write_json(store, facts, f"facts/{artifact_key}.json")
    return artifact, facts


def ingest_record(record, bundle_root, store, worker, *, cache=None, runner=run,
                  max_artifact_bytes=None, worker_seconds=None, output_bytes=None,
                  cache_context=None, cache_eligible=False):
    if record["status"] != "produced":
        raise AnalysisError("external_artifact_missing" if record["status"] == "missing" else "external_build_failed",
                            record["diagnostic"]["detail_en"])
    member = safe_bundle_file(bundle_root, record["bitcode"]["path"])
    classify_bitcode(member)
    key = artifact_identity(record, record["bitcode"]["sha256"])
    cache_key = _cache_key(key, cache_context or {})
    if cache and cache_eligible:
        cache_paths = _cache_paths(cache, cache_key)
        present = [path.exists() for path in cache_paths]
        if all(present):
            artifact, facts = _copy_cached(cache, store, cache_key, key)
            return artifact, facts, True
        if any(present):
            raise AnalysisError("cache_corrupt", f"Incomplete external ingestion cache entry: {cache_key}")
    source_path = None
    inputs = dict(record["input_digests"])
    if record["source"]:
        try:
            candidate = safe_bundle_file(bundle_root, record["source"]["path"])
            if file_hash(candidate) == record["source"]["sha256"]:
                source_path = candidate
                inputs[str(candidate)] = record["source"]["sha256"]
        except AnalysisError:
            pass
    with store.temporary() as temporary:
        staged = temporary / "module.bc"
        digest, copied = stable_copy(member, staged, record["bitcode"]["sha256"],
                                     max_artifact_bytes or expected_external_bitcode_protocol()["budgets"]["max_artifact_bytes"])
        if copied != record["bitcode"]["bytes"]:
            raise AnalysisError("hash_mismatch", "External artifact byte count differs from its record")
        facts = read_facts(staged, key, worker, inputs=inputs,
                           expected={"target": record["target"]["triple"],
                                     "layout": record["target"]["data_layout"]}, runner=runner,
                           timeout=worker_seconds, output_limit=output_bytes)
        if file_hash(member) != digest:
            raise AnalysisError("inputs_changed", f"External artifact changed after reader verification: {member}")
        destination = store.publish(staged, f"artifacts/{key}.bc")
    artifact = document(
        "BCArtifact", artifact_key=key, context_id=record["physical_tu_id"], path=str(destination),
        sha256=digest, profile="build-faithful", provenance="verified", inputs=inputs,
        toolchain={"external_record_id": record["record_id"], "producer_attested": record["producer"],
                   "target": record["target"]["triple"], "layout": record["target"]["data_layout"],
                   "abi": record["target"]["abi"], "language": record["language"],
                   "standard": record["standard"], "optimization": record["optimization"],
                   "debug": record["debug"], "module_kind": record["module_kind"],
                   "source": str(source_path) if source_path else None,
                   "compile_record_digest": record["compile_record_digest"],
                   "verified": {"sha256": digest, "format": "raw-llvm-bitcode",
                                "target": facts["target"], "data_layout": facts["layout"]},
                   "extraction": expected_protocol(), "ingestion": expected_external_bitcode_protocol()},
        lineage=[])
    write_json(store, artifact, f"artifacts/{key}.json")
    write_json(store, facts, f"facts/{key}.json")
    cacheable = (cache and cache_eligible and facts["extraction"]["status"] == "complete")
    if cacheable:
        with cache.temporary() as temporary:
            staged = temporary / "module.bc"
            shutil.copyfile(destination, staged)
            cached_destination = cache.publish(staged, f"external/{cache_key}/module.bc")
        cached_artifact = {**artifact, "path": str(cached_destination),
                           "toolchain": {**artifact["toolchain"],
                                         "ingestion_cache_identity": cache_key}}
        write_json(cache, cached_artifact, f"external/{cache_key}/artifact.json")
        write_json(cache, facts, f"external/{cache_key}/facts.json")
    return artifact, facts, False


def _source_binding(record, root):
    if not record["source"] or not record["compile_record_digest"]:
        return "unavailable"
    try:
        source = safe_bundle_file(root, record["source"]["path"])
        return "bound" if file_hash(source) == record["source"]["sha256"] else "mismatch"
    except AnalysisError:
        return "mismatch"


def _failure_diagnostic(exc, record_id=None):
    translations = {
        "external_artifact_missing": "外部 BC 未生成", "external_build_failed": "外部构建失败",
        "artifact_format_unsupported": "输入不是受支持的 raw LLVM BC", "hash_mismatch": "BC 摘要不匹配",
        "inputs_changed": "读取期间输入发生变化", "provenance_mismatch": "目标或 DataLayout 与声明不一致",
        "worker_protocol": "LLVM reader 协议不兼容", "reader_failed": "LLVM reader 无法读取输入",
        "verify_failed": "LLVM verify 失败", "reader_incompatible": "LLVM reader 不兼容",
        "worker_budget": "LLVM reader 预算耗尽", "budget_exceeded": "导入预算耗尽",
        "path_unsafe": "bundle 路径不安全", "artifact_missing": "bundle 文件缺失",
        "cache_corrupt": "导入缓存损坏",
    }
    code = {"worker_protocol": "reader_incompatible", "timed_out": "worker_budget",
            "log_limit": "worker_budget", "extraction_budget_exceeded": "worker_budget"}.get(exc.code, exc.code)
    return diagnostic(code, translations.get(code, "外部 BC 导入失败") + "：" + exc.detail,
                      exc.detail, record_id=record_id)


def _ratio(hit, total):
    return None if total == 0 else hit / total


def ingest_bundle(bundle_path, output, worker, *, cache_path=None, runner=run):
    bundle_path, output = Path(bundle_path).resolve(), Path(output)
    if output.exists():
        raise AnalysisError("output_exists", "Ingestion output must be a new directory")
    root = bundle_path.parent
    manifest = read_external_document(bundle_path, "ExternalBitcodeBundleManifest")
    store = OutputStore(output)
    cache = OutputStore(cache_path) if cache_path else None
    records, diagnostics = [], []
    referenced = set()
    for reference in manifest["records"]:
        path = safe_bundle_file(root, reference["path"])
        if file_hash(path) != reference["sha256"]:
            raise AnalysisError("hash_mismatch", f"Standalone record digest mismatch: {reference['path']}")
        record = read_external_document(path, "ExternalBitcodeArtifactRecord")
        if record["producer"] != manifest["producer"]:
            raise AnalysisError("provenance_mismatch", f"Record producer differs from bundle producer: {record['record_id']}")
        if record["record_id"] in referenced:
            raise AnalysisError("invalid_reference", f"Duplicate record_id: {record['record_id']}")
        referenced.add(record["record_id"])
        records.append(record)
    physical = [item["physical_tu_id"] for item in records]
    if len(physical) != len(set(physical)):
        raise AnalysisError("invalid_reference", "Duplicate physical_tu_id in bundle")
    for scope in manifest["scopes"]:
        missing = sorted(set(scope["record_ids"]) - referenced)
        if missing:
            raise AnalysisError("invalid_reference", f"Scope has dangling record references: {missing}")
    scoped = {record_id for scope in manifest["scopes"] for record_id in scope["record_ids"]}
    if referenced - scoped:
        raise AnalysisError("invalid_reference", f"Records are missing explicit scope membership: {sorted(referenced - scoped)}")
    records.sort(key=lambda item: item["record_id"])
    mappings, artifacts, facts_map = [], {}, {}
    hits = misses = total_bytes = 0
    for record in records:
        source_binding = _source_binding(record, root)
        memberships = [scope for scope in manifest["scopes"] if record["record_id"] in scope["record_ids"]]
        cache_context = {"budgets": manifest["budgets"], "scopes": memberships}
        cache_eligible = (bool(memberships) and source_binding == "bound"
                          and record["module_kind"] == "translation-unit"
                          and record["optimization"] in ("O0", "unknown")
                          and all(scope["closed"] and not scope["external_boundaries"]
                                  and scope["target_triple"] == record["target"]["triple"]
                                  for scope in memberships))
        if record["bitcode"]:
            total_bytes += record["bitcode"]["bytes"]
        if total_bytes > manifest["budgets"]["max_total_bytes"]:
            exc = AnalysisError("budget_exceeded", "Bundle exceeds max_total_bytes")
        else:
            exc = None
        try:
            if exc:
                raise exc
            artifact, facts, hit = ingest_record(
                record, root, store, worker, cache=cache, runner=runner,
                max_artifact_bytes=manifest["budgets"]["max_artifact_bytes"],
                worker_seconds=manifest["budgets"]["max_worker_seconds"],
                output_bytes=manifest["budgets"]["max_output_bytes"],
                cache_context=cache_context, cache_eligible=cache_eligible)
            hits += int(hit); misses += int(not hit)
            artifacts[record["record_id"]] = artifact
            facts_map[record["record_id"]] = facts
            facts_status = "complete" if facts["extraction"]["status"] == "complete" else "partial"
            mappings.append({"record_id": record["record_id"], "physical_tu_id": record["physical_tu_id"],
                             "producer_host": record["producer"]["host_triple"],
                             "target_triple": record["target"]["triple"],
                             "data_layout": record["target"]["data_layout"],
                             "status": "published", "artifact_key": artifact["artifact_key"],
                             "facts_status": facts_status, "source_binding": source_binding})
            if facts_status != "complete":
                diagnostics.append(diagnostic("facts_partial", "LLVM 事实提取不完整", "LLVM fact extraction is partial",
                                              record_id=record["record_id"]))
            if source_binding != "bound":
                diagnostics.append(diagnostic("source_" + source_binding, "源码绑定不可用或不匹配",
                                              "Source binding is unavailable or mismatched", record_id=record["record_id"]))
            if record["module_kind"] != "translation-unit":
                diagnostics.append(diagnostic("linked_or_lto_partial", "linked/LTO 输入仅支持低完整性 IR-only 分析",
                                              "Linked/LTO input is accepted only as partial IR-only evidence", record_id=record["record_id"]))
            if record["optimization"] not in ("O0", "unknown"):
                diagnostics.append(diagnostic("optimized_evidence_loss", "优化 BC 可能丢失源码访问证据",
                                              "Optimized bitcode may have lost source-level accesses", record_id=record["record_id"]))
        except (AnalysisError, OSError) as caught:
            exc = caught if isinstance(caught, AnalysisError) else AnalysisError("io_failed", str(caught))
            diagnostics.append(_failure_diagnostic(exc, record["record_id"]))
            mappings.append({"record_id": record["record_id"], "physical_tu_id": record["physical_tu_id"],
                             "producer_host": record["producer"]["host_triple"],
                             "target_triple": record["target"]["triple"],
                             "data_layout": record["target"]["data_layout"],
                             "status": "missing" if record["status"] == "missing" else "failed",
                             "artifact_key": None,
                             "facts_status": "not_run" if record["status"] != "produced" else "failed",
                             "source_binding": source_binding})
    scopes = []
    for scope in sorted(manifest["scopes"], key=lambda item: item["target_id"]):
        available = [artifacts[item]["artifact_key"] for item in scope["record_ids"] if item in artifacts]
        missing = sorted(set(scope["record_ids"]) - set(artifacts))
        conflicts = [item for item in scope["record_ids"] if item in artifacts and
                     facts_map[item]["target"] != scope["target_triple"]]
        status = "resolved" if available and not missing and not conflicts else "partial" if available else "failed"
        path = None
        if available:
            normalized = document("ScopeManifest", target_id=scope["target_id"], members=sorted(available),
                                  evidence=scope["evidence"] + "; normalized from external record membership",
                                  closed=scope["closed"] and not missing and not conflicts,
                                  external_boundaries=[*scope["external_boundaries"],
                                                       *([{"missing_records": missing}] if missing else [])],)
            path = str(write_json(store, normalized, f"scopes/{scope['target_id']}.json"))
        if conflicts:
            diagnostics.append(diagnostic("scope_target_conflict", "scope target 与成员 BC 不一致",
                                          "Scope target conflicts with member bitcode", references=conflicts))
        scopes.append({"target_id": scope["target_id"], "status": status, "path": path,
                       "members": sorted(available), "missing_records": sorted(set(missing + conflicts))})
    planned = len(records)
    counts = {
        "planned": planned, "produced": sum(item["status"] == "produced" for item in records),
        "missing": sum(item["status"] == "missing" for item in records),
        "upstream_failed": sum(item["status"] == "failed" for item in records),
        "hash_failed": sum(item["code"] == "hash_mismatch" for item in diagnostics),
        "format_failed": sum(item["code"] == "artifact_format_unsupported" for item in diagnostics),
        "reader_failed": sum(item["code"] in {"reader_failed", "verify_failed", "reader_incompatible", "worker_budget"} for item in diagnostics),
        "published": len(artifacts),
        "facts_complete": sum(item["facts_status"] == "complete" for item in mappings),
        "facts_partial": sum(item["facts_status"] == "partial" for item in mappings),
        "facts_failed": sum(item["facts_status"] == "failed" for item in mappings),
        "source_bound": sum(item["source_binding"] == "bound" for item in mappings),
        "scope_resolved": sum(item["status"] == "resolved" for item in scopes),
    }
    counts.update({
        "hash_valid": max(0, counts["produced"] - counts["hash_failed"]),
        "format_valid": max(0, counts["produced"] - counts["hash_failed"] - counts["format_failed"]),
        "parsed": counts["published"], "verified": counts["published"],
    })
    relevant = [item for item in diagnostics if item["relevant"]]
    if not artifacts:
        status, exit_code = "failed", 1
    elif relevant or len(artifacts) != planned or any(item["status"] != "resolved" for item in scopes):
        status, exit_code = "partial", 2
    else:
        status, exit_code = "complete", 0
    report = external_document(
        "ExternalBitcodeIngestionReport", bundle_id=manifest["bundle_id"], status=status,
        exit_code=exit_code, semantic_analysis="not_run", safety="not_evaluated", findings=None,
        counts=counts, ratios={"published": _ratio(counts["published"], planned),
                               "facts_complete": _ratio(counts["facts_complete"], planned),
                               "source_bound": _ratio(counts["source_bound"], planned),
                               "scope_resolved": _ratio(counts["scope_resolved"], len(scopes))},
        record_artifacts=sorted(mappings, key=lambda item: item["record_id"]), scopes=scopes,
        artifacts=sorted(item["artifact_key"] for item in artifacts.values()),
        cache={"hits": hits, "misses": misses}, frontier=relevant, diagnostics=diagnostics)
    write_json(store, report, "report.json")
    return report
