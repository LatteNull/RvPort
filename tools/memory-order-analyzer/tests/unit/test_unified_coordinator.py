import json
from pathlib import Path

import pytest

import memory_order_analyzer.unified_coordinator as coordinator
from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.finding_contracts import provenance
from memory_order_analyzer.finding_projection import project_assessment
from memory_order_analyzer.unified_contracts import expected_unified_protocol, unified_document
from memory_order_analyzer.unified_plan import stage_registry


def request(path, bundle_hash, **updates):
    fields = {"policy_preset": "bounded-default-v1", "project": {"id": "p", "name": "p"},
              "bundle": {"path": "bundle.json", "sha256": bundle_hash},
              "scope_selection": {"mode": "all", "scope_ids": []}, "source_assistance": "disabled",
              "source_requests": [], "explicit_roots": [], "cache": {"mode": "disabled", "resume": False},
              "cancel_file": None, "budgets": expected_unified_protocol()["budgets"]}
    fields.update(updates)
    value = unified_document("UnifiedMemoryOrderAnalysisRequest", **fields)
    path.write_text(canonical(value), encoding="utf-8")
    return value


def test_atomic_output_publishes_and_cleans_failure(tmp_path):
    destination = tmp_path / "result"
    with coordinator.atomic_analysis_output(destination) as work:
        (work / "ok").write_text("ok")
    assert (destination / "ok").read_text() == "ok"
    with pytest.raises(AnalysisError, match="fresh"):
        with coordinator.atomic_analysis_output(destination):
            pass
    failed = tmp_path / "failed"
    with pytest.raises(RuntimeError):
        with coordinator.atomic_analysis_output(failed) as work:
            (work / "partial").write_text("x")
            raise RuntimeError("boom")
    assert not failed.exists()


def test_copy_reference_stage_mode_and_json_helpers(tmp_path):
    source = tmp_path / "a"; source.write_text("a")
    store = OutputStore(tmp_path / "store")
    destination = coordinator._copy_once(store, source, "x/a")
    assert coordinator._copy_once(store, source, "x/a") == destination
    other = tmp_path / "b"; other.write_text("b")
    with pytest.raises(AnalysisError, match="different"):
        coordinator._copy_once(store, other, "x/a")
    value = {"x": 1}
    ref = coordinator._reference("K", "id", value, "a\\b", "producer")
    assert ref["path"] == "a/b"
    stage = {"id": "a" * 64, "stage": "unit"}
    assert coordinator._stage_result(stage, "complete")["cache"] == "miss"
    rec = {"record_id": "tu", "physical_tu_id": "b" * 64}
    assert coordinator._mode(rec, source_usable=True, ir_usable=True)["mode"] == "ast-ir"
    assert coordinator._mode(rec, source_usable=True, ir_usable=False)["mode"] == "ast-only"
    assert coordinator._mode(rec, source_usable=False, ir_usable=True)["mode"] == "ir-only"
    assert coordinator._mode(rec, source_usable=False, ir_usable=False)["mode"] == "failed"
    path = tmp_path / "doc.json"; path.write_text(json.dumps(value))
    assert coordinator._json_document(path) == value
    with pytest.raises(AnalysisError):
        coordinator._json_document(tmp_path / "missing")


def test_stage_outputs_are_typed_and_scope_filtered(tmp_path):
    write_root = tmp_path / "data"; write_root.mkdir()
    (write_root / "facts").mkdir()
    (write_root / "facts/scope-a.json").write_text(json.dumps({
        "schema_version": 2, "kind": "ModuleFacts", "policy_id": "p"}))
    (write_root / "facts/scope-b.json").write_text(json.dumps({
        "schema_version": 2, "kind": "ModuleFacts", "policy_id": "p"}))
    planned = {"ingest": {"outputs": ["ModuleFacts"]}}
    results = [{"stage": "ingest", "outputs": []}]
    coordinator._attach_stage_outputs(results, planned, write_root, ["scope-a"])
    assert len(results[0]["outputs"]) == 1
    assert results[0]["outputs"][0]["kind"] == "ModuleFacts"


@pytest.mark.parametrize("unpublished", [
    "source/other-scope/.task-pending/document.json",
    "derived/source-ir-binding/.digest.random.tmp",
    "derived/.digest.artifacts.tmp/document.json",
])
def test_nested_inflight_outputs_are_never_read_or_cached(tmp_path, monkeypatch, unpublished):
    root = tmp_path / "data"
    staging = root / unpublished
    staging.parent.mkdir(parents=True)
    staging.write_text('{"kind":"IncompleteOtherScope"}')
    published = root / "source/current-scope/facts.json"
    published.parent.mkdir(parents=True)
    published.write_text('{"kind":"SourceSemanticFacts"}')
    read_text = Path.read_text
    def guarded_read(path, *args, **kwargs):
        assert path != staging, "Unpublished output from another scope must not be consumed"
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    assert coordinator._published_paths(root) == [published]
    assert [item["path"] for item in coordinator._artifact_index(root)] == ["source/current-scope/facts.json"]
    request_path = tmp_path / "request.json"
    req = request(request_path, "b" * 64, cache={"mode": "read-write", "resume": True})
    scope = {"target_id": "scope", "records": []}
    bundle = {"manifest": {"bundle_id": "bundle"}}
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "out", cache_path=tmp_path / "cache")
    analyzer._store_scope_cache(req, bundle, scope, stage_plan(), coordinator._cache_payload(complete_record(), [], [], []), root)
    envelope = json.loads(analyzer._scope_cache_file(analyzer._scope_cache_key(req, bundle, scope, stage_plan())).read_text())
    assert [item["path"] for item in envelope["artifacts"]] == ["source/current-scope/facts.json"]


@pytest.mark.parametrize("diagnostic_budget", [1, 2, 100])
def test_coordinator_run_aggregates_scope_failure_and_success(tmp_path, monkeypatch, diagnostic_budget):
    bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    request_path = tmp_path / "request.json"; req = request(request_path, file_hash(bundle_path),
        budgets={**expected_unified_protocol()["budgets"], "frontier_items": diagnostic_budget})
    records = [{"record_id": "tu", "physical_tu_id": "a" * 64, "source": None}]
    bundle = {"manifest": {"bundle_id": "bundle"}, "manifest_path": bundle_path,
              "records": {"tu": records[0]}, "source_requests": {},
              "scopes": [{"target_id": "scope", "records": records}]}
    plan = unified_document("UnifiedAnalysisPlan", request_digest=req["semantic_digest"], bundle_id="bundle",
                            selected_scopes=["scope"], stages=[], edges=[], diagnostics=[], frontier=[])
    monkeypatch.setattr(coordinator, "preflight_bundle", lambda *args: bundle)
    monkeypatch.setattr(coordinator, "build_plan", lambda *args: plan)
    def ingest(path, data, worker, cache_path=None):
        data.mkdir(); write = data / "report.json"
        value = {"record_artifacts": []}; write.write_text(json.dumps(value))
        return value
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "result", ingest=ingest)
    monkeypatch.setattr(analyzer, "_write_request_inputs", lambda *args: {})
    monkeypatch.setattr(analyzer, "_snapshot_sources", lambda *args: ({}, {}))
    record = unified_document("ScopeAnalysisExecutionRecord", scope_id="scope", status="partial",
                              tu_modes=[{"record_id": "tu", "physical_tu_id": "a" * 64, "mode": "failed",
                                         "status": "failed", "available_evidence": [], "missing_evidence": ["ast", "ir"]}],
                              stages=[], counts={}, diagnostics=[coordinator.diagnostic(f"cause-{i}", "原因", "cause") for i in range(3)],
                              frontier=[coordinator.diagnostic("x", "不完整", "incomplete", scope_id="scope")])
    monkeypatch.setattr(analyzer, "_scope", lambda *args: (record, [], [], []))
    report = analyzer.run()
    assert report["status"] == "partial" and report["exit_code"] == 2
    assert (tmp_path / "result/report.json").is_file()
    assert report["summary"]["diagnostics_total"] == 4
    assert len(report["diagnostics"]) <= diagnostic_budget
    if diagnostic_budget < 4:
        assert report["diagnostics"][-1]["code"] == "diagnostic-budget-exhausted"
        assert len(json.loads((tmp_path / "result/diagnostics/full.json").read_text())["diagnostics"]) == 4


