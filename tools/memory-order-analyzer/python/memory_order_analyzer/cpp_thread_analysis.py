"""A3 local sidecars, bounded thread-object state, and P3 relation composition."""

from collections import defaultdict
from copy import deepcopy
import re

from .contracts import AnalysisError, canonical, identity
from .cpp_thread_contracts import cpp_thread_document, dependency, diagnostic
from .cpp_thread_profiles import normalize_wrapper_calls


SOURCE_OPERATIONS = {
    "cpp-thread-construct": "construct",
    "cpp-thread-move-construct": "move-construct",
    "cpp-thread-move-assign": "move-assign",
    "cpp-thread-join": "join",
    "cpp-thread-detach": "detach",
    "cpp-thread-joinable": "joinable",
    "cpp-thread-destruct": "destruct",
}
ROLE_FOR_OPERATION = {
    "construct": "construct-attempt", "join": "join-attempt",
    "detach": "detach-attempt", "move-construct": "handle-transfer",
    "move-assign": "handle-transfer",
}
PROVENANCE_OPCODES = {"alloca", "load", "store", "bitcast", "addrspacecast", "phi", "select", "getelementptr"}


def _source_anchor(source):
    location = (source or {}).get("expansion") or {}
    return (location.get("file"), location.get("line"), location.get("column"))


def _ir_anchor(source):
    chain = (source or {}).get("inline_chain") or []
    location = chain[-1] if chain else {}
    return (location.get("file"), location.get("line"), location.get("column"))


def trace_handle_provenance(seeds, values, *, limit=64):
    """Bounded local SSA provenance; escaping/unsupported values never become unique."""
    registry = {item["id"]: item for item in values}
    pending, visited, roots, opposed = list(sorted(set(seeds))), set(), set(), set()
    while pending:
        current = pending.pop(0)
        if current in visited:
            continue
        if len(visited) >= limit:
            opposed.add("provenance-budget-exhausted"); break
        visited.add(current)
        node = registry.get(current)
        if node is None:
            roots.add(current); continue
        opcode = node.get("details", {}).get("opcode") or node.get("opcode")
        if opcode not in PROVENANCE_OPCODES:
            opposed.add("unsupported-provenance-operation"); continue
        if opcode == "alloca":
            roots.add(current); continue
        pending.extend(item for item in node.get("operands", []) if item not in visited)
    status = ("exact" if len(roots) == 1 and not opposed else "candidate" if roots
              else "unresolved")
    return {"status": status, "roots": sorted(roots), "evidence": sorted(visited),
            "opposed": sorted(opposed)}


def module_wrapper_calls(modules, profile):
    """Normalize exact direct calls while retaining raw call/value provenance."""
    signatures = {item["symbol"]: item for item in profile["wrapper_signatures"]}
    calls = []
    for artifact, module in sorted(modules.items()):
        if module.get("target") != profile["target"] or module.get("layout") != profile["data_layout"]:
            continue
        values = module.get("values", [])
        for call in module.get("calls", []):
            signature = signatures.get(call.get("target"))
            if call.get("kind") != "direct" or signature is None:
                continue
            handle_seeds = ([call["result_ref"]] if call.get("result_ref") else []) + list(call.get("arguments", []))
            provenance = trace_handle_provenance(handle_seeds, values)
            raw_convention = call.get("calling_convention")
            calling_convention = "ccc" if raw_convention in (None, 0, "ccc") else f"llvm:{raw_convention}"
            calls.append({
                "id": f"{artifact}:{call['id']}", "symbol": call["target"],
                # Preserve the convention observed in ModuleFacts.  Copying the
                # registered convention here would turn an ABI mismatch into a
                # false exact match during normalization.
                "calling_convention": calling_convention,
                "signature_digest": signature["digest"],
                "contains_pthread": "pthread" in call["target"],
                "evidence": [f"{artifact}:{call['id']}"], "source": call.get("source", {}),
                "arguments": list(call.get("arguments", [])), "result_ref": call.get("result_ref"),
                "normal": call.get("normal"), "unwind": call.get("unwind"),
                "handle_provenance": provenance,
            })
    return calls


