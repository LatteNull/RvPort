"""Finite P3 thread, lifecycle, MHP, mutex and atomic candidate graph."""

from collections import defaultdict, deque
from copy import deepcopy

from .contracts import AnalysisError, canonical, identity
from .thread_contracts import (
    diagnostic,
    thread_context_id,
    thread_document,
    thread_instance_id,
)
from .thread_models import MODEL_ID, adopt_all


def _source_key(source):
    return canonical(source) if source is not None else None


def _function_pair(reference):
    return reference["artifact_key"], reference["id"]


def _dependency(kind, identifier, value):
    return {"kind": kind, "id": identifier, "digest": identity(value)}


def _argument(value=None, reason="unbound-thread-argument"):
    if isinstance(value, dict) and value.get("artifact_key"):
        return {"kind": "object", "source": deepcopy(value)}
    return {"kind": "unknown", "reason": reason}


def _object_range(address, overlay=None):
    if not isinstance(address, dict) or address.get("kind") == "unknown":
        return None, None
    if address.get("kind") == "object":
        if overlay is not None:
            from .source_assistance import canonical_object_key
            canonical_key = canonical_object_key(overlay, address)
            if canonical_key is not None:
                offset = address.get("offset")
                return canonical_key, offset if isinstance(offset, str) else None
        base = {name: address.get(name) for name in ("kind", "source", "address_space", "allocation")}
        offset = address.get("offset")
        return identity(base), offset if isinstance(offset, str) else None
    return identity(address), None


def _ranges_disjoint(left, right):
    try:
        left_start, right_start = int(left["offset_bytes"]), int(right["offset_bytes"])
        left_size, right_size = int(left["size_bytes"]), int(right["size_bytes"])
    except (TypeError, ValueError):
        return False
    return left_start + left_size <= right_start or right_start + right_size <= left_start


