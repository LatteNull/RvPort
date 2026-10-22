import json
from copy import deepcopy
from pathlib import Path

import pytest

import memory_order_analyzer.source_binding as binding_module
from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.source_binding import build_source_ir_binding
from memory_order_analyzer.source_cache import SourceEvidenceCache, cache_key
from memory_order_analyzer.source_contracts import (
    counts,
    dependency,
    diagnostic,
    expected_source_protocol,
    semantic_digest,
    source_document,
    validate_source_document,
)
from memory_order_analyzer import source_cache as source_cache_module
from memory_order_analyzer.source_index import build_entity_index
from memory_order_analyzer.source_overlay import build_overlay, resolve_artifact_object
from memory_order_analyzer.source_profile import build_profile, replay_failure
from memory_order_analyzer.source_worker import analyze_ir_binding, analyze_source, check_source_worker


def budgets(**overrides):
    value = dict(expected_source_protocol()["budgets"])
    value.update(overrides)
    return value


def profile(tmp_path, name="unit.c", arguments=None, **kwargs):
    source = tmp_path / name
    source.write_text("int flag;\n", encoding="utf-8")
    record = {"directory": str(tmp_path), "file": name,
              "arguments": arguments or ["gcc", "-std=c17", "-g", "-O2", "-c", name]}
    return build_profile(record, compiler_version="13.3.0", **kwargs)


def node(identifier, *, name="flag", definition=True, linkage="external",
         definition_kind="strong", source_file="unit.c", kind="variable"):
    return {"id": identifier, "kind": kind, "name": name, "qualified_name": name,
            "usr": f"usr:{name}" if linkage == "external" else None,
            "mangled_name": name or None, "canonical_decl": identifier,
            "definition": definition, "definition_kind": definition_kind,
            "linkage": linkage, "language_linkage": "c", "storage": "none",
            "visibility": "default", "tls": False, "canonical_type": "int",
            "abi": {"complete": True, "size_bits": 32, "align_bits": 32}, "source": {"spelling": {"file": source_file, "line": 1, "column": 5},
                                    "expansion": {"file": source_file, "line": 1, "column": 5}},
            "macro_stack": [], "attributes": []}


def facts(profile_value, physical, nodes, relations=(), status="complete"):
    return source_document(
        "SourceSemanticFacts", profile_id=profile_value["profile_id"], physical_tu_id=physical,
        source_digest=profile_value["source"]["sha256"], status=status,
        nodes=sorted(nodes, key=lambda item: item["id"]),
        relations=sorted(relations, key=lambda item: item["id"]),
        counts={"nodes": counts(len(nodes))}, diagnostics=[], frontier=[], semantic_digest=None)


def test_language_context_uses_v2_and_preserves_strict_v1_boundary(tmp_path):
    profile_value = profile(tmp_path, arguments=["gcc", "-std=gnu99", "-c", "unit.c"])
    assert profile_value["schema_version"] == 2
    assert (profile_value["standard"], profile_value["dialect"], profile_value["standard_source"]) == (
        "c99", "gnu", "explicit")
    request = source_document(
        "SourceSemanticRequest", profile=profile_value, physical_tu_id="a" * 64,
        source_path=profile_value["source"]["path"], budgets=budgets())
    assert request["schema_version"] == 2

    legacy_claiming_v2_fields = deepcopy(profile_value)
    legacy_claiming_v2_fields["schema_version"] = 1
    with pytest.raises(AnalysisError, match="v1"):
        validate_source_document(legacy_claiming_v2_fields, "CompilationProfileIdentity")
    future = deepcopy(profile_value)
    future["schema_version"] = 3
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_source_document(future, "CompilationProfileIdentity")
    mismatched_request = deepcopy(request)
    mismatched_request["schema_version"] = 1
    with pytest.raises(AnalysisError, match="versions must match"):
        validate_source_document(mismatched_request, "SourceSemanticRequest")


def index_request(scope, fact_map, **budget_overrides):
    return source_document(
        "ProgramEntityIndexRequest", scope_id=scope, members=sorted(fact_map),
        dependencies=sorted((dependency("SourceSemanticFacts", key, value)
                             for key, value in fact_map.items()), key=lambda item: (item["kind"], item["id"])),
        budgets=budgets(**budget_overrides))


def module(artifact, source_file="unit.c", symbols=("flag",)):
    globals_ = [{"id": f"global:{name}", "name": name, "linkage": "external",
                 "declaration": False, "comdat": False} for name in symbols]
    return {"schema_version": 2, "kind": "ModuleFacts", "artifact_key": artifact,
            "module_hash": "f" * 64, "target": "x86_64-pc-linux-gnu", "layout": "",
            "producer": [], "functions": [], "globals": globals_,
            "events": [{"id": "event:load", "kind": "load", "function": "reader",
                        "source": {"inline_chain": [{"file": source_file, "line": 1, "column": 5}]}}],
            "calls": [], "capabilities": {}, "source_mapping": "complete", "values": [],
            "protocol": {}, "extraction": {"status": "complete"}}


def test_binding_uses_typed_tu_identity_when_debug_paths_are_split(tmp_path):
    profile_value = profile(tmp_path)
    physical = "b" * 64
    semantic = facts(profile_value, physical, [node("node:flag", source_file=str(tmp_path / "unit.c"))])
    modules = {"a" * 64: module("a" * 64, source_file="unit.c")}
    modules["a" * 64]["events"][0]["source"]["inline_chain"][0]["directory"] = str(tmp_path)
    ir = {"a" * 64: llvm_facts("a" * 64, profile_value, physical)}
    indexed = build_entity_index(index_request("scope", {physical: semantic}),
                                 {physical: semantic}, {physical: profile_value})
    binding = build_source_ir_binding(
        binding_request("scope", indexed, {physical: semantic}, modules, ir),
        indexed, {physical: semantic}, modules, ir)
    assert binding["entity_bindings"][0]["resolution"] == "exact"
    assert binding["expression_bindings"] == []


