from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import AnalysisError
from memory_order_analyzer.thread_entry_contracts import (
    diagnostic, expected_thread_entry_protocol, model_profile_digest, semantic_digest,
    thread_entry_document, validate_model_profile, validate_thread_entry_document,
)
from memory_order_analyzer.thread_entry_cache import ThreadEntryCache
from memory_order_analyzer.thread_entry_profiles import (
    adopt_model, broker_for_symbol, c_api_profile, import_cpp_thread_profile,
    load_model_registry, model_profile,
)


A, B = "a" * 64, "b" * 64


def request(**updates):
    fields = {
        "scope_id": "scope", "closed_scope": True,
        "members": [{"physical_tu_id": "tu", "profile_id": A, "language": "c",
                     "standard": "c11", "evidence": []}],
        "global_evidence": [],
        "model_profiles": [c_api_profile("pthread", "x86_64-pc-linux-gnu", "e-p:64:64")],
        "framework_descriptors": [],
        "budgets": deepcopy(expected_thread_entry_protocol()["budgets"]),
        "semantic_digest": None,
    }
    fields.update(updates)
    return thread_entry_document("ThreadEntryDiscoveryRequest", **fields)


def candidate(layer="source", **updates):
    value = {
        "id": A, "layer": layer, "physical_tu_id": "tu", "profile_id": A,
        "api_family": "pthread", "model_id": "model", "callsite_id": B,
        "operation": "create", "callback": {"entry": None, "source_entity_id": "worker", "candidates": ["worker"]},
        "launch_policy": "not-applicable", "guard": None, "evidence": ["e"],
        "status": "candidate", "reason": "needs-ir", "metadata": {},
    }
    value.update(updates)
    return value


def local(**updates):
    fields = {
        "scope_id": "scope", "request_hash": A, "physical_tu_id": "tu", "profile_id": A,
        "language": "c", "standard": "c11", "status": "complete",
        "source_candidates": [candidate()], "ir_candidates": [], "counts": {"source": 1, "ir": 0},
        "dependencies": [], "diagnostics": [], "frontier": [], "semantic_digest": None,
    }
    fields.update(updates)
    return thread_entry_document("ThreadEntryLocalFacts", **fields)


def site(**updates):
    value = {
        "id": A, "physical_tu_id": "tu", "profile_id": A, "api_family": "pthread",
        "model_id": "model", "callsite_id": B, "observations": [A],
        "evidence_status": "source-candidate", "execution_semantics": "creates-thread",
        "root_disposition": "frontier", "callback": {"entry": None, "candidates": ["worker"]},
        "object_lineage": None, "handle_lineage": None, "guard": None, "cardinality": "single",
        "evidence": ["e"], "opposed": [], "reason": "needs-ir",
    }
    value.update(updates)
    return value


def test_protocol_request_and_model_profile_are_strict():
    assert expected_thread_entry_protocol()["kinds"]["ThreadEntryRootOverlay"] == 1
    value = request()
    assert validate_thread_entry_document(value, "ThreadEntryDiscoveryRequest") is value
    profile = value["model_profiles"][0]
    assert validate_model_profile(profile) is profile
    broken = deepcopy(profile); broken["digest"] = B
    with pytest.raises(AnalysisError, match="digest"):
        validate_model_profile(broken)
    broken = deepcopy(profile); broken["unexpected"] = True
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_model_profile(broken)
    unsupported = model_profile(api_family="framework", vendor="demo", version="1", language="c++",
        standards=("c++20",), target="x", data_layout="e-p:64:64", abi="itanium", status="unsupported")
    assert unsupported["digest"] == model_profile_digest(unsupported)


def test_locked_cpp_model_registry_and_corruption(tmp_path):
    profiles = load_model_registry()
    assert {(item["vendor"], item["api_family"]) for item in profiles} == {
        ("libstdc++", "std-jthread"), ("libstdc++", "std-async"),
        ("libc++", "std-jthread"), ("libc++", "std-async"),
    }
    assert all(item["status"] == "verified" and item["brokers"] for item in profiles)
    broken = tmp_path / "registry.json"
    broken.write_text('{"schema_version": 2, "kind": "ThreadEntryModelRegistry", "profiles": []}', encoding="utf-8")
    with pytest.raises(AnalysisError):
        load_model_registry(broken)


