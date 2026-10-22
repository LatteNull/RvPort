import json
from copy import deepcopy
from pathlib import Path

import pytest

from memory_order_analyzer.cli import parser
from memory_order_analyzer.contracts import AnalysisError, file_hash, identity
from memory_order_analyzer.cpp_thread_contracts import (
    cpp_thread_document, dependency, diagnostic, expected_cpp_thread_protocol,
    library_profile_id, semantic_digest, validate_cpp_thread_document,
)


ROOT = Path(__file__).resolve().parents[2]


def budgets(**overrides):
    value = dict(expected_cpp_thread_protocol()["budgets"])
    value.update(overrides)
    return value


def profile(vendor="libstdc++", standard="c++17", *, status="verified"):
    fields = {
        "profile_id": "pending", "vendor": vendor, "version": "13.3.0" if vendor == "libstdc++" else "18.1.3",
        "cxx_standard": standard, "cxx_abi": "itanium", "target": "x86_64-pc-linux-gnu",
        "data_layout": "e-p:64:64", "pointer_width": 64, "exceptions": True, "rtti": True,
        "thread_backend": "pthread", "toolchain_lineage": "locked-dev-image",
        "header_digests": [{"kind": "Header", "id": "thread", "digest": "a" * 64}],
        "wrapper_signatures": [{"role": "entry-broker", "symbol": "broker", "calling_convention": "ccc",
                                "parameter_roles": ["callable"], "digest": "b" * 64}],
        "model_version": "cpp-thread-library-v1", "status": status,
        "provenance": ["compile-only", "llvm-ir"], "semantic_digest": None,
    }
    envelope = {"schema_version": 1, "kind": "CppThreadLibraryProfile", "analysis_version": "0.1.0",
                "policy_id": "cpp-thread-lifecycle-v1", **fields}
    fields["profile_id"] = library_profile_id(envelope)
    return cpp_thread_document("CppThreadLibraryProfile", **fields)


def request(profile_value=None, *, language="c++", standard="c++17"):
    profile_value = profile_value or profile(standard=standard)
    source = {"kind": "SourceSemanticFacts", "id": "tu", "digest": "c" * 64}
    ir = {"kind": "LLVMSourceBindingFacts", "id": "artifact", "digest": "d" * 64}
    profile_ref = dependency("CppThreadLibraryProfile", profile_value["profile_id"], profile_value)
    return cpp_thread_document(
        "CppThreadLifecycleRequest", scope_id="scope", roots=["main"],
        members=[{"physical_tu_id": "tu", "profile_id": "e" * 64, "language": language,
                  "standard": standard, "source_facts": source, "ir_facts": ir}],
        dependencies=sorted([source, ir], key=lambda item: (item["kind"], item["id"])),
        library_profiles=[profile_ref], budgets=budgets(), semantic_digest=None)


