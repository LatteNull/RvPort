"""Projection helpers that keep formal, source-only, and discharged results distinct."""

from copy import deepcopy

from .contracts import AnalysisError, identity
from .finding_contracts import finding_document


PRODUCER = "org.rvport.memory-order-analyzer.unified-projection"


def _id(prefix, value):
    return f"{prefix}:{identity(value)}"


class EvidenceChainBuilder:
    def __init__(self, *, max_depth=128, max_visited=4096, max_paths=64):
        if min(max_depth, max_visited, max_paths) < 1:
            raise AnalysisError("finding_budget", "Evidence-chain budgets must be positive")
        self.maximum = (max_depth, max_visited, max_paths)
        self.steps, self.edges, self.breaks = [], [], []

    def step(self, kind, title, title_en, provenance, *, status="complete", reason="证据已验证",
             reason_en="Evidence is verified", reason_codes=(), source=None, data=None):
        seed = {"kind": kind, "title": title, "source": source, "provenance": provenance, "data": data or {}}
        identifier = _id("step", seed)
        item = {"id": identifier, "kind": kind, "title": title, "title_en": title_en,
                "status": status, "reason": reason, "reason_en": reason_en,
                "reasonCodes": sorted(set(reason_codes)), "source": deepcopy(source),
                "provenance": deepcopy(provenance), "data": deepcopy(data or {})}
        if identifier not in {value["id"] for value in self.steps}:
            self.steps.append(item)
        return identifier

    def edge(self, source, target, kind, provenance, *, status="complete", reason_codes=()):
        if source not in {item["id"] for item in self.steps} or target not in {item["id"] for item in self.steps}:
            raise AnalysisError("invalid_reference", "Evidence edge endpoints must already exist")
        item = {"id": _id("edge", {"from": source, "to": target, "kind": kind}),
                "fromStepId": source, "toStepId": target, "kind": kind, "status": status,
                "reasonCodes": sorted(set(reason_codes)), "provenance": deepcopy(provenance)}
        if item["id"] not in {value["id"] for value in self.edges}:
            self.edges.append(item)
        return item["id"]

    def gap(self, reason_code, stage, detail, detail_en, suggestion, suggestion_en, *,
            status="unknown", from_step=None, candidates=(), expected_kind=None, missing_id=None):
        item = {"id": _id("break", {"reason": reason_code, "stage": stage, "from": from_step,
                                     "candidates": sorted(candidates), "missing": missing_id}),
                "status": status, "reasonCode": reason_code, "stage": stage,
                "fromStepId": from_step, "candidateStepIds": sorted(set(candidates)),
                "expectedKind": expected_kind, "missingId": missing_id,
                "detail": detail, "detail_en": detail_en,
                "suggestion": suggestion, "suggestion_en": suggestion_en}
        self.breaks.append(item)
        return item["id"]

    def build(self, root, primary_path, *, impacts=(), force_status=None):
        max_depth, max_visited, max_paths = self.maximum
        if len(self.steps) > max_visited or len(primary_path) > max_depth:
            self.gap("evidence-budget-exhausted", "projection", "证据链预算耗尽",
                     "Evidence-chain budget was exhausted", "提高证据链预算后重试",
                     "Retry with a larger evidence-chain budget", status="partial", from_step=root)
        truncated = len(self.steps) > max_visited or len(primary_path) > max_depth
        steps = sorted(self.steps[:max_visited], key=lambda item: item["id"])
        kept = {item["id"] for item in steps}
        edges = sorted((item for item in self.edges if item["fromStepId"] in kept and item["toStepId"] in kept),
                       key=lambda item: item["id"])
        path = [item for item in primary_path[:max_depth] if item in kept]
        breaks = sorted(self.breaks, key=lambda item: item["id"])
        status = force_status or ("partial" if truncated else
                                  "unknown" if breaks else "complete")
        reasons = sorted({item["reasonCode"] for item in breaks})
        return {"status": status, "reasonCodes": reasons, "rootStepId": root,
                "primaryPath": path, "steps": steps, "edges": edges, "breaks": breaks,
                "impactStepIds": sorted(set(impacts) & kept),
                "budget": {"maxDepth": max_depth, "maxVisited": max_visited,
                           "maxPaths": max_paths, "visited": min(len(self.steps), max_visited),
                           "paths": 1 if path else 0, "truncated": truncated}}