def test_profile_helpers_cover_c11_import_adoption_and_brokers():
    c11 = c_api_profile("c11-thread", "x86_64-pc-linux-gnu", "e-p:64:64")
    assert c11["brokers"][0]["callback_index"] == 1
    with pytest.raises(AnalysisError, match="Unsupported"):
        c_api_profile("unknown", "x", "e")

    imported = import_cpp_thread_profile({
        "vendor": "demo", "version": "1", "cxx_standard": "c++20",
        "target": "x86_64-pc-linux-gnu", "data_layout": "e-p:64:64",
        "cxx_abi": "itanium", "header_digests": [{"kind": "header", "id": "thread", "digest": A}],
        "wrapper_signatures": [{"role": "construct-attempt", "symbol": "broker",
                                "digest": B, "parameter_roles": ["state"]}],
    })
    assert imported["canonical_entities"][0]["qualified_name"] == "std::thread"
    member = {"language": "c++", "standard": "c++20"}
    adopted, mismatches = adopt_model(member, imported, target=imported["target"],
                                      data_layout=imported["data_layout"])
    assert adopted == imported and mismatches == [] and adopted is not imported
    rejected, mismatches = adopt_model(
        {"language": "c", "standard": "c11"},
        {**imported, "status": "unsupported",
         "digest": model_profile_digest({**imported, "status": "unsupported"})},
        target="other", data_layout="other")
    assert rejected is None
    assert mismatches == ["data_layout", "language", "standard", "target", "verification_status"]
    assert broker_for_symbol(imported, "broker")["role"] == "construct-attempt"
    assert broker_for_symbol(imported, "missing") is None


def test_registry_rejects_invalid_json_order_and_duplicate_ids(tmp_path):
    invalid = tmp_path / "invalid.json"; invalid.write_text("{", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid"):
        load_model_registry(invalid)
    first = c_api_profile("pthread", "x", "e")
    second = c_api_profile("c11-thread", "x", "e")
    unordered = tmp_path / "unordered.json"
    unordered.write_text(__import__("json").dumps({"schema_version": 1,
        "kind": "ThreadEntryModelRegistry", "profiles": sorted([first, second], key=lambda x: x["id"], reverse=True)}))
    with pytest.raises(AnalysisError, match="sorted"):
        load_model_registry(unordered)
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(__import__("json").dumps({"schema_version": 1,
        "kind": "ThreadEntryModelRegistry", "profiles": [first, first]}))
    with pytest.raises(AnalysisError, match="unique"):
        load_model_registry(duplicate)


def test_request_rejects_future_unknown_duplicate_conflict_and_paths():
    value = request()
    broken = deepcopy(value); broken["schema_version"] = 2
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_thread_entry_document(broken, broken["kind"])
    broken = deepcopy(value); broken["unknown"] = 1; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_thread_entry_document(broken, broken["kind"])
    with pytest.raises(AnalysisError, match="Unknown thread-entry"):
        validate_thread_entry_document(value, "Unknown")
    broken = deepcopy(value); broken["members"].append(deepcopy(broken["members"][0])); broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="unique"):
        validate_thread_entry_document(broken, broken["kind"])
    broken = deepcopy(value); broken["members"][0]["standard"] = "c++20"; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="disagree"):
        validate_thread_entry_document(broken, broken["kind"])


def test_request_budget_duplicate_global_profile_and_protocol_failures(tmp_path):
    value = request()
    broken = deepcopy(value); broken["budgets"]["translation_units"] = 1
    broken["members"].append({**deepcopy(broken["members"][0]), "physical_tu_id": "tu2"})
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="translation unit"):
        validate_thread_entry_document(broken, broken["kind"])
    evidence = {"kind": "ModuleFacts", "id": A, "digest": A, "path": "a.json"}
    broken = deepcopy(value); broken["global_evidence"] = [evidence]
    broken["members"][0]["evidence"] = [evidence]; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="more than once"):
        validate_thread_entry_document(broken, broken["kind"])
    broken = deepcopy(value); broken["budgets"]["profiles"] = 1
    broken["model_profiles"] = sorted([*broken["model_profiles"],
        c_api_profile("c11-thread", "x86_64-pc-linux-gnu", "e-p:64:64")], key=lambda x: x["id"])
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="profile budget"):
        validate_thread_entry_document(broken, broken["kind"])
    protocol = deepcopy(expected_thread_entry_protocol()); protocol["llvm_version"] = "0"
    path = tmp_path / "protocol.json"; path.write_text(__import__("json").dumps(protocol))
    with pytest.raises(AnalysisError, match="disagree"):
        expected_thread_entry_protocol(path)
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        expected_thread_entry_protocol(tmp_path / "missing.json")
    evidence = {"kind": "ModuleFacts", "id": A, "digest": A, "path": "../escape.json"}
    broken = deepcopy(value); broken["members"][0]["evidence"] = [evidence]; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="relative"):
        validate_thread_entry_document(broken, broken["kind"])
    cpp_evidence = {"kind": "CppThreadLocalFacts", "id": A, "digest": A, "path": "cpp.json"}
    broken = deepcopy(value); broken["members"][0]["evidence"] = [cpp_evidence]; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="C members"):
        validate_thread_entry_document(broken, broken["kind"])
    bad_profile = deepcopy(value["model_profiles"][0]); bad_profile["language"] = "c++"
    bad_profile["digest"] = model_profile_digest(bad_profile)
    broken = deepcopy(value); broken["model_profiles"] = [bad_profile]; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="disagree"):
        validate_thread_entry_document(broken, broken["kind"])


