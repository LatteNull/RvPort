from copy import deepcopy
import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from conftest import success
from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash
from memory_order_analyzer.external_bitcode_contracts import (
    diagnostic, expected_external_bitcode_protocol, external_document,
)
from memory_order_analyzer.external_bitcode_ingestion import (
    artifact_identity, classify_bitcode, ingest_bundle, ingest_record,
    safe_bundle_file, stable_copy,
)
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.protocol import expected_protocol


PRODUCER = {"family": "clang", "version": "21.1.8", "llvm_version": "21.1.8",
            "host_triple": "x86_64-pc-linux-gnu"}


def make_record(root, record_id="tu-a", *, status="produced", module_kind="translation-unit",
                optimization="O0", target="x86_64-pc-linux-gnu", source=True, byte_count=None):
    bc = root / "bc" / f"{record_id}.bc"
    bc.parent.mkdir(exist_ok=True)
    bc.write_bytes(b"BC\xc0\xde" + record_id.encode())
    src = root / "src" / f"{record_id}.c"
    src.parent.mkdir(exist_ok=True)
    src.write_text("int value;\n")
    produced = status == "produced"
    return external_document(
        "ExternalBitcodeArtifactRecord", record_id=record_id,
        physical_tu_id=("a" if record_id == "tu-a" else "b") * 64, status=status,
        diagnostic=None if produced else diagnostic("external_" + ("artifact_missing" if status == "missing" else "build_failed"),
                                                    "上游缺失", "upstream missing", record_id=record_id),
        bitcode={"path": f"bc/{record_id}.bc", "sha256": file_hash(bc),
                 "bytes": bc.stat().st_size if byte_count is None else byte_count} if produced else None,
        producer=PRODUCER, target={"triple": target, "data_layout": "e-p:64:64", "abi": {}},
        language="c", standard="c17", optimization=optimization, debug="full",
        module_kind=module_kind,
        source={"path": f"src/{record_id}.c", "sha256": file_hash(src)} if source else None,
        compile_record_digest="d" * 64, input_digests={})


def write_bundle(root, records, *, scopes=True, max_bytes=None):
    refs = []
    for item in records:
        path = root / "records" / f"{item['record_id']}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(canonical(item) + "\n")
        refs.append({"path": f"records/{item['record_id']}.json", "sha256": file_hash(path)})
    refs.sort(key=lambda item: item["path"])
    target = records[0]["target"]["triple"]
    scope_values = ([{"target_id": "app", "record_ids": sorted(item["record_id"] for item in records),
                      "evidence": "unit build graph", "closed": True, "external_boundaries": [],
                      "target_triple": target}] if scopes else [])
    budgets = deepcopy(expected_external_bitcode_protocol()["budgets"])
    if max_bytes is not None:
        budgets["max_artifact_bytes"] = max_bytes
    bundle = external_document("ExternalBitcodeBundleManifest", bundle_id="unit-build", producer=PRODUCER,
                               records=refs, scopes=scope_values, budgets=budgets)
    path = root / "bundle.json"
    path.write_text(canonical(bundle) + "\n")
    return path


def worker(fixture_module, seen=None):
    def runner(argv, cwd, **kwargs):
        if seen is not None:
            seen.append(list(argv))
        if argv[-1] == "--protocol":
            return success(json.dumps(expected_protocol()))
        facts = {**fixture_module, "artifact_key": argv[2], "module_hash": file_hash(argv[1]),
                 "target": "x86_64-pc-linux-gnu", "layout": "e-p:64:64"}
        return success(json.dumps(facts))
    return runner


def test_safe_path_format_and_stable_copy(tmp_path):
    member = tmp_path / "a.bc"
    member.write_bytes(b"BC\xc0\xdeunit")
    assert safe_bundle_file(tmp_path, "a.bc") == member.resolve()
    assert classify_bitcode(member) == "raw-llvm-bitcode"
    for value in ("../a.bc", str(member.resolve()), "."):
        with pytest.raises(AnalysisError):
            safe_bundle_file(tmp_path, value)
    for data in (b"\x7fELFunit", b"MZunit", b"; ModuleID = 'x'", b"BC", b"not-bitcode"):
        member.write_bytes(data)
        with pytest.raises(AnalysisError) as caught:
            classify_bitcode(member)
        assert caught.value.code == "artifact_format_unsupported"
    member.write_bytes(b"BC\xc0\xdeunit")
    with pytest.raises(AnalysisError, match="exceeds"):
        stable_copy(member, tmp_path / "large.bc", file_hash(member), 4)
    with pytest.raises(AnalysisError, match="digest"):
        stable_copy(member, tmp_path / "wrong.bc", "0" * 64, 100)
    assert stable_copy(member, tmp_path / "copy.bc", file_hash(member), 100)[1] == member.stat().st_size