def test_pre_a3_protocol_schema_truth_and_cli_baseline_are_frozen():
    baseline = json.loads((ROOT / "tests/fixtures/cpp-thread-lifecycle/pre-a3-baseline.json").read_text())
    intentionally_extended = {
        "schemas/degraded_source_analysis.json",
        "schemas/source_evidence.json",
        "protocols/source-evidence-protocol.json",
    }
    unchanged = {path: digest for path, digest in baseline["files"].items()
                 if path not in intentionally_extended}
    assert {path: file_hash(ROOT / path) for path in unchanged} == unchanged
    degraded = json.loads((ROOT / "schemas/degraded_source_analysis.json").read_text())
    failure_classes = degraded["$defs"]["FailureRecord"]["properties"]["failure_class"]["enum"]
    assert {"external-artifact-missing", "external-build-failed", "artifact-format-unsupported",
            "reader-incompatible"} <= set(failure_classes)
    source_evidence = json.loads((ROOT / "schemas/source_evidence.json").read_text())
    profile_schema = source_evidence["$defs"]["CompilationProfileIdentity"]["allOf"][1]
    standard_values = profile_schema["properties"]["standard"]["enum"]
    assert {"c89", "c99", "c11", "c17", "c23", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"} <= set(standard_values)
    source_protocol = json.loads((ROOT / "protocols/source-evidence-protocol.json").read_text())
    assert source_protocol["protocol_version"] == 2
    assert source_protocol["kinds"]["CompilationProfileIdentity"] == 2
    assert source_protocol["kinds"]["SourceSemanticRequest"] == 2
    assert source_protocol["kinds"]["SourceSemanticFacts"] == 1
    commands = parser()._subparsers._group_actions[0].choices
    assert set(baseline["existing_cli_operations"]) - {"collect", "link"} <= set(commands)
    assert {"collect", "link"}.isdisjoint(commands)
    assert "ingest-bc-bundle" in commands
    assert baseline["contract_versions"] == {
        "ModuleFacts": 2, "RunReport": 2, "EffectSummary": 1,
        "ThreadContextGraph": 1, "PublicationRiskReport": 1,
        "SourceSemanticFacts": 1, "DegradedSourceAnalysisReport": 1,
    }


def test_protocol_profile_request_and_bilingual_diagnostics_are_strict():
    protocol = expected_cpp_thread_protocol()
    assert protocol["kinds"]["CppThreadLifecycleGraph"] == 1
    value = profile()
    assert value["profile_id"] == library_profile_id(value)
    assert request(value) == validate_cpp_thread_document(request(value), "CppThreadLifecycleRequest")
    item = diagnostic("x", "中文" * 50, "English" * 50, suggestion="建议", suggestion_en="Suggestion", limit=32)
    assert len(item["detail"].encode()) <= 32 and len(item["detail_en"].encode()) <= 32

    invalid = deepcopy(value); invalid["extra"] = True
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_cpp_thread_document(invalid, invalid["kind"])
    invalid = deepcopy(value); invalid["schema_version"] = 2
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_cpp_thread_document(invalid, invalid["kind"])
    invalid = deepcopy(value); invalid["version"] = "changed"; invalid["semantic_digest"] = semantic_digest(invalid)
    with pytest.raises(AnalysisError, match="identity"):
        validate_cpp_thread_document(invalid, invalid["kind"])


def test_request_rejects_duplicate_mixed_stale_and_invalid_budget():
    value = request()
    duplicate = deepcopy(value); duplicate["members"] *= 2; duplicate["semantic_digest"] = semantic_digest(duplicate)
    with pytest.raises(AnalysisError, match="unique"):
        validate_cpp_thread_document(duplicate, duplicate["kind"])
    mixed = deepcopy(value); mixed["members"][0]["standard"] = "c17"; mixed["semantic_digest"] = semantic_digest(mixed)
    with pytest.raises(AnalysisError, match="disagree"):
        validate_cpp_thread_document(mixed, mixed["kind"])
    stale = deepcopy(value); stale["dependencies"] = stale["dependencies"][:-1]; stale["semantic_digest"] = semantic_digest(stale)
    with pytest.raises(AnalysisError, match="missing"):
        validate_cpp_thread_document(stale, stale["kind"])
    over = deepcopy(value); over["budgets"]["instances"] = 65537; over["semantic_digest"] = semantic_digest(over)
    with pytest.raises(AnalysisError, match="greater"):
        validate_cpp_thread_document(over, over["kind"])


def test_c_member_never_adopts_cpp_local_facts():
    value = cpp_thread_document(
        "CppThreadLocalFacts", scope_id="scope", physical_tu_id="c-tu", profile_id="f" * 64,
        language="c", standard="c17", status="complete", library_profile_id=None,
        callables=[], operations=[], dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    assert value["language"] == "c"
    broken = deepcopy(value); broken["library_profile_id"] = "a" * 64; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="cannot adopt"):
        validate_cpp_thread_document(broken, broken["kind"])


def test_protocol_and_schema_loader_failures(tmp_path, monkeypatch):
    import memory_order_analyzer.cpp_thread_contracts as contracts
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        contracts._load(tmp_path / "missing.json", "missing")
    bad = tmp_path / "protocol.json"; bad.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="does not match"):
        expected_cpp_thread_protocol(bad)
    with pytest.raises(AnalysisError, match="Unknown"):
        validate_cpp_thread_document({}, "UnknownKind")
    wrong = profile(); wrong["kind"] = "CppThreadLifecycleRequest"
    with pytest.raises(AnalysisError, match="Expected"):
        validate_cpp_thread_document(wrong, "CppThreadLibraryProfile")