def test_binding_does_not_associate_a_different_typed_physical_tu(tmp_path):
    profile_value = profile(tmp_path)
    source_tu, other_tu = "b" * 64, "c" * 64
    semantic = facts(profile_value, source_tu, [node("node:flag")])
    modules = {"a" * 64: module("a" * 64)}
    ir = {"a" * 64: llvm_facts("a" * 64, profile_value, other_tu)}
    indexed = build_entity_index(index_request("scope", {source_tu: semantic}),
                                 {source_tu: semantic}, {source_tu: profile_value})
    binding = build_source_ir_binding(
        binding_request("scope", indexed, {source_tu: semantic}, modules, ir),
        indexed, {source_tu: semantic}, modules, ir)
    assert binding["entity_bindings"][0]["resolution"] == "unresolved"
    assert binding["entity_bindings"][0]["opposed"] == ["missing-ir-symbol"]


def llvm_facts(artifact, profile_value, physical, symbols=("flag",)):
    values = [{"id": f"global:{name}", "kind": "global", "name": name,
               "linkage": "external", "visibility": "default", "tls": False,
               "comdat": False, "definition": True, "canonical_type": "i32",
               "abi": {"complete": True, "size_bits": 32, "align_bits": 32}}
              for name in symbols]
    return source_document(
        "LLVMSourceBindingFacts", artifact_key=artifact, profile_id=profile_value["profile_id"],
        physical_tu_id=physical, bitcode_digest="d" * 64,
        target="x86_64-pc-linux-gnu", data_layout="e-p:64:64", status="complete",
        symbols=values, counts={"symbols": counts(len(values))}, diagnostics=[], frontier=[],
        semantic_digest=None)


def binding_request(scope, index, fact_map, modules, ir_facts=None, **budget_overrides):
    ir_facts = ir_facts or {}
    return source_document(
        "SourceIRBindingRequest", scope_id=scope,
        entity_index=dependency("ProgramEntityIndex", scope, index),
        source_facts=sorted((dependency("SourceSemanticFacts", key, value)
                            for key, value in fact_map.items()), key=lambda item: (item["kind"], item["id"])),
        module_facts=sorted((dependency("ModuleFacts", key, value)
                            for key, value in modules.items()), key=lambda item: (item["kind"], item["id"])),
        ir_facts=sorted((dependency("LLVMSourceBindingFacts", key, value)
                        for key, value in ir_facts.items()), key=lambda item: (item["kind"], item["id"])),
        budgets=budgets(**budget_overrides))


def test_protocol_counts_and_bilingual_diagnostics():
    assert expected_source_protocol()["llvm_version"] == "21.1.8"
    assert counts(0)["ratio"] is None
    assert counts(4, emitted=2, skipped=1, failed=1)["ratio"] == 0.5
    with pytest.raises(AnalysisError, match="Counts"):
        counts(1, emitted=2)
    item = diagnostic("x", "中文", "English", suggestion="修复", suggestion_en="Fix")
    assert item["detail_en"] == "English" and item["suggestion_en"] == "Fix"


def test_binding_compatibility_helpers_cover_conservative_edges():
    assert binding_module._compatible_linkage("none", "private")
    assert binding_module._compatible_linkage("internal", "internal")
    assert binding_module._compatible_linkage("external", "common")
    assert binding_module._compatible_linkage("unique_external", "linkonce")
    assert not binding_module._compatible_linkage("module", "external")
    assert binding_module._parameter_count("int") is None
    assert binding_module._parameter_count("void (void)") == 0
    assert binding_module._parameter_count("int (int, ..., long)") == 2
    assert binding_module._location_path(None) is None
    assert binding_module._location_path({"file": "unit.c"}) == "unit.c"
    assert not binding_module._same_location({"file": "a.c", "line": 1},
                                             {"file": "b.c", "line": 1})
    assert not binding_module._same_location({"line": 1}, {"line": 2})
    assert binding_module._same_location({"line": 1}, {"line": 1})
    assert binding_module._same_location({"line": 1, "column": 10},
                                         {"line": 1, "column": 42})
    assert not binding_module._same_location({"line": 1, "column": 10},
                                             {"line": 1, "column": 43})


def test_typed_binding_evidence_reports_each_abi_conflict():
    source = node("n", kind="function")
    source.update(canonical_type="int (int)", visibility="hidden", tls=True)
    typed = {"definition": False, "linkage": "private", "visibility": "default",
             "tls": False, "target": "aarch64-unknown-linux-gnu",
             "profile_id": "other", "physical_tu_id": "other",
             "abi": {"complete": True, "parameters": 2}}
    entity = {"key": {"compatibility": {"target": "x86_64-pc-linux-gnu"}}}
    fact = {"profile_id": "profile", "physical_tu_id": "tu"}
    evidence, opposed = binding_module._typed_evidence(source, typed, entity, fact)
    assert evidence == ["profile-tu", "mangled-name", "definition-role", "linkage", "visibility", "tls"]
    assert set(opposed) >= {"definition-role-mismatch", "linkage-mismatch",
                            "visibility-mismatch", "tls-mismatch", "target-mismatch",
                            "profile-tu-mismatch", "function-type-abi-mismatch"}
    variable = node("v")
    typed.update(definition=True, linkage="external", visibility="default", tls=False,
                 target="x86_64-pc-linux-gnu", profile_id="profile", physical_tu_id="tu",
                 abi={"complete": False})
    _, opposed = binding_module._typed_evidence(variable, typed, entity, fact)
    assert opposed == ["missing-type-abi"]


