from copy import deepcopy
import json

import pytest

import memory_order_analyzer.unified_plan as plan_module
from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash
from memory_order_analyzer.external_bitcode_contracts import (
    expected_external_bitcode_protocol, external_document,
)
from memory_order_analyzer.unified_contracts import expected_unified_protocol, unified_document
from memory_order_analyzer.unified_plan import (
    build_plan, preflight_bundle, preliminary_tu_modes, stage_registry,
)


PRODUCER = {"family": "clang", "version": "21.1.8", "llvm_version": "21.1.8",
            "host_triple": "x86_64-pc-linux-gnu"}


def request(bundle_hash, **updates):
    fields = {"policy_preset": "bounded-default-v1", "project": {"id": "p", "name": "p"},
              "bundle": {"path": "bundle.json", "sha256": bundle_hash},
              "scope_selection": {"mode": "all", "scope_ids": []}, "source_assistance": "auto",
              "source_requests": [], "explicit_roots": [], "cache": {"mode": "disabled", "resume": False},
              "cancel_file": None, "budgets": expected_unified_protocol()["budgets"]}
    fields.update(updates)
    return unified_document("UnifiedMemoryOrderAnalysisRequest", **fields)


def bundle(tmp_path, *, records=1, closed=True):
    refs = []
    record_ids = []
    for index in range(records):
        identifier = f"tu-{index}"
        value = external_document(
            "ExternalBitcodeArtifactRecord", record_id=identifier,
            physical_tu_id=f"{index + 1:064x}", status="produced", diagnostic=None,
            bitcode={"path": f"bc/{index}.bc", "sha256": f"{index + 8:064x}", "bytes": 8},
            producer=PRODUCER, target={"triple": "x86_64-pc-linux-gnu", "data_layout": "e-p:64:64", "abi": {}},
            language="c" if index % 2 == 0 else "c++", standard="c17" if index % 2 == 0 else "c++20",
            optimization="O0", debug="full", module_kind="translation-unit",
            source={"path": f"src/{index}.c", "sha256": f"{index + 16:064x}"},
            compile_record_digest=f"{index + 24:064x}", input_digests={})
        path = tmp_path / f"record-{index}.json"; path.write_text(canonical(value), encoding="utf-8")
        refs.append({"path": path.name, "sha256": file_hash(path)}); record_ids.append(identifier)
    manifest = external_document(
        "ExternalBitcodeBundleManifest", bundle_id="bundle", producer=PRODUCER,
        records=refs, scopes=[{"target_id": "scope", "record_ids": record_ids,
                              "evidence": "unit", "closed": closed,
                              "external_boundaries": [] if closed else [{"kind": "plugin"}],
                              "target_triple": "x86_64-pc-linux-gnu"}],
        budgets=expected_external_bitcode_protocol()["budgets"])
    path = tmp_path / "bundle.json"; path.write_text(canonical(manifest), encoding="utf-8")
    return path


def test_preflight_selection_modes_and_deterministic_plan(tmp_path):
    path = bundle(tmp_path, records=2)
    value = request(file_hash(path))
    index = preflight_bundle(value, tmp_path)
    assert [item["target_id"] for item in index["scopes"]] == ["scope"]
    plan1 = build_plan(value, index); plan2 = build_plan(value, index)
    assert plan1 == plan2 and len(plan1["stages"]) == len(stage_registry())
    cpp = next(item for item in plan1["stages"] if item["stage"] == "cpp-thread-lifecycle")
    assert cpp["status"] == "planned"
    selected = request(file_hash(path), scope_selection={"mode": "explicit", "scope_ids": ["scope"]})
    assert build_plan(selected, preflight_bundle(selected, tmp_path))["selected_scopes"] == ["scope"]


def test_c_only_skips_cpp_stages_and_open_scope_has_frontier(tmp_path):
    path = bundle(tmp_path, records=1, closed=False)
    value = request(file_hash(path))
    index = preflight_bundle(value, tmp_path)
    plan = build_plan(value, index)
    assert plan["frontier"][0]["code"] == "open_scope"
    assert next(item for item in plan["stages"] if item["stage"] == "cpp-thread-lifecycle")["status"] == "skipped-not-applicable"
    modes = preliminary_tu_modes(value, index, index["scopes"][0])
    assert modes[0]["mode"] == "ir-only"


