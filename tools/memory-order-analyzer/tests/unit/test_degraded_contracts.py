import json
from copy import deepcopy

import pytest

import memory_order_analyzer.degraded_cache as cache_module
from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.degraded_cache import DegradedAnalysisCache, cache_key
from memory_order_analyzer.degraded_contracts import (
    classify_failure, degraded_document, dependency, diagnostic, expected_degraded_protocol,
    failure_record, input_hash, semantic_digest, stage_counts, validate_degraded_document,
)
from memory_order_analyzer.source_profile import build_profile


def budgets(**overrides):
    value = dict(expected_degraded_protocol()["budgets"])
    value.update(overrides)
    return value


def request(tmp_path):
    source_request = tmp_path / "source.json"
    source_request.write_text("{}", encoding="utf-8")
    return degraded_document(
        "DegradedSourceAnalysisRequest", scope_id="scope",
        source_requests=[input_hash(source_request)], ir_requests=[], module_facts=[],
        declared_failures=[], products={"thread_graph": None, "publication_graph": None,
                                        "publication_report": None}, budgets=budgets())


def availability(mode="ast-only", *, status="partial", language="c", standard="c17"):
    return degraded_document(
        "TUEvidenceAvailability", scope_id="scope", physical_tu_id="tu",
        profile_id="a" * 64, language=language, standard=standard, mode=mode,
        products=[{"stage": stage, "status": "not-run", "dependency": None, "failure_ids": []}
                  for stage in sorted(("source", "bc", "p1", "p2", "p3", "p4"))],
        failures=[], dependencies=[], status=status, semantic_digest=None)


def report(status, formal=(), availabilities=()):
    exit_code = 1 if status == "failed" else 2 if status == "partial" else 3 if any(item["effective_status"] == "finding" for item in formal) else 0
    return degraded_document(
        "DegradedSourceAnalysisReport", scope_id="scope" if status != "failed" else None,
        request_hash="a" * 64 if status != "failed" else None, status=status,
        mode="failed" if not availabilities else "ast-only", exit_code=exit_code,
        safety="not-established", stages={},
        mode_counts={name: sum(item["id"] == name for item in availabilities)
                     for name in ("ast-ir", "ir-only", "ast-only", "failed")},
        availabilities=[{"kind": "TUEvidenceAvailability", "id": item["id"], "digest": "b" * 64}
                        for item in availabilities], source_candidates=[], synchronization_gaps=[],
        formal_assessments=list(formal), dependencies=[], diagnostics=[], frontier=[],
        cache={"hits": 0, "misses": 0}, semantic_digest=None)


def effective(status):
    seed = {"original": "assessment", "status": status}
    return {"id": identity(seed), "original_id": "assessment", "original_kind": "publication-order-risk",
            "original_status": status, "effective_status": status, "reason_codes": [],
            "physical_tu_ids": [], "gap_ids": [],
            "slice": {"roots": [], "items": [], "status": "complete", "missing": []},
            "detail": "中文", "detail_en": "English",
            "suggestion": "建议", "suggestion_en": "Suggestion"}


def test_protocol_counts_diagnostics_and_failure_taxonomy():
    protocol = expected_degraded_protocol()
    assert protocol["kinds"]["SourceCandidate"] == 1
    assert stage_counts(0)["ratio"] is None
    assert stage_counts(4, 2, 1, 1)["ratio"] == 0.5
    with pytest.raises(AnalysisError, match="exceed"):
        stage_counts(1, 2)
    with pytest.raises(AnalysisError, match="non-negative"):
        stage_counts(-1)
    item = diagnostic("x", "中文" * 20, "English" * 20, limit=20)
    assert len(item["detail"].encode()) <= 20 and len(item["detail_en"].encode()) <= 20
    cases = {
        "timeout": "worker-budget", "profile replay": "profile-replay-incompatible",
        "syntax error": "frontend-invalid", "bitcode verify": "reader-incompatible",
        "external_artifact_missing": "external-artifact-missing",
        "external_build_failed": "external-build-failed",
        "artifact_format_unsupported": "artifact-format-unsupported",
        "worker_protocol": "reader-incompatible", "ir-generation-failed": "ir-generation-failed",
        "digest changed": "artifact-validation-failed", "other": "analysis-stage-failed",
    }
    assert {text: classify_failure(text)[0] for text in cases} == cases
    failure = failure_record("tu", "p3", "timeout", "too slow", limit=128)
    assert failure["stability"] == "transient" and failure["detail_en"] and failure["suggestion"]


def test_request_is_strict_versioned_sorted_and_digest_stable(tmp_path):
    value = request(tmp_path)
    assert value == validate_degraded_document(deepcopy(value), value["kind"])
    assert semantic_digest(value) == semantic_digest(deepcopy(value))
    changed_cache = report("failed")
    digest = changed_cache["semantic_digest"]
    changed_cache["cache"]["hits"] = 42
    assert semantic_digest(changed_cache) == digest
    invalid = deepcopy(value); invalid["extra"] = True
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_degraded_document(invalid, invalid["kind"])
    invalid = deepcopy(value); invalid["schema_version"] = 2
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_degraded_document(invalid, invalid["kind"])
    duplicate = deepcopy(value); duplicate["source_requests"] *= 2
    with pytest.raises(AnalysisError, match="unique"):
        validate_degraded_document(duplicate, duplicate["kind"])
    (tmp_path / "source.json").write_text('{"changed":true}', encoding="utf-8")
    with pytest.raises(AnalysisError, match="changed"):
        validate_degraded_document(value, value["kind"])


