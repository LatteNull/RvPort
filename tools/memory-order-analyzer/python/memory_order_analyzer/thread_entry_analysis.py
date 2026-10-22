"""AST/BC thread-entry normalization, alignment, root overlay, and reporting."""

from collections import defaultdict
from copy import deepcopy

from .contracts import canonical, identity
from .thread_entry_contracts import dependency, diagnostic, thread_entry_document


SOURCE_KINDS = {
    "pthread_create": ("pthread", "create"),
    "thrd_create": ("c11-thread", "create"),
    "cpp-thread-construct": ("std-thread", "callable-construction"),
    "cpp-jthread-construct": ("std-jthread", "callable-construction"),
    "cpp-async-call": ("std-async", "callable-construction"),
    "cpp-thread-default": ("std-thread", "default"),
    "cpp-jthread-default": ("std-jthread", "default"),
    "cpp-thread-move-construct": ("std-thread", "move-construction"),
    "cpp-jthread-move-construct": ("std-jthread", "move-construction"),
    "cpp-thread-factory-return": ("std-thread", "factory-return"),
    "cpp-jthread-factory-return": ("std-jthread", "factory-return"),
    "unsupported-thread-api": ("framework", "unsupported"),
}
CALLBACK_KINDS = {
    "pthread": {"callback"}, "c11-thread": {"callback", "thrd-callback"},
    "std-thread": {"cpp-thread-callback"}, "std-jthread": {"cpp-jthread-callback"},
    "std-async": {"cpp-async-callback"},
}


def _entry(value):
    if not isinstance(value, dict):
        return None
    artifact = value.get("artifact_key")
    function = value.get("function_id") or value.get("id")
    return {"artifact_key": artifact, "function_id": function} if artifact and function else None


def _anchor(source):
    if not isinstance(source, dict):
        return None
    point = source.get("expansion") or source.get("spelling") or source
    if not isinstance(point, dict):
        return None
    if not point.get("file"):
        return None
    return {"file": point["file"], "line": point.get("line", 0), "column": point.get("column", 0)}


def _candidate(*, layer, member, api_family, model_id, callsite_id, operation,
               callback=None, launch_policy="not-applicable", guard=None, evidence=(),
               status="candidate", reason=None, metadata=None):
    seed = {"layer": layer, "tu": member["physical_tu_id"], "profile": member["profile_id"],
            "api": api_family, "model": model_id, "site": callsite_id, "operation": operation,
            "evidence": sorted(set(evidence))}
    return {
        "id": identity(seed), "layer": layer, "physical_tu_id": member["physical_tu_id"],
        "profile_id": member["profile_id"], "api_family": api_family, "model_id": model_id,
        "callsite_id": callsite_id, "operation": operation,
        "callback": callback or {"entry": None, "source_entity_id": None, "candidates": []},
        "launch_policy": launch_policy, "guard": deepcopy(guard),
        "evidence": sorted(set(str(item) for item in evidence)), "status": status,
        "reason": reason, "metadata": deepcopy(metadata or {}),
    }


def _source_callback(api_family, relation, by_from, nodes, binding_by_source):
    matches = [item for item in by_from[relation["from"]]
               if item.get("kind") in CALLBACK_KINDS.get(api_family, set())]
    target_ids = sorted({item.get("to") for item in matches if item.get("to")})
    entries = []
    for target_id in target_ids:
        binding = binding_by_source.get(target_id)
        if binding and binding.get("resolution") == "exact":
            entries.extend(filter(None, (_entry(item) for item in binding.get("targets", []))))
    unique_entries = sorted({canonical(item): item for item in entries}.values(), key=canonical)
    node = nodes.get(target_ids[0], {}) if len(target_ids) == 1 else {}
    return {
        "entry": unique_entries[0] if len(unique_entries) == 1 else None,
        "source_entity_id": target_ids[0] if len(target_ids) == 1 else None,
        "candidates": unique_entries if unique_entries else target_ids,
        "canonical_type": node.get("canonical_type"),
    }, matches


def _relation_metadata(relation, node, expression_binding):
    attributes = node.get("attributes", []) if isinstance(node, dict) else []
    parsed = {}
    for item in attributes:
        if isinstance(item, str) and item.startswith("thread-entry:") and "=" in item:
            key, value = item[len("thread-entry:"):].split("=", 1)
            parsed[key] = value
    source = relation.get("source") or node.get("source") or {}
    ir_call_ids = sorted(item.get("id") for item in (expression_binding or {}).get("targets", []) if item.get("id"))
    return {
        "source": source, "anchor": _anchor(source), "ir_call_ids": ir_call_ids,
        "spelled_type": parsed.get("spelled-type"),
        "canonical_type": parsed.get("canonical-type") or node.get("canonical_type"),
        "canonical_record": parsed.get("canonical-record"),
        "constructor_decl": parsed.get("constructor-decl"),
        "constructor_kind": parsed.get("constructor-kind"),
        "alias_chain": [item for item in parsed.get("alias-chain", "").split("|") if item],
        "declaration_origin": parsed.get("declaration-origin"),
        "system_boundary": parsed.get("system-boundary") == "true",
        "stop_token_injected": parsed.get("stop-token-injected") == "true",
        "launch_policy": parsed.get("launch-policy"),
    }