def _p3_markers(value):
    """Return stable, explicit markers carried by one P3 evidence value."""
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return set().union(*(_p3_markers(item) for item in value)) if value else set()
    if not isinstance(value, dict):
        return {str(value)}
    result = {canonical(value)}
    for name in ("id", "operation_id", "a3_operation_id", "analysis_id"):
        if value.get(name):
            result.add(str(value[name]))
    return result | _p3_markers(value.get("proof"))


def adapt_p3_join_proofs(thread_graph, local_facts):
    """Map only closed P3 exit/join/not-parallel chains to A3 join operations.

    P3 remains immutable.  A lifecycle name or source order alone is deliberately
    insufficient: the adapter requires a join-complete event, its incoming join
    edge from a thread-exit event, and a not-parallel record reaching a parent
    successor.
    """
    if not thread_graph:
        return {}
    events = {item["id"]: item for item in thread_graph.get("lifecycles", [])}
    incoming = defaultdict(list)
    for edge in thread_graph.get("order", []):
        incoming[edge.get("after")].append(edge)
    mhp_by_exit = defaultdict(list)
    for item in thread_graph.get("mhp", []):
        if item.get("relation") == "not_parallel" and item.get("right_endpoint"):
            mhp_by_exit[item.get("left_endpoint")].append(item)
    result = {}
    joins = [op for facts in local_facts for op in facts.get("operations", [])
             if op.get("operation") == "join"]
    for operation in joins:
        operation_markers = {operation["id"], *operation.get("source_nodes", []),
                             *operation.get("ir_nodes", [])}
        candidates = []
        for event in events.values():
            if event.get("kind") != "join-complete" or event.get("status") == "unknown":
                continue
            if not operation_markers & (_p3_markers(event.get("source")) |
                                        _p3_markers(event.get("proof"))):
                continue
            for edge in incoming.get(event["id"], []):
                exit_event = events.get(edge.get("before"))
                if (edge.get("kind") != "join" or edge.get("relation") not in {"must-before", "may-before"}
                        or not exit_event or exit_event.get("kind") != "thread-exit"
                        or exit_event.get("status") == "unknown" or not mhp_by_exit.get(exit_event["id"])):
                    continue
                proof = {event["id"], exit_event["id"], edge["id"]}
                proof.update(item["id"] for item in mhp_by_exit[exit_event["id"]])
                proof.update(_p3_markers(event.get("proof")))
                proof.update(_p3_markers(edge.get("proof")))
                candidates.append(sorted(proof))
        if len(candidates) == 1:
            result[operation["id"]] = candidates[0]
    return result


def _entity_for_node(index, node_id):
    if not index:
        return None
    return next((item for item in index.get("entities", []) if node_id in item["declarations"]), None)


def _binding_for_node(binding, node_id):
    if not binding:
        return None
    return next((item for item in binding.get("entity_bindings", []) if item["source_id"] == node_id), None)


def _callable_kind(node):
    name = " ".join(str(node.get(key) or "") for key in ("name", "qualified_name", "canonical_type"))
    if "lambda" in name:
        return "lambda"
    if node.get("name") == "operator()":
        return "functor"
    if "::*" in name or (node.get("qualified_name") or "").count("::") > 1:
        return "member-function"
    return "free-function"


def _gap(code, detail, detail_en, *, tu, nodes=(), objects=(), threads=(), dependencies=()):
    seed = {"code": code, "tu": tu, "nodes": sorted(set(nodes)),
            "objects": sorted(set(objects)), "threads": sorted(set(threads))}
    return {
        "id": identity(seed), "code": code, "physical_tu_ids": [tu] if tu else [],
        "node_ids": seed["nodes"], "object_ids": seed["objects"],
        "thread_ids": seed["threads"], "path_ids": [],
        "dependencies": sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
        "detail": detail, "detail_en": detail_en,
        "suggestion": "补齐精确 AST、ABI/IR、对象和路径证据后重试",
        "suggestion_en": "Retry after completing exact AST, ABI/IR, object, and path evidence",
    }


