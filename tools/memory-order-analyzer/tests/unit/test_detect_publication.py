"""P4 orchestration, language identity and failure-path unit coverage."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import memory_order_analyzer.detect_publication as module
from memory_order_analyzer.contracts import AnalysisError, canonical, document
from memory_order_analyzer.detect_publication import (
    _check_deadline, _only, _profiles, _resolve, _standard, _summaries,
    detect_publication_risks,
)
from memory_order_analyzer.publication_graph import build_publication_graph
from memory_order_analyzer.publication_report import build_publication_report
from memory_order_analyzer.thread_contracts import thread_document
from test_publication_contracts import A, B, budgets, scenario
from test_thread_contracts import budgets as thread_budgets


def test_path_summary_standard_and_deadline_helpers(tmp_path, monkeypatch):
    owner = tmp_path / "request.json"
    assert _resolve(owner, "child.json") == (tmp_path / "child.json").resolve()
    assert _resolve(owner, tmp_path / "absolute.json") == (tmp_path / "absolute.json").resolve()
    with pytest.raises(AnalysisError, match="exactly one"):
        _only(tmp_path, "*.json", "unit")
    (tmp_path / "one.json").write_text("{}")
    assert _only(tmp_path, "*.json", "unit").name == "one.json"
    (tmp_path / "two.json").write_text("{}")
    with pytest.raises(AnalysisError):
        _only(tmp_path, "*.json", "unit")
    empty = tmp_path / "empty"; empty.mkdir()
    with pytest.raises(AnalysisError, match="no P2"):
        _summaries(empty)
    monkeypatch.setattr(module, "read_effect_document",
                        lambda path, kind: {"context_id": Path(path).stem})
    (empty / "a.json").write_text("{}")
    assert set(_summaries(empty)) == {"a"}
    assert _standard(["clang", "-std=c11"]) == "c11"
    assert _standard(["clang", "-std", "c17"]) == "c17"
    assert _standard(["clang", "-std=c11", "-std=c17"]) is None
    assert _standard(["clang"]) is None
    monkeypatch.setattr(module, "monotonic", lambda: 100)
    with pytest.raises(AnalysisError, match="wall-clock"):
        _check_deadline(0, {"budgets": {"request_seconds": 1}}, "unit")


def test_language_profiles_require_context_compiler_language_and_explicit_standard(tmp_path):
    keys = [A, B, "c" * 64, "d" * 64, "e" * 64]
    contexts = {key: chr(97 + index) * 64 for index, key in enumerate(keys)}
    artifacts = {key: {"context_id": contexts[key]} for key in keys}
    artifacts[keys[-1]]["context_id"] = None
    inputs = SimpleNamespace(
        artifacts=artifacts,
        modules={key: {"target": "x86_64-linux-gnu", "layout": "e-p:64:64"} for key in keys})
    directory = tmp_path / "contexts"; directory.mkdir()
    manifests = [
        (keys[0], "c", ["clang", "-std=c11"], {"description": "clang 21"}),
        (keys[1], "c++", ["g++", "-std", "c++20"], {"description": "gcc 15"}),
        (keys[2], "c", ["vendor", "-std=c17"], {}),
        (keys[3], "c", ["clang"], {"description": "clang"}),
    ]
    for key, language, argv, production in manifests:
        value = document("TUManifest", context_id=contexts[key], source="input.c",
            directory=str(tmp_path), original={}, effective_argv=argv, production=production,
            analysis={}, adaptations=[], response_files={}, environment={}, language=language, abi={})
        (directory / f"{contexts[key]}.json").write_text(canonical(value))
    values = _profiles(inputs, tmp_path)
    assert values[A].startswith("clang:c:c11")
    assert values[B].startswith("gcc:c++:c++20")
    assert values[keys[2]] is None and values[keys[3]] is None and values[keys[4]] is None
    (directory / f"{contexts[keys[2]]}.json").unlink()
    assert _profiles(inputs, tmp_path)[keys[2]] is None


class FakeCache:
    values = {}
    published = []

    def __init__(self, root):
        self.root = root

    def load(self, layer, key, kind):
        return deepcopy(self.values.get((layer, kind)))

    def publish(self, layer, key, value):
        self.published.append((layer, key, deepcopy(value)))


def orchestration(monkeypatch, tmp_path, *, cached=False, member_failure=False,
                  graph_cached=False, output_limit=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    inputs, publication_request, thread_graph, locals_, summaries, profiles = scenario()
    inputs.artifacts = {key: {"sha256": ("1" if key == A else "2") * 64,
                              "profile": "source-preserving", "context_id": None}
                        for key in inputs.scope["members"]}
    inputs.modules = {key: {"protocol": {"extractor_version": "0.2.0", "llvm_version": "21.1.8"},
                            "target": "x86", "layout": "layout", "source_mapping": "complete"}
                      for key in inputs.scope["members"]}
    thread_request = thread_document("ThreadAnalysisRequest", scope="scope.json",
        roots=[{"artifact_key": A, "function_id": "main", "arguments": []}],
        model_id="posix-pthread-v1", budgets=thread_budgets())
    request_path = tmp_path / "publication.json"
    publication_request["thread_request"] = "thread.json"
    if output_limit is not None:
        publication_request["budgets"]["request_output_bytes"] = output_limit
    request_path.write_text(canonical(publication_request))
    (tmp_path / "thread.json").write_text(canonical(thread_request))
    graph = build_publication_graph(inputs, publication_request, thread_graph, locals_, summaries, profiles)
    thread_report = {"thread_modeling": "complete"}
    report = build_publication_report(inputs, publication_request, graph, locals_, thread_report)

    monkeypatch.setattr(module.EffectInputs, "load", lambda *args: inputs)
    def model(*args):
        output = Path(args[2]); (output / "graphs").mkdir(parents=True)
        (output / "graphs/g.json").write_text("{}")
        (output / "execution-order").mkdir(); (output / "execution-order/o.json").write_text("{}")
        (output / "effects/summaries").mkdir(parents=True)
        return thread_report
    monkeypatch.setattr(module, "model_threads", model)
    def read_thread(path, kind):
        if kind == "ThreadAnalysisRequest":
            return thread_request
        if kind == "ThreadContextGraph":
            return thread_graph
        return {"origin": {"artifact_key": A}, "edges": []}
    monkeypatch.setattr(module, "read_thread_document", read_thread)
    monkeypatch.setattr(module, "_summaries", lambda path: summaries)
    monkeypatch.setattr(module, "_profiles", lambda *args: profiles)
    monkeypatch.setattr(module, "PublicationCache", FakeCache)
    FakeCache.values = {}
    FakeCache.published = []
    if cached:
        FakeCache.values[("local", "PublicationLocalFacts")] = locals_[A]
    entries = {key: {"result": value, "error": None} for key, value in locals_.items()}
    if member_failure:
        entries[B] = {"result": None, "error": {"code": "unit", "detail": "broken"}}
    monkeypatch.setattr(module, "analyze_publication_facts", lambda *args, **kwargs: entries)
    monkeypatch.setattr(module, "build_publication_graph", lambda *args: deepcopy(graph))
    monkeypatch.setattr(module, "build_publication_report", lambda *args: deepcopy(report))
    if graph_cached:
        FakeCache.values[("graphs", "SinglePublicationProtocolGraph")] = graph
    return request_path, report


def test_orchestration_writes_all_products_and_publishes_cache(monkeypatch, tmp_path):
    request_path, expected = orchestration(monkeypatch, tmp_path)
    output = tmp_path / "result"
    result = detect_publication_risks(request_path, tmp_path / "store", output, "worker")
    assert result == expected
    assert (output / "request.json").is_file() and (output / "thread-request.json").is_file()
    assert len(list((output / "publication-local").glob("*.json"))) == 2
    assert len(list((output / "graphs").glob("*.json"))) == 1
    assert {item[0] for item in FakeCache.published} == {"local", "graphs"}
    with pytest.raises(AnalysisError, match="fresh output"):
        detect_publication_risks(request_path, tmp_path / "store", output, "worker")


def test_orchestration_writes_complete_and_partial_source_candidate_slices(monkeypatch, tmp_path):
    request_path, expected = orchestration(monkeypatch, tmp_path)
    assistance = {"report": {"status": "complete"}, "binding": {"status": "complete"},
                  "overlay": {"status": "complete"}}
    monkeypatch.setattr(module, "load_source_assistance", lambda *args, **kwargs: assistance)
    monkeypatch.setattr(module, "relevant_dependency_slice", lambda *args: {
        "artifacts": [], "program_objects": [], "source_report_digest": "0" * 64,
        "status": "complete", "missing": []})
    output = tmp_path / "source-result"
    assert detect_publication_risks(request_path, tmp_path / "store", output, "worker",
                                    tmp_path / "source") == expected
    slices = json.loads((output / "source-assistance/candidate-slices.json").read_text())
    assert slices["status"] == "complete" and not slices["frontier"]
    assert slices["counts"]["downstream_consumption"] == slices["counts"]["candidates"]

    request_path, _ = orchestration(monkeypatch, tmp_path / "partial-source")
    monkeypatch.setattr(module, "load_source_assistance", lambda *args, **kwargs: assistance)
    monkeypatch.setattr(module, "relevant_dependency_slice", lambda *args: {
        "artifacts": [], "program_objects": [], "source_report_digest": "0" * 64,
        "status": "partial", "missing": ["flag-object-binding"]})
    output = tmp_path / "partial-source/result"
    detect_publication_risks(request_path, tmp_path / "partial-source/store", output,
                             "worker", tmp_path / "source")
    slices = json.loads((output / "source-assistance/candidate-slices.json").read_text())
    assert slices["status"] == "partial"
    assert slices["frontier"][0]["code"] == "candidate-source-dependency-incomplete"


def test_orchestration_cache_hits_partial_member_and_structural_failures(monkeypatch, tmp_path):
    request_path, expected = orchestration(monkeypatch, tmp_path, graph_cached=True)
    assert detect_publication_risks(request_path, tmp_path / "store", tmp_path / "cached", "worker") == expected
    request_path, _ = orchestration(monkeypatch, tmp_path / "partial", member_failure=True)
    result = detect_publication_risks(request_path, tmp_path / "partial/store",
                                      tmp_path / "partial/result", "worker")
    assert result["exit_code"] in {0, 2, 3}

    request_path, _ = orchestration(monkeypatch, tmp_path / "root-failure", member_failure=True)
    thread = thread_document("ThreadAnalysisRequest", scope="scope.json",
        roots=[{"artifact_key": B, "function_id": "main", "arguments": []}],
        model_id="posix-pthread-v1", budgets=thread_budgets())
    monkeypatch.setattr(module, "read_thread_document",
                        lambda path, kind: thread if kind == "ThreadAnalysisRequest" else
                        scenario()[2] if kind == "ThreadContextGraph" else {"origin": {"artifact_key": A}, "edges": []})
    with pytest.raises(AnalysisError, match="broken") as caught:
        detect_publication_risks(request_path, tmp_path / "root-failure/store",
                                 tmp_path / "root-failure/result", "worker")
    assert caught.value.code == "publication_local_failed"


def test_orchestration_rejects_model_timeout_and_output_budget(monkeypatch, tmp_path):
    request_path, _ = orchestration(monkeypatch, tmp_path / "model")
    invalid = json.loads(request_path.read_text()); invalid["model_id"] = "future"
    monkeypatch.setattr(module, "read_publication_document", lambda *args: invalid)
    with pytest.raises(AnalysisError, match="Unsupported publication model"):
        detect_publication_risks(request_path, tmp_path / "model/store",
                                 tmp_path / "model/result", "worker")
    monkeypatch.undo()

    request_path, _ = orchestration(monkeypatch, tmp_path / "limit", output_limit=1)
    with pytest.raises(AnalysisError, match="output budget"):
        detect_publication_risks(request_path, tmp_path / "limit/store",
                                 tmp_path / "limit/result", "worker")