def _profile_accepts_source(api_family, metadata, models):
    if len(models) != 1 or models[0].get("status") != "verified":
        return False
    if api_family in {"pthread", "c11-thread"}:
        return True
    observed = metadata.get("canonical_record")
    declared = {item.get("qualified_name") for item in models[0].get("canonical_entities", [])}
    return bool(observed and observed in declared)


def source_candidates(member, source_facts, source_binding, models):
    if not source_facts:
        return []
    nodes = {item["id"]: item for item in source_facts.get("nodes", [])}
    relations = source_facts.get("relations", [])
    by_from = defaultdict(list)
    for relation in relations:
        by_from[relation.get("from")].append(relation)
    bindings = {item["source_id"]: item for item in (source_binding or {}).get("entity_bindings", [])}
    expression_bindings = {item["source_id"]: item for item in (source_binding or {}).get("expression_bindings", [])}
    model_by_api = defaultdict(list)
    for model in models:
        model_by_api[model["api_family"]].append(model)
    result = []
    for relation in sorted(relations, key=lambda item: item["id"]):
        mapped = SOURCE_KINDS.get(relation.get("kind"))
        if not mapped:
            continue
        api_family, operation = mapped
        callback, callback_relations = _source_callback(api_family, relation, by_from, nodes, bindings)
        node = nodes.get(relation.get("from"), {})
        metadata = _relation_metadata(relation, node, expression_bindings.get(relation.get("from")))
        object_relations = [item for item in relations
                            if item.get("kind") in {"cpp-thread-object", "cpp-jthread-object"}
                            and _anchor(item.get("source")) == metadata["anchor"]]
        if len(object_relations) == 1:
            object_id = object_relations[0].get("to")
            metadata["object"] = object_id
            object_node = nodes.get(object_id, {})
            declared = {}
            for attribute in object_node.get("attributes", []):
                if isinstance(attribute, str) and attribute.startswith("thread-entry:declared-") and "=" in attribute:
                    key, value = attribute[len("thread-entry:declared-"):].split("=", 1)
                    declared[key] = value
            if declared.get("spelled-type"):
                metadata["spelled_type"] = declared["spelled-type"]
            if declared.get("canonical-type"):
                metadata["canonical_type"] = declared["canonical-type"]
            if declared.get("alias-chain"):
                metadata["alias_chain"] = declared["alias-chain"].split("|")
        anchor = metadata["anchor"] or {"source_id": relation.get("from")}
        callsite_id = identity({"tu": member["physical_tu_id"], "profile": member["profile_id"],
                                "api": api_family, "anchor": anchor})
        eligible_models = model_by_api.get(api_family, [])
        model_id = eligible_models[0]["id"] if len(eligible_models) == 1 else f"builtin:{api_family}"
        constructor_kind = metadata.get("constructor_kind")
        if constructor_kind in {"default", "move-construction", "factory-return", "copy-or-deleted"}:
            operation = constructor_kind
        launch_policy = "not-applicable"
        if api_family == "std-async":
            launch_policy = metadata.get("launch_policy") or relation.get("reason") or "unknown"
            launch_policy = {"async-policy": "async", "deferred-policy": "deferred",
                             "default-policy": "default", "combined-policy": "both"}.get(launch_policy, launch_policy)
            if launch_policy not in {"async", "deferred", "default", "both", "unknown"}:
                launch_policy = "unknown"
        exact = (relation.get("status") != "unknown" and callback.get("entry") is not None
                 and _profile_accepts_source(api_family, metadata, eligible_models))
        status = "exact" if exact else "unknown" if relation.get("status") == "unknown" else "candidate"
        if operation == "unsupported":
            status = "unsupported"
        if operation in {"default", "move-construction", "factory-return", "copy-or-deleted"}:
            status = "excluded"
        evidence = [relation["id"], *(item["id"] for item in callback_relations)]
        result.append(_candidate(
            layer="source", member=member, api_family=api_family, model_id=model_id,
            callsite_id=callsite_id, operation=operation, callback=callback,
            launch_policy=launch_policy, guard={"kind": "source", "value": "normal-construction"},
            evidence=evidence, status=status,
            reason=relation.get("reason") if status != "exact" else None, metadata=metadata))
    return sorted(result, key=lambda item: item["id"])


def _thread_local_candidates(member, facts, models):
    model_by_api = {item["api_family"]: item for item in models}
    result = []
    for call in facts.get("calls", []):
        symbol = call.get("symbol")
        api = "pthread" if symbol == "pthread_create" else "c11-thread" if symbol == "thrd_create" else None
        if api is None:
            continue
        source = call.get("source") or {}
        callsite_id = identity({"tu": member["physical_tu_id"], "profile": member["profile_id"],
                                "api": api, "ir": source})
        targets = sorted(filter(None, (_entry(item) for item in call.get("callback_targets", []))), key=canonical)
        callback = {"entry": targets[0] if len(targets) == 1 else None,
                    "source_entity_id": None, "candidates": targets}
        exact = call.get("direct") is True and call.get("status") == "candidate" and len(targets) == 1
        model = model_by_api.get(api)
        status = "exact" if exact and model and model["status"] == "verified" else "candidate" if exact else "unknown"
        result.append(_candidate(
            layer="ir", member=member, api_family=api,
            model_id=model["id"] if model else f"builtin:{api}", callsite_id=callsite_id,
            operation="create", callback=callback, guard=call.get("success_test"),
            evidence=[canonical(source)], status=status,
            reason=None if status == "exact" else call.get("reason") or "abi-callback-or-model-incomplete",
            metadata={"ir_call_id": source.get("id"), "source": source,
                      "handle": call.get("handle_source"), "argument": (call.get("arguments") or [None])[-1]}))
    return result