def build_local_facts(scope_id, member, source_facts, profile=None, *, modules=None,
                      entity_index=None, source_binding=None, wrapper_calls=None):
    """Build an independent A3 sidecar; C never adopts a C++ library model."""
    language, standard, tu = member["language"], member["standard"], member["physical_tu_id"]
    dependencies = []
    if source_facts is not None:
        dependencies.append(dependency("SourceSemanticFacts", tu, source_facts))
    if language == "c":
        return cpp_thread_document(
            "CppThreadLocalFacts", scope_id=scope_id, physical_tu_id=tu,
            profile_id=member["profile_id"], language=language, standard=standard,
            status="complete" if source_facts and source_facts.get("status") == "complete" else "partial",
            library_profile_id=None, callables=[], operations=[], dependencies=dependencies,
            diagnostics=[], frontier=[] if source_facts else [diagnostic(
                "source-evidence-missing", "C TU 的源码证据缺失", "Source evidence is missing for the C TU")],
            semantic_digest=None)
    if profile is None:
        raise AnalysisError("library_profile_unsupported", "C++ local facts require an adopted library profile")
    dependencies.append(dependency("CppThreadLibraryProfile", profile["profile_id"], profile))
    if profile.get("status") != "verified":
        item = diagnostic(
            "library-profile-unsupported", "C++ 标准库 profile 未经验证，线程生命周期保持 unknown",
            "The C++ standard-library profile is unverified; thread lifecycle remains unknown",
            suggestion="提供与编译 profile、标准库、ABI 和目标完全匹配的已验证注册项",
            suggestion_en="Provide a verified registration matching the compilation profile, library, ABI, and target",
            source={"physical_tu_id": tu, "profile_id": profile["profile_id"]})
        return cpp_thread_document(
            "CppThreadLocalFacts", scope_id=scope_id, physical_tu_id=tu,
            profile_id=member["profile_id"], language=language, standard=standard,
            status="partial", library_profile_id=profile["profile_id"], callables=[], operations=[],
            dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
            diagnostics=[item], frontier=[item], semantic_digest=None)
    if source_facts is None:
        item = diagnostic("source-evidence-missing", "C++ 线程源码证据缺失",
                          "C++ thread source evidence is missing")
        return cpp_thread_document(
            "CppThreadLocalFacts", scope_id=scope_id, physical_tu_id=tu,
            profile_id=member["profile_id"], language=language, standard=standard,
            status="partial", library_profile_id=profile["profile_id"], callables=[], operations=[],
            dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
            diagnostics=[item], frontier=[item], semantic_digest=None)

    nodes = {item["id"]: item for item in source_facts["nodes"]}
    relations = source_facts["relations"]
    by_from = defaultdict(list)
    for relation in relations:
        by_from[relation["from"]].append(relation)
    object_at = {}
    for relation in relations:
        if relation["kind"] == "cpp-thread-object" and relation.get("to"):
            object_at[_source_anchor(relation.get("source"))] = relation["to"]

    raw_calls = (list(wrapper_calls) if wrapper_calls is not None
                 else module_wrapper_calls(modules or {}, profile))
    normalized, wrapper_diagnostics = normalize_wrapper_calls(raw_calls, profile)
    raw_by_id = {item["id"]: item for item in raw_calls}
    wrappers_by_anchor = defaultdict(list)
    for item in normalized:
        wrappers_by_anchor[_ir_anchor(raw_by_id[item["call_id"]].get("source"))].append(item)
    wrappers_by_role = defaultdict(list)
    for item in normalized:
        wrappers_by_role[item["role"]].append(item)

    callables, operations, frontier = {}, [], list(wrapper_diagnostics)
    move_sources = {item["from"]: item.get("to") for item in relations
                    if item["kind"] == "cpp-thread-move-source"}
    for relation in sorted(relations, key=lambda item: item["id"]):
        operation = SOURCE_OPERATIONS.get(relation["kind"])
        if operation is None:
            continue
        anchor = _source_anchor(relation.get("source"))
        object_id = (relation["from"] if operation == "destruct" else
                     relation.get("to") if operation not in {"construct", "move-construct"}
                     else object_at.get(anchor))
        if object_id is None:
            object_id = f"source-object:{relation['from']}"
        callback = next((item for item in by_from[relation["from"]]
                         if item["kind"] == "cpp-thread-callback"), None)
        callable_id = None
        callable_exact = False
        if callback:
            target_node = callback.get("to")
            node = nodes.get(target_node, {})
            entity = _entity_for_node(entity_index, target_node)
            binding = _binding_for_node(source_binding, target_node)
            targets = (entity.get("definitions", []) if entity else [])
            resolution = "exact" if (entity and entity["resolution"] == "resolved" and len(targets) == 1
                                       and binding and binding["resolution"] == "exact") else (
                "ambiguous" if entity and entity["resolution"] in {"ambiguous", "conflict"}
                else "candidate" if target_node else "unresolved")
            callable_id = identity({"tu": tu, "node": target_node, "targets": targets})
            callables[callable_id] = {
                "id": callable_id, "callable_kind": _callable_kind(node) if node else "unknown",
                "entity_id": entity["id"] if entity else None, "receiver_id": None,
                "capture_ids": [], "resolution": resolution, "targets": sorted(targets),
                "source_nodes": sorted([target_node] if target_node else []),
                "ir_nodes": sorted(item["id"] for item in (binding or {}).get("targets", [])),
            }
            callable_exact = resolution == "exact"
        role = ROLE_FOR_OPERATION.get(operation)
        candidates = wrappers_by_anchor.get(anchor, [])
        if not candidates and role and len(wrappers_by_role[role]) == 1:
            candidates = wrappers_by_role[role]
        matching = [item for item in candidates if item["role"] == role] if role else []
        exact_wrapper = len(matching) == 1
        exact = relation["status"] != "unknown" and (role is None or exact_wrapper)
        if operation == "construct":
            exact = exact and callable_exact
        raw_match = raw_by_id[matching[0]["call_id"]] if exact_wrapper else {}
        outcome = ("throw" if exact and raw_match.get("unwind") and not raw_match.get("normal")
                   else "success" if exact else "unknown")
        ir_nodes = sorted(set(matching[0]["evidence"])) if exact_wrapper else []
        other = relation.get("to") if operation == "move-construct" else move_sources.get(relation["from"])
        op = {
            "id": identity({"tu": tu, "relation": relation["id"], "object": object_id,
                            "ir": ir_nodes}), "operation": operation, "object_id": object_id,
            "other_object_id": other, "callable_id": callable_id, "outcome": outcome,
            "guard": (f"normal-return:{raw_match['normal']}" if exact and raw_match.get("normal") else
                      f"exception:{raw_match['unwind']}" if exact and raw_match.get("unwind") else None),
            "wrapper_role": role if exact_wrapper else None,
            "native_handle": ((raw_by_id[matching[0]["call_id"]].get("handle_provenance") or {}).get("roots", [None])[0]
                              if exact_wrapper and len((raw_by_id[matching[0]["call_id"]].get("handle_provenance") or {}).get("roots", [])) == 1
                              else raw_by_id[matching[0]["call_id"]].get("result_ref") if exact_wrapper else None),
            "source_nodes": [relation["from"]], "ir_nodes": ir_nodes, "repeated": False,
        }
        operations.append(op)
        if not exact:
            item = diagnostic(
                "cpp-thread-evidence-incomplete", "C++ 线程操作缺少精确 AST 与 ABI/IR 双重证据",
                "The C++ thread operation lacks exact AST plus ABI/IR evidence",
                suggestion="补齐精确 callable、对象及已验证 wrapper 绑定",
                suggestion_en="Complete exact callable, object, and verified-wrapper bindings",
                source={"operation_id": op["id"], "physical_tu_id": tu})
            frontier.append(item)
    operations.sort(key=lambda item: item["id"])
    callable_values = sorted(callables.values(), key=lambda item: item["id"])
    status = ("complete" if source_facts.get("status") == "complete" and not frontier
              else "partial")
    return cpp_thread_document(
        "CppThreadLocalFacts", scope_id=scope_id, physical_tu_id=tu,
        profile_id=member["profile_id"], language=language, standard=standard,
        status=status, library_profile_id=profile["profile_id"], callables=callable_values,
        operations=operations,
        dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
        diagnostics=frontier, frontier=frontier, semantic_digest=None)