def test_symlink_and_nonregular_rejected(tmp_path):
    target = tmp_path / "target.bc"; target.write_bytes(b"BC\xc0\xdeunit")
    link = tmp_path / "link.bc"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(AnalysisError, match="symbolic"):
        safe_bundle_file(tmp_path, "link.bc")
    with pytest.raises(AnalysisError):
        safe_bundle_file(tmp_path, "missing.bc")
    empty = tmp_path / "empty.bc"; empty.touch()
    with pytest.raises(AnalysisError, match="nonempty"):
        safe_bundle_file(tmp_path, "empty.bc")
    assert safe_bundle_file(tmp_path, "missing.bc", allow_missing=True).name == "missing.bc"


def test_stable_copy_detects_toctou_without_publishing(tmp_path, monkeypatch):
    source = tmp_path / "input.bc"; source.write_bytes(b"BC\xc0\xdeunit")
    original = Path.stat
    calls = 0

    def changed(path, *args, **kwargs):
        nonlocal calls
        value = original(path, *args, **kwargs)
        if path == source:
            calls += 1
            if calls > 1:
                return SimpleNamespace(st_dev=value.st_dev, st_ino=value.st_ino,
                                       st_size=value.st_size, st_mtime_ns=value.st_mtime_ns + 1,
                                       st_mode=value.st_mode)
        return value

    monkeypatch.setattr(Path, "stat", changed)
    with pytest.raises(AnalysisError) as caught:
        stable_copy(source, tmp_path / "copy.bc", file_hash(source), 100)
    assert caught.value.code == "inputs_changed"


def test_identity_ignores_path_but_preserves_tu_and_profile(tmp_path):
    first = make_record(tmp_path)
    changed_path = deepcopy(first)
    changed_path["bitcode"]["path"] = "elsewhere/same.bc"
    changed_path["semantic_digest"] = "0" * 64
    assert artifact_identity(first, first["bitcode"]["sha256"]) == artifact_identity(changed_path, first["bitcode"]["sha256"])
    changed_tu = deepcopy(first); changed_tu["physical_tu_id"] = "f" * 64
    assert artifact_identity(first, first["bitcode"]["sha256"]) != artifact_identity(changed_tu, first["bitcode"]["sha256"])
    changed_profile = deepcopy(first); changed_profile["optimization"] = "O2"
    assert artifact_identity(first, first["bitcode"]["sha256"]) != artifact_identity(changed_profile, first["bitcode"]["sha256"])


def test_complete_bundle_scope_and_no_compiler_execution(tmp_path, fixture_module):
    record = make_record(tmp_path)
    bundle = write_bundle(tmp_path, [record])
    seen = []
    report = ingest_bundle(bundle, tmp_path / "out", "reader", runner=worker(fixture_module, seen))
    assert report["status"] == "complete" and report["exit_code"] == 0
    assert report["counts"]["planned"] == report["counts"]["published"] == 1
    assert report["scopes"][0]["status"] == "resolved" and report["findings"] is None
    assert all(argv[0] == "reader" for argv in seen)
    assert not any(token in " ".join(argv) for argv in seen for token in ("clang", "gcc", "llvm-link", "cmake", "ssh"))
    key = report["artifacts"][0]
    assert (tmp_path / "out" / "artifacts" / f"{key}.bc").is_file()
    assert (tmp_path / "out" / "facts" / f"{key}.json").is_file()


def test_partial_missing_linked_optimized_and_target_conflict(tmp_path, fixture_module):
    good = make_record(tmp_path, module_kind="linked", optimization="O2", source=False)
    missing = make_record(tmp_path, "tu-b", status="missing")
    bundle = write_bundle(tmp_path, [good, missing])
    report = ingest_bundle(bundle, tmp_path / "out", "reader", runner=worker(fixture_module))
    assert report["status"] == "partial" and report["exit_code"] == 2
    assert report["counts"]["planned"] == 2 and report["counts"]["published"] == 1
    assert {item["code"] for item in report["frontier"]} >= {
        "external_artifact_missing", "source_unavailable", "linked_or_lto_partial", "optimized_evidence_loss"}
    assert report["scopes"][0]["status"] == "partial"


