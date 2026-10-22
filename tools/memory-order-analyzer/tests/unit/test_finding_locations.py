from copy import deepcopy
import json

from memory_order_analyzer.contracts import file_hash
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.finding_locations import (
    assessment_locations, candidate_locations, locations_for_source, source_points,
)
from memory_order_analyzer.finding_projection import project_pipeline_assessment, project_source_candidate
from memory_order_analyzer.finding_contracts import provenance, validate_finding
from memory_order_analyzer.source_context import snapshot_source
from memory_order_analyzer.unified_coordinator import AnalysisCoordinator


def fixture_data(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    out = tmp_path / "out"
    store = OutputStore(out)
    snapshots = {}
    for name, text in (("main.c", "main\nbody\nend\n"), ("shared.h", "header\natomic\nend\n")):
        path = root / name
        path.write_text(text)
        snapshots[name] = snapshot_source(store, root, name, file_hash(path))
    record = {"record_id": "r", "physical_tu_id": "tu"}
    request = {"budgets": {"context_lines": 256, "context_characters": 65536}}
    return record, snapshots, out, request


def test_header_macro_and_end_exclusive(tmp_path):
    record, snapshots, out, request = fixture_data(tmp_path)
    source = {"expansion": {"file": "main.c", "line": 2, "column": 1},
              "spelling": {"file": "shared.h", "line": 2, "column": 1},
              "spelling_end": {"file": "shared.h", "line": 3, "column": 1}}
    values = locations_for_source(source, record, snapshots, out, request)
    assert [item["location"]["file"] for item in values] == ["main.c", "shared.h"]
    context = values[1]["location"]["context"]
    assert context["status"] == "complete"
    assert context["highlights"] == [{"line": 2, "startColumn": 1, "endColumn": 7}]
    assert context["lines"][1]["text"] == "atomic"
    source["spelling_end"]["file"] = "main.c"
    other = locations_for_source(source, record, snapshots, out, request)[1]["location"]
    assert other["span"]["end"] == {"line": 2, "column": 2}
    source["spelling_end"] = dict(source["spelling"])
    point = locations_for_source(source, record, snapshots, out, request)[1]["location"]
    assert point["span"]["end"] == {"line": 2, "column": 2}
    assert point["context"]["status"] == "complete"


def test_unavailable_coordinates_and_snapshots(tmp_path):
    record, snapshots, out, request = fixture_data(tmp_path)
    assert source_points(None) == []
    assert source_points({}) == []
    for point in ({"line": 1, "column": 1}, {"file": "external.h", "line": 1, "column": 1},
                  {"file": "main.c", "line": 0, "column": 1},
                  {"file": "main.c", "line": 1, "column": 0}):
        assert locations_for_source(point, record, snapshots, out, request) == []
    for end in ({"line": 0, "column": 1}, {"line": 1, "column": None}):
        assert locations_for_source({"location": {"file": "main.c", "line": 1, "column": 1},
                                     "location_end": end}, record, snapshots, out, request) == []
    point = {"file": "main.c", "line": 1, "column": 1}
    (out / snapshots["main.c"]["path"]).write_text("changed")
    assert locations_for_source(point, record, snapshots, out, request)[0]["location"]["context"]["status"] == "unavailable"
    unsafe = deepcopy(snapshots["shared.h"])
    unsafe["sourcePath"] = "../escape"
    assert locations_for_source({**point, "file": "../escape"}, record, {"bad": unsafe}, out, request) == []


def test_candidates_keep_scope_and_locations(tmp_path):
    record, snapshots, out, request = fixture_data(tmp_path)
    scope = {"records": [record, {"record_id": "other", "physical_tu_id": "other"}]}
    facts = {"r": {"nodes": [{"id": "n", "source": {"file": "shared.h", "line": 2, "column": 1}},
                               {"id": "ignored", "source": {}}]}}
    candidate = {"id": "candidate", "physical_tu_ids": ["tu"], "node_ids": ["n"]}
    values = candidate_locations(candidate, facts, scope, snapshots, out, request)
    assert len(values) == 1 and values[0]["location"]["file"] == "shared.h"
    assert candidate_locations({}, facts, scope, snapshots, out, request) == []
    prov = [provenance("Fact", "n", "org.rvport.memory-order-analyzer.test", 1, "a" * 64)]
    result = project_source_candidate("scope", candidate, prov, locations=values)
    validate_finding(result)
    assert result["conclusion"]["verdict"] == "source-candidate"
    assert result["fact"]["primaryLocation"]["context"]["lines"][1]["text"] == "atomic"


def test_root_normalization_and_snapshot_gap(tmp_path):
    record, snapshots, out, request = fixture_data(tmp_path)
    root = tmp_path / "source"
    point = {"file": str(root / "shared.h"), "line": 2, "column": 1}
    absolute = locations_for_source(point, record, snapshots, out, request, root)
    assert absolute[0]["location"]["file"] == "shared.h"
    assert locations_for_source({**point, "file": "shared.h", "directory": str(root)},
                                record, snapshots, out, request, root) == absolute
    assert locations_for_source({**point, "file": "shared.h"}, record, snapshots, out, request, root) == absolute
    assert locations_for_source({**point, "file": "/etc/passwd"}, record, snapshots, out, request, root) == []
    assert locations_for_source({**point, "file": "../outside.h"}, record, snapshots, out, request, root) == []
    mapped_record = {**record, "source_path_map": [{"from": "/remote", "to": "."},
                                                 {"from": "/other", "to": "."},
                                                 {"from": "/ignored", "to": "unsupported"}]}
    remote = {"file": "shared.h", "directory": "/remote", "line": 2, "column": 1}
    assert locations_for_source(remote, mapped_record, snapshots, out, request, root) == absolute
    assert locations_for_source({**remote, "directory": "/remote-evil"}, mapped_record, snapshots, out, request, root) == []
    assert locations_for_source({**remote, "directory": "/remote", "file": "../escape"}, mapped_record, snapshots, out, request, root) == []
    (out / snapshots["shared.h"]["path"]).write_text("changed")
    values = locations_for_source(point, record, snapshots, out, request, root)
    layers = {name: {} for name in ("root", "thread_instance", "mhp", "access", "object", "synchronization")}
    prov = [provenance("Fact", "n", "org.rvport.memory-order-analyzer.test", 1, "a" * 64)]
    result = project_pipeline_assessment("scope", {"id": "a"}, prov, category="discharged", layers=layers, locations=values)
    assert result["evidenceChain"]["status"] == "partial"
    assert result["fact"]["primaryLocation"]["context"]["status"] == "unavailable"


def test_formal_references_and_a6_protocol(tmp_path):
    record, snapshots, out, request = fixture_data(tmp_path)
    scope = {"target_id": "scope", "records": [record]}
    mappings = {"r": {"artifact_key": "key"}}
    facts = out / "facts"
    facts.mkdir()
    (facts / "key.json").write_text(json.dumps({"events": [
        {"id": "read", "source": {"inline_chain": [{"file": "shared.h", "line": 2, "column": 1}]}},
        {"id": "write", "source": {"inline_chain": [{"file": "main.c", "line": 2, "column": 1}]}},
        {"id": "unrelated", "source": {}}]}))
    assessment = {"id": "a", "evidence": [{"artifact_key": "key", "id": "read"},
                                             {"artifact_key": "key", "id": "write"}, "ignored"]}
    reader = lambda path: json.loads(path.read_text())
    values = assessment_locations(assessment, scope, mappings, out, snapshots, out, request, reader)
    assert len(values) == 2
    layers = {name: {} for name in ("root", "thread_instance", "mhp", "access", "object", "synchronization")}
    prov = [provenance("Fact", "n", "org.rvport.memory-order-analyzer.test", 1, "a" * 64)]
    for category in ("formal", "discharged"):
        result = project_pipeline_assessment("scope", assessment, prov, category=category, layers=layers, locations=values)
        validate_finding(result)
        assert len(result["occurrences"]) == 2
        assert result["fact"]["primaryLocation"] is not None
        assert all(step["source"] is None for step in result["evidenceChain"]["steps"] if step["kind"] == "execution-root")
    directory = out / "analysis/scope/publication/graphs"
    directory.mkdir(parents=True)
    (directory / "graph.json").write_text(json.dumps({"assessments": [
        {**assessment, "protocol_id": "protocol"}, {"protocol_id": "other"}]}))
    assert assessment_locations({"p4_protocol_id": "protocol"}, scope, mappings, out, snapshots, out, request, reader) == values
    assert assessment_locations(assessment, scope, {}, out, snapshots, out, request, reader) == []
    (facts / "key.json").unlink()
    assert assessment_locations(assessment, scope, mappings, out, snapshots, out, request, reader) == []


def test_header_snapshot_before_analysis_and_missing_formal_location(tmp_path):
    record, snapshots, out, request = fixture_data(tmp_path)
    root = tmp_path / "source"
    (root / "large.h").write_bytes(b" " * (8 * 1024 * 1024 + 1))
    (root / "escape.h").symlink_to("/etc/passwd")
    analyzer = AnalysisCoordinator(tmp_path / "request.json", tmp_path / "result")
    captured, failures = analyzer._snapshot_sources({"manifest_path": root / "bundle.json", "records": {}}, OutputStore(tmp_path / "snapshots"))
    assert captured["header:shared.h"]["digest"] == file_hash(root / "shared.h")
    assert failures["header:large.h"].code == "snapshot_budget"
    assert failures["header:escape.h"].code == "path_unsafe"
    layers = {name: {} for name in ("root", "thread_instance", "mhp", "access", "object", "synchronization")}
    prov = [provenance("Fact", "n", "org.rvport.memory-order-analyzer.test", 1, "a" * 64)]
    value = project_pipeline_assessment("scope", {"id": "a"}, prov, category="formal", layers=layers, locations=[])
    assert value["conclusion"]["verdict"] == "risk"
    assert value["evidenceChain"]["status"] == "partial"
    assert "source-location-unavailable" in value["evidenceChain"]["reasonCodes"]


def test_declared_original_source_root_is_snapshotted(tmp_path, monkeypatch):
    import memory_order_analyzer.unified_coordinator as coordinator
    record, snapshots, out, request = fixture_data(tmp_path)
    root = tmp_path / "source"
    profile = {"source": {"path": str(root / "main.c")},
               "path_map": [{"from": str(root), "to": "."}, {"from": "/missing-remote", "to": "."}]}
    monkeypatch.setattr(coordinator, "_source_request", lambda path: {"profile": profile})
    bundle = {"manifest_path": tmp_path / "external/bundle.json",
              "source_requests": {"r": {"resolved_path": tmp_path / "profile.json"}},
              "records": {"r": {**record, "source": {"path": "source/renamed.c", "sha256": file_hash(root / "main.c")}}}}
    analyzer = AnalysisCoordinator(tmp_path / "request.json", tmp_path / "result")
    captured, failures = analyzer._snapshot_sources(bundle, OutputStore(tmp_path / "captured"))
    assert failures == {}
    assert captured["r"]["sourcePath"] == "main.c"
    assert captured["header:shared.h"]["sourcePath"] == "shared.h"
    profile["source"]["path"] = str(tmp_path / "outside.c")
    captured, failures = analyzer._snapshot_sources(bundle, OutputStore(tmp_path / "unmapped"))
    assert "r" in failures and captured == {}