def test_cancel_deadline_and_failed_scope_record(tmp_path, monkeypatch):
    request_path = tmp_path / "request.json"; bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    cancel = tmp_path / "cancel"; cancel.write_text("stop")
    req = request(request_path, file_hash(bundle_path), cancel_file=str(cancel.resolve()))
    instance = coordinator.AnalysisCoordinator(request_path, tmp_path / "out", clock=lambda: 0)
    instance.started = 0
    assert instance._cancelled(req)
    with pytest.raises(AnalysisError, match="cancelled"):
        instance._check_stop(req, "unit")
    req["cancel_file"] = None; instance.clock = lambda: req["budgets"]["deadline_seconds"] + 1
    assert instance._deadline(req)
    with pytest.raises(AnalysisError, match="deadline"):
        instance._check_stop(req, "unit")


def complete_record(scope_id="scope"):
    return unified_document(
        "ScopeAnalysisExecutionRecord", scope_id=scope_id, status="complete",
        tu_modes=[{"record_id": "tu", "physical_tu_id": "a" * 64, "mode": "ast-ir",
                   "status": "complete", "available_evidence": ["ast", "ir"],
                   "missing_evidence": []}], stages=[], counts={}, diagnostics=[], frontier=[])


def stage_plan(scope_id="scope"):
    stages = []
    for index, item in enumerate(stage_registry()):
        stages.append({"id": f"{index + 1:064x}", "scope_id": scope_id, "stage": item["name"],
                       "version": item["version"], "producer": "org.rvport.memory-order-analyzer.test",
                       "inputs": list(item["inputs"]), "outputs": list(item["outputs"]),
                       "dependencies": [], "status": "planned", "applicability": "unit",
                       "budget_key": item["budget"], "cache_policy": item["cache"],
                       "failure_policy": item["failure"]})
    return {"stages": stages}


def test_artifact_index_tree_size_source_location_and_racing_copy(tmp_path):
    root = tmp_path / "out"; root.mkdir()
    (root / "a.json").write_text(json.dumps({"schema_version": 1, "kind": "K", "policy_id": "p"}))
    (root / "b.bin").write_bytes(b"bc")
    (root / "report.json").write_text("{}")
    (root / "artifacts.json").write_text("{}")
    values = coordinator._artifact_index(root)
    assert {item["kind"] for item in values} == {"K", "BinaryArtifact"}
    assert coordinator._tree_bytes(root) == sum(item.stat().st_size for item in root.iterdir())
    project = tmp_path / "project"; project.mkdir(); source = project / "a.c"
    source.write_text("int x;\n", encoding="utf-8")
    store = OutputStore(root / "store")
    snapshot = coordinator.snapshot_source(store, project, "a.c", file_hash(source))
    facts = {"tu": {"nodes": [{"id": "n", "source": {"expansion": {
        "file": "a.c", "line": 1, "column": 1}}}], "relations": []}}
    scope = {"records": [{"record_id": "tu", "physical_tu_id": "a" * 64,
                            "source": {"path": "a.c", "sha256": file_hash(source)}}]}
    candidate = {"physical_tu_ids": ["a" * 64], "node_ids": ["n"], "relation_ids": []}
    location = coordinator._candidate_location(
        candidate, facts, scope, {"tu": snapshot}, store.root,
        {"budgets": {"context_lines": 256, "context_characters": 65536}})
    assert location["context"]["status"] == "complete" and location["context"]["lines"][0]["line"] == 1
    assert coordinator._candidate_location({}, facts, scope, {}, store.root,
                                           {"budgets": {"context_lines": 1, "context_characters": 1}}) is None


def test_candidate_location_conservative_source_and_snapshot_branches(tmp_path):
    project = tmp_path / "project"; project.mkdir(); source = project / "a.c"
    source.write_text("abc\n", encoding="utf-8")
    out = tmp_path / "out"; store = OutputStore(out)
    snapshot = coordinator.snapshot_source(store, project, "a.c", file_hash(source))
    record = {"record_id": "tu", "physical_tu_id": "a" * 64,
              "source": {"path": "a.c", "sha256": file_hash(source)}}
    scope_value = {"records": [record]}
    candidate = {"physical_tu_ids": ["a" * 64], "node_ids": ["n"], "relation_ids": []}
    request_value = {"budgets": {"context_lines": 256, "context_characters": 65536}}
    assert coordinator._source_point({"column": 1}) == (None, None)
    assert coordinator._candidate_location(candidate, {}, scope_value, {}, out, request_value) is None
    empty = {"tu": {"nodes": [], "relations": []}}
    assert coordinator._candidate_location(candidate, empty, scope_value, {}, out, request_value) is None
    facts = {"tu": {"nodes": [{"id": "n", "source": {"line": 1, "column": 1,
                                                           "location_end": {"line": 1, "column": 1}}}],
                     "relations": []}}
    assert coordinator._candidate_location(candidate, facts, scope_value, {}, out, request_value) is None
    location = coordinator._candidate_location(candidate, facts, scope_value, {"tu": snapshot}, out, request_value)
    assert location is None  # A line number without file identity must not use the main TU.


def test_scope_cache_round_trip_rejects_corruption_and_partial(tmp_path):
    bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    request_path = tmp_path / "request.json"
    req = request(request_path, file_hash(bundle_path),
                  cache={"mode": "read-write", "resume": True})
    scope = {"target_id": "scope", "records": [{"record_id": "tu", "bitcode": {"sha256": "b" * 64},
             "compile_record_digest": "c" * 64}]}
    bundle = {"manifest": {"bundle_id": "bundle"}}
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "out", cache_path=tmp_path / "cache")
    data = tmp_path / "data"; data.mkdir(); (data / "proof.json").write_text("{}")
    payload = coordinator._cache_payload(complete_record(), [], [], [])
    analyzer._store_scope_cache(req, bundle, scope, stage_plan(), payload, data)
    (data / "proof.json").unlink()
    loaded, problem = analyzer._load_scope_cache(req, bundle, scope, stage_plan(), data)
    assert problem is None and loaded["record"]["status"] == "complete"
    assert (data / "proof.json").is_file()
    key = analyzer._scope_cache_key(req, bundle, scope, stage_plan())
    cache_file = analyzer._scope_cache_file(key)
    old_envelope = json.loads(cache_file.read_text())
    old_envelope["namespace"] = "unified-project-analysis-v1"
    cache_file.write_text(json.dumps(old_envelope))
    loaded, problem = analyzer._load_scope_cache(req, bundle, scope, stage_plan(), data)
    assert loaded is None and problem["code"] == "cache-corrupt"
    assert json.loads(cache_file.read_text()) == old_envelope
    cache_file.write_text("{}")
    loaded, problem = analyzer._load_scope_cache(req, bundle, scope, stage_plan(), data)
    assert loaded is None and problem["code"] == "cache-corrupt"
    partial = unified_document("ScopeAnalysisExecutionRecord", scope_id="scope", status="partial",
                               tu_modes=[], stages=[], counts={}, diagnostics=[],
                               frontier=[coordinator.diagnostic("x", "x", "x")])
    cache_file.unlink()
    analyzer._store_scope_cache(req, bundle, scope, stage_plan(),
                                coordinator._cache_payload(partial, [], [], []), data)
    assert not cache_file.exists()