def test_failed_format_hash_size_budget_and_worker(tmp_path, fixture_module):
    cases = []
    for name in ("format", "size", "worker"):
        root = tmp_path / name; root.mkdir()
        record = make_record(root, byte_count=999 if name == "size" else None)
        if name == "format":
            bc = root / record["bitcode"]["path"]
            bc.write_bytes(b"\x7fELFbad")
            record["bitcode"]["sha256"] = file_hash(bc)
            record["bitcode"]["bytes"] = bc.stat().st_size
            record["semantic_digest"] = __import__("memory_order_analyzer.external_bitcode_contracts", fromlist=["semantic_digest"]).semantic_digest(record)
        bundle = write_bundle(root, [record])
        runner = (lambda argv, *a, **k: success(json.dumps(expected_protocol())) if argv[-1] == "--protocol" else success(stderr="verify_failed: bad", code=1)) if name == "worker" else worker(fixture_module)
        report = ingest_bundle(bundle, root / "out", "reader", runner=runner)
        assert report["exit_code"] == 1 and report["counts"]["published"] == 0
        cases.append({item["code"] for item in report["frontier"]})
    assert "artifact_format_unsupported" in cases[0]
    assert "hash_mismatch" in cases[1]
    assert "verify_failed" in cases[2]


def test_cache_cold_warm_and_corruption(tmp_path, fixture_module):
    record = make_record(tmp_path)
    bundle = write_bundle(tmp_path, [record])
    cache = tmp_path / "cache"
    cold = ingest_bundle(bundle, tmp_path / "cold", "reader", cache_path=cache, runner=worker(fixture_module))
    warm = ingest_bundle(bundle, tmp_path / "warm", "reader", cache_path=cache, runner=worker(fixture_module))
    assert cold["cache"] == {"hits": 0, "misses": 1}
    assert warm["cache"] == {"hits": 1, "misses": 0}
    assert cold["semantic_digest"] == warm["semantic_digest"]
    cached_module = next(cache.glob("external/*/module.bc"))
    cached_module.write_bytes(b"corrupt")
    corrupt = ingest_bundle(bundle, tmp_path / "corrupt", "reader", cache_path=cache, runner=worker(fixture_module))
    assert corrupt["status"] == "failed"
    assert corrupt["frontier"][0]["code"] == "cache_corrupt"


def test_cache_identity_includes_ingestion_budget(tmp_path, fixture_module):
    record = make_record(tmp_path)
    bundle = write_bundle(tmp_path, [record])
    cache = tmp_path / "cache"
    first = ingest_bundle(bundle, tmp_path / "first", "reader", cache_path=cache,
                          runner=worker(fixture_module))
    value = json.loads(bundle.read_text())
    value["budgets"]["max_worker_seconds"] -= 1
    semantic = __import__("memory_order_analyzer.external_bitcode_contracts",
                          fromlist=["semantic_digest"]).semantic_digest
    value["semantic_digest"] = semantic(value)
    bundle.write_text(canonical(value) + "\n")
    second = ingest_bundle(bundle, tmp_path / "second", "reader", cache_path=cache,
                           runner=worker(fixture_module))
    assert first["cache"] == second["cache"] == {"hits": 0, "misses": 1}
    assert len(list(cache.glob("external/*/module.bc"))) == 2


def test_incomplete_cache_source_error_and_post_reader_change_are_conservative(tmp_path, fixture_module):
    record = make_record(tmp_path)
    bundle = write_bundle(tmp_path, [record])
    cache = tmp_path / "cache"
    ingest_bundle(bundle, tmp_path / "cold", "reader", cache_path=cache,
                  runner=worker(fixture_module))
    next(cache.glob("external/*/facts.json")).unlink()
    report = ingest_bundle(bundle, tmp_path / "incomplete", "reader", cache_path=cache,
                           runner=worker(fixture_module))
    assert report["frontier"][0]["code"] == "cache_corrupt"

    direct_root = tmp_path / "direct"; direct_root.mkdir()
    unsafe = make_record(direct_root)
    unsafe["source"]["path"] = "../outside.c"
    artifact, _, _ = ingest_record(unsafe, direct_root, OutputStore(direct_root / "out"), "reader",
                                   runner=worker(fixture_module))
    assert artifact["toolchain"]["source"] is None

    changed_root = tmp_path / "changed"; changed_root.mkdir()
    changed = make_record(changed_root)
    member = changed_root / changed["bitcode"]["path"]

    def changing(argv, cwd, **kwargs):
        result = worker(fixture_module)(argv, cwd, **kwargs)
        if argv[-1] != "--protocol":
            member.write_bytes(member.read_bytes() + b"x")
        return result

    with pytest.raises(AnalysisError) as caught:
        ingest_record(changed, changed_root, OutputStore(changed_root / "out"), "reader",
                      runner=changing)
    assert caught.value.code == "inputs_changed"


