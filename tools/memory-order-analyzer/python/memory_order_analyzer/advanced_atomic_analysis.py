"""Bounded A6 atomic communication analysis.

The module deliberately consumes immutable P1/A1/A5/P3/P4/R1-R3 products and
produces independent sidecars.  It is not a general C/C++ happens-before solver.
"""

from collections import defaultdict
from copy import deepcopy
from itertools import permutations, product
import json
import time

from .advanced_atomic_contracts import (
    MODEL_ID,
    advanced_atomic_document,
    dependency,
    diagnostic,
)
from .contracts import canonical, identity


RELEASE_ORDERS = {"release", "acq_rel", "seq_cst"}
ACQUIRE_ORDERS = {"acquire", "acq_rel", "seq_cst"}
RMW_OPERATIONS = {"xchg", "add", "sub", "and", "or", "xor"}
ADVANCED_KINDS = {"load", "store", "atomicrmw", "cmpxchg", "fence", "initialization"}
SOURCE_TO_IR_KIND = {
    "atomic-c-load": "load", "atomic-c-store": "store", "atomic-c-rmw": "atomicrmw",
    "atomic-c-cas": "cmpxchg", "atomic-c-thread-fence": "fence",
    "atomic-c-signal-fence": "fence", "atomic-cpp-load": "load",
    "atomic-cpp-store": "store", "atomic-cpp-rmw": "atomicrmw",
    "atomic-cpp-cas": "cmpxchg", "atomic-cpp-thread-fence": "fence",
    "atomic-cpp-signal-fence": "fence",
}
SOURCE_ORDER = {"relaxed": "monotonic", "acquire": "acquire", "release": "release",
                "acq_rel": "acq_rel", "seq_cst": "seq_cst", "consume": "consume"}


def release_sequence_policy(language_standard):
    if language_standard in {"c11", "c17", "c++11", "c++14", "c++17"}:
        return "c11-c17-cpp17-v1"
    if language_standard == "c++20":
        return "cpp20-v1"
    if language_standard in {"compiler-default", "c89", "c99", "c++98", "c++03"}:
        return "legacy-no-iso-atomics-v1"
    raise ValueError(f"unsupported language standard: {language_standard}")


def _value(values, reference, bits_hint=None):
    if isinstance(reference, int) or (isinstance(reference, str) and reference.lstrip("-").isdigit()):
        number = int(reference)
        bits = bits_hint or 64
        return {"state": "exact", "bits": bits, "hex": f"{number & ((1 << bits) - 1):X}"}
    node = values.get(reference)
    if not node:
        return {"state": "unknown", "reason": "missing-value-node"}
    if node.get("kind") in {"integer", "zero"}:
        bits = node.get("bits") or 0
        raw = node.get("details", {}).get("hex", "0")
        return {"state": "exact", "bits": bits, "hex": raw.upper()}
    return {"state": "unknown", "reason": node.get("reason", "non-integer-value")}


def _integer(value):
    if not isinstance(value, dict) or value.get("state") != "exact":
        return None
    try:
        return int(value.get("hex", "0"), 16), int(value.get("bits") or 64)
    except (TypeError, ValueError):
        return None


def _rmw_transition(operation, old, operand):
    previous, argument = _integer(old), _integer(operand)
    if operation not in RMW_OPERATIONS or previous is None or argument is None:
        return None
    left, bits = previous
    right, right_bits = argument
    bits = max(bits, right_bits)
    mask = (1 << bits) - 1
    result = {"xchg": right, "add": left + right, "sub": left - right,
              "and": left & right, "or": left | right, "xor": left ^ right}[operation] & mask
    return {"state": "exact", "bits": bits, "hex": f"{result:X}"}


def _address_key(address, artifact, function):
    if not isinstance(address, dict):
        return None, None
    kind = address.get("kind")
    if kind == "global":
        return f"global:{address.get('symbol')}", 0
    if kind in {"alloca", "argument"}:
        return f"{artifact}:{function}:{address.get('object')}", 0
    if kind == "constant_gep":
        base, offset = _address_key(address.get("base"), artifact, function)
        indices = address.get("indices", [])
        return (base, None) if base is None else (base, identity(indices) if offset is None else offset)
    return None, None


def _range(event, artifact):
    ranges = event.get("ranges") or []
    if event.get("kind") == "fence":
        return None, None, None, None
    object_key, offset = _address_key(event.get("address"), artifact, event["function"])
    access = ranges[0] if ranges else {}
    if object_key is None and access.get("address_ref"):
        object_key = f"{artifact}:{event['function']}:{access['address_ref']}"
        offset = 0
    size = access.get("size", {})
    size_bytes = size.get("bytes") if size.get("status") in {"exact", "known"} else None
    try:
        size_bytes = int(size_bytes) if size_bytes is not None else None
    except (TypeError, ValueError):
        size_bytes = None
    if not isinstance(offset, int):
        offset = None
    return object_key, offset, size_bytes, access.get("address_space")


def _source_id(event):
    return event.get("id") or identity(event)


def _attribute(attributes, prefix):
    return next((item[len(prefix):] for item in attributes if item.startswith(prefix)), None)


def _location_keys(value):
    result = set()
    if isinstance(value, dict):
        if value.get("file") and value.get("line") is not None:
            result.add((str(value["file"]).replace("\\", "/"), value.get("line")))
        for child in value.values():
            result.update(_location_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_location_keys(child))
    return result


def _source_matches(event, construct):
    event_locations = _location_keys(event.get("source", {}))
    construct_locations = _location_keys(construct.get("source", {}))
    if event_locations and construct_locations:
        return bool(event_locations.intersection(construct_locations))
    symbol = construct.get("enclosing_symbol")
    function = event.get("function")
    return bool(symbol and isinstance(function, str) and
                function.split(":symbol:")[-1] == symbol)


def _source_point(value):
    source = value.get("source", {}) if isinstance(value, dict) else {}
    for key in ("spelling", "expansion"):
        point = source.get(key, {})
        if point.get("file") and point.get("line") is not None:
            return str(point["file"]).replace("\\", "/"), int(point["line"])
    return None


def _enclosing_symbol(source_node, nodes):
    point = _source_point(source_node)
    if point is None:
        return None
    file_name, line = point
    candidates = []
    for node in nodes.values():
        if node.get("kind") not in {"function", "method", "constructor", "destructor"}:
            continue
        source = node.get("source", {})
        begin = source.get("spelling", source.get("expansion", {}))
        end = source.get("spelling_end", source.get("expansion_end", begin))
        if str(begin.get("file", "")).replace("\\", "/") != file_name:
            continue
        if begin.get("line") is None or end.get("line") is None:
            continue
        if int(begin["line"]) <= line <= int(end["line"]):
            candidates.append((int(end["line"]) - int(begin["line"]), node))
    if not candidates:
        return None
    node = min(candidates, key=lambda item: item[0])[1]
    return node.get("mangled_name") or node.get("name") or node.get("qualified_name")


