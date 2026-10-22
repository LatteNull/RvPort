"""Context-evaluation reference invariants, not LLVM transfer/alias proofs."""

from .contracts import identity
from .effect_instances import check, validate_instances, walk


def validate_evaluation(value, modules, *, registry, summaries):
    """Called after schema, raw/analysis reference and origin validation.

    The immutable request contains only the current activation and its ancestors.
    Callee effects are composed later; local results cannot smuggle child frames.
    """
    functions = {(k, f["id"]): f for k, m in modules.items() for f in m["functions"]}
    raw = {(k, v["id"]): v for k, m in modules.items() for v in m["values"]}
    calls = {(k, c["id"]): c for k, m in modules.items() for c in m["calls"]}
    function = value["function"]
    key, fn = function["artifact_key"], function["id"]
    check((key, fn) in functions and not functions[key, fn]["declaration"] and
          function["function_id"] is None, "Invalid evaluation function")
    check({o["artifact_key"] for o in value["origins"]} ==
          {d["artifact_key"] for d in value["local_dependencies"]}, "Evaluation origins need exact local dependencies")
    entries = value["invocations"]
    # Reuse activation/allocation validation without imposing public root-argument
    # restrictions. These synthetic fields are never published as a summary.
    first = entries[0]
    binding_view = {**value, "root_invocation_id": first["id"], "context_id": first["context_id"],
        "root": {"artifact_key": first["function"]["artifact_key"], "function_id": first["function"]["id"]},
        "status": value.get("status", "partial"), "diagnostics": value.get("diagnostics", ["input-binding"]),
        "effects": value.get("effects", []), "order": value.get("order", []),
        "returns": value.get("returns", []), "resolutions": value.get("resolutions", []),
        "escape": [value["arguments"], value.get("values", []), value.get("call_requests", []), value.get("escape", [])]}
    table = validate_instances(binding_view, modules, registry=registry)
    current = value["invocation_id"]
    check(current in table and table[current]["function"] == function and
          table[current]["context_id"] == value["context_id"], "Evaluation activation mismatch")
    chain = set()
    while current is not None:
        chain.add(current)
        current = table[current]["parent_id"]
    check(chain == set(table), "Evaluation contains non-ancestor activation")

    def local(source):
        check(source["artifact_key"] == key and source["function_id"] == fn, "Foreign local evaluation source")
        return key, source["id"]

    def typed(domain, formal):
        check(formal["type"] != "void", "Void cannot have an evaluated value")
        for candidate in domain["candidates"]:
            item = candidate["value"]
            if item["kind"] == "integer":
                check(formal["type"] == f'i{item["bits"]}', "Evaluation integer type mismatch")
            elif item["kind"] in {"object", "null"}:
                expected = "ptr" if item["address_space"] == 0 else f'ptr addrspace({item["address_space"]})'
                check(formal["type"] == expected, "Evaluation pointer type mismatch")
            elif item["kind"] in {"parameter", "expression"}:
                source = item["source"]
                pair = source["artifact_key"], source["id"]
                node = raw.get(pair, registry.get(pair, {}))
                check(node.get("type") == formal["type"], "Evaluation symbolic type mismatch")
                check(item["kind"] != "expression" or pair in registry and node.get("kind") != "argument",
                      "Expression requires registered instruction")

    parameters = functions[key, fn]["parameters"]
    check(len(value["arguments"]) == len(parameters), "Evaluation argument count mismatch")
    for domain, parameter in zip(value["arguments"], parameters):
        typed(domain, raw[key, parameter])
    for node in walk(value):
        if set(node) == {"state", "candidates", "reason"}:
            check(len(node["candidates"]) <= value["budgets"]["value_candidates"], "Evaluation candidate budget exceeded")
        if "guards" in node:
            check(len({identity(g) for g in node["guards"]}) == len(node["guards"]), "Duplicate evaluation guard")

    check(len({identity(a["call"]) for a in value["adoptions"]}) == len(value["adoptions"]), "Duplicate evaluation adoption")
    for adoption in value["adoptions"]:
        pair = local(adoption["call"])
        check(pair in calls, "Adoption source is not a call")
        target = adoption["target"]
        if adoption["kind"] == "unknown":
            check(target is None, "Unknown adoption cannot select a body")
        else:
            check(target is not None and target["function_id"] is None, "Adoption needs function target")
            target_fn = functions.get((target["artifact_key"], target["id"]), {})
            check(target_fn and not target_fn["declaration"] and calls[pair]["kind"] == "direct" and
                  calls[pair]["target"] == target_fn["name"], "Adoption target does not match direct call")
    bindings = value["call_bindings"]
    check(len({identity(b["source"]) for b in bindings}) == len(bindings), "Duplicate call binding")
    adopted = {identity(a["call"]): a for a in value["adoptions"]}
    dependencies = {d["context_id"] for d in value["dependencies"]}
    for binding in bindings:
        local(binding["source"])
        context = binding["context_id"]
        adoption = adopted.get(identity(binding["source"]))
        check(context in dependencies and context in summaries and adoption is not None and
              adoption["kind"] != "unknown", "Call binding lacks adopted dependency")
        root = summaries[context]["root"]
        check(adoption["target"] == dict(artifact_key=root["artifact_key"], function_id=None, id=root["function_id"]),
              "Call binding target mismatch")
    if value["kind"] == "LocalEvaluationRequest":
        return

    blocks = {b["id"]: b for b in functions[key, fn]["blocks"]}
    for category in ("values", "blocks", "call_requests"):
        items = value[category]
        check(len({identity(i["source"]) for i in items}) == len(items), "Duplicate evaluation output source")
        for item in items:
            pair = local(item["source"])
            if category == "values":
                check(pair in raw and raw[pair]["function"] == fn or pair in registry, "Value output is not a local value")
                typed(item["domain"], raw.get(pair, registry.get(pair)))
            elif category == "blocks":
                check(pair[1] in blocks, "Block output is not a block")
                check(item["state"] != "unreachable" or bool(item["proof"]), "Unreachable block needs proof")
            else:
                check(pair in calls, "Call request is not a call")
                check(len(item["arguments"]) == len(calls[pair]["arguments"]), "Call argument count mismatch")
                for domain, argument in zip(item["arguments"], calls[pair]["arguments"]):
                    typed(domain, raw[key, argument])
    check({b["source"]["id"] for b in value["blocks"]} == set(blocks), "Incomplete evaluation block plan")
    for category in ("effects", "returns", "resolutions"):
        for item in value[category]:
            # A raw diagnostic may be module-owned; its explicit binding is still local.
            if category != "resolutions" or item["source"]["function_id"] is not None:
                local(item["source"])
            check(item["invocation_id"] == value["invocation_id"], "Foreign output activation")
            if "context_id" in item:
                check(item["context_id"] == value["context_id"], "Foreign output context")
    for item in value["returns"]:
        pair = key, item["source"]["id"]
        opcode = registry.get(pair, {}).get("opcode")
        allowed = {"normal": {"ret"}, "unwind": {"resume", "cleanupret", "invoke"},
                   "noreturn": {"call", "invoke", "unreachable"}, "unknown": {"call", "invoke", "callbr", "unreachable", "resume", "cleanupret", "catchswitch"}}
        check(opcode in allowed[item["exit"]], "Evaluation exit source role mismatch")
    check(value["steps"] <= value["budgets"]["local_steps"], "Evaluation work budget exceeded")
    check(len(value["effects"]) + len(value["order"]) <= value["budgets"]["effect_items"], "Evaluation effect budget exceeded")
    pending = [b["source"] for b in value["blocks"] if b["state"] == "pending"]
    pending += [c["source"] for c in value["call_requests"]]
    check(all(any(d["source"] == source for d in value["frontier"]) for source in pending), "Pending work needs explicit frontier")
    unknown_paths = []
    pending_nodes = [(value, "$")]
    while pending_nodes:
        node, path = pending_nodes.pop()
        if isinstance(node, dict):
            if node.get("state") == "unknown" or node.get("kind") == "unknown":
                unknown_paths.append(path)
            pending_nodes.extend((child, f"{path}.{name}") for name, child in node.items())
        elif isinstance(node, list):
            pending_nodes.extend((child, f"{path}[{index}]") for index, child in enumerate(node))
    unknown = bool(unknown_paths)
    if value["status"] == "complete":
        check(not value["frontier"] and not unknown and value["steps"] > 0,
              "Incomplete evaluation claimed complete: " + ", ".join(unknown_paths[:8]))
    else:
        check(bool(value["frontier"]) and bool(value["diagnostics"]), "Incomplete evaluation needs frontier and diagnostics")
