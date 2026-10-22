"""Local protocol adversarial tests; no synthetic fixture proves LLVM semantics."""

from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.effect_bounds import bounded_values
from memory_order_analyzer.effect_contracts import effect_document, validate_effect_document
from test_effect_contracts import samples
from test_effect_inputs import inputs
from test_effect_references import references
from test_effect_registry import registry
from test_semantic import graph


def finite(value=None, guards=(), proof=()):
    return dict(state="finite", candidates=[dict(value=value or dict(kind="integer", bits=32, hex="1"),
                                                guards=list(guards), proof=list(proof))], reason=None)


def unknown():
    return dict(state="unknown", candidates=[], reason="not-known")


@pytest.fixture
def evaluation(inputs):
    snapshot, summary = inputs
    local = registry(summary["origins"][0])
    key = local["origin"]["artifact_key"]
    request = samples()["LocalEvaluationRequest"]
    request.update(scope_id=snapshot.scope_id, origins=summary["origins"], arguments=[finite()],
                   local_dependencies=[dict(artifact_key=key, digest=identity(local))])
    def src(name):
        return dict(artifact_key=key, function_id="f", id=name)
    frontier = [dict(code="pending", detail="block not evaluated", source=src("b"), context_id="context")]
    result = samples()["LocalEvaluationResult"]
    result.update(request=request, request_hash=identity(request), scope_id=request["scope_id"],
        values=[dict(source=src("phi"), domain=finite())], blocks=[
            dict(source=src("entry"), state="reachable", proof=[]), dict(source=src("b"), state="pending", proof=[])],
        frontier=frontier, diagnostics=deepcopy(frontier), status="partial", steps=1)
    return snapshot, request, result, {key: local}


def consume(fixture, *, request=None, result=None):
    snapshot, planned, output, locals_ = fixture
    return snapshot.consume_evaluation(request or planned, result or output, local_facts=locals_)


def refresh(fixture):
    snapshot, request, result, locals_ = fixture
    for key, local in locals_.items():
        local["origin"]["facts_hash"] = identity(snapshot.modules[key])
    request["local_dependencies"] = [dict(artifact_key=k, digest=identity(v)) for k, v in locals_.items()]
    request["origins"] = [v["origin"] for v in locals_.values()]
    result["request_hash"] = identity(request)


def test_roundtrip_snapshot_and_explicit_partial_frontier(evaluation, tmp_path):
    snapshot, request, result, locals_ = evaluation
    before = deepcopy(evaluation[1:])
    assert consume(evaluation) == result
    assert snapshot.consume(request, local_facts=locals_) == request
    path = tmp_path / "evaluation.json"
    path.write_text(canonical(result))
    assert snapshot.consume_file(path, "LocalEvaluationResult", local_facts=locals_) == result
    assert evaluation[1:] == before
    substituted = deepcopy(result)
    substituted["request"]["context_id"] = "other"
    substituted["request_hash"] = identity(substituted["request"])
    with pytest.raises(AnalysisError, match="substituted"):
        consume(evaluation, result=substituted)
    for field, replacement in [("request_hash", "e" * 64), ("scope_id", "e" * 64), ("context_id", "other"),
                               ("budgets", {**result["budgets"], "local_steps": 50})]:
        with pytest.raises(AnalysisError):
            consume(evaluation, result={**result, field: replacement})


@pytest.mark.parametrize("change", [
    lambda r: r["function"].update(id="global"),
    lambda r: r["function"].update(function_id="f"),
    lambda r: r.update(invocation_id="missing"),
    lambda r: r.update(context_id="other"),
    lambda r: r.update(arguments=[]),
    lambda r: r.update(arguments=[finite(dict(kind="integer", bits=8, hex="1"))]),
    lambda r: r.update(arguments=[finite(dict(kind="null", address_space=0))]),
    lambda r: r.update(arguments=[dict(state="finite", candidates=[], reason=None)]),
    lambda r: r.update(arguments=[dict(state="bottom", candidates=[], reason=None)]),
    lambda r: r["arguments"][0].update(reason="bad"),
    lambda r: r["arguments"][0]["candidates"][0].update(value=dict(kind="unknown", reason="bad")),
    lambda r: r["arguments"][0]["candidates"].append(deepcopy(r["arguments"][0]["candidates"][0])),
    lambda r: r["local_dependencies"][0].update(digest="e" * 64),
    lambda r: r["local_dependencies"].append(dict(artifact_key="e" * 64, digest="e" * 64)),
    lambda r: r.update(dependencies=[dict(context_id="missing", digest="e" * 64)]),
    lambda r: r["arguments"][0]["candidates"][0].update(proof=[dict(artifact_key="a" * 64, function_id="f", analysis_id="missing")]),
])
def test_invalid_request_domain_identity_and_dependencies(evaluation, change):
    snapshot, request, _, locals_ = evaluation
    change(request)
    with pytest.raises(AnalysisError):
        snapshot.consume(request, local_facts=locals_)


