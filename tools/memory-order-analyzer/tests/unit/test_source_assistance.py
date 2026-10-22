from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.effect_adoption import derive_adoptions
from memory_order_analyzer.publication_graph import _object_key as publication_object_key
from memory_order_analyzer.source_assistance import (
    ast_sequence_edges,
    canonical_object_key,
    load_source_assistance,
    relevant_dependency_slice,
    resolve_event_object,
    resolve_function,
    resolve_object,
)
from memory_order_analyzer.source_contracts import counts, dependency, source_document
from memory_order_analyzer.thread_graph import _object_range as thread_object_range


A, B, C = "a" * 64, "b" * 64, "c" * 64


def binding():
    entity = "entity:function"
    targets = [
        {"artifact_key": A, "id": "f-decl", "name": "f", "kind": "function",
         "linkage": "external", "declaration": True, "comdat": False},
        {"artifact_key": B, "id": "f", "name": "f", "kind": "function",
         "linkage": "external", "declaration": False, "comdat": False},
    ]
    items = []
    for ordinal, target in enumerate(targets):
        items.append({"id": f"binding:{ordinal}", "source_id": f"source:{ordinal}",
                      "program_entity_id": entity, "resolution": "exact", "targets": [target],
                      "cardinality": "one-to-one", "evidence": ["symbol-name"],
                      "opposed": [], "reason": None})
    return source_document("SourceIRBinding", scope_id="scope", status="complete",
                           dependencies=[], entity_bindings=items, expression_bindings=[],
                           counts={"bindings": counts(2)}, diagnostics=[], frontier=[],
                           semantic_digest=None)


def overlay():
    mapping = {"program_object_id": "program:flag", "program_entity_id": "entity:flag",
               "resolution": "exact",
               "artifact_objects": [
                   {"artifact_key": A, "id": "flag", "kind": "global"},
                   {"artifact_key": B, "id": "flag", "kind": "global"}],
               "source_nodes": ["source:flag"], "binding_ids": ["binding:flag"],
               "evidence": ["symbol-name"]}
    return source_document("CanonicalObjectOverlay", scope_id="scope", status="complete",
                           dependencies=[], mappings=[mapping], counts={"objects": counts(1)},
                           diagnostics=[], frontier=[], semantic_digest=None)


def report(binding_value, overlay_value):
    return source_document(
        "AstAssistedAnalysisReport", scope_id="scope", status="complete", exit_code=0,
        dependencies=[], layers={"downstream_consumption": {"status": "not_run", "counts": counts(0)}},
        outputs=sorted([dependency("SourceIRBinding", "scope", binding_value),
                        dependency("CanonicalObjectOverlay", "scope", overlay_value)],
                       key=lambda item: item["kind"]),
        cache={"hits": 0, "misses": 2}, diagnostics=[], frontier=[], semantic_digest=None)


def bundle():
    binding_value, overlay_value = binding(), overlay()
    return {"binding": binding_value, "overlay": overlay_value,
            "report": report(binding_value, overlay_value)}