def test_scope_cache_validates_artifacts_conflicts_incomplete_and_stage_hits(tmp_path):
    bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    request_path = tmp_path / "request.json"
    req = request(request_path, file_hash(bundle_path), cache={"mode": "read-write", "resume": True})
    scope_value = {"target_id": "scope", "records": [{"record_id": "tu", "bitcode": {"sha256": "b" * 64},
                                                         "compile_record_digest": "c" * 64}]}
    bundle = {"manifest": {"bundle_id": "bundle"}}
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "out", cache_path=tmp_path / "cache")
    plan = stage_plan(); stage = plan["stages"][0]
    execution = unified_document(
        "ScopeAnalysisExecutionRecord", scope_id="scope", status="complete", tu_modes=[],
        stages=[coordinator._stage_result(stage, "complete", cache="miss"),
                coordinator._stage_result({**stage, "id": "f" * 64, "stage": "disabled"},
                                          "complete", cache="disabled")],
        counts={}, diagnostics=[], frontier=[])
    data = tmp_path / "data"; data.mkdir(); (data / "proof.json").write_text("{}")
    payload = coordinator._cache_payload(execution, [], [], [])
    analyzer._store_scope_cache(req, bundle, scope_value, plan, payload, data)
    key = analyzer._scope_cache_key(req, bundle, scope_value, plan)
    cache_file = analyzer._scope_cache_file(key); artifact_root = cache_file.with_suffix(".artifacts")
    (data / "proof.json").unlink()
    warmed, problem = analyzer._load_scope_cache(req, bundle, scope_value, plan, data)
    assert problem is None and [item["cache"] for item in warmed["record"]["stages"]] == ["hit", "disabled"]

    (artifact_root / "proof.json").unlink()
    assert analyzer._load_scope_cache(req, bundle, scope_value, plan, data)[1]["code"] == "cache-corrupt"
    # Recreate the cache and force a destination conflict during restore.
    (data / "proof.json").write_text("{}")
    analyzer._store_scope_cache(req, bundle, scope_value, plan, payload, data)
    (data / "proof.json").write_text('{"different":true}')
    assert analyzer._load_scope_cache(req, bundle, scope_value, plan, data)[1]["code"] == "cache-corrupt"

    envelope = json.loads(cache_file.read_text())
    partial = unified_document(
        "ScopeAnalysisExecutionRecord", scope_id="scope", status="partial", tu_modes=[], stages=[], counts={},
        diagnostics=[], frontier=[coordinator.diagnostic("gap", "缺口", "gap")])
    envelope["payload"]["record"] = partial
    from memory_order_analyzer.contracts import identity
    envelope["payload_digest"] = identity(envelope["payload"])
    cache_file.write_text(canonical(envelope))
    (data / "proof.json").unlink()
    assert analyzer._load_scope_cache(req, bundle, scope_value, plan, data)[1]["code"] == "cache-corrupt"


def test_root_request_keeps_source_only_member_and_ignores_unbound_root(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir()
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "out")
    first = {"record_id": "source", "physical_tu_id": "a" * 64, "compile_record_digest": "b" * 64,
             "language": "c", "standard": "c17", "target": {"triple": "x", "data_layout": "e", "abi": {}}}
    second = {**first, "record_id": "empty", "physical_tu_id": "c" * 64}
    scope_value = {"target_id": "scope", "closed": True, "external_boundaries": [],
                   "records": [first, second]}
    monkeypatch.setattr(coordinator, "root_document", lambda kind, **fields: {"kind": kind, **fields})
    result = analyzer._root_request(
        {"explicit_roots": [{"kind": "program-entry", "symbol": "main"}]}, scope_value, data,
        {}, {}, {"source": {"kind": "SourceSemanticFacts"}}, {}, {}, [])
    assert len(result["members"]) == 1
    assert result["members"][0]["evidence"][0]["kind"] == "SourceSemanticFacts"
    assert result["explicit_roots"] == []


def test_scope_cache_key_accepts_ast_only_record_without_bitcode(tmp_path):
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "output")
    request = {"semantic_digest": "a" * 64}
    bundle = {"manifest": {"bundle_id": "b" * 64}}
    scope_value = {
        "target_id": "scope",
        "records": [
            {
                "record_id": "source-only",
                "bitcode": None,
                "compile_record_digest": "c" * 64,
            }
        ],
    }
    plan = {"stages": []}

    first = analyzer._scope_cache_key(request, bundle, scope_value, plan)
    second = analyzer._scope_cache_key(request, bundle, scope_value, plan)

    assert first == second
    assert len(first) == 64


