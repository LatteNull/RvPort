"""P3 orchestration and CLI integration stay separate from P1/P2 commands."""

from copy import deepcopy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from memory_order_analyzer import cli, model_threads as subject
from memory_order_analyzer.contracts import AnalysisError, canonical
from memory_order_analyzer.model_threads import (
    _callback_definition, _check_deadline, _effect_summaries, _p2_argument,
    _p2_roots, _resolve_scope, model_threads,
)
from test_effect_contracts import samples as effect_samples
from test_thread_contracts import A, B, D, call, graph, local, order, ref, request


def inputs():
    return SimpleNamespace(
        scope_id=D, scope={"members": [A]},
        modules={A: {"source_mapping": "complete"}}, artifacts={A: {}},
    )


class Cache:
    value = None
    published = []

    def __init__(self, root):
        self.root = root

    def load(self, layer, key, kind):
        assert (layer, kind) == ("graphs", "ThreadContextGraph")
        return deepcopy(self.value)

    def publish(self, layer, key, value):
        self.published.append((layer, key, deepcopy(value)))


def prepare(monkeypatch, *, entries=None, cached=None):
    req = request()
    data = inputs()
    effect_summary = {"context_id": "summary", "root": req["roots"][0],
                      "invocations": [], "effects": [], "status": "complete"}
    monkeypatch.setattr(subject, "read_thread_document", lambda path, kind: deepcopy(req))
    monkeypatch.setattr(subject.EffectInputs, "load", lambda scope, store: data)
    monkeypatch.setattr(subject, "summarize", lambda *args: {"interprocedural_analysis": "complete"})
    monkeypatch.setattr(subject, "_effect_summaries", lambda path: {"summary": effect_summary})
    monkeypatch.setattr(subject, "analyze_thread_facts", lambda *args, **kwargs: entries or {
        A: {"id": A, "result": {"local": local(), "order": order()}, "error": None}})
    monkeypatch.setattr(subject, "build_thread_graph", lambda *args: graph())
    Cache.value = cached
    Cache.published = []
    monkeypatch.setattr(subject, "ThreadCache", Cache)
    return req


def test_scope_resolution_and_effect_summary_loading(tmp_path):
    request_path = tmp_path / "requests" / "request.json"
    request_path.parent.mkdir()
    assert _resolve_scope(request_path, "../scope.json") == (tmp_path / "scope.json").resolve()
    absolute = tmp_path / "absolute.json"
    assert _resolve_scope(request_path, absolute) == absolute.resolve()
    directory = tmp_path / "effects" / "summaries"; directory.mkdir(parents=True)
    summary = effect_samples()["EffectSummary"]
    (directory / "one.json").write_text(canonical(summary))
    assert _effect_summaries(directory.parent)[summary["context_id"]] == summary
    (directory / "one.json").unlink()
    with pytest.raises(AnalysisError, match="no root summaries"):
        _effect_summaries(directory.parent)
    assert _check_deadline(subject.monotonic(), {"budgets": {"request_seconds": 10}}, "unit") is None
    with pytest.raises(AnalysisError, match="wall-clock"):
        _check_deadline(-1000, {"budgets": {"request_seconds": 1}}, "unit")


def test_p2_plan_uses_only_explicit_roots_and_adopted_callbacks():
    req = request()
    req["roots"][0]["arguments"] = [
        {"kind": "integer", "bits": 8, "hex": "af"},
        {"kind": "object", "source": ref("global", None)},
        {"kind": "null"},
        {"kind": "unknown", "reason": "unit"},
    ]
    create = call(arguments=[ref("tid"), None, ref("worker", None), ref("arg")])
    data = SimpleNamespace(scope={"closed": True, "external_boundaries": []}, modules={
        A: {"functions": [{"id": "main", "name": "main", "declaration": False,
                           "linkage": "external", "comdat": None},
                          {"id": "worker", "name": "worker", "declaration": False,
                           "linkage": "external", "comdat": None}]},
    })
    roots = _p2_roots(data, req, {A: local([create])})
    assert len(roots) == 2
    main = next(item for item in roots if item["function_id"] == "main")
    worker = next(item for item in roots if item["function_id"] == "worker")
    assert main["arguments"] == [
        {"kind": "integer", "bits": 8, "hex": "AF"},
        {"kind": "object", "source": ref("global", None), "offset": None,
         "address_space": 0, "allocation": None},
        {"kind": "null", "address_space": 0},
        {"kind": "unknown", "reason": "unit"},
    ]
    assert worker["arguments"][0]["source"] == ref("arg")
    assert all(item["function_id"] != "unrelated" for item in roots)

    declaration = {"artifact_key": A, "function_id": None, "id": "worker-decl"}
    data.modules[A]["functions"].append({"id": "worker-decl", "name": "cross_worker",
                                          "declaration": True, "linkage": "external", "comdat": None})
    data.modules[B] = {"functions": [{"id": "worker-def", "name": "cross_worker",
                                       "declaration": False, "linkage": "external", "comdat": None}]}
    assert _callback_definition(data, declaration) == {"artifact_key": B, "function_id": "worker-def"}
    data.scope["closed"] = False
    assert _callback_definition(data, declaration) is None
    assert _callback_definition(data, {"artifact_key": A, "function_id": None, "id": "missing"}) is None

    create["arguments"][3] = None
    unknown = _p2_roots(data, request(), {A: local([create])})
    assert next(item for item in unknown if item["function_id"] == "worker")["arguments"] == []


