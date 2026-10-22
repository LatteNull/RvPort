from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.effect_references import validate_effect_references
from test_effect_contracts import samples
from test_semantic import graph


@pytest.fixture
def references(graph, fixture_artifact):
    key = graph["artifact_key"]
    origin = {**samples()["LocalAnalysisFacts"]["origin"], "facts_hash": identity(graph)}
    source = {"artifact_key": key, "function_id": "f", "id": "e"}
    effect = {"id": "effect", "source": source, "context_id": "context", "invocation_id": "root-instance", "kind": "write",
              "address": {"kind": "parameter", "source": {**source, "id": "arg"}, "invocation_id": "root-instance"}, "size_bytes": "4",
              "value": {"kind": "integer", "bits": 32, "hex": "1"}, "atomic": False, "volatile": False,
              "ordering": None, "failure_ordering": None, "syncscope": None, "visibility": "observable",
              "guards": [{"source": {**source, "id": "entry:i9"}, "edge": 0, "invocation_id": "root-instance", "multiplicity": "single"}], "occurrence": "may",
              "multiplicity": "single", "proof": [], "call_path": []}
    result = samples()["EffectSummary"]
    result.update(origins=[origin], effects=[effect], status="partial", resolutions=[{
        "facts_hash": identity(graph), "source": {"artifact_key": key, "function_id": None, "id": "unknown"},
        "reason": "unsupported_value", "context_id": "context", "invocation_id": "root-instance", "rule": "unit-evidence",
        "evidence": [source], "status": "irrelevant"}])
    result["root"]["arguments"] = [{"kind": "unknown", "reason": "generic-input"}]
    return result, {key: fixture_artifact}, {key: graph}


def test_valid_origins_sources_and_dependency(references):
    value, artifacts, modules = references
    before = deepcopy((value, artifacts, modules))
    assert validate_effect_references(value, artifacts, modules) is value
    assert (value, artifacts, modules) == before
    caller = deepcopy(value)
    caller["dependencies"] = [{"context_id": "context", "digest": identity(value)}]
    validate_effect_references(caller, artifacts, modules, summaries={"context": value})
    local = samples()["LocalAnalysisFacts"]
    local["origin"] = value["origins"][0]
    validate_effect_references(local, artifacts, modules)
    request = samples()["EffectAnalysisRequest"]
    request["roots"] = [value["root"]]
    validate_effect_references(request, artifacts, modules)
    report = samples()["EffectAnalysisReport"]
    report["scope_id"] = value["scope_id"]
    report["summaries"] = [{"context_id": "context", "digest": identity(value)}]
    validate_effect_references(report, artifacts, modules, summaries={"context": value})


@pytest.mark.parametrize("mutate", [
    lambda v: v["origins"].append(deepcopy(v["origins"][0])),
    lambda v: v["origins"][0].update(artifact_key="e" * 64),
    lambda v: v["origins"][0].update(module_hash="e" * 64),
    lambda v: v["origins"][0].update(facts_hash="e" * 64),
    lambda v: v["origins"][0].update(profile="build-faithful"),
    lambda v: v["effects"][0]["source"].update(id="absent"),
    lambda v: v["effects"][0]["source"].update(function_id="other"),
    lambda v: v["effects"][0]["value"].update(bits=1, hex="2"),
    lambda v: v["effects"][0]["guards"][0].update(edge=9),
    lambda v: v["effects"][0]["guards"][0]["source"].update(id="arg"),
    lambda v: v["root"].update(function_id="absent"),
    lambda v: v["root"].update(arguments=[]),
    lambda v: v["resolutions"][0].update(facts_hash="e" * 64),
    lambda v: v["resolutions"][0].update(reason="not-a-diagnostic"),
    lambda v: v["resolutions"][0].update(context_id="other"),
    lambda v: v["effects"].append(deepcopy(v["effects"][0])),
    lambda v: v["effects"][0].update(context_id="other"),
    lambda v: v["effects"][0]["source"].update(id="arg"),
    lambda v: v["effects"][0].update(kind="read"),
    lambda v: v["effects"][0].update(call_path=[v["effects"][0]["source"]]),
    lambda v: v.update(order=[{"before": "effect", "after": "absent", "guards": []}]),
    lambda v: v.update(order=[{"before": "effect", "after": "effect", "guards": []}]),
    lambda v: v.update(dependencies=[{"context_id": "absent", "digest": "e" * 64}]),
    lambda v: v.update(dependencies=[{"context_id": "same", "digest": "e" * 64}] * 2),
])
def test_invalid_derived_reference(references, mutate):
    value, artifacts, modules = references
    mutate(value)
    with pytest.raises(AnalysisError):
        validate_effect_references(value, artifacts, modules)