def test_scope_pipeline_happy_path_keeps_formal_and_bounded_results(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "producer": {"family": "clang"},
           "compile_record_digest": "b" * 64, "language": "c++", "standard": "c++17",
           "target": {"triple": "x86_64", "data_layout": "e-p:64:64", "abi": {}},
           "bitcode": {"sha256": "c" * 64}, "source": None}
    scope = {"target_id": "scope", "target_triple": "x86_64", "closed": True,
             "external_boundaries": [], "records": [rec]}
    ingestion = {"record_artifacts": [{"record_id": "tu", "status": "published",
                                        "facts_status": "complete", "artifact_key": "d" * 64}]}
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "output", clock=lambda: 0)
    analyzer.started = 0
    source_facts = {"tu": {"profile_id": "e" * 64, "nodes": [], "relations": []}}
    monkeypatch.setattr(analyzer, "_scope_source_analysis",
                        lambda *args: ({"status": "complete", "frontier": []},
                                       {"source_candidates": [{"id": "candidate", "shape": "atomic", "reason": "AST candidate"}]},
                                       source_facts, {}))
    thread_dir = data / "thread"; (thread_dir / "effects/summaries").mkdir(parents=True)
    (thread_dir / "effects/summaries/s.json").write_text('{"status":"complete"}')
    (data / "graphs").mkdir(); (data / "graphs/scope.json").write_text('{"status":"complete"}')
    monkeypatch.setattr(analyzer, "_run_roots_and_threads",
                        lambda *args: (data / "roots", thread_dir, {}, [], [], None))
    monkeypatch.setattr(analyzer, "_run_thread_entry", lambda *args: {"status": "complete"})
    for relative in ("execution-roots/scope.json", "thread-entry-sites/scope.json",
                     "provenance-graphs/scope.json", "analysis/scope/concurrent/candidate-graph.json",
                     "analysis/scope/concurrent/access-protection.json"):
        path = data / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"kind": Path(relative).stem}))
    monkeypatch.setattr(coordinator, "run_demand", lambda *args: {"status": "complete"})
    monkeypatch.setattr(coordinator, "run_cpp_lifecycle", lambda *args: {"status": "complete"})
    monkeypatch.setattr(coordinator, "run_raii", lambda *args: {"status": "complete"})
    monkeypatch.setattr(coordinator, "run_provenance", lambda *args: {"status": "complete"})
    monkeypatch.setattr(coordinator, "run_concurrent", lambda *args: {"status": "complete"})
    publication = {"status": "complete", "semantic_digest": "f" * 64,
                   "findings": [{"id": "risk", "reason": "relaxed"}]}
    monkeypatch.setattr(coordinator, "run_publication", lambda *args: publication)
    graph_dir = data / "analysis/scope/publication/graphs"; graph_dir.mkdir(parents=True)
    (graph_dir / "g.json").write_text(json.dumps({"assessments": [{"id": "ok", "status": "discharged"}]}))
    atomic = {"status": "complete", "semantic_digest": "1" * 64, "language_standard": "c++17",
              "findings": [{"id": "atomic-risk", "reason": "fence"}]}
    monkeypatch.setattr(coordinator, "run_atomic", lambda *args: [atomic])
    atomic_dir = data / "analysis/scope/advanced-atomic/cpp17"; atomic_dir.mkdir(parents=True)
    (atomic_dir / "advanced-publication-protocol-overlay.json").write_text(json.dumps({
        "protocols": [{"id": "atomic-ok", "assessment": "discharged-within-bounded-model"}]}))
    req = {"source_assistance": "auto", "cancel_file": None,
           "budgets": {"worklist_items": 2, "deadline_seconds": 100,
                       "context_lines": 256, "context_characters": 65536}, "explicit_roots": []}
    record_value, formal, candidates, bounded = analyzer._scope(
        req, stage_plan(), {"manifest_path": tmp_path / "bundle.json"}, scope, data, store, ingestion, {}, {}, tmp_path)
    assert record_value["status"] == "complete"
    assert len(formal) == 2 and len(candidates) == 1 and len(bounded) == 2


def test_run_publishes_cancelled_report_without_ingestion(tmp_path, monkeypatch):
    bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    cancel = tmp_path / "cancel"; cancel.write_text("stop")
    request_path = tmp_path / "request.json"
    req = request(request_path, file_hash(bundle_path), cancel_file=str(cancel.resolve()))
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "source": None}
    bundle = {"manifest": {"bundle_id": "bundle"}, "manifest_path": bundle_path,
              "records": {"tu": rec}, "source_requests": {},
              "scopes": [{"target_id": "scope", "records": [rec]}]}
    plan = unified_document("UnifiedAnalysisPlan", request_digest=req["semantic_digest"], bundle_id="bundle",
                            selected_scopes=["scope"], stages=[], edges=[], diagnostics=[], frontier=[])
    monkeypatch.setattr(coordinator, "preflight_bundle", lambda *args: bundle)
    monkeypatch.setattr(coordinator, "build_plan", lambda *args: plan)
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "result",
                                               ingest=lambda *args, **kwargs: pytest.fail("must not ingest"))
    report = analyzer.run()
    assert report["status"] == "cancelled" and report["exit_code"] == 2
    assert json.loads((tmp_path / "result/report.json").read_text())["verdict"] == "inconclusive"


def test_run_publishes_deadline_report_without_ingestion(tmp_path, monkeypatch):
    bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    request_path = tmp_path / "request.json"
    req = request(request_path, file_hash(bundle_path))
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "source": None}
    bundle = {"manifest": {"bundle_id": "bundle"}, "manifest_path": bundle_path,
              "records": {"tu": rec}, "source_requests": {},
              "scopes": [{"target_id": "scope", "records": [rec]}]}
    plan = unified_document("UnifiedAnalysisPlan", request_digest=req["semantic_digest"], bundle_id="bundle",
                            selected_scopes=["scope"], stages=[], edges=[], diagnostics=[], frontier=[])
    monkeypatch.setattr(coordinator, "preflight_bundle", lambda *args: bundle)
    monkeypatch.setattr(coordinator, "build_plan", lambda *args: plan)
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "deadline-result",
                                               ingest=lambda *args, **kwargs: pytest.fail("must not ingest"))
    monkeypatch.setattr(analyzer, "_check_stop",
                        lambda *args: (_ for _ in ()).throw(AnalysisError("analysis_deadline", "expired")))
    report = analyzer.run()
    assert report["status"] == "partial" and report["verdict"] == "inconclusive"
    assert report["frontier"][0]["code"] == "analysis_deadline"


