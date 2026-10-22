"""Compose P1/P2/P3 and P4 local facts into the bounded P4 protocol model."""

from collections import defaultdict, deque
from copy import deepcopy

from .contracts import canonical, identity
from .publication_contracts import (
    MODEL_ID,
    diagnostic,
    outcome_counts,
    protocol_candidate_id,
    publication_document,
    successful_observation_id,
)


def _key(value):
    return canonical(value) if value is not None else None


def _dependency(kind, identifier, value):
    return {"kind": kind, "id": identifier, "digest": identity(value)}


def _object_key(object_range, overlay=None):
    source = object_range.get("object") if isinstance(object_range, dict) else None
    address_space = object_range.get("address_space") if isinstance(object_range, dict) else None
    if source is None or address_space is None:
        return None
    if overlay is not None:
        from .source_assistance import resolve_object
        resolved = resolve_object(overlay, source)
        if resolved["status"] == "resolved":
            return resolved["program_object_id"]
    return identity({"kind": "object", "source": source, "address_space": address_space,
                     "allocation": None})


def _overlap(left, right):
    if left.get("object_key") != right.get("object_key"):
        return False
    try:
        a, b = int(left["offset_bytes"]), int(right["offset_bytes"])
        x, y = int(left["size_bytes"]), int(right["size_bytes"])
    except (KeyError, TypeError, ValueError):
        return False
    return a < b + y and b < a + x


def _in_blocks(source, blocks):
    if not isinstance(source, dict):
        return False
    return any(source["artifact_key"] == block["artifact_key"] and
               source["function_id"] == block["function_id"] and
               source["id"].startswith(block["id"] + ":") for block in blocks)


def _predicate_accepts(predicate, scalar):
    if not predicate or scalar.get("state") != "exact" or scalar.get("bits") != predicate.get("bits"):
        return None
    value = int(scalar["hex"], 16)
    kind = predicate["kind"]
    expected = int(predicate["hex"], 16) if predicate.get("hex") is not None else 0
    accepted = value == expected if kind in {"eq", "zero"} else value != expected
    return not accepted if predicate.get("negated") else accepted


