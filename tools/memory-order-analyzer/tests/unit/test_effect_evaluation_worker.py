"""Evaluation transport tests; synthetic results do not prove LLVM transfers."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from conftest import success
from test_effect_evaluation import evaluation
from test_effect_inputs import inputs
from test_effect_references import references
from test_semantic import graph
from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.effect_contracts import expected_analysis_protocol
from memory_order_analyzer.effect_worker import evaluate_batch
from memory_order_analyzer.execution import OutputStore


def response_runner(result, change=None, during=None):
    def runner(argv, cwd, **limits):
        if argv[-1] == "--analysis-protocol":
            return success(canonical(expected_analysis_protocol()))
        assert argv[1] == "--evaluate-batch"
        batch = json.loads(Path(argv[-1]).read_text())
        assert batch["protocol"] == expected_analysis_protocol()
        entries = []
        for job in batch["jobs"]:
            assert set(job) == {"id", "path", "request", "summaries"}
            assert job["id"] == identity(job["request"])
            assert limits == dict(timeout=job["request"]["budgets"]["worker_seconds"],
                                  log_limit=job["request"]["budgets"]["worker_output_bytes"])
            entries.append(dict(id=job["id"], result=deepcopy(result), error=None))
        response = dict(protocol_version=1, results=entries, error=None)
        if change:
            change(response)
        if during:
            during()
        return success(canonical(response))
    return runner


def test_evaluation_roundtrip_and_dependency_snapshot(evaluation, tmp_path):
    snapshot, request, result, locals_ = evaluation
    before = deepcopy((request, result, locals_))
    store = OutputStore(tmp_path / "output")
    run = lambda **kw: evaluate_batch(snapshot, [request], "worker", store, local_facts=locals_, **kw)
    actual = run(runner=response_runner(result))
    assert list(actual) == [identity(request)] and actual[identity(request)]["result"] == result
    assert (request, result, locals_) == before and not list(store.root.iterdir())
    # A caller mutating its dependency map after dispatch cannot substitute the snapshot.
    assert run(runner=response_runner(result, during=lambda: locals_.clear())) == actual


@pytest.mark.parametrize("change", [
    lambda r: r.update(results=[]),
    lambda r: r["results"][0].update(id="foreign"),
    lambda r: r["results"][0]["result"].update(request_hash="e" * 64),
    lambda r: r["results"][0]["result"]["request"].update(context_id="substituted"),
    lambda r: r["results"][0]["result"].update(blocks=[]),
    lambda r: r["results"][0].update(result=None, error=dict(code="", detail="bad")),
])
def test_invalid_evaluation_response(evaluation, tmp_path, change):
    snapshot, request, result, locals_ = evaluation
    with pytest.raises(AnalysisError):
        evaluate_batch(snapshot, [request], "worker", OutputStore(tmp_path / "out"),
                       local_facts=locals_, runner=response_runner(result, change))


def test_evaluation_failures_and_plan_validation(evaluation, tmp_path):
    snapshot, request, result, locals_ = evaluation
    store = OutputStore(tmp_path / "out")
    def run(requests, **kw):
        return evaluate_batch(snapshot, requests, "worker", store, local_facts=locals_, **kw)
    for plan in ([], None, [result], [request, request]):
        with pytest.raises(AnalysisError):
            run(plan)
    def failure(r):
        r["results"][0].update(result=None, error=dict(code="inputs_changed", detail="generation mismatch"))
    actual = run([request], runner=response_runner(result, failure))
    assert actual[identity(request)]["error"]["code"] == "inputs_changed"
    other = deepcopy(request)
    other["budgets"]["worker_seconds"] = 1
    # The local supplement must use the same budgets, so this is rejected before dispatch.
    with pytest.raises(AnalysisError):
        run([request, other])
    with pytest.raises(AnalysisError):
        run([request], summaries={"invalid": None})
    decimal = deepcopy(request)
    decimal["arguments"][0]["candidates"][0]["value"]["bits"] = 32.0
    with pytest.raises(AnalysisError, match="integer JSON"):
        run([decimal])
    with pytest.raises(AnalysisError):
        run([request], runner=response_runner(result, during=lambda: Path(next(iter(snapshot.artifacts.values()))["path"]).write_bytes(b"changed")))


@pytest.mark.parametrize("status,code", [("timed_out", "timed_out"), ("failed", "log_limit")])
def test_evaluation_process_failures(evaluation, tmp_path, status, code):
    snapshot, request, result, locals_ = evaluation
    def runner(argv, cwd, **limits):
        if argv[-1] == "--analysis-protocol":
            return success(canonical(expected_analysis_protocol()))
        return dict(status=status, code=code, stdout="", stderr="budget")
    with pytest.raises(AnalysisError) as caught:
        evaluate_batch(snapshot, [request], "worker", OutputStore(tmp_path / "out"), local_facts=locals_, runner=runner)
    assert caught.value.code == code