def _cpp_local_candidates(member, facts, models):
    model = next((item for item in models if item["api_family"] == "std-thread"), None)
    if model is None:
        return []
    callables = {item["id"]: item for item in facts.get("callables", [])}
    result = []
    for operation in facts.get("operations", []):
        if operation.get("operation") not in {"construct", "move-construct"}:
            continue
        callsite_id = identity({"tu": member["physical_tu_id"], "profile": member["profile_id"],
                                "api": "std-thread", "source": operation.get("source_nodes", [])})
        callable_ = callables.get(operation.get("callable_id"), {})
        targets = sorted(filter(None, (_entry(item) for item in callable_.get("targets", []))), key=canonical)
        callback = {"entry": targets[0] if len(targets) == 1 else None,
                    "source_entity_id": callable_.get("entity_id"), "candidates": targets}
        creating = operation.get("operation") == "construct"
        exact = creating and operation.get("outcome") == "success" and callback["entry"] and operation.get("ir_nodes")
        result.append(_candidate(
            layer="ir", member=member, api_family="std-thread", model_id=model["id"],
            callsite_id=callsite_id, operation="callable-construction" if creating else "move-construction",
            callback=callback, guard=operation.get("guard"), evidence=operation.get("ir_nodes", []),
            status="exact" if exact else "excluded" if not creating else "candidate",
            reason=None if exact else "move-does-not-create" if not creating else "a3-evidence-incomplete",
            metadata={"ir_call_id": operation.get("id"), "object": operation.get("object_id"),
                      "handle": operation.get("native_handle"), "source_nodes": operation.get("source_nodes", [])}))
    return result


def _broker_paths(module, start_call, brokers, depth_limit):
    functions_by_name = defaultdict(list)
    for function in module.get("functions", []):
        if not function.get("declaration"):
            functions_by_name[function.get("name")].append(function)
    calls_by_function = defaultdict(list)
    for call in module.get("calls", []):
        calls_by_function[call.get("function")].append(call)
    found, exhausted = [], False

    def visit(call, depth, chain, seen):
        nonlocal exhausted
        symbol = call.get("target") or call.get("symbol")
        broker = brokers.get(symbol)
        next_chain = [*chain, str(call.get("id"))]
        if broker:
            found.append((call, broker, next_chain))
            return
        if depth >= depth_limit:
            exhausted = True
            return
        definitions = functions_by_name.get(symbol, [])
        if len(definitions) != 1:
            return
        function_id = definitions[0].get("id")
        if function_id in seen:
            exhausted = True
            return
        for child in calls_by_function.get(function_id, []):
            visit(child, depth + 1, next_chain, {*seen, function_id})

    visit(start_call, 0, [], set())
    unique = {item[0].get("id"): item for item in found}
    return sorted(unique.values(), key=lambda item: str(item[0].get("id"))), exhausted