def _transition(operation, before, after, instance, evidence):
    seed = {"operation": operation["id"], "from": sorted(before), "to": after,
            "instance": instance}
    return {
        "id": identity(seed), "object_id": operation["object_id"],
        "operation_id": operation["id"], "from": sorted(before), "to": after,
        "guard": operation["guard"], "outcome": operation["outcome"],
        "instance_id": instance, "evidence": sorted(set(evidence)),
    }


def build_lifecycle_graph(request, local_facts, profiles, *, p3_join_proofs=None,
                          thread_graph=None):
    """Compose bounded exact local facts into an additive lifecycle graph."""
    if p3_join_proofs is None:
        p3_join_proofs = adapt_p3_join_proofs(thread_graph, local_facts)
    budgets = request["budgets"]
    states, handles, object_instances = defaultdict(lambda: {"empty"}), {}, {}
    contexts, instances, transitions, relations, gaps, frontier = {}, {}, [], [], [], []
    def operation_order(item):
        match = re.search(r":(\d+):(\d+)$", item["source_nodes"][0]) if item["source_nodes"] else None
        location = (int(match.group(1)), int(match.group(2))) if match else (2**31, 2**31)
        return (item["operation"] == "destruct", location, item["id"])
    all_operations = sorted((op for facts in local_facts for op in facts["operations"]),
                            key=operation_order)
    callable_map = {item["id"]: item for facts in local_facts for item in facts["callables"]}
    tu_for_operation = {op["id"]: facts["physical_tu_id"] for facts in local_facts for op in facts["operations"]}

    def cut(name, current, maximum, operation):
        if current < maximum:
            return False
        item = diagnostic(f"{name}-budget-exhausted", f"{name} 预算已耗尽",
                          f"The {name} budget is exhausted", source={"operation_id": operation["id"]})
        frontier.append(item)
        return True

    for operation in all_operations:
        evidence = [*operation["source_nodes"], *operation["ir_nodes"]]
        object_id, kind = operation["object_id"], operation["operation"]
        before = set(states[object_id])
        if operation["outcome"] != "success":
            after = ("failed" if kind == "construct" and operation["outcome"] in {"failure", "throw"}
                     else next(iter(before)) if kind in {"join", "detach"} and
                     operation["outcome"] in {"failure", "throw"} and len(before) == 1
                     else "unknown")
            states[object_id] = {after}
            gaps.append(_gap("cpp-thread-operation-unknown", "线程对象操作未建立成功结果",
                             "The thread-object operation did not establish a successful outcome",
                             tu=tu_for_operation[operation["id"]], nodes=evidence,
                             objects=[object_id]))
            if not cut("transitions", len(transitions), budgets["transitions"], operation):
                transitions.append(_transition(operation, before, after, None, evidence))
            continue
        instance_id = object_instances.get(object_id)
        after = None
        if kind == "construct":
            callable_ = callable_map.get(operation["callable_id"])
            if not callable_ or callable_["resolution"] != "exact":
                after = "unknown"
            else:
                context_id = identity({"callable": callable_["id"], "profile": next(
                    facts["library_profile_id"] for facts in local_facts
                    if operation in facts["operations"]), "arguments": []})
                contexts.setdefault(context_id, {
                    "id": context_id, "callable_id": callable_["id"], "arguments": [],
                    "profile_id": next(facts["library_profile_id"] for facts in local_facts
                                       if operation in facts["operations"]), "status": "complete",
                })
                repeated = operation["repeated"]
                instance_id = identity({"context": context_id, "construct": operation["id"],
                                        "object": object_id, "bucket": "repeated" if repeated else "single"})
                instances[instance_id] = {
                    "id": instance_id, "context_id": context_id, "parent_id": None,
                    "construct_operation_id": operation["id"], "object_id": object_id,
                    "handle": operation["native_handle"],
                    "cardinality": "repeated" if repeated else "single",
                    "reason": "loop-or-recursion" if repeated else None,
                    "guard": operation["guard"], "status": "partial" if repeated else "complete",
                }
                object_instances[object_id] = instance_id
                handles[object_id] = operation["native_handle"]
                after = "joinable"
                if len(relations) + 2 <= budgets["relations"]:
                    start = identity({"relation": "thread-start", "instance": instance_id})
                    relations.append({"id": start, "relation": "thread-start", "from": operation["id"],
                                      "to": instance_id, "guard": operation["guard"], "evidence": sorted(evidence)})
                    parallel = identity({"relation": "may-parallel", "instance": instance_id})
                    relations.append({"id": parallel, "relation": "may-parallel", "from": "root",
                                      "to": instance_id, "guard": operation["guard"], "evidence": sorted(evidence)})
                else:
                    cut("relations", budgets["relations"], budgets["relations"], operation)
        elif kind in {"move-construct", "move-assign"}:
            source = operation["other_object_id"]
            if not source or source == object_id or states[source] & {"unknown"}:
                after = "unknown"
            elif kind == "move-assign" and before & {"joinable"}:
                after = "terminated-path"
                gaps.append(_gap("move-assign-joinable-target",
                                 "move assignment 覆盖可能 joinable 的目标并终止路径",
                                 "Move assignment overwrites a possibly joinable target and terminates the path",
                                 tu=tu_for_operation[operation["id"]], nodes=evidence,
                                 objects=[object_id], threads=[instance_id] if instance_id else []))
            else:
                after = next(iter(states[source])) if len(states[source]) == 1 else "unknown"
                object_instances[object_id] = object_instances.get(source)
                handles[object_id] = handles.get(source)
                states[source] = {"moved-from"}
        elif kind == "joinable":
            after = next(iter(before)) if len(before) == 1 else "unknown"
        elif kind == "join":
            if before == {"joinable"} and operation["id"] in p3_join_proofs:
                after = "joined"
                proof = sorted(set([*evidence, *p3_join_proofs[operation["id"]]]))
                for relation_kind, left, right in (("thread-exit", instance_id, operation["id"]),
                                                    ("join-complete", instance_id, operation["id"]),
                                                    ("not-parallel", instance_id, "root")):
                    if not cut("relations", len(relations), budgets["relations"], operation):
                        relations.append({"id": identity({"relation": relation_kind, "operation": operation["id"]}),
                                          "relation": relation_kind, "from": left, "to": right,
                                          "guard": operation["guard"], "evidence": proof})
            else:
                after = "unknown"
                gaps.append(_gap("join-proof-incomplete", "join 缺少 worker-exit 与父线程后继顺序证明",
                                 "join lacks worker-exit and parent-successor order proof",
                                 tu=tu_for_operation[operation["id"]], nodes=evidence,
                                 objects=[object_id], threads=[instance_id] if instance_id else []))
        elif kind == "detach":
            after = "detached" if before == {"joinable"} else "unknown"
            if after == "detached" and instance_id:
                if not cut("relations", len(relations), budgets["relations"], operation):
                    relations.append({"id": identity({"relation": "detach", "operation": operation["id"]}),
                                      "relation": "detach", "from": operation["id"], "to": instance_id,
                                      "guard": operation["guard"], "evidence": sorted(evidence)})
        elif kind == "destruct":
            after = ("terminated-path" if "joinable" in before else
                     next(iter(before)) if len(before) == 1 else "unknown")
            if after == "terminated-path":
                gaps.append(_gap("joinable-destructor", "可 join 的 std::thread 析构会终止路径，不是隐式 join",
                                 "Destroying a joinable std::thread terminates the path; it is not an implicit join",
                                 tu=tu_for_operation[operation["id"]], nodes=evidence,
                                 objects=[object_id], threads=[instance_id] if instance_id else []))
        if after is None:
            after = "unknown"
        states[object_id] = {after}
        if not cut("transitions", len(transitions), budgets["transitions"], operation):
            transitions.append(_transition(operation, before, after, object_instances.get(object_id), evidence))

    for facts in local_facts:
        frontier.extend(facts["frontier"])
    if any(item["cardinality"] != "single" for item in instances.values()):
        frontier.append(diagnostic("instance-abstraction", "循环或递归线程实例已合并",
                                   "Loop or recursive thread instances were merged"))
    objects = [{
        "id": identity({"object": object_id, "state": sorted(values)}), "object_id": object_id,
        "state": next(iter(values)) if len(values) == 1 else "unknown",
        "handle": handles.get(object_id), "instance_id": object_instances.get(object_id),
        "guard": None, "source_operation_id": next((op["id"] for op in reversed(all_operations)
                                                       if op["object_id"] == object_id), None),
    } for object_id, values in sorted(states.items())]
    if len(objects) > budgets["objects"]:
        objects = objects[:budgets["objects"]]
        frontier.append(diagnostic("objects-budget-exhausted", "对象预算已耗尽",
                                   "The object budget is exhausted"))
    if len(instances) > budgets["instances"]:
        kept = dict(list(sorted(instances.items()))[:budgets["instances"]])
        instances = kept
        objects = [item for item in objects if item["instance_id"] is None or item["instance_id"] in kept]
        frontier.append(diagnostic("instances-budget-exhausted", "实例预算已耗尽",
                                   "The instance budget is exhausted"))
    gaps = sorted({item["id"]: item for item in gaps}.values(), key=lambda item: item["id"])
    status = "partial" if gaps or frontier or any(f["status"] != "complete" for f in local_facts) else "complete"
    profile_refs = sorted((dependency("CppThreadLibraryProfile", item["profile_id"], item)
                           for item in profiles), key=lambda item: (item["kind"], item["id"]))
    dependencies = sorted([dependency("CppThreadLifecycleRequest", request["scope_id"], request),
                           *(dependency("CppThreadLocalFacts", item["physical_tu_id"], item)
                             for item in local_facts),
                           *([dependency("ThreadContextGraph", thread_graph["scope_id"], thread_graph)]
                             if thread_graph else [])], key=lambda item: (item["kind"], item["id"]))
    return cpp_thread_document(
        "CppThreadLifecycleGraph", scope_id=request["scope_id"], request_hash=identity(request),
        status=status, profiles=profile_refs, objects=sorted(objects, key=lambda item: item["id"]),
        contexts=sorted(contexts.values(), key=lambda item: item["id"]),
        instances=sorted(instances.values(), key=lambda item: item["id"]),
        transitions=sorted(transitions, key=lambda item: item["id"]),
        relations=sorted(relations, key=lambda item: item["id"]), gaps=gaps,
        counts={"operations": len(all_operations), "objects": len(objects),
                "contexts": len(contexts), "instances": len(instances),
                "transitions": len(transitions), "relations": len(relations), "gaps": len(gaps)},
        dependencies=dependencies, diagnostics=frontier,
        frontier=frontier, semantic_digest=None)