def test_local_facts_reject_candidate_shape_sorting_and_language_conflict():
    assert local()["source_candidates"][0]["layer"] == "source"
    broken = deepcopy(local()); broken["source_candidates"][0]["extra"] = 1; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="Candidate fields"):
        validate_thread_entry_document(broken, broken["kind"])
    broken = deepcopy(local()); broken["source_candidates"][0]["evidence"] = ["z", "a"]; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="evidence"):
        validate_thread_entry_document(broken, broken["kind"])
    broken = deepcopy(local()); broken["language"] = "c++"; broken["standard"] = "c11"; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="disagree"):
        validate_thread_entry_document(broken, broken["kind"])
    for field, value, message in (
        ("layer", "ir", "layer"), ("api_family", "bad", "API family"),
        ("status", "bad", "status"),
    ):
        broken = deepcopy(local()); broken["source_candidates"][0][field] = value
        broken["semantic_digest"] = semantic_digest(broken)
        with pytest.raises(AnalysisError, match=message):
            validate_thread_entry_document(broken, broken["kind"])
    broken = deepcopy(local()); broken["source_candidates"][0]["callback"]["candidates"] = ["z", "a"]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="Callback candidates"):
        validate_thread_entry_document(broken, broken["kind"])


def test_site_overlay_report_and_diagnostic_invariants():
    index = thread_entry_document("ThreadEntrySiteIndex", scope_id="scope", request_hash=A,
        status="partial", sites=[site()], counts={}, dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    ref = {"kind": "ThreadEntrySiteIndex", "id": "scope", "digest": "0" * 64}
    overlay = thread_entry_document("ThreadEntryRootOverlay", scope_id="scope", request_hash=A,
        status="partial", site_index=ref, base_execution_roots=None, base_plan=None, roots=[], contexts=[], demands=[],
        reconciliation={}, completeness={}, counts={}, dependencies=[ref], diagnostics=[], frontier=[], semantic_digest=None)
    overlay_ref = {"kind": "ThreadEntryRootOverlay", "id": "scope", "digest": "1" * 64}
    report = thread_entry_document("ThreadEntryDiscoveryReport", scope_id="scope", request_hash=A,
        status="partial", exit_code=2, safety="not_evaluated", findings=None, site_index=ref,
        root_overlay=overlay_ref, language_counts={}, evidence_counts={}, completeness={},
        dependencies=sorted([ref, overlay_ref], key=lambda item: (item["kind"], item["id"])),
        diagnostics=[], frontier=[], cache={"hits": 0, "misses": 1}, semantic_digest=None)
    assert index["sites"] and overlay["roots"] == [] and report["exit_code"] == 2
    adopted = site(evidence_status="dual-exact", root_disposition="adopted",
                   callback={"entry": {"artifact_key": A, "function_id": "worker"}, "candidates": []}, reason=None)
    thread_entry_document("ThreadEntrySiteIndex", scope_id="scope", request_hash=A,
        status="complete", sites=[adopted], counts={}, dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    invalid = deepcopy(index); invalid["sites"][0]["root_disposition"] = "adopted"; invalid["semantic_digest"] = semantic_digest(invalid)
    with pytest.raises(AnalysisError, match="Adopted"):
        validate_thread_entry_document(invalid, invalid["kind"])
    invalid = deepcopy(report); invalid["exit_code"] = 0; invalid["semantic_digest"] = semantic_digest(invalid)
    with pytest.raises(AnalysisError, match="exit code"):
        validate_thread_entry_document(invalid, invalid["kind"])
    invalid = deepcopy(report); invalid["safety"] = "safe"; invalid["semantic_digest"] = semantic_digest(invalid)
    with pytest.raises(AnalysisError):
        validate_thread_entry_document(invalid, invalid["kind"])
    message = diagnostic("x", "中" * 5000, "e" * 5000, limit=128)
    assert len(message["detail"].encode()) <= 128 and len(message["detail_en"].encode()) <= 128
    dangling = deepcopy(overlay); dangling["dependencies"] = []; dangling["semantic_digest"] = semantic_digest(dangling)
    with pytest.raises(AnalysisError, match="missing from dependencies"):
        validate_thread_entry_document(dangling, dangling["kind"])
    replacement = deepcopy(overlay); replacement["site_index"] = {**ref, "id": "other"}
    replacement["semantic_digest"] = semantic_digest(replacement)
    with pytest.raises(AnalysisError, match="missing from dependencies"):
        validate_thread_entry_document(replacement, replacement["kind"])


def test_site_overlay_report_reject_every_cross_field_invariant():
    index = thread_entry_document("ThreadEntrySiteIndex", scope_id="scope", request_hash=A,
        status="partial", sites=[site()], counts={}, dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    mutations = [
        ("api_family", "bad", "API family"), ("evidence_status", "bad", "evidence status"),
        ("execution_semantics", "bad", "semantics"), ("root_disposition", "bad", "disposition"),
    ]
    for field, value, message in mutations:
        broken = deepcopy(index); broken["sites"][0][field] = value; broken["semantic_digest"] = semantic_digest(broken)
        with pytest.raises(AnalysisError, match=message):
            validate_thread_entry_document(broken, broken["kind"])
    for field in ("observations", "evidence", "opposed"):
        broken = deepcopy(index); broken["sites"][0][field] = ["z", "a"]
        broken["semantic_digest"] = semantic_digest(broken)
        with pytest.raises(AnalysisError, match="unique and sorted"):
            validate_thread_entry_document(broken, broken["kind"])
    adopted = deepcopy(index); adopted["sites"][0].update({
        "evidence_status": "source-candidate", "root_disposition": "adopted",
        "execution_semantics": "creates-thread",
        "callback": {"entry": {"artifact_key": A, "function_id": "worker"}, "candidates": []}})
    adopted["semantic_digest"] = semantic_digest(adopted)
    with pytest.raises(AnalysisError, match="exact evidence"):
        validate_thread_entry_document(adopted, adopted["kind"])
    noncreating = deepcopy(index); noncreating["sites"][0]["execution_semantics"] = "does-not-create-thread"
    noncreating["semantic_digest"] = semantic_digest(noncreating)
    with pytest.raises(AnalysisError, match="must be excluded"):
        validate_thread_entry_document(noncreating, noncreating["kind"])


def test_cache_complete_partial_collision_and_escape(tmp_path, monkeypatch):
    cache = ThreadEntryCache(tmp_path)
    complete = thread_entry_document("ThreadEntrySiteIndex", scope_id="scope", request_hash=A,
        status="complete", sites=[], counts={}, dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    partial = thread_entry_document("ThreadEntrySiteIndex", scope_id="scope", request_hash=A,
        status="partial", sites=[], counts={}, dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    assert cache.load("sites", A, "ThreadEntrySiteIndex") is None
    path = cache.publish("sites", A, complete)
    assert cache.publish("sites", A, complete) == path
    assert cache.load("sites", A, "ThreadEntrySiteIndex") == complete
    path.write_text(__import__("json").dumps(partial), encoding="utf-8")
    assert cache.load("sites", A, "ThreadEntrySiteIndex") is None
    invalid = deepcopy(complete); invalid["semantic_digest"] = B
    path.write_text(__import__("json").dumps(invalid), encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid thread-entry cache"):
        cache.load("sites", A, "ThreadEntrySiteIndex")
    path.write_text(__import__("json").dumps(complete), encoding="utf-8")
    changed = deepcopy(complete); changed["counts"] = {"x": 1}; changed["semantic_digest"] = semantic_digest(changed)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("sites", A, changed)
    with pytest.raises(AnalysisError, match="escapes"):
        cache._path("../outside", A)
    fresh = ThreadEntryCache(tmp_path / "race")
    original_link = __import__("os").link
    def racing_link(source, destination):
        original_link(source, destination)
        raise FileExistsError
    monkeypatch.setattr("memory_order_analyzer.thread_entry_cache.os.link", racing_link)
    assert fresh.publish("sites", B, complete).is_file()