def _module_broker_candidates(member, module, models, source_observations=(), wrapper_depth=0):
    result = []
    calls = {item.get("id"): item for item in module.get("calls", []) if item.get("id")}
    model_by_id = {item["id"]: item for item in models}
    assisted_call_ids = set()
    for source_candidate in source_observations:
        model = model_by_id.get(source_candidate["model_id"])
        if model is None:
            continue
        brokers = {item.get("symbol"): item for item in model["brokers"]}
        matched, exhausted = [], False
        for ir_id in source_candidate["metadata"].get("ir_call_ids", []):
            call = calls.get(ir_id)
            if call and call.get("kind") == "direct":
                paths, hit = _broker_paths(module, call, brokers, wrapper_depth)
                matched.extend(paths); exhausted |= hit
        matched = list({item[0].get("id"): item for item in matched}.values())
        if len(matched) != 1:
            if exhausted or len(matched) > 1:
                start_ids = source_candidate["metadata"].get("ir_call_ids", [])
                result.append(_candidate(
                    layer="ir", member=member, api_family=source_candidate["api_family"],
                    model_id=model["id"], callsite_id=source_candidate["callsite_id"],
                    operation=source_candidate["operation"], callback=deepcopy(source_candidate["callback"]),
                    launch_policy=source_candidate["launch_policy"], guard=source_candidate.get("guard"),
                    evidence=start_ids, status="unknown",
                    reason="wrapper-depth-budget-exhausted" if exhausted else "broker-ambiguous",
                    metadata={"ir_call_id": start_ids[0] if len(start_ids) == 1 else None,
                              "source_assisted": True, "broker_candidates": len(matched)}))
            continue
        call, broker, chain = matched[0]
        assisted_call_ids.add(call["id"])
        callback = deepcopy(source_candidate["callback"])
        exact = source_candidate["status"] == "exact" and callback.get("entry") is not None
        result.append(_candidate(
            layer="ir", member=member, api_family=source_candidate["api_family"],
            model_id=model["id"], callsite_id=source_candidate["callsite_id"],
            operation=source_candidate["operation"], callback=callback,
            launch_policy=source_candidate["launch_policy"], guard=source_candidate.get("guard"),
            evidence=chain,
            status="exact" if exact else "candidate",
            reason=None if exact else "source-callback-or-binding-incomplete",
            metadata={"ir_call_id": call["id"], "source": call.get("source"),
                      "broker_role": broker.get("role"), "source_assisted": True,
                      "wrapper_depth": max(0, len(chain) - 1)}))

    for model in models:
        if model["language"] != member["language"] or member["standard"] not in model["standards"]:
            continue
        brokers = {item.get("symbol"): item for item in model["brokers"]}
        for call in module.get("calls", []):
            if call.get("id") in assisted_call_ids:
                continue
            symbol = call.get("target") or call.get("symbol")
            broker = brokers.get(symbol)
            if not broker or broker.get("role") not in {"create", "construct-attempt", "entry-broker", "async-start"}:
                continue
            source = call.get("source") or {"id": call.get("id")}
            callsite_id = identity({"tu": member["physical_tu_id"], "profile": member["profile_id"],
                                    "api": model["api_family"], "ir": source})
            callback_targets = call.get("callback_targets", [])
            targets = sorted(filter(None, (_entry(item) for item in callback_targets)), key=canonical)
            callback = {"entry": targets[0] if len(targets) == 1 else None,
                        "source_entity_id": None, "candidates": targets}
            candidate = _candidate(
                layer="ir", member=member, api_family=model["api_family"], model_id=model["id"],
                callsite_id=callsite_id, operation="callable-construction", callback=callback,
                launch_policy=call.get("launch_policy", "not-applicable"), guard=call.get("success_test"),
                evidence=[str(call.get("id"))], status="exact" if callback["entry"] else "candidate",
                reason=None if callback["entry"] else "broker-callback-binding-required",
                metadata={"ir_call_id": call.get("id"), "source": source, "broker_role": broker.get("role")})
            if not broker.get("source_binding_required"):
                result.append(candidate)
    return result


