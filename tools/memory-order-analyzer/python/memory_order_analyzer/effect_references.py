"""Cross-product identity validation. Structural validity is not an analysis proof."""

from .contracts import AnalysisError, identity, validate
from .effect_contracts import validate_effect_document
from .effect_instances import validate_instances
from .effect_registry import local_registry
from .effect_evaluation import validate_evaluation


def require(condition, detail):
    if not condition:
        raise AnalysisError("invalid_reference", detail)


def nodes(value):
    """Iterative traversal also makes nested expression validation explicit."""
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            yield current
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


def source_inventory(modules):
    sources, functions, terms = {}, {}, {}
    for key, module in modules.items():
        validate(module, "ModuleFacts")
        require(module["artifact_key"] == key, "Module map key mismatch")
        for symbol in module["functions"] + module["globals"]:
            sources[key, symbol["id"]] = None
        for function in module["functions"]:
            functions[key, function["id"]] = function
            for block in function.get("blocks", []):
                sources[key, block["id"]] = function["id"]
                term = block["terminator"]
                sources[key, term["id"]] = function["id"]
                terms[key, term["id"]] = term
        for item in module["values"] + module["events"] + module["calls"]:
            pair = key, item["id"]
            require(pair not in sources or sources[pair] == item["function"], "Conflicting raw node owner")
            sources[pair] = item["function"]
    return sources, functions, terms