def project_assessment(scope_id, assessment, provenance, *, category, location=None,
                       chain=None, finding_type="memory-order", symbol=None, locations=()):
    location = locations[0]["location"] if locations else location
    if category not in {"formal", "source", "discharged", "inconclusive"}:
        raise AnalysisError("projection_invalid", f"Unknown projection category: {category}")
    verdict = {"formal": "risk", "source": "source-candidate",
               "discharged": "discharged-within-bounded-model",
               "inconclusive": "inconclusive"}[category]
    status = "complete" if category in {"formal", "discharged"} else "unknown"
    if chain is None:
        builder = EvidenceChainBuilder()
        root = builder.step("conclusion", "分析结论", "Analysis conclusion", provenance,
                            status=status, source=location)
        if status != "complete":
            builder.gap("evidence-incomplete", "projection", "证据不足，不能形成正式结论",
                        "Evidence is insufficient for a formal conclusion", "补充 BC、绑定或同步证据",
                        "Provide bitcode, binding, or synchronization evidence", from_step=root)
        chain = builder.build(root, [root], impacts=[root], force_status=status)
    if chain["status"] == "complete" and category in {"source", "inconclusive"}:
        raise AnalysisError("safety_claim", "Source or inconclusive projections require an evidence break")
    identifier = _id("finding", {"scope": scope_id, "category": category,
                                  "assessment": assessment.get("id") or assessment})
    occurrence_id = _id("occurrence", {"finding": identifier, "location": location})
    titles = {
        "formal": ("发现受支持模型内的内存序风险", "Memory-order risk found within the supported model"),
        "source": ("发现仅有源码证据的候选", "Source-evidence-only candidate found"),
        "discharged": ("在受限模型内已消解", "Discharged within the bounded model"),
        "inconclusive": ("证据不足，结论不确定", "Evidence is incomplete; conclusion is inconclusive"),
    }
    title, title_en = titles[category]
    title = str(assessment.get("title") or title)
    title_en = str(assessment.get("title_en") or title_en)
    reason = str(assessment.get("reason") or titles[category][0])
    reason_en = str(assessment.get("reason_en") or titles[category][1])
    source_kind = "source-candidate" if category == "source" else str(assessment.get("fact_kind") or "synchronization-gap")
    occurrence = {"id": occurrence_id, "kind": source_kind, "role": "primary",
                  "scopeId": scope_id, "physicalTuId": assessment.get("physical_tu_id"),
                  "functionId": assessment.get("function_id"), "contextId": assessment.get("context_id"),
                  "threadInstanceId": assessment.get("thread_instance_id"), "location": deepcopy(location),
                  "status": chain["status"], "reasonCodes": deepcopy(chain["reasonCodes"]),
                  "provenance": deepcopy(provenance)}
    occurrences = [occurrence]
    for entry in locations[1:]:
        other = deepcopy(occurrence)
        other.update(id=_id("occurrence", {"finding": identifier, "entry": entry}),
                     role=entry["role"], location=deepcopy(entry["location"]),
                     physicalTuId=entry["physicalTuId"])
        occurrences.append(other)
    if locations:
        occurrence["physicalTuId"] = locations[0]["physicalTuId"]
    return finding_document(
        id=identifier, scopeId=scope_id,
        fact={"kind": source_kind, "symbol": symbol, "matchedText": str(assessment.get("matched_text") or reason),
              "primaryLocation": deepcopy(location), "provenance": deepcopy(provenance)},
        conclusion={"title": title, "title_en": title_en,
                    "severity": assessment.get("severity", "high") if category == "formal" else "info",
                    "confidence": None,
                    "evidenceLevel": "bounded-model" if category in {"formal", "discharged"} else
                                     "source-only" if category == "source" else "incomplete",
                    "findingType": finding_type, "verdict": verdict,
                    "actionable": category in {"formal", "source", "inconclusive"},
                    "blocking": category == "formal", "status": chain["status"],
                    "reason": reason, "reason_en": reason_en,
                    "suggestion": str(assessment.get("suggestion") or "检查证据链并修正内存序或同步"),
                    "suggestion_en": str(assessment.get("suggestion_en") or "Inspect the evidence chain and correct ordering or synchronization"),
                    "detail": str(assessment.get("detail") or reason),
                    "detail_en": str(assessment.get("detail_en") or reason_en),
                    "assumptions": sorted(set(assessment.get("assumptions", []))),
                    "limitations": sorted(set(assessment.get("limitations", [])))},
        occurrences=sorted(occurrences, key=lambda item: item["id"]), primaryOccurrenceId=occurrence_id, evidenceChain=chain)