def test_profile_canonicalizes_gcc_inputs_and_detects_changes(tmp_path):
    include = tmp_path / "inc"
    include.mkdir()
    forced = tmp_path / "config.h"
    forced.write_text("#define X 1\n", encoding="utf-8")
    value = profile(tmp_path, arguments=["g++", "-std=gnu++20", "-I", "inc", "-DVALUE=1",
                                         "-UOLD", "-include", "config.h", "--target=aarch64-linux-gnu",
                                         "-g", "-O3", "-c", "unit.c"])
    assert value["compiler"]["family"] == "gcc"
    assert value["standard"] == "c++20" and value["target"] == "aarch64-linux-gnu"
    assert value["includes"] == [str(include.resolve())]
    assert value["macros"] == ["!OLD", "VALUE=1"] and value["debug"] is True
    changed = dict(value)
    changed["target"] = "other"
    with pytest.raises(AnalysisError, match="identity"):
        validate_source_document(changed, "CompilationProfileIdentity")


@pytest.mark.parametrize("arguments", [["gcc", "-std=vendor-c", "unit.c"], []])
def test_profile_rejects_unknown_or_empty_compile_record(tmp_path, arguments):
    (tmp_path / "unit.c").write_text("int x;", encoding="utf-8")
    with pytest.raises(AnalysisError):
        build_profile({"directory": str(tmp_path), "file": "unit.c", "arguments": arguments},
                      compiler_version="13")
    assert replay_failure("x", "错", "error")["suggestion_en"]


def test_strict_contract_rejects_unknown_future_and_dangling_nodes(tmp_path):
    p = profile(tmp_path)
    physical = "a" * 64
    value = facts(p, physical, [node("n")])
    value["extra"] = True
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_source_document(value, "SourceSemanticFacts")
    value.pop("extra")
    value["schema_version"] = 2
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_source_document(value, "SourceSemanticFacts")
    broken = facts(p, physical, [node("n")])
    broken["nodes"][0]["canonical_decl"] = "missing"
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="dangling"):
        validate_source_document(broken, "SourceSemanticFacts")


def test_entity_index_resolves_cross_tu_and_is_deterministic(tmp_path):
    p1 = profile(tmp_path, "one.c")
    p2 = profile(tmp_path, "two.c")
    one, two = "1" * 64, "2" * 64
    fact_map = {one: facts(p1, one, [node("one:decl", definition=False)]),
                two: facts(p2, two, [node("two:def", source_file="two.c")])}
    request = index_request("scope", fact_map)
    first = build_entity_index(request, fact_map, {one: p1, two: p2})
    second = build_entity_index(request, dict(reversed(list(fact_map.items()))), {two: p2, one: p1})
    assert first["semantic_digest"] == second["semantic_digest"]
    assert first["entities"][0]["resolution"] == "resolved"
    assert len(first["entities"][0]["declarations"]) == 2


def test_entity_index_isolates_static_and_reports_conflict_and_budget(tmp_path):
    p1 = profile(tmp_path, "one.c")
    p2 = profile(tmp_path, "two.c")
    one, two = "1" * 64, "2" * 64
    local = {one: facts(p1, one, [node("one", linkage="internal")]),
             two: facts(p2, two, [node("two", linkage="internal", source_file="two.c")])}
    separated = build_entity_index(index_request("scope", local), local, {one: p1, two: p2})
    assert len(separated["entities"]) == 2
    conflict = {one: facts(p1, one, [node("a")]),
                two: facts(p2, two, [{**node("b", source_file="two.c"), "canonical_type": "long"}])}
    conflicting = build_entity_index(index_request("scope", conflict), conflict, {one: p1, two: p2})
    assert {item["resolution"] for item in conflicting["entities"]} == {"conflict"}
    limited = build_entity_index(index_request("scope", local, entity_groups=1), local, {one: p1, two: p2})
    assert limited["status"] == "partial" and limited["counts"]["groups"]["failed"] == 1


def test_entity_index_rejects_stale_or_incomplete_scope(tmp_path):
    p = profile(tmp_path)
    key = "a" * 64
    fact_map = {key: facts(p, key, [node("n")])}
    request = index_request("scope", fact_map)
    request["dependencies"][0]["digest"] = "0" * 64
    with pytest.raises(AnalysisError, match="dependencies"):
        build_entity_index(request, fact_map, {key: p})
    with pytest.raises(AnalysisError, match="exactly match"):
        build_entity_index(index_request("scope", fact_map), {}, {})


def test_binding_and_overlay_resolve_exact_object(tmp_path):
    p = profile(tmp_path)
    key, artifact = "a" * 64, "b" * 64
    fact_map = {key: facts(p, key, [node("n", source_file=str(tmp_path / "unit.c"))])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {artifact: module(artifact, str(tmp_path / "unit.c"))}
    ir = {artifact: llvm_facts(artifact, p, key)}
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules, ir),
                                      index, fact_map, modules, ir)
    assert binding["entity_bindings"][0]["resolution"] == "exact"
    overlay = build_overlay("scope", index, binding)
    result = resolve_artifact_object(overlay, artifact, "global:flag")
    assert result["status"] == "resolved"
    assert result["program_object_id"] == overlay["mappings"][0]["program_object_id"]