class ThreadGraphBuilder:
    def __init__(self, inputs, request, local_facts, order_facts, summaries,
                 source_assistance=None):
        self.inputs = inputs
        self.request = deepcopy(request)
        self.local_facts = deepcopy(local_facts)
        self.order_facts = deepcopy(order_facts)
        values = summaries.values() if isinstance(summaries, dict) else summaries
        self.summaries = sorted((deepcopy(item) for item in values), key=lambda item: item["context_id"])
        self.source_assistance = deepcopy(source_assistance)
        self.object_overlay = (self.source_assistance["overlay"]
                               if self.source_assistance is not None else None)
        self.summary_by_function = defaultdict(list)
        for summary in self.summaries:
            self.summary_by_function[(summary["root"]["artifact_key"], summary["root"]["function_id"])].append(summary)
        self.calls_by_function = defaultdict(list)
        self.calls_by_source = {}
        for facts in self.local_facts.values():
            for call in facts["calls"]:
                pair = _function_pair(call["function"])
                self.calls_by_function[pair].append(call)
                self.calls_by_source[_source_key(call["source"])] = call
        self.order_edges = [edge for facts in self.order_facts.values() for edge in facts["edges"]]
        self.order_multiplicity = {
            _source_key(node["source"]): node["multiplicity"]
            for facts in self.order_facts.values() for node in facts["nodes"]
        }
        self.adoptions, model_diagnostics = adopt_all(self.local_facts)
        self.adoption_by_source = {_source_key(item["call"]): item for item in self.adoptions}
        self.contexts, self.instances, self.lifecycles, self.effects = [], [], [], []
        self.anchors, self.order, self.mhp, self.synchronization = [], [], [], []
        self.frontier, self.diagnostics = [], model_diagnostics
        self.context_table, self.instance_table = {}, {}
        self.effect_by_instance_source = defaultdict(lambda: defaultdict(list))
        self.anchor_by_instance_source = defaultdict(lambda: defaultdict(list))
        self.create_records, self.join_records, self.mutex_records = [], [], []
        self.limit = request["budgets"]["graph_items"]
        self.cut = False

    def _resolve_callback_target(self, target):
        module = self.inputs.modules.get(target["artifact_key"])
        declaration = next((item for item in module["functions"]
                            if item["id"] == target["id"]), None) if module else None
        if declaration is None:
            return None
        if not declaration["declaration"]:
            return deepcopy(target)
        name = declaration.get("name")
        if not name or not self.inputs.scope.get("closed") or self.inputs.scope.get("external_boundaries"):
            return None
        candidates = [
            {"artifact_key": artifact, "function_id": None, "id": function["id"]}
            for artifact, facts in self.inputs.modules.items()
            for function in facts["functions"]
            if not function["declaration"] and function.get("name") == name
            and function.get("linkage") in {"external", "internal"} and not function.get("comdat")
        ]
        return candidates[0] if len(candidates) == 1 else None

    def _append(self, target, item, *, context=None, instance=None):
        current = sum(len(value) for value in (
            self.contexts, self.instances, self.lifecycles, self.effects,
            self.anchors, self.order, self.mhp, self.synchronization,
        ))
        if current >= self.limit:
            if not self.cut:
                item_diag = diagnostic(
                    "thread-graph-budget", "线程关系图超过显式预算",
                    "The thread relation graph exceeded its explicit budget",
                    context=context, instance=instance,
                    suggestion="收紧分析根或提高预算后重新运行",
                    suggestion_en="Narrow the roots or rerun with a larger budget",
                )
                self.frontier.append(item_diag)
                self.diagnostics.append(deepcopy(item_diag))
                self.cut = True
            return False
        target.append(item)
        return True

    def _summary(self, entry):
        candidates = self.summary_by_function.get(_function_pair(entry), [])
        return candidates[0] if candidates else None

    def _context(self, entry, arguments):
        key = thread_context_id(self.inputs.scope_id, entry, arguments, MODEL_ID, self.request["budgets"])
        if key in self.context_table:
            return self.context_table[key]
        if len(self.contexts) >= self.request["budgets"]["thread_contexts"]:
            self.cut = True
            item = diagnostic(
                "thread-context-budget", "线程上下文超过显式预算",
                "Thread contexts exceeded the explicit budget",
                context=key,
                suggestion="收紧分析根或提高 thread_contexts 预算",
                suggestion_en="Narrow the roots or increase the thread_contexts budget",
            )
            self.frontier.append(item); self.diagnostics.append(deepcopy(item))
            return None
        summary = self._summary(entry)
        status = summary["status"] if summary else "partial"
        reason = None if summary and status == "complete" else "effect-summary-incomplete" if summary else "effect-summary-missing"
        context = {
            "id": key, "entry": deepcopy(entry), "arguments": deepcopy(arguments),
            "status": status, "reason": reason,
            "dependency": _dependency("EffectSummary", summary["context_id"], summary) if summary else None,
        }
        if not self._append(self.contexts, context, context=key):
            return None
        self.context_table[key] = context
        if not summary:
            item = diagnostic(
                "effect-summary-missing", "线程入口缺少可消费的 P2 效果摘要",
                "The thread entry has no consumable P2 effect summary",
                context=key, suggestion="确认入口位于显式 scope 并先生成 P2 摘要",
                suggestion_en="Ensure the entry is in the explicit scope and generate its P2 summary",
            )
            self.frontier.append(item); self.diagnostics.append(deepcopy(item))
        return context

    def _instance(self, root_id, context, parent, create, cardinality="single", reason=None):
        key = thread_instance_id(root_id, context["id"], parent, create, cardinality, reason)
        if key in self.instance_table:
            return self.instance_table[key]
        if len(self.instances) >= self.request["budgets"]["thread_instances"]:
            self.cut = True
            item = diagnostic("thread-instance-budget", "线程实例超过显式预算",
                              "Thread instances exceeded the explicit budget",
                              context=context["id"], instance=parent)
            self.frontier.append(item); self.diagnostics.append(deepcopy(item))
            return None
        value = {"id": key, "root_id": root_id, "context_id": context["id"],
                 "parent_id": parent, "create": deepcopy(create),
                 "cardinality": cardinality, "reason": reason}
        if not self._append(self.instances, value, context=context["id"], instance=key):
            return None
        self.instance_table[key] = value
        if cardinality != "single":
            item = diagnostic(
                "thread-instance-merged", "重复或递归创建被合并为抽象线程实例",
                "Repeated or recursive creation was merged into an abstract thread instance",
                source=create, context=context["id"], instance=key,
                suggestion="将该实例视为可能代表多个动态线程",
                suggestion_en="Treat this instance as potentially representing multiple dynamic threads",
            )
            self.frontier.append(item); self.diagnostics.append(deepcopy(item))
        return value

    def _lifecycle(self, kind, instance, source=None, guards=(), status="may", proof=()):
        seed = {"kind": kind, "instance": instance["id"], "source": source, "guards": list(guards)}
        event = {"id": identity(seed), "kind": kind, "thread_instance_id": instance["id"],
                 "source": deepcopy(source), "guards": list(guards), "status": status,
                 "proof": deepcopy(list(proof))}
        return event if self._append(
            self.lifecycles, event, context=instance["context_id"], instance=instance["id"]
        ) else None

    def _anchor(self, kind, source, invocation, instance, status="may"):
        seed = {"kind": kind, "source": source, "invocation": invocation, "thread": instance["id"]}
        value = {"id": identity(seed), "kind": kind, "source": deepcopy(source),
                 "invocation_id": invocation, "thread_instance_id": instance["id"],
                 "status": status, "proof": [deepcopy(source)]}
        if self._append(self.anchors, value, context=instance["context_id"], instance=instance["id"]):
            self.anchor_by_instance_source[instance["id"]][_source_key(source)].append(value["id"])
            return value
        return None

    def _bind_summary(self, instance, summary):
        if not summary:
            return
        for invocation in summary["invocations"]:
            entry = invocation["function"]
            self._anchor("function-entry", entry, invocation["id"], instance)
            self._anchor("function-exit", entry, invocation["id"], instance)
            if invocation["callsite"] is not None:
                self._anchor("callsite", invocation["callsite"], invocation["parent_id"], instance)
        for effect in summary["effects"]:
            address = effect["address"]
            object_key, offset = _object_range(address, self.object_overlay)
            if object_key is None and self.source_assistance is not None:
                from .source_assistance import resolve_event_object
                resolved = resolve_event_object(
                    self.source_assistance["binding"], self.object_overlay, effect["source"])
                if resolved["status"] == "resolved":
                    object_key = resolved["program_object_id"]
                    offset = "0"
            value = effect["value"]
            bound = {
                "id": identity({"thread": instance["id"], "effect": effect["id"]}),
                "effect_id": effect["id"], "source": deepcopy(effect["source"]),
                "invocation_id": effect["invocation_id"], "thread_instance_id": instance["id"],
                "kind": effect["kind"], "object_key": object_key,
                "offset_bytes": offset, "size_bytes": effect["size_bytes"], "atomic": effect["atomic"],
                "ordering": effect["ordering"], "failure_ordering": effect["failure_ordering"],
                "syncscope": effect["syncscope"],
                "value_key": identity(value) if isinstance(value, dict) else None,
                "guards": [identity(guard) for guard in effect["guards"]],
            }
            if self._append(self.effects, bound, context=instance["context_id"], instance=instance["id"]):
                self.effect_by_instance_source[instance["id"]][_source_key(effect["source"])].append(bound["id"])
        self._bind_local_order(instance)
        self._bind_call_anchors(instance, summary)

    def _graph_edge(self, kind, before, after, relation, proof=(), guards=()):
        if before == after:
            return None
        seed = {"kind": kind, "before": before, "after": after, "relation": relation,
                "guards": list(guards)}
        value = {"id": identity(seed), **seed, "proof": deepcopy(list(proof))}
        if any(item["id"] == value["id"] for item in self.order):
            return value
        self._append(self.order, value)
        return value

    def _endpoints(self, instance_id, source):
        key = _source_key(source)
        return [*self.effect_by_instance_source[instance_id].get(key, ()),
                *self.anchor_by_instance_source[instance_id].get(key, ())]

    def _bind_local_order(self, instance):
        for edge in self.order_edges:
            before = self._endpoints(instance["id"], edge["before"])
            after = self._endpoints(instance["id"], edge["after"])
            if edge["relation"] == "mutually-exclusive":
                continue
            relation = edge["relation"] if edge["relation"] in {"must-before", "may-before"} else "unknown"
            for left in before:
                for right in after:
                    self._graph_edge("intra-thread", left, right, relation, edge["proof"])

    def _bind_call_anchors(self, instance, summary):
        for item in summary["invocations"]:
            if item["callsite"] is None:
                continue
            callsite_ids = self.anchor_by_instance_source[instance["id"]].get(_source_key(item["callsite"]), [])
            entry_ids = [anchor["id"] for anchor in self.anchors
                         if anchor["thread_instance_id"] == instance["id"] and anchor["invocation_id"] == item["id"] and anchor["kind"] == "function-entry"]
            exit_ids = [anchor["id"] for anchor in self.anchors
                        if anchor["thread_instance_id"] == instance["id"] and anchor["invocation_id"] == item["id"] and anchor["kind"] == "function-exit"]
            for left in callsite_ids:
                for right in entry_ids:
                    self._graph_edge("call-entry", left, right, "must-before", [item["callsite"]])
            call = self.calls_by_source.get(_source_key(item["callsite"]))
            if not call:
                continue
            if call["unwind_successor"] is not None:
                self._anchor("unwind-successor", call["unwind_successor"], item["id"], instance,
                             status="unknown")
            if call["noreturn"] or call["normal_successor"] is None:
                continue
            successor = self._anchor("normal-successor", call["normal_successor"], item["id"], instance)
            if successor is None:
                continue
            for left in exit_ids:
                self._graph_edge("call-exit", left, successor["id"], "may-before", [item["callsite"]])

    def _calls_for_summary(self, summary):
        if not summary:
            return []
        pairs = {_function_pair(item["function"]) for item in summary["invocations"]}
        return [call for pair in sorted(pairs) for call in self.calls_by_function.get(pair, ())]

    def _success_guard(self, call):
        return identity({"api-success": call["source"], "value": 0,
                         "test": call["success_test"]})

    def _expand(self, queue):
        expanded = set()
        while queue and not self.cut:
            instance, context, ancestry, allow_spawns = queue.popleft()
            summary = self._summary(context["entry"])
            self._bind_summary(instance, summary)
            exit_event = self._lifecycle("thread-exit", instance, context["entry"], status="may",
                                         proof=[context["entry"]])
            if exit_event is None:
                continue
            instance["exit_event"] = exit_event["id"]
            if not allow_spawns or not summary:
                continue
            expansion_key = (instance["id"], context["id"])
            if expansion_key in expanded:
                continue
            expanded.add(expansion_key)
            for call in self._calls_for_summary(summary):
                adoption = self.adoption_by_source.get(_source_key(call["source"]))
                if not adoption or adoption["kind"] != "adopted":
                    continue
                if adoption["event"] == "create":
                    guard = self._success_guard(call)
                    attempt = self._lifecycle("create-attempt", instance, call["source"], [guard], "may", [call["source"]])
                    if attempt is None:
                        break
                    target = self._resolve_callback_target(call["callback_targets"][0])
                    if target is None:
                        item = diagnostic(
                            "callback-target-unresolved", "线程回调目标无法在显式 scope 中唯一绑定",
                            "The thread callback target cannot be bound uniquely in the explicit scope",
                            source=call["source"], context=context["id"], instance=instance["id"],
                            suggestion="检查 scope 闭包、符号 linkage、COMDAT 和外部边界",
                            suggestion_en="Check the scope closure, linkage, COMDAT, and external boundaries",
                        )
                        self.frontier.append(item); self.diagnostics.append(deepcopy(item))
                        continue
                    argument = _argument(call["arguments"][3] if len(call["arguments"]) > 3 else None)
                    child_context = self._context(target, [argument])
                    if child_context is None:
                        continue
                    recursive = child_context["id"] in ancestry
                    repeated = self.order_multiplicity.get(_source_key(call["source"])) != "single"
                    cardinality = "merged" if recursive or repeated else "single"
                    reason = "recursive-thread-create" if recursive else "repeated-thread-create" if repeated else None
                    child = self._instance(instance["root_id"], child_context, instance["id"], call["source"], cardinality, reason)
                    if child is None:
                        continue
                    start = self._lifecycle("thread-start", child, call["source"], [guard], "may", [call["source"]])
                    if start is None:
                        continue
                    self._graph_edge("create", attempt["id"], start["id"], "may-before", [call["source"]], [guard])
                    self.create_records.append({"parent": instance, "child": child, "call": call,
                                                "guard": guard, "start": start["id"]})
                    queue.append((child, child_context, ancestry | {child_context["id"]}, not recursive))
                elif adoption["event"] == "join":
                    self.join_records.append({"parent": instance, "call": call,
                                              "guard": self._success_guard(call)})
                elif adoption["event"].startswith("mutex-"):
                    self.mutex_records.append({"thread": instance, "call": call,
                                               "event": adoption["event"], "guard": self._success_guard(call)})

    def _provenance_reaches(self, artifact, start, target, modeled_sources):
        if start is None or target is None:
            return False, True
        graph = defaultdict(set)
        unknown = False
        for item in self.local_facts[artifact]["provenance"]:
            source = _source_key(item["source"])
            value, obj = _source_key(item["value"]), _source_key(item["object"])
            if item["kind"] == "store" and value and obj:
                graph[value].add(obj)
            elif item["kind"] == "load" and obj:
                graph[obj].add(source)
            elif item["kind"] in {"cast", "phi", "select"} and value:
                graph[value].add(source)
            elif item["kind"] == "clobber" and source not in modeled_sources:
                unknown = True
        pending, seen = [_source_key(start)], set()
        goal = _source_key(target)
        while pending:
            value = pending.pop()
            if value == goal:
                return True, unknown
            if value in seen:
                continue
            seen.add(value); pending.extend(graph.get(value, ()))
        return False, unknown

    def _joins(self):
        modeled = set(self.adoption_by_source)
        for record in self.join_records:
            parent, call = record["parent"], record["call"]
            attempt = self._lifecycle("join-attempt", parent, call["source"], [record["guard"]], "may", [call["source"]])
            if attempt is None:
                return
            candidates, uncertain = [], False
            for create in self.create_records:
                if create["parent"]["id"] != parent["id"]:
                    continue
                reached, unknown = self._provenance_reaches(call["source"]["artifact_key"],
                    create["call"]["handle_source"], call["handle_source"], modeled)
                uncertain |= unknown
                if reached:
                    candidates.append(create)
            if len(candidates) != 1 or uncertain:
                item = diagnostic(
                    "join-handle-ambiguous", "pthread_join 的线程句柄无法唯一关联",
                    "The pthread_join handle cannot be associated uniquely",
                    source=call["source"], instance=parent["id"],
                    suggestion="检查句柄复制、覆盖、逃逸或未知调用",
                    suggestion_en="Check handle copies, overwrites, escapes, or unknown calls",
                )
                self.frontier.append(item); self.diagnostics.append(deepcopy(item))
                continue
            create = candidates[0]
            complete = self._lifecycle("join-complete", parent, call["source"], [record["guard"]], "may", [call["source"]])
            if complete is None:
                return
            child = create["child"]
            self._graph_edge("join", child["exit_event"], complete["id"], "may-before",
                             [call["source"]], [record["guard"]])
            for effect in self.effects:
                if effect["thread_instance_id"] != parent["id"]:
                    continue
                relation = self._local_relation(call["source"], effect["source"])
                if relation != "must-before":
                    continue
                left, right = sorted((parent["id"], child["id"]))
                seed = {"left": left, "right": right, "left_endpoint": child["exit_event"],
                        "right_endpoint": effect["id"], "relation": "not_parallel"}
                self._append(self.mhp, {"id": identity(seed), **seed, "guards": [record["guard"]],
                    "proof": [call["source"]], "reason": "successful-join-before-parent-effect"})

    def _local_relation(self, before, after):
        left, right = _source_key(before), _source_key(after)
        for edge in self.order_edges:
            if _source_key(edge["before"]) == left and _source_key(edge["after"]) == right:
                return edge["relation"]
        return None

    def _mhp(self):
        existing = {(item["left"], item["right"], item["left_endpoint"], item["right_endpoint"])
                    for item in self.mhp}
        for index, left_item in enumerate(self.instances):
            for right_item in self.instances[index + 1:]:
                if left_item["root_id"] != right_item["root_id"]:
                    continue
                left, right = sorted((left_item["id"], right_item["id"]))
                marker = (left, right, None, None)
                if marker in existing:
                    continue
                relation = "unknown" if "unknown" in {left_item["cardinality"], right_item["cardinality"]} else "may_parallel"
                seed = {"left": left, "right": right, "left_endpoint": None,
                        "right_endpoint": None, "relation": relation}
                self._append(self.mhp, {"id": identity(seed), **seed, "guards": [], "proof": [],
                    "reason": "lifecycle-overlap-candidate" if relation == "may_parallel" else "instance-cardinality-unknown"})

    def _mutex(self):
        groups = defaultdict(list)
        for item in self.mutex_records:
            source = item["call"]["mutex_source"]
            if source is not None:
                groups[_source_key(source)].append(item)
        for object_key, records in sorted(groups.items()):
            by_thread = defaultdict(list)
            for item in records:
                by_thread[item["thread"]["id"]].append(item)
            eligible = {}
            for thread, items in by_thread.items():
                locks = [item for item in items if item["event"] == "mutex-lock"]
                unlocks = [item for item in items if item["event"] == "mutex-unlock"]
                ordered = len(locks) == len(unlocks) == 1 and self._local_relation(
                    locks[0]["call"]["source"], unlocks[0]["call"]["source"]
                ) == "must-before"
                if ordered:
                    eligible[thread] = items
                    continue
                item = diagnostic(
                    "mutex-state-unknown", "mutex 获取与释放无法形成受支持的平衡区间",
                    "The mutex acquire and release do not form a supported balanced interval",
                    source=items[0]["call"]["source"], instance=thread,
                    suggestion="检查失败路径、提前或重复 unlock、循环及对象覆盖",
                    suggestion_en="Check failure paths, early or repeated unlocks, loops, and object clobbers",
                )
                self.frontier.append(item); self.diagnostics.append(deepcopy(item))
            threads = sorted(eligible)
            for index, left in enumerate(threads):
                for right in threads[index + 1:]:
                    left_events, right_events = eligible[left], eligible[right]
                    proof = [item["call"]["source"] for item in left_events + right_events]
                    seed = {"kind": "mutex", "object": object_key, "left": left, "right": right}
                    self._append(self.synchronization, {"id": identity(seed), "kind": "mutex",
                        "object_key": identity(object_key), "write_effect": None, "read_effect": None,
                        "left_thread": left, "right_thread": right, "status": "candidate",
                        "guards": sorted({item["guard"] for item in left_events + right_events}),
                        "proof": proof, "reason": "same-supported-mutex"})

    def _atomics(self):
        writes = [item for item in self.effects if item["atomic"] and item["kind"] in {"write", "rmw", "cas"}]
        reads = [item for item in self.effects if item["atomic"] and item["kind"] in {"read", "rmw", "cas"}]
        roots = {item["id"]: item["root_id"] for item in self.instances}
        for write in writes:
            for read in reads:
                if write["thread_instance_id"] == read["thread_instance_id"]:
                    continue
                if roots[write["thread_instance_id"]] != roots[read["thread_instance_id"]]:
                    continue
                if write["object_key"] is None or read["object_key"] is None:
                    continue
                same_object = write["object_key"] == read["object_key"]
                compatible_scope = write["syncscope"] != "singlethread" and read["syncscope"] != "singlethread"
                disjoint_range = same_object and _ranges_disjoint(write, read)
                status = "candidate" if same_object and compatible_scope and not disjoint_range else "excluded"
                reason = ("same-atomic-object-may-read-from" if status == "candidate" else
                          "incompatible-syncscope" if same_object and not compatible_scope else
                          "disjoint-atomic-range" if disjoint_range else "disjoint-atomic-object")
                seed = {"kind": "reads-from", "write": write["id"], "read": read["id"]}
                self._append(self.synchronization, {"id": identity(seed), "kind": "reads-from",
                    "object_key": write["object_key"] if status == "candidate" else None,
                    "write_effect": write["id"], "read_effect": read["id"],
                    "left_thread": write["thread_instance_id"], "right_thread": read["thread_instance_id"],
                    "status": status, "guards": sorted(set(write["guards"] + read["guards"])),
                    "proof": [write["source"], read["source"]], "reason": reason})

    def build(self):
        queue = deque()
        for root in self.request["roots"]:
            entry = {"artifact_key": root["artifact_key"], "function_id": None, "id": root["function_id"]}
            context = self._context(entry, root["arguments"])
            if context is None:
                raise AnalysisError("thread_graph_budget", "Thread graph budget cannot represent every explicit root")
            root_id = identity({"root": root})
            instance = self._instance(root_id, context, None, None)
            if instance is None:
                raise AnalysisError("thread_graph_budget", "Thread graph budget cannot represent every explicit root")
            if self._lifecycle("root-start", instance, entry, status="must", proof=[entry]) is None:
                raise AnalysisError("thread_graph_budget", "Thread graph budget cannot represent every explicit root")
            queue.append((instance, context, {context["id"]}, True))
        self._expand(queue)
        self._joins()
        self._mhp()
        self._mutex()
        self._atomics()
        for instance in self.instances:
            instance.pop("exit_event", None)
        dependencies = []
        for key in sorted(self.local_facts):
            dependencies.append(_dependency("ThreadLocalFacts", key, self.local_facts[key]))
            dependencies.append(_dependency("ExecutionOrderFacts", key, self.order_facts[key]))
        for summary in self.summaries:
            dependencies.append(_dependency("EffectSummary", summary["context_id"], summary))
        if self.source_assistance is not None:
            dependencies.append(_dependency("SourceIRBinding", self.inputs.scope_id,
                                            self.source_assistance["binding"]))
            dependencies.append(_dependency("CanonicalObjectOverlay", self.inputs.scope_id,
                                            self.source_assistance["overlay"]))
        partial_inputs = any(item["status"] != "complete" for item in [*self.local_facts.values(), *self.order_facts.values()])
        source_partial = (self.source_assistance is not None and
                          any(self.source_assistance[name]["status"] != "complete"
                              for name in ("binding", "overlay")))
        status = "partial" if self.cut or self.frontier or partial_inputs or source_partial or any(item["status"] != "complete" for item in self.contexts) else "complete"
        return thread_document(
            "ThreadContextGraph", scope_id=self.inputs.scope_id,
            request_hash=identity(self.request), model_id=MODEL_ID,
            budgets=self.request["budgets"], dependencies=dependencies,
            contexts=self.contexts, instances=self.instances, lifecycles=self.lifecycles,
            effects=self.effects, anchors=self.anchors, order=self.order, mhp=self.mhp,
            synchronization=self.synchronization, frontier=self.frontier,
            diagnostics=self.diagnostics, status=status,
        )


def build_thread_graph(inputs, request, local_facts, order_facts, summaries,
                       source_assistance=None):
    if not request["roots"]:
        raise AnalysisError("invalid_root", "Thread analysis requires explicit roots")
    functions = {(key, item["id"]): item for key, module in inputs.modules.items()
                 for item in module["functions"]}
    for root in request["roots"]:
        pair = root["artifact_key"], root["function_id"]
        if pair not in functions or functions[pair]["declaration"]:
            raise AnalysisError("invalid_root", f"Root is not a defined scope member: {pair}")
    return ThreadGraphBuilder(inputs, request, local_facts, order_facts, summaries,
                              source_assistance).build()
