"""Module-local reference integrity, not alias analysis or path solving."""

from .protocol import expected_protocol


def validate_graph(facts):
    from .contracts import AnalysisError

    def require(condition, detail):
        if not condition:
            raise AnalysisError("invalid_reference", detail)

    require(facts["protocol"] == expected_protocol(), "Facts extractor/policy mismatch")
    diagnostics = {(d["id"], d["reason"]) for d in facts["extraction"]["diagnostics"]}
    values = {v["id"]: v for v in facts["values"]}
    require(len(values) == len(facts["values"]), "Duplicate value ID")
    symbols = facts["functions"] + facts["globals"]
    require(len({s["id"] for s in symbols}) == len(symbols), "Duplicate symbol ID")
    functions = {f["id"]: f for f in facts["functions"]}
    blocks, predecessors = {}, {}
    for function in functions.values():
        for block in function.get("blocks", []):
            require(block["id"] not in blocks, "Duplicate block ID")
            blocks[block["id"]] = function["id"]
            predecessors[block["id"]] = set()

    def reference(key, owner=None, nullable=False):
        if key is None and nullable:
            return
        require(key in values, f"Dangling value: {key}")
        require(values[key]["function"] in (None, owner), f"Foreign value: {key}")

    for function in functions.values():
        owner = function["id"]
        for position, key in enumerate(function.get("parameters", [])):
            reference(key, owner)
            node = values[key]
            require(node["kind"] == "argument" and node["function"] == owner and node["details"].get("position") == position, "Parameter owner/position mismatch")
        for block in function.get("blocks", []):
            term = block["terminator"]
            require(term["id"].startswith(block["id"] + ":i"), "Terminator outside block")
            edges = term["edges"]
            require([edge["target"] for edge in edges] == block["successors"], "CFG successors mismatch")
            reference(term["condition_ref"], owner, True)
            reference(term["return_ref"], owner, True)
            for ordinal, edge in enumerate(edges):
                require(edge["ordinal"] == ordinal and blocks.get(edge["target"]) == owner, "Invalid CFG edge")
                predecessors[edge["target"]].add(block["id"])
                reference(edge["condition_ref"], owner, True)
                reference(edge["case_ref"], owner, True)
    for node in values.values():
        owner, block = node["function"], node["block"]
        require(owner is None or owner in functions, "Unknown function owner")
        require(block is None or blocks.get(block) == owner and owner is not None, "Unknown block owner")
        for key in node["operands"]:
            reference(key, owner)
        if node["status"] == "unknown":
            require(bool(node.get("reason")), "Unknown node without reason")
            require((node["id"], node["reason"]) in diagnostics, "Unknown node without diagnostic")
        if node["kind"] == "integer":
            import re
            text = node["details"].get("hex", "")
            require(bool(re.fullmatch("[0-9a-fA-F]+", text)), "Invalid integer bit pattern")
            require(node.get("bits", 0) > 0 and int(text, 16).bit_length() <= node["bits"], "Integer exceeds bit width")
        if node["details"].get("opcode") == "phi":
            incoming = node["details"].get("incoming", [])
            require(isinstance(incoming, list) and all(isinstance(x, dict) and set(x) == {"predecessor", "value_ref"} for x in incoming), "Invalid phi incoming")
            require(block in blocks and {x["predecessor"] for x in incoming} == predecessors[block], "Phi predecessor mismatch")
            require([x["value_ref"] for x in incoming] == node["operands"], "Phi operands mismatch")
    for global_ in facts["globals"]:
        initial = global_.get("initializer")
        if initial:
            reference(initial["value_ref"], None, initial["state"] != "value")
            require(not global_["declaration"] or initial["state"] == "declaration", "Declaration has initializer")
    for category in ("events", "calls"):
        require(len({x["id"] for x in facts[category]}) == len(facts[category]), f"Duplicate {category} ID")
        for item in facts[category]:
            owner = item["function"]
            require(owner in functions, "Unknown event/call function")
            reference(item["result_ref"], owner, True)
            if category == "events":
                require(blocks.get(item["block"]) == owner, "Event outside function")
                for key in item["inputs"].values():
                    reference(key, owner)
                for access in item["ranges"]:
                    reference(access["address_ref"], owner)
                    pointer = values[access["address_ref"]]
                    require(pointer["type_kind"] == "pointer" and pointer.get("address_space") == access["address_space"], "Range pointer address space mismatch")
            else:
                reference(item["called_ref"], owner)
                for key in item["arguments"]:
                    reference(key, owner)
                for bundle in item["bundles"]:
                    for key in bundle["inputs"]:
                        reference(key, owner)
                for target in (item["normal"], item["unwind"]):
                    require(target is None or blocks.get(target) == owner, "Call successor outside function")
    extraction = facts["extraction"]
    require(extraction["nodes"] == len(values), "Extraction node count mismatch")
    require(extraction["references"] == sum(len(v["operands"]) for v in values.values()), "Extraction reference count mismatch")
    require(extraction["unknown"] == len(extraction["diagnostics"]), "Extraction diagnostic count mismatch")
    require(extraction["status"] == ("partial" if extraction["diagnostics"] else "complete"), "Extraction status mismatch")
    valid_ids = set(values) | {x["id"] for x in facts["events"] + facts["calls"]}
    valid_ids.update(b["terminator"]["id"] for f in functions.values() for b in f.get("blocks", []))
    require(all(d["id"] in valid_ids for d in extraction["diagnostics"]), "Unknown diagnostic reference")
