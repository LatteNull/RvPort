from copy import deepcopy
import json

import pytest

from memory_order_analyzer.cli import main
from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash, identity
from memory_order_analyzer.index_source_evidence import failed_source_report, index_source_evidence
from memory_order_analyzer.pipeline import write_json
from memory_order_analyzer.source_contracts import counts, dependency, expected_source_protocol, source_document
from memory_order_analyzer.source_profile import build_profile


def request_fixture(tmp_path, fixture_module, members=1):
    store = tmp_path / "store"
    (store / "facts").mkdir(parents=True)
    artifact = fixture_module["artifact_key"]
    (store / "facts" / f"{artifact}.json").write_text(canonical(fixture_module), encoding="utf-8")
    source_paths = []
    requests = []
    for ordinal in range(members):
        source = tmp_path / f"unit{ordinal}.c"
        source.write_text(f"int value_{ordinal};\n", encoding="utf-8")
        profile = build_profile({"directory": str(tmp_path), "file": source.name,
                                 "arguments": ["gcc", "-std=c17", "-c", source.name]},
                                compiler_version="13")
        physical = f"{ordinal + 1:064x}"
        request = source_document("SourceSemanticRequest", profile=profile,
                                  physical_tu_id=physical, source_path=str(source.resolve()),
                                  budgets=expected_source_protocol()["budgets"])
        path = tmp_path / f"source-request-{ordinal}.json"
        path.write_text(canonical(request), encoding="utf-8")
        source_paths.append(path.name)
        requests.append(request)
    wrapper = source_document(
        "AstAssistedAnalysisRequest", scope_id="scope", source_requests=source_paths,
        module_facts=[dependency("ModuleFacts", artifact, fixture_module)],
        budgets=expected_source_protocol()["budgets"])
    wrapper_path = tmp_path / "request.json"
    wrapper_path.write_text(canonical(wrapper), encoding="utf-8")
    return store, wrapper_path, requests


def empty_facts(request):
    return source_document(
        "SourceSemanticFacts", profile_id=request["profile"]["profile_id"],
        physical_tu_id=request["physical_tu_id"], source_digest=request["profile"]["source"]["sha256"],
        status="complete", nodes=[], relations=[], counts={"nodes": counts(0)},
        diagnostics=[], frontier=[], semantic_digest=None)


def add_ir_request(tmp_path, wrapper_path, source_request, artifact):
    bitcode = tmp_path / f"{artifact}.bc"
    bitcode.write_bytes(b"fixture bitcode")
    request = source_document(
        "LLVMSourceBindingRequest", artifact_key=artifact,
        profile_id=source_request["profile"]["profile_id"],
        physical_tu_id=source_request["physical_tu_id"],
        bitcode={"path": str(bitcode), "sha256": file_hash(bitcode)},
        budgets=expected_source_protocol()["budgets"])
    path = tmp_path / "ir-request.json"
    path.write_text(canonical(request), encoding="utf-8")
    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    wrapper["ir_requests"] = [path.name]
    wrapper_path.write_text(canonical(wrapper), encoding="utf-8")
    return request


def empty_ir_facts(request):
    return source_document(
        "LLVMSourceBindingFacts", artifact_key=request["artifact_key"],
        profile_id=request["profile_id"], physical_tu_id=request["physical_tu_id"],
        bitcode_digest=request["bitcode"]["sha256"], target="x86_64-pc-linux-gnu",
        data_layout="", status="complete", symbols=[], counts={"symbols": counts(0)},
        diagnostics=[], frontier=[], semantic_digest=None)


def test_orchestration_cold_warm_and_deterministic_outputs(tmp_path, fixture_module):
    store, request_path, _ = request_fixture(tmp_path, fixture_module)
    calls = []

    def runner(request, worker, directory):
        calls.append(request["physical_tu_id"])
        return empty_facts(request)

    cold = index_source_evidence(request_path, store, tmp_path / "cold", "worker", runner=runner)
    warm = index_source_evidence(request_path, store, tmp_path / "warm", "worker", runner=runner)
    assert cold["status"] == warm["status"] == "complete"
    assert cold["semantic_digest"] == warm["semantic_digest"]
    assert cold["cache"]["misses"] == 4 and warm["cache"]["hits"] == 4
    assert len(calls) == 1
    assert (tmp_path / "cold" / "canonical-object-overlay.json").is_file()
    assert json.loads((tmp_path / "warm" / "report.json").read_text())["exit_code"] == 0


def test_orchestration_preserves_failed_member_denominator(tmp_path, fixture_module):
    store, request_path, requests = request_fixture(tmp_path, fixture_module, members=2)

    def runner(request, worker, directory):
        if request["physical_tu_id"] == requests[1]["physical_tu_id"]:
            raise AnalysisError("clang-replay-failed", "missing include")
        return empty_facts(request)

    report = index_source_evidence(request_path, store, tmp_path / "partial", "worker", runner=runner)
    assert report["status"] == "partial" and report["exit_code"] == 2
    layer = report["layers"]["source_extraction"]["counts"]
    assert layer["planned"] == 2 and layer["emitted"] == 1 and layer["failed"] == 1
    assert report["diagnostics"][0]["detail_en"].startswith("Source semantic member failed")