def validate_effect_references(value, artifacts, modules, *, summaries=None, local_facts=None):
    """Validate loaded raw references and dependency content, without rewriting inputs.

    Callers must additionally validate the requested scope, physical BC hashes and
    semantic proofs. A legal SourceRef names its IR owner (symbols use null).
    Facts digests use canonical JSON, not incidental whitespace on disk.
    """
    validate_effect_document(value, value.get("kind") if isinstance(value, dict) else None)
    original = value
    if value["kind"] == "LocalEvaluationResult":
        request = value["request"]
        require(value["request_hash"] == identity(request), "Evaluation request digest mismatch")
        require(all(value[k] == request[k] for k in ("scope_id", "context_id", "budgets")), "Evaluation snapshot mismatch")
        validate_effect_references(request, artifacts, modules, summaries=summaries, local_facts=local_facts)
        value = {**request, **value}
    sources, functions, terms = source_inventory(modules)
    raw_values = {(k, v["id"]): v for k, m in modules.items() for v in m["values"]}
    raw_calls = {(k, c["id"]) for k, m in modules.items() for c in m["calls"]}
    raw_events = {(k, e["id"]): e for k, m in modules.items() for e in m["events"]}
    raw_globals = {(k, g["id"]) for k, m in modules.items() for g in m["globals"]}
    summaries = summaries or {}
    for key, artifact in artifacts.items():
        validate(artifact, "BCArtifact")
        require(artifact["artifact_key"] == key, "Artifact map key mismatch")
        if key in modules:
            require(artifact["sha256"] == modules[key]["module_hash"], "BC/facts hash mismatch")

    def source(reference):
        pair = reference["artifact_key"], reference["id"]
        require(pair in sources, "Dangling source reference")
        require(sources[pair] == reference["function_id"], "Foreign source owner")
        return pair

    origins = value.get("origins", [value["origin"]] if "origin" in value else [])
    require(len({o["artifact_key"] for o in origins}) == len(origins), "Duplicate origin")
    for origin in origins:
        key = origin["artifact_key"]
        require(key in artifacts and key in modules, "Missing origin inputs")
        require(origin["module_hash"] == artifacts[key]["sha256"], "Origin BC hash mismatch")
        require(origin["facts_hash"] == identity(modules[key]), "Origin facts hash mismatch")
        require(origin["profile"] == artifacts[key]["profile"], "Origin profile mismatch")
        require(origin["extractor_version"] == modules[key]["protocol"]["extractor_version"], "Origin extractor mismatch")

    registry, evidence = {}, {}
    local_facts = local_facts or {}
    dependencies = value.get("local_dependencies", [])
    require(len({d["artifact_key"] for d in dependencies}) == len(dependencies), "Duplicate local dependency")
    supplements = []
    for dependency in dependencies:
        key = dependency["artifact_key"]
        require(key in local_facts, "Missing local dependency")
        target = local_facts[key]
        validate_effect_document(target, "LocalAnalysisFacts")
        require(target["origin"]["artifact_key"] == key and identity(target) == dependency["digest"], "Local dependency digest mismatch")
        require(target["budgets"] == value["budgets"], "Foreign local dependency budget")
        validate_effect_references(target, artifacts, modules)
        supplements.append(target)
    if value["kind"] == "LocalAnalysisFacts":
        supplements.append(value)
    for supplement in supplements:
        ir, analysis = local_registry(supplement, sources, functions, raw_values)
        registry.update(ir)
        evidence.update(analysis)
    for pair, node in registry.items():
        if pair in terms:
            require(node["opcode"] == terms[pair]["opcode"], "Conflicting terminator opcode")
        if pair in raw_events and raw_events[pair]["kind"] in {"load", "store", "atomicrmw", "cmpxchg", "fence"}:
            require(node["opcode"] == raw_events[pair]["kind"], "Conflicting memory opcode")
        if pair in raw_calls:
            require(node["opcode"] in {"call", "invoke", "callbr"}, "Conflicting call opcode")

    for node in nodes(value):
        if set(node) == {"artifact_key", "function_id", "id"}:
            require(not origins or node["artifact_key"] in {o["artifact_key"] for o in origins}, "Source outside declared origins")
            source(node)
        if set(node) == {"artifact_key", "function_id", "analysis_id"}:
            require(not origins or node["artifact_key"] in {o["artifact_key"] for o in origins}, "Analysis outside declared origins")
            pair = node["artifact_key"], node["analysis_id"]
            require(pair in evidence and evidence[pair]["ref"] == node, "Dangling or foreign analysis reference")
        if node.get("kind") == "integer":
            require(int(node["hex"], 16).bit_length() <= node["bits"], "Integer exceeds bit width")
        if set(node) == {"source", "edge", "invocation_id", "multiplicity"}:
            pair = source(node["source"])
            require(pair in terms and node["edge"] < len(terms[pair]["edges"]), "Invalid guard edge")

    roots = value.get("roots", []) if value["kind"] == "EffectAnalysisRequest" else [value["root"]] if "root" in value else []
    for root in roots:
        pair = root["artifact_key"], root["function_id"]
        require(pair in functions and not functions[pair]["declaration"], "Missing root definition")
        require(len(root["arguments"]) == len(functions[pair]["parameters"]), "Root argument count mismatch")
        for argument, parameter in zip(root["arguments"], functions[pair]["parameters"]):
            formal = raw_values[root["artifact_key"], parameter]
            if argument["kind"] == "integer":
                require(formal["type_kind"] == "integer" and formal["bits"] == argument["bits"], "Root integer type mismatch")
            if argument["kind"] in {"object", "null"}:
                require(formal["type_kind"] == "pointer" and formal["address_space"] == argument["address_space"], "Root pointer type mismatch")
            if argument["kind"] == "object":
                require(source(argument["source"]) in raw_globals and argument["allocation"] is None, "Root cannot import local allocation")
            if argument["kind"] == "parameter":
                require(argument["source"] == dict(artifact_key=root["artifact_key"], function_id=root["function_id"], id=parameter)
                        and argument["invocation_id"] is None, "Root parameter must name its own template slot")
            require(argument["kind"] != "expression", "Root expression needs an evaluated binding")

    for resolution in value.get("resolutions", []):
        key = resolution["source"]["artifact_key"]
        require(resolution["facts_hash"] == identity(modules[key]), "Resolution facts hash mismatch")
        require({"id": resolution["source"]["id"], "reason": resolution["reason"]}
                in modules[key]["extraction"]["diagnostics"], "Resolution has no matching raw diagnostic")
        if value["kind"] == "EffectSummary":
            require(resolution["context_id"] == value["context_id"], "Foreign resolution context")

    for category in ("functions", "calls", "objects"):
        entries = value.get(category, [])
        refs = [identity(entry["source"]) for entry in entries]
        require(len(set(refs)) == len(refs), f"Duplicate {category} source")
        for entry in entries:
            pair = source(entry["source"])
            if category == "functions":
                require(pair in functions, "Supplement function is not function")
            elif category == "calls":
                require(pair in raw_calls, "Supplement call is not call")
            else:
                require(registry.get(pair, {}).get("opcode", raw_values.get(pair, {}).get("details", {}).get("opcode")) == "alloca",
                        "Supplement object is not alloca")
    effects = value.get("effects", [])
    effect_ids = {effect["id"] for effect in effects}
    require(len(effect_ids) == len(effects), "Duplicate effect ID")
    for effect in effects:
        require(effect["context_id"] == value["context_id"], "Foreign effect context")
        for call in effect["call_path"]:
            require(source(call) in raw_calls, "Call path contains non-call source")
        if effect["kind"] != "unknown":
            pair = source(effect["source"])
            require(pair in raw_events, "Effect source is not a raw event")
            event = raw_events[pair]
            allowed = {"load": {"read"}, "store": {"write"}, "atomicrmw": {"rmw"}, "cmpxchg": {"cas"}, "fence": {"fence"}}
            kinds = allowed.get(event["kind"], {r["role"] for r in event.get("ranges", [])})
            require(effect["kind"] in kinds, "Effect kind disagrees with raw event")
    if value["kind"] == "EffectSummary":
        validate_instances(value, modules, registry=registry)
    if value["kind"] in {"LocalEvaluationRequest", "LocalEvaluationResult"}:
        validate_evaluation(value, modules, registry=registry, summaries=summaries)
    for edge in value.get("order", []):
        require(edge["before"] in effect_ids and edge["after"] in effect_ids, "Dangling effect edge")
        require(edge["before"] != edge["after"], "Self effect edge")
    dependencies = value.get("dependencies", value.get("summaries", []))
    require(len({d["context_id"] for d in dependencies}) == len(dependencies), "Duplicate dependency")
    for dependency in dependencies:
        context = dependency["context_id"]
        require(context in summaries, "Missing summary dependency")
        target = summaries[context]
        validate_effect_document(target, "EffectSummary")
        require(target["context_id"] == context and identity(target) == dependency["digest"], "Summary dependency mismatch")
        require(target["scope_id"] == value["scope_id"], "Foreign summary scope")
    return original
