from copy import deepcopy
import json
from pathlib import Path
import pytest
from memory_order_analyzer import pipeline as p
from memory_order_analyzer.contracts import AnalysisError, file_hash
from memory_order_analyzer.execution import OutputStore
from conftest import success
from memory_order_analyzer.protocol import expected_protocol


def test_source_mapping(tmp_path, fixture_module):
    source = tmp_path / "a.c"
    source.write_text("int a;")
    location = {"inline_chain": [{"directory": str(tmp_path), "file": "a.c", "line": 1, "column": 1}]}
    fixture_module["events"] = [{"source": deepcopy(location)}, {"source": deepcopy(location)}]
    assert p.map_sources(fixture_module, {str(source): file_hash(source)})["source_mapping"] == "complete"
    facts = p.map_sources(fixture_module, {str(source): "0" * 64})
    assert facts["source_mapping"] == "partial"
    assert facts["events"][0]["source"]["consistency"] == "source_mismatch"
    assert p.map_sources(fixture_module, {})["events"][0]["source"]["consistency"] == "unverified"
    fixture_module["events"].append({"source": {"inline_chain": []}})
    assert p.map_sources(fixture_module, {str(source): file_hash(source)})["source_mapping"] == "partial"
    fixture_module["events"] = []
    assert p.map_sources(fixture_module, {})["source_mapping"] == "unavailable"


def test_reader_protocol_and_manifest(tmp_path, fixture_module):
    bc = tmp_path / "x.bc"
    for contents in (None, b""):
        if contents is not None:
            bc.write_bytes(contents)
        with pytest.raises(AnalysisError, match="Missing or empty"):
            p.read_facts(bc, "a" * 64, "worker")
    bc.write_bytes(b"test")
    fixture_module["module_hash"] = file_hash(bc)
    runner = lambda argv, *a, **k: success(json.dumps(expected_protocol() if argv[-1] == "--protocol" else fixture_module))
    assert p.read_facts(bc, "a" * 64, "worker", runner=runner)["target"] == fixture_module["target"]
    with pytest.raises(AnalysisError, match="target"):
        p.read_facts(bc, "a" * 64, "worker", expected={"target": "arm"}, runner=runner)
    with pytest.raises(AnalysisError, match="layout"):
        p.read_facts(bc, "a" * 64, "worker", expected={"layout": "bad"}, runner=runner)
    with pytest.raises(AnalysisError, match="requested artifact"):
        p.read_facts(bc, "c" * 64, "worker", runner=runner)
    with pytest.raises(AnalysisError):
        p.read_facts(bc, "a" * 64, "worker", runner=lambda *a, **k: success("not json"))
    for code in ("format_invalid", "reader_failed", "verify_failed", "extraction_budget_exceeded", "unknown"):
        with pytest.raises(AnalysisError) as caught:
            p.read_facts(bc, "a" * 64, "worker", runner=lambda argv, *a, **k: success(json.dumps(expected_protocol())) if argv[-1] == "--protocol" else success(stderr=code + ": bad", code=1))
        assert caught.value.code == (code if code != "unknown" else "nonzero_exit")


def test_import_unknown_and_verified(tmp_path, fixture_module, fixture_artifact, monkeypatch):
    source = tmp_path / "input.bc"
    with pytest.raises(AnalysisError):
        p.import_bc(source, OutputStore(tmp_path / "absent"), "worker")
    source.write_bytes(b"BC\xc0\xdeunit")
    def runner(argv, cwd, **kwargs):
        if argv[-1] == "--protocol":
            return success(json.dumps(expected_protocol()))
        return success(json.dumps({**fixture_module, "artifact_key": argv[2], "module_hash": file_hash(argv[1])}))
    artifact, facts = p.import_bc(source, OutputStore(tmp_path / "unknown"), "worker", runner=runner)
    assert artifact["provenance"] == "unknown" and artifact["context_id"] is None
    fixture_artifact["sha256"] = file_hash(source)
    artifact, _ = p.import_bc(source, OutputStore(tmp_path / "verified"), "worker", manifest=fixture_artifact, runner=runner)
    assert artifact["provenance"] == "verified"
    fixture_artifact["sha256"] = "0" * 64
    with pytest.raises(AnalysisError, match="hash differs"):
        p.import_bc(source, OutputStore(tmp_path / "mismatch"), "worker", manifest=fixture_artifact, runner=runner)
    original_reader = p.read_facts
    def modifying(*args, **kwargs):
        result = original_reader(*args, **kwargs)
        source.write_bytes(b"changed")
        return result
    monkeypatch.setattr(p, "read_facts", modifying)
    with pytest.raises(AnalysisError, match="digest/size mismatch"):
        p.import_bc(source, OutputStore(tmp_path / "changed"), "worker", runner=runner)