def test_overlay_preserves_exact_cross_tu_declaration_and_definition_set(tmp_path):
    p1, p2 = profile(tmp_path, "one.c"), profile(tmp_path, "two.c")
    one, two, first, second = "1" * 64, "2" * 64, "a" * 64, "b" * 64
    declaration = node("decl", definition=False, definition_kind="declaration",
                       source_file=str(tmp_path / "one.c"))
    definition = node("def", source_file=str(tmp_path / "two.c"))
    fact_map = {one: facts(p1, one, [declaration]), two: facts(p2, two, [definition])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {one: p1, two: p2})
    modules = {first: module(first, str(tmp_path / "one.c")),
               second: module(second, str(tmp_path / "two.c"))}
    modules[first]["globals"][0]["declaration"] = True
    ir = {first: llvm_facts(first, p1, one), second: llvm_facts(second, p2, two)}
    ir[first]["symbols"][0]["definition"] = False
    ir[first]["semantic_digest"] = semantic_digest(ir[first])
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules, ir),
                                      index, fact_map, modules, ir)
    overlay = build_overlay("scope", index, binding)
    assert overlay["mappings"][0]["resolution"] == "exact"
    assert len(overlay["mappings"][0]["artifact_objects"]) == 2
    assert resolve_artifact_object(overlay, first, "global:flag")["status"] == "resolved"


def test_overlay_deduplicates_targets_and_accepts_definition_role_only_fan_in(tmp_path):
    p = profile(tmp_path)
    key, artifact = "a" * 64, "b" * 64
    fact_map = {key: facts(p, key, [node("n", source_file=str(tmp_path / "unit.c"))])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {artifact: module(artifact, str(tmp_path / "unit.c"))}
    ir = {artifact: llvm_facts(artifact, p, key)}
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules, ir),
                                      index, fact_map, modules, ir)
    original = binding["entity_bindings"][0]
    original["resolution"] = "candidate"
    original["opposed"] = ["definition-role-mismatch"]
    original["reason"] = "non-unique-or-incomplete-evidence"
    duplicate = deepcopy(original)
    duplicate["id"] = identity({"duplicate-binding": original["id"]})
    duplicate["source_id"] = "header-declaration"
    empty_declaration = deepcopy(original)
    empty_declaration.update(
        id=identity({"empty-declaration-binding": original["id"]}),
        source_id="unused-header-declaration", resolution="unresolved", targets=[],
        cardinality="zero", evidence=[], opposed=["missing-ir-symbol"])
    binding["entity_bindings"] = sorted(
        [original, duplicate, empty_declaration], key=lambda item: item["id"])
    binding["semantic_digest"] = semantic_digest(binding)
    validate_source_document(binding, "SourceIRBinding")

    overlay = build_overlay("scope", index, binding)
    mapping = overlay["mappings"][0]
    assert mapping["resolution"] == "exact"
    assert len(mapping["artifact_objects"]) == 1
    assert len(mapping["binding_ids"]) == 3


def test_entity_index_excludes_only_modeled_system_external_boundaries(tmp_path):
    p = profile(tmp_path)
    key = "a" * 64
    pthread = node("pthread", name="pthread_create", definition=False,
                   definition_kind="declaration", kind="function",
                   source_file="/usr/include/pthread.h")
    unknown = node("vendor", name="vendor_hook", definition=False,
                   definition_kind="declaration", kind="function",
                   source_file="/usr/include/vendor.h")
    fact_map = {key: facts(p, key, [node("flag"), pthread, unknown])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})

    names = {item["key"]["symbol"] for item in index["entities"]}
    assert "usr:pthread_create" not in names
    assert "usr:vendor_hook" in names
    assert index["counts"]["external_boundaries"]["emitted"] == 1
    assert any(item["code"] == "modeled-external-entity" for item in index["diagnostics"])
    assert any(item["code"] == "entity-unresolved" for item in index["frontier"])


def test_binding_requires_typed_profile_abi_evidence_for_exact(tmp_path):
    p = profile(tmp_path)
    key, artifact = "a" * 64, "b" * 64
    fact_map = {key: facts(p, key, [node("n", source_file=str(tmp_path / "unit.c"))])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {artifact: module(artifact, str(tmp_path / "unit.c"))}
    legacy = build_source_ir_binding(binding_request("scope", index, fact_map, modules),
                                     index, fact_map, modules)
    assert legacy["entity_bindings"][0]["resolution"] == "candidate"
    assert legacy["entity_bindings"][0]["opposed"] == ["missing-llvm-binding-facts"]
    incompatible = llvm_facts(artifact, p, key)
    incompatible["symbols"][0]["abi"]["size_bits"] = 64
    incompatible["semantic_digest"] = semantic_digest(incompatible)
    ir = {artifact: incompatible}
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules, ir),
                                      index, fact_map, modules, ir)
    assert binding["entity_bindings"][0]["resolution"] == "candidate"
    assert "object-type-abi-mismatch" in binding["entity_bindings"][0]["opposed"]


def test_binding_degrades_without_location_and_never_creates_order_edges(tmp_path):
    p = profile(tmp_path)
    key, artifact = "a" * 64, "b" * 64
    relation = {"id": "r", "kind": "atomic-c-rmw", "from": "expr", "to": "n",
                "source": {"spelling": {"file": "elsewhere.c", "line": 9, "column": 1}},
                "status": "candidate", "reason": None}
    expression = node("expr", name="", definition=False, linkage="none", kind="reference-expression")
    fact_map = {key: facts(p, key, [expression, node("n")], [relation])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {artifact: module(artifact)}
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules), index, fact_map, modules)
    assert binding["expression_bindings"][0]["resolution"] == "unresolved"
    assert binding["expression_bindings"][0]["program_entity_id"] == index["entities"][0]["id"]
    assert "missing-debug-location" in binding["expression_bindings"][0]["opposed"]
    assert not any(key in json.dumps(binding).lower() for key in ('"hb"', '"sw"', '"rf"', '"sb"'))


