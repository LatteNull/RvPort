import io
import json
from copy import deepcopy

import pytest

from memory_order_analyzer import cli
from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.cpp_raii_analysis import (
    _state_transition, build_local_facts, build_synchronization_graph,
    build_synchronization_report, failed_synchronization_report,
    module_synchronization_calls, trace_mutex_provenance,
)
from memory_order_analyzer.cpp_raii_cache import CppRaiiCache, cache_key
from memory_order_analyzer.cpp_raii_contracts import (
    cpp_raii_document, dependency, diagnostic, expected_cpp_raii_protocol,
    semantic_digest, synchronization_profile_id, validate_cpp_raii_document,
)
from memory_order_analyzer.cpp_raii_profiles import (
    adopt_synchronization_profile, build_synchronization_profile,
    normalize_synchronization_calls,
)
from memory_order_analyzer.cpp_raii_validation import compare_synchronization_truth
from memory_order_analyzer.model_cpp_raii_synchronization import model_cpp_raii_synchronization
from memory_order_analyzer.source_contracts import counts, source_document


def profile(vendor="libstdc++", standard="c++17", *, status="verified"):
    macro = {"__GLIBCXX__": "20230818"} if vendor == "libstdc++" else {"_LIBCPP_VERSION": "210000"}
    return build_synchronization_profile(
        {"language": "c++", "standard": standard, "target": "x86_64-pc-linux-gnu"},
        {"macros": macro, "data_layout": "e-p:64:64", "pointer_width": 64,
         "toolchain_lineage": "locked-dev-image", "cxx_abi": "itanium",
         "exceptions": True, "rtti": True, "headers": [], "status": status,
         "wrappers": [
             {"role": "mutex-lock", "symbol": f"{vendor}-lock", "parameter_roles": ["mutex"],
              "calling_convention": "ccc", "exception_behavior": "may-throw", "layout": "v1"},
             {"role": "mutex-unlock", "symbol": f"{vendor}-unlock", "parameter_roles": ["mutex"],
              "calling_convention": "ccc", "exception_behavior": "nothrow", "layout": "v1"},
         ], "provenance": ["compile-only", "unit-test"]}, status=status,
    )


def member(tu="tu", standard="c++17", language="c++"):
    return {"physical_tu_id": tu, "profile_id": "a" * 64, "language": language,
            "standard": standard, "source_facts": None, "ir_facts": None}


def request(value=None, members=None, **budget_overrides):
    members = members or [member()]
    profiles = [] if value is None else [dependency("CppRaiiSynchronizationProfile", value["profile_id"], value)]
    budgets = dict(expected_cpp_raii_protocol()["budgets"])
    budgets.update(budget_overrides)
    return cpp_raii_document(
        "CppRaiiSynchronizationRequest", scope_id="scope", roots=["main"], members=members,
        dependencies=[], synchronization_profiles=profiles, budgets=budgets, semantic_digest=None)


def relation(index, kind, from_, to=None, *, file="a.cpp", status="candidate", reason=None):
    return {"id": f"r{index}:{kind}", "kind": kind, "from": from_, "to": to,
            "source": {"expansion": {"file": file, "line": index, "column": 1}},
            "status": status, "reason": reason}


def source(tu, file, owner, mutex="shared-mutex"):
    return {"physical_tu_id": tu, "profile_id": "a" * 64, "status": "complete", "nodes": [],
            "relations": [
                relation(1, "cpp-raii-mutex-object", mutex, mutex, file=file,
                         reason="plain-mutex-requires-profile-and-ir-binding"),
                relation(2, "cpp-raii-owner-object", f"init-{owner}", owner, file=file,
                         reason="lock-guard-requires-profile-cfg-and-ir-binding"),
                relation(2, "cpp-raii-owner-construct", f"init-{owner}", owner, file=file,
                         reason="lock-guard-requires-profile-cfg-and-ir-binding"),
                relation(2, "cpp-raii-mutex-argument", f"init-{owner}", mutex, file=file),
                relation(3, "cpp-raii-owner-destruct", owner, owner, file=file,
                         reason="implicit-cleanup-lock-guard"),
            ]}


def module(value, file, prefix):
    signatures = {item["role"]: item for item in value["wrapper_signatures"]}
    calls = []
    for line, role in ((2, "mutex-lock"), (3, "mutex-unlock")):
        item = signatures[role]
        calls.append({"id": f"{prefix}-{role}", "kind": "direct", "target": item["symbol"],
                      "calling_convention": "ccc", "arguments": ["mutex-root"],
                      "source": {"inline_chain": [{"file": file, "line": line, "column": 1}]}})
    return {"target": value["target"], "layout": value["data_layout"], "values": [], "calls": calls}


