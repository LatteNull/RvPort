"""Finite activation identities; no identity operation constitutes an alias proof."""

from copy import deepcopy

from .contracts import AnalysisError, identity


def check(condition, detail):
    if not condition:
        raise AnalysisError("invalid_reference", detail)


def invocation(context, function, *, root_key, parent=None, callsite=None,
               cardinality="single", reason=None):
    """Construct a deterministic entry. Callers select finite SCC/budget buckets.

    root_key separates instantiations, not reusable summary cache contexts.
    No unbounded recursion or stack exploration happens in this constructor.
    """
    entry = dict(context_id=context, function=deepcopy(function), parent_id=parent,
                 callsite=deepcopy(callsite), cardinality=cardinality, reason=reason)
    check(cardinality in {"single", "merged", "unknown"}, "Invalid invocation cardinality")
    check((cardinality == "single") == (reason is None), "Invalid abstraction reason")
    check((parent is None) == (callsite is None), "Invalid parent/callsite pair")
    return {"id": identity({"root": root_key, "invocation": entry}), **entry}


def walk(value):
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            yield item
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def validate_instances(summary, modules, *, registry=None):
    """Validate schema-checked instances and bindings, not local LLVM proofs."""
    entries = summary["invocations"]
    table = {entry["id"]: entry for entry in entries}
    check(len(table) == len(entries), "Duplicate invocation ID")
    check(len(table) <= summary["budgets"]["contexts_per_request"], "Invocation budget exceeded")
    root_id = summary["root_invocation_id"]
    check(root_id in table, "Missing root invocation")
    root = summary["root"]
    check(table[root_id]["function"] == dict(artifact_key=root["artifact_key"],
          function_id=None, id=root["function_id"]), "Root invocation function mismatch")
    check(table[root_id]["context_id"] == summary["context_id"], "Root invocation context mismatch")
    functions = {(key, f["id"]): f for key, m in modules.items() for f in m["functions"]}
    calls = {(key, c["id"]): c for key, m in modules.items() for c in m["calls"]}
    values = {(key, v["id"]): v for key, m in modules.items() for v in m["values"]}
    local_allocas = {pair for pair, node in (registry or {}).items() if node["opcode"] == "alloca"}
    globals_ = {(key, g["id"]) for key, m in modules.items() for g in m["globals"]}

    def owner(reference, instance):
        check(instance in table, "Dangling invocation binding")
        fn = table[instance]["function"]
        check(reference["artifact_key"] == fn["artifact_key"] and
              reference["function_id"] == fn["id"], "Foreign invocation owner")

    seen = set()
    for entry in entries:
        fn = entry["function"]
        pair = fn["artifact_key"], fn["id"]
        check(pair in functions and not functions[pair]["declaration"] and
              fn["function_id"] is None, "Invalid invocation function")
        check((entry["cardinality"] == "single") == (entry["reason"] is None), "Invalid abstraction reason")
        parent = entry["parent_id"]
        if entry["id"] == root_id:
            check(parent is None and entry["callsite"] is None, "Root cannot have a parent")
        else:
            check(parent in seen and entry["callsite"] is not None, "Dangling or cyclic invocation parent")
            owner(entry["callsite"], parent)
            check((entry["callsite"]["artifact_key"], entry["callsite"]["id"]) in calls, "Invalid invocation callsite")
            check(table[parent]["cardinality"] == "single" or entry["cardinality"] != "single",
                  "Child is more precise than merged parent")
        seen.add(entry["id"])
    if any(e["cardinality"] != "single" for e in entries):
        check(summary["status"] != "complete" and bool(summary["diagnostics"]), "Merged invocation needs partial evidence")

    # Root arguments are reusable template bindings; result payloads must be bound.
    for category in ("effects", "order", "returns", "escape", "resolutions"):
        for node in walk(summary[category]):
            if "invocation_id" in node:
                instance = node["invocation_id"]
                check(instance in table, f"Unbound or dangling invocation: {instance!r}")
                if "source" in node and node["source"]["function_id"] is not None:
                    owner(node["source"], instance)
                if "edge" in node and table[instance]["cardinality"] != "single":
                    check(node["multiplicity"] != "single", "Merged invocation cannot prove single guard")
            if node.get("kind") == "object":
                src, allocation = node["source"], node["allocation"]
                pair = src["artifact_key"], src["id"]
                if src["function_id"] is None:
                    check(pair in globals_ and allocation is None, "Invalid global allocation")
                else:
                    check(allocation is not None, "Local allocation lacks instance")
                    owner(src, allocation["invocation_id"])
                    check(pair in local_allocas or pair in values and values[pair]["details"].get("opcode") == "alloca", "Local object is not alloca")
                    check((allocation["cardinality"] == "single") == (allocation["reason"] is None), "Invalid allocation reason")
                    check(table[allocation["invocation_id"]]["cardinality"] == "single" or
                          allocation["cardinality"] != "single", "Allocation is more precise than invocation")
                    if allocation["cardinality"] != "single":
                        check(summary["status"] != "complete" and bool(summary["diagnostics"]), "Merged allocation needs partial evidence")
            if node.get("kind") == "parameter":
                src = node["source"]
                check((src["artifact_key"], src["id"]) in values and
                      values[src["artifact_key"], src["id"]]["kind"] == "argument", "Parameter is not argument")
    for effect in summary["effects"]:
        if table[effect["invocation_id"]]["cardinality"] != "single":
            check(effect["occurrence"] == "may" and effect["multiplicity"] != "single",
                  "Merged invocation cannot prove must/single effect")
    return table


def guards_exclusive(left, right, instances):
    """Only distinct successor choices of one singleton activation conflict."""
    same = left["invocation_id"] == right["invocation_id"]
    entry = instances.get(left["invocation_id"])
    return bool(same and entry and entry["cardinality"] == "single" and
                left["multiplicity"] == right["multiplicity"] == "single" and
                left["source"] == right["source"] and left["edge"] != right["edge"])


def singleton_allocation(value, instances):
    """Necessary identity precondition, NEVER sufficient for a strong update."""
    allocation = value.get("allocation")
    if value.get("kind") != "object" or not allocation:
        return False
    entry = instances.get(allocation["invocation_id"])
    return bool(entry and entry["cardinality"] == "single" and allocation["cardinality"] == "single")


def rebind_payload(payload, replacements):
    """Copy template-local bindings only; caller-owned arguments stay untouched.

    replacements maps old invocation IDs to new validated entries. Deliberately
    does not rewrite SourceRef, context_id, or arbitrary strings equal to an ID.
    """
    result = deepcopy(payload)
    effect_ids = {}
    for node in walk(result):
        if "occurrence" in node and node["invocation_id"] in replacements:
            new = replacements[node["invocation_id"]]["id"]
            effect_ids[node["id"]] = identity({"template_effect": node["id"], "invocation": new})
            node["id"] = effect_ids[node["id"]]
    for node in walk(result):
        if set(node) == {"before", "after", "guards"}:
            node["before"] = effect_ids.get(node["before"], node["before"])
            node["after"] = effect_ids.get(node["after"], node["after"])
        old = node.get("invocation_id")
        if old not in replacements:
            continue
        entry = replacements[old]
        node["invocation_id"] = entry["id"]
        if entry["cardinality"] != "single":
            if "edge" in node:
                node["multiplicity"] = "unknown"
            if "cardinality" in node:
                if node["cardinality"] != "unknown":
                    node.update(cardinality=entry["cardinality"], reason=entry["reason"])
            if "occurrence" in node:
                node.update(occurrence="may", multiplicity="unknown", proof=[])
    return result