def test_binding_rejects_stale_modules_and_preserves_duplicate_dependency_ids(tmp_path):
    p = profile(tmp_path)
    key = "a" * 64
    fact_map = {key: facts(p, key, [node("n", source_file=str(tmp_path / "unit.c"))])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {key: module(key, str(tmp_path / "unit.c"))}
    request = binding_request("scope", index, fact_map, modules)
    binding = build_source_ir_binding(request, index, fact_map, modules)
    assert len(binding["dependencies"]) == 3
    request["module_facts"][0]["digest"] = "0" * 64
    with pytest.raises(AnalysisError, match="dependencies"):
        build_source_ir_binding(request, index, fact_map, modules)


def test_binding_and_overlay_budget_frontiers_are_counted(tmp_path):
    p = profile(tmp_path)
    key, artifact = "a" * 64, "b" * 64
    fact_map = {key: facts(p, key, [node("a", name="a"), node("b", name="b")])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {artifact: module(artifact, symbols=("a", "b"))}
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules,
                                                       binding_candidates=1), index, fact_map, modules)
    assert binding["status"] == "partial" and binding["counts"]["bindings"]["failed"] == 1
    full = build_source_ir_binding(binding_request("scope", index, fact_map, modules), index, fact_map, modules)
    overlay = build_overlay("scope", index, full, item_budget=1)
    assert overlay["status"] == "partial" and overlay["counts"]["objects"]["failed"] == 1


def test_overlay_rejects_scope_mismatch_and_ambiguous_reverse_lookup(tmp_path):
    p = profile(tmp_path)
    key = "a" * 64
    fact_map = {key: facts(p, key, [node("n")])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {}
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules), index, fact_map, modules)
    with pytest.raises(AnalysisError, match="different explicit scopes"):
        build_overlay("other", index, binding)
    overlay = build_overlay("scope", index, binding)
    assert resolve_artifact_object(overlay, "x", "y")["status"] == "unresolved"


def test_cache_cold_warm_stale_corruption_and_collision(tmp_path):
    cache = SourceEvidenceCache(tmp_path / "cache")
    p = profile(tmp_path)
    key = "a" * 64
    value = facts(p, key, [node("n")])
    digest = cache_key("facts", {"profile": p["profile_id"]})
    assert cache.load("facts", digest, "SourceSemanticFacts") is None
    path = cache.publish("facts", digest, value)
    assert cache.load("facts", digest, "SourceSemanticFacts") == value
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid source evidence cache"):
        cache.load("facts", digest, "SourceSemanticFacts")
    path.unlink()
    cache.publish("facts", digest, value)
    other = dict(value)
    other["status"] = "partial"
    other["semantic_digest"] = semantic_digest(other)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("facts", digest, other)


def test_worker_protocol_transport_and_identity(tmp_path):
    p = profile(tmp_path)
    physical = "a" * 64
    request = source_document("SourceSemanticRequest", profile=p, physical_tu_id=physical,
                              source_path=p["source"]["path"], budgets=budgets())
    value = facts(p, physical, [node("n")])

    def runner(argv, cwd, **kwargs):
        if "--source-analysis-protocol" in argv:
            return {"status": "completed", "stdout": json.dumps(expected_source_protocol()), "stderr": ""}
        return {"status": "completed", "stdout": json.dumps(value), "stderr": ""}

    assert check_source_worker("worker", tmp_path, runner=runner)["protocol_version"] == 2
    assert analyze_source(request, "worker", tmp_path, runner=runner)["physical_tu_id"] == physical
    assert not list(tmp_path.glob("source-request-*.json"))


@pytest.mark.parametrize("result, match", [
    ({"status": "timed_out", "code": "timeout", "stderr": "late"}, "failed"),
    ({"status": "completed", "stdout": "not-json", "stderr": ""}, "Invalid source worker JSON"),
])
def test_worker_rejects_failure_and_corrupt_output(tmp_path, result, match):
    p = profile(tmp_path)
    request = source_document("SourceSemanticRequest", profile=p, physical_tu_id="a" * 64,
                              source_path=p["source"]["path"], budgets=budgets())

    def runner(argv, cwd, **kwargs):
        if "--source-analysis-protocol" in argv:
            return {"status": "completed", "stdout": json.dumps(expected_source_protocol()), "stderr": ""}
        return result

    with pytest.raises(AnalysisError, match=match):
        analyze_source(request, "worker", tmp_path, runner=runner)


def test_worker_rejects_protocol_and_result_identity(tmp_path):
    with pytest.raises(AnalysisError, match="mismatch"):
        check_source_worker("worker", tmp_path,
                            runner=lambda *args, **kwargs: {"status": "completed", "stdout": "{}"})
    p = profile(tmp_path)
    request = source_document("SourceSemanticRequest", profile=p, physical_tu_id="a" * 64,
                              source_path=p["source"]["path"], budgets=budgets())
    wrong = facts(p, "b" * 64, [node("n")])

    def runner(argv, cwd, **kwargs):
        payload = expected_source_protocol() if "--source-analysis-protocol" in argv else wrong
        return {"status": "completed", "stdout": json.dumps(payload), "stderr": ""}

    with pytest.raises(AnalysisError, match="does not match"):
        analyze_source(request, "worker", tmp_path, runner=runner)


def test_report_status_and_cache_do_not_change_semantic_digest():
    layer = {"status": "complete", "counts": counts(1)}
    report = source_document(
        "AstAssistedAnalysisReport", scope_id="scope", status="complete", exit_code=0,
        dependencies=[], layers={"source": layer}, outputs=[], cache={"hits": 0, "misses": 1},
        diagnostics=[], frontier=[], semantic_digest=None)
    changed = dict(report)
    changed["cache"] = {"hits": 1, "misses": 0}
    assert semantic_digest(changed) == report["semantic_digest"]
    changed["status"] = "failed"
    changed["semantic_digest"] = semantic_digest(changed)
    with pytest.raises(AnalysisError, match="exit zero"):
        validate_source_document(changed, "AstAssistedAnalysisReport")