def test_protocol_profiles_requests_and_diagnostics_are_strict():
    value = profile()
    assert value["profile_id"] == synchronization_profile_id(value)
    assert validate_cpp_raii_document(request(value), "CppRaiiSynchronizationRequest")
    assert expected_cpp_raii_protocol()["kinds"]["CppRaiiSynchronizationGraph"] == 1
    item = diagnostic("code", "中文" * 100, "English" * 100, suggestion="建议",
                      suggestion_en="Suggestion", limit=48)
    assert len(item["detail"].encode()) <= 48 and len(item["detail_en"].encode()) <= 48
    broken = deepcopy(value); broken["extra"] = True
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_cpp_raii_document(broken, broken["kind"])
    broken = deepcopy(value); broken["version"] = "drift"; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="identity"):
        validate_cpp_raii_document(broken, broken["kind"])
    with pytest.raises(AnalysisError, match=r"C\+\+17"):
        build_synchronization_profile({"language": "c", "standard": "c17", "target": "x"}, {})


def test_request_and_reference_boundaries_reject_mixed_or_dangling_values():
    value = profile()
    missing = request(value)
    missing["synchronization_profiles"] = []
    missing["semantic_digest"] = semantic_digest(missing)
    with pytest.raises(AnalysisError, match="explicit"):
        validate_cpp_raii_document(missing, missing["kind"])
    mixed = request(value)
    mixed["members"][0].update(language="c", standard="c++17")
    mixed["semantic_digest"] = semantic_digest(mixed)
    with pytest.raises(AnalysisError, match="disagree"):
        validate_cpp_raii_document(mixed, mixed["kind"])
    duplicate = request(value)
    duplicate["members"] *= 2
    duplicate["semantic_digest"] = semantic_digest(duplicate)
    with pytest.raises(AnalysisError, match="unique"):
        validate_cpp_raii_document(duplicate, duplicate["kind"])
    future = deepcopy(value); future["schema_version"] = 2
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_cpp_raii_document(future, future["kind"])


def test_profile_adoption_wrapper_normalization_and_provenance_limits():
    value = profile()
    adopted, gap = adopt_synchronization_profile(value, deepcopy(value))
    assert adopted == value and gap is None
    drift = profile("libc++")
    assert adopt_synchronization_profile(value, drift)[0] is None
    signature = value["wrapper_signatures"][0]
    calls = [{"id": "call", "symbol": signature["symbol"], "calling_convention": "ccc",
              "signature_digest": signature["digest"], "evidence": ["ir"]}]
    normalized, gaps = normalize_synchronization_calls(calls, value)
    assert normalized[0]["role"] == signature["role"] and not gaps
    calls[0]["signature_digest"] = "0" * 64
    assert normalize_synchronization_calls(calls, value)[1][0]["code"] == "abi-wrapper-mismatch"
    values = [{"id": "load", "opcode": "load", "operands": ["slot"]},
              {"id": "slot", "opcode": "alloca", "operands": []}]
    assert trace_mutex_provenance(["load"], values)["roots"] == ["slot"]
    assert trace_mutex_provenance(["load"], values, limit=1)["status"] != "exact"
    assert trace_mutex_provenance(["bad"], [{"id": "bad", "opcode": "call"}])["status"] == "unresolved"
    with pytest.raises(AnalysisError, match="Exactly one"):
        build_synchronization_profile(
            {"language": "c++", "standard": "c++17", "target": "x"},
            {"macros": {}, "wrappers": []})
    with pytest.raises(AnalysisError, match="Unsupported"):
        build_synchronization_profile(
            {"language": "c++", "standard": "c++17", "target": "x"},
            {"macros": {"__GLIBCXX__": 1}, "wrappers": [{"role": "alien"}]})
    with pytest.raises(AnalysisError, match="lock and unlock"):
        build_synchronization_profile(
            {"language": "c++", "standard": "c++17", "target": "x"},
            {"macros": {"__GLIBCXX__": 1}, "wrappers": []})


