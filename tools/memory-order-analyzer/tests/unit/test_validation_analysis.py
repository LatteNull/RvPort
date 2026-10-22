"""P5 truth, metrics, profile, backend and decision unit tests."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from memory_order_analyzer.contracts import AnalysisError, file_hash, identity
from memory_order_analyzer.validation_analysis import (
    aggregate_layers,
    aggregate_metrics,
    backend_bundle,
    bind_truth,
    case_input_digest,
    compare_backend,
    compare_case,
    extension_decision,
    import_devkit_evidence,
    layer_state,
    metric,
    materialize_compile_database,
    normalize_genmc_output,
    normalize_herdtools_output,
    public_case_result,
    safe_path,
    semantic_digest,
    stratified_sample,
    validate_real_project_profile,
    verify_entry,
)
from memory_order_analyzer.validation_contracts import CAPABILITIES, validation_document


H = "a" * 64


def assertion(code):
    return {"code": code, "object": None, "thread_relation": None, "evidence_relation": None}


def truth(required=(), forbidden=(), *, verdicts=("risk",), statuses=("complete",), unknown=()):
    return {"expected": {"required_findings": [assertion(code) for code in required],
                         "forbidden_findings": [assertion(code) for code in forbidden],
                         "verdicts": list(verdicts), "statuses": list(statuses), "unknown_codes": list(unknown)}}


def case(category="risk"):
    return {"id": "case", "profile_id": "c11", "category": category}


def assessment(code, status="finding"):
    return {"code": code, "status": status}


def report(verdict="risks_found", status="complete", frontier=()):
    return {"verdict": verdict, "risk_evaluation": status, "frontier": list(frontier)}


def graph(items=()):
    return {"assessments": list(items)}


def test_compare_complete_mismatch_unknown_and_metrics():
    matched = compare_case(case(), truth(["relaxed"]), report(), graph([assessment("relaxed")]))
    assert matched["matched"] and matched["_counts"] == {"tp": 1, "fp": 0, "fn": 0,
                                                           "supported_tp": 1, "supported_fp": 0, "supported_fn": 0}
    mismatch = compare_case(case(), truth(["missing"], ["forbidden"]), report(),
                            graph([assessment("extra"), assessment("forbidden")]))
    assert not mismatch["matched"] and mismatch["strict_fn"] == 1
    assert mismatch["_counts"]["fp"] == 2
    abstain = compare_case(case(), truth(["risk"], unknown=["pointer-analysis"]),
                           report("inconclusive", "partial", [{"code": "pointer-analysis"}]),
                           graph([assessment("pointer-analysis", "unknown")]))
    assert abstain["abstained"] and abstain["strict_fn"] == 1
    metrics = aggregate_metrics([matched, mismatch, abstain])
    assert metrics["true_positive"] == 1 and metrics["false_positive"] == 2
    assert metrics["recall"]["value"] == 1 / 3
    assert metric(0, 0)["value"] is None
    assert "_counts" not in public_case_result(matched)


def test_layer_denominators_and_partial_precedence():
    assert layer_state([]) == {"status": "not_run", "hit": 0, "total": 0}
    assert layer_state(["complete"])["status"] == "complete"
    assert layer_state(["failed"])["status"] == "failed"
    assert layer_state(["complete", "failed"])["status"] == "partial"
    rows = [{name: "complete" for name in ("request_input", "compile", "p1", "p2", "p3", "p4", "truth", "sampling", "performance", "backend")}]
    assert aggregate_layers(rows)["backend"]["status"] == "complete"
    rows[0]["p2"] = "partial"
    assert aggregate_layers(rows, True)["p2"] == {"status": "partial", "hit": 0, "total": 1}


def test_semantic_digest_normalizes_resources_and_paths(tmp_path):
    first = {"path": str(tmp_path / "a"), "wall_seconds": 1, "nested": {"peak_rss_bytes": 2, "value": 3}}
    second = {"path": "${ROOT}/a", "wall_seconds": 99, "nested": {"peak_rss_bytes": 200, "value": 3}}
    assert semantic_digest(first, roots=(("${ROOT}", tmp_path),)) == semantic_digest(second)
    assert semantic_digest({"value": 1}) != semantic_digest({"value": 2})


def test_stratified_sample_is_deterministic_and_balanced():
    items = [{"id": f"{category}-{index}", "category": category}
             for category in ("finding", "unknown", "none") for index in range(5)]
    selected = stratified_sample(items, 2, 17)
    assert selected == stratified_sample(list(reversed(items)), 2, 17)
    assert len(selected) == 6 and {item["category"] for item in selected} == {"finding", "unknown", "none"}
    assert selected != stratified_sample(items, 2, 18)


def test_paths_entries_and_truth_binding(tmp_path):
    source = tmp_path / "case/main.c"; source.parent.mkdir(); source.write_text("int main(void){return 0;}")
    database = tmp_path / "case/compile.json"; database.write_text("[]")
    scope = tmp_path / "case/scope.json"; scope.write_text("{}")
    truth_path = tmp_path / "case/truth.json"; truth_path.write_text("{}")
    item = {"id": "case", "profile_id": "c11", "category": "correct", "layout": "single-tu", "roots": ["main"],
            "sources": [{"path": "case/main.c", "sha256": file_hash(source), "role": "source"}],
            "compile_commands": {"path": "case/compile.json", "sha256": file_hash(database), "role": "compile-database"},
            "scope": {"path": "case/scope.json", "sha256": file_hash(scope), "role": "scope"},
            "truth": {"path": "case/truth.json", "sha256": file_hash(truth_path), "role": "truth"}}
    digest = case_input_digest(tmp_path, item)
    annotation = {"suite_id": "s", "suite_version": 1, "case_id": "case", "input_digest": digest,
                  "review": {"status": "reviewed"}}
    assert bind_truth(tmp_path, {"suite_id": "s", "suite_version": 1}, item, annotation) is annotation
    for update, pattern in [({"case_id": "other"}, "identity"), ({"input_digest": H}, "stale")]:
        changed = deepcopy(annotation); changed.update(update)
        with pytest.raises(AnalysisError, match=pattern):
            bind_truth(tmp_path, {"suite_id": "s", "suite_version": 1}, item, changed)
    pending = deepcopy(annotation); pending["review"]["status"] = "pending"
    with pytest.raises(AnalysisError, match="human-reviewed"):
        bind_truth(tmp_path, {"suite_id": "s", "suite_version": 1}, item, pending)
    assert verify_entry(tmp_path, item["sources"][0]) == source
    with pytest.raises(AnalysisError, match="escapes"):
        safe_path(tmp_path, "../escape")


def test_real_project_profile_counts_and_rejections(tmp_path):
    root = tmp_path / "project"; root.mkdir()
    (root / "LICENSE").write_text("MIT")
    (root / "scope.json").write_text("{}")
    database = [{"directory": str(root), "file": "a.c", "command": "clang -c a.c"},
                {"directory": str(root), "file": "a.c", "command": "clang -c a.c"},
                {"directory": str(root), "file": "b.c", "command": "clang -c b.c"}]
    (root / "compile_commands.json").write_text(json.dumps(database))
    profile = {"schema_version": 1, "project": "fixture", "upstream": "https://example.invalid/fixture",
               "revision": H, "root": "project", "source_tree_hash": H,
               "license": {"path": "LICENSE", "sha256": file_hash(root / "LICENSE")},
               "compile_commands": {"path": "compile_commands.json", "sha256": file_hash(root / "compile_commands.json")},
               "scope": {"path": "scope.json", "sha256": file_hash(root / "scope.json")},
               "included": [{"path": "a.c", "sha256": H}, {"path": "missing.c", "sha256": H}],
               "excluded": [{"path": "b.c", "reason": "fixture"}]}
    (root / "a.c").write_text("a"); (root / "missing.c").write_text("missing")
    profile["included"][0]["sha256"] = file_hash(root / "a.c")
    profile["included"][1]["sha256"] = file_hash(root / "missing.c")
    profile["source_tree_hash"] = identity(profile["included"])
    path = tmp_path / "profile.json"; path.write_text(json.dumps(profile))
    result = validate_real_project_profile(path)
    assert result["records"] == 3 and result["unique_tus"] == 2 and result["missing"] == ["missing.c"]
    bad = deepcopy(profile); bad["extra"] = True; path.write_text(json.dumps(bad))
    with pytest.raises(AnalysisError, match="fields/version"):
        validate_real_project_profile(path)
    path.write_text(json.dumps(profile)); profile["license"]["sha256"] = H; path.write_text(json.dumps(profile))
    with pytest.raises(AnalysisError, match="dependency changed"):
        validate_real_project_profile(path)
    profile["license"]["sha256"] = file_hash(root / "LICENSE")
    outside = tmp_path / "outside.c"; outside.write_text("x")
    profile["compile_commands"]["sha256"] = file_hash(root / "compile_commands.json")
    (root / "compile_commands.json").write_text(json.dumps([{"directory": str(tmp_path), "file": "outside.c"}]))
    profile["compile_commands"]["sha256"] = file_hash(root / "compile_commands.json"); path.write_text(json.dumps(profile))
    with pytest.raises(AnalysisError, match="escapes"):
        validate_real_project_profile(path)


def test_committed_real_project_profile_and_path_materialization(tmp_path):
    root = Path(__file__).resolve().parents[2]
    profile = root / "tests/fixtures/validation/real-project/tinycthread-profile.json"
    result = validate_real_project_profile(profile)
    assert result == {"records": 2, "unique_tus": 1, "included": 1, "excluded": 3,
                      "configurations": ["clang-21", "gcc"], "scope_roots": 4, "missing": [],
                      "status": "complete", "source_tree_hash": "a14757b85a8acab53c184a65cff36974a9666bad77d3d8e1b3d1319eddb0ab24",
                      "revision": "6957fc8383d6c7db25b60b8c849b29caab1caaee"}
    materialized = materialize_compile_database(profile, tmp_path / "compile_commands.json")
    records = json.loads((tmp_path / "compile_commands.json").read_text())
    assert materialized["records"] == 2 and all(Path(item["directory"]).is_absolute() for item in records)
    assert all("${PROJECT_ROOT}" not in json.dumps(item) for item in records)


def test_backend_recording_import_comparison_and_empty_success(tmp_path):
    raw = tmp_path / "raw.txt"; raw.write_text("SAFE")
    bundle = backend_bundle("genmc", "case", H, version="0.8.1", license_id="GPL-3.0",
                            command=["genmc", "input.ll"], raw_output_paths=[raw], observation={"risk": True})
    assert bundle["raw_output_hashes"] == [file_hash(raw)] and bundle["status"] == "complete"
    empty = backend_bundle("herdtools7", "case", H, version="7.58", license_id="CeCILL-B",
                           command=["herd7"], observation={})
    assert empty["status"] == "partial" and empty["diagnostics"][0]["code"] == "empty_backend_output"
    result = compare_case(case(), truth(["risk"]), report(), graph([assessment("risk")]))
    assert compare_backend(truth(["risk"]), result, bundle) == "agree"
    disagree = deepcopy(bundle); disagree["observation"]["risk"] = False
    assert compare_backend(truth(["risk"]), result, disagree) == "disagree"
    not_applicable = deepcopy(bundle); not_applicable["applicability"] = "not_applicable"
    assert compare_backend(truth(), result, not_applicable) == "not_applicable"
    partial = deepcopy(bundle); partial["status"] = "partial"
    assert compare_backend(truth(), result, partial) == "inconclusive"
    manifest = {"captured_on": "2026-09-10", "devkit_version": "25.3.0", "llvm_version": "12.0.0",
                "source_sha256": "1" * 64, "bc_sha256": "2" * 64, "command": ["mmcheck"], "report_sha256": "3" * 64}
    path = tmp_path / "devkit.json"; path.write_text(json.dumps(manifest))
    assert import_devkit_evidence(path, "case", H)["applicability"] == "approximate"
    del manifest["bc_sha256"]; path.write_text(json.dumps(manifest))
    with pytest.raises(AnalysisError, match="incomplete"):
        import_devkit_evidence(path, "case", H)
    manifest["bc_sha256"] = "2" * 64; manifest["captured_on"] = "2026-09-12"; path.write_text(json.dumps(manifest))
    with pytest.raises(AnalysisError, match="date"):
        import_devkit_evidence(path, "case", H)


def test_genmc_and_herdtools_adapters_cover_success_empty_crash_timeout_and_mapping():
    assert normalize_genmc_output("case", H, "No errors were detected", exit_code=0)["observation"]["risk"] is False
    assert normalize_genmc_output("case", H, "Data race: x", exit_code=0)["observation"]["risk"] is True
    assert normalize_genmc_output("case", H, "", exit_code=0)["status"] == "partial"
    assert normalize_genmc_output("case", H, "crash", exit_code=139)["status"] == "failed"
    timed = normalize_genmc_output("case", H, "partial", exit_code=0, timed_out=True, truncated=True)
    assert timed["status"] == "partial" and {item["code"] for item in timed["diagnostics"]} == {"backend_timeout", "backend_truncated"}
    assert normalize_herdtools_output("case", H, "", exit_code=0, mapped=False)["applicability"] == "not_applicable"
    allowed = normalize_herdtools_output("case", H, "Sometimes 1 1\nWitnesses Positive: 1", exit_code=0, mapped=True)
    assert allowed["observation"] == {"risk": True, "normalized": "allowed", "source_equivalent": False}
    absent = normalize_herdtools_output("case", H, "Never\nWitnesses Positive: 0", exit_code=0, mapped=True)
    assert absent["observation"]["risk"] is False
    assert normalize_herdtools_output("case", H, "crash", exit_code=1, mapped=True)["status"] == "failed"
    partial = normalize_herdtools_output("case", H, "partial", exit_code=0, mapped=True, timed_out=True, truncated=True)
    assert partial["status"] == "partial" and len(partial["diagnostics"]) == 3


def test_extension_decisions_are_quantified_bilingual_and_unconfirmed():
    evidence = {"std-thread": {"blocking_cases": 2, "blocking_tus": 3, "blocking_candidates": 4,
                               "denominator": 8, "cost": "medium", "compatibility": "compatible"},
                "pointer-analysis": {"denominator": 8}, "fence-rmw": {}, "b1-cmake-scope": {"denominator": 5}}
    decision = extension_decision(H, H, evidence)
    assert {item["capability"] for item in decision["entries"]} == set(CAPABILITIES)
    states = {item["capability"]: item["state"] for item in decision["entries"]}
    assert states == {"b1-cmake-scope": "defer", "std-thread": "recommend",
                      "pointer-analysis": "defer", "fence-rmw": "insufficient-evidence"}
    std = next(item for item in decision["entries"] if item["capability"] == "std-thread")
    assert std["potential_coverage_gain"] == 0.5 and not std["human_confirmed"]
    translated = deepcopy(decision); translated["entries"][0]["detail"] = "翻译改变"
    assert identity(translated) != identity(decision)
    assert states == {item["capability"]: item["state"] for item in translated["entries"]}