def _refresh(value):
    value["semantic_digest"] = semantic_digest(value)
    return value


def test_protocol_and_document_loader_reject_corrupt_inputs(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        expected_source_protocol(broken)
    malformed_schema = tmp_path / "schema.json"
    malformed_schema.write_text("{}", encoding="utf-8")
    import memory_order_analyzer.source_contracts as contracts_module
    original = contracts_module.SCHEMA
    contracts_module.SCHEMA = malformed_schema
    try:
        with pytest.raises(AnalysisError, match="budget schema"):
            expected_source_protocol()
    finally:
        contracts_module.SCHEMA = original
    protocol = json.loads(expected_source_protocol.__defaults__[0].read_text(encoding="utf-8"))
    protocol["analysis_version"] = "future"
    mismatch = tmp_path / "mismatch.json"
    mismatch.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(AnalysisError, match="does not match"):
        expected_source_protocol(mismatch)
    with pytest.raises(AnalysisError, match="Unknown"):
        validate_source_document({}, "Unknown")
    with pytest.raises(AnalysisError, match="Expected kind"):
        validate_source_document({"schema_version": 1, "kind": "wrong"}, "SourceSemanticRequest")


def test_semantic_validators_reject_duplicate_and_inconsistent_evidence(tmp_path):
    p = profile(tmp_path)
    key = "a" * 64
    base = facts(p, key, [node("a"), node("b", name="b")])
    duplicate = deepcopy(base)
    duplicate["nodes"][1]["id"] = "a"
    duplicate["nodes"][1]["canonical_decl"] = "a"
    _refresh(duplicate)
    with pytest.raises(AnalysisError, match="unique and sorted"):
        validate_source_document(duplicate, "SourceSemanticFacts")
    relation = {"id": "r", "kind": "read", "from": "missing", "to": None,
                "source": {}, "status": "unknown", "reason": "missing"}
    dangling = deepcopy(base)
    dangling["relations"] = [relation]
    _refresh(dangling)
    with pytest.raises(AnalysisError, match="dangling endpoint"):
        validate_source_document(dangling, "SourceSemanticFacts")

    fact_map = {key: base}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    bad_index = deepcopy(index)
    bad_index["entities"][0]["declarations"] += bad_index["entities"][0]["declarations"]
    _refresh(bad_index)
    with pytest.raises(AnalysisError, match="declarations"):
        validate_source_document(bad_index, "ProgramEntityIndex")
    no_definition = deepcopy(index)
    no_definition["entities"][0]["definitions"] = []
    _refresh(no_definition)
    with pytest.raises(AnalysisError, match="requires a definition"):
        validate_source_document(no_definition, "ProgramEntityIndex")
    ambiguous = deepcopy(index)
    ambiguous["entities"][0].update(resolution="ambiguous", candidates=[])
    _refresh(ambiguous)
    with pytest.raises(AnalysisError, match="requires candidates"):
        validate_source_document(ambiguous, "ProgramEntityIndex")


def test_binding_overlay_slice_and_report_invariants(tmp_path):
    p = profile(tmp_path)
    key, artifact = "a" * 64, "b" * 64
    fact_map = {key: facts(p, key, [node("n", source_file=str(tmp_path / "unit.c"))])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {artifact: module(artifact, str(tmp_path / "unit.c"))}
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules), index, fact_map, modules)
    bad = deepcopy(binding)
    bad["entity_bindings"][0]["cardinality"] = "one-to-many"
    _refresh(bad)
    with pytest.raises(AnalysisError, match="cardinality"):
        validate_source_document(bad, "SourceIRBinding")
    bad = deepcopy(binding)
    bad["entity_bindings"][0].update(resolution="exact", targets=[])
    bad["entity_bindings"][0]["cardinality"] = "zero"
    _refresh(bad)
    with pytest.raises(AnalysisError, match="exactly one"):
        validate_source_document(bad, "SourceIRBinding")
    bad = deepcopy(binding)
    bad["expression_bindings"] = [deepcopy(bad["entity_bindings"][0])]
    _refresh(bad)
    with pytest.raises(AnalysisError, match="overlap"):
        validate_source_document(bad, "SourceIRBinding")

    overlay_value = build_overlay("scope", index, binding)
    bad_overlay = deepcopy(overlay_value)
    bad_overlay["mappings"][0]["artifact_objects"] += [
        {"artifact_key": "0", "id": "x", "kind": "global"}]
    _refresh(bad_overlay)
    with pytest.raises(AnalysisError, match="sorted"):
        validate_source_document(bad_overlay, "CanonicalObjectOverlay")

    slice_item = {"id": "c", "status": "complete", "artifacts": ["b", "a"],
                  "program_objects": [], "source_report_digest": "0" * 64, "missing": []}
    slices = source_document("AstAssistedCandidateSlices", scope_id="scope", status="complete",
                             dependencies=[], slices=[], counts={"candidates": counts(0)},
                             diagnostics=[], frontier=[], semantic_digest=None)
    slices["slices"] = [slice_item]
    _refresh(slices)
    with pytest.raises(AnalysisError, match="members"):
        validate_source_document(slices, "AstAssistedCandidateSlices")
    slice_item["artifacts"] = ["a", "b"]
    slice_item["status"] = "partial"
    _refresh(slices)
    with pytest.raises(AnalysisError, match="status"):
        validate_source_document(slices, "AstAssistedCandidateSlices")

    for status, exit_code in (("partial", 1), ("failed", 2)):
        report = source_document("AstAssistedAnalysisReport", scope_id="scope", status="complete",
                                 exit_code=0, dependencies=[], layers={}, outputs=[],
                                 cache={"hits": 0, "misses": 0}, diagnostics=[], frontier=[],
                                 semantic_digest=None)
        report.update(status=status, exit_code=exit_code)
        _refresh(report)
        with pytest.raises(AnalysisError, match="exit code"):
            validate_source_document(report, "AstAssistedAnalysisReport")