def test_source_inputs_snapshots_and_source_stage(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); source = tmp_path / "unit.c"
    source.write_text("int x;\n", encoding="utf-8")
    profile = {"profile_id": "p" * 64, "source": {"path": str(source), "sha256": file_hash(source)},
               "working_directory": str(tmp_path), "argv": ["clang", "-c", "unit.c"],
               "compiler": {"family": "clang", "version": "21", "path": "/usr/bin/clang"},
               "replay": {"clang_version": "21"}, "language": "c", "standard": "c17", "abi": {}}
    source_request = {"physical_tu_id": "a" * 64, "profile": profile}
    source_request_path = tmp_path / "source-request.json"; source_request_path.write_text("{}")
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "source": {
        "path": "unit.c", "sha256": file_hash(source)}, "bitcode": {"sha256": "b" * 64}}
    bundle = {"manifest_path": tmp_path / "bundle.json", "records": {"tu": rec},
              "source_requests": {"tu": {"resolved_path": source_request_path}}}
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "out")
    monkeypatch.setattr(coordinator, "_source_request", lambda path: source_request)
    monkeypatch.setattr(coordinator, "document", lambda kind, **fields: {"kind": kind, **fields})
    inputs = analyzer._write_request_inputs({}, bundle, data, OutputStore(data))
    assert inputs["tu"]["request"] == source_request and (data / "contexts" / f"{'a' * 64}.json").is_file()
    assert inputs["tu"]["path"].name == f"{'a' * 64}.json"
    bad = {**source_request, "physical_tu_id": "z" * 64}
    monkeypatch.setattr(coordinator, "_source_request", lambda path: bad)
    with pytest.raises(AnalysisError, match="TU differs"):
        analyzer._write_request_inputs({}, bundle, data, OutputStore(data))
    mismatch = {**source_request, "profile": {**profile, "source": {**profile["source"], "sha256": "0" * 64}}}
    monkeypatch.setattr(coordinator, "_source_request", lambda path: mismatch)
    with pytest.raises(AnalysisError, match="lineage"):
        analyzer._write_request_inputs({}, bundle, data, OutputStore(data))
    unsupported = {**source_request, "profile": {**profile,
                    "compiler": {"family": "clang", "version": "21", "path": "clang-cl"}}}
    monkeypatch.setattr(coordinator, "_source_request", lambda path: unsupported)
    with pytest.raises(AnalysisError, match="clang-cl"):
        analyzer._write_request_inputs({}, bundle, data, OutputStore(data))
    snapshots, failures = analyzer._snapshot_sources(bundle, OutputStore(tmp_path / "snapshots"))
    assert "tu" in snapshots and not failures
    source.unlink()
    snapshots, failures = analyzer._snapshot_sources(bundle, OutputStore(tmp_path / "missing-snapshots"))
    assert not snapshots and failures["tu"].code == "source_unavailable"

    # Exercise source/IR preparation and the missing-source declaration without
    # depending on the external workers in this unit test.
    source.write_text("int x;\n", encoding="utf-8")
    second = {**rec, "record_id": "missing", "physical_tu_id": "c" * 64, "source": None}
    scope = {"target_id": "scope", "records": [rec, second]}
    source_inputs = {"tu": {"request": source_request, "path": data / "inputs/source.json"}}
    source_inputs["tu"]["path"].parent.mkdir(parents=True, exist_ok=True); source_inputs["tu"]["path"].write_text("{}")
    (data / f"facts/{'d' * 64}.json").parent.mkdir(); (data / f"facts/{'d' * 64}.json").write_text("{}")
    monkeypatch.setattr(coordinator, "read_document", lambda *args: {"kind": "ModuleFacts"})
    monkeypatch.setattr(coordinator, "source_document", lambda kind, **fields: {"kind": kind, **fields})
    monkeypatch.setattr(coordinator, "degraded_document", lambda kind, **fields: {"kind": kind, **fields})
    monkeypatch.setattr(coordinator, "input_hash", lambda path: {"path": str(path), "sha256": file_hash(path)})
    def source_index(request_path, artifact_store, output, worker):
        for relative, kind in ((f"source-facts/{'a' * 64}.json", "SourceSemanticFacts"),
                               (f"llvm-binding-facts/{'d' * 64}.json", "LLVMSourceBindingFacts"),
                               ("entity-index.json", "ProgramEntityIndex"),
                               ("source-ir-binding.json", "SourceIRBinding"),
                               ("canonical-object-overlay.json", "CanonicalObjectOverlay")):
            path = output / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"kind": kind}))
        return {"status": "complete", "frontier": []}
    monkeypatch.setattr(coordinator, "index_source_evidence", source_index)
    monkeypatch.setattr(coordinator, "analyze_degraded_source", lambda *args: {"status": "partial"})
    monkeypatch.setattr(coordinator, "read_source_document",
                        lambda path, kind: json.loads(Path(path).read_text()))
    source_report, degraded, facts, globals_ = analyzer._scope_source_analysis(
        {"source_assistance": "auto"}, {}, scope, data, OutputStore(data), source_inputs,
        {"tu": {"artifact_key": "d" * 64}})
    assert source_report["status"] == "complete" and degraded["status"] == "partial"
    assert "tu" in facts and set(globals_) == {"ProgramEntityIndex", "SourceIRBinding", "CanonicalObjectOverlay"}
    assert analyzer._scope_source_analysis({"source_assistance": "disabled"}, {}, scope, data,
                                           OutputStore(data), {}, {}) == (None, None, {}, {})


def test_scope_source_analysis_orders_requests_by_physical_tu(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "out")
    records = [
        {"record_id": "a-record", "physical_tu_id": "b" * 64,
         "bitcode": {"sha256": "1" * 64}},
        {"record_id": "z-record", "physical_tu_id": "a" * 64,
         "bitcode": {"sha256": "2" * 64}},
    ]
    source_inputs = {}
    module_by_record = {}
    for record in records:
        record_id = record["record_id"]
        source_path = data / "inputs" / f"{record_id}.json"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("{}", encoding="utf-8")
        source_inputs[record_id] = {
            "path": source_path,
            "request": {"physical_tu_id": record["physical_tu_id"], "profile": {"profile_id": record_id}},
        }
        artifact_key = ("3" if record_id == "a-record" else "4") * 64
        module_by_record[record_id] = {"artifact_key": artifact_key}
        facts_path = data / "facts" / f"{artifact_key}.json"
        facts_path.parent.mkdir(parents=True, exist_ok=True)
        facts_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(coordinator, "read_document", lambda *args: {"kind": "ModuleFacts"})
    monkeypatch.setattr(coordinator, "source_document", lambda kind, **fields: {"kind": kind, **fields})
    captured = {}
    degraded = {}

    def capture_request(request_path, *args):
        captured.update(json.loads(Path(request_path).read_text(encoding="utf-8")))
        return {"status": "complete", "frontier": []}

    def capture_degraded(kind, **fields):
        degraded.update(fields)
        raise RuntimeError("captured")

    monkeypatch.setattr(coordinator, "index_source_evidence", capture_request)
    monkeypatch.setattr(coordinator, "degraded_document", capture_degraded)
    with pytest.raises(RuntimeError, match="captured"):
        analyzer._scope_source_analysis(
            {"source_assistance": "auto"}, {}, {"target_id": "scope", "records": records},
            data, OutputStore(data), source_inputs, module_by_record)

    expected = [
        str(data / "requests/scope" / ("source-" + "a" * 64 + ".json")),
        str(data / "requests/scope" / ("source-" + "b" * 64 + ".json")),
    ]
    assert captured["source_requests"] == expected
    assert [item["path"] for item in degraded["source_requests"]] == sorted(
        expected)


def test_root_request_worklist_and_thread_entry_adapters(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "out", clock=lambda: 0)
    analyzer.started = 0
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "compile_record_digest": "b" * 64,
           "language": "c", "standard": "c17", "target": {"triple": "x", "data_layout": "e", "abi": {}},
           "bitcode": {"sha256": "c" * 64}}
    scope = {"target_id": "scope", "target_triple": "x", "closed": True,
             "external_boundaries": [], "records": [rec]}
    (data / f"facts/{'d' * 64}.json").parent.mkdir(); (data / f"facts/{'d' * 64}.json").write_text("{}")
    monkeypatch.setattr(coordinator, "read_document", lambda *args: {"kind": "ModuleFacts"})
    monkeypatch.setattr(coordinator, "root_document", lambda kind, **fields: {"kind": kind, **fields})
    request_value = {"explicit_roots": [{"kind": "program-entry", "symbol": "main",
                                          "artifact_key": "d" * 64, "function_id": "f"}]}
    root_request = analyzer._root_request(
        request_value, scope, data, {"tu": {"artifact_key": "d" * 64}}, {}, {},
        {"ProgramEntityIndex": {}, "SourceIRBinding": {}, "ignored": {}},
        {"tu": [{"kind": "ThreadLocalFacts", "id": "x", "digest": "1" * 64, "path": "x"}]},
        [{"kind": "ThreadContextGraph", "id": "g", "digest": "2" * 64, "path": "g"}])
    assert root_request["explicit_roots"][0]["kind"] == "program"
    assert len(root_request["members"][0]["evidence"]) == 2

    monkeypatch.setattr(analyzer, "_root_request", lambda *args: {"kind": "RootRequest"})
    calls = {"root": 0}
    def roots(request_path, artifact_store, output):
        calls["root"] += 1; (output / "execution-roots").mkdir(parents=True)
        entry = {"artifact_key": "d" * 64, "function_id": "f"}
        (output / "execution-roots/index.json").write_text(json.dumps({
            "roots": [{"status": "complete", "entry": entry, "arguments": []}]}))
        (output / "plans").mkdir(); (output / "plans/p.json").write_text("{}")
        (output / "thread-creation-sites").mkdir(); (output / "thread-creation-sites/index.json").write_text("{}")
    monkeypatch.setattr(coordinator, "plan_execution_roots", roots)
    monkeypatch.setattr(coordinator, "thread_document", lambda kind, **fields: {"kind": kind, **fields})
    def threads(request_path, artifact_store, output, worker, source=None):
        for relative in (f"thread-local/{'d' * 64}.json", f"execution-order/{'d' * 64}.json",
                         "graphs/g.json", "effects/summaries/s.json"):
            path = output / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"context_id": "ctx", "kind": Path(relative).stem}))
        return {"status": "complete"}
    monkeypatch.setattr(coordinator, "model_threads", threads)
    req = {"cancel_file": None, "budgets": {"deadline_seconds": 100, "worklist_items": 3}}
    root_dir, thread_dir, members, globals_, frontier, p3_request = analyzer._run_roots_and_threads(
        req, scope, data, store, {"tu": {"artifact_key": "d" * 64}}, {}, {}, {})
    assert calls["root"] == 2 and root_dir and thread_dir and not frontier
    assert members["tu"] and {item["kind"] for item in globals_} == {"ThreadContextGraph", "EffectSummary"}

    monkeypatch.setattr(coordinator, "thread_entry_document", lambda kind, **fields: {"kind": kind, **fields})
    monkeypatch.setattr(coordinator, "c_api_profile", lambda family, target, layout: {"id": family})
    monkeypatch.setattr(coordinator, "load_model_registry", lambda: [])
    def entries(request_path, artifact_store, output):
        (output / "sites").mkdir(parents=True); (output / "sites/index.json").write_text("{}")
        (output / "roots").mkdir(); (output / "roots/overlay.json").write_text("{}")
        return {"status": "complete"}
    monkeypatch.setattr(coordinator, "discover_thread_entries", entries)
    report = analyzer._run_thread_entry(req, scope, data, store, {"tu": {"artifact_key": "d" * 64}},
                                        {}, {}, {}, root_dir, members)
    assert report["status"] == "complete" and (data / "thread-entry-sites/scope.json").is_file()
    assert analyzer._run_thread_entry(req, scope, data, store, {}, {}, {}, {}, None, {}) is None