def _thread_lookup(thread_graph):
    result = defaultdict(list)
    if not thread_graph:
        return result
    for effect in thread_graph.get("effects", []):
        source = effect.get("source") or {}
        marker = (source.get("artifact_key"), source.get("id"))
        result[marker].append((effect.get("thread_context_id"), effect.get("thread_instance_id"), effect.get("id")))
    return result


def _event_base(module, event, *, context_id=None, instance_id=None, suffix="single",
                 provenance=None):
    artifact = module["artifact_key"]
    object_key, offset, size, address_space = _range(event, artifact)
    if event.get("_a6_object_key") is not None:
        object_key = event["_a6_object_key"]
        offset = event.get("_a6_offset", 0)
        size = event.get("_a6_size")
        address_space = event.get("_a6_address_space", 0)
    reason = None
    status = "exact"
    if event["kind"] != "fence" and (object_key is None or offset is None or size is None or address_space is None):
        status, reason = "unknown", "atomic-object-identity-unknown"
    if provenance and object_key in provenance:
        binding = provenance[object_key]
        if binding.get("resolution") == "must" and len(binding.get("candidates", [])) == 1:
            object_key = binding["candidates"][0]
        else:
            status, reason = "unknown", "atomic-object-identity-unknown"
    return {
        "id": identity({"layer": "advanced-atomic-event-v1", "artifact": artifact,
                        "source": event["id"], "context": context_id, "instance": instance_id,
                        "outcome": suffix}),
        "artifact_key": artifact,
        "function_id": event["function"],
        "context_id": context_id,
        "thread_instance_id": instance_id,
        "source_id": _source_id(event),
        "kind": {"atomicrmw": "rmw", "cmpxchg": "cas"}.get(event["kind"], event["kind"]),
        "outcome": suffix,
        "object_key": object_key,
        "offset_bytes": offset,
        "size_bytes": size,
        "address_space": address_space,
        "ordering": event.get("ordering"),
        "failure_ordering": event.get("failure_ordering"),
        "syncscope": event.get("syncscope"),
        "operation": event.get("operation"),
        "compare_ref": event.get("inputs", {}).get("compare"),
        "desired_ref": event.get("inputs", {}).get("new"),
        "observed_ref": event.get("result_ref"),
        "value": None,
        "weak": bool(event.get("weak", False)),
        "guards": [],
        "multiplicity": "single",
        "mo_member": False,
        "read_effect": False,
        "write_effect": False,
        "status": status,
        "reason": reason,
        "evidence": [f"p1:{artifact}:{event['id']}"],
    }


def _provenance_map(provenance_graph):
    result = {}
    if not provenance_graph:
        return result
    for node in provenance_graph.get("nodes", provenance_graph.get("bindings", [])):
        key = node.get("value_id") or node.get("source_object") or node.get("id")
        candidates = node.get("candidates", [])
        normalized = []
        for candidate in candidates:
            normalized.append(candidate if isinstance(candidate, str) else candidate.get("object_id") or candidate.get("id"))
        result[key] = {"resolution": node.get("certainty", node.get("resolution")),
                       "candidates": [item for item in normalized if item]}
    return result


def _walk_demand_keys(value, result):
    if isinstance(value, dict):
        artifact = value.get("artifact_key")
        function = value.get("function_id") or value.get("function")
        context = value.get("context_id")
        if artifact and function:
            result.add((artifact, function, context))
        for child in value.values():
            _walk_demand_keys(child, result)
    elif isinstance(value, list):
        for child in value:
            _walk_demand_keys(child, result)


def _demand_keys(documents):
    result = set()
    for document in documents:
        if document:
            _walk_demand_keys(document, result)
    return result


def _is_demanded(demanded, artifact, function, context):
    return any(
        key_artifact == artifact and key_function == function and
        (key_context is None or context is None or key_context == context)
        for key_artifact, key_function, key_context in demanded
    )


def _mhp_relation(thread_graph, left, right):
    if left is None or right is None:
        return None, None
    if left == right:
        return "same-instance", None
    pair = {left, right}
    for item in (thread_graph or {}).get("mhp", []):
        item_pair = {item.get("left"), item.get("right")}
        if item_pair != pair:
            continue
        raw = item.get("relation", item.get("disposition"))
        normalized = {
            "may_parallel": "may-parallel", "may-parallel": "may-parallel",
            "parallel-possible": "may-parallel",
            "not_parallel": "not-parallel", "not-parallel": "not-parallel",
            "unknown": "unknown",
        }.get(raw, "unknown")
        return normalized, item.get("id")
    return None, None


def _function_shard_module(shard):
    facts = shard.get("facts") or {}
    events = []
    for event in facts.get("atomic_events", []):
        kind = {"rmw": "atomicrmw", "cas": "cmpxchg"}.get(event.get("kind"), event.get("kind"))
        object_value = event.get("object")
        object_key = None
        if isinstance(object_value, str):
            if object_value.startswith("@"):
                object_key = "global:" + object_value[1:]
            elif ":symbol:" in object_value and ":" not in object_value.split(":symbol:", 1)[1]:
                object_key = "global:" + object_value.split(":symbol:", 1)[1]
            else:
                object_key = object_value
        events.append({
            "id": event["id"], "kind": kind, "function": event.get("function", shard["function_id"]),
            "block": event.get("block"), "source": event.get("location", {"inline_chain": []}),
            "address": None, "inputs": event.get("inputs", {}), "result_ref": event.get("result_ref"),
            "ranges": [], "range_status": "available", "ordering": event.get("ordering"),
            "failure_ordering": event.get("failure_ordering"), "success_ordering": event.get("ordering"),
            "syncscope": event.get("syncscope"), "operation": event.get("operation"),
            "weak": bool(event.get("weak", False)), "guards": event.get("guards", []),
            "multiplicity": event.get("multiplicity", "single"), "_a6_object_key": object_key,
            "_a6_size": event.get("size_bytes"), "_a6_address_space": event.get("address_space", 0),
        })
    return {
        "kind": "A6FunctionSemanticShardView", "artifact_key": shard["artifact_key"],
        "values": facts.get("values", []), "globals": [], "events": events,
        "_a6_context_id": shard.get("context_id"), "_a6_dependency": shard,
        "_a6_status": shard.get("status"),
    }


def _prepared_modules(modules):
    result = []
    for module in modules:
        if module.get("kind") == "AdvancedAtomicFunctionFacts":
            result.append(_function_shard_module(module))
        else:
            result.append(module)
    return result