def test_profile_path_argv_command_and_missing_source_validation(tmp_path):
    source = tmp_path / "unit.cpp"
    source.write_text("int x;", encoding="utf-8")
    value = build_profile({"directory": str(tmp_path), "file": source.name,
                           "command": "clang++ -g0 -c unit.cpp"}, compiler_version="21")
    assert value["standard"] == "compiler-default" and value["debug"] is False
    assert value["dialect"] == "compiler-default"
    assert value["standard_source"] == "compiler-default"
    assert value["standard_option"] is None
    with pytest.raises(AnalysisError, match="does not exist"):
        build_profile({"directory": str(tmp_path), "file": "missing.c",
                       "arguments": ["clang", "missing.c"]}, compiler_version="21")
    invalid = deepcopy(value)
    invalid["argv_digest"] = "0" * 64
    payload = {k: v for k, v in invalid.items()
               if k not in {"schema_version", "kind", "analysis_version", "policy_id", "profile_id"}}
    invalid["profile_id"] = identity(payload)
    with pytest.raises(AnalysisError, match="argv digest"):
        validate_source_document(invalid, "CompilationProfileIdentity")


def test_cache_stale_dependencies_escape_and_publish_races(tmp_path, monkeypatch):
    cache = SourceEvidenceCache(tmp_path / "cache")
    with pytest.raises(AnalysisError, match="escapes"):
        cache.load("facts", "../../../outside", "SourceSemanticFacts")
    p = profile(tmp_path)
    value = facts(p, "a" * 64, [node("n")])
    key = "race"

    def same_race(source, destination):
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        raise FileExistsError

    monkeypatch.setattr(source_cache_module.os, "link", same_race)
    assert cache.publish("facts", key, value).is_file()
    dependency_value = source_document("ProgramEntityIndex", scope_id="scope", status="complete",
                                       dependencies=[], entities=[], counts={"groups": counts(0)},
                                       diagnostics=[], frontier=[], semantic_digest=None)
    cache.publish("index", "stale", dependency_value)
    with pytest.raises(AnalysisError, match="stale"):
        cache.load("index", "stale", "ProgramEntityIndex",
                   dependencies=[dependency("x", "y", {})])

    def conflict_race(source, destination):
        destination.write_text("{}", encoding="utf-8")
        raise FileExistsError

    monkeypatch.setattr(source_cache_module.os, "link", conflict_race)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("facts", "conflict", value)


def test_entity_resolution_variants_and_profile_conflict(tmp_path):
    p1 = profile(tmp_path, "one.c")
    p2 = profile(tmp_path, "two.c")
    one, two = "1" * 64, "2" * 64

    def build(left, right):
        values = {one: facts(p1, one, [left]), two: facts(p2, two, [right])}
        return build_entity_index(index_request("scope", values), values, {one: p1, two: p2})

    unresolved_map = {one: facts(p1, one, [node("decl", definition=False)])}
    unresolved = build_entity_index(index_request("scope", unresolved_map), unresolved_map, {one: p1})
    assert unresolved["entities"][0]["resolution"] == "unresolved"
    tentative = build(node("a", definition_kind="tentative"),
                      node("b", definition_kind="tentative", source_file="two.c"))
    assert tentative["entities"][0]["resolution"] == "resolved"
    weak = build(node("a", definition_kind="weak"),
                 node("b", definition_kind="weak", source_file="two.c"))
    assert weak["entities"][0]["resolution"] == "ambiguous"
    strong = build(node("a"), node("b", source_file="two.c"))
    assert strong["entities"][0]["resolution"] == "conflict"
    one_inline = node("a", definition_kind="inline", kind="function")
    two_inline = node("b", definition_kind="inline", kind="function", source_file="two.c")
    one_inline["attributes"] = ["definition-sha256:" + "a" * 64]
    two_inline["attributes"] = ["definition-sha256:" + "a" * 64]
    assert build(one_inline, two_inline)["entities"][0]["resolution"] == "resolved"
    two_inline["attributes"] = ["definition-sha256:" + "b" * 64]
    assert build(one_inline, two_inline)["entities"][0]["reason"] == "odr-definition-mismatch"

    p2_conflict = deepcopy(p2)
    payload = {k: v for k, v in p2_conflict.items()
               if k not in {"schema_version", "kind", "analysis_version", "policy_id", "profile_id"}}
    payload["target"] = "aarch64-linux-gnu"
    p2_conflict["target"] = payload["target"]
    p2_conflict["profile_id"] = identity(payload)
    profile_values = {one: facts(p1, one, [node("a")]),
                      two: facts(p2_conflict, two, [node("b", source_file="two.c")])}
    profile_result = build_entity_index(index_request("scope", profile_values), profile_values,
                                        {one: p1, two: p2_conflict})
    assert profile_result["entities"][0]["reason"] == "incompatible-profiles"

    invalid = {one: facts(p1, one, [node("n")])}
    invalid[one]["profile_id"] = "0" * 64
    _refresh(invalid[one])
    with pytest.raises(AnalysisError, match="profile"):
        build_entity_index(index_request("scope", invalid), invalid, {one: p1})

    ignored = {one: facts(p1, one, [node("p", kind="parameter", definition=False,
                                           linkage="none")])}
    result = build_entity_index(index_request("scope", ignored), ignored, {one: p1})
    assert result["entities"] == [] and result["status"] == "complete"