def test_helper_error_fallbacks_cache_guards_and_source_points(tmp_path, monkeypatch):
    source = tmp_path / "source"; source.write_text("x")
    store = OutputStore(tmp_path / "store")
    real_link = coordinator.os.link
    calls = {"count": 0}
    def fail_first_link(*args):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("no link")
        return real_link(*args)
    monkeypatch.setattr(coordinator.os, "link", fail_first_link)
    copied = coordinator._copy_once(store, source, "fallback/x")
    assert copied.read_text() == "x"
    monkeypatch.setattr(coordinator.os, "link", real_link)

    root = tmp_path / "index"; root.mkdir()
    (root / "source-snapshots").mkdir(); (root / "source-snapshots/a").write_text("snapshot")
    (root / "broken.json").write_text("{")
    kinds = {item["kind"] for item in coordinator._artifact_index(root)}
    assert kinds == {"SourceSnapshot", "BinaryArtifact"}
    with pytest.raises(AnalysisError, match="invalid shape"):
        coordinator._validate_cache_payload({})

    assert coordinator._source_point(None) == (None, None)
    assert coordinator._source_point({"line": 3}) == ({"line": 3}, None)
    assert coordinator._source_point({"spelling": {"line": 2}, "spelling_end": {"line": 2}})[1] == {"line": 2}
    scope_value = {"records": [{"record_id": "tu", "physical_tu_id": "a" * 64, "source": None}]}
    assert coordinator._candidate_location({"physical_tu_ids": ["a" * 64]}, {}, scope_value, {}, root,
                                           {"budgets": {"context_lines": 1, "context_characters": 1}}) is None

    request_path = tmp_path / "request.json"; bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    req = request(request_path, file_hash(bundle_path), cache={"mode": "disabled", "resume": False})
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "out", cache_path=tmp_path / "cache")
    bundle = {"manifest": {"bundle_id": "bundle"}}
    scope_cache = {"target_id": "scope", "records": [{"record_id": "tu", "bitcode": {"sha256": "b" * 64},
                                                         "compile_record_digest": "c" * 64}]}
    assert analyzer._load_scope_cache(req, bundle, scope_cache, stage_plan(), tmp_path)[0] is None
    req["cache"] = {"mode": "read-write", "resume": True}
    assert analyzer._load_scope_cache(req, bundle, scope_cache, stage_plan(), tmp_path)[0] is None
    req["cache"] = {"mode": "read-only", "resume": True}
    analyzer._store_scope_cache(req, bundle, scope_cache, stage_plan(),
                                coordinator._cache_payload(complete_record(), [], [], []), tmp_path)
    assert not analyzer._scope_cache_file(analyzer._scope_cache_key(req, bundle, scope_cache, stage_plan())).exists()


def test_empty_and_budgeted_root_worklists_and_cpp_entry_models(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "out", clock=lambda: 0)
    analyzer.started = 0
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "compile_record_digest": "b" * 64,
           "language": "c++", "standard": "c++20", "target": {"triple": "x", "data_layout": "e", "abi": {}},
           "bitcode": {"sha256": "c" * 64}}
    scope_value = {"target_id": "scope", "target_triple": "x", "closed": True,
                   "external_boundaries": [], "records": [rec]}
    monkeypatch.setattr(analyzer, "_root_request", lambda *args: {"kind": "RootRequest"})
    def empty_roots(request_path, artifact_store, output):
        write = lambda relative, value: (output / relative).write_text(json.dumps(value))
        (output / "execution-roots").mkdir(parents=True); write("execution-roots/index.json", {"roots": []})
        (output / "plans").mkdir(); write("plans/p.json", {})
        (output / "thread-creation-sites").mkdir(); write("thread-creation-sites/index.json", {})
    monkeypatch.setattr(coordinator, "plan_execution_roots", empty_roots)
    req = {"cancel_file": None, "budgets": {"deadline_seconds": 100, "worklist_items": 1}}
    root_dir, thread_dir, _, _, frontier, p3_request = analyzer._run_roots_and_threads(
        req, scope_value, data, store, {}, {}, {}, {})
    assert root_dir and thread_dir is None and not frontier

    # A changing root with a one-item budget executes once and records exhaustion.
    def one_root(request_path, artifact_store, output):
        (output / "execution-roots").mkdir(parents=True)
        (output / "execution-roots/index.json").write_text(json.dumps({"roots": [{
            "status": "complete", "entry": {"artifact_key": "d" * 64, "function_id": "f"}, "arguments": []}]}))
        (output / "plans").mkdir(); (output / "plans/p.json").write_text("{}")
        (output / "thread-creation-sites").mkdir(); (output / "thread-creation-sites/index.json").write_text("{}")
    def threads(request_path, artifact_store, output, worker, source=None):
        (output / "graphs").mkdir(parents=True); (output / "graphs/g.json").write_text("{}")
        (output / "effects/summaries").mkdir(parents=True)
    monkeypatch.setattr(coordinator, "plan_execution_roots", one_root)
    monkeypatch.setattr(coordinator, "thread_document", lambda kind, **fields: {"kind": kind, **fields})
    monkeypatch.setattr(coordinator, "model_threads", threads)
    import shutil
    shutil.rmtree(data / "analysis/scope")
    for relative in ("execution-roots", "thread-creation-sites", "root-plans"):
        shutil.rmtree(data / relative)
    _, _, _, _, frontier, _ = analyzer._run_roots_and_threads(req, scope_value, data, store, {}, {}, {}, {})
    assert frontier[0]["code"] == "demand-worklist-budget"

    root_for_entry = data / "entry-root"; (root_for_entry / "execution-roots").mkdir(parents=True)
    (root_for_entry / "execution-roots/index.json").write_text(json.dumps({"roots": []}))
    (root_for_entry / "plans").mkdir(); (root_for_entry / "plans/p.json").write_text("{}")
    model = {"id": "cpp-model", "target": "x", "data_layout": "e", "standards": ["c++20"]}
    monkeypatch.setattr(coordinator, "load_model_registry", lambda: [model, {**model, "id": "wrong", "target": "y"}])
    monkeypatch.setattr(coordinator, "thread_entry_document", lambda kind, **fields: {"kind": kind, **fields})
    captured = {}
    def entries(path, artifact_store, output):
        captured.update(json.loads(Path(path).read_text()))
        (output / "sites").mkdir(parents=True); (output / "sites/index.json").write_text("{}")
        (output / "roots").mkdir(); (output / "roots/overlay.json").write_text("{}")
        return {"status": "partial"}
    monkeypatch.setattr(coordinator, "discover_thread_entries", entries)
    assert analyzer._run_thread_entry(req, scope_value, data, store, {}, {}, {}, {},
                                      root_for_entry, {})["status"] == "partial"
    assert [item["id"] for item in captured["model_profiles"]] == ["cpp-model"]