def build_local_facts(request, member, evidence):
    tu = member["physical_tu_id"]
    local = evidence.get("by_member", {}).get(tu, {})
    applicable_models = [item for item in request["model_profiles"]
                         if item["language"] == member["language"] and member["standard"] in item["standards"]]
    module = local.get("ModuleFacts") or {}
    target, data_layout = module.get("target"), module.get("layout")
    models = [item for item in applicable_models
              if (target is None or item["target"] == target)
              and (data_layout is None or item["data_layout"] == data_layout)]
    rejected_models = [item for item in applicable_models if item not in models]
    dependencies = []
    for kind, value in local.items():
        key = value.get("physical_tu_id") or value.get("artifact_key") or value.get("origin", {}).get("artifact_key") or tu
        dependencies.append(dependency(kind, key, value))
    source_binding = evidence.get("SourceIRBinding", {}).get(request["scope_id"])
    if source_binding is not None:
        dependencies.append(dependency("SourceIRBinding", request["scope_id"], source_binding))
    dependencies = list({(item["kind"], item["id"]): item for item in dependencies}.values())
    source = source_candidates(member, local.get("SourceSemanticFacts"), source_binding, models)
    ir = []
    if local.get("ThreadLocalFacts"):
        ir.extend(_thread_local_candidates(member, local["ThreadLocalFacts"], models))
    if local.get("CppThreadLocalFacts"):
        ir.extend(_cpp_local_candidates(member, local["CppThreadLocalFacts"], models))
    if local.get("ModuleFacts"):
        ir.extend(_module_broker_candidates(member, local["ModuleFacts"], models, source,
                                            min(request["budgets"]["wrapper_depth"],
                                                request["budgets"]["scc_iterations"])))
    ir = sorted({item["id"]: item for item in ir}.values(), key=lambda item: item["id"])
    diagnostics, frontier = [], []
    if rejected_models:
        frontier.append(diagnostic(
            "thread-entry-model-profile-mismatch", "线程入口模型与 target、DataLayout 或 ABI profile 不匹配",
            "A thread-entry model does not match the target, DataLayout, or ABI profile",
            source={"physical_tu_id": tu, "models": sorted(item["id"] for item in rejected_models)}))
    platform_excluded = isinstance(target, str) and any(piece in target.lower() for piece in ("windows", "msvc"))
    if platform_excluded:
        for candidate in [*source, *ir]:
            candidate["status"] = "unsupported"
            candidate["reason"] = "windows-msvc-clang-cl-excluded"
        frontier.append(diagnostic(
            "thread-entry-platform-excluded", "Windows、MSVC 与 clang-cl 不在支持范围",
            "Windows, MSVC, and clang-cl are outside the supported scope",
            source={"physical_tu_id": tu, "target": target}))
    budgets = request["budgets"]
    budget_hits = {}
    for candidate in source:
        alias_count = len(candidate["metadata"].get("alias_chain", []))
        type_text = candidate["metadata"].get("canonical_type") or ""
        type_depth = max(type_text.count("<"), type_text.count("*"), type_text.count("[")) + 1
        binding_count = len(candidate["metadata"].get("ir_call_ids", []))
        callback_count = len(candidate["callback"].get("candidates", []))
        exceeded = ("alias-depth-budget-exhausted" if alias_count > budgets["alias_depth"] else
                    "type-depth-budget-exhausted" if type_depth > budgets["type_depth"] else
                    "binding-candidates-budget-exhausted" if binding_count > budgets["binding_candidates"] else
                    "callback-candidates-budget-exhausted" if callback_count > budgets["callback_candidates"] else None)
        if exceeded:
            candidate["status"] = "unknown"
            candidate["reason"] = exceeded
            observed = {"alias-depth-budget-exhausted": alias_count,
                        "type-depth-budget-exhausted": type_depth,
                        "binding-candidates-budget-exhausted": binding_count,
                        "callback-candidates-budget-exhausted": callback_count}[exceeded]
            budget_hits[exceeded] = max(budget_hits.get(exceeded, 0), observed)
            candidate["metadata"]["ir_call_ids"] = candidate["metadata"].get("ir_call_ids", [])[:budgets["binding_candidates"]]
            candidate["callback"]["candidates"] = candidate["callback"].get("candidates", [])[:budgets["callback_candidates"]]
    if len(source) > budgets["source_facts"]:
        budget_hits["source-facts-budget-exhausted"] = len(source)
        source = source[:budgets["source_facts"]]
    if len(ir) > budgets["ir_facts"]:
        budget_hits["ir-facts-budget-exhausted"] = len(ir)
        ir = ir[:budgets["ir_facts"]]
    budget_limits = {
        "alias-depth-budget-exhausted": budgets["alias_depth"],
        "type-depth-budget-exhausted": budgets["type_depth"],
        "binding-candidates-budget-exhausted": budgets["binding_candidates"],
        "callback-candidates-budget-exhausted": budgets["callback_candidates"],
        "source-facts-budget-exhausted": budgets["source_facts"],
        "ir-facts-budget-exhausted": budgets["ir_facts"],
    }
    for code, hit in sorted(budget_hits.items()):
        frontier.append(diagnostic(code, "线程入口局部分析预算已耗尽",
                                   "A local thread-entry analysis budget was exhausted",
                                   source={"physical_tu_id": tu, "hit": hit,
                                           "limit": budget_limits[code]}))
    if not source and not ir:
        item = diagnostic("thread-entry-local-zero", "该 TU 未发现线程入口观察",
                          "No thread-entry observation was found in this translation unit",
                          source={"physical_tu_id": tu})
        diagnostics.append(item)
    dependency_failed = any(value.get("status") == "failed" for value in local.values())
    if dependency_failed:
        item = diagnostic("thread-entry-local-dependency-failed", "线程入口局部依赖失败",
                          "A local thread-entry dependency failed", source={"physical_tu_id": tu})
        frontier.append(item)
    status = ("failed" if dependency_failed and not source and not ir else
              "partial" if dependency_failed or frontier else "complete")
    return thread_entry_document(
        "ThreadEntryLocalFacts", scope_id=request["scope_id"], request_hash=identity(request),
        physical_tu_id=tu, profile_id=member["profile_id"], language=member["language"],
        standard=member["standard"], status=status, source_candidates=source, ir_candidates=ir,
        counts={"source": len(source), "ir": len(ir),
                **{f"budget:{key}:hit": value for key, value in sorted(budget_hits.items())},
                **{f"budget:{key}:limit": budget_limits[key] for key in sorted(budget_hits)}},
        dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
        diagnostics=diagnostics, frontier=frontier, semantic_digest=None)


def _same_callback(source, ir):
    left, right = source["callback"].get("entry"), ir["callback"].get("entry")
    return left is not None and right is not None and canonical(left) == canonical(right)


def _matches(source, ir):
    if any(source[key] != ir[key] for key in ("physical_tu_id", "profile_id", "api_family", "model_id")):
        return False
    if source["callsite_id"] == ir["callsite_id"]:
        return True
    ir_id = ir["metadata"].get("ir_call_id")
    return bool(ir_id and ir_id in source["metadata"].get("ir_call_ids", []))


def _merge_duplicate_observations(candidates):
    groups = defaultdict(list)
    for candidate in candidates:
        key = (candidate["layer"], candidate["physical_tu_id"], candidate["profile_id"],
               candidate["api_family"], candidate["model_id"], candidate["callsite_id"],
               candidate["operation"], candidate["launch_policy"])
        groups[key].append(candidate)
    result = []
    rank = {"exact": 5, "excluded": 4, "candidate": 3, "unknown": 2, "unsupported": 1, "failed": 0}
    for values in groups.values():
        if len(values) == 1:
            result.append(values[0]); continue
        merged = deepcopy(max(values, key=lambda item: rank[item["status"]]))
        entries = {canonical(item["callback"].get("entry")) for item in values if item["callback"].get("entry")}
        if len(entries) > 1:
            merged["callback"]["entry"] = None
            merged["status"] = "unknown"
            merged["reason"] = "duplicate-observation-callback-conflict"
        merged["evidence"] = sorted({piece for item in values for piece in item["evidence"]})
        merged["metadata"]["ir_call_ids"] = sorted({ir_id for item in values
                                                       for ir_id in item["metadata"].get("ir_call_ids", [])})
        merged["id"] = identity({"duplicates": sorted(item["id"] for item in values),
                                  "callsite": merged["callsite_id"], "layer": merged["layer"]})
        result.append(merged)
    return sorted(result, key=lambda item: item["id"])