def test_load_source_assistance_checks_scope_and_output_digests(tmp_path):
    values = bundle()
    for name, value in (("source-ir-binding.json", values["binding"]),
                        ("canonical-object-overlay.json", values["overlay"]),
                        ("report.json", values["report"])):
        (tmp_path / name).write_text(canonical(value), encoding="utf-8")
    loaded = load_source_assistance(tmp_path, scope_id="scope")
    assert loaded["binding"]["semantic_digest"] == values["binding"]["semantic_digest"]
    with pytest.raises(AnalysisError, match="scope"):
        load_source_assistance(tmp_path, scope_id="other")
    stale = deepcopy(values["report"])
    stale["outputs"][0]["digest"] = "0" * 64
    stale["semantic_digest"] = identity({key: value for key, value in stale.items()
                                         if key not in {"semantic_digest", "cache"}})
    (tmp_path / "report.json").write_text(canonical(stale), encoding="utf-8")
    with pytest.raises(AnalysisError, match="stale"):
        load_source_assistance(tmp_path)

    missing_fact = source_document(
        "SourceSemanticFacts", profile_id=A, physical_tu_id=B, source_digest=C,
        status="complete", nodes=[], relations=[],
        counts={"nodes": counts(0), "relations": counts(0)}, diagnostics=[],
        frontier=[], semantic_digest=None)
    changed_binding = deepcopy(values["binding"])
    changed_binding["dependencies"] = [
        dependency("SourceSemanticFacts", B, missing_fact)]
    changed_binding["semantic_digest"] = identity({
        key: value for key, value in changed_binding.items()
        if key != "semantic_digest"})
    changed_report = report(changed_binding, values["overlay"])
    (tmp_path / "source-ir-binding.json").write_text(
        canonical(changed_binding), encoding="utf-8")
    (tmp_path / "report.json").write_text(canonical(changed_report), encoding="utf-8")
    with pytest.raises(AnalysisError, match="source facts"):
        load_source_assistance(tmp_path)


def test_function_and_object_resolution_are_exact_or_conservative():
    values = bundle()
    resolved = resolve_function(values["binding"], A, "f-decl")
    assert resolved["status"] == "resolved" and resolved["target"] == {
        "artifact_key": B, "function_id": "f"}
    assert resolve_function(values["binding"], A, "missing")["status"] == "unresolved"
    source = {"artifact_key": A, "function_id": None, "id": "flag"}
    assert resolve_object(values["overlay"], source)["program_object_id"] == "program:flag"
    assert resolve_object(values["overlay"], {"artifact_key": C, "id": "flag"})["status"] == "unresolved"
    assert resolve_object(values["overlay"], None)["status"] == "unresolved"
    address = {"kind": "object", "source": source, "address_space": 0,
               "allocation": None, "offset": "0"}
    assert canonical_object_key(values["overlay"], address) == "program:flag"
    assert canonical_object_key(values["overlay"], None) is None
    assert canonical_object_key(values["overlay"], {"kind": "global"}) is None
    assert thread_object_range(address, values["overlay"]) == ("program:flag", "0")
    assert publication_object_key({"object": source, "address_space": 0}, values["overlay"]) == "program:flag"


def test_expression_event_resolves_only_through_one_exact_overlay_entity():
    values = bundle()
    expression = {"id": "expression:flag", "source_id": "relation:flag",
                  "program_entity_id": "entity:flag", "resolution": "candidate",
                  "targets": [{"artifact_key": A, "id": "load", "kind": "load"}],
                  "cardinality": "one-to-one", "evidence": ["source-range"],
                  "opposed": [], "reason": "expression-mapping-is-never-memory-model-proof"}
    values["binding"]["expression_bindings"] = [expression]
    source = {"artifact_key": A, "function_id": "reader", "id": "load"}
    resolved = resolve_event_object(values["binding"], values["overlay"], source)
    assert resolved["status"] == "resolved"
    assert resolved["program_object_id"] == "program:flag"
    assert resolve_event_object(values["binding"], values["overlay"], None)["status"] == "unresolved"
    assert resolve_event_object(
        values["binding"], values["overlay"],
        {"artifact_key": C, "id": "missing"})["status"] == "unresolved"
    other = deepcopy(values["overlay"]["mappings"][0])
    other.update(program_object_id="program:other", program_entity_id="entity:other")
    values["overlay"]["mappings"].append(other)
    second = deepcopy(expression)
    second.update(id="expression:other", program_entity_id="entity:other")
    values["binding"]["expression_bindings"].append(second)
    assert resolve_event_object(values["binding"], values["overlay"], source)["status"] == "ambiguous"


