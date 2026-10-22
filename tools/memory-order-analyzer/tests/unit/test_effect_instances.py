"""Activation identity tests deliberately do not claim LLVM alias proofs."""

from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.effect_instances import (
    guards_exclusive, invocation, rebind_payload, singleton_allocation, validate_instances,
)
from memory_order_analyzer.effect_references import validate_effect_references
from test_effect_references import references
from test_semantic import graph


def allocation(value, *, cardinality="single", reason=None):
    src = value["effects"][0]["source"]
    return dict(kind="object", source={**src, "id": "slot"}, offset="0", address_space=0,
                allocation=dict(invocation_id="root-instance", cardinality=cardinality, reason=reason))


@pytest.fixture
def allocated(references):
    value, artifacts, modules = references
    module = next(iter(modules.values()))
    slot = deepcopy(module["values"][0])
    slot.pop("bits")
    slot.update(id="slot", kind="instruction", block="entry", type_kind="pointer", address_space=0,
                type="ptr", operands=[], details={"opcode": "alloca"})
    module["values"].append(slot)
    module["extraction"]["nodes"] += 1
    value["origins"][0]["facts_hash"] = identity(module)
    value["resolutions"][0]["facts_hash"] = identity(module)
    value["effects"][0]["address"] = allocation(value)
    value["returns"] = [{"source": {**value["effects"][0]["source"], "id": "entry:i9"},
                         "invocation_id": "root-instance", "value": None, "guards": [], "exit": "unknown"}]
    validate_effect_references(value, artifacts, modules)
    return value, artifacts, modules


def child(value, **changes):
    entry = {**deepcopy(value["invocations"][0]), "id": "child", "parent_id": "root-instance",
             "callsite": {**value["effects"][0]["source"], "id": "c"}}
    return {**entry, **changes}


def test_stable_contexts_distinct_calls_and_roots(references):
    value, _, _ = references
    fn = value["invocations"][0]["function"]
    first = invocation("shared-context", fn, root_key="root")
    assert first == invocation("shared-context", fn, root_key="root")
    assert first["id"] != invocation("shared-context", fn, root_key="other")["id"]
    call = value["effects"][0]["source"]
    a = invocation("callee-context", fn, root_key="root", parent=first["id"], callsite=call)
    b = invocation("callee-context", fn, root_key="root", parent=first["id"], callsite={**call, "id": "call2"})
    assert a["id"] != b["id"] and a["context_id"] == b["context_id"]
    assert fn == value["invocations"][0]["function"]
    assert invocation("c", fn, root_key="root", cardinality="merged", reason="scc")["reason"] == "scc"
    for patch in [dict(cardinality="bad"), dict(reason="why"), dict(cardinality="merged"),
                  dict(parent="parent"), dict(callsite=call)]:
        with pytest.raises(AnalysisError):
            invocation("c", fn, root_key="root", **patch)


def test_valid_objects_invocations_and_caller_owned_pointers(allocated):
    value, artifacts, modules = allocated
    value["invocations"].append(child(value))
    value["effects"][0]["invocation_id"] = "child"
    # The callee effect still addresses the caller's allocation.
    assert validate_effect_references(value, artifacts, modules) is value
    table = validate_instances(value, modules)
    assert singleton_allocation(value["effects"][0]["address"], table)
    value["escape"] = [dict(kind="object", source={"artifact_key": next(iter(modules)),
                      "function_id": None, "id": "global"}, offset="0", address_space=0, allocation=None)]
    assert validate_effect_references(value, artifacts, modules)
    value["effects"][0]["address"]["allocation"].update(cardinality="merged", reason="loop-alloca")
    value["diagnostics"] = [{"code": "instance_merge", "detail": "loop-alloca", "source": None, "context_id": "context"}]
    assert validate_effect_references(value, artifacts, modules)
    assert not singleton_allocation(value["effects"][0]["address"], table)


@pytest.mark.parametrize("mutate", [
    lambda v: v["invocations"].append(deepcopy(v["invocations"][0])),
    lambda v: v["budgets"].update(contexts_per_request=1),
    lambda v: v.update(root_invocation_id="missing"),
    lambda v: v["invocations"][0]["function"].update(id="bad"),
    lambda v: v["invocations"][0].update(context_id="other"),
    lambda v: v["invocations"][0].update(parent_id="child"),
    lambda v: v["invocations"][1].update(parent_id="child"),
    lambda v: v["invocations"][1].update(parent_id="missing"),
    lambda v: v["invocations"][1].update(callsite=None),
    lambda v: v["invocations"][1]["callsite"].update(id="e"),
    lambda v: v["invocations"][1]["callsite"].update(function_id="other"),
    lambda v: v["invocations"][1]["function"].update(id="absent"),
    lambda v: v["invocations"][1].update(reason="spurious"),
    lambda v: v["invocations"][0].update(cardinality="merged", reason="scc"),
    lambda v: v["effects"][0].update(invocation_id="missing"),
    lambda v: v["effects"][0]["guards"][0].update(invocation_id="missing"),
    lambda v: v["effects"][0]["address"].update(allocation=None),
    lambda v: v["effects"][0]["address"]["source"].update(id="arg"),
    lambda v: v["effects"][0]["address"]["allocation"].update(reason="spurious"),
    lambda v: v["effects"][0]["address"]["allocation"].update(invocation_id="missing"),
    lambda v: v["effects"][0].update(address={"kind": "parameter", "source": v["effects"][0]["source"], "invocation_id": "root-instance"}),
    lambda v: v["effects"][0].update(address={"kind": "parameter", "source": {**v["effects"][0]["source"], "id": "slot"}, "invocation_id": "root-instance"}),
    lambda v: v["effects"][0].update(address={"kind": "object", "source": {"artifact_key": "a" * 64, "function_id": None, "id": "f"}, "offset": "0", "address_space": 0, "allocation": None}),
])
def test_invalid_instance_bindings(allocated, mutate):
    value, artifacts, modules = allocated
    value["invocations"].append(child(value))
    mutate(value)
    with pytest.raises(AnalysisError):
        validate_effect_references(value, artifacts, modules)