@pytest.mark.parametrize("change", [
    lambda r: r["values"].append(deepcopy(r["values"][0])),
    lambda r: r["values"][0]["source"].update(id="global", function_id=None),
    lambda r: r["values"][0]["source"].update(id="b"),
    lambda r: r["values"][0].update(domain=finite(dict(kind="integer", bits=8, hex="1"))),
    lambda r: r["blocks"][0]["source"].update(id="phi"),
    lambda r: r["blocks"][1].update(state="unreachable"),
    lambda r: r["blocks"].pop(),
    lambda r: r.update(frontier=[]),
    lambda r: r.update(diagnostics=[]),
    lambda r: r.update(status="complete"),
    lambda r: r.update(steps=100001),
    lambda r: r.update(call_requests=[dict(source=r["values"][0]["source"], arguments=[], guards=[])]),
    lambda r: r.update(call_requests=[dict(source={**r["values"][0]["source"], "id": "c"}, arguments=[], guards=[])]),
    lambda r: r.update(returns=[dict(source=r["values"][0]["source"], value=None, guards=[], exit="normal", invocation_id="root-instance")]),
])
def test_invalid_result_roles_plans_and_completeness(evaluation, change):
    change(evaluation[2])
    with pytest.raises(AnalysisError):
        consume(evaluation)


def test_finite_unknown_candidates_guards_and_bound_parameters(evaluation):
    snapshot, request, result, locals_ = evaluation
    source = result["values"][0]["source"]
    parameter = dict(kind="parameter", source={**source, "id": "arg"}, invocation_id="root-instance")
    expression = dict(kind="expression", source=source, invocation_id="root-instance", operands=[parameter])
    guard = dict(source={**source, "id": "entry:i9"}, edge=0, invocation_id="root-instance", multiplicity="single")
    request["arguments"] = [finite(expression, [guard], [next(iter(locals_.values()))["analysis_evidence"][1]["ref"]])]
    refresh(evaluation)
    assert consume(evaluation)
    for replacement in [{**parameter, "invocation_id": None}, {**expression, "source": parameter["source"]},
                        {**expression, "source": {**source, "id": "entry:i0"}}]:
        bad = {**request, "arguments": [finite(replacement)]}
        with pytest.raises(AnalysisError):
            snapshot.consume(bad, local_facts=locals_)
    for patch in [dict(invocation_id="other"), dict(edge=9), dict(source={**source, "id": "arg"})]:
        with pytest.raises(AnalysisError):
            snapshot.consume({**request, "arguments": [finite(parameter, [{**guard, **patch}])]}, local_facts=locals_)
    request["arguments"] = [unknown()]
    refresh(evaluation)
    assert consume(evaluation)
    result["blocks"][1]["state"] = "reachable"
    result.update(frontier=[], diagnostics=[], status="complete")
    with pytest.raises(AnalysisError, match="claimed complete"):
        consume(evaluation)
    request["arguments"] = [finite()]
    refresh(evaluation)
    assert consume(evaluation)
    result["steps"] = 0
    with pytest.raises(AnalysisError):
        consume(evaluation)
    # Candidate limit is on every domain, not the number of root arguments.
    request["arguments"][0]["candidates"] = [finite(dict(kind="integer", bits=32, hex=f"{i:X}"))["candidates"][0] for i in range(9)]
    with pytest.raises(AnalysisError, match="candidate budget"):
        snapshot.consume(request, local_facts=locals_)


def test_ancestor_allocations_are_not_rebound_and_siblings_are_rejected(evaluation):
    snapshot, request, result, locals_ = evaluation
    key = request["function"]["artifact_key"]
    formal = snapshot.modules[key]["values"][0]
    formal.pop("bits")
    formal.update(type="ptr", type_kind="pointer", address_space=0)
    child = {**deepcopy(request["invocations"][0]), "id": "child", "context_id": "child-context", "parent_id": "root-instance",
             "callsite": dict(artifact_key=key, function_id="f", id="c")}
    request["invocations"].append(child)
    request.update(invocation_id="child", context_id="child-context")
    object_ = dict(kind="object", source=next(iter(locals_.values()))["objects"][0]["source"], offset="0", address_space=0,
                   allocation=dict(invocation_id="root-instance", cardinality="single", reason=None))
    request["arguments"] = [finite(object_)]
    refresh(evaluation)
    validated = snapshot.consume(request, local_facts=locals_)
    assert validated["arguments"][0]["candidates"][0]["value"]["allocation"]["invocation_id"] == "root-instance"
    for arg in [dict(kind="null", address_space=0), {**object_, "source": dict(artifact_key=key, function_id=None, id="global"), "allocation": None}]:
        assert snapshot.consume({**request, "arguments": [finite(arg)]}, local_facts=locals_)
    with pytest.raises(AnalysisError, match="pointer type"):
        snapshot.consume({**request, "arguments": [finite({**object_, "address_space": 1})]}, local_facts=locals_)
    formal.update(type="ptr addrspace(1)", address_space=1)
    refresh(evaluation)
    assert snapshot.consume({**request, "arguments": [finite(dict(kind="null", address_space=1))]}, local_facts=locals_)
    request["invocations"].append({**child, "id": "sibling"})
    with pytest.raises(AnalysisError, match="non-ancestor"):
        snapshot.consume(request, local_facts=locals_)


