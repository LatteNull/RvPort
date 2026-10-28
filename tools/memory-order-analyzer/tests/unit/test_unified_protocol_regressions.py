"""编排回归：使用实际请求 validator，不将协议检查替换为成功。"""

import json

import pytest

from memory_order_analyzer import unified_adapters as adapters
from memory_order_analyzer.contracts import AnalysisError
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.thread_contracts import expected_thread_protocol, thread_document
from test_unified_adapters import record, scope, write


@pytest.mark.parametrize("field", ["status", "cxx_standard", "target", "data_layout", "cxx_abi", "vendor"])
def test_profile_configuration_mismatch_is_not_silently_accepted(tmp_path, monkeypatch, field):
    monkeypatch.setattr(adapters, "ROOT", tmp_path)
    write(tmp_path / "profiles/one.json", {})
    monkeypatch.setattr(adapters, "_source_fact", lambda *args: {"nodes": [{"qualified_name": "std::thread"}]})
    profile = {"profile_id": "p", "status": "verified", "cxx_standard": "c++17", "target": "x86_64-pc-linux-gnu",
               "data_layout": "e-p:64:64", "cxx_abi": "itanium", "vendor": "libstdc++"}
    cpp = scope([record(language="c++", standard="c++17")])
    assert len(adapters._profiles("profiles", lambda *args: profile, "Profile", cpp, tmp_path)) == 1
    with pytest.raises(AnalysisError, match=field) as caught:
        adapters._profiles("profiles", lambda *args: {**profile, field: "different"}, "Profile", cpp, tmp_path)
    assert caught.value.code == "library_profile_missing"
    monkeypatch.setattr(adapters, "_source_fact", lambda *args: None)
    with pytest.raises(AnalysisError, match="vendor"):
        adapters._profiles("profiles", lambda *args: profile, "Profile", cpp, tmp_path)


def test_identity_normalization_preserves_order_and_rejects_conflicts():
    a, b = {"id": "a", "digest": "z"}, {"id": "b", "digest": "a"}
    assert adapters.canonical_members([b, a, a], lambda item: item["id"]) == [a, b]
    assert adapters.canonical_members([], lambda item: item["id"]) == []
    with pytest.raises(AnalysisError, match="Conflicting"):
        adapters.canonical_members([a, {**a, "digest": "different"}], lambda item: item["id"])


def test_r3_sorts_by_tu_independently_of_artifact(tmp_path, monkeypatch):
    write(tmp_path / "root-plans/scope.json", {"schema_version": 1, "policy_id": "p"})
    write(tmp_path / "thread-entry-roots/scope.json", {"schema_version": 1, "policy_id": "p"})
    a, b = record("a"), record("b")
    b["physical_tu_id"] = "b" * 64
    captured = []
    monkeypatch.setattr(adapters, "analyze_demanded_functions",
                        lambda path, *args: captured.append(json.loads(path.read_text())) or {"status": "complete"})
    mappings = {"a": {"artifact_key": "f" * 64}, "b": {"artifact_key": "e" * 64}}
    adapters.run_demand(scope([b, a, a]), tmp_path, OutputStore(tmp_path), mappings, {}, tmp_path / "out", "worker")
    assert [item["physical_tu_id"] for item in captured[0]["members"]] == ["a" * 64, "b" * 64]
    assert [item["artifact_key"] for item in captured[0]["members"]] == ["f" * 64, "e" * 64]


def test_publication_uses_only_explicit_validated_p3(tmp_path, monkeypatch):
    request = thread_document("ThreadAnalysisRequest", scope=str(tmp_path / "scopes/scope.json"),
                              roots=[{"artifact_key": "a" * 64, "function_id": "f", "arguments": []}],
                              model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
    chosen = write(tmp_path / "requests/scope/thread-2.json", request)
    write(tmp_path / "requests/scope/thread-0.json", {"invalid": True})
    write(tmp_path / "requests/scope/thread-entry.json", {"invalid": True})
    captured = []
    monkeypatch.setattr(adapters, "detect_publication_risks",
                        lambda path, *args: captured.append(json.loads(path.read_text())) or {"status": "complete"})
    adapters.run_publication(scope(), tmp_path, tmp_path / "out", "worker", chosen)
    assert captured[0]["thread_request"] == str(chosen.resolve())
    with pytest.raises(AnalysisError, match="requires"):
        adapters.run_publication(scope(), tmp_path, tmp_path / "out", "worker")
    with pytest.raises(AnalysisError, match="current scope"):
        adapters.run_publication(scope(), tmp_path, tmp_path / "out", "worker", tmp_path / "other.json")
    with pytest.raises(AnalysisError):
        adapters.run_publication(scope(), tmp_path, tmp_path / "out", "worker", chosen.with_name("thread-entry.json"))


def test_dependency_failures_precede_invalid_requests(tmp_path):
    with pytest.raises(AnalysisError, match="A5 requires"):
        adapters.run_provenance(scope(), tmp_path, OutputStore(tmp_path), {}, {}, tmp_path / "out", "s", "i")
    write(tmp_path / "root-plans/scope.json", {})
    write(tmp_path / "thread-entry-roots/scope.json", {})
    with pytest.raises(AnalysisError, match="EffectSummary"):
        adapters.run_concurrent(scope(), tmp_path, {}, {}, tmp_path / "out")


def test_atomic_standard_groups_keep_inputs_separate_and_isolate_failures(tmp_path, monkeypatch):
    a, b, unknown = record("a", standard="c++17"), record("b", standard="c++20"), record("default", standard="compiler-default")
    b["physical_tu_id"], unknown["physical_tu_id"] = "b" * 64, "c" * 64
    mappings = [{"record_id": item["record_id"], "artifact_key": item["physical_tu_id"]} for item in [a, b, unknown]]
    write(tmp_path / "report.json", {"record_artifacts": mappings})
    for item in mappings:
        write(tmp_path / f"facts/{item['artifact_key']}.json", {})
        write(tmp_path / f"source-facts/{item['artifact_key']}.json", {})
    write(tmp_path / "source-facts/unrelated-scope.json", {})
    captured = []
    def analyze(path, *args):
        request = json.loads(path.read_text())
        captured.append(request)
        if request["language_standard"] == "c++17":
            raise AnalysisError("test-stage-failed", "one group failed")
        return {"status": "complete", "findings": [{"id": "kept"}]}
    monkeypatch.setattr(adapters, "model_fence_rmw_publication", analyze)
    reports = adapters.run_atomic(scope([b, a, unknown]), tmp_path, tmp_path / "output")
    assert [item["status"] for item in reports] == ["partial", "complete", "partial"]
    assert reports[1]["findings"] == [{"id": "kept"}]
    assert reports[2]["diagnostics"][0]["code"] == "atomic-standard-unresolved"
    assert all(len(item["source_facts"]) == len(item["module_facts"]) == 1 for item in captured)
    assert captured[0]["source_facts"] != captured[1]["source_facts"]