def test_cpp_local_state_machine_regions_and_cross_thread_proofs():
    value = profile()
    modules = {"a": module(value, "a.cpp", "a"), "b": module(value, "b.cpp", "b")}
    first = build_local_facts("scope", member("a"), source("a", "a.cpp", "guard-a"), value,
                              modules=modules)
    second = build_local_facts("scope", member("b"), source("b", "b.cpp", "guard-b"), value,
                               modules=modules)
    assert first["status"] == second["status"] == "complete"
    for facts, thread in ((first, "thread-a"), (second, "thread-b")):
        for operation in facts["operations"]:
            operation["thread_id"] = thread
        facts["accesses"] = [{
            "id": f"access-{thread}", "object_id": "shared-payload",
            "access_kind": "write" if thread == "thread-a" else "read",
            "owner_id": facts["owners"][0]["id"], "thread_id": thread,
            "evidence": [f"ir-{thread}"],
        }]
        facts["semantic_digest"] = semantic_digest(facts)
    thread_graph = {
        "scope_id": "threads", "instances": [],
        "mhp": [{"id": "mhp-a-b", "left": "thread-a", "right": "thread-b",
                 "relation": "may_parallel", "proof": []}],
    }
    no_mhp = build_synchronization_graph(request(value, [member("a"), member("b")]),
                                         [first, second], [value])
    assert not no_mhp["proofs"] and no_mhp["status"] == "partial"
    graph = build_synchronization_graph(request(value, [member("a"), member("b")]),
                                        [first, second], [value], thread_graph=thread_graph)
    assert graph["status"] == "complete"
    assert len(graph["held_regions"]) == 2
    assert {item["proof_kind"] for item in graph["proofs"]} == {
        "mutual-exclusion", "mutex-sync-candidate"}
    report = build_synchronization_report(request(value, [member("a"), member("b")]), graph,
                                          [value], hits=1, misses=2)
    assert report["exit_code"] == 0 and report["safety"] == "not_established"

    read_only = deepcopy(second)
    read_only["accesses"][0]["access_kind"] = "read"
    first_read = deepcopy(first)
    first_read["accesses"][0]["access_kind"] = "read"
    read_graph = build_synchronization_graph(request(value, [member("a"), member("b")]),
                                             [first_read, read_only], [value],
                                             thread_graph=thread_graph)
    assert not read_graph["proofs"]


def test_unknown_state_budget_ast_only_and_c_path_stay_conservative():
    value = profile()
    local = build_local_facts("scope", member(), source("tu", "a.cpp", "guard"), value, modules={})
    assert local["status"] == "partial" and local["frontier"]
    graph = build_synchronization_graph(request(value, transitions=1), [local], [value])
    assert graph["status"] == "partial" and not graph["proofs"]
    assert any(item["code"] == "transitions-budget-exhausted" for item in graph["frontier"])
    assert _state_transition("uninitialized", {"operation": "construct", "guard": "defer_lock"},
                             "unique-lock") == "deferred"
    assert _state_transition("owns", {"operation": "unlock", "guard": None}, "unique-lock") == "released"
    c_member = member("c", "c17", "c")
    c_source = {"physical_tu_id": "c", "status": "complete", "relations": [], "nodes": []}
    c_module = {"target": "x", "layout": "y", "values": [], "calls": [
        {"id": "l", "kind": "direct", "target": "pthread_mutex_lock", "arguments": ["m"]},
        {"id": "u", "kind": "direct", "target": "pthread_mutex_unlock", "arguments": ["m"]},
    ]}
    c_local = build_local_facts("scope", c_member, c_source, modules={"c": c_module})
    assert c_local["synchronization_profile_id"] is None and not any(
        item["owner_kind"] != "pthread-direct" for item in c_local["owners"])
    assert _state_transition("owns", {"operation": "move", "guard": None}, "unique-lock") == "owns"
    assert _state_transition("unknown", {"operation": "owns-lock", "guard": None}, "unique-lock") == "unknown"
    assert _state_transition("released", {"operation": "destruct", "guard": None}, "lock-guard") == "released"


