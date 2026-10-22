from copy import deepcopy
import json

import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash, identity
from memory_order_analyzer.effect_inputs import EffectInputs
from test_effect_references import references
from test_semantic import graph
from test_scope_report import scope


@pytest.fixture
def inputs(references, tmp_path):
    value, artifacts, modules = references
    key = next(iter(modules))
    path = tmp_path / "input.bc"
    path.write_bytes(b"BC-unit-hash-boundary")
    artifacts[key]["path"] = str(path)
    artifacts[key]["sha256"] = modules[key]["module_hash"] = file_hash(path)
    value["origins"][0].update(module_hash=file_hash(path), facts_hash=identity(modules[key]))
    value["resolutions"][0]["facts_hash"] = identity(modules[key])
    snapshot = EffectInputs(scope([key]), artifacts, modules)
    value["scope_id"] = snapshot.scope_id
    return snapshot, value


def test_memory_and_file_consumption_preserve_inputs(inputs, tmp_path):
    snapshot, value = inputs
    before = deepcopy(value)
    assert snapshot.consume(value) == before and value == before
    path = tmp_path / "summary.json"
    path.write_text(canonical(value))
    assert snapshot.consume_file(path, "EffectSummary") == value
    dep = deepcopy(value)
    dep["context_id"] = dep["invocations"][0]["context_id"] = "dep"
    dep["effects"][0]["context_id"] = dep["resolutions"][0]["context_id"] = "dep"
    value["dependencies"] = [{"context_id": "dep", "digest": identity(dep)}]
    assert snapshot.consume(value, summaries={"dep": dep}) == value
    for patch in [{"scope_id": "e" * 64}, {"budgets": {**dep["budgets"], "local_steps": 1}}]:
        bad = {**dep, **patch}
        caller = {**value, "dependencies": [{"context_id": "dep", "digest": identity(bad)}]}
        with pytest.raises(AnalysisError):
            snapshot.consume(caller, summaries={"dep": bad})
    with pytest.raises(AnalysisError, match="map key"):
        snapshot.consume(value, summaries={"wrong": dep})
    bad = deepcopy(dep)
    bad["effects"][0]["source"]["id"] = "absent"
    caller = {**value, "dependencies": [{"context_id": "dep", "digest": identity(bad)}]}
    with pytest.raises(AnalysisError, match="Dangling"):
        snapshot.consume(caller, summaries={"dep": bad})


def test_manifest_loading_and_snapshots(inputs, tmp_path):
    snapshot, value = inputs
    scope_path = tmp_path / "scope.json"
    scope_path.write_text(canonical(snapshot.scope))
    for category, entries in [("artifacts", snapshot.artifacts), ("facts", snapshot.modules)]:
        (tmp_path / category).mkdir()
        for key, entry in entries.items():
            (tmp_path / category / f"{key}.json").write_text(canonical(entry))
    loaded = EffectInputs.load(scope_path, tmp_path)
    assert loaded.consume(value) == value
    assert len(loaded.files) == 4
    scope_path.write_text(canonical({**snapshot.scope, "closed": False}))
    with pytest.raises(AnalysisError, match="Input changed"):
        loaded.consume(value)
    # Data passed by the caller is copied, not aliased into the snapshot.
    original = deepcopy(snapshot.scope)
    other = EffectInputs(original, snapshot.artifacts, snapshot.modules)
    original["closed"] = False
    assert other.scope["closed"]


def test_reject_missing_changed_and_foreign_inputs(inputs):
    snapshot, value = inputs
    with pytest.raises(AnalysisError, match="exactly"):
        EffectInputs(snapshot.scope, {}, snapshot.modules)
    key = next(iter(snapshot.artifacts))
    other_key = "e" * 64
    artifacts = {**snapshot.artifacts, other_key: {**snapshot.artifacts[key], "artifact_key": other_key, "profile": "imported"}}
    modules = {**snapshot.modules, other_key: {**snapshot.modules[key], "artifact_key": other_key}}
    with pytest.raises(AnalysisError, match="Mixed"):
        EffectInputs(scope([key, other_key]), artifacts, modules)
    artifacts[other_key].update(profile=artifacts[key]["profile"], sha256="f" * 64)
    modules[other_key]["module_hash"] = "f" * 64
    with pytest.raises(AnalysisError, match="same BC path"):
        EffectInputs(scope([key, other_key]), artifacts, modules)
    with pytest.raises(AnalysisError, match="Foreign analysis scope"):
        snapshot.consume({**value, "scope_id": "e" * 64})
    with pytest.raises(AnalysisError):
        snapshot.consume(None)
    path = next(iter(snapshot.files))
    from pathlib import Path
    Path(path).write_bytes(b"changed")
    with pytest.raises(AnalysisError, match="Input changed"):
        snapshot.consume(value)
    Path(path).unlink()
    with pytest.raises(AnalysisError, match="unavailable"):
        snapshot.recheck()


def test_load_races_and_derived_file_race(inputs, tmp_path, monkeypatch):
    snapshot, value = inputs
    import memory_order_analyzer.effect_inputs as module
    path = tmp_path / "derived.json"
    path.write_text(canonical(value))
    original = snapshot.consume
    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        path.write_text("{}")
        return result
    monkeypatch.setattr(snapshot, "consume", changing)
    with pytest.raises(AnalysisError, match="Derived input changed"):
        snapshot.consume_file(path, "EffectSummary")
    scope_path = tmp_path / "scope.json"
    scope_path.write_text(canonical(snapshot.scope))
    for category, entries in [("artifacts", snapshot.artifacts), ("facts", snapshot.modules)]:
        (tmp_path / category).mkdir()
        for key, entry in entries.items():
            (tmp_path / category / f"{key}.json").write_text(canonical(entry))
    read = module.read_document
    count = 0
    def racing(source, kind):
        nonlocal count
        result = read(source, kind)
        if kind == "ScopeManifest":
            count += 1
            if count > 1:
                result["closed"] = False
        return result
    monkeypatch.setattr(module, "read_document", racing)
    with pytest.raises(AnalysisError, match="Scope changed"):
        EffectInputs.load(scope_path, tmp_path)