def build_lifecycle_report(request, graph, profiles, *, hits=0, misses=0):
    graph_ref = dependency("CppThreadLifecycleGraph", graph["scope_id"], graph)
    diagnostics = [diagnostic(
        gap["code"], gap["detail"], gap["detail_en"],
        suggestion=gap["suggestion"], suggestion_en=gap["suggestion_en"],
        source={"gap_id": gap["id"]}) for gap in graph["gaps"]]
    return cpp_thread_document(
        "CppThreadLifecycleReport", scope_id=request["scope_id"], request_hash=identity(request),
        status=graph["status"], exit_code=2 if graph["status"] == "partial" else 0,
        safety="not_evaluated", findings=None, graph=graph_ref,
        profiles=sorted((dependency("CppThreadLibraryProfile", item["profile_id"], item)
                         for item in profiles), key=lambda item: (item["kind"], item["id"])),
        counts=deepcopy(graph["counts"]),
        dependencies=sorted([graph_ref, dependency("CppThreadLifecycleRequest", request["scope_id"], request)],
                            key=lambda item: (item["kind"], item["id"])),
        diagnostics=diagnostics, frontier=[*graph["frontier"], *diagnostics],
        cache={"hits": hits, "misses": misses}, semantic_digest=None)


def failed_lifecycle_report(code, detail, detail_en=None):
    item = diagnostic(code, f"C++ 线程生命周期分析失败：{detail}",
                      f"C++ thread lifecycle analysis failed: {detail_en or detail}",
                      suggestion="修复显式请求、profile 或依赖后重试",
                      suggestion_en="Repair the explicit request, profile, or dependency and retry")
    return cpp_thread_document(
        "CppThreadLifecycleReport", scope_id=None, request_hash=None, status="failed",
        exit_code=1, safety="not_evaluated", findings=None, graph=None, profiles=[], counts={},
        dependencies=[], diagnostics=[item], frontier=[item], cache={"hits": 0, "misses": 0},
        semantic_digest=None)