def test_orchestration_indexes_and_caches_typed_llvm_facts(tmp_path, fixture_module):
    store, request_path, requests = request_fixture(tmp_path, fixture_module)
    ir_request = add_ir_request(tmp_path, request_path, requests[0], fixture_module["artifact_key"])
    calls = []

    def ir_runner(request, worker, directory):
        calls.append(request["artifact_key"])
        return empty_ir_facts(request)

    cold = index_source_evidence(request_path, store, tmp_path / "cold-ir", "worker",
                                 runner=lambda request, *_: empty_facts(request), ir_runner=ir_runner)
    warm = index_source_evidence(request_path, store, tmp_path / "warm-ir", "worker",
                                 runner=lambda request, *_: empty_facts(request), ir_runner=ir_runner)
    assert ir_request["artifact_key"] in calls and len(calls) == 1
    assert cold["layers"]["llvm_binding_facts"]["status"] == "complete"
    assert warm["cache"]["hits"] == 5
    assert (tmp_path / "cold-ir" / "llvm-binding-facts" / f"{ir_request['artifact_key']}.json").is_file()


def test_orchestration_rejects_ir_profile_mismatch_and_counts_failure(tmp_path, fixture_module):
    store, request_path, requests = request_fixture(tmp_path, fixture_module)
    add_ir_request(tmp_path, request_path, requests[0], fixture_module["artifact_key"])
    wrapper = json.loads(request_path.read_text(encoding="utf-8"))
    ir_path = tmp_path / wrapper["ir_requests"][0]
    ir_request = json.loads(ir_path.read_text(encoding="utf-8"))
    ir_request["profile_id"] = "f" * 64
    ir_path.write_text(canonical(ir_request), encoding="utf-8")
    with pytest.raises(AnalysisError, match="profile/TU"):
        index_source_evidence(request_path, store, tmp_path / "mismatch", "worker",
                              runner=lambda request, *_: empty_facts(request))

    ir_request["profile_id"] = requests[0]["profile"]["profile_id"]
    ir_path.write_text(canonical(ir_request), encoding="utf-8")
    report = index_source_evidence(
        request_path, store, tmp_path / "ir-failed", "worker",
        runner=lambda request, *_: empty_facts(request),
        ir_runner=lambda *args: (_ for _ in ()).throw(AnalysisError("worker", "failed")))
    assert report["status"] == "partial"
    assert report["layers"]["llvm_binding_facts"]["counts"]["failed"] == 1


def test_orchestration_rejects_existing_output_stale_module_and_all_failures(tmp_path, fixture_module):
    store, request_path, _ = request_fixture(tmp_path, fixture_module)
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(AnalysisError, match="fresh"):
        index_source_evidence(request_path, store, existing, "worker", runner=lambda *args: None)
    with pytest.raises(AnalysisError, match="All planned"):
        index_source_evidence(request_path, store, tmp_path / "failed", "worker",
                              runner=lambda *args: (_ for _ in ()).throw(AnalysisError("x", "failed")))
    wrapper = json.loads(request_path.read_text())
    wrapper["module_facts"][0]["digest"] = "0" * 64
    stale = tmp_path / "stale.json"
    stale.write_text(canonical(wrapper), encoding="utf-8")
    with pytest.raises(AnalysisError, match="changed"):
        index_source_evidence(stale, store, tmp_path / "stale-output", "worker",
                              runner=lambda request, *_: empty_facts(request))


def test_failed_report_and_cli_exit_codes(tmp_path, monkeypatch):
    failed = failed_source_report("bad", "错误", "error")
    assert failed["exit_code"] == 1 and failed["diagnostics"][0]["detail_en"] == "error"
    output = []
    code = main(["index-source-evidence"], stdout=type("Stream", (), {"write": lambda self, value: output.append(value)})(),
                stderr=type("Stream", (), {"write": lambda self, value: None})())
    assert code == 1 and json.loads("".join(output))["kind"] == "AstAssistedAnalysisReport"

    complete = source_document(
        "AstAssistedAnalysisReport", scope_id="scope", status="complete", exit_code=0,
        dependencies=[], layers={}, outputs=[], cache={"hits": 0, "misses": 0},
        diagnostics=[], frontier=[], semantic_digest=None)
    monkeypatch.setattr("memory_order_analyzer.cli.index_source_evidence", lambda *args: complete)
    out = []
    code = main(["index-source-evidence", "--request", "r", "--artifact-store", "s",
                 "--output", str(tmp_path / "out")],
                stdout=type("Stream", (), {"write": lambda self, value: out.append(value)})(),
                stderr=type("Stream", (), {"write": lambda self, value: None})())
    assert code == 0 and json.loads("".join(out))["status"] == "complete"