def project_pipeline_assessment(scope_id, assessment, provenance, *, category,
                                layers, atomic=False, location=None, locations=()):
    """Build a typed chain only from explicitly available upstream layer references."""
    builder = EvidenceChainBuilder()
    location = locations[0]["location"] if locations else location
    path = []
    kinds = [
        ("thread-creation", "线程创建点", "Thread creation site", "thread_creation"),
        ("callback-binding", "回调绑定", "Callback binding", "callback"),
        ("execution-root", "执行根", "Execution root", "root"),
        ("call-path", "调用路径", "Call path", "call_path"),
        ("thread-instance", "线程实例", "Thread instance", "thread_instance"),
        ("mhp", "可能并行关系", "May-happen-in-parallel relation", "mhp"),
        ("memory-access", "内存访问", "Memory access", "access"),
        ("object-provenance", "对象来源", "Object provenance", "object"),
        ("byte-range-overlap", "字节范围重叠", "Byte-range overlap", "byte_range"),
    ]
    if atomic:
        kinds.extend([("atomic-event", "原子事件", "Atomic event", "atomic"),
                      ("reads-from", "读取来源", "Reads-from", "reads_from"),
                      ("modification-order", "修改顺序", "Modification order", "modification_order"),
                      ("release-sequence", "释放序列", "Release sequence", "release_sequence")])
    kinds.append(("synchronization-proof" if category == "discharged" else "synchronization-gap",
                  "同步证明" if category == "discharged" else "同步缺口",
                  "Synchronization proof" if category == "discharged" else "Synchronization gap", "synchronization"))
    for kind, title, title_en, layer in kinds:
        if layer not in layers:
            continue
        identifier = builder.step(kind, title, title_en, provenance, source=None,
                                  data={"layer": layer, "reference": deepcopy(layers[layer])})
        if path:
            relation = "ordered-by" if kind == "synchronization-proof" else "supports"
            builder.edge(path[-1], identifier, relation, provenance)
        path.append(identifier)
    for entry in locations:
        access = builder.step("memory-access", "关联源码访问", "Referenced source access", provenance,
                              source=entry["location"], data={"physicalTuId": entry["physicalTuId"],
                                                             "role": entry["role"]})
        if path:
            builder.edge(path[-1], access, "supports", provenance)
        path.append(access)
    conclusion = builder.step("conclusion", "分析结论", "Analysis conclusion", provenance,
                              source=location, data={"assessment": assessment.get("id")})
    if path:
        builder.edge(path[-1], conclusion, "supports", provenance)
    else:
        path.append(conclusion)
    path.append(conclusion) if path[-1] != conclusion else None
    required = {"root", "thread_instance", "mhp", "access", "object", "synchronization"}
    missing = sorted(required - set(layers))
    if category in {"source", "inconclusive"} or missing:
        builder.gap("evidence-layer-missing", "projection",
                    "证据链缺少必要分析层：" + ", ".join(missing or ["formal-proof"]),
                    "The evidence chain lacks required layers: " + ", ".join(missing or ["formal-proof"]),
                    "补充相关 AST/IR、线程、对象和同步证据",
                    "Provide the relevant AST/IR, thread, object, and synchronization evidence",
                    from_step=path[-2] if len(path) > 1 else path[0], expected_kind=missing[0] if missing else None)
    complete = category in {"formal", "discharged"} and not missing
    source_incomplete = locations == [] or (location is not None and location["context"]["status"] != "complete")
    if source_incomplete:
        builder.gap("source-location-unavailable", "source-context",
                    "源码位置或快照不完整，保留原始分析结论",
                    "Source location or snapshot is incomplete; the analysis verdict is preserved",
                    "补充匹配的源码位置和快照", "Provide matching source locations and snapshots",
                    from_step=conclusion, expected_kind="source-context")
    chain = builder.build(path[0], path, impacts=[conclusion],
                          force_status=("partial" if source_incomplete else "complete") if complete else "unknown")
    effective = category if complete or category in {"source", "inconclusive"} else "inconclusive"
    return project_assessment(scope_id, assessment, provenance, category=effective,
                              location=location, chain=chain, locations=locations,
                              finding_type="advanced-atomic-publication" if atomic else "single-publication")