def test_model_threads_fresh_output_cache_miss_and_hit(monkeypatch, tmp_path):
    req = prepare(monkeypatch)
    def rooted_summary(request_path, *args):
        planned = json.loads(Path(request_path).read_text())
        assert planned["mode"] == "roots" and planned["roots"]
        return {"interprocedural_analysis": "complete"}
    monkeypatch.setattr(subject, "summarize", rooted_summary)
    request_path = tmp_path / "request.json"; request_path.write_text("{}")
    output = tmp_path / "result"
    report = model_threads(request_path, tmp_path / "store", output, "worker")
    assert report["exit_code"] == 0
    assert (output / "request.json").is_file() and (output / "report.json").is_file()
    assert list((output / "thread-local").glob("*.json"))
    assert Cache.published and Cache.published[0][0] == "graphs"
    cached = graph()
    prepare(monkeypatch, cached=cached)
    monkeypatch.setattr(subject, "build_thread_graph", lambda *args: pytest.fail("cache hit rebuilt graph"))
    assert model_threads(request_path, tmp_path / "store", tmp_path / "cached", "worker")["exit_code"] == 0


def test_model_threads_rejects_existing_output_member_failure_and_output_limit(monkeypatch, tmp_path):
    prepare(monkeypatch)
    request_path = tmp_path / "request.json"; request_path.write_text("{}")
    existing = tmp_path / "existing"; existing.mkdir()
    with pytest.raises(AnalysisError, match="fresh output"):
        model_threads(request_path, tmp_path, existing, "worker")
    failed = {A: {"id": A, "result": None, "error": {"code": "bc_invalid", "detail": "bad"}}}
    prepare(monkeypatch, entries=failed)
    with pytest.raises(AnalysisError, match="bc_invalid"):
        model_threads(request_path, tmp_path, tmp_path / "failed", "worker")
    req = prepare(monkeypatch)
    req["budgets"]["request_output_bytes"] = 1024
    monkeypatch.setattr(subject, "read_thread_document", lambda path, kind: req)
    with pytest.raises(AnalysisError, match="output budget"):
        model_threads(request_path, tmp_path, tmp_path / "limited", "worker")


def test_model_threads_preserves_non_root_member_failure_denominator(monkeypatch, tmp_path):
    prepare(monkeypatch)
    other = "b" * 64
    data = inputs()
    data.scope["members"].append(other)
    data.modules[other] = {"source_mapping": "unavailable"}
    monkeypatch.setattr(subject.EffectInputs, "load", lambda scope, store: data)
    entries = {
        A: {"id": A, "result": {"local": local(), "order": order()}, "error": None},
        other: {"id": other, "result": None, "error": {"code": "bc_invalid", "detail": "bad"}},
    }
    monkeypatch.setattr(subject, "analyze_thread_facts", lambda *args, **kwargs: entries)
    request_path = tmp_path / "request.json"; request_path.write_text("{}")
    result = model_threads(request_path, tmp_path, tmp_path / "partial-member", "worker")
    assert result["exit_code"] == 2
    assert result["member_counts"]["planned"] == 2 and result["member_counts"]["failed"] == 1
    assert "thread-local-member-failed" in {item["code"] for item in result["frontier"]}


def test_model_threads_cli_parser_execute_and_failure(monkeypatch, tmp_path):
    args = cli.parser().parse_args(["model-threads", "--request", "request.json",
                                    "--artifact-store", "store", "--output", "out"])
    assert args.operation == "model-threads" and args.worker
    monkeypatch.setattr(cli, "model_threads", lambda *args: {"exit_code": 2, "kind": "unit"})
    assert cli.execute(args)[0]["exit_code"] == 2
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(["model-threads"], stdout=out, stderr=err) == 1
    invalid = json.loads(out.getvalue())
    assert invalid["kind"] == "ThreadAnalysisReport" and invalid["findings"] is None
    monkeypatch.setattr(cli, "model_threads", lambda *args: (_ for _ in ()).throw(AnalysisError("unit", "bad")))
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(["model-threads", "--request", "r", "--artifact-store", "s", "--output", "o"],
                    stdout=out, stderr=err) == 1
    assert json.loads(out.getvalue())["safety"] == "not_evaluated" and "bad" in err.getvalue()