def extract_local_facts(modules, *, scope_id, language_standard, thread_graph=None,
                        provenance_graph=None, budgets=None, demand_documents=(),
                        source_constructs=None):
    """Normalize immutable ModuleFacts into outcome-aware A6 events."""
    started_wall, started_cpu = time.monotonic(), time.process_time()
    protocol_budgets = budgets or {}
    event_limit = protocol_budgets.get("atomic_events", 100000)
    lookup = _thread_lookup(thread_graph)
    provenance = _provenance_map(provenance_graph)
    events, order, frontier, dependencies = [], [], [], []
    source_candidates = [item for item in (source_constructs or {}).get("constructs", [])
                         if item.get("status") == "exact"]
    adopted_source_operations = set()
    demand_supplied = any(item is not None for item in demand_documents)
    demanded = _demand_keys(demand_documents)
    if demand_supplied and not demanded:
        frontier.append(diagnostic("analysis-demand-incomplete", "A6 需求图没有可分析的函数上下文",
                                   "A6 demand inputs contain no analyzable function/context"))
    for module in sorted(_prepared_modules(modules), key=lambda item: item["artifact_key"]):
        artifact = module["artifact_key"]
        dependency_value = module.get("_a6_dependency", module)
        dependency_kind = "AdvancedAtomicFunctionFacts" if module.get("_a6_dependency") else "ModuleFacts"
        dependencies.append(dependency(dependency_kind, artifact, dependency_value))
        if module.get("_a6_status") not in {None, "complete"}:
            frontier.append(diagnostic("demanded-function-shard-incomplete",
                                       "R3 A6 函数 shard 不完整", "R3 A6 function shard is incomplete"))
        values = {item["id"]: item for item in module.get("values", [])}
        emitted = []
        module_events = list(module.get("events", []))
        for call in module.get("calls", []):
            target = str(call.get("target", call.get("callee", "")))
            if "__atomic_" in target or "libatomic" in target:
                frontier.append(diagnostic(
                    "atomic-runtime-call-unsupported",
                    "检测到未经 profile 建模的原子运行时调用",
                    "An atomic runtime call lacks a verified broker profile",
                    references=[call.get("id", target)]))
        global_events = {}
        for raw in module_events:
            address = raw.get("address") or {}
            atomic_access = (raw.get("kind") in {"atomicrmw", "cmpxchg"} or
                             raw.get("kind") in {"load", "store"} and
                             raw.get("ordering") not in {None, "not_atomic", "not-atomic"})
            if address.get("kind") == "global" and atomic_access:
                global_events.setdefault(address.get("symbol"), raw)
        for global_value in module.get("globals", []):
            initializer = global_value.get("initializer") or {}
            template = global_events.get(global_value.get("name")) or global_events.get(global_value.get("id"))
            explicit_context = module.get("_a6_context_id")
            template_demanded = template and (
                not demand_supplied or
                _is_demanded(demanded, artifact, template.get("function"), explicit_context))
            if template_demanded and initializer.get("value_ref"):
                module_events.append({
                    "id": f"{global_value['id']}:initialization", "kind": "initialization",
                    "function": "<global-initializer>", "block": "<initialization>",
                    "source": {"inline_chain": []}, "address": deepcopy(template.get("address")),
                    "inputs": {"value": initializer["value_ref"]}, "result_ref": None,
                    "ranges": deepcopy(template.get("ranges", [])),
                    "range_status": template.get("range_status", "available"),
                    "ordering": "initialization", "syncscope": "system",
                })
        for raw in module_events:
            if raw.get("kind") not in ADVANCED_KINDS:
                continue
            if raw.get("kind") in {"load", "store"} and raw.get("ordering") in {
                    None, "not_atomic", "not-atomic"}:
                continue
            matching_source = [item for item in source_candidates
                               if item.get("ir_kind") == raw.get("kind") and
                               _source_matches(raw, item)]
            def order_matches(construct):
                if construct.get("ordering") is None:
                    return True
                if raw.get("kind") == "cmpxchg":
                    return (raw.get("success_ordering") == construct["ordering"] and
                            (construct.get("failure_ordering") is None or
                             raw.get("failure_ordering") == construct["failure_ordering"]))
                return raw.get("ordering") == construct["ordering"]

            ordered_source = [item for item in matching_source if order_matches(item)]
            if matching_source and not ordered_source and all(
                    item.get("ordering") is not None for item in matching_source):
                continue
            if len(ordered_source) > 1:
                frontier.append(diagnostic(
                    "source-dispatcher-binding-ambiguous",
                    "多个源码原子构造可对应同一个 IR dispatcher 事件",
                    "Multiple source atomic constructs can bind the same IR dispatcher event",
                    references=[raw.get("id"), *[item["id"] for item in ordered_source]]))
            adopted_construct = ordered_source[0] if len(ordered_source) == 1 else None
            if adopted_construct is not None and adopted_construct.get("ordering") is not None:
                marker = (artifact, adopted_construct["id"], raw.get("kind"), raw.get("operation"),
                          raw.get("success_ordering", raw.get("ordering")), raw.get("failure_ordering"))
                if marker in adopted_source_operations:
                    continue
                adopted_source_operations.add(marker)
            explicit_context = module.get("_a6_context_id")
            if demand_supplied and raw.get("kind") != "initialization" and not _is_demanded(
                    demanded, artifact, raw.get("function"), explicit_context):
                continue
            bindings = lookup.get((artifact, raw.get("id"))) or [(explicit_context, None, None)]
            for context_id, instance_id, effect_id in bindings:
                base = _event_base(module, raw, context_id=context_id, instance_id=instance_id,
                                   provenance=provenance)
                if effect_id:
                    base["evidence"].append(f"p3:{effect_id}")
                if adopted_construct is not None:
                    base["evidence"].append(f"ast:{adopted_construct['id']}")
                base["guards"] = deepcopy(raw.get("guards", []))
                base["multiplicity"] = raw.get("multiplicity", "single")
                kind = base["kind"]
                if kind == "load":
                    base.update(read_effect=True, ordering=raw.get("ordering"),
                                value=_value(values, raw.get("result_ref"),
                                             (base["size_bytes"] or 0) * 8 or None))
                    variants = [base]
                elif kind in {"store", "initialization"}:
                    reference = raw.get("inputs", {}).get("value")
                    base.update(write_effect=True, mo_member=True, ordering=raw.get("ordering"),
                                value=_value(values, reference, (base["size_bytes"] or 0) * 8 or None))
                    variants = [base]
                elif kind == "rmw":
                    reference = raw.get("inputs", {}).get("value")
                    base.update(read_effect=True, write_effect=True, mo_member=True,
                                ordering=raw.get("ordering"),
                                value=_value(values, reference, (base["size_bytes"] or 0) * 8 or None))
                    if raw.get("operation") not in RMW_OPERATIONS:
                        base.update(status="unknown", reason="rmw-value-transition-unknown")
                    variants = [base]
                elif kind == "cas":
                    compare_value = _value(values, raw.get("inputs", {}).get("compare"),
                                           (base["size_bytes"] or 0) * 8 or None)
                    success = deepcopy(base)
                    success.update(outcome="success", read_effect=True, write_effect=True, mo_member=True,
                                   ordering=raw.get("success_ordering"),
                                   value=_value(values, raw.get("inputs", {}).get("new"),
                                                (base["size_bytes"] or 0) * 8 or None))
                    success["guards"] = [*base["guards"], {"kind": "cas-success",
                                                           "compare": compare_value}]
                    success["id"] = identity({"base": base["id"], "outcome": "success"})
                    failure = deepcopy(base)
                    failure.update(outcome="failure", read_effect=True, write_effect=False, mo_member=False,
                                   ordering=raw.get("failure_ordering"), value=None,
                                   reason=base["reason"])
                    failure["guards"] = [*base["guards"], {"kind": "cas-failure",
                                                           "compare": compare_value}]
                    failure["id"] = identity({"base": base["id"], "outcome": "failure"})
                    variants = [success, failure]
                    if raw.get("weak"):
                        spurious = deepcopy(failure)
                        spurious.update(outcome="spurious-failure", reason="weak-cas-spurious-path")
                        spurious["id"] = identity({"base": base["id"], "outcome": "spurious-failure"})
                        variants.append(spurious)
                else:
                    base.update(object_key=None, offset_bytes=None, size_bytes=None,
                                address_space=None, ordering=raw.get("ordering"), value=None)
                    variants = [base]
                    if base["syncscope"] not in {None, "system"}:
                        code = ("signal-fence-interthread-unsupported" if base["syncscope"] in {"singlethread", "single-thread"}
                                else "atomic-syncscope-unsupported")
                        base.update(status="unknown", reason=code)
                for item in variants:
                    if item.get("ordering") == "consume":
                        item.update(status="unknown", reason="consume-ordering-unsupported")
                    if item.get("syncscope") not in {None, "system"} and item["kind"] != "fence":
                        item.update(status="unknown", reason="atomic-syncscope-unsupported")
                    if item.get("multiplicity") in {"repeated", "unknown"} and item["kind"] == "cas":
                        item.update(status="unknown", reason="cas-loop-unsupported")
                    if len(item.get("guards", [])) > protocol_budgets.get("guards", 100000):
                        item.update(status="unknown", reason="guard-budget-exhausted")
                    if len(events) >= event_limit:
                        frontier.append(diagnostic("atomic-event-budget-exhausted",
                                                   "原子事件预算耗尽", "Atomic event budget exhausted",
                                                   references=[item["source_id"]]))
                        break
                    events.append(item)
                    emitted.append(item)
                    if time.monotonic() - started_wall > protocol_budgets.get("worker_seconds", 120):
                        frontier.append(diagnostic("worker-time-budget-exhausted",
                                                   "局部事实提取时间预算耗尽",
                                                   "Local fact extraction time budget exhausted"))
                        break
                    if time.process_time() - started_cpu > protocol_budgets.get("worker_seconds", 120):
                        frontier.append(diagnostic("worker-cpu-budget-exhausted",
                                                   "局部事实提取 CPU 预算耗尽",
                                                   "Local fact extraction CPU budget exhausted"))
                        break
        by_block = defaultdict(list)
        for item in emitted:
            source = next((raw for raw in module.get("events", []) if raw.get("id") == item["source_id"]), None)
            if source:
                by_block[(item["function_id"], source.get("block"))].append(item)
        for members in by_block.values():
            members.sort(key=lambda item: item["source_id"])
            for before, after in zip(members, members[1:]):
                if before["source_id"] == after["source_id"]:
                    continue
                order.append({"id": identity({"before": before["id"], "after": after["id"]}),
                              "before": before["id"], "after": after["id"],
                              "relation": "must-before", "reason": "same-basic-block-ir-order"})
    if source_constructs:
        frontier.extend(deepcopy(source_constructs.get("frontier", [])))
        if source_constructs.get("constructs") and not events:
            frontier.append(diagnostic("ast-only-runtime-binding-unavailable",
                                       "源码原子构造没有对应的运行时 IR 事件",
                                       "Source atomic constructs have no corresponding runtime IR event"))
    if thread_graph is None and any(item["kind"] != "initialization" for item in events):
        frontier.append(diagnostic("thread-instance-binding-unknown",
                                   "缺少 P3 ThreadInstance/MHP 输入",
                                   "P3 ThreadInstance/MHP input is unavailable"))
    encoded_events = len(json.dumps(events, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    if encoded_events > protocol_budgets.get("worker_output_bytes", 1 << 30):
        frontier.append(diagnostic("worker-output-budget-exhausted",
                                   "局部事实输出预算耗尽",
                                   "Local fact output budget exhausted"))
    for item in events:
        if item["reason"]:
            frontier.append(diagnostic(item["reason"], "高级原子事件证据不完整",
                                       "Advanced atomic event evidence is incomplete",
                                       references=[item["id"]]))
    relevant = any(item["relevant"] for item in frontier)
    return advanced_atomic_document(
        "AdvancedAtomicLocalFacts", scope_id=scope_id, language_standard=language_standard,
        dependencies=dependencies, events=sorted(events, key=lambda item: item["id"]),
        local_order=sorted(order, key=lambda item: item["id"]),
        status="partial" if relevant else "complete", frontier=frontier, diagnostics=[])


def classify_source_constructs(source_facts, *, scope_id, language_standard):
    constructs, frontier, dependencies = [], [], []
    cpp = language_standard.startswith("c++")
    for facts in source_facts:
        physical = facts.get("physical_tu_id", identity(facts))
        dependencies.append(dependency("SourceSemanticFacts", physical, facts))
        nodes = {item["id"]: item for item in facts.get("nodes", [])}
        for relation in facts.get("relations", []):
            if relation.get("kind") not in {"atomic", "atomic-c-load", "atomic-c-store", "atomic-c-rmw",
                                             "atomic-c-cas", "atomic-c-thread-fence", "atomic-c-signal-fence",
                                             "atomic-cpp-load", "atomic-cpp-store", "atomic-cpp-rmw",
                                             "atomic-cpp-cas", "atomic-cpp-thread-fence", "atomic-cpp-signal-fence"}:
                continue
            source = nodes.get(relation["from"], {})
            target = nodes.get(relation.get("to"), {})
            qualified = target.get("qualified_name", "")
            canonical_type = source.get("canonical_type", "")
            attributes = source.get("attributes", [])
            precise_kind = relation["kind"] if relation["kind"] != "atomic" else None
            exact = precise_kind is not None
            if cpp:
                semantic_std = (qualified.startswith("std::") or qualified.startswith("std::__1::")) and (
                    "atomic" in qualified or "atomic" in canonical_type)
                exact = exact and semantic_std
            else:
                exact = exact and source.get("kind") == "atomic-expression"
            construct = {
                "id": identity({"layer": "atomic-source-construct-v1", "tu": physical,
                                "source": relation["from"], "relation": relation["id"]}),
                "physical_tu_id": physical, "source_node_id": relation["from"],
                "selected_declaration_id": relation.get("to"), "operation": precise_kind,
                "spelled_type": canonical_type, "canonical_type": canonical_type,
                "qualified_declaration": qualified, "attributes": attributes,
                "source": deepcopy(source.get("source", relation.get("source", {}))),
                "enclosing_symbol": _enclosing_symbol(source, nodes),
                "ir_kind": SOURCE_TO_IR_KIND.get(precise_kind),
                "ordering": SOURCE_ORDER.get(_attribute(attributes, "atomic-order:")),
                "failure_ordering": SOURCE_ORDER.get(_attribute(attributes, "atomic-failure-order:")),
                "status": "exact" if exact else "candidate",
                "reason": None if exact else "atomic-source-ir-binding-ambiguous",
                "evidence": [relation["id"]],
            }
            source_operation = _attribute(attributes, "atomic-operation:") or ""
            if exact and construct["ordering"] is None and "init" not in source_operation:
                construct["ordering"] = "seq_cst"
            constructs.append(construct)
            if precise_kind in {"atomic-c-signal-fence", "atomic-cpp-signal-fence"}:
                construct["status"] = "candidate"
                construct["reason"] = "signal-fence-interthread-unsupported"
                frontier.append(diagnostic(
                    "signal-fence-interthread-unsupported",
                    "atomic_signal_fence 不提供线程间同步证明",
                    "atomic_signal_fence does not provide inter-thread synchronization evidence",
                    references=[construct["id"]]))
            if not exact:
                frontier.append(diagnostic("atomic-source-ir-binding-ambiguous",
                                           "原子源码构造缺少 canonical operation 或标准库绑定",
                                           "Atomic source construct lacks canonical operation or library binding",
                                           references=[construct["id"]]))
    return advanced_atomic_document(
        "AtomicSourceConstructFacts", scope_id=scope_id, language_standard=language_standard,
        dependencies=dependencies, constructs=constructs,
        status="partial" if frontier else "complete", frontier=frontier, diagnostics=[])


def _overlap(left, right):
    if left["object_key"] is None or left["object_key"] != right["object_key"]:
        return False
    fields = (left["offset_bytes"], left["size_bytes"], right["offset_bytes"], right["size_bytes"])
    if any(value is None for value in fields):
        return False
    lo, ls, ro, rs = fields
    return lo < ro + rs and ro < lo + ls


def _before_closure(order, *, iteration_limit=None, budget_frontier=None):
    edges = defaultdict(set)
    for item in order:
        edges[item["before"]].add(item["after"])
    changed = True
    iteration = 0
    while changed:
        if iteration_limit is not None and iteration >= iteration_limit:
            if budget_frontier is not None:
                budget_frontier.append(diagnostic("local-order-closure-budget-exhausted",
                                                  "局部顺序闭包预算耗尽",
                                                  "Local-order closure budget exhausted"))
            break
        iteration += 1
        changed = False
        for before in list(edges):
            expanded = set().union(*(edges.get(item, set()) for item in list(edges[before])))
            if not expanded.issubset(edges[before]):
                edges[before].update(expanded)
                changed = True
    return edges


def _dedupe_diagnostics(items):
    result = {}
    for item in items:
        marker = canonical({key: item.get(key) for key in ("code", "references", "relevant")})
        result.setdefault(marker, item)
    return list(result.values())


def _frontier_affects(read, incoming, frontier, by_id):
    related = {read["id"], read.get("source_id"), read.get("object_key")}
    for edge in incoming:
        related.add(edge["id"])
        for key in ("write_event", "read_event"):
            event = by_id.get(edge[key], {})
            related.update((edge[key], event.get("source_id"), event.get("object_key")))
    related.discard(None)
    for item in frontier:
        if not item.get("relevant"):
            continue
        references = set(item.get("references", []))
        if not references or references.intersection(related):
            return True
    return False


def _is_write(event):
    return event["write_effect"] and event["mo_member"]


def _is_read(event):
    return event["read_effect"]


def _compatible(write, read):
    if not _overlap(write, read):
        return False
    if write.get("thread_instance_id") is not None and write.get("thread_instance_id") == read.get("thread_instance_id"):
        return False
    if read["kind"] == "cas":
        compare = next((item.get("compare") for item in read.get("guards", [])
                        if isinstance(item, dict) and item.get("kind", "").startswith("cas-")), None)
        exact_compare = _integer(compare)
        exact_write = _integer(write.get("value"))
        if exact_compare is None or exact_write is None:
            return True
        equal = exact_compare == exact_write
        if read["outcome"] == "success":
            return equal
        if read["outcome"] == "failure":
            return not equal
        return True
    return True


def _communication_relation(write, read, thread_graph, frontier):
    if write["kind"] == "initialization":
        return True
    relation, evidence = _mhp_relation(
        thread_graph, write.get("thread_instance_id"), read.get("thread_instance_id"))
    if relation == "may-parallel":
        return True
    if relation in {"same-instance", "not-parallel"}:
        return False
    frontier.append(diagnostic(
        "mhp-unknown", "原子通信两端的可能并行关系未知",
        "Possible parallelism between atomic communication endpoints is unknown",
        references=[item for item in (write["id"], read["id"], evidence) if item]))
    return False


def _mo_orders(events, before, budgets, frontier):
    modifications = [item for item in events if _is_write(item)]
    if len(modifications) > budgets.get("mo_nodes", 100000):
        frontier.append(diagnostic("modification-order-search-incomplete",
                                   "modification order 节点预算耗尽",
                                   "Modification-order node budget exhausted",
                                   references=[item["id"] for item in modifications[:8]]))
        return []
    if len(modifications) > 8:
        frontier.append(diagnostic("modification-order-search-incomplete",
                                   "原子修改过多，首版不枚举其 modification order",
                                   "Too many atomic modifications for the bounded v1 enumerator",
                                   references=[item["id"] for item in modifications[:8]]))
        return []
    valid = []
    branch_limit = budgets.get("mo_branches", 200000)
    for ordinal, candidate in enumerate(permutations(modifications)):
        if ordinal >= branch_limit:
            frontier.append(diagnostic("modification-order-search-incomplete",
                                       "modification order 分支预算耗尽",
                                       "Modification-order branch budget exhausted"))
            break
        positions = {item["id"]: index for index, item in enumerate(candidate)}
        if any(positions[left] >= positions[right] for left in positions for right in before.get(left, ())
               if right in positions):
            continue
        valid.append([item["id"] for item in candidate])
    return valid


def _release_sequences(order, by_id, policy):
    result = []
    for position, identifier in enumerate(order):
        head = by_id[identifier]
        if head.get("ordering") not in RELEASE_ORDERS:
            continue
        members = [identifier]
        for follower_id in order[position + 1:]:
            follower = by_id[follower_id]
            if follower["kind"] in {"rmw", "cas"} and follower["outcome"] != "failure":
                members.append(follower_id)
                continue
            same_thread = head.get("thread_instance_id") == follower.get("thread_instance_id")
            if policy == "c11-c17-cpp17-v1" and same_thread:
                members.append(follower_id)
                continue
            break
        result.append({"id": identity({"head": identifier, "members": members, "policy": policy}),
                       "head": identifier, "members": members, "policy": policy})
    return result


def _fence_pairings(events, rf_edges, before):
    by_id = {item["id"]: item for item in events}
    fences = [item for item in events if item["kind"] == "fence"]
    pairings = []
    for edge in rf_edges:
        write, read = by_id[edge["write_event"]], by_id[edge["read_event"]]
        release_fences = [item for item in fences if item["ordering"] in RELEASE_ORDERS and
                          item["thread_instance_id"] == write["thread_instance_id"] and
                          item["id"] in before and write["id"] in before[item["id"]]]
        acquire_fences = [item for item in fences if item["ordering"] in ACQUIRE_ORDERS and
                          item["thread_instance_id"] == read["thread_instance_id"] and
                          read["id"] in before and item["id"] in before[read["id"]]]
        candidates = []
        candidates.extend(("fence-fence", left, right) for left in release_fences for right in acquire_fences)
        if read["ordering"] in ACQUIRE_ORDERS:
            candidates.extend(("fence-atomic", left, read) for left in release_fences)
        if write["ordering"] in RELEASE_ORDERS:
            candidates.extend(("atomic-fence", write, right) for right in acquire_fences)
        for kind, release, acquire in candidates:
            if release.get("syncscope") not in {None, "system"} or acquire.get("syncscope") not in {None, "system"}:
                continue
            pairings.append({"id": identity({"kind": kind, "release": release["id"],
                                              "acquire": acquire["id"], "rf": edge["id"]}),
                             "kind": kind, "release": release["id"], "acquire": acquire["id"],
                             "carrier_write": write["id"], "carrier_read": read["id"],
                             "rf_edge": edge["id"], "status": "proved"})
    return pairings


def build_communication_graph(local_facts, *, scope_id, language_standard, budgets,
                              closed_scope=True, thread_graph=None):
    started_wall, started_cpu = time.monotonic(), time.process_time()
    events = deepcopy(local_facts["events"])
    frontier = deepcopy(local_facts["frontier"])
    if not closed_scope:
        frontier.append(diagnostic("reads-from-candidate-set-open", "分析 scope 未闭合",
                                   "Analysis scope is open"))
    before = _before_closure(local_facts["local_order"],
                             iteration_limit=budgets.get("scc_iterations", 32),
                             budget_frontier=frontier)
    by_object = defaultdict(list)
    for event in events:
        if event["object_key"] is not None:
            by_object[event["object_key"]].append(event)
    sc_objects = {item["object_key"] for item in events
                  if item.get("ordering") == "seq_cst" and item.get("object_key") is not None}
    if len(sc_objects) > 1:
        frontier.append(diagnostic("seq-cst-global-order-unsupported",
                                   "多个对象需要全局 seq_cst 全序，超出 A6 受限模型",
                                   "Multiple objects require a global seq_cst total order outside the A6 model"))
    if len(by_object) > budgets["objects"]:
        frontier.append(diagnostic("atomic-object-budget-exhausted", "原子对象预算耗尽",
                                   "Atomic object budget exhausted"))
    rf_edges, mo_orders, releases = [], [], []
    all_assignments = [{"rf_edges": [], "mo_orders": []}]
    by_id = {item["id"]: item for item in events}
    for object_index, (object_key, members) in enumerate(sorted(by_object.items())):
        if object_index >= budgets["objects"]:
            break
        if time.monotonic() - started_wall > budgets.get("request_seconds", 600) or \
                time.process_time() - started_cpu > budgets.get("request_seconds", 600):
            frontier.append(diagnostic("request-time-budget-exhausted", "A6 求解时间预算耗尽",
                                       "A6 solver time budget exhausted"))
            break
        writes = [item for item in members if _is_write(item)]
        reads = [item for item in members if _is_read(item)]
        object_edges = []
        for read in reads:
            for write in writes:
                if write["id"] == read["id"] or not _compatible(write, read):
                    continue
                if not _communication_relation(write, read, thread_graph, frontier):
                    continue
                if read["id"] in before.get(write["id"], set()) or write["id"] not in before.get(read["id"], set()):
                    edge = {"id": identity({"object": object_key, "write": write["id"], "read": read["id"]}),
                            "object_key": object_key, "write_event": write["id"],
                            "read_event": read["id"], "status": "candidate", "reason": "bounded-rf-candidate"}
                    if len(rf_edges) >= budgets["rf_edges"]:
                        frontier.append(diagnostic("reads-from-candidate-set-open", "reads-from edge 预算耗尽",
                                                   "Reads-from edge budget exhausted"))
                        break
                    object_edges.append(edge)
                    rf_edges.append(edge)
        read_groups = []
        grouped_cas = defaultdict(list)
        for read in reads:
            if read["kind"] == "cas":
                grouped_cas[read["source_id"]].append(read)
            else:
                read_groups.append([read])
        read_groups.extend(grouped_cas[key] for key in sorted(grouped_cas))
        object_assignments = []
        variant_sets = product(*read_groups) if read_groups else [()]
        for selected_reads in variant_sets:
            edge_choices = []
            for read in selected_reads:
                candidates = [edge for edge in object_edges if edge["read_event"] == read["id"]]
                if not candidates:
                    frontier.append(diagnostic("reads-from-candidate-set-open", "读取没有闭合的 reads-from 候选",
                                               "Read has no closed reads-from candidate", references=[read["id"]]))
                    edge_choices = []
                    break
                edge_choices.append(candidates)
            if selected_reads and not edge_choices:
                continue
            selected_success = {item["id"] for item in selected_reads
                                if item["kind"] == "cas" and item["outcome"] == "success"}
            modifications = [item for item in members if _is_write(item) and
                             (item["kind"] != "cas" or item["id"] in selected_success)]
            orders = _mo_orders(modifications, before, budgets, frontier)
            for order in orders:
                order_doc = {"id": identity({"object": object_key, "events": order}),
                             "object_key": object_key, "events": order, "status": "valid"}
                if not any(item["id"] == order_doc["id"] for item in mo_orders):
                    mo_orders.append(order_doc)
                    releases.extend(_release_sequences(order, by_id, release_sequence_policy(language_standard)))
            for selected in product(*edge_choices) if edge_choices else [()]:
                for order in orders or [None]:
                    if order is None:
                        continue
                    positions = {identifier: index for index, identifier in enumerate(order)}
                    valid = True
                    transitions = []
                    written_values = {}
                    for edge in selected:
                        read = by_id[edge["read_event"]]
                        if read["kind"] in {"rmw", "cas"} and read["outcome"] == "success":
                            pos = positions.get(read["id"])
                            if pos is None or pos == 0 or order[pos - 1] != edge["write_event"]:
                                valid = False
                    for identifier in order:
                        modification = by_id[identifier]
                        if modification["kind"] in {"store", "initialization"}:
                            written_values[identifier] = modification.get("value")
                        elif modification["kind"] == "rmw":
                            incoming = next((edge for edge in selected if edge["read_event"] == identifier), None)
                            old = written_values.get(incoming["write_event"]) if incoming else None
                            new = _rmw_transition(modification.get("operation"), old, modification.get("value"))
                            if new is None:
                                valid = False
                                frontier.append(diagnostic("rmw-value-transition-unknown",
                                                           "RMW 值转换无法闭合", "RMW value transition is not closed",
                                                           references=[identifier]))
                            else:
                                written_values[identifier] = new
                                transitions.append({"event": identifier, "old": old, "new": new})
                        elif modification["kind"] == "cas" and modification["outcome"] == "success":
                            written_values[identifier] = modification.get("value")
                    if valid:
                        object_assignments.append({"rf_edges": [item["id"] for item in selected],
                                                   "mo_orders": [identity({"object": object_key, "events": order})],
                                                   "transitions": transitions})
                    if len(object_assignments) >= budgets["assignments"]:
                        frontier.append(diagnostic("modification-order-search-incomplete", "assignment 预算耗尽",
                                                   "Assignment budget exhausted"))
                        break
        combined = []
        for left in all_assignments:
            for right in object_assignments:
                combined.append({"rf_edges": left["rf_edges"] + right["rf_edges"],
                                 "mo_orders": left["mo_orders"] + right["mo_orders"],
                                 "transitions": left.get("transitions", []) + right.get("transitions", [])})
                if len(combined) >= budgets["assignments"]:
                    break
        all_assignments = combined
    assignments = [{"id": identity({"ordinal": index, **item}), "ordinal": index,
                    **item, "status": "valid"} for index, item in enumerate(all_assignments)]
    if any(_is_read(item) for item in events) and not assignments:
        frontier.append(diagnostic("advanced-atomic-assignment-incomplete",
                                   "没有形成闭合的有效 RF/MO assignment",
                                   "No closed valid RF/MO assignment was constructed"))
    pairings = _fence_pairings(events, rf_edges, before)
    valid_edge_ids = {edge for assignment in assignments for edge in assignment["rf_edges"]}
    release_edges = {edge["id"] for edge in rf_edges for sequence in releases
                     if edge["write_event"] in sequence["members"] and
                     by_id[edge["read_event"]].get("ordering") in ACQUIRE_ORDERS and
                     edge["id"] in valid_edge_ids}
    pairing_edges = {item["rf_edge"] for item in pairings if item["rf_edge"] in valid_edge_ids}
    synchronized = release_edges | pairing_edges
    assessments = []
    for read in [item for item in events if _is_read(item)]:
        incoming = [edge for edge in rf_edges if edge["read_event"] == read["id"] and
                    edge["id"] in valid_edge_ids]
        if not incoming:
            status = "unknown"
        elif all(edge["id"] in synchronized for edge in incoming):
            status = "discharged-within-bounded-model"
        elif any(edge["id"] not in synchronized for edge in incoming):
            status = "risk"
        else:
            status = "unknown"
        if _frontier_affects(read, incoming, frontier, by_id):
            status = "unknown"
        assessments.append({"id": identity({"read": read["id"], "status": status}),
                            "read_event": read["id"], "assessment": status,
                            "rf_edges": [edge["id"] for edge in incoming],
                            "evidence": sorted(synchronized.intersection(edge["id"] for edge in incoming))})
    frontier = _dedupe_diagnostics(frontier)
    frontier_limit = budgets.get("frontier_items", 100000)
    if len(frontier) > frontier_limit:
        frontier = frontier[:max(0, frontier_limit - 1)] + [diagnostic(
            "frontier-budget-exhausted", "frontier 输出预算耗尽",
            "Frontier output budget exhausted")]
    relevant = any(item["relevant"] for item in frontier)
    counts = {"events": len(events), "objects": len(by_object), "rf_edges": len(rf_edges),
              "mo_orders": len(mo_orders), "assignments": len(assignments),
              "release_sequences": len(releases), "fence_pairings": len(pairings),
              "risk": sum(item["assessment"] == "risk" for item in assessments),
              "discharged": sum(item["assessment"] == "discharged-within-bounded-model" for item in assessments),
              "unknown": sum(item["assessment"] == "unknown" for item in assessments)}
    result = advanced_atomic_document(
        "BoundedAtomicCommunicationGraph", model_id=MODEL_ID, scope_id=scope_id,
        language_standard=language_standard,
        release_sequence_policy=release_sequence_policy(language_standard),
        dependencies=[dependency("AdvancedAtomicLocalFacts", local_facts["semantic_digest"], local_facts)],
        events=events, rf_edges=rf_edges, mo_orders=mo_orders, assignments=assignments,
        release_sequences=sorted({item["id"]: item for item in releases}.values(), key=lambda item: item["id"]),
        fence_pairings=pairings, assessments=assessments, counts=counts,
        status="partial" if relevant else "complete", frontier=frontier, diagnostics=[])
    if len(canonical(result).encode("utf-8")) > budgets.get("request_output_bytes", 1 << 30):
        result = deepcopy(result)
        result["frontier"].append(diagnostic("request-output-budget-exhausted",
                                             "A6 求解输出预算耗尽",
                                             "A6 solver output budget exhausted"))
        result["status"] = "partial"
        result.pop("semantic_digest", None)
        return advanced_atomic_document(
            "BoundedAtomicCommunicationGraph",
            **{key: value for key, value in result.items()
               if key not in {"schema_version", "kind", "analysis_version", "policy_id"}})
    return result


def _thread_source_and_order(thread_graph):
    sources = {}
    for effect in (thread_graph or {}).get("effects", []):
        source = effect.get("source") or {}
        if effect.get("id") and source.get("id"):
            sources[effect["id"]] = source["id"]
    return sources, _before_closure((thread_graph or {}).get("order", []))


def build_overlay(graph, publication_graph=None, thread_graph=None):
    dependencies = [dependency("BoundedAtomicCommunicationGraph", graph["semantic_digest"], graph)]
    protocols = []
    if publication_graph is not None:
        identifier = publication_graph.get("scope_id", identity(publication_graph))
        dependencies.append(dependency("SinglePublicationProtocolGraph", identifier, publication_graph))
        event_assessments = {item["read_event"]: item for item in graph["assessments"]}
        events_by_id = {item["id"]: item for item in graph["events"]}
        edges_by_id = {item["id"]: item for item in graph["rf_edges"]}
        valid_edges = {edge for assignment in graph["assignments"] for edge in assignment["rf_edges"]}
        source_by_effect, thread_before = _thread_source_and_order(thread_graph)
        by_source = defaultdict(list)
        for event in graph["events"]:
            by_source[event["source_id"]].append(event)
        for protocol in publication_graph.get("protocols", []):
            flag_read = protocol.get("flag_read")
            flag_write = protocol.get("flag_write")
            reads = by_source.get(source_by_effect.get(flag_read, flag_read), [])
            writes = by_source.get(source_by_effect.get(flag_write, flag_write), [])
            matched = [event_assessments[item["id"]] for item in reads if item["id"] in event_assessments]
            write_ids = {item["id"] for item in writes}
            read_ids = {item["id"] for item in reads}
            protocol_edges = [edge for edge in graph["rf_edges"]
                              if edge["id"] in valid_edges and edge["write_event"] in write_ids and
                              edge["read_event"] in read_ids]
            payload_write = protocol.get("payload_write")
            payload_read = protocol.get("payload_read")
            payload_order = bool(
                payload_write and payload_read and flag_write and flag_read and
                flag_write in thread_before.get(payload_write, set()) and
                payload_read in thread_before.get(flag_read, set()))
            if not payload_order and {
                    "payload-write-before-flag-store", "flag-observation-before-payload-read"
                    }.issubset(set(protocol.get("chain", []))):
                payload_order = True
            selected_for_reads = [set(assignment["rf_edges"]).intersection(
                edge["id"] for edge in graph["rf_edges"] if edge["read_event"] in read_ids)
                                  for assignment in graph["assignments"]]
            unique_protocol_rf = bool(selected_for_reads) and all(
                len(selected) == 1 and selected.issubset({edge["id"] for edge in protocol_edges})
                for selected in selected_for_reads)
            synchronized = {edge for item in matched for edge in item.get("evidence", [])}
            if not matched or not protocol_edges:
                assessment = "unknown"
                frontier = ["publication-event-binding-unresolved"]
            elif not payload_order:
                assessment = "unknown"
                frontier = ["publication-payload-order-unproved"]
            elif not unique_protocol_rf:
                assessment = "unknown"
                frontier = ["publication-reads-from-not-unique"]
            elif any(item["assessment"] == "unknown" for item in matched):
                assessment = "unknown"
                frontier = ["advanced-atomic-assignment-incomplete"]
            elif all(edge["id"] in synchronized for edge in protocol_edges):
                assessment, frontier = "discharged-within-bounded-model", []
            elif any(edge["id"] not in synchronized for edge in protocol_edges):
                assessment, frontier = "risk", []
            else:
                assessment, frontier = "unknown", ["advanced-atomic-assignment-incomplete"]
            protocols.append({"id": identity({"p4": protocol["id"], "graph": graph["semantic_digest"]}),
                              "p4_protocol_id": protocol["id"], "assessment": assessment,
                              "event_assessments": [item["id"] for item in matched],
                              "frontier": frontier,
                              "evidence": [graph["semantic_digest"],
                                           *[edge["id"] for edge in protocol_edges]]})
    if publication_graph is None:
        protocols = [{"id": item["id"], "p4_protocol_id": None,
                      "assessment": item["assessment"], "event_assessments": [item["id"]],
                      "frontier": [], "evidence": item["evidence"]} for item in graph["assessments"]]
    relevant = bool(graph["frontier"] or any(item["frontier"] for item in protocols))
    return advanced_atomic_document(
        "AdvancedPublicationProtocolOverlay", scope_id=graph["scope_id"], dependencies=dependencies,
        protocols=protocols, status="partial" if relevant else "complete",
        frontier=deepcopy(graph["frontier"]), diagnostics=[])


def build_report(graph, overlay, *, cache_hits=0, cache_misses=0):
    findings = [item for item in overlay["protocols"] if item["assessment"] == "risk"]
    frontier = deepcopy(overlay["frontier"])
    for item in overlay["protocols"]:
        for code in item["frontier"]:
            frontier.append(diagnostic(code, "高级原子发布候选证据不完整",
                                       "Advanced atomic publication candidate is incomplete",
                                       references=[item["id"]]))
    relevant = any(item["relevant"] for item in frontier)
    if relevant:
        status, verdict, exit_code = "partial", "inconclusive", 2
    elif findings:
        status, verdict, exit_code = "complete", "risk", 3
    else:
        status, verdict, exit_code = "complete", "complete-no-supported-risk", 0
    return advanced_atomic_document(
        "FenceRmwPublicationReport", model_id=MODEL_ID, scope_id=graph["scope_id"],
        language_standard=graph["language_standard"], status=status, verdict=verdict,
        safety="not_established", exit_code=exit_code,
        stages={"local_facts": "complete" if not graph["events"] or graph["status"] == "complete" else "partial",
                "rf_mo": graph["status"], "overlay": overlay["status"]},
        counts={**graph["counts"], "protocols": len(overlay["protocols"]), "findings": len(findings),
                "frontier": len(frontier)},
        outputs=[dependency("BoundedAtomicCommunicationGraph", graph["semantic_digest"], graph),
                 dependency("AdvancedPublicationProtocolOverlay", overlay["semantic_digest"], overlay)],
        cache={"hits": cache_hits, "misses": cache_misses}, findings=findings, frontier=frontier,
        diagnostics=[], limitations=["bounded-publication-model-only",
                                     "not-a-whole-program-safety-proof",
                                     "no-general-happens-before-or-data-race-proof"])


def normalize_for_equivalence(local_facts):
    normalized = []
    for item in local_facts["events"]:
        value = {key: child for key, child in item.items()
                 if key not in {"id", "evidence", "artifact_key", "source_id",
                                "compare_ref", "desired_ref", "observed_ref"}}
        function = value.get("function_id")
        if isinstance(function, str) and ":symbol:" in function:
            value["function_id"] = function.split(":symbol:", 1)[1]
        normalized.append(value)
    return sorted(normalized, key=canonical)