def test_exact_adjacent_statement_sequence_projects_to_same_thread_events(tmp_path):
    source_file = str((tmp_path / "unit.cpp").resolve())
    before_node = {"id": "before", "source": {
        "expansion": {"file": source_file, "line": 1, "column": 10},
        "expansion_end": {"file": source_file, "line": 1, "column": 20}}}
    after_node = {"id": "after", "source": {
        "expansion": {"file": source_file, "line": 1, "column": 30},
        "expansion_end": {"file": source_file, "line": 1, "column": 40}}}
    facts = {"nodes": [before_node, after_node], "relations": [{
        "kind": "sequenced-before", "status": "exact", "from": "before", "to": "after"}]}
    modules = {A: {"events": [
        {"id": "store-flag", "source": {"inline_chain": [
            {"file": source_file, "line": 1, "column": 15}]}},
        {"id": "store-payload", "source": {"inline_chain": [
            {"file": source_file, "line": 1, "column": 35}]}},
    ]}}
    effects = {
        "left": {"id": "left", "thread_instance_id": "thread",
                 "source": {"artifact_key": A, "id": "store-flag"}},
        "right": {"id": "right", "thread_instance_id": "thread",
                  "source": {"artifact_key": A, "id": "store-payload"}},
    }
    assert ast_sequence_edges({"source_facts": [facts]}, modules, effects) == [("left", "right")]
    effects["right"]["thread_instance_id"] = "other"
    assert ast_sequence_edges({"source_facts": [facts]}, modules, effects) == []


def test_ast_sequence_ignores_missing_nodes_paths_and_locations(tmp_path):
    source_file = tmp_path / "relative.cpp"
    source = {
        "expansion": {"file": source_file.name, "directory": str(tmp_path),
                      "line": 2, "column": 1},
        "expansion_end": {"file": source_file.name, "directory": str(tmp_path),
                          "line": 2, "column": 20},
    }
    facts = {"nodes": [{"id": "valid", "source": source}], "relations": [
        {"kind": "sequenced-before", "status": "exact", "from": "missing", "to": "valid"},
        {"kind": "sequenced-before", "status": "exact", "from": "valid", "to": "valid"},
    ]}
    modules = {A: {"events": [
        {"id": "no-file", "source": {"inline_chain": [{"line": 2, "column": 3}]}},
        {"id": "wrong-path", "source": {"inline_chain": [
            {"file": str(tmp_path / "other.cpp"), "line": 2, "column": 3}]}},
        {"id": "relative", "source": {"inline_chain": [
            {"file": source_file.name, "directory": str(tmp_path), "line": 2, "column": 3}]}},
    ]}}
    effects = [
        {"id": "no-file", "thread_instance_id": "thread",
         "source": {"artifact_key": A, "id": "no-file"}},
        {"id": "wrong-path", "thread_instance_id": "thread",
         "source": {"artifact_key": A, "id": "wrong-path"}},
        {"id": "relative", "thread_instance_id": "thread",
         "source": {"artifact_key": A, "id": "relative"}},
    ]
    assert ast_sequence_edges({"source_facts": [facts]}, modules, effects) == []


def test_ambiguous_function_and_object_are_never_selected():
    values = bundle()
    extra = deepcopy(values["binding"]["entity_bindings"][1])
    extra.update(id="binding:extra", source_id="source:extra")
    extra["targets"] = [{**extra["targets"][0], "artifact_key": C, "id": "f2"}]
    values["binding"]["entity_bindings"].append(extra)
    values["binding"]["entity_bindings"].sort(key=lambda item: item["id"])
    values["binding"]["semantic_digest"] = identity({key: value for key, value in values["binding"].items()
                                                       if key != "semantic_digest"})
    assert resolve_function(values["binding"], A, "f-decl")["status"] == "ambiguous"
    second = deepcopy(values["overlay"]["mappings"][0])
    second.update(program_object_id="program:other", program_entity_id="entity:other")
    values["overlay"]["mappings"].append(second)
    assert resolve_object(values["overlay"], {"artifact_key": A, "id": "flag"})["status"] == "ambiguous"
    duplicate_source = deepcopy(values["binding"]["entity_bindings"][0])
    duplicate_source.update(id="binding:foreign", program_entity_id="entity:foreign")
    values["binding"]["entity_bindings"].append(duplicate_source)
    assert resolve_function(values["binding"], A, "f-decl")["status"] == "ambiguous"


