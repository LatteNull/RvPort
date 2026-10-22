"""Parameterised summaries, instance rebinding, SCC convergence and widening."""

from copy import deepcopy

from .contracts import AnalysisError, canonical, identity
from .effect_contracts import effect_document
from .effect_instances import invocation, rebind_payload


def finite(value, proof=()):
    return {"state": "finite", "candidates": [{"value": deepcopy(value), "guards": [],
                                                  "proof": list(proof)}], "reason": None}


def unknown(reason):
    return {"state": "unknown", "candidates": [], "reason": reason}


def public_arguments(domains):
    result = []
    for domain in domains:
        candidates = domain.get("candidates", [])
        if domain.get("state") == "finite" and len(candidates) == 1:
            value = deepcopy(candidates[0]["value"])
            if value.get("kind") == "parameter":
                value["invocation_id"] = None
            result.append(value)
        else:
            result.append({"kind": "unknown", "reason": domain.get("reason") or "multiple_candidates"})
    return result


def context_id(scope_id, function, domains, budgets):
    return identity({"scope": scope_id, "function": function, "arguments": domains,
                     "budgets": budgets, "analysis": "0.1.0", "policy": "scoped-effects-v1"})


def make_request(inputs, function, domains, local_facts, budgets, adoptions):
    key, fn = function["artifact_key"], function["id"]
    context = context_id(inputs.scope_id, function, domains, budgets)
    root = invocation(context, function, root_key=context)
    domains = deepcopy(domains)
    pending = [domains]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("kind") == "parameter":
                item["invocation_id"] = root["id"]
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    origins = [{"artifact_key": member, "module_hash": inputs.artifacts[member]["sha256"],
                "facts_hash": identity(inputs.modules[member]),
                "extractor_version": inputs.modules[member]["protocol"]["extractor_version"],
                "llvm_version": inputs.modules[member]["protocol"]["llvm_version"],
                "profile": inputs.artifacts[member]["profile"]}
               for member in sorted(inputs.scope["members"])]
    selected = [deepcopy(item) for item in adoptions if
                item["call"]["artifact_key"] == key and item["call"]["function_id"] == fn]
    return effect_document("LocalEvaluationRequest", scope_id=inputs.scope_id, context_id=context,
        function=deepcopy(function), invocation_id=root["id"], invocations=[root], origins=origins,
        arguments=domains, adoptions=selected, dependencies=[], call_bindings=[],
        local_dependencies=[{"artifact_key": member, "digest": identity(local_facts[member])}
                            for member in sorted(inputs.scope["members"])], budgets=budgets)


def _remap_effect_ids(effects, order, context):
    mapping = {item["id"]: identity({"context": context, "effect": item["id"],
                                     "invocation": item["invocation_id"]}) for item in effects}
    for item in effects:
        item["id"] = mapping[item["id"]]
    for item in order:
        item["before"], item["after"] = mapping[item["before"]], mapping[item["after"]]


def summary_from_result(result):
    request = result["request"]
    known_calls = {canonical(item["call"]) for item in request["adoptions"] if item["kind"] != "unknown"}
    removed = {item["id"] for item in result["effects"] if
               item["kind"] == "unknown" and canonical(item["source"]) in known_calls}
    effects = [deepcopy(item) for item in result["effects"] if item["id"] not in removed]
    order = [deepcopy(item) for item in result["order"] if item["before"] not in removed and item["after"] not in removed]
    _remap_effect_ids(effects, order, request["context_id"])
    diagnostics = [deepcopy(item) for item in result["diagnostics"] if not
                   (item["code"] == "unknown_call_effect" and item["source"] and
                    canonical(item["source"]) in known_calls)]
    if known_calls and not [item for item in diagnostics if item["code"] not in {"block_pending", "local_evaluation_pending"}]:
        diagnostics = [item for item in diagnostics if item["code"] != "block_pending"]
    unresolved = [item for item in diagnostics if item["code"] not in {"local_evaluation_pending"}]
    status = "complete" if result["status"] == "complete" or not unresolved else "partial"
    function = request["function"]
    root = {"artifact_key": function["artifact_key"], "function_id": function["id"],
            "arguments": public_arguments(request["arguments"])}
    return effect_document("EffectSummary", scope_id=request["scope_id"], context_id=request["context_id"],
        root=root, root_invocation_id=request["invocation_id"], invocations=deepcopy(request["invocations"]),
        origins=deepcopy(request["origins"]), budgets=deepcopy(request["budgets"]), effects=effects,
        order=order, returns=deepcopy(result["returns"]), escape=deepcopy(result["escape"]),
        adoptions=deepcopy(request["adoptions"]), dependencies=[],
        local_dependencies=deepcopy(request["local_dependencies"]),
        resolutions=deepcopy(result["resolutions"]), diagnostics=diagnostics, status=status)