def test_scope_conservatively_handles_source_root_and_adapter_failures(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "producer": {"family": "clang"},
           "compile_record_digest": "b" * 64, "language": "c++", "standard": "c++17",
           "target": {"triple": "x", "data_layout": "e", "abi": {}},
           "bitcode": {"sha256": "c" * 64}, "source": None}
    scope_value = {"target_id": "scope", "target_triple": "x", "closed": False,
                   "external_boundaries": [{"kind": "plugin"}], "records": [rec]}
    ingestion = {"record_artifacts": []}
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "out", clock=lambda: 0)
    analyzer.started = 0
    monkeypatch.setattr(analyzer, "_scope_source_analysis", lambda *args: (_ for _ in ()).throw(ValueError("bad AST")))
    monkeypatch.setattr(analyzer, "_run_roots_and_threads", lambda *args: (_ for _ in ()).throw(ValueError("bad root")))
    monkeypatch.setattr(analyzer, "_run_thread_entry", lambda *args: None)
    monkeypatch.setattr(coordinator, "run_demand", lambda *args: [{"status": "complete"}, {"status": "partial"}])
    monkeypatch.setattr(coordinator, "run_cpp_lifecycle", lambda *args: None)
    monkeypatch.setattr(coordinator, "run_raii", lambda *args: (_ for _ in ()).throw(AnalysisError("raii", "bad")))
    monkeypatch.setattr(coordinator, "run_provenance", lambda *args: {"thread_modeling": "resolved"})
    monkeypatch.setattr(coordinator, "run_concurrent", lambda *args: {"status": "failed"})
    monkeypatch.setattr(coordinator, "run_publication", lambda *args: {
        "status": "partial", "findings": [{"id": "upstream-risk"}]})
    monkeypatch.setattr(coordinator, "run_atomic", lambda *args: [{
        "status": "partial", "findings": [{"id": "atomic-risk"}]}])
    req = {"source_assistance": "required", "cancel_file": None, "explicit_roots": [],
           "budgets": {"worklist_items": 1, "deadline_seconds": 100,
                       "context_lines": 256, "context_characters": 65536}}
    result, formal, candidates, bounded = analyzer._scope(
        req, stage_plan(), {"manifest_path": tmp_path / "bundle.json"}, scope_value, data, store, ingestion, {}, {}, tmp_path)
    assert result["status"] == "failed" and not formal and not bounded
    assert len(candidates) == 2 and all(item["conclusion"]["verdict"] == "inconclusive" for item in candidates)
    assert {item["code"] for item in result["frontier"]} >= {
        "bc-unavailable", "source-failed", "root-failed", "thread-entry-incomplete", "raii",
        "projection-evidence-incomplete"}


def test_execute_scopes_uses_cache_and_isolates_crash(tmp_path, monkeypatch):
    request_path = tmp_path / "request.json"; bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    req = request(request_path, file_hash(bundle_path))
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "out", clock=lambda: 0)
    analyzer.started = 0
    scopes = []
    for name in ("a", "b", "c"):
        scopes.append({"target_id": name, "records": [{"record_id": name, "physical_tu_id": name * 64,
                                                         "source": None}]})
    bundle = {"scopes": scopes, "source_requests": {}}
    cached = coordinator._cache_payload(complete_record("a"), [], [], [])
    monkeypatch.setattr(analyzer, "_load_scope_cache",
                        lambda request_value, bundle_value, scope_value, plan, data:
                        (cached, coordinator.diagnostic("cache-corrupt", "坏", "bad"))
                        if scope_value["target_id"] == "a" else (None, None))
    def analyze_scope(*args):
        scope_value = args[3]
        if scope_value["target_id"] == "b":
            raise RuntimeError("worker crash")
        return complete_record(scope_value["target_id"]), [], [], []
    monkeypatch.setattr(analyzer, "_scope", analyze_scope)
    payloads, diagnostics = analyzer._execute_scopes(
        req, stage_plan(), bundle, tmp_path / "data", {"record_artifacts": []}, {}, {}, tmp_path)
    assert [item["record"]["scope_id"] for item in payloads] == ["a", "b", "c"]
    assert payloads[1]["record"]["status"] == "failed" and diagnostics[0]["code"] == "cache-corrupt"


def test_execute_scopes_stores_only_when_all_complete(tmp_path, monkeypatch):
    request_path = tmp_path / "request.json"; bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    req = request(request_path, file_hash(bundle_path))
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "out", clock=lambda: 0)
    analyzer.started = 0
    scope_value = {"target_id": "scope", "records": [{"record_id": "tu", "physical_tu_id": "a" * 64,
                                                         "source": None}]}
    monkeypatch.setattr(analyzer, "_load_scope_cache", lambda *args: (None, None))
    monkeypatch.setattr(analyzer, "_scope", lambda *args: (complete_record(), [], [], []))
    stored = []
    monkeypatch.setattr(analyzer, "_store_scope_cache", lambda *args: stored.append(args[2]["target_id"]))
    payloads, diagnostics = analyzer._execute_scopes(
        req, stage_plan(), {"scopes": [scope_value], "source_requests": {}}, tmp_path / "data",
        {"record_artifacts": []}, {}, {}, tmp_path)
    assert payloads[0]["record"]["status"] == "complete" and stored == ["scope"] and not diagnostics


