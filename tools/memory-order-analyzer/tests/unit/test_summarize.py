"""Fresh-output orchestration and P2 failure reports."""

from types import SimpleNamespace

import pytest

from memory_order_analyzer.contracts import AnalysisError
from memory_order_analyzer.effect_contracts import effect_document, expected_analysis_protocol
from memory_order_analyzer import summarize as module


def request(scope):
    return effect_document("EffectAnalysisRequest", scope=str(scope), mode="all-defined", roots=[],
                           budgets=expected_analysis_protocol()["budgets"])


def test_summarize_success_scope_output_and_local_failure(monkeypatch, tmp_path):
    scope = tmp_path / "scope.json"; request_path = tmp_path / "request.json"
    value = request(scope)
    fake_inputs = SimpleNamespace(scope={"members": ["a"]})
    writes = []
    monkeypatch.setattr(module, "read_effect_document", lambda path, kind: value)
    monkeypatch.setattr(module.EffectInputs, "load", lambda scope, store: fake_inputs)
    monkeypatch.setattr(module, "OutputStore", lambda output: SimpleNamespace(root=output))
    monkeypatch.setattr(module, "write_json", lambda store, document, path: writes.append(path))
    monkeypatch.setattr(module, "analyze_metadata", lambda *a, **k: {"a": {"result": {"kind": "local"}, "error": None}})
    monkeypatch.setattr(module, "derive_adoptions", lambda *a: ["adoption"])
    summary = {"context_id": "c"}
    monkeypatch.setattr(module, "run_scheduler", lambda *a, **k: {"roots": [summary], "contexts": {}, "failures": []})
    monkeypatch.setattr(module, "build_report", lambda *a: {"exit_code": 0})
    result = module.summarize(request_path, scope, tmp_path / "store", tmp_path / "fresh", "worker")
    assert result == {"exit_code": 0}
    assert writes == ["local/a.json", next(path for path in writes if path.startswith("summaries/")),
                      "request.json", "report.json"]

    existing = tmp_path / "existing"; existing.mkdir()
    with pytest.raises(AnalysisError) as caught:
        module.summarize(request_path, scope, tmp_path / "store", existing, "worker")
    assert caught.value.code == "output_exists"
    other = tmp_path / "other"
    monkeypatch.setattr(module, "read_effect_document", lambda path, kind: request(other))
    with pytest.raises(AnalysisError) as caught:
        module.summarize(request_path, scope, tmp_path / "store", tmp_path / "mismatch", "worker")
    assert caught.value.code == "scope_mismatch"

    monkeypatch.setattr(module, "read_effect_document", lambda path, kind: value)
    monkeypatch.setattr(module, "analyze_metadata", lambda *a, **k: {"a": {"result": None,
        "error": {"code": "worker", "detail": "failed"}}})
    with pytest.raises(AnalysisError) as caught:
        module.summarize(request_path, scope, tmp_path / "store", tmp_path / "local-failed", "worker")
    assert caught.value.code == "local_analysis_failed"


def test_failed_report_default_and_explicit_budgets():
    report = module.failed_report("bad", "detail")
    assert report["exit_code"] == 1 and report["safety"] == "not_evaluated"
    assert report["frontier"] == report["diagnostics"]
    budgets = {**expected_analysis_protocol()["budgets"], "local_steps": 1}
    assert module.failed_report("bad", "detail", budgets=budgets)["budgets"]["local_steps"] == 1