def instantiate_child(child, parent_invocation, callsite, root_key, cardinality="single", reason=None,
                      arguments=None):
    """Rebind a reusable summary tree to a distinct abstract call instance."""
    replacements = {}
    for old in child["invocations"]:
        parent = parent_invocation if old["id"] == child["root_invocation_id"] else replacements[old["parent_id"]]["id"]
        site = callsite if old["id"] == child["root_invocation_id"] else old["callsite"]
        replacements[old["id"]] = invocation(old["context_id"], old["function"], root_key=root_key,
            parent=parent, callsite=site, cardinality=cardinality if old["id"] == child["root_invocation_id"] else old["cardinality"],
            reason=reason if old["id"] == child["root_invocation_id"] else old["reason"])
    rebound = rebind_payload({name: child[name] for name in
        ("effects", "order", "returns", "escape", "resolutions")}, replacements)
    # A foreign argument denotes caller-owned storage.  Template evaluation
    # temporarily binds it to the callee activation for validation; publishing
    # restores the caller activation rather than transferring ownership.
    actuals = {}
    if arguments:
        for formal, domain in zip(child["root"]["arguments"], arguments):
            if formal.get("kind") == "parameter":
                candidates = domain.get("candidates", [])
                actuals[formal["source"]["id"]] = (deepcopy(candidates[0]["value"])
                    if domain.get("state") == "finite" and len(candidates) == 1
                    else {"kind": "unknown", "reason": domain.get("reason") or "multiple_candidates"})
    pending = [rebound]
    child_function = child["root"]["function_id"]
    child_artifact = child["root"]["artifact_key"]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("kind") == "parameter" and item["source"]["id"] in actuals:
                formal_id = item["source"]["id"]
                item.clear(); item.update(deepcopy(actuals[formal_id]))
            elif (item.get("kind") == "parameter" and
                (item["source"]["artifact_key"], item["source"]["function_id"]) !=
                    (child_artifact, child_function)):
                item["invocation_id"] = parent_invocation
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return replacements, rebound


def compose(parent, child, callsite, arguments=None):
    parent = deepcopy(parent)
    root_key = parent["root_invocation_id"]
    replacements, rebound = instantiate_child(child, parent["root_invocation_id"], callsite, root_key,
                                                arguments=arguments)
    parent["invocations"].extend(replacements[item["id"]] for item in child["invocations"])
    for name in ("effects", "order", "escape", "resolutions"):
        parent[name].extend(rebound[name])
    dependency = {"context_id": child["context_id"], "digest": identity(child)}
    if dependency not in parent["dependencies"]:
        parent["dependencies"].append(dependency)
    for item in child["local_dependencies"]:
        if item not in parent["local_dependencies"]:
            parent["local_dependencies"].append(deepcopy(item))
    parent["diagnostics"].extend(deepcopy(child["diagnostics"]))
    if child["status"] != "complete":
        parent["status"] = "partial"
    return effect_document("EffectSummary", **{key: value for key, value in parent.items()
                                                if key not in {"schema_version", "kind", "analysis_version", "policy_id"}})


def strongly_connected(graph):
    """Deterministic Tarjan components used by scheduling and cache identities."""
    index, stack, active, indices, low, result = 0, [], set(), {}, {}, []
    def visit(node):
        nonlocal index
        indices[node] = low[node] = index; index += 1; stack.append(node); active.add(node)
        for target in sorted(graph.get(node, ())):
            if target not in indices:
                visit(target); low[node] = min(low[node], low[target])
            elif target in active:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component = []
            while True:
                value = stack.pop(); active.remove(value); component.append(value)
                if value == node:
                    break
            result.append(tuple(sorted(component)))
    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return result


def fixed_point(graph, seeds, transfer, iterations):
    """Monotone set fixed point; non-convergence is explicit, never empty complete."""
    values = {node: set(seeds.get(node, ())) for node in graph}
    for turn in range(iterations):
        changed = False
        for component in strongly_connected(graph):
            for node in component:
                produced = set(transfer(node, values))
                merged = values[node] | produced
                changed |= merged != values[node]
                values[node] = merged
        if not changed:
            return values, True, turn + 1
    return values, False, iterations


def conservative_widen(summary, source, code="recursive_budget"):
    summary = deepcopy(summary)
    diagnostic = {"code": code, "detail": "recursive or context budget retained an unknown effect frontier",
                  "source": deepcopy(source), "context_id": summary["context_id"]}
    summary["effects"].append({"id": identity(diagnostic), "source": deepcopy(source),
        "context_id": summary["context_id"], "invocation_id": summary["root_invocation_id"],
        "kind": "unknown", "address": None, "size_bytes": None, "value": None,
        "atomic": False, "volatile": False, "ordering": None, "failure_ordering": None,
        "syncscope": None, "visibility": "unknown", "guards": [], "occurrence": "may",
        "multiplicity": "unknown", "proof": [], "call_path": [deepcopy(source)]})
    summary["diagnostics"].append(diagnostic); summary["status"] = "partial"
    return effect_document("EffectSummary", **{key: value for key, value in summary.items()
        if key not in {"schema_version", "kind", "analysis_version", "policy_id"}})
