"""P3 worker negotiation, bounded batch transport and rejection paths."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.thread_contracts import expected_thread_protocol
from memory_order_analyzer.thread_worker import analyze_thread_facts, check_thread_worker
from test_thread_contracts import A, B, budgets, local, order


def completed(stdout="", stderr=""):
    return {"status": "completed", "code": None, "exit_code": 0,
            "stdout": stdout, "stderr": stderr}


class Inputs:
    def __init__(self, count=1):
        self.scope = {"members": [chr(97 + index) * 64 for index in range(count)]}
        self.artifacts = {key: {"path": f"/{key}.bc", "sha256": B,
                                "profile": "source-preserving"}
                          for key in self.scope["members"]}
        self.modules = {key: {"protocol": {"extractor_version": "0.2.0",
                                            "llvm_version": "21.1.8"}}
                        for key in self.scope["members"]}
        self.checks = 0

    def recheck(self):
        self.checks += 1


def worker_runner(transform=lambda value: value):
    def run(command, cwd, **kwargs):
        if command[1] == "--thread-analysis-protocol":
            return completed(canonical(expected_thread_protocol()))
        request = json.loads(open(command[2], encoding="utf-8").read())
        results = []
        for job in request["jobs"]:
            local_value = local(artifact=job["id"]); local_value["origin"] = job["origin"]
            order_value = order(artifact=job["id"]); order_value["origin"] = job["origin"]
            results.append({"id": job["id"], "result": {"local": local_value, "order": order_value},
                            "error": None})
        response = {"protocol_version": 1, "results": results, "error": None}
        changed = transform(response)
        if isinstance(changed, dict) and changed.get("runner_failure"):
            return {"status": "failed", "code": changed["runner_failure"], "exit_code": 1,
                    "stdout": "", "stderr": "worker failed"}
        return completed(changed if isinstance(changed, str) else json.dumps(changed))
    return run


@pytest.mark.parametrize("runner", [
    lambda *a, **k: {"status": "failed", "stdout": "", "stderr": "x"},
    lambda *a, **k: completed("not-json"),
    lambda *a, **k: completed(json.dumps({**expected_thread_protocol(), "policy_id": "future"})),
])
def test_protocol_mismatch_is_rejected(tmp_path, runner):
    with pytest.raises(AnalysisError, match="mismatch"):
        check_thread_worker("worker", tmp_path, runner=runner)


def test_batch_roundtrip_is_sorted_rechecked_and_bounded(tmp_path):
    inputs = Inputs(2)
    result = analyze_thread_facts(inputs, "worker", OutputStore(tmp_path / "out"),
                                  runner=worker_runner())
    assert list(result) == sorted(inputs.scope["members"])
    assert inputs.checks == 3
    assert all(item["result"]["local"]["origin"]["facts_hash"] ==
               identity(inputs.modules[key]) for key, item in result.items())
    tiny = budgets(thread_contexts=1)
    with pytest.raises(AnalysisError, match="context budget"):
        analyze_thread_facts(Inputs(2), "worker", OutputStore(tmp_path / "small"),
                             budgets=tiny, runner=worker_runner())


@pytest.mark.parametrize("transform,match", [
    (lambda r: {"runner_failure": "timeout"}, "worker failed"),
    (lambda r: "not-json", "Invalid thread worker JSON"),
    (lambda r: {**r, "extra": True}, "response fields"),
    (lambda r: {**r, "protocol_version": 2}, "version/error"),
    (lambda r: {**r, "error": {"code": "unit"}}, "version/error"),
    (lambda r: {**r, "results": []}, "result plan"),
    (lambda r: {**r, "results": [{**r["results"][0], "extra": 1}]}, "batch result"),
    (lambda r: {**r, "results": [{**r["results"][0], "id": "z" * 64}]}, "Foreign or duplicate"),
    (lambda r: {**r, "results": [{**r["results"][0], "error": {"code": "x", "detail": "x"}}]}, "one outcome"),
    (lambda r: {**r, "results": [{**r["results"][0], "result": {"local": r["results"][0]["result"]["local"]}}]}, "sidecar pair"),
])
def test_batch_envelope_failures(tmp_path, transform, match):
    with pytest.raises(AnalysisError, match=match):
        analyze_thread_facts(Inputs(), "worker", OutputStore(tmp_path / identity(str(transform))),
                             runner=worker_runner(transform))


@pytest.mark.parametrize("transform,match", [
    (lambda r: r["results"][0]["result"]["local"].update(origin={**r["results"][0]["result"]["local"]["origin"], "facts_hash": "d" * 64}), "origin mismatch"),
    (lambda r: r["results"][0]["result"]["order"].update(budgets={**r["results"][0]["result"]["order"]["budgets"], "local_steps": 1}), "budget mismatch"),
])
def test_sidecar_origin_and_budget_mismatch(tmp_path, transform, match):
    def mutate(response):
        transform(response)
        return response
    with pytest.raises(AnalysisError, match=match):
        analyze_thread_facts(Inputs(), "worker", OutputStore(tmp_path / match.replace(" ", "-")),
                             runner=worker_runner(mutate))


def test_member_failure_is_validated_and_returned(tmp_path):
    def failure(response):
        response["results"][0] = {"id": A, "result": None,
                                  "error": {"code": "bc_invalid", "detail": "broken"}}
        return response
    result = analyze_thread_facts(Inputs(), "worker", OutputStore(tmp_path / "failure"),
                                  runner=worker_runner(failure))
    assert result[A]["error"]["code"] == "bc_invalid"
    def malformed(response):
        response["results"][0] = {"id": A, "result": None,
                                  "error": {"code": "", "detail": 1}}
        return response
    with pytest.raises(AnalysisError, match="member failure"):
        analyze_thread_facts(Inputs(), "worker", OutputStore(tmp_path / "malformed"),
                             runner=worker_runner(malformed))