class PublicationGraphBuilder:
    def __init__(self, inputs, request, thread_graph, local_facts, summaries, profiles,
                 order_facts=None, source_assistance=None):
        self.inputs = inputs
        self.request = deepcopy(request)
        self.thread_graph = deepcopy(thread_graph)
        self.local_facts = deepcopy(local_facts)
        self.summaries = deepcopy(summaries)
        self.profiles = deepcopy(profiles)
        self.order_facts = deepcopy(order_facts or {})
        self.source_assistance = deepcopy(source_assistance)
        self.object_overlay = (self.source_assistance["overlay"]
                               if self.source_assistance is not None else None)
        self.effects = {item["id"]: item for item in thread_graph["effects"]}
        self._augment_local_effects()
        self.effects_by_source = defaultdict(list)
        self.effects_by_object = defaultdict(list)
        for effect in self.effects.values():
            self.effects_by_source[_key(effect["source"])].append(effect)
            self.effects_by_object[effect["object_key"]].append(effect)
        self.summary_effects = {effect["id"]: effect for summary in summaries.values()
                                for effect in summary["effects"]}
        self.invocations = {item["id"]: item for summary in summaries.values()
                            for item in summary["invocations"]}
        self.accesses = {}
        self.access_by_source = defaultdict(list)
        self.initializers = defaultdict(list)
        self.observations = {}
        self.gates_by_observation = defaultdict(list)
        returns = []
        for facts in local_facts.values():
            for access in facts["accesses"]:
                self.accesses[(facts["origin"]["artifact_key"], access["id"])] = access
                self.access_by_source[_key(access["source"])].append(access)
            for initializer in facts["initializers"]:
                self.initializers[_object_key(initializer["range"], self.object_overlay)].append(initializer)
            for observation in facts["observations"]:
                self.observations[(facts["origin"]["artifact_key"], observation["id"])] = observation
            for gate in facts["gates"]:
                self.gates_by_observation[(facts["origin"]["artifact_key"], gate["observation_id"])].append(gate)
            returns.extend((facts["origin"]["artifact_key"], item) for item in facts["returns"])
        self.return_access_sources = defaultdict(set)
        for artifact, item in returns:
            observation = self.observations.get((artifact, item["observation_id"]))
            access = self.accesses.get((artifact, observation["access_id"])) if observation else None
            if access:
                self.return_access_sources[(artifact, item["source"]["function_id"])].add(_key(access["source"]))
        self.order = defaultdict(set)
        for edge in thread_graph["order"]:
            if edge["relation"] == "must-before":
                self.order[edge["before"]].add(edge["after"])
        self._bind_supplemental_order()
        if self.source_assistance is not None:
            from .source_assistance import ast_sequence_edges
            for before, after in ast_sequence_edges(
                    self.source_assistance, self.inputs.modules, self.effects):
                self.order[before].add(after)
        self.parallel = {}
        for edge in thread_graph["mhp"]:
            self.parallel[tuple(sorted((edge["left"], edge["right"])))] = edge["relation"]
        self.successful, self.protocols, self.assessments = [], [], []
        self.frontier, self.diagnostics = [], []
        self.cut = False

    def _augment_local_effects(self):
        """Bind P4 local accesses when a P2 summary deliberately stayed partial.

        These IDs are P4 analysis nodes and never masquerade as P1/P2 events.
        """
        contexts = {item["id"]: item for item in self.thread_graph.get("contexts", [])}
        by_source = {(item["thread_instance_id"], _key(item["source"])) for item in self.effects.values()}
        for instance in self.thread_graph.get("instances", []):
            context = contexts.get(instance["context_id"])
            if not context:
                continue
            # A bound P2 summary has already specialized library wrappers and
            # constant memory-order branches for this context.  Raw P4 local
            # accesses are only a fallback for a genuinely missing summary;
            # mixing both would reintroduce unreachable C++ atomic variants.
            if context.get("dependency") is not None:
                continue
            entry = context["entry"]
            facts = self.local_facts.get(entry["artifact_key"])
            if not facts:
                continue
            for access in facts["accesses"]:
                if access["source"]["function_id"] != entry["id"] or access["kind"] == "call":
                    continue
                marker = instance["id"], _key(access["source"])
                if marker in by_source:
                    continue
                identifier = identity({"layer": "publication-local-thread-access-v1",
                                       "thread": instance["id"], "access": access["id"]})
                object_range = access["range"]
                self.effects[identifier] = {
                    "id": identifier, "effect_id": access["id"], "source": deepcopy(access["source"]),
                    "invocation_id": identity({"p4-local-invocation": instance["id"], "function": entry}),
                    "thread_instance_id": instance["id"], "kind": access["kind"],
                    "object_key": _object_key(object_range, self.object_overlay), "offset_bytes": object_range["offset_bytes"],
                    "size_bytes": object_range["size_bytes"], "atomic": access["atomic"],
                    "ordering": access["ordering"], "failure_ordering": None,
                    "syncscope": access["syncscope"], "value_key": identity(access["value"]),
                    "guards": [], "_p4_multiplicity": access["multiplicity"],
                }
                by_source.add(marker)

    def _bind_supplemental_order(self):
        endpoints = defaultdict(list)
        for effect in self.effects.values():
            endpoints[(effect["thread_instance_id"], _key(effect["source"]))].append(effect["id"])
        edge_sets = [facts.get("order", ()) for facts in self.local_facts.values()]
        edge_sets.extend(facts["edges"] for facts in self.order_facts.values())
        for instance in self.thread_graph.get("instances", []):
            for edges in edge_sets:
                for edge in edges:
                    if edge["relation"] != "must-before":
                        continue
                    before = endpoints.get((instance["id"], _key(edge["before"])), ())
                    after = endpoints.get((instance["id"], _key(edge["after"])), ())
                    for left in before:
                        for right in after:
                            self.order[left].add(right)

    def _before(self, before, after):
        pending, seen = deque([before]), set()
        while pending:
            current = pending.popleft()
            if current == after:
                return True
            if current in seen:
                continue
            seen.add(current)
            pending.extend(sorted(self.order.get(current, ())))
        return False

    def _profile(self, *artifacts):
        values = {self.profiles.get(artifact) for artifact in artifacts}
        return values.pop() if len(values) == 1 and None not in values else None

    def _local_access(self, effect):
        matches = self.access_by_source.get(_key(effect["source"]), ())
        return matches[0] if len(matches) == 1 else None

    def _bound_effects(self, observation):
        access = self.accesses.get((observation["source"]["artifact_key"], observation["access_id"]))
        if not access:
            return []
        direct = self.effects_by_source.get(_key(access["source"]), ())
        if access["kind"] != "call":
            return list(direct)
        result = []
        for effect in self.effects.values():
            invocation = self.invocations.get(effect["invocation_id"])
            function = invocation.get("function") if invocation else None
            returned = (self.return_access_sources.get((function["artifact_key"], function["id"]), set())
                        if isinstance(function, dict) else set())
            if (invocation and _key(invocation.get("callsite")) == _key(access["source"]) and
                    _key(effect["source"]) in returned):
                result.append(effect)
        return result

    def _successful_observations(self):
        for (artifact, observation_id), observation in sorted(self.observations.items()):
            if observation["predicate"] is None:
                continue
            for gate in self.gates_by_observation.get((artifact, observation_id), ()):
                for effect in self._bound_effects(observation):
                    if effect["kind"] != "read":
                        continue
                    identifier = successful_observation_id(
                        observation_id, effect["id"], effect["thread_instance_id"],
                        effect["invocation_id"], observation["predicate"], gate["id"])
                    status = "exact" if observation["status"] == gate["status"] == "exact" else "candidate"
                    self.successful.append({
                        "id": identifier, "local_observation_id": observation_id,
                        "thread_effect_id": effect["id"], "thread_instance_id": effect["thread_instance_id"],
                        "invocation_id": effect["invocation_id"], "predicate": deepcopy(observation["predicate"]),
                        "gate_id": gate["id"], "guards": sorted(set(effect["guards"])),
                        "proof": [deepcopy(observation["source"]), deepcopy(gate["terminator"])],
                        "status": status, "reason": None if status == "exact" else "local-gate-candidate",
                        "_blocks": deepcopy(gate["controlled_blocks"]),
                    })

    def _mhp(self, left, right):
        return self.parallel.get(tuple(sorted((left, right))))

    def _candidate_pairs(self, observation):
        flag_read = self.effects[observation["thread_effect_id"]]
        for flag_write in self.effects_by_object.get(flag_read["object_key"], ()):
            if flag_write["kind"] != "write" or flag_write["thread_instance_id"] == flag_read["thread_instance_id"]:
                continue
            relation = self._mhp(flag_write["thread_instance_id"], flag_read["thread_instance_id"])
            if relation not in {"may_parallel", "unknown"}:
                continue
            publisher = flag_write["thread_instance_id"]
            consumer = flag_read["thread_instance_id"]
            payload_writes = [item for item in self.effects.values()
                              if item["thread_instance_id"] == publisher and item["kind"] in {"write", "rmw", "cas"}
                              and item["object_key"] != flag_read["object_key"]]
            payload_reads = [item for item in self.effects.values()
                             if item["thread_instance_id"] == consumer and item["kind"] == "read"
                             and item["object_key"] != flag_read["object_key"]
                             and _in_blocks(item["source"], observation["_blocks"])]
            for payload_write in payload_writes:
                for payload_read in payload_reads:
                    if _overlap(payload_write, payload_read):
                        yield flag_write, flag_read, payload_write, payload_read, relation

    def _assessment(self, protocol_id, kind, code, status, severity, confidence, events,
                    missing=(), assumptions=(), limitations=(), evidence=(), suggestion=None,
                    suggestion_en=None):
        prose = {
            "ordinary-conflict": ("一次性发布中的普通对象访问可能并行冲突", "Ordinary accesses in the publication protocol may conflict in parallel"),
            "missing-release": ("发布写不是 release-capable，无法建立发布顺序", "The publication store is not release-capable, so publication ordering is not established"),
            "missing-acquire": ("成功观察读不是 acquire-capable，无法建立发布顺序", "The successful observation load is not acquire-capable, so publication ordering is not established"),
            "acquire-too-late": ("另一个 acquire 发生在 payload 使用之后，不能修复当前观察", "Another acquire occurs after the payload use and cannot repair this observation"),
            "publication-store-too-early": ("flag 发布写已证明早于 payload 写", "The flag publication store is proved to occur before the payload write"),
            "all-atomic-relaxed": ("flag 与 payload 均为原子，但 relaxed 顺序不能证明发布关系", "Flag and payload are atomic, but relaxed ordering does not prove publication"),
            "single-publication-discharged": ("受限一次性发布模型内已建立 release/acquire 证明链", "A release/acquire proof chain is established within the bounded single-publication model"),
            "protocol-unknown": ("相关证据不足，无法对该发布候选给出确定结论", "Relevant evidence is incomplete, so this publication candidate is inconclusive"),
            "protocol-unsupported": ("候选使用首版模型不支持的同步或发布形式", "The candidate uses synchronization or publication forms unsupported by the first model"),
        }
        detail, detail_en = prose[code]
        seed = {"protocol": protocol_id, "kind": kind, "code": code, "status": status,
                "events": list(events), "missing": list(missing),
                "assumptions": list(assumptions), "limitations": list(limitations)}
        return {"id": identity(seed), "protocol_id": protocol_id, "kind": kind, "code": code,
                "status": status, "severity": severity, "confidence": confidence,
                "detail": detail, "detail_en": detail_en, "suggestion": suggestion,
                "suggestion_en": suggestion_en, "events": list(events),
                "missing_edges": list(missing), "assumptions": list(assumptions),
                "limitations": list(limitations), "evidence": deepcopy(list(evidence))}

    def _evaluate(self, protocol, flag_write, flag_read, payload_write, payload_read, relation):
        events = [payload_write["id"], flag_write["id"], flag_read["id"], payload_read["id"]]
        evidence = [item["source"] for item in (payload_write, flag_write, flag_read, payload_read)]
        assumptions = ["single-publication-model", "successful-observation-is-conditional"]
        summary_write = self.summary_effects.get(flag_write["effect_id"])
        write_access, read_access = self._local_access(flag_write), self._local_access(flag_read)
        payload_before = self._before(payload_write["id"], flag_write["id"])
        too_early = self._before(flag_write["id"], payload_write["id"])
        fences = [item for item in self.effects.values()
                  if item["thread_instance_id"] in {flag_write["thread_instance_id"], flag_read["thread_instance_id"]}
                  and item["kind"] in {"fence", "rmw", "cas"}]
        profile = protocol["language_profile"]
        if relation == "unknown" or profile is None or fences:
            return [self._assessment(protocol["id"], "unsupported" if fences else "unknown",
                "protocol-unsupported" if fences else "protocol-unknown",
                "unsupported" if fences else "unknown", "info", "unknown", events,
                limitations=["fence-or-rmw-cas" if fences else "incomplete-profile-or-mhp"], evidence=evidence)]

        writers = [item for item in self.effects_by_object[flag_read["object_key"]]
                   if item["kind"] in {"write", "rmw", "cas"}]
        initializers = self.initializers.get(flag_read["object_key"], ())
        initial = initializers[0]["value"] if len(initializers) == 1 else {"state": "unknown", "reason": "initializer-not-unique"}
        published = write_access["value"] if write_access else {"state": "unknown", "reason": "publish-value-unavailable"}
        initial_accepts = _predicate_accepts(protocol["predicate"], initial)
        publish_accepts = _predicate_accepts(protocol["predicate"], published)
        multiplicity = (summary_write["multiplicity"] if summary_write is not None else
                        flag_write.get("_p4_multiplicity", "unknown"))
        unique = (len(writers) == 1 and multiplicity == "single" and
                  flag_write["kind"] == "write" and
                  self.inputs.scope["closed"] and not self.inputs.scope["external_boundaries"] and
                  flag_write["syncscope"] != "singlethread" and flag_read["syncscope"] != "singlethread" and
                  initial_accepts is False and publish_accepts is True)
        protocol["unique_reads_from"] = "proved" if unique else "unknown"

        if not flag_write["atomic"] or not flag_read["atomic"]:
            return [self._assessment(protocol["id"], "potential-data-race", "ordinary-conflict",
                "finding", "high", "conditional", events,
                missing=["atomic-communication", "happens-before"], assumptions=assumptions,
                evidence=evidence, suggestion="将 flag 改为与该协议匹配的原子 release/acquire 通信",
                suggestion_en="Use atomic release/acquire communication for the flag in this protocol")]
        if not unique:
            return [self._assessment(protocol["id"], "unknown", "protocol-unknown", "unknown",
                "info", "unknown", events, missing=["unique-reads-from"],
                assumptions=assumptions, evidence=evidence)]
        if too_early:
            return [self._assessment(protocol["id"], "publication-order-risk", "publication-store-too-early",
                "finding", "high", "proved-within-model", events,
                missing=["payload-write-before-publication-store"], assumptions=assumptions, evidence=evidence,
                suggestion="将 payload 写移动到发布 flag 之前",
                suggestion_en="Move the payload write before publishing the flag")]
        if not payload_before:
            return [self._assessment(protocol["id"], "unknown", "protocol-unknown", "unknown",
                "info", "unknown", events, missing=["payload-write-before-publication-store"],
                assumptions=assumptions, evidence=evidence)]

        release = flag_write["ordering"] in {"release", "acq_rel", "seq_cst"}
        acquire = flag_read["ordering"] in {"acquire", "acq_rel", "seq_cst"}
        payload_atomic = payload_write["atomic"] and payload_read["atomic"]
        assessments = []
        if not release:
            code = "all-atomic-relaxed" if payload_atomic else "missing-release"
            assessments.append(self._assessment(protocol["id"], "publication-order-risk", code,
                "finding", "high", "proved-within-model", events, missing=["release-store"],
                assumptions=assumptions, evidence=evidence,
                suggestion="为发布 flag 写使用 release 顺序",
                suggestion_en="Use release ordering for the publication flag store"))
        if not acquire:
            later = any(item["thread_instance_id"] == flag_read["thread_instance_id"] and
                        item["object_key"] == flag_read["object_key"] and item["kind"] == "read" and
                        item["ordering"] in {"acquire", "seq_cst"} and
                        self._before(payload_read["id"], item["id"]) for item in self.effects.values())
            code = "acquire-too-late" if later else "all-atomic-relaxed" if payload_atomic else "missing-acquire"
            assessments.append(self._assessment(protocol["id"], "publication-order-risk", code,
                "finding", "high", "proved-within-model", events, missing=["acquire-load"],
                assumptions=assumptions, evidence=evidence,
                suggestion="在控制 payload 使用的 flag 观察上使用 acquire 顺序",
                suggestion_en="Use acquire ordering on the flag observation that controls the payload use"))
        if not payload_atomic and (not release or not acquire):
            assessments.append(self._assessment(protocol["id"], "potential-data-race", "ordinary-conflict",
                "finding", "high", "conditional", events, missing=["happens-before"],
                assumptions=assumptions, evidence=evidence,
                suggestion="建立完整 release/acquire 发布链或使用适合的原子 payload",
                suggestion_en="Establish a complete release/acquire publication chain or use suitable atomic payload access"))
        if not assessments:
            assessments.append(self._assessment(protocol["id"], "discharged", "single-publication-discharged",
                "discharged", "info", "proved-within-model", events,
                assumptions=assumptions, limitations=["not-a-whole-program-safety-proof"], evidence=evidence))
            protocol["chain"] = ["payload-write-before-flag-store", "unique-reads-from",
                                 "synchronizes-with", "flag-observation-before-payload-read"]
        return assessments

    def build(self):
        self._successful_observations()
        for successful in sorted(self.successful, key=lambda item: item["id"]):
            for flag_write, flag_read, payload_write, payload_read, relation in self._candidate_pairs(successful):
                if len(self.protocols) >= self.request["budgets"]["protocol_candidates"]:
                    self.cut = True
                    break
                roles = {"publisher": flag_write["thread_instance_id"], "consumer": flag_read["thread_instance_id"],
                         "flag_write": flag_write["id"], "flag_read": flag_read["id"],
                         "observation": successful["id"], "payload_write": payload_write["id"],
                         "payload_read": payload_read["id"]}
                identifier = protocol_candidate_id(**roles)
                profile = self._profile(*(item["source"]["artifact_key"] for item in
                                          (flag_write, flag_read, payload_write, payload_read)))
                protocol = {"id": identifier, "publisher_thread": roles["publisher"],
                    "consumer_thread": roles["consumer"], "flag_write": flag_write["id"],
                    "flag_read": flag_read["id"], "successful_observation": successful["id"],
                    "payload_write": payload_write["id"], "payload_read": payload_read["id"],
                    "flag_object": flag_read["object_key"], "payload_object": payload_read["object_key"],
                    "predicate": deepcopy(successful["predicate"]), "guards": sorted(set(
                        successful["guards"] + flag_write["guards"] + payload_write["guards"] + payload_read["guards"])),
                    "language_profile": profile, "unique_reads_from": "candidate", "chain": [],
                    "assessment_ids": [], "status": "candidate", "reason": None}
                assessments = self._evaluate(protocol, flag_write, flag_read, payload_write, payload_read, relation)
                if len(self.assessments) + len(assessments) > self.request["budgets"]["assessments"]:
                    self.cut = True
                    break
                protocol["assessment_ids"] = [item["id"] for item in assessments]
                states = {item["status"] for item in assessments}
                protocol["status"] = "unsupported" if "unsupported" in states else "unknown" if "unknown" in states else "evaluated"
                protocol["reason"] = None if protocol["status"] == "evaluated" else "assessment-incomplete"
                self.protocols.append(protocol); self.assessments.extend(assessments)
            if self.cut:
                break
        for item in self.successful:
            item.pop("_blocks", None)
        for effect in self.effects.values():
            effect.pop("_p4_multiplicity", None)
        relevant_without_protocol = (self.source_assistance is not None and not self.protocols and
                                     bool(self.successful) and any(
                                         item["kind"] in {"write", "rmw", "cas"}
                                         for item in self.effects.values()))
        if relevant_without_protocol:
            item = diagnostic(
                "publication-candidate-unresolved",
                "已发现成功发布观察及写入效果，但未能形成可求值的一次性发布协议候选",
                "A successful publication observation and write effects exist, but no evaluable single-publication candidate could be formed",
                source=self.successful[0]["proof"][0],
                suggestion="检查候选相关的跨 TU 对象绑定、MHP 与 payload 控制依赖证据",
                suggestion_en="Inspect candidate-relevant cross-TU object binding, MHP, and payload control-dependency evidence")
            self.frontier.append(item); self.diagnostics.append(deepcopy(item))
        if self.cut:
            item = diagnostic("publication-graph-budget", "发布协议图超过显式预算",
                              "The publication protocol graph exceeded its explicit budget",
                              suggestion="收紧 scope 或提高 P4 预算后重试",
                              suggestion_en="Narrow the scope or increase the P4 budget and retry")
            self.frontier.append(item); self.diagnostics.append(deepcopy(item))
        dependencies = [_dependency("ThreadContextGraph", identity(self.thread_graph), self.thread_graph)]
        dependencies.extend(_dependency("PublicationLocalFacts", key, value)
                            for key, value in sorted(self.local_facts.items()))
        dependencies.extend(_dependency("ExecutionOrderFacts", key, value)
                            for key, value in sorted(self.order_facts.items()))
        dependencies.extend(_dependency("EffectSummary", key, value)
                            for key, value in sorted(self.summaries.items()))
        if self.source_assistance is not None:
            dependencies.append(_dependency("SourceIRBinding", self.inputs.scope_id,
                                            self.source_assistance["binding"]))
            dependencies.append(_dependency("CanonicalObjectOverlay", self.inputs.scope_id,
                                            self.source_assistance["overlay"]))
            dependencies.extend(_dependency("SourceSemanticFacts", item["physical_tu_id"], item)
                                for item in self.source_assistance.get("source_facts", []))
        thread_relevant_partial = (self.thread_graph["status"] != "complete" and
                                   (bool(self.thread_graph.get("frontier")) or any(
                                       item.get("status") != "complete"
                                       for item in self.thread_graph.get("contexts", []))))
        partial = (self.cut or thread_relevant_partial or bool(self.frontier) or
                   any(item["status"] != "complete" for item in self.local_facts.values()) or
                   any(item["status"] in {"unknown", "unsupported"} for item in self.protocols))
        return publication_document(
            "SinglePublicationProtocolGraph", model_id=MODEL_ID, scope_id=self.inputs.scope_id,
            request_hash=identity(self.request), thread_graph_digest=identity(self.thread_graph),
            budgets=self.request["budgets"], dependencies=dependencies,
            successful_observations=sorted(self.successful, key=lambda item: item["id"]),
            protocols=sorted(self.protocols, key=lambda item: item["id"]),
            assessments=sorted(self.assessments, key=lambda item: item["id"]),
            counts=outcome_counts(self.protocols, self.assessments), frontier=self.frontier,
            diagnostics=self.diagnostics, status="partial" if partial else "complete")


def build_publication_graph(inputs, request, thread_graph, local_facts, summaries, profiles,
                            order_facts=None, source_assistance=None):
    return PublicationGraphBuilder(inputs, request, thread_graph, local_facts, summaries, profiles,
                                   order_facts, source_assistance).build()