def _site_from(observations):
    source = next((item for item in observations if item["layer"] == "source"), None)
    ir = next((item for item in observations if item["layer"] == "ir"), None)
    exemplar = source or ir
    opposed, reason = [], None
    if source and ir:
        if source["callback"].get("entry") and ir["callback"].get("entry") and not _same_callback(source, ir):
            evidence_status, opposed, reason = "ambiguous", ["source-ir-callback-disagreement"], "source-ir-callback-disagreement"
        elif source["status"] == "exact" and ir["status"] == "exact" and _same_callback(source, ir):
            evidence_status = "dual-exact"
        elif "failed" in {source["status"], ir["status"]}:
            evidence_status, reason = "failed", "source-or-ir-failed"
        elif "unsupported" in {source["status"], ir["status"]}:
            evidence_status, reason = "unsupported", "source-or-ir-unsupported"
        else:
            evidence_status, reason = "ambiguous", "source-ir-evidence-incomplete"
    elif source:
        evidence_status = "failed" if source["status"] == "failed" else "unsupported" if source["status"] == "unsupported" else "source-candidate"
        reason = source.get("reason") or "ir-evidence-missing"
    else:
        exact_c = ir["status"] == "exact" and ir["api_family"] in {"pthread", "c11-thread"}
        evidence_status = "ir-exact" if exact_c else "failed" if ir["status"] == "failed" else "unsupported" if ir["status"] == "unsupported" else "ir-candidate"
        reason = None if exact_c else ir.get("reason") or "source-evidence-missing"

    operations = {item["operation"] for item in observations}
    policies = {item["launch_policy"] for item in observations if item["launch_policy"] != "not-applicable"}
    if operations & {"default", "move-construction", "factory-return", "copy-or-deleted"}:
        execution, disposition = "does-not-create-thread", "excluded"
    elif exemplar["api_family"] == "std-async":
        policy = next(iter(policies)) if len(policies) == 1 else "unknown"
        if policy == "deferred":
            execution, disposition = "does-not-create-thread", "excluded"
        elif policy in {"default", "both"}:
            execution, disposition = "may-create-thread", "conditional-frontier"
        elif policy == "async":
            execution, disposition = "creates-thread", "adopted" if evidence_status == "dual-exact" else "frontier"
        else:
            execution, disposition, reason = "unknown", "frontier", reason or "launch-policy-unknown"
    else:
        execution = "creates-thread"
        disposition = "adopted" if evidence_status in {"dual-exact", "ir-exact"} else "frontier"
    callback_entries = [item["callback"].get("entry") for item in observations if item["callback"].get("entry")]
    callback = deepcopy(source["callback"] if source and source["callback"].get("entry") else
                        ir["callback"] if ir else source["callback"])
    if len({canonical(item) for item in callback_entries}) > 1:
        callback["entry"] = None
    if disposition == "adopted" and not callback.get("entry"):
        disposition, evidence_status, reason = "frontier", "ambiguous", reason or "callback-not-exact"
    evidence = sorted({piece for item in observations for piece in item["evidence"]})
    callsite = source["callsite_id"] if source else ir["callsite_id"]
    site_id = identity({"tu": exemplar["physical_tu_id"], "profile": exemplar["profile_id"],
                        "api": exemplar["api_family"], "model": exemplar["model_id"],
                        "callsite": callsite, "observations": sorted(item["id"] for item in observations)})
    return {
        "id": site_id, "physical_tu_id": exemplar["physical_tu_id"], "profile_id": exemplar["profile_id"],
        "api_family": exemplar["api_family"], "model_id": exemplar["model_id"], "callsite_id": callsite,
        "observations": sorted(item["id"] for item in observations), "evidence_status": evidence_status,
        "execution_semantics": execution, "root_disposition": disposition, "callback": callback,
        "object_lineage": (source or ir)["metadata"].get("object"),
        "handle_lineage": (ir or source)["metadata"].get("handle"),
        "guard": deepcopy((ir or source).get("guard")),
        "cardinality": ("repeated" if any(item["metadata"].get("cardinality") == "repeated" for item in observations)
                        else "merged" if any(item["metadata"].get("cardinality") == "merged" for item in observations)
                        else "single"),
        "evidence": evidence, "opposed": sorted(opposed), "reason": reason,
    }