def test_cache_isolated_deterministic_and_rejects_corruption(tmp_path, monkeypatch):
    cache = CppRaiiCache(tmp_path)
    report = failed_synchronization_report("x", "失败", "failed")
    with pytest.raises(AnalysisError, match="not cacheable"):
        cache.publish("reports", cache_key("report", {}), report)
    value = profile()
    key = cache_key("profiles", {"profile": value["profile_id"]})
    path = cache.publish("profiles", key, value)
    assert cache.load("profiles", key, value["kind"]) == value
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid A4 cache"):
        cache.load("profiles", key, value["kind"])
    assert "cpp-raii-synchronization-v1" in str(path)
    assert cache.load("missing", "0" * 64, value["kind"]) is None
    with pytest.raises(AnalysisError, match="escapes"):
        cache._path("../../outside", "key")
    good_key = cache_key("profiles", {"other": True})
    cache.publish("profiles", good_key, value)
    other = profile("libc++")
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("profiles", good_key, other)
    with pytest.raises(AnalysisError, match="must be documents"):
        cache.publish("profiles", "bad", [])
    with pytest.raises(AnalysisError, match="Transient"):
        cache.publish("profiles", "bad", value, stability="wall-clock")
    with pytest.raises(AnalysisError, match="stale"):
        cache.load("profiles", good_key, value["kind"], dependencies=[])
    same = cache.publish("profiles", good_key, value)
    assert same.exists()
    malformed_key = cache_key("profiles", {"malformed": True})
    malformed = cache._path("profiles", malformed_key)
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid A4 cache"):
        cache.load("profiles", malformed_key, value["kind"])
    race_key = cache_key("profiles", {"race": True})
    real_link = __import__("os").link
    def raced_link(source_path, target_path):
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        raise FileExistsError
    monkeypatch.setattr("memory_order_analyzer.cpp_raii_cache.os.link", raced_link)
    assert cache.publish("profiles", race_key, value).is_file()
    monkeypatch.setattr("memory_order_analyzer.cpp_raii_cache.os.link", real_link)


def validation_case(case_id, language, standard, vendor):
    return {"id": case_id, "language": language, "standard": standard, "vendor": vendor,
            "eligible": True}


def test_truth_comparison_preserves_four_denominators_and_vendor_boundaries():
    cases = [validation_case("c11", "c", "c11", None),
             validation_case("c17", "c", "c17", None),
             validation_case("cpp17", "c++", "c++17", "libstdc++"),
             validation_case("cpp20", "c++", "c++20", "libc++")]
    suite = cpp_raii_document("CppRaiiValidationSuite", suite_version="v1", cases=cases,
                              semantic_digest=None)
    truth = cpp_raii_document(
        "CppRaiiValidationTruth", suite_version="v1",
        cases=[{"case_id": item["id"], "mutexes": [], "owners": [], "regions": [],
                "proofs": [], "unknown": ["missing-result"]} for item in cases], semantic_digest=None)
    report = compare_synchronization_truth(suite, truth, {})
    assert report["metrics"]["exact"] == 4
    assert all(value["planned"] == 1 for value in report["languages"].values())
    broken = deepcopy(suite); broken["cases"][-1]["vendor"] = "libstdc++"
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match=r"libc\+\+"):
        validate_cpp_raii_document(broken, broken["kind"])
    other_version = deepcopy(truth); other_version["suite_version"] = "v2"
    other_version["semantic_digest"] = semantic_digest(other_version)
    with pytest.raises(ValueError, match="versions"):
        compare_synchronization_truth(suite, other_version, {})
    reduced = deepcopy(truth); reduced["cases"][-1]["case_id"] = "different"
    reduced["cases"].sort(key=lambda item: item["case_id"])
    reduced["semantic_digest"] = semantic_digest(reduced)
    with pytest.raises(ValueError, match="denominator"):
        compare_synchronization_truth(suite, reduced, {})
    mismatch_truth = deepcopy(truth)
    mismatch_truth["cases"][0]["mutexes"] = ["expected"]
    mismatch_truth["semantic_digest"] = semantic_digest(mismatch_truth)
    mismatch = compare_synchronization_truth(suite, mismatch_truth, {})
    assert mismatch["status"] == "partial" and mismatch["diagnostics"][0]["code"] == "truth-mismatch"
    complete_cases = deepcopy(cases)
    complete_cases[0]["eligible"] = False
    complete_suite = cpp_raii_document("CppRaiiValidationSuite", suite_version="v2",
                                       cases=complete_cases, semantic_digest=None)
    complete_truth = cpp_raii_document(
        "CppRaiiValidationTruth", suite_version="v2",
        cases=[{"case_id": item["id"], "mutexes": [item["id"]], "owners": [],
                "regions": [], "proofs": [], "unknown": []} for item in complete_cases],
        semantic_digest=None)
    actuals = {item["id"]: {"status": "complete", "mutexes": [{"object_id": item["id"]}],
                             "owners": [], "held_regions": [], "proofs": [], "gaps": [], "frontier": []}
               for item in complete_cases}
    complete = compare_synchronization_truth(complete_suite, complete_truth, actuals, [profile()])
    assert complete["status"] == "complete" and complete["metrics"]["abstention"] == 0