def test_scope_disabled_source_and_not_applicable_cpp_stages(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "producer": {"family": "clang"},
           "compile_record_digest": "b" * 64, "language": "c", "standard": "c17",
           "target": {"triple": "x", "data_layout": "e", "abi": {}},
           "bitcode": {"sha256": "c" * 64}, "source": None}
    scope_value = {"target_id": "scope", "target_triple": "x", "closed": True,
                   "external_boundaries": [], "records": [rec]}
    ingestion = {"record_artifacts": [{"record_id": "tu", "status": "published",
                                        "facts_status": "complete", "artifact_key": "d" * 64}]}
    plan = stage_plan()
    for stage in plan["stages"]:
        if stage["stage"] in {"cpp-thread-lifecycle", "raii-synchronization"}:
            stage["status"] = "skipped-not-applicable"
    analyzer = coordinator.AnalysisCoordinator(tmp_path / "request", tmp_path / "out", clock=lambda: 0)
    analyzer.started = 0
    monkeypatch.setattr(analyzer, "_scope_source_analysis", lambda *args: (None, None, {}, {}))
    monkeypatch.setattr(analyzer, "_run_roots_and_threads", lambda *args: (None, None, {}, [], [], None))
    monkeypatch.setattr(analyzer, "_run_thread_entry", lambda *args: None)
    for name in ("run_demand", "run_provenance", "run_concurrent", "run_publication"):
        monkeypatch.setattr(coordinator, name, lambda *args: {"status": "complete"})
    monkeypatch.setattr(coordinator, "run_atomic", lambda *args: [{"status": "complete"}])
    result, _, _, _ = analyzer._scope(
        {"source_assistance": "disabled", "cancel_file": None, "explicit_roots": [],
         "budgets": {"worklist_items": 1, "deadline_seconds": 100,
                     "context_lines": 256, "context_characters": 65536}},
        plan, {}, scope_value, data, store, ingestion, {}, {}, tmp_path)
    statuses = {item["stage"]: item["status"] for item in result["stages"]}
    assert statuses["source-evidence"] == "skipped-not-applicable"
    assert statuses["cpp-thread-lifecycle"] == statuses["raii-synchronization"] == "skipped-not-applicable"


@pytest.mark.parametrize("scope_status,collection,expected_status,expected_verdict,expected_exit", [
    ("complete", "none", "complete", "no-finding-within-supported-model", 0),
    ("complete", "risk", "complete", "risk", 3),
    ("failed", "none", "failed", "failed", 1),
    ("partial", "risk", "partial", "inconclusive", 2),
])
def test_project_aggregation_exit_code_matrix(tmp_path, monkeypatch, scope_status, collection,
                                              expected_status, expected_verdict, expected_exit):
    case = f"{scope_status}-{collection}"
    root = tmp_path / case; root.mkdir()
    bundle_path = root / "bundle.json"; bundle_path.write_text("{}")
    request_path = root / "request.json"; req = request(request_path, file_hash(bundle_path))
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "source": None}
    scope_value = {"target_id": "scope", "records": [rec]}
    bundle = {"manifest": {"bundle_id": "bundle"}, "manifest_path": bundle_path,
              "records": {"tu": rec}, "source_requests": {}, "scopes": [scope_value]}
    plan = unified_document("UnifiedAnalysisPlan", request_digest=req["semantic_digest"], bundle_id="bundle",
                            selected_scopes=["scope"], stages=[], edges=[], diagnostics=[], frontier=[])
    monkeypatch.setattr(coordinator, "preflight_bundle", lambda *args: bundle)
    monkeypatch.setattr(coordinator, "build_plan", lambda *args: plan)
    def ingest(path, data, worker, cache_path=None):
        data.mkdir(); (data / "report.json").write_text(json.dumps({"record_artifacts": []}))
        return {"record_artifacts": []}
    frontier = [] if scope_status == "complete" else [coordinator.diagnostic("gap", "缺口", "gap", scope_id="scope")]
    execution = unified_document(
        "ScopeAnalysisExecutionRecord", scope_id="scope", status=scope_status,
        tu_modes=[], stages=[], counts={}, diagnostics=[], frontier=frontier)
    formal = [project_assessment("scope", {"id": "risk"}, [
        provenance("UnitFact", "fact", "org.rvport.memory-order-analyzer.unit", 1, "a" * 64)],
        category="formal")]
    payload = coordinator._cache_payload(execution, formal if collection == "risk" else [], [], [])
    analyzer = coordinator.AnalysisCoordinator(request_path, root / "result", ingest=ingest)
    monkeypatch.setattr(analyzer, "_write_request_inputs", lambda *args: {})
    monkeypatch.setattr(analyzer, "_snapshot_sources", lambda *args: ({}, {}))
    monkeypatch.setattr(analyzer, "_execute_scopes", lambda *args: ([payload], []))
    report = analyzer.run()
    assert (report["status"], report["verdict"], report["exit_code"]) == (
        expected_status, expected_verdict, expected_exit)


def test_project_aggregation_records_snapshot_finding_and_output_budgets(tmp_path, monkeypatch):
    bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    request_path = tmp_path / "request.json"
    budgets = {**expected_unified_protocol()["budgets"], "findings": 1,
               "artifact_bytes": 1024, "request_output_bytes": 1024}
    req = request(request_path, file_hash(bundle_path), budgets=budgets)
    rec = {"record_id": "tu", "physical_tu_id": "a" * 64, "source": None}
    scope_value = {"target_id": "scope", "records": [rec]}
    bundle = {"manifest": {"bundle_id": "bundle"}, "manifest_path": bundle_path,
              "records": {"tu": rec}, "source_requests": {}, "scopes": [scope_value]}
    plan = unified_document("UnifiedAnalysisPlan", request_digest=req["semantic_digest"], bundle_id="bundle",
                            selected_scopes=["scope"], stages=[], edges=[], diagnostics=[], frontier=[])
    monkeypatch.setattr(coordinator, "preflight_bundle", lambda *args: bundle)
    monkeypatch.setattr(coordinator, "build_plan", lambda *args: plan)
    def ingest(path, data, worker, cache_path=None):
        data.mkdir(); (data / "report.json").write_text(json.dumps({"record_artifacts": []}))
        return {"record_artifacts": []}
    prov = [provenance("UnitFact", "fact", "org.rvport.memory-order-analyzer.unit", 1, "a" * 64)]
    findings = [project_assessment("scope", {"id": f"risk-{index}"}, prov, category="formal")
                for index in range(2)]
    execution = complete_record()
    payload = coordinator._cache_payload(execution, findings, [], [])
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "result", ingest=ingest)
    monkeypatch.setattr(analyzer, "_write_request_inputs", lambda *args: {})
    monkeypatch.setattr(analyzer, "_snapshot_sources", lambda *args: (
        {}, {"tu": AnalysisError("source_unavailable", "missing")}))
    monkeypatch.setattr(analyzer, "_execute_scopes", lambda *args: ([payload], []))
    report = analyzer.run()
    codes = {item["code"] for item in report["frontier"]}
    assert report["status"] == "partial" and report["verdict"] == "inconclusive"
    assert {"source_unavailable", "finding-budget-exhausted", "output-budget-exhausted"} <= codes
    assert len(report["findings"]) == 1


def test_analyze_project_wrapper_forwards_arguments(tmp_path, monkeypatch):
    captured = {}
    class FakeCoordinator:
        def __init__(self, request_path, output, **options):
            captured.update(request_path=request_path, output=output, **options)
        def run(self):
            return {"status": "complete"}
    monkeypatch.setattr(coordinator, "AnalysisCoordinator", FakeCoordinator)
    result = coordinator.analyze_project("request.json", "out", ir_worker="ir", source_worker="source",
                                         cache_path="cache")
    assert result["status"] == "complete" and captured["ir_worker"] == "ir"