def build_site_index(request, local_facts):
    sources = _merge_duplicate_observations(
        [item for facts in local_facts for item in facts["source_candidates"]])
    irs = _merge_duplicate_observations(
        [item for facts in local_facts for item in facts["ir_candidates"]])
    groups, used_ir = [], set()
    for source in sources:
        matches = [item for item in irs if item["id"] not in used_ir and _matches(source, item)]
        if len(matches) == 1:
            groups.append([source, matches[0]]); used_ir.add(matches[0]["id"])
        elif len(matches) > 1:
            groups.append([source, *matches])
            used_ir.update(item["id"] for item in matches)
        else:
            groups.append([source])
    groups.extend([[item] for item in irs if item["id"] not in used_ir])
    frontier = [item for facts in local_facts for item in facts["frontier"]]
    if not request["closed_scope"]:
        frontier.append(diagnostic(
            "thread-entry-open-scope", "开放 scope 可能遗漏外部线程创建点或 callback",
            "An open scope may omit external thread creation sites or callbacks"))
    planned_groups = len(groups)
    truncated = planned_groups > request["budgets"]["sites"]
    groups = groups[:request["budgets"]["sites"]]
    sites = sorted((_site_from(group) for group in groups), key=lambda item: item["id"])
    incomplete = [item for item in sites if item["root_disposition"] in {"frontier", "conditional-frontier"}]
    for site in incomplete:
        frontier.append(diagnostic(
            "thread-entry-site-incomplete", "线程入口证据不完整或执行语义为条件化",
            "Thread-entry evidence is incomplete or its execution semantics are conditional",
            suggestion="补齐 canonical type、AST/BC binding、callback、ABI 与 profile 证据",
            suggestion_en="Complete canonical type, AST/BC binding, callback, ABI, and profile evidence",
            source={"site_id": site["id"], "reason": site["reason"]}))
    if truncated:
        frontier.append(diagnostic("sites-budget-exhausted", "线程入口 site 预算已耗尽",
                                   "The thread-entry site budget is exhausted",
                                   source={"hit": planned_groups, "limit": request["budgets"]["sites"]}))
    if not sites:
        diagnostics = [diagnostic("thread-entry-site-zero", "完整分母中未发现线程入口 site",
                                  "No thread-entry site was found in the observed denominator")]
    else:
        diagnostics = []
    dependencies = sorted((dependency("ThreadEntryLocalFacts", item["physical_tu_id"], item)
                           for item in local_facts), key=lambda item: (item["kind"], item["id"]))
    status = "failed" if local_facts and all(item["status"] == "failed" for item in local_facts) else "partial" if frontier else "complete"
    counts = {name: sum(item["evidence_status"] == name for item in sites)
              for name in ("dual-exact", "ir-exact", "source-candidate", "ir-candidate", "ambiguous", "unsupported", "failed")}
    counts.update({"sites": len(sites), "adopted": sum(item["root_disposition"] == "adopted" for item in sites),
                   "conditional": sum(item["root_disposition"] == "conditional-frontier" for item in sites),
                   "excluded": sum(item["root_disposition"] == "excluded" for item in sites),
                   "planned": planned_groups, "completed": len(sites)})
    return thread_entry_document(
        "ThreadEntrySiteIndex", scope_id=request["scope_id"], request_hash=identity(request),
        status=status, sites=sites, counts=counts, dependencies=dependencies,
        diagnostics=diagnostics, frontier=frontier[:request["budgets"]["frontier_items"]], semantic_digest=None)


