"""Typed P2 registries. Validation checks references, not LLVM query truth."""

import re

from .effect_instances import check


def local_registry(value, sources, functions, raw_values):
    """Extend a private source inventory only after checking the entire registry."""
    key = value["origin"]["artifact_key"]
    blocks = {(k, b["id"]): f["id"] for (k, _), f in functions.items() for b in f.get("blocks", [])}
    ir, evidence, queries = {}, {}, set()
    successors = {(k, b["id"]): b["successors"] for (k, _), f in functions.items() for b in f.get("blocks", [])}
    cost = len(value["ir_nodes"]) + len(value["analysis_evidence"]) + len(value["objects"])
    cost += sum(len(e["inputs"]) // 2 for e in value["analysis_evidence"] if e["kind"] == "memory_phi")
    check(cost <= value["budgets"]["local_steps"], "Local registry budget exceeded")
    for node in value["ir_nodes"]:
        src, block = node["source"], node["block"]
        pair = key, src["id"]
        check(src["artifact_key"] == block["artifact_key"] == key, "Foreign registry artifact")
        check((key, block["id"]) in blocks and blocks[key, block["id"]] == src["function_id"] == block["function_id"],
              "Invalid IR block owner")
        check(pair not in ir and pair not in blocks and pair not in functions, "Duplicate or non-instruction IR node")
        check(pair not in sources or sources[pair] == src["function_id"], "Conflicting IR owner")
        raw = raw_values.get(pair)
        if raw:
            check(raw["kind"] == "instruction" and raw["details"].get("opcode") == node["opcode"] and
                  raw["block"] == block["id"] and raw["type"] == node["type"], "Conflicting original IR node")
        else:
            check(re.fullmatch(re.escape(block["id"]) + r":i(0|[1-9][0-9]*)", src["id"]) is not None,
                  "Invalid original instruction namespace")
        ir[pair] = node
        sources[pair] = src["function_id"]
    for entry in value["analysis_evidence"]:
        ref = entry["ref"]
        pair = key, ref["analysis_id"]
        check(ref["artifact_key"] == key and (key, ref["function_id"]) in functions,
              "Foreign analysis owner")
        check(not functions[key, ref["function_id"]]["declaration"], "Analysis of declaration")
        check(pair not in evidence and pair not in sources, "Duplicate or raw analysis ID")
        query = entry["kind"], entry["source"]["id"]
        check(query not in queries, "Duplicate analysis query")
        queries.add(query)
        check(re.fullmatch(re.escape(ref["function_id"] + ":p2:" + entry["kind"] + ":") + r"(0|[1-9][0-9]*)",
                           ref["analysis_id"]) is not None, "Invalid analysis namespace")
        evidence[pair] = entry
    for entry in evidence.values():
        ref, src, kind, inputs = entry["ref"], entry["source"], entry["kind"], entry["inputs"]
        owner = ref["function_id"]
        check(src["artifact_key"] == key and (key, src["id"]) in sources, "Dangling analysis source")
        check(src["function_id"] == sources[key, src["id"]], "Incorrect analysis source owner")
        for item in inputs:
            check(item["artifact_key"] == key and item["function_id"] == owner, "Cross-function evidence input")
            table, field = (evidence, "analysis_id") if "analysis_id" in item else (sources, "id")
            check((key, item[field]) in table, "Dangling evidence input")
            actual = table[key, item[field]]["ref"]["function_id"] if field == "analysis_id" else table[key, item[field]]
            check(actual == owner, "Incorrect evidence input owner")
        if kind == "memory_live_on_entry":
            check(src["function_id"] is None and src["id"] == owner and not inputs, "Invalid live-on-entry")
        else:
            check(src["function_id"] == owner, "Cross-function evidence source")
        if kind == "dominance":
            check((key, src["id"]) in blocks and entry["result"] in {"reachable", "unreachable"}, "Invalid dominance source/result")
            check(len(inputs) <= 1 and (entry["result"] == "reachable" or not inputs), "Invalid dominator arity")
            check(all("id" in i and (key, i["id"]) in blocks and i["id"] != src["id"] for i in inputs), "Invalid dominator block")
        else:
            check(entry["result"] == "candidate", "Memory evidence is only a candidate")
            if kind == "memory_phi":
                check((key, src["id"]) in blocks and len(inputs) >= 2 and len(inputs) % 2 == 0, "Invalid MemoryPhi")
                check(all("id" in i and (key, i["id"]) in blocks for i in inputs[::2]), "Invalid phi predecessor")
                check(all(src["id"] in successors[key, i["id"]] for i in inputs[::2]), "Phi input is not a CFG predecessor")
                memory_inputs = inputs[1::2]
            else:
                check(kind == "memory_live_on_entry" or (key, src["id"]) in ir, "Memory access lacks IR registration")
                if kind in {"memory_def", "memory_use"}:
                    check(ir[key, src["id"]]["opcode"] in {"load", "store", "atomicrmw", "cmpxchg", "fence", "call", "invoke",
                          "callbr", "va_arg", "catchpad", "cleanuppad", "catchret", "cleanupret"}, "Invalid memory instruction role")
                check(len(inputs) == (0 if kind == "memory_live_on_entry" else 2 if kind == "aa_clobber" else 1),
                      "Invalid memory evidence arity")
                memory_inputs = inputs
            for index, item in enumerate(memory_inputs):
                check("analysis_id" in item, "Memory input is not analysis evidence")
                target = evidence[key, item["analysis_id"]]
                if kind == "aa_clobber" and index == 0:
                    check(target["kind"] in {"memory_def", "memory_use"} and target["source"] == src, "Invalid queried access")
                else:
                    check(target["kind"] in {"memory_def", "memory_phi", "memory_live_on_entry"}, "Invalid memory definition")
    return ir, evidence