def test_input_and_dependency_mismatches(references):
    value, artifacts, modules = references
    key = next(iter(modules))
    with pytest.raises(AnalysisError, match="map key"):
        validate_effect_references(value, artifacts, {"e" * 64: modules[key]})
    with pytest.raises(AnalysisError, match="map key"):
        validate_effect_references(value, {"e" * 64: artifacts[key]}, modules)
    bad = deepcopy(artifacts)
    bad[key]["sha256"] = "e" * 64
    with pytest.raises(AnalysisError, match="BC/facts"):
        validate_effect_references(value, bad, modules)
    for change, digest in [({"context_id": "other"}, None), ({"scope_id": "e" * 64}, None), ({}, "e" * 64)]:
        target = {**value, **change}
        caller = {**value, "dependencies": [{"context_id": "context", "digest": digest or identity(target)}]}
        with pytest.raises(AnalysisError):
            validate_effect_references(caller, artifacts, modules, summaries={"context": target})


def test_local_objects_duplicate_sources_and_order_edges(references):
    value, artifacts, modules = references
    key = next(iter(modules))
    slot = deepcopy(modules[key]["values"][0])
    slot.pop("bits")
    slot.update(id="slot", kind="instruction", block="entry", type="ptr", type_kind="pointer",
                address_space=0, details={"opcode": "alloca"})
    modules[key]["values"].append(slot)
    modules[key]["extraction"]["nodes"] += 1
    value["origins"][0]["facts_hash"] = identity(modules[key])
    value["resolutions"][0]["facts_hash"] = identity(modules[key])
    local = samples()["LocalAnalysisFacts"]
    local["origin"] = value["origins"][0]
    local["objects"] = [{"source": {"artifact_key": key, "function_id": "f", "id": "slot"},
        "allocated_type": "i32", "size_bytes": "4", "address_space": 0, "private": True, "reason": None}]
    validate_effect_references(local, artifacts, modules)
    invalid = deepcopy(local)
    invalid["objects"][0]["source"]["id"] = "arg"
    with pytest.raises(AnalysisError, match="not alloca"):
        validate_effect_references(invalid, artifacts, modules)
    local["objects"] *= 2
    with pytest.raises(AnalysisError, match="Duplicate objects"):
        validate_effect_references(local, artifacts, modules)
    value["effects"].append({**deepcopy(value["effects"][0]), "id": "second"})
    value["order"] = [{"before": "effect", "after": "second", "guards": []}]
    validate_effect_references(value, artifacts, modules)
    with pytest.raises(AnalysisError):
        validate_effect_references(None, artifacts, modules)


def test_symbol_node_owner_conflict(references):
    value, artifacts, modules = references
    key = next(iter(modules))
    modules[key]["values"][0]["id"] = "global"
    modules[key]["functions"][0]["parameters"] = ["global"]
    modules[key]["values"][1]["operands"][0] = "global"
    modules[key]["values"][1]["details"]["incoming"][0]["value_ref"] = "global"
    with pytest.raises(AnalysisError, match="Conflicting raw node owner"):
        validate_effect_references(value, artifacts, modules)