def test_contract_semantic_reference_and_report_validators_cover_failures():
    import memory_order_analyzer.cpp_raii_contracts as contracts
    value = profile()
    broken = deepcopy(value); broken["wrapper_signatures"] = broken["wrapper_signatures"][:1]
    broken["profile_id"] = synchronization_profile_id(broken)
    with pytest.raises(AnalysisError, match="lock and unlock"):
        contracts._validate_profile(broken)
    broken = deepcopy(value); broken["provenance"] *= 2
    with pytest.raises(AnalysisError, match="provenance"):
        contracts._validate_profile(broken)
    bad_report = {"status": "partial", "exit_code": 0, "profiles": [], "dependencies": [], "graph": None}
    with pytest.raises(AnalysisError, match="exit code"):
        contracts._validate_report(bad_report)
    graph_ref = {"kind": "CppRaiiSynchronizationGraph", "id": "scope", "digest": "0" * 64}
    with pytest.raises(AnalysisError, match="missing"):
        contracts._validate_report({"status": "complete", "exit_code": 0, "profiles": [],
                                    "dependencies": [], "graph": graph_ref})
    with pytest.raises(AnalysisError, match="four"):
        contracts._validate_validation({"kind": "CppRaiiValidationReport", "languages": {}})
    with pytest.raises(AnalysisError, match="Unknown"):
        validate_cpp_raii_document({}, "Alien")
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_cpp_raii_document([], "CppRaiiSynchronizationProfile")
    with pytest.raises(AnalysisError, match="Expected kind"):
        validate_cpp_raii_document({"schema_version": 1, "kind": "Other"},
                                   "CppRaiiSynchronizationProfile")
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        contracts._load("missing-a4.json", "missing")
    invalid_request = request(value)
    invalid_request["roots"] *= 2
    with pytest.raises(AnalysisError, match="roots"):
        contracts._validate_request(invalid_request)
    invalid_request = request(value)
    invalid_request["budgets"]["profiles"] = 1
    other_profile = profile("libc++")
    invalid_request["synchronization_profiles"].append(
        dependency("CppRaiiSynchronizationProfile", other_profile["profile_id"], other_profile))
    invalid_request["synchronization_profiles"].sort(key=lambda item: (item["kind"], item["id"]))
    with pytest.raises(AnalysisError, match="profile budget"):
        contracts._validate_request(invalid_request)
    invalid_request = request(value)
    invalid_request["synchronization_profiles"][0]["kind"] = "Other"
    with pytest.raises(AnalysisError, match="wrong kind"):
        contracts._validate_request(invalid_request)
    invalid_request = request(value)
    invalid_request["members"][0]["source_facts"] = {"kind": "SourceSemanticFacts", "id": "x", "digest": "0" * 64}
    with pytest.raises(AnalysisError, match="missing"):
        contracts._validate_request(invalid_request)
    invalid_profile = deepcopy(value)
    invalid_profile["wrapper_signatures"][0]["parameter_roles"] = ["mutex", "mutex"]
    invalid_profile["profile_id"] = synchronization_profile_id(invalid_profile)
    with pytest.raises(AnalysisError, match="wrapper signature"):
        contracts._validate_profile(invalid_profile)

    mutex = {"id": "1" * 64, "object_id": "m", "kind": "plain", "resolution": "exact",
             "source_nodes": [], "ir_nodes": []}
    owner = {"id": "2" * 64, "object_id": "o", "owner_kind": "lock-guard",
             "mutex_ids": [mutex["id"]], "state": "owns", "thread_id": "t", "guard": None,
             "source_nodes": [], "ir_nodes": []}
    operation = {"id": "3" * 64, "operation": "lock", "owner_id": owner["id"],
                 "mutex_ids": [mutex["id"]], "outcome": "success", "guard": None,
                 "thread_id": "t", "source_nodes": [], "ir_nodes": []}
    local = {"language": "c++", "standard": "c++17", "mutexes": [mutex], "owners": [owner],
             "operations": [operation], "accesses": [], "dependencies": [], "status": "complete",
             "frontier": [], "synchronization_profile_id": value["profile_id"]}
    for field, expected in (("standard", "disagree"), ("synchronization_profile_id", "cannot adopt")):
        broken = deepcopy(local)
        if field == "standard": broken[field] = "c17"
        else: broken.update(language="c", standard="c17")
        with pytest.raises(AnalysisError, match=expected): contracts._validate_local(broken)
    broken = deepcopy(local); broken["owners"][0]["mutex_ids"] = ["9" * 64]
    with pytest.raises(AnalysisError, match="Owner"): contracts._validate_local(broken)
    broken = deepcopy(local); broken["operations"][0]["owner_id"] = "9" * 64
    with pytest.raises(AnalysisError, match="owner"): contracts._validate_local(broken)
    broken = deepcopy(local); broken["operations"][0]["mutex_ids"] = ["9" * 64]
    with pytest.raises(AnalysisError, match="mutex"): contracts._validate_local(broken)
    broken = deepcopy(local); broken["frontier"] = [diagnostic("x", "中", "en")]
    with pytest.raises(AnalysisError, match="Complete"): contracts._validate_local(broken)

    region = {"id": "4" * 64, "owner_id": owner["id"], "mutex_ids": [mutex["id"]],
              "thread_id": "t", "acquire_id": operation["id"], "release_id": operation["id"],
              "access_ids": [], "guard": None, "status": "complete", "evidence": []}
    proof = {"id": "5" * 64, "proof_kind": "mutual-exclusion", "mutex_id": mutex["id"],
             "region_ids": [region["id"], "6" * 64], "thread_ids": ["a", "b"], "guard": None,
             "status": "complete", "evidence": [], "limitations": []}
    graph = {"profiles": [], "dependencies": [], "mutexes": [mutex], "owners": [owner],
             "operations": [operation], "accesses": [], "held_regions": [region], "proofs": [], "gaps": [],
             "status": "complete", "frontier": []}
    broken = deepcopy(graph); broken["owners"][0]["state"] = "alien"
    with pytest.raises(AnalysisError, match="owner"): contracts._validate_graph(broken)
    broken = deepcopy(graph); broken["held_regions"][0]["owner_id"] = "9" * 64
    with pytest.raises(AnalysisError, match="Held"): contracts._validate_graph(broken)
    broken = deepcopy(graph); broken["proofs"] = [proof]
    with pytest.raises(AnalysisError, match="proof"): contracts._validate_graph(broken)
    broken = deepcopy(graph); proof2 = deepcopy(proof); proof2["region_ids"] = [region["id"], region["id"]]
    proof2["status"] = "partial"; broken["proofs"] = [proof2]
    with pytest.raises(AnalysisError, match="complete"): contracts._validate_graph(broken)
    broken = deepcopy(graph); broken["gaps"] = [diagnostic("x", "中", "en")]
    with pytest.raises(AnalysisError, match="Complete"): contracts._validate_graph(broken)
    bad_truth = {"kind": "CppRaiiValidationTruth", "cases": [
        {"case_id": "a", "mutexes": ["x", "x"], "owners": [], "regions": [], "proofs": [], "unknown": []}]}
    with pytest.raises(AnalysisError, match="mutexes"):
        contracts._validate_validation(bad_truth)