def test_availability_candidate_gap_and_report_semantics():
    assert availability()["mode"] == "ast-only"
    with pytest.raises(AnalysisError, match="language"):
        availability(language="c", standard="c++17")
    broken = availability(); broken["products"][0]["failure_ids"] = ["f" * 64]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="dangling"):
        validate_degraded_document(broken, broken["kind"])
    candidate = degraded_document(
        "SourceCandidate", scope_id="scope", id="1" * 64, physical_tu_ids=["tu"],
        profile_ids=["a" * 64], language="c", standard="c11", shape="atomic",
        node_ids=["node"], relation_ids=["relation"], evidence_level="source-only",
        verdict="unknown", safety="not-established", mode="ast-only",
        assumptions=["source-shape-only"], missing_evidence=["happens-before"],
        dependencies=[], diagnostics=[], suggestion="补齐证据", suggestion_en="Complete evidence",
        semantic_digest=None)
    assert candidate["verdict"] == "unknown" and "severity" not in candidate
    for language, standard in (("c", "c89"), ("c", "c99"),
                               ("c++", "c++98"), ("c++", "c++03")):
        legacy = deepcopy(candidate)
        legacy.update(language=language, standard=standard)
        legacy["semantic_digest"] = semantic_digest(legacy)
        validate_degraded_document(legacy, legacy["kind"])
    mismatch = deepcopy(candidate)
    mismatch.update(language="c", standard="c++98")
    mismatch["semantic_digest"] = semantic_digest(mismatch)
    with pytest.raises(AnalysisError, match="language and standard disagree"):
        validate_degraded_document(mismatch, mismatch["kind"])
    promoted = deepcopy(candidate); promoted["severity"] = "high"
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_degraded_document(promoted, promoted["kind"])
    gap = degraded_document(
        "SynchronizationGap", scope_id="scope", id="2" * 64, reason="mutex-kind-unknown",
        stage="p3", physical_tu_ids=[], node_ids=[], relation_ids=[], object_candidates=[],
        thread_candidates=[], path_candidates=[], budget=None, dependencies=[], detail="未知",
        detail_en="Unknown", suggestion="检查", suggestion_en="Inspect", semantic_digest=None)
    assert gap["reason"] == "mutex-kind-unknown"
    assert report("failed")["exit_code"] == 1
    assert report("complete", [effective("finding")], [{"id": "ast-only"}])["exit_code"] == 3
    invalid_report = report("complete", [], [{"id": "ast-only"}]); invalid_report["exit_code"] = 2
    invalid_report["semantic_digest"] = semantic_digest(invalid_report)
    with pytest.raises(AnalysisError, match="exit code"):
        validate_degraded_document(invalid_report, invalid_report["kind"])


def test_cache_keys_publish_load_corruption_stale_and_collision(tmp_path, monkeypatch):
    cache = DegradedAnalysisCache(tmp_path / "cache")
    value = availability()
    key = cache_key("availability", {"x": 1}, ["b", "a"])
    assert key == cache_key("availability", {"x": 1}, ["a", "b"])
    path = cache.publish("availability", key, value)
    assert cache.publish("availability", key, value) == path
    assert cache.load("availability", key, value["kind"], dependencies=[]) == value
    assert cache.load("availability", "missing", value["kind"]) is None
    with pytest.raises(AnalysisError, match="stale"):
        cache.load("availability", key, value["kind"], dependencies=[dependency("x", "y", {})])
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid"):
        cache.load("availability", key, value["kind"])
    path.unlink()
    cache.publish("availability", key, value)
    changed = deepcopy(value); changed["status"] = "complete"; changed["semantic_digest"] = semantic_digest(changed)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("availability", key, changed)
    with pytest.raises(AnalysisError, match="escapes"):
        cache._path("../escape", key)

    path.unlink()
    def racing(source, destination):
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        raise FileExistsError
    monkeypatch.setattr(cache_module.os, "link", racing)
    assert cache.publish("availability", key, value).is_file()
    path.unlink()
    def conflict_racing(source, destination):
        destination.write_text("{}", encoding="utf-8")
        raise FileExistsError
    monkeypatch.setattr(cache_module.os, "link", conflict_racing)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("availability", key, value)


def test_contract_loader_protocol_and_reference_failures(tmp_path):
    import memory_order_analyzer.degraded_contracts as contracts
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        contracts._load(tmp_path / "missing.json", "missing")
    bad_protocol = tmp_path / "protocol.json"; bad_protocol.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="does not match"):
        expected_degraded_protocol(bad_protocol)
    old_schema = contracts.SCHEMA
    broken_schema = tmp_path / "schema.json"; broken_schema.write_text('{"$defs":{"Budgets":{"properties":{"x":{}}}}}', encoding="utf-8")
    contracts.SCHEMA = broken_schema
    try:
        with pytest.raises(AnalysisError, match="schema is invalid"):
            expected_degraded_protocol()
    finally:
        contracts.SCHEMA = old_schema
    with pytest.raises(AnalysisError, match="Unknown"):
        validate_degraded_document({}, "UnknownKind")
    wrong = availability(); wrong["kind"] = "SourceCandidate"
    with pytest.raises(AnalysisError, match="Expected"):
        validate_degraded_document(wrong, "TUEvidenceAvailability")


@pytest.mark.parametrize("compiler", ["cl", "clang-cl", "mystery-cc"])
def test_profiles_explicitly_exclude_windows_and_unknown_compilers(tmp_path, compiler):
    source = tmp_path / "unit.c"; source.write_text("int x;", encoding="utf-8")
    with pytest.raises(AnalysisError, match="supported"):
        build_profile({"directory": str(tmp_path), "file": "unit.c",
                       "arguments": [compiler, "-std=c17", "-c", "unit.c"]}, compiler_version="1")