def test_pending_calls_and_exit_roles(evaluation):
    snapshot, request, result, locals_ = evaluation
    source = result["values"][0]["source"]
    call = {**source, "id": "c"}
    result["call_requests"] = [dict(source=call, arguments=[finite(), unknown()], guards=[])]
    with pytest.raises(AnalysisError, match="frontier"):
        consume(evaluation)
    result["frontier"].append(dict(code="callee_pending", detail="waiting", source=call, context_id="context"))
    assert consume(evaluation)
    local = next(iter(locals_.values()))
    # Registered original exit required; a random source reference is insufficient.
    local["ir_nodes"].append(dict(source={**source, "id": "b:i2"}, block={**source, "id": "b"}, opcode="ret", type="void"))
    result["returns"] = [dict(source={**source, "id": "b:i2"}, value=None, guards=[], exit="normal", invocation_id="root-instance")]
    refresh(evaluation)
    assert consume(evaluation)
    result["returns"][0]["invocation_id"] = "foreign"
    with pytest.raises(AnalysisError):
        consume(evaluation)


def test_adoption_shape_is_not_eligibility_proof(evaluation):
    snapshot, request, _, locals_ = evaluation
    key = request["function"]["artifact_key"]
    adoption = dict(call=dict(artifact_key=key, function_id="f", id="c"), target=None,
                    kind="unknown", reason="unresolved", assumptions=[])
    request["adoptions"] = [adoption]
    assert snapshot.consume(request, local_facts=locals_)
    for replacement in [{**adoption, "target": request["function"]}, {**adoption, "kind": "unique-definition"},
                        {**adoption, "call": {**adoption["call"], "id": "phi"}}]:
        with pytest.raises(AnalysisError):
            snapshot.consume({**request, "adoptions": [replacement]}, local_facts=locals_)
    with pytest.raises(AnalysisError, match="Duplicate evaluation adoption"):
        snapshot.consume({**request, "adoptions": [adoption, adoption]}, local_facts=locals_)
    adoption.update(kind="unique-definition", target=request["function"])
    with pytest.raises(AnalysisError, match="direct call"):
        snapshot.consume(request, local_facts=locals_)
    snapshot.modules[key]["calls"][0].update(kind="direct", target="f")
    refresh(evaluation)
    assert snapshot.consume(request, local_facts=locals_)


def test_expression_tree_limits_precede_recursive_operations():
    request = samples()["LocalEvaluationRequest"]
    source = dict(artifact_key="a" * 64, function_id="f", id="phi")
    expression = dict(kind="integer", bits=32, hex="1")
    for _ in range(63):
        expression = dict(kind="expression", source=source, invocation_id="root-instance", operands=[expression])
    request["arguments"] = [finite(expression)]
    assert validate_effect_document(request, "LocalEvaluationRequest")
    expression["operands"] = [deepcopy(expression)]
    with pytest.raises(AnalysisError, match="budget"):
        validate_effect_document(request, "LocalEvaluationRequest")
    cyc = {}
    cyc["cycle"] = cyc
    with pytest.raises(AnalysisError, match="Cyclic"):
        bounded_values(cyc)
    for data in [None, {"budgets": []}, {"budgets": {"local_steps": True}}, {"kind": []}]:
        assert bounded_values(data) == []
    request["arguments"] = [finite()]
    request["budgets"]["local_steps"] = 1
    assert validate_effect_document(request, "LocalEvaluationRequest")
    request["arguments"].append(finite())
    with pytest.raises(AnalysisError, match="budget"):
        validate_effect_document(request, "LocalEvaluationRequest")
    request["arguments"] = [finite(dict(kind="expression", source=source, invocation_id="i", operands=[42]))]
    request["budgets"]["local_steps"] = 100000
    with pytest.raises(AnalysisError):
        validate_effect_document(request, "LocalEvaluationRequest")
    nested = {}
    for _ in range(258):
        nested = {"extra": nested}
    with pytest.raises(AnalysisError, match="nested"):
        bounded_values(nested)


