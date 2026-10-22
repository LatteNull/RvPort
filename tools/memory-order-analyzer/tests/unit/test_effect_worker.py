from copy import deepcopy
import json
from pathlib import Path

import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical
from memory_order_analyzer.effect_contracts import effect_document, expected_analysis_protocol
from memory_order_analyzer.effect_worker import analyze_metadata, check_analysis_worker
from memory_order_analyzer.execution import OutputStore
from conftest import success
from test_effect_inputs import inputs
from test_effect_references import references
from test_semantic import graph


def runner_for(inputs, *, change=None, result_patch=None):
    def runner(argv, cwd, **limits):
        if argv[-1] == "--analysis-protocol":
            return success(canonical(expected_analysis_protocol()))
        assert argv[1] == "--local-batch" and limits["timeout"] == 60 and limits["log_limit"] == 16777216
        request = json.loads(Path(argv[-1]).read_text())
        assert len(request["jobs"]) == len(inputs.scope["members"])
        entries = []
        for job in request["jobs"]:
            entries.append({"id": job["id"], "result": effect_document("LocalAnalysisFacts", origin=job["origin"],
                budgets=job["budgets"], functions=[], calls=[], objects=[], ir_nodes=[], analysis_evidence=[], resolutions=[], diagnostics=[], status="not_run"), "error": None})
        response = {"protocol_version": 1, "results": entries, "error": None}
        if change:
            change(response)
        return {**success(canonical(response)), **(result_patch or {})}
    return runner


def test_batch_success_failures_and_no_input_mutation(inputs, tmp_path):
    snapshot, _ = inputs
    before = deepcopy(snapshot.modules)
    store = OutputStore(tmp_path / "output")
    result = analyze_metadata(snapshot, "worker", store, runner=runner_for(snapshot))
    assert list(result) == sorted(snapshot.scope["members"])
    assert snapshot.modules == before
    assert list(store.root.iterdir()) == []
    def failure(value):
        value["results"][0].update(result=None, error={"code": "reader_failed", "detail": "bad bitcode"})
    result = analyze_metadata(snapshot, "worker", store, runner=runner_for(snapshot, change=failure))
    assert next(iter(result.values()))["error"]["code"] == "reader_failed"


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(extra=True), lambda r: r.update(protocol_version=True),
    lambda r: r.update(error={"code": "failure"}), lambda r: r.update(results=[]),
    lambda r: r.update(results=[None]), lambda r: r["results"][0].update(id="foreign"),
    lambda r: r["results"][0].update(id=[]), lambda r: r["results"][0].update(result=None),
    lambda r: r["results"][0].update(error={"code": "bad", "detail": "both outcomes"}),
    lambda r: r["results"][0].update(result=None, error={"code": "bad", "detail": 1}),
    lambda r: r["results"][0]["result"]["budgets"].update(local_steps=1),
])
def test_malformed_or_mismatched_batch_output(inputs, tmp_path, mutate):
    snapshot, _ = inputs
    with pytest.raises(AnalysisError):
        analyze_metadata(snapshot, "worker", OutputStore(tmp_path / "out"), runner=runner_for(snapshot, change=mutate))


def test_transport_errors_old_worker_and_invalid_budgets(inputs, tmp_path):
    snapshot, _ = inputs
    legacy = expected_analysis_protocol()
    for kind in ("LocalEvaluationRequest", "LocalEvaluationResult"):
        del legacy["kinds"][kind]
    with pytest.raises(AnalysisError, match="mismatch"):
        check_analysis_worker("four-kind-worker", tmp_path, runner=lambda *a, **k: success(canonical(legacy)))
    for response in [{}, success("not JSON"), success("null"), success("{}"), {**success("{}"), "status": "failed"}]:
        with pytest.raises(AnalysisError, match="mismatch"):
            check_analysis_worker("old-worker", tmp_path, runner=lambda *a, **k: response)
    store = OutputStore(tmp_path / "out")
    for patch, expected in [({"stdout": "bad"}, "analysis_worker_output"),
                            ({"stdout": "null"}, "invalid_reference"),
                            ({"status": "timed_out", "code": "timed_out", "stderr": "time"}, "timed_out"),
                            ({"status": "failed", "code": "log_limit", "stderr": "limit"}, "log_limit")]:
        with pytest.raises(AnalysisError) as caught:
            analyze_metadata(snapshot, "worker", store, runner=runner_for(snapshot, result_patch=patch))
        assert caught.value.code == expected
    with pytest.raises(AnalysisError):
        analyze_metadata(snapshot, "worker", store, budgets={}, runner=runner_for(snapshot))
    snapshot.scope["members"] *= 2
    budgets = {**expected_analysis_protocol()["budgets"], "contexts_per_request": 1}
    with pytest.raises(AnalysisError, match="transport budget"):
        analyze_metadata(snapshot, "worker", store, budgets=budgets, runner=runner_for(snapshot))
