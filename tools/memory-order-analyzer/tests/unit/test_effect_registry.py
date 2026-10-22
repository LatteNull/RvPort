"""Independent structural adversarial cases; LLVM query truth is tested in C++."""
from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.effect_references import validate_effect_references
from test_effect_contracts import samples
from test_effect_inputs import inputs
from test_effect_references import references
from test_semantic import graph


def registry(origin):
    key = origin["artifact_key"]
    def src(id_, function="f"):
        return dict(artifact_key=key, function_id=function, id=id_)
    def ref(kind, index):
        return dict(artifact_key=key, function_id="f", analysis_id=f"f:p2:{kind}:{index}")
    def evidence(kind, index, source, inputs=(), result="candidate"):
        return dict(ref=ref(kind, index), kind=kind, source=source, inputs=list(inputs), result=result)
    local = samples()["LocalAnalysisFacts"]
    local.update(origin=origin, status="partial", ir_nodes=[
        dict(source=src("entry:i0"), block=src("entry"), opcode="alloca", type="ptr"),
        dict(source=src("entry:i1"), block=src("entry"), opcode="store", type="void"),
        dict(source=src("b:i0"), block=src("b"), opcode="load", type="i32"),
        dict(source=src("phi"), block=src("b"), opcode="phi", type="i32"),
        dict(source=src("entry:i9"), block=src("entry"), opcode="br", type="void"),
    ], objects=[dict(source=src("entry:i0"), allocated_type="i32", size_bytes="4", address_space=0, private=True, reason=None)],
        analysis_evidence=[
            evidence("memory_live_on_entry", 0, src("f", None)),
            evidence("dominance", 1, src("entry"), result="reachable"),
            evidence("dominance", 2, src("b"), [src("entry")], "reachable"),
            evidence("memory_def", 3, src("entry:i1"), [ref("memory_live_on_entry", 0)]),
            evidence("memory_use", 4, src("b:i0"), [ref("memory_phi", 5)]),
            evidence("memory_phi", 5, src("b"), [src("entry"), ref("memory_def", 3), src("b"), ref("memory_phi", 5)]),
            evidence("aa_clobber", 6, src("b:i0"), [ref("memory_use", 4), ref("memory_phi", 5)]),
        ])
    return local


def test_supplement_and_summary_use_separate_node_namespaces(references):
    summary, artifacts, modules = references
    before = deepcopy(modules)
    local = registry(summary["origins"][0])
    key = local["origin"]["artifact_key"]
    assert validate_effect_references(local, artifacts, modules) is local
    summary["local_dependencies"] = [dict(artifact_key=key, digest=identity(local))]
    summary["effects"][0]["proof"] = [local["analysis_evidence"][-1]["ref"]]
    summary["escape"] = [dict(kind="object", source=local["objects"][0]["source"], offset="0", address_space=0,
                              allocation=dict(invocation_id="root-instance", cardinality="single", reason=None))]
    assert validate_effect_references(summary, artifacts, modules, local_facts={key: local}) is summary
    assert modules == before
    for patch, facts in [({}, {}), ({"local_dependencies": []}, {key: local}),
                         ({"local_dependencies": summary["local_dependencies"] * 2}, {key: local}),
                         ({}, {key: {**local, "status": "not_run"}})]:
        with pytest.raises(AnalysisError):
            validate_effect_references({**summary, **patch}, artifacts, modules, local_facts=facts)
    bad = deepcopy(summary)
    bad["effects"][0]["proof"][0]["function_id"] = "other"
    with pytest.raises(AnalysisError, match="analysis reference"):
        validate_effect_references(bad, artifacts, modules, local_facts={key: local})
    bad = deepcopy(summary)
    ref = bad["effects"][0]["proof"][0]
    ref["id"] = ref.pop("analysis_id")
    with pytest.raises(AnalysisError, match="Dangling source"):
        validate_effect_references(bad, artifacts, modules, local_facts={key: local})
    local["budgets"]["local_steps"] = 100
    summary["local_dependencies"][0]["digest"] = identity(local)
    with pytest.raises(AnalysisError, match="budget"):
        validate_effect_references(summary, artifacts, modules, local_facts={key: local})