def _interface():
    return {"function_type": "i32 ()", "return_type": "i32", "parameter_types": [],
            "calling_convention": 0, "vararg": False, "attributes": [], "status": "supported",
            "nounwind": False, "noreturn": False}


def _local_function(key, identifier):
    return {"source": {"artifact_key": key, "function_id": None, "id": identifier},
            "linkage": "external", "visibility": "default", "dso_local": True,
            "declaration": False, "interposable": False, "exact_definition": True,
            "comdat": None, "selection": None, "interface": _interface(),
            "body_fingerprint": "1" * 64}


def test_p2_adoption_uses_source_binding_only_to_choose_verified_definition():
    call = {"id": "call", "kind": "direct", "target": "f", "function": "caller"}
    function = lambda identifier, declaration=False: {
        "id": identifier, "name": "f", "linkage": "external", "declaration": declaration,
        "comdat": False}
    modules = {
        A: {"functions": [{"id": "caller", "name": "caller", "linkage": "external",
                           "declaration": False, "comdat": False}, function("f-decl", True)],
            "calls": [call]},
        B: {"functions": [function("f")], "calls": []},
        C: {"functions": [function("f2")], "calls": []},
    }
    local = {
        A: {"functions": [_local_function(A, "caller")],
            "calls": [{"source": {"artifact_key": A, "function_id": "caller", "id": "call"},
                       "interface": _interface(), "target": {"artifact_key": A, "function_id": None,
                                                               "id": "f-decl"},
                       "tail": "none", "bundles": []}]},
        B: {"functions": [_local_function(B, "f")], "calls": []},
        C: {"functions": [_local_function(C, "f2")], "calls": []},
    }
    inputs = SimpleNamespace(scope={"members": [A, B, C], "closed": True, "external_boundaries": []},
                             modules=modules)
    assert derive_adoptions(inputs, local)[0]["kind"] == "unknown"
    assisted = derive_adoptions(inputs, local, binding())
    assert assisted[0]["kind"] == "source-verified-definition"
    assert assisted[0]["target"] == {"artifact_key": B, "function_id": None, "id": "f"}


def test_candidate_dependency_slice_and_strict_sidecar_document():
    values = bundle()
    graph = {"effects": [
        {"id": "fw", "source": {"artifact_key": A, "id": "store"}},
        {"id": "fr", "source": {"artifact_key": B, "id": "load"}},
        {"id": "pw", "source": {"artifact_key": A, "id": "payload-store"}},
        {"id": "pr", "source": {"artifact_key": B, "id": "payload-load"}},
    ]}
    protocol = {"id": "candidate", "flag_write": "fw", "flag_read": "fr",
                "payload_write": "pw", "payload_read": "pr",
                "flag_object": "program:flag", "payload_object": "program:payload"}
    result = relevant_dependency_slice(protocol, graph, values)
    assert result["status"] == "partial" and result["missing"] == ["payload-object-binding"]
    item = {"id": protocol["id"], **result}
    document = source_document(
        "AstAssistedCandidateSlices", scope_id="scope", status="partial", dependencies=[],
        slices=[item], counts={"candidates": counts(1, emitted=0, failed=1)},
        diagnostics=[], frontier=[], semantic_digest=None)
    assert document["slices"][0]["source_report_digest"] == identity(values["report"])
    payload_mapping = deepcopy(values["overlay"]["mappings"][0])
    payload_mapping.update(program_object_id="program:payload", program_entity_id="entity:payload")
    values["overlay"]["mappings"].append(payload_mapping)
    complete = relevant_dependency_slice(protocol, graph, values)
    assert complete["status"] == "complete" and complete["missing"] == []
    missing_event = relevant_dependency_slice({**protocol, "payload_read": "absent"}, graph, values)
    assert "thread-effect" in missing_event["missing"]
