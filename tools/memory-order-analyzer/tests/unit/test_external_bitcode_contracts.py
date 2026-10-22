from copy import deepcopy
import json

import pytest

from memory_order_analyzer.contracts import AnalysisError, file_hash
from memory_order_analyzer.external_bitcode_contracts import (
    diagnostic, expected_external_bitcode_protocol, external_document,
    failed_report, read_external_document, semantic_digest,
    validate_external_document,
)


PRODUCER = {"family": "clang", "version": "21.1.8", "llvm_version": "21.1.8",
            "host_triple": "x86_64-pc-linux-gnu"}


def record(**changes):
    fields = {
        "record_id": "tu-a", "physical_tu_id": "a" * 64, "status": "produced",
        "diagnostic": None, "bitcode": {"path": "bc/a.bc", "sha256": "b" * 64, "bytes": 8},
        "producer": PRODUCER, "target": {"triple": "x86_64-pc-linux-gnu",
        "data_layout": "e-p:64:64", "abi": {}}, "language": "c", "standard": "c17",
        "dialect": "iso", "standard_source": "explicit", "standard_option": "-std=c17",
        "optimization": "O0", "debug": "full", "module_kind": "translation-unit",
        "source": {"path": "src/a.c", "sha256": "c" * 64},
        "compile_record_digest": "d" * 64, "input_digests": {},
    }
    fields.update(changes)
    return external_document("ExternalBitcodeArtifactRecord", **fields)


def manifest(references=None, scopes=None, **changes):
    fields = {
        "bundle_id": "build-a", "producer": PRODUCER,
        "records": references if references is not None else [{"path": "records/a.json", "sha256": "e" * 64}],
        "scopes": scopes if scopes is not None else [{"target_id": "app", "record_ids": ["tu-a"], "evidence": "build graph",
                              "closed": True, "external_boundaries": [],
                              "target_triple": "x86_64-pc-linux-gnu"}],
        "budgets": expected_external_bitcode_protocol()["budgets"],
    }
    fields.update(changes)
    return external_document("ExternalBitcodeBundleManifest", **fields)


def test_protocol_documents_and_failure_report(tmp_path):
    assert expected_external_bitcode_protocol()["policy_id"] == "external-bitcode-ingestion-v1"
    value = record()
    assert value["semantic_digest"] == semantic_digest(value)
    path = tmp_path / "record.json"
    path.write_text(json.dumps(value))
    assert read_external_document(path, value["kind"]) == value
    report = failed_report("unit", "错误", "broken", bundle_id="build-a")
    assert report["exit_code"] == 1 and report["findings"] is None
    assert report["frontier"][0]["suggestion"] and report["frontier"][0]["suggestion_en"]
    with pytest.raises(AnalysisError):
        read_external_document(tmp_path / "absent", value["kind"])
    bad_protocol = tmp_path / "protocol.json"
    bad_protocol.write_text(json.dumps({"protocol_version": 99}))
    with pytest.raises(AnalysisError, match="does not match"):
        expected_external_bitcode_protocol(bad_protocol)


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(schema_version=3),
    lambda value: value.update(extra=True),
    lambda value: value.update(semantic_digest="0" * 64),
    lambda value: value.update(language="c++"),
    lambda value: value.update(status="missing"),
])
def test_record_rejects_version_unknown_digest_and_combinations(mutation):
    value = record()
    mutation(value)
    with pytest.raises(AnalysisError):
        validate_external_document(value, "ExternalBitcodeArtifactRecord")


def test_missing_record_and_manifest_cross_fields():
    missing = record(status="missing", bitcode=None,
                     diagnostic=diagnostic("external_artifact_missing", "缺失", "missing", record_id="tu-a"))
    assert missing["status"] == "missing"
    with pytest.raises(AnalysisError, match="at least one"):
        manifest(references=[])
    with pytest.raises(AnalysisError):
        manifest(scopes=[])
    with pytest.raises(AnalysisError, match="Duplicate"):
        manifest(references=[{"path": "a", "sha256": "a" * 64}, {"path": "a", "sha256": "b" * 64}])
    with pytest.raises(AnalysisError, match="sorted"):
        manifest(references=[{"path": "z", "sha256": "a" * 64}, {"path": "a", "sha256": "b" * 64}])
    with pytest.raises(AnalysisError, match="Duplicate"):
        manifest(scopes=[{"target_id": "app", "record_ids": ["tu-a"], "evidence": "a", "closed": True,
                          "external_boundaries": [], "target_triple": "x86_64"}] * 2)
    with pytest.raises(AnalysisError, match="Scopes must be sorted"):
        manifest(scopes=[{"target_id": key, "record_ids": ["tu-a"], "evidence": "a", "closed": True,
                          "external_boundaries": [], "target_triple": "x86_64"}
                         for key in ("z", "a")])


def test_language_standard_context_accepts_default_and_isolates_unsupported():
    default = record(standard="compiler-default", dialect="compiler-default",
                     standard_source="compiler-default", standard_option=None)
    assert default["standard"] == "compiler-default"
    unsupported = record(status="missing", bitcode=None, standard="unsupported",
                         dialect="iso", standard_source="explicit", standard_option="-std=vendor-c",
                         diagnostic=diagnostic("language_unsupported", "标准不受支持", "unsupported standard"))
    assert unsupported["status"] == "missing"
    with pytest.raises(AnalysisError, match="trusted bitcode"):
        record(standard="unsupported", dialect="iso", standard_source="explicit",
               standard_option="-std=vendor-c")
    with pytest.raises(AnalysisError, match="must not invent"):
        record(standard="c17", dialect="compiler-default", standard_source="compiler-default",
               standard_option=None)


def test_legacy_v1_record_remains_readable_but_cannot_claim_v2_language_context():
    legacy = external_document(
        "ExternalBitcodeArtifactRecord", schema_version=1,
        record_id="legacy", physical_tu_id="a" * 64, status="missing",
        diagnostic=diagnostic("external_artifact_missing", "缺失", "missing"), bitcode=None,
        producer=PRODUCER, target={"triple": "x86_64-pc-linux-gnu", "data_layout": "e", "abi": {}},
        language="c", standard="c17", optimization="O0", debug="none",
        module_kind="translation-unit", source=None, compile_record_digest="b" * 64,
        input_digests={})
    assert legacy["schema_version"] == 1
    broken = dict(legacy, dialect="iso", standard_source="explicit", standard_option="-std=c17")
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="v1"):
        validate_external_document(broken, "ExternalBitcodeArtifactRecord")


def test_report_status_cross_checks():
    base = failed_report("unit", "错误", "broken")
    for change in ({"exit_code": 0}, {"status": "partial", "exit_code": 2}):
        value = {**deepcopy(base), **change}
        value["semantic_digest"] = semantic_digest(value)
        with pytest.raises(AnalysisError):
            validate_external_document(value, value["kind"])
    with pytest.raises(AnalysisError):
        validate_external_document({}, "Unknown")