def test_preflight_rejects_hash_scope_profile_source_and_budgets(tmp_path):
    path = bundle(tmp_path)
    with pytest.raises(AnalysisError, match="digest"):
        preflight_bundle(request("0" * 64), tmp_path)
    with pytest.raises(AnalysisError, match="absent"):
        preflight_bundle(request(file_hash(path), scope_selection={"mode": "explicit", "scope_ids": ["missing"]}), tmp_path)
    limited = request(file_hash(path), budgets={**expected_unified_protocol()["budgets"], "translation_units": 1})
    (tmp_path / "two").mkdir()
    path2 = bundle(tmp_path / "two", records=2)
    limited["bundle"] = {"path": "two/bundle.json", "sha256": file_hash(path2)}
    from memory_order_analyzer.unified_contracts import semantic_digest
    limited["semantic_digest"] = semantic_digest(limited)
    with pytest.raises(AnalysisError, match="translation units"):
        preflight_bundle(limited, tmp_path)


def test_preflight_validates_source_request_reference(tmp_path):
    path = bundle(tmp_path)
    source = tmp_path / "source-request.json"; source.write_text("{}", encoding="utf-8")
    value = request(file_hash(path), source_requests=[{"record_id": "unknown", "path": source.name,
                                                       "sha256": file_hash(source)}])
    with pytest.raises(AnalysisError, match="unknown record"):
        preflight_bundle(value, tmp_path)


def test_preflight_rejects_record_scope_configuration_and_source_hashes(tmp_path, monkeypatch):
    manifest_path = tmp_path / "bundle.json"; manifest_path.write_text("bundle")
    base = external_document(
        "ExternalBitcodeArtifactRecord", record_id="tu", physical_tu_id="a" * 64,
        status="produced", diagnostic=None,
        bitcode={"path": "a.bc", "sha256": "b" * 64, "bytes": 4}, producer=PRODUCER,
        target={"triple": "x86_64-pc-linux-gnu", "data_layout": "e", "abi": {}},
        language="c", standard="c17", optimization="O0", debug="none",
        module_kind="translation-unit", source=None, compile_record_digest="c" * 64,
        input_digests={})
    manifest = {"bundle_id": "bundle", "records": [{"path": "record.json", "sha256": "d" * 64}],
                "scopes": [{"target_id": "scope", "record_ids": ["tu"], "closed": True,
                            "external_boundaries": [], "target_triple": "x86_64-pc-linux-gnu"}]}
    monkeypatch.setattr(plan_module, "read_external_document",
                        lambda path, kind: manifest if kind == "ExternalBitcodeBundleManifest" else base)
    monkeypatch.setattr(plan_module, "_record_reference", lambda *args: base)
    req = request(file_hash(manifest_path)); req["bundle"] = {"path": "bundle.json", "sha256": file_hash(manifest_path)}
    from memory_order_analyzer.unified_contracts import semantic_digest
    req["semantic_digest"] = semantic_digest(req)
    assert preflight_bundle(req, tmp_path)["scopes"][0]["records"][0]["record_id"] == "tu"
    duplicate = {**manifest, "records": manifest["records"] * 2}
    monkeypatch.setattr(plan_module, "read_external_document",
                        lambda path, kind: duplicate if kind == "ExternalBitcodeBundleManifest" else base)
    monkeypatch.setattr(plan_module, "_record_reference", lambda *args: base)
    with pytest.raises(AnalysisError, match="duplicate"):
        preflight_bundle(req, tmp_path)
    for changed, match in (({**base, "target": {**base["target"], "triple": "arm64"}}, "target differs"),
                           ({**base, "target": {**base["target"], "data_layout": "other"}}, None)):
        current = {**manifest, "records": manifest["records"]}
        if match is None:
            current["records"] = [{"path": "one", "sha256": "1" * 64},
                                  {"path": "two", "sha256": "2" * 64}]
            current["scopes"] = [{**manifest["scopes"][0], "record_ids": ["tu", "other"]}]
            other = {**changed, "record_id": "other", "physical_tu_id": "e" * 64}
            values = iter([base, other])
            monkeypatch.setattr(plan_module, "_record_reference", lambda *args: next(values))
            expected = "mixes"
        else:
            monkeypatch.setattr(plan_module, "_record_reference", lambda *args, value=changed: value)
            expected = match
        monkeypatch.setattr(plan_module, "read_external_document",
                            lambda path, kind, value=current: value if kind == "ExternalBitcodeBundleManifest" else base)
        with pytest.raises(AnalysisError, match=expected):
            preflight_bundle(req, tmp_path)
    source = tmp_path / "source.json"; source.write_text("source")
    monkeypatch.setattr(plan_module, "read_external_document",
                        lambda path, kind: manifest if kind == "ExternalBitcodeBundleManifest" else base)
    monkeypatch.setattr(plan_module, "_record_reference", lambda *args: base)
    req_source = {**req, "source_requests": [{"record_id": "tu", "path": "source.json",
                                               "sha256": "0" * 64}]}
    with pytest.raises(AnalysisError, match="Source request digest"):
        preflight_bundle(req_source, tmp_path)
    req_source["source_requests"][0]["sha256"] = file_hash(source)
    assert preflight_bundle(req_source, tmp_path)["source_requests"]["tu"]["resolved_path"] == source
    assert "resolved_path" not in req_source["source_requests"][0]
    limited = deepcopy(req); limited["budgets"] = {**req["budgets"], "scopes": 0}
    with pytest.raises(AnalysisError, match="scope count"):
        preflight_bundle(limited, tmp_path)