def test_sources_need_a_declared_origin(references):
    value, artifacts, modules = references
    key = next(iter(modules))
    other = "d" * 64
    modules[other] = {**modules[key], "artifact_key": other}
    artifacts[other] = {**artifacts[key], "artifact_key": other}
    value["effects"][0]["source"]["artifact_key"] = other
    with pytest.raises(AnalysisError, match="outside declared origins"):
        validate_effect_references(value, artifacts, modules)


def test_root_argument_bindings_and_types(references):
    value, artifacts, modules = references
    request = samples()["EffectAnalysisRequest"]
    request["roots"] = [deepcopy(value["root"])]
    root = request["roots"][0]
    key = root["artifact_key"]
    integer = {"kind": "integer", "bits": 32, "hex": "0"}
    parameter = {"kind": "parameter", "source": {"artifact_key": key, "function_id": "f", "id": "arg"}, "invocation_id": None}
    for argument in [integer, parameter]:
        root["arguments"] = [argument]
        assert validate_effect_references(request, artifacts, modules)
    for argument in [{**integer, "bits": 8}, {**parameter, "invocation_id": "foreign"},
                     {"kind": "expression", "source": parameter["source"], "operands": [], "invocation_id": None},
                     {"kind": "null", "address_space": 0}]:
        root["arguments"] = [argument]
        with pytest.raises(AnalysisError):
            validate_effect_references(request, artifacts, modules)
    formal = modules[key]["values"][0]
    formal.pop("bits")
    formal.update(type="ptr", type_kind="pointer", address_space=0)
    global_object = {"kind": "object", "source": {"artifact_key": key, "function_id": None, "id": "global"},
                     "offset": "0", "address_space": 0, "allocation": None}
    for argument in [{"kind": "null", "address_space": 0}, global_object]:
        root["arguments"] = [argument]
        assert validate_effect_references(request, artifacts, modules)
    for argument in [integer, {**global_object, "address_space": 1},
                     {**global_object, "allocation": {"invocation_id": "foreign", "cardinality": "single", "reason": None}}]:
        root["arguments"] = [argument]
        with pytest.raises(AnalysisError):
            validate_effect_references(request, artifacts, modules)


def test_supplement_source_roles(references):
    value, artifacts, modules = references
    key = next(iter(modules))
    local = samples()["LocalAnalysisFacts"]
    local["origin"] = value["origins"][0]
    interface = dict(function_type="void (i32)", return_type="void", parameter_types=["i32"],
                     calling_convention=0, vararg=False, attributes=[], status="supported", nounwind=False, noreturn=False)
    local["functions"] = [dict(source={"artifact_key": key, "function_id": None, "id": "f"},
        linkage="external", visibility="default", dso_local=True, declaration=False, interposable=False,
        exact_definition=True, comdat=None, selection=None, interface=interface, body_fingerprint=None)]
    local["calls"] = [dict(source={"artifact_key": key, "function_id": "f", "id": "c"},
                           interface=interface, target=None, tail="none", bundles=[])]
    assert validate_effect_references(local, artifacts, modules)
    for category, replacement in [("functions", "global"), ("calls", "e")]:
        bad = deepcopy(local)
        bad[category][0]["source"]["id"] = replacement
        with pytest.raises(AnalysisError, match="Supplement"):
            validate_effect_references(bad, artifacts, modules)


def test_effect_unknown_and_call_path_roles(references):
    value, artifacts, modules = references
    value["effects"][0].update(kind="unknown", call_path=[{**value["effects"][0]["source"], "id": "c"}])
    assert validate_effect_references(value, artifacts, modules)
    key = next(iter(modules))
    modules[key]["events"][0]["kind"] = "llvm.memset.p0.i64"
    value["effects"][0]["kind"] = "write"
    value["origins"][0]["facts_hash"] = value["resolutions"][0]["facts_hash"] = identity(modules[key])
    assert validate_effect_references(value, artifacts, modules)