@pytest.mark.parametrize("mutate", [
    lambda v: v["ir_nodes"].append(deepcopy(v["ir_nodes"][0])),
    lambda v: v["ir_nodes"][0]["source"].update(artifact_key="e" * 64),
    lambda v: v["ir_nodes"][0]["block"].update(id="missing"),
    lambda v: v["ir_nodes"][0]["block"].update(function_id="other"),
    lambda v: v["ir_nodes"][0]["source"].update(id="f"),
    lambda v: v["ir_nodes"][0]["source"].update(id="entry"),
    lambda v: v["ir_nodes"][0]["source"].update(id="global"),
    lambda v: v["ir_nodes"][0]["source"].update(id="arg"),
    lambda v: v["ir_nodes"][0]["source"].update(id="invented"),
    lambda v: v["ir_nodes"][3].update(opcode="alloca"),
    lambda v: v["ir_nodes"][3].update(type="ptr"),
    lambda v: v["ir_nodes"][4].update(opcode="alloca"),
    lambda v: v["analysis_evidence"].append(deepcopy(v["analysis_evidence"][0])),
    lambda v: v["analysis_evidence"].append({**deepcopy(v["analysis_evidence"][0]), "ref": {**v["analysis_evidence"][0]["ref"], "analysis_id": "f:p2:memory_live_on_entry:99"}}),
    lambda v: v["analysis_evidence"][0]["ref"].update(artifact_key="e" * 64),
    lambda v: v["analysis_evidence"][0]["ref"].update(function_id="other"),
    lambda v: v["analysis_evidence"][0]["ref"].update(analysis_id="entry:i0"),
    lambda v: v["analysis_evidence"][0]["ref"].update(analysis_id="f:p2:madeup:0"),
    lambda v: v["analysis_evidence"][0]["source"].update(id="missing"),
    lambda v: v["analysis_evidence"][0]["source"].update(function_id="f"),
    lambda v: v["analysis_evidence"][0].update(source=v["ir_nodes"][0]["source"]),
    lambda v: v["analysis_evidence"][1].update(source=v["ir_nodes"][0]["source"]),
    lambda v: v["analysis_evidence"][1].update(result="candidate"),
    lambda v: v["analysis_evidence"][2].update(result="unreachable"),
    lambda v: v["analysis_evidence"][2].update(inputs=v["analysis_evidence"][2]["inputs"] * 2),
    lambda v: v["analysis_evidence"][2]["inputs"][0].update(id="b"),
    lambda v: v["analysis_evidence"][2]["inputs"][0].update(id="entry:i0"),
    lambda v: v["analysis_evidence"][2]["inputs"][0].update(function_id="other"),
    lambda v: v["analysis_evidence"][2]["inputs"][0].update(id="global"),
    lambda v: v["analysis_evidence"][3]["inputs"][0].update(analysis_id="missing"),
    lambda v: v["analysis_evidence"][3].update(result="reachable"),
    lambda v: v["analysis_evidence"][3].update(inputs=[]),
    lambda v: v["analysis_evidence"][3].update(inputs=[v["ir_nodes"][0]["source"]]),
    lambda v: v["analysis_evidence"][3].update(source=v["ir_nodes"][0]["block"]),
    lambda v: v["analysis_evidence"][3].update(source=v["ir_nodes"][0]["source"]),
    lambda v: v["analysis_evidence"][3].update(inputs=[v["analysis_evidence"][1]["ref"]]),
    lambda v: v["analysis_evidence"][5].update(inputs=[]),
    lambda v: v["analysis_evidence"][5].update(inputs=v["analysis_evidence"][5]["inputs"][:3]),
    lambda v: v["analysis_evidence"][5]["inputs"][0].update(id="entry:i0"),
    lambda v: v["analysis_evidence"][5].update(source=v["ir_nodes"][0]["block"]),
    lambda v: v["analysis_evidence"][6]["inputs"].reverse(),
    lambda v: v["budgets"].update(local_steps=1),
])
def test_invalid_registry_is_rejected(references, mutate):
    summary, artifacts, modules = references
    local = registry(summary["origins"][0])
    mutate(local)
    with pytest.raises(AnalysisError):
        validate_effect_references(local, artifacts, modules)