def build_root_overlay(request, sites, base_roots=None, base_plan=None):
    dependencies = [dependency("ThreadEntrySiteIndex", request["scope_id"], sites)]
    if base_roots is not None:
        dependencies.append(dependency("ExecutionRootIndex", base_roots["scope_id"], base_roots))
    if base_plan is not None:
        dependencies.append(dependency("RootDrivenAnalysisPlan", base_plan["scope_id"], base_plan))
    base_items = base_roots.get("roots", []) if base_roots else []
    roots, contexts, demands, adopted_from, frontier = [], {}, [], [], list(sites["frontier"])
    for site in sites["sites"]:
        if site["root_disposition"] != "adopted":
            continue
        existing = next((root for root in base_items
                         if root.get("creation_site_id") == site["id"] or
                         (root.get("entry") == site["callback"]["entry"] and
                          root.get("source_site_id") == site["callsite_id"])), None)
        if existing:
            adopted_from.append({"site_id": site["id"], "base_root_id": existing["id"]})
            continue
        context_id = identity({"callable": site["callback"]["entry"], "profile": site["profile_id"],
                               "model": site["model_id"]})
        contexts.setdefault(context_id, {"id": context_id, "entry": site["callback"]["entry"],
                                         "profile_id": site["profile_id"], "model_id": site["model_id"]})
        root_id = identity({"site": site["id"], "context": context_id, "guard": site["guard"]})
        roots.append({"id": root_id, "kind": site["api_family"], "entry": site["callback"]["entry"],
                      "creation_site_id": site["id"], "source_site_id": site["callsite_id"],
                      "context_id": context_id, "object_lineage": site["object_lineage"],
                      "handle_lineage": site["handle_lineage"], "guard": site["guard"],
                      "cardinality": site["cardinality"]})
        demands.append({"id": identity({"root": root_id, "entry": site["callback"]["entry"]}),
                        "root_id": root_id, "entry": site["callback"]["entry"],
                        "physical_tu_id": site["physical_tu_id"], "kind": "reachable-entry"})
    roots.sort(key=lambda item: item["id"]); demands.sort(key=lambda item: item["id"])
    context_values = sorted(contexts.values(), key=lambda item: item["id"])
    root_hit = len(roots)
    if root_hit > request["budgets"]["roots"]:
        roots = roots[:request["budgets"]["roots"]]
        root_ids = {item["id"] for item in roots}
        demands = [item for item in demands if item["root_id"] in root_ids]
        referenced_contexts = {item["context_id"] for item in roots}
        context_values = [item for item in context_values if item["id"] in referenced_contexts]
        frontier.append(diagnostic("roots-budget-exhausted", "线程入口 root 预算已耗尽",
                                   "The thread-entry root budget is exhausted",
                                   source={"hit": root_hit, "limit": request["budgets"]["roots"]}))
    context_hit = len(context_values)
    if context_hit > request["budgets"]["contexts"]:
        context_values = context_values[:request["budgets"]["contexts"]]
        context_ids = {item["id"] for item in context_values}
        roots = [item for item in roots if item["context_id"] in context_ids]
        root_ids = {item["id"] for item in roots}
        demands = [item for item in demands if item["root_id"] in root_ids]
        frontier.append(diagnostic("contexts-budget-exhausted", "线程入口 context 预算已耗尽",
                                   "The thread-entry context budget is exhausted",
                                   source={"hit": context_hit, "limit": request["budgets"]["contexts"]}))
    status = "partial" if frontier or sites["status"] != "complete" else "complete"
    site_ref = dependencies[0]
    base_roots_ref = next((item for item in dependencies if item["kind"] == "ExecutionRootIndex"), None)
    base_plan_ref = next((item for item in dependencies if item["kind"] == "RootDrivenAnalysisPlan"), None)
    return thread_entry_document(
        "ThreadEntryRootOverlay", scope_id=request["scope_id"], request_hash=identity(request),
        status=status, site_index=site_ref, base_execution_roots=base_roots_ref, base_plan=base_plan_ref,
        roots=roots, contexts=context_values, demands=demands,
        reconciliation={"base_roots": len(base_items), "overlay_roots": len(roots),
                        "adopted_from_base": sorted(adopted_from, key=lambda item: item["site_id"])},
        completeness={"sites": sites["status"], "roots": status,
                      "candidate_frontier": sum(item["root_disposition"] in {"frontier", "conditional-frontier"}
                                                for item in sites["sites"])},
        counts={"roots": len(roots), "contexts": len(context_values), "demands": len(demands),
                "adopted_from_base": len(adopted_from)},
        dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
        diagnostics=[], frontier=frontier[:request["budgets"]["frontier_items"]], semantic_digest=None)


def build_report(request, local_facts, sites, overlay, *, hits=0, misses=0):
    language_counts = {}
    members = {item["physical_tu_id"]: item for item in request["members"]}
    for standard in ("c11", "c17", "c++17", "c++20"):
        relevant = [item for item in local_facts if item["standard"] == standard]
        language_sites = [site for site in sites["sites"]
                          if members.get(site["physical_tu_id"], {}).get("standard") == standard]
        language_counts[standard] = {
            "planned": len(relevant), "completed": sum(item["status"] != "failed" for item in relevant),
            "failed": sum(item["status"] == "failed" for item in relevant),
            "sites": len(language_sites), "adopted": sum(item["root_disposition"] == "adopted" for item in language_sites),
            "abstention": sum(item["root_disposition"] in {"frontier", "conditional-frontier"} for item in language_sites),
        }
    status = "failed" if sites["status"] == "failed" else "partial" if sites["status"] == "partial" or overlay["status"] == "partial" else "complete"
    site_ref = dependency("ThreadEntrySiteIndex", request["scope_id"], sites)
    overlay_ref = dependency("ThreadEntryRootOverlay", request["scope_id"], overlay)
    dependencies = sorted([site_ref, overlay_ref], key=lambda item: (item["kind"], item["id"]))
    return thread_entry_document(
        "ThreadEntryDiscoveryReport", scope_id=request["scope_id"], request_hash=identity(request),
        status=status, exit_code=1 if status == "failed" else 2 if status == "partial" else 0,
        safety="not_evaluated", findings=None, site_index=site_ref, root_overlay=overlay_ref,
        language_counts=language_counts, evidence_counts=deepcopy(sites["counts"]),
        completeness={"local": {item["physical_tu_id"]: item["status"] for item in local_facts},
                      "sites": sites["status"], "overlay": overlay["status"]},
        dependencies=dependencies, diagnostics=[*sites["diagnostics"], *overlay["diagnostics"]],
        frontier=overlay["frontier"], cache={"hits": hits, "misses": misses}, semantic_digest=None)


def failed_report(code, detail, detail_en):
    item = diagnostic(code, detail, detail_en,
                      suggestion="修复请求、依赖或 worker 后重试",
                      suggestion_en="Fix the request, dependency, or worker and retry")
    return thread_entry_document(
        "ThreadEntryDiscoveryReport", scope_id=None, request_hash=None, status="failed", exit_code=1,
        safety="not_evaluated", findings=None, site_index=None, root_overlay=None,
        language_counts={}, evidence_counts={}, completeness={}, dependencies=[],
        diagnostics=[item], frontier=[item], cache={"hits": 0, "misses": 0}, semantic_digest=None)