def test_offline_runner_cold_warm_dependency_and_output_boundaries(tmp_path):
    tu = "c" * 64
    facts = source_document(
        "SourceSemanticFacts", profile_id="a" * 64, physical_tu_id=tu,
        source_digest="b" * 64, status="complete", nodes=[], relations=[],
        counts={"nodes": counts(0), "relations": counts(0)}, diagnostics=[], frontier=[],
        semantic_digest=None)
    source_ref = dependency("SourceSemanticFacts", tu, facts)
    req = cpp_raii_document(
        "CppRaiiSynchronizationRequest", scope_id="scope-c", roots=["main"],
        members=[{**member(tu, "c17", "c"), "source_facts": source_ref}],
        dependencies=[source_ref], synchronization_profiles=[],
        budgets=dict(expected_cpp_raii_protocol()["budgets"]), semantic_digest=None)
    artifacts = tmp_path / "artifacts"
    (artifacts / "source-facts").mkdir(parents=True)
    (artifacts / "source-facts" / f"{tu}.json").write_text(json.dumps(facts), encoding="utf-8")
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(req), encoding="utf-8")
    cold = model_cpp_raii_synchronization(request_path, artifacts, tmp_path / "cold")
    warm = model_cpp_raii_synchronization(request_path, artifacts, tmp_path / "warm")
    assert cold["status"] == warm["status"] == "complete"
    assert cold["semantic_digest"] == warm["semantic_digest"]
    assert cold["cache"] == {"hits": 0, "misses": 2}
    assert warm["cache"] == {"hits": 2, "misses": 0}
    with pytest.raises(AnalysisError, match="fresh output"):
        model_cpp_raii_synchronization(request_path, artifacts, tmp_path / "cold")
    stale = deepcopy(req); stale["dependencies"][0]["digest"] = "0" * 64
    stale["members"][0]["source_facts"] = stale["dependencies"][0]
    stale["semantic_digest"] = semantic_digest(stale)
    stale_path = tmp_path / "stale.json"; stale_path.write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(AnalysisError, match="digest changed"):
        model_cpp_raii_synchronization(stale_path, artifacts, tmp_path / "stale")