def test_worker_budgets_and_partial_or_open_results_are_not_cached(tmp_path, fixture_module):
    record = make_record(tmp_path)
    bundle = write_bundle(tmp_path, [record])
    value = json.loads(bundle.read_text())
    value["scopes"][0]["closed"] = False
    value["scopes"][0]["external_boundaries"] = [{"kind": "unit-open"}]
    semantic = __import__("memory_order_analyzer.external_bitcode_contracts",
                          fromlist=["semantic_digest"]).semantic_digest
    value["semantic_digest"] = semantic(value)
    bundle.write_text(canonical(value) + "\n")
    seen = []
    ingest_bundle(bundle, tmp_path / "open", "reader", cache_path=tmp_path / "cache",
                  runner=worker(fixture_module, seen))
    extraction = [argv for argv in seen if argv[-1] != "--protocol"]
    assert extraction and not list((tmp_path / "cache").glob("external/*/module.bc"))

    partial_root = tmp_path / "partial"; partial_root.mkdir()
    partial = make_record(partial_root)
    partial_bundle = write_bundle(partial_root, [partial])
    partial_facts = deepcopy(fixture_module)
    partial_facts["values"] = [{"id": "unknown", "kind": "unknown", "type": "i32",
                                "type_kind": "integer", "bits": 32, "function": None,
                                "block": None, "operands": [], "details": {},
                                "status": "unknown", "reason": "unit"}]
    partial_facts["extraction"] = {"status": "partial", "roots": 0, "nodes": 1,
                                   "references": 0, "unknown": 1,
                                   "diagnostics": [{"id": "unknown", "reason": "unit"}]}
    report = ingest_bundle(partial_bundle, partial_root / "out", "reader",
                           cache_path=partial_root / "cache", runner=worker(partial_facts))
    assert report["status"] == "partial", report["diagnostics"]
    assert not list((partial_root / "cache").glob("external/*/module.bc"))


def test_worker_budget_and_protocol_incompatibility_are_reported(tmp_path, fixture_module):
    record = make_record(tmp_path)
    bundle = write_bundle(tmp_path, [record])
    seen = []

    def timed(argv, cwd, **kwargs):
        seen.append((argv, kwargs))
        if argv[-1] == "--protocol":
            return success(json.dumps(expected_protocol()))
        return {"status": "timed_out", "code": "timed_out", "exit_code": None,
                "stdout": "", "stderr": "reader exceeded budget"}

    report = ingest_bundle(bundle, tmp_path / "timed", "reader", runner=timed)
    assert report["frontier"][0]["code"] == "worker_budget"
    extraction = next(kwargs for argv, kwargs in seen if argv[-1] != "--protocol")
    assert extraction["timeout"] == expected_external_bitcode_protocol()["budgets"]["max_worker_seconds"]
    assert extraction["log_limit"] == expected_external_bitcode_protocol()["budgets"]["max_output_bytes"]

    other = tmp_path / "other"; other.mkdir()
    other_record = make_record(other)
    other_bundle = write_bundle(other, [other_record])
    incompatible = lambda argv, *args, **kwargs: success("{}")
    report = ingest_bundle(other_bundle, other / "out", "reader", runner=incompatible)
    assert report["frontier"][0]["code"] == "reader_incompatible"


def test_manifest_reference_and_output_failures(tmp_path, fixture_module):
    record = make_record(tmp_path)
    bundle = write_bundle(tmp_path, [record])
    (tmp_path / "out").mkdir()
    with pytest.raises(AnalysisError, match="new directory"):
        ingest_bundle(bundle, tmp_path / "out", "reader", runner=worker(fixture_module))
    manifest = json.loads(bundle.read_text())
    manifest["records"][0]["sha256"] = "0" * 64
    manifest["semantic_digest"] = __import__("memory_order_analyzer.external_bitcode_contracts", fromlist=["semantic_digest"]).semantic_digest(manifest)
    bundle.write_text(canonical(manifest))
    with pytest.raises(AnalysisError, match="record digest"):
        ingest_bundle(bundle, tmp_path / "tampered", "reader", runner=worker(fixture_module))