def test_binding_event_candidates_ambiguity_scope_and_expression_budget(tmp_path):
    p = profile(tmp_path)
    key, first, second = "a" * 64, "b" * 64, "c" * 64
    source_file = str(tmp_path / "unit.c")
    relation = {"id": "r", "kind": "read", "from": "expr", "to": "n",
                "source": {"location": {"file": source_file, "line": 1, "column": 5}},
                "status": "candidate", "reason": None}
    expression = node("expr", name="", definition=False, linkage="none",
                      kind="reference-expression", source_file=source_file)
    fact_map = {key: facts(p, key, [expression, node("n", source_file=source_file)], [relation])}
    index = build_entity_index(index_request("scope", fact_map), fact_map, {key: p})
    modules = {first: module(first, source_file), second: module(second, source_file)}
    binding = build_source_ir_binding(binding_request("scope", index, fact_map, modules),
                                      index, fact_map, modules)
    assert binding["entity_bindings"][0]["resolution"] == "ambiguous"
    assert binding["expression_bindings"][0]["cardinality"] == "one-to-many"

    wrong_scope = binding_request("other", index, fact_map, modules)
    with pytest.raises(AnalysisError, match="different scopes"):
        build_source_ir_binding(wrong_scope, index, fact_map, modules)
    stale = binding_request("scope", index, fact_map, modules)
    stale["entity_index"]["id"] = "other"
    with pytest.raises(AnalysisError, match="digest changed"):
        build_source_ir_binding(stale, index, fact_map, modules)

    # One entity candidate consumes the budget; the expression remains in the denominator.
    one_module = {first: module(first, source_file)}
    limited = build_source_ir_binding(binding_request("scope", index, fact_map, one_module,
                                                       binding_candidates=1),
                                      index, fact_map, one_module)
    assert limited["status"] == "partial"
    assert limited["counts"]["bindings"]["failed"] == 1


def test_worker_accepts_digestless_output_and_protocol_parse_errors(tmp_path):
    p = profile(tmp_path)
    physical = "a" * 64
    request = source_document("SourceSemanticRequest", profile=p, physical_tu_id=physical,
                              source_path=p["source"]["path"], budgets=budgets())
    value = facts(p, physical, [node("n")])
    value.pop("semantic_digest")

    def runner(argv, cwd, **kwargs):
        if "--source-analysis-protocol" in argv:
            return {"status": "completed", "stdout": json.dumps(expected_source_protocol()), "stderr": ""}
        return {"status": "completed", "stdout": json.dumps(value), "stderr": ""}

    result = analyze_source(request, "worker", tmp_path, runner=runner)
    assert result["semantic_digest"] == semantic_digest(result)
    with pytest.raises(AnalysisError, match="mismatch"):
        check_source_worker("worker", tmp_path,
                            runner=lambda *args, **kwargs: {"status": "completed"})


def test_ir_binding_worker_transport_digest_and_identity(tmp_path):
    p = profile(tmp_path)
    bitcode = tmp_path / "unit.bc"
    bitcode.write_bytes(b"llvm fixture")
    artifact, physical = "b" * 64, "a" * 64
    digest = __import__("hashlib").sha256(bitcode.read_bytes()).hexdigest()
    request = source_document(
        "LLVMSourceBindingRequest", artifact_key=artifact, profile_id=p["profile_id"],
        physical_tu_id=physical, bitcode={"path": str(bitcode), "sha256": digest},
        budgets=budgets())
    value = llvm_facts(artifact, p, physical)
    value["bitcode_digest"] = digest
    value["semantic_digest"] = semantic_digest(value)

    def runner(argv, cwd, **kwargs):
        if "--source-analysis-protocol" in argv:
            return {"status": "completed", "stdout": json.dumps(expected_source_protocol()), "stderr": ""}
        return {"status": "completed", "stdout": json.dumps(value), "stderr": ""}

    assert analyze_ir_binding(request, "worker", tmp_path, runner=runner)["artifact_key"] == artifact
    assert not list(tmp_path.glob("ir-binding-request-*.json"))
    def failed(argv, cwd, **kwargs):
        if "--source-analysis-protocol" in argv:
            return {"status": "completed", "stdout": json.dumps(expected_source_protocol()), "stderr": ""}
        return {"status": "failed", "code": "crashed", "stderr": "boom"}
    with pytest.raises(AnalysisError, match="boom"):
        analyze_ir_binding(request, "worker", tmp_path, runner=failed)
    def broken(argv, cwd, **kwargs):
        if "--source-analysis-protocol" in argv:
            return {"status": "completed", "stdout": json.dumps(expected_source_protocol()), "stderr": ""}
        return {"status": "completed", "stdout": "not-json", "stderr": ""}
    with pytest.raises(AnalysisError, match="Invalid LLVM binding worker JSON"):
        analyze_ir_binding(request, "worker", tmp_path, runner=broken)
    foreign = deepcopy(value); foreign["artifact_key"] = "c" * 64
    foreign["semantic_digest"] = semantic_digest(foreign)
    def substituted(argv, cwd, **kwargs):
        if "--source-analysis-protocol" in argv:
            return {"status": "completed", "stdout": json.dumps(expected_source_protocol()), "stderr": ""}
        return {"status": "completed", "stdout": json.dumps(foreign), "stderr": ""}
    with pytest.raises(AnalysisError, match="does not match"):
        analyze_ir_binding(request, "worker", tmp_path, runner=substituted)
    bitcode.write_bytes(b"changed")
    with pytest.raises(AnalysisError, match="missing or changed"):
        analyze_ir_binding(request, "worker", tmp_path, runner=runner)