def test_record_reference_and_all_mode_budget_edges(tmp_path, monkeypatch):
    record_path = tmp_path / "record.json"; record_path.write_text("record")
    with pytest.raises(AnalysisError, match="record digest"):
        plan_module._record_reference(tmp_path, {"path": "record.json", "sha256": "0" * 64})
    budget_root = tmp_path / "bundle-budget"; budget_root.mkdir()
    path = bundle(budget_root, records=1)
    value = request(file_hash(path))
    index = preflight_bundle(value, path.parent)
    modes = preliminary_tu_modes(value, index, index["scopes"][0])
    assert modes[0]["mode"] == "ir-only"
    index["scopes"][0]["records"][0]["status"] = "failed"
    value["source_assistance"] = "auto"
    index["source_requests"] = {"tu-0": {}}
    assert preliminary_tu_modes(value, index, index["scopes"][0])[0]["mode"] == "ast-only"
    value["source_assistance"] = "disabled"
    assert preliminary_tu_modes(value, index, index["scopes"][0])[0]["mode"] == "failed"
    value["budgets"]["stages"] = 1
    with pytest.raises(AnalysisError, match="Planned stages"):
        build_plan(value, index)


def test_preflight_rejects_windows_msvc_targets(tmp_path):
    path = bundle(tmp_path)
    record_path = tmp_path / "record-0.json"
    record_value = json.loads(record_path.read_text())
    record_value["target"]["triple"] = "x86_64-pc-windows-msvc"
    from memory_order_analyzer.external_bitcode_contracts import semantic_digest as external_semantic_digest
    record_value["semantic_digest"] = external_semantic_digest(record_value)
    record_path.write_text(canonical(record_value), encoding="utf-8")
    manifest = json.loads(path.read_text())
    manifest["records"][0]["sha256"] = file_hash(record_path)
    manifest["scopes"][0]["target_triple"] = "x86_64-pc-windows-msvc"
    manifest["semantic_digest"] = external_semantic_digest(manifest)
    path.write_text(canonical(manifest), encoding="utf-8")
    value = request(file_hash(path))
    with pytest.raises(AnalysisError, match="Windows/MSVC"):
        preflight_bundle(value, tmp_path)