def test_runner_dispatch_and_missing_dependency_errors(tmp_path):
    import memory_order_analyzer.model_cpp_raii_synchronization as runner
    with pytest.raises(AnalysisError, match="Unsupported"):
        runner._read_kind(tmp_path / "x", "Other")
    with pytest.raises(AnalysisError, match="missing"):
        runner._resolve_dependency(tmp_path, {"kind": "CppRaiiLocalFacts", "id": "none",
                                              "digest": "0" * 64})
    for kind in ("ModuleFacts", "ThreadContextGraph", "CppThreadLifecycleGraph",
                 "DegradedSourceReport", "SinglePublicationProtocolGraph", "ProgramEntityIndex"):
        with pytest.raises(AnalysisError):
            runner._read_kind(tmp_path / "missing.json", kind)


def test_precomputed_cpp_runner_profile_conflict_and_limits(tmp_path, monkeypatch):
    value = profile()
    local = cpp_raii_document(
        "CppRaiiLocalFacts", scope_id="cpp-scope", physical_tu_id="t" * 64,
        profile_id="a" * 64, language="c++", standard="c++17", status="complete",
        synchronization_profile_id=value["profile_id"], mutexes=[], owners=[], operations=[],
        accesses=[], dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    local_ref = dependency("CppRaiiLocalFacts", local["physical_tu_id"], local)
    profile_ref = dependency("CppRaiiSynchronizationProfile", value["profile_id"], value)
    req = cpp_raii_document(
        "CppRaiiSynchronizationRequest", scope_id="cpp-scope", roots=["main"],
        members=[{**member(local["physical_tu_id"]), "source_facts": None}],
        dependencies=[local_ref], synchronization_profiles=[profile_ref],
        budgets=dict(expected_cpp_raii_protocol()["budgets"]), semantic_digest=None)
    artifacts = tmp_path / "store"
    (artifacts / "local-facts").mkdir(parents=True)
    (artifacts / "cpp-raii-profiles").mkdir()
    (artifacts / "local-facts" / f"{local['physical_tu_id']}.json").write_text(json.dumps(local), encoding="utf-8")
    (artifacts / "cpp-raii-profiles" / f"{value['profile_id']}.json").write_text(json.dumps(value), encoding="utf-8")
    path = tmp_path / "cpp-request.json"; path.write_text(json.dumps(req), encoding="utf-8")
    assert model_cpp_raii_synchronization(path, artifacts, tmp_path / "cpp-out")["exit_code"] == 0

    other = profile("libc++", "c++17")
    other_ref = dependency("CppRaiiSynchronizationProfile", other["profile_id"], other)
    (artifacts / "cpp-raii-profiles" / f"{other['profile_id']}.json").write_text(json.dumps(other), encoding="utf-8")
    conflict = deepcopy(req); conflict["synchronization_profiles"] = sorted([profile_ref, other_ref], key=lambda x: x["id"])
    conflict["semantic_digest"] = semantic_digest(conflict)
    conflict_path = tmp_path / "conflict.json"; conflict_path.write_text(json.dumps(conflict), encoding="utf-8")
    with pytest.raises(AnalysisError, match="one synchronization profile"):
        model_cpp_raii_synchronization(conflict_path, artifacts, tmp_path / "conflict-out")

    import memory_order_analyzer.model_cpp_raii_synchronization as runner
    ticks = iter((0, 9999))
    monkeypatch.setattr(runner, "monotonic", lambda: next(ticks))
    with pytest.raises(AnalysisError, match="request budget"):
        model_cpp_raii_synchronization(path, artifacts, tmp_path / "timeout-out")


def test_analysis_conservative_branch_matrix():
    value = profile()
    cycle = [{"id": "a", "opcode": "phi", "operands": ["a", "root"]}]
    assert trace_mutex_provenance(["a"], cycle)["roots"] == ["root"]
    wrong = {"wrong": {"target": "wrong", "layout": value["data_layout"], "values": [], "calls": []},
             "right": {"target": value["target"], "layout": value["data_layout"], "values": [],
                       "calls": [{"id": "ignored", "target": "ordinary", "arguments": []}]}}
    assert module_synchronization_calls(wrong, value)[0] == []
    unknown_relation = relation(1, "cpp-raii-owner-object", "x", "owner", reason=None)
    unsupported = relation(2, "cpp-raii-owner-unsupported", "bad", None,
                           reason="adopt_lock")
    orphan = relation(3, "cpp-raii-owner-lock", "orphan", "new-owner",
                      reason="unique-lock")
    facts = {"physical_tu_id": "tu", "profile_id": "a" * 64, "status": "complete",
             "nodes": [], "relations": [unknown_relation, unsupported, orphan]}
    partial = build_local_facts("scope", member(), facts, value, modules={})
    assert {item["code"] for item in partial["frontier"]} >= {
        "unsupported-adopt-lock", "raii-evidence-incomplete"}
    assert any(item["owner_kind"] == "unknown" for item in partial["owners"])
    missing = build_local_facts("scope", member(), None, None, modules={})
    assert {item["code"] for item in missing["frontier"]} >= {
        "source-evidence-missing", "library-profile-unsupported"}
    unsupported_profile = profile(status="unsupported")
    unverified = build_local_facts("scope", member(), {"status": "complete", "relations": []},
                                   unsupported_profile, modules={})
    assert unverified["frontier"][0]["code"] == "library-profile-unsupported"
    assert _state_transition("owns", {"operation": "lock", "guard": None}, "unique-lock") == "unknown"
    assert _state_transition("released", {"operation": "move", "guard": None}, "unique-lock") == "unknown"
    assert _state_transition("owns", {"operation": "alien", "guard": None}, "unique-lock") == "unknown"

    modules = {"a": module(value, "a.cpp", "a"), "b": module(value, "b.cpp", "b")}
    first = build_local_facts("scope", member("a"), source("a", "a.cpp", "guard-a"), value,
                              modules=modules)
    second = build_local_facts("scope", member("b"), source("b", "b.cpp", "guard-b"), value,
                               modules=modules)
    marker = first["operations"][0]["source_nodes"][0]
    thread_graph = {"scope_id": "threads", "instances": [{"id": "mapped", "source_nodes": [marker]}]}
    mapped = build_synchronization_graph(request(value, [member("a")]), [first], [value],
                                         thread_graph=thread_graph)
    assert any(item["thread_id"] == "mapped" for item in mapped["owners"])
    open_only = deepcopy(first)
    open_only["operations"] = [item for item in open_only["operations"] if item["operation"] == "construct"]
    open_only["semantic_digest"] = semantic_digest(open_only)
    open_graph = build_synchronization_graph(request(value, [member("a")]), [open_only], [value],
                                             degraded_report={"scope_id": "degraded"},
                                             publication_graph={"scope_id": "publication"})
    assert any(item["code"] == "unclosed-held-region" for item in open_graph["gaps"])
    for facts_item, thread in ((first, "a"), (second, "b")):
        for operation in facts_item["operations"]: operation["thread_id"] = thread
    limited = build_synchronization_graph(request(value, [member("a"), member("b")], held_regions=1),
                                          [first, second], [value])
    assert any(item["code"] == "held-regions-budget-exhausted" for item in limited["frontier"])


def test_cli_command_failure_exit_and_bilingual_report():
    assert "model-cpp-raii-synchronization" in cli.parser()._subparsers._group_actions[0].choices
    stdout, stderr = io.StringIO(), io.StringIO()
    assert cli.main(["model-cpp-raii-synchronization"], stdout=stdout, stderr=stderr) == 1
    parsed = json.loads(stdout.getvalue())
    assert parsed["status"] == "failed" and parsed["diagnostics"][0]["detail_en"]
    stdout, stderr = io.StringIO(), io.StringIO()
    code = cli.main(["model-cpp-raii-synchronization", "--request", "missing",
                     "--artifact-store", "missing", "--output", "out"],
                    stdout=stdout, stderr=stderr)
    assert code == 1 and json.loads(stdout.getvalue())["exit_code"] == 1