def project_source_candidate(scope_id, candidate, provenance, *, location=None, locations=()):
    """Project AST evidence without promoting it to runtime ordering proof."""
    builder = EvidenceChainBuilder()
    location = locations[0]["location"] if locations else location
    source_step = builder.step(
        "source-fact", "源码语义候选", "Source semantic candidate", provenance,
        status="unknown", reason="仅验证了源码形状", reason_en="Only the source shape is verified",
        reason_codes=["source-evidence-only"], source=location,
        data={"shape": candidate.get("shape"), "nodes": candidate.get("node_ids", []),
              "relations": candidate.get("relation_ids", [])},
    )
    conclusion = builder.step(
        "conclusion", "源码候选结论", "Source candidate conclusion", provenance,
        status="unknown", reason="缺少运行时证明", reason_en="Runtime proof is missing",
        reason_codes=["source-evidence-only"], source=location,
        data={"candidate": candidate.get("id")},
    )
    builder.edge(source_step, conclusion, "supports-candidate", provenance, status="unknown",
                 reason_codes=["source-evidence-only"])
    missing = set(candidate.get("missing_evidence", []))
    if candidate.get("shape") != "atomic":
        missing -= {"reads-from", "modification-order", "release-sequence"}
    missing = sorted(missing) or ["runtime-evidence"]
    for reason in missing:
        builder.gap(
            f"missing-{reason}", "source-projection",
            f"源码候选缺少 {reason} 证据", f"The source candidate lacks {reason} evidence",
            "补充匹配的 BC、运行时对象、线程和同步证据",
            "Provide matching bitcode, runtime-object, thread, and synchronization evidence",
            from_step=source_step, expected_kind=reason,
        )
    if location is None or location["context"]["status"] != "complete":
        reason = (location or {"context": {"reasonCodes": ["source-location-unavailable"]}})["context"]["reasonCodes"]
        builder.gap(
            reason[0] if reason else "source-context-partial", "source-context",
            "分析时源码上下文不完整", "Analysis-time source context is incomplete",
            "提供与 source digest 匹配且位于源码边界内的快照",
            "Provide a source snapshot matching the digest and source boundary",
            from_step=source_step, expected_kind="source-context",
        )
    chain = builder.build(source_step, [source_step, conclusion], impacts=[conclusion],
                          force_status="unknown")
    shape = candidate.get("shape", "unknown")
    description = {"atomic": ("原子操作", "atomic operation"),
                   "pthread-create": ("线程创建", "thread creation"),
                   "pthread-join": ("线程等待", "thread join"),
                   "pthread-mutex": ("互斥同步", "mutex synchronization"),
                   "unknown-raii": ("RAII 锁生命周期", "RAII lock lifetime"),
                   "unknown-sync-wrapper": ("可能的同步封装", "possible synchronization wrapper"),
                   "memory-access": ("与并发构造关联的访问", "access related to a concurrency construct"),
                   "control": ("与并发构造关联的控制流", "control flow related to a concurrency construct")}
    label, label_en = description.get(shape, ("未识别源码形状", "unidentified source shape"))
    candidate = {**candidate, "title": f"{label}待核实", "title_en": f"Verify {label_en}",
                 "reason": f"源码包含{label}，尚未建立线程、对象与顺序证明",
                 "reason_en": f"Source contains {label_en}; thread, object and ordering evidence is incomplete",
                 "detail": f"该候选只有源码证据；需要补充：{', '.join(missing)}",
                 "detail_en": f"This candidate has source evidence only; missing: {', '.join(missing)}"}
    return project_assessment(scope_id, candidate, provenance, category="source",
                              location=location, chain=chain, locations=locations,
                              finding_type="source-only-memory-order-candidate")