def test_semantic_validators_reject_every_reference_and_denominator_fault():
    import memory_order_analyzer.cpp_thread_contracts as c
    value = request()
    broken = deepcopy(value); broken["roots"] *= 2
    with pytest.raises(AnalysisError, match="roots"):
        c._validate_request(broken)
    broken = deepcopy(value); broken["library_profiles"][0]["kind"] = "Other"
    with pytest.raises(AnalysisError, match="wrong kind"):
        c._validate_request(broken)
    broken = deepcopy(value); broken["library_profiles"] = []
    with pytest.raises(AnalysisError, match="explicit library"):
        c._validate_request(broken)

    value = profile()
    broken = deepcopy(value); broken["wrapper_signatures"][0]["parameter_roles"] = ["z", "z"]
    broken["profile_id"] = library_profile_id(broken)
    with pytest.raises(AnalysisError, match="parameter roles"):
        c._validate_profile(broken)
    broken = deepcopy(value); broken["provenance"] *= 2
    with pytest.raises(AnalysisError, match="provenance"):
        c._validate_profile(broken)

    callable_ = {"id": "a" * 64, "callable_kind": "free-function", "entity_id": None,
                 "receiver_id": None, "capture_ids": [], "resolution": "exact",
                 "targets": ["target"], "source_nodes": ["source"], "ir_nodes": ["ir"]}
    operation = {"id": "b" * 64, "operation": "construct", "object_id": "object",
                 "other_object_id": None, "callable_id": callable_["id"], "outcome": "success",
                 "guard": None, "wrapper_role": "construct-attempt", "native_handle": "handle",
                 "source_nodes": ["source"], "ir_nodes": ["ir"], "repeated": False}
    local = {"language": "c++", "standard": "c++20", "library_profile_id": "p",
             "callables": [callable_], "operations": [operation], "dependencies": []}
    broken = deepcopy(local); broken["standard"] = "c17"
    with pytest.raises(AnalysisError, match="disagree"):
        c._validate_local(broken)
    broken = deepcopy(local); broken["callables"][0]["targets"] = []
    with pytest.raises(AnalysisError, match="one target"):
        c._validate_local(broken)
    broken = deepcopy(local); broken["operations"][0]["callable_id"] = "missing"
    with pytest.raises(AnalysisError, match="dangling"):
        c._validate_local(broken)
    broken = deepcopy(local); broken["operations"][0]["source_nodes"] *= 2
    with pytest.raises(AnalysisError, match="source_nodes"):
        c._validate_local(broken)
    broken = deepcopy(local); broken["callables"][0]["capture_ids"] = ["x", "x"]
    with pytest.raises(AnalysisError, match="capture_ids"):
        c._validate_local(broken)

    context = {"id": "c" * 64}
    instance = {"id": "d" * 64, "context_id": context["id"], "parent_id": None,
                "cardinality": "single", "reason": None}
    object_ = {"id": "e" * 64, "state": "joinable", "instance_id": instance["id"]}
    graph = {"profiles": [], "dependencies": [], "objects": [object_], "contexts": [context],
             "instances": [instance], "transitions": [], "relations": [], "gaps": [],
             "status": "complete", "frontier": []}
    for field, expected in (("context_id", "context"), ("parent_id", "parent")):
        broken = deepcopy(graph); broken["instances"][0][field] = "missing"
        with pytest.raises(AnalysisError, match=expected): c._validate_graph(broken)
    broken = deepcopy(graph); broken["instances"][0]["reason"] = "bad"
    with pytest.raises(AnalysisError, match="Single"): c._validate_graph(broken)
    broken = deepcopy(graph); broken["instances"][0].update(cardinality="merged", reason=None)
    with pytest.raises(AnalysisError, match="requires"): c._validate_graph(broken)
    broken = deepcopy(graph); broken["objects"][0]["state"] = "alien"
    with pytest.raises(AnalysisError, match="Unknown"): c._validate_graph(broken)
    broken = deepcopy(graph); broken["objects"][0]["instance_id"] = "missing"
    with pytest.raises(AnalysisError, match="dangling instance"): c._validate_graph(broken)
    broken = deepcopy(graph); broken["instances"][0].update(cardinality="merged", reason="loop")
    with pytest.raises(AnalysisError, match="partial"): c._validate_graph(broken)
    broken = deepcopy(graph); broken["gaps"] = [{"id": "gap"}]
    with pytest.raises(AnalysisError, match="Complete"): c._validate_graph(broken)


def test_report_validation_suite_and_schema_shape_failures(monkeypatch):
    import memory_order_analyzer.cpp_thread_contracts as c
    with pytest.raises(AnalysisError, match="exit code"):
        c._validate_report({"status": "partial", "exit_code": 0, "profiles": [],
                            "dependencies": [], "graph": None})
    graph = {"kind": "CppThreadLifecycleGraph", "id": "graph", "digest": "a" * 64}
    with pytest.raises(AnalysisError, match="missing"):
        c._validate_report({"status": "complete", "exit_code": 0, "profiles": [],
                            "dependencies": [], "graph": graph})
    cases = [
        {"id": "1", "language": "c", "standard": "c11", "vendor": None},
        {"id": "2", "language": "c", "standard": "c17", "vendor": None},
        {"id": "3", "language": "c++", "standard": "c++17", "vendor": "libstdc++"},
        {"id": "4", "language": "c++", "standard": "c++20", "vendor": "libc++"},
    ]
    c._validate_validation({"kind": "CppThreadValidationSuite", "cases": cases})
    broken = deepcopy(cases); broken.pop()
    with pytest.raises(AnalysisError, match="four profiles"):
        c._validate_validation({"kind": "CppThreadValidationSuite", "cases": broken})
    broken = deepcopy(cases); broken[-1]["vendor"] = "libstdc++"
    with pytest.raises(AnalysisError, match=r"libstdc\+\+"):
        c._validate_validation({"kind": "CppThreadValidationSuite", "cases": broken})
    truth_cases = [{"case_id": "a", "callables": [], "instances": [], "relations": [], "unknown": []}]
    c._validate_validation({"kind": "CppThreadValidationTruth", "cases": truth_cases})
    truth_cases[0]["unknown"] = ["x", "x"]
    with pytest.raises(AnalysisError, match="unknown"):
        c._validate_validation({"kind": "CppThreadValidationTruth", "cases": truth_cases})

    original = c._load
    def invalid_schema(path, code):
        if str(path).endswith("cpp_thread_lifecycle.json"):
            return {}
        return original(path, code)
    monkeypatch.setattr(c, "_load", invalid_schema)
    with pytest.raises(AnalysisError, match="budget schema"):
        c.expected_cpp_thread_protocol()