def test_call_bindings_select_an_explicit_matching_dependency(evaluation, inputs):
    snapshot, request, _, locals_ = evaluation
    summary = inputs[1]
    key = request["function"]["artifact_key"]
    snapshot.modules[key]["calls"][0].update(kind="direct", target="f")
    refresh(evaluation)
    summary["origins"] = deepcopy(request["origins"])
    summary["resolutions"] = []
    call = dict(artifact_key=key, function_id="f", id="c")
    request["adoptions"] = [dict(call=call, target=request["function"], kind="unique-definition", reason="test", assumptions=[])]
    request["dependencies"] = [dict(context_id="context", digest=identity(summary))]
    request["call_bindings"] = [dict(source=call, context_id="context")]
    assert snapshot.consume(request, summaries={"context": summary}, local_facts=locals_)
    for patch in [dict(call_bindings=request["call_bindings"] * 2),
                  dict(call_bindings=[dict(source=call, context_id="absent")]), dict(adoptions=[]),
                  dict(adoptions=[dict(call=call, target=None, kind="unknown", reason="unknown", assumptions=[])])]:
        with pytest.raises(AnalysisError):
            snapshot.consume({**request, **patch}, summaries={"context": summary}, local_facts=locals_)
    # Missing/stale dependencies are errors, even when the call binding looks valid.
    with pytest.raises(AnalysisError):
        snapshot.consume(request, local_facts=locals_)
    summary["status"] = "not_run"
    with pytest.raises(AnalysisError, match="dependency mismatch"):
        snapshot.consume(request, summaries={"context": summary}, local_facts=locals_)
    snapshot.modules[key]["functions"].append({**deepcopy(snapshot.modules[key]["functions"][0]),
        "id": "other-function", "name": "other-function", "parameters": [], "blocks": []})
    refresh(evaluation)
    summary.update(origins=deepcopy(request["origins"]), effects=[], root=dict(artifact_key=key, function_id="other-function", arguments=[]))
    summary["invocations"][0]["function"]["id"] = "other-function"
    # This is a valid summary, but it belongs to the wrong adopted function.
    assert snapshot.consume(summary, local_facts=locals_)
    request["dependencies"][0]["digest"] = identity(summary)
    with pytest.raises(AnalysisError, match="target mismatch"):
        snapshot.consume(request, summaries={"context": summary}, local_facts=locals_)


def test_result_payloads_and_effect_budget(evaluation, inputs):
    snapshot, request, result, locals_ = evaluation
    summary = inputs[1]
    result["effects"] = deepcopy(summary["effects"])
    result["resolutions"] = deepcopy(summary["resolutions"])
    assert consume(evaluation)
    bad = deepcopy(result)
    bad["resolutions"][0]["context_id"] = "foreign"
    with pytest.raises(AnalysisError, match="output context"):
        consume(evaluation, result=bad)
    # An owned instruction used as a resolution remains bound to this activation.
    key = request["function"]["artifact_key"]
    source = result["values"][0]["source"]
    snapshot.modules[key]["extraction"]["diagnostics"].append(dict(id="phi", reason="unit_reason"))
    snapshot.modules[key]["extraction"]["unknown"] += 1
    refresh(evaluation)
    result["resolutions"] = [dict(facts_hash=identity(snapshot.modules[key]), source=source, reason="unit_reason", context_id="context",
        invocation_id="root-instance", rule="unit-rule", evidence=[source], status="explained")]
    # Preserve the P1 diagnostic denominator when extending the synthetic fixture.
    assert consume(evaluation)
    request["budgets"]["effect_items"] = 1
    result["budgets"] = request["budgets"]
    next(iter(locals_.values()))["budgets"] = request["budgets"]
    result["effects"].append({**deepcopy(result["effects"][0]), "id": "second"})
    refresh(evaluation)
    with pytest.raises(AnalysisError, match="effect budget"):
        consume(evaluation)


def test_unreachable_proof_and_non_raw_result_value(evaluation):
    _, _, result, locals_ = evaluation
    local = next(iter(locals_.values()))
    result["blocks"][1].update(state="unreachable", proof=[local["analysis_evidence"][2]["ref"]])
    result.update(frontier=[], diagnostics=[], status="complete")
    # This checks evidence identity, NOT the truth of the reachability claim.
    assert consume(evaluation)
    result["values"][0].update(source=local["ir_nodes"][2]["source"])
    assert consume(evaluation)
    result["values"][0]["domain"] = unknown()
    with pytest.raises(AnalysisError, match="claimed complete"):
        consume(evaluation)