def test_local_dependency_consumption_checks_closure_and_disk(inputs, tmp_path):
    snapshot, summary = inputs
    key = next(iter(snapshot.modules))
    local = registry(summary["origins"][0])
    summary["local_dependencies"] = [dict(artifact_key=key, digest=identity(local))]
    path = tmp_path / "summary.json"
    path.write_text(canonical(summary))
    assert snapshot.consume_file(path, "EffectSummary", local_facts={key: local}) == summary
    with pytest.raises(AnalysisError, match="map key"):
        snapshot.consume(summary, local_facts={"e" * 64: local})
    invalid = deepcopy(local)
    invalid["ir_nodes"][0]["source"]["id"] = "missing"
    with pytest.raises(AnalysisError):
        snapshot.consume({**summary, "local_dependencies": []}, local_facts={key: invalid})


def test_registered_memory_and_call_opcodes_must_match_raw_roles(references):
    summary, artifacts, modules = references
    key = next(iter(modules))
    module = modules[key]
    module["events"][0]["id"] = "b:i1"
    module["calls"][0]["id"] = "b:i2"
    local = registry({**summary["origins"][0], "facts_hash": identity(module)})
    for id_, opcode in [("b:i1", "store"), ("b:i2", "call")]:
        src = dict(artifact_key=key, function_id="f", id=id_)
        local["ir_nodes"].append(dict(source=src, block={**src, "id": "b"}, opcode=opcode, type="void"))
    assert validate_effect_references(local, artifacts, modules)
    for index in [-1, -2]:
        bad = deepcopy(local)
        bad["ir_nodes"][index]["opcode"] = "alloca"
        with pytest.raises(AnalysisError, match="Conflicting"):
            validate_effect_references(bad, artifacts, modules)


def test_analysis_ownership_and_origin_cannot_be_bypassed(references):
    summary, artifacts, modules = references
    key = next(iter(modules))
    modules[key]["functions"].append(dict(id="decl", name="decl", linkage="external", declaration=True,
                                         comdat=False, parameters=[], return_type="void", vararg=False, blocks=[]))
    local = registry({**summary["origins"][0], "facts_hash": identity(modules[key])})
    bad = deepcopy(local)
    bad["analysis_evidence"][0]["ref"]["function_id"] = "decl"
    with pytest.raises(AnalysisError, match="declaration"):
        validate_effect_references(bad, artifacts, modules)
    bad = deepcopy(local)
    bad["analysis_evidence"][1]["source"] = dict(artifact_key=key, function_id=None, id="decl")
    with pytest.raises(AnalysisError, match="Cross-function"):
        validate_effect_references(bad, artifacts, modules)
    bad = deepcopy(local)
    bad["analysis_evidence"][0]["ref"]["function_id"] = "decl"
    bad["analysis_evidence"][0]["source"]["id"] = "decl"
    # Incoming evidence cannot lie about the actual owner even if its ID exists.
    modules[key]["functions"][-1]["declaration"] = False
    bad["origin"]["facts_hash"] = identity(modules[key])
    bad["analysis_evidence"][0]["ref"]["analysis_id"] = "decl:p2:memory_live_on_entry:0"
    bad["analysis_evidence"][3]["inputs"][0]["analysis_id"] = "decl:p2:memory_live_on_entry:0"
    with pytest.raises(AnalysisError, match="input owner"):
        validate_effect_references(bad, artifacts, modules)

    # A valid supplement from another member is not automatically an origin of this summary.
    other = "e" * 64
    modules[other] = {**deepcopy(modules[key]), "artifact_key": other}
    artifacts[other] = {**deepcopy(artifacts[key]), "artifact_key": other}
    local = registry({**summary["origins"][0], "artifact_key": other, "facts_hash": identity(modules[other])})
    summary["origins"][0]["facts_hash"] = summary["resolutions"][0]["facts_hash"] = identity(modules[key])
    summary["local_dependencies"] = [dict(artifact_key=other, digest=identity(local))]
    summary["effects"][0]["proof"] = [local["analysis_evidence"][-1]["ref"]]
    with pytest.raises(AnalysisError, match="outside declared origins"):
        validate_effect_references(summary, artifacts, modules, local_facts={other: local})