def test_merged_activation_must_not_improve_precision(allocated):
    value, artifacts, modules = allocated
    entry = value["invocations"][0]
    entry.update(cardinality="merged", reason="scc")
    value["diagnostics"] = [{"code": "instance_merge", "detail": "scc", "source": None, "context_id": "context"}]
    with pytest.raises(AnalysisError, match="single guard"):
        validate_effect_references(value, artifacts, modules)
    value["effects"][0]["guards"][0]["multiplicity"] = "unknown"
    with pytest.raises(AnalysisError, match="Allocation is more precise"):
        validate_effect_references(value, artifacts, modules)
    value["effects"][0]["address"]["allocation"].update(cardinality="merged", reason="scc")
    with pytest.raises(AnalysisError, match="cannot prove"):
        validate_effect_references(value, artifacts, modules)
    value["effects"][0]["multiplicity"] = "unknown"
    assert validate_effect_references(value, artifacts, modules)
    for changes in [dict(status="complete"), dict(diagnostics=[])]:
        with pytest.raises(AnalysisError, match="partial evidence"):
            validate_effect_references({**value, **changes}, artifacts, modules)
    value["invocations"].append(child(value, cardinality="unknown", reason="budget"))
    assert validate_effect_references(value, artifacts, modules)


def test_guard_exclusivity_requires_same_singleton_activation(references):
    value, _, modules = references
    table = validate_instances(value, modules)
    guard = value["effects"][0]["guards"][0]
    other = {**guard, "edge": 1}
    assert guards_exclusive(guard, other, table)
    assert not guards_exclusive(guard, guard, table)
    assert not guards_exclusive(guard, {**other, "invocation_id": "child"}, table)
    assert not guards_exclusive(guard, {**other, "source": {**guard["source"], "id": "other"}}, table)
    assert not guards_exclusive(guard, other, {})
    for multiplicity in ("repeated", "unknown"):
        assert not guards_exclusive({**guard, "multiplicity": multiplicity}, other, table)
        assert not guards_exclusive(guard, {**other, "multiplicity": multiplicity}, table)
    for cardinality in ("merged", "unknown"):
        table["root-instance"]["cardinality"] = cardinality
        assert not guards_exclusive(guard, other, table)


def test_template_rebinding_preserves_raw_and_caller_identity(allocated):
    value, _, modules = allocated
    raw = deepcopy(value)
    payload = deepcopy({name: value[name] for name in ("effects", "returns", "escape", "resolutions")})
    payload["order"] = [{"before": "effect", "after": "caller-effect", "guards": []}]
    # An argument already belonging to a caller is not template-local.
    payload["escape"] = [{**allocation(value), "allocation": {
        "invocation_id": "caller", "cardinality": "single", "reason": None}}]
    entry = child(value, cardinality="unknown", reason="budget")
    rebound = rebind_payload(payload, {"root-instance": entry})
    effect = rebound["effects"][0]
    assert effect["invocation_id"] == "child"
    assert effect["id"] != "effect"
    assert rebound["order"][0] == {"before": effect["id"], "after": "caller-effect", "guards": []}
    assert effect["address"]["allocation"] == {"invocation_id": "child", "cardinality": "unknown", "reason": "budget"}
    assert effect["source"] == raw["effects"][0]["source"]
    assert effect["guards"][0]["invocation_id"] == "child"
    assert effect["guards"][0]["multiplicity"] == "unknown"
    assert effect["occurrence"] == "may" and effect["multiplicity"] == "unknown"
    assert rebound["returns"][0]["invocation_id"] == "child"
    assert rebound["resolutions"][0]["invocation_id"] == "child"
    assert rebound["escape"][0]["allocation"]["invocation_id"] == "caller"
    assert value == raw
    assert rebind_payload(payload, {}) == payload
    single = rebind_payload(payload, {"root-instance": child(value)})
    assert single["effects"][0]["multiplicity"] == "single"
    other = rebind_payload(payload, {"root-instance": child(value, id="other-child")})
    assert other["effects"][0]["id"] != single["effects"][0]["id"]
    payload["effects"][0]["address"]["allocation"].update(cardinality="unknown", reason="prior-loss")
    merged = rebind_payload(payload, {"root-instance": child(value, cardinality="merged", reason="scc")})
    assert merged["effects"][0]["address"]["allocation"]["cardinality"] == "unknown"
    table = validate_instances(value, modules)
    assert not singleton_allocation({"kind": "unknown"}, table)
    assert not singleton_allocation({**allocation(value), "allocation": None}, table)
    assert not singleton_allocation(allocation(value), {})
    table["root-instance"]["cardinality"] = "merged"
    assert not singleton_allocation(allocation(value), table)
