"""Pure construction logic for degraded source evidence and conservative P4 adaptation."""

from collections import defaultdict, deque
from copy import deepcopy

from .contracts import AnalysisError, canonical, identity
from .degraded_contracts import degraded_document, dependency, diagnostic, stage_counts


_FATAL_SOURCE_CODES = {
    "clang-replay-failed", "source-member-failed", "source-worker-failed",
    "source-request-invalid", "profile-conflict", "fatal-include", "error-recovery-node",
}
_SYNC_DIAGNOSTICS = {
    "mutex-kind-unknown": "mutex-kind-unknown",
    "mutex-state-unknown": "unbalanced-or-conditional-lock",
    "thread-graph-budget": "synchronization-budget",
    "thread-local-budget": "synchronization-budget",
    "order-budget": "synchronization-budget",
}
_SHAPES = {
    "pthread_create": "pthread-create", "pthread_join": "pthread-join",
    "pthread_mutex_lock": "pthread-mutex", "pthread_mutex_unlock": "pthread-mutex",
    "atomic": "atomic", "read": "memory-access", "write": "memory-access",
    "control": "control",
}


def source_facts_usable(facts):
    """Partial facts are usable only when partiality is a non-fatal explicit budget cut."""
    if facts is None or facts.get("status") == "failed":
        return False
    codes = {item.get("code") for item in [*facts.get("diagnostics", []), *facts.get("frontier", [])]}
    if codes & _FATAL_SOURCE_CODES:
        return False
    return not any("fatal" in str(code) or "recovery" in str(code) for code in codes)


def evidence_mode(source_facts, ir_available):
    source_available = source_facts_usable(source_facts)
    if source_available and ir_available:
        return "ast-ir"
    if ir_available:
        return "ir-only"
    if source_available:
        return "ast-only"
    return "failed"


def request_mode(modes):
    values = set(modes)
    return next(iter(values)) if len(values) == 1 else "mixed"


def build_availability(scope_id, source_request, source_facts, ir_facts, module_refs, failures):
    profile = source_request["profile"]
    physical = source_request["physical_tu_id"]
    ir_available = bool(ir_facts or module_refs)
    mode = evidence_mode(source_facts, ir_available)
    by_stage = defaultdict(list)
    for item in failures:
        by_stage[item["stage"]].append(item)
    source_dep = dependency("SourceSemanticFacts", physical, source_facts) if source_facts is not None else None
    ir_dep = None
    if ir_facts:
        first = sorted(ir_facts, key=lambda item: item["artifact_key"])[0]
        ir_dep = dependency("LLVMSourceBindingFacts", first["artifact_key"], first)
    module_dep = module_refs[0] if len(module_refs) == 1 else None
    stages = (("source", source_dep), ("bc", ir_dep), ("p1", module_dep),
              ("p2", None), ("p3", None), ("p4", None))
    products = []
    for stage, reference in stages:
        failed = sorted(item["id"] for item in by_stage.get(stage, ()))
        status = "complete" if reference else "failed" if failed else "not-run"
        products.append({"stage": stage, "status": status, "dependency": reference,
                         "failure_ids": failed})
    products.sort(key=lambda item: item["stage"])
    deps = sorted([item for item in [source_dep, ir_dep, *module_refs] if item is not None],
                  key=lambda item: (item["kind"], item["id"]))
    status = "failed" if mode == "failed" else "complete" if mode == "ast-ir" and not failures else "partial"
    return degraded_document(
        "TUEvidenceAvailability", scope_id=scope_id, physical_tu_id=physical,
        profile_id=profile["profile_id"], language=profile["language"], standard=profile["standard"],
        mode=mode, products=products, failures=sorted(failures, key=lambda item: item["id"]),
        dependencies=deps, status=status, semantic_digest=None)


def _node_name(node):
    return " ".join(str(node.get(key) or "") for key in ("name", "qualified_name", "canonical_type")).lower()


def _relation_shape(relation, nodes, language):
    if relation["kind"] in _SHAPES:
        return _SHAPES[relation["kind"]]
    if relation["kind"] != "call":
        return None
    target = nodes.get(relation.get("to"))
    name = _node_name(target or {})
    if language == "c++" and any(token in name for token in ("lock_guard", "unique_lock", "scoped_lock")):
        return "unknown-raii"
    if any(token in name for token in ("lock", "unlock", "mutex", "synchron")):
        return "unknown-sync-wrapper"
    return None


def generate_source_candidates(scope_id, facts, availability, *, limit):
    if not source_facts_usable(facts):
        return [], False
    nodes = {item["id"]: item for item in facts["nodes"]}
    results, cut = [], False
    fact_ref = dependency("SourceSemanticFacts", facts["physical_tu_id"], facts)
    availability_ref = dependency("TUEvidenceAvailability", availability["physical_tu_id"], availability)
    def append_candidate(shape, node_ids, relation_ids, *, callback_unknown=False, object_unknown=False):
        missing = {"memory-effect", "execution-order", "byte-range", "thread-instance",
                   "reads-from", "synchronizes-with", "happens-before"}
        if availability["mode"] == "ast-only":
            missing.add("ir-binding")
        if callback_unknown:
            missing.add("callback-target")
        if object_unknown:
            missing.add("object-identity")
        if shape in {"unknown-raii", "unknown-sync-wrapper"}:
            missing.add("synchronization-model")
        seed = {"scope_id": scope_id, "physical_tu_id": facts["physical_tu_id"],
                "profile_id": facts["profile_id"], "shape": shape,
                "nodes": sorted(node_ids), "relations": sorted(relation_ids)}
        results.append(degraded_document(
            "SourceCandidate", scope_id=scope_id, id=identity(seed),
            physical_tu_ids=[facts["physical_tu_id"]], profile_ids=[facts["profile_id"]],
            language=availability["language"], standard=availability["standard"], shape=shape,
            node_ids=sorted(node_ids), relation_ids=sorted(relation_ids), evidence_level="source-only",
            verdict="unknown", safety="not-established", mode=availability["mode"],
            assumptions=sorted(["source-shape-only", "not-a-memory-model-proof"]),
            missing_evidence=sorted(missing), dependencies=sorted([availability_ref, fact_ref], key=lambda item: (item["kind"], item["id"])),
            diagnostics=[diagnostic("source-candidate-only", "该记录仅是源码候选，不能建立正式内存序结论",
                                    "This record is a source candidate only and cannot establish a formal memory-order conclusion",
                                    suggestion="补齐匹配 profile 的 IR、线程和顺序证据",
                                    suggestion_en="Provide matching-profile IR, thread, and order evidence")],
            suggestion="补齐 IR 与跨层证明链后重新评估", suggestion_en="Re-evaluate after completing the IR and cross-layer proof chain",
            semantic_digest=None))
    for relation in facts["relations"]:
        shape = _relation_shape(relation, nodes, availability["language"])
        if shape is None:
            continue
        if len(results) >= limit:
            cut = True
            break
        node_ids = sorted({item for item in (relation.get("from"), relation.get("to")) if item})
        append_candidate(
            shape, node_ids, [relation["id"]],
            callback_unknown=shape == "pthread-create" and (relation.get("status") != "exact" or relation.get("to") is None),
            object_unknown=shape in {"pthread-mutex", "memory-access", "atomic"} and relation.get("to") is None)
    if not cut and availability["language"] == "c++":
        represented = {node_id for item in results if item["shape"] == "unknown-raii" for node_id in item["node_ids"]}
        for node_id, node in sorted(nodes.items()):
            if node_id in represented or not any(token in _node_name(node) for token in ("lock_guard", "unique_lock", "scoped_lock")):
                continue
            if len(results) >= limit:
                cut = True
                break
            append_candidate("unknown-raii", [node_id], [])
    return sorted(results, key=lambda item: item["id"]), cut


def _gap(scope_id, reason, stage, tus, node_ids=(), relation_ids=(), objects=(), threads=(),
         paths=(), budget=None, dependencies=()):
    prose = {
        "mutex-kind-unknown": ("mutex 类型或初始化语义未知", "The mutex kind or initialization semantics are unknown"),
        "unmodeled-raii-lifetime": ("RAII 锁生命周期尚未建模", "The RAII lock lifetime is not modeled"),
        "unknown-synchronization-wrapper": ("同步 wrapper 的锁语义未知", "The synchronization wrapper semantics are unknown"),
        "unresolved-lock-object": ("锁对象无法精确解析", "The lock object cannot be resolved exactly"),
        "unbalanced-or-conditional-lock": ("锁定与解锁路径不平衡或带条件", "Lock and unlock paths are unbalanced or conditional"),
        "synchronization-budget": ("同步分析因预算丢失证据", "Synchronization evidence was lost to an analysis budget"),
    }
    detail, detail_en = prose[reason]
    seed = {"scope_id": scope_id, "reason": reason, "stage": stage, "tus": sorted(set(tus)),
            "nodes": sorted(set(node_ids)), "relations": sorted(set(relation_ids)),
            "objects": sorted(set(objects)), "threads": sorted(set(threads)), "paths": sorted(set(paths)),
            "budget": budget, "dependencies": sorted(dependencies, key=lambda item: (item["kind"], item["id"]))}
    return degraded_document(
        "SynchronizationGap", scope_id=scope_id, id=identity(seed), reason=reason, stage=stage,
        physical_tu_ids=seed["tus"], node_ids=seed["nodes"], relation_ids=seed["relations"],
        object_candidates=seed["objects"], thread_candidates=seed["threads"], path_candidates=seed["paths"],
        budget=budget, dependencies=seed["dependencies"], detail=detail, detail_en=detail_en,
        suggestion="保留为 unknown，直到同步对象、生命周期和路径证据完整",
        suggestion_en="Keep the candidate unknown until object, lifetime, and path evidence is complete",
        semantic_digest=None)


def build_synchronization_gaps(scope_id, candidates, thread_graph, artifact_to_tu):
    gaps = []
    for candidate in candidates:
        if candidate["shape"] not in {"unknown-raii", "unknown-sync-wrapper"}:
            continue
        reason = "unmodeled-raii-lifetime" if candidate["shape"] == "unknown-raii" else "unknown-synchronization-wrapper"
        gaps.append(_gap(scope_id, reason, "source", candidate["physical_tu_ids"],
                         candidate["node_ids"], candidate["relation_ids"],
                         dependencies=candidate["dependencies"]))
    if thread_graph is not None:
        graph_ref = dependency("ThreadContextGraph", identity(thread_graph), thread_graph)
        for item in [*thread_graph.get("diagnostics", []), *thread_graph.get("frontier", [])]:
            reason = _SYNC_DIAGNOSTICS.get(item.get("code"))
            if reason is None:
                continue
            source = item.get("source") or {}
            artifact = source.get("artifact_key") if isinstance(source, dict) else None
            tus = [artifact_to_tu[artifact]] if artifact in artifact_to_tu else []
            threads = [item["instance"]] if item.get("instance") else []
            paths = [canonical(source)] if source else []
            gaps.append(_gap(scope_id, reason, "p3", tus, threads=threads, paths=paths,
                             budget={"diagnostic": item["code"]} if reason == "synchronization-budget" else None,
                             dependencies=[graph_ref]))
    unique = {item["id"]: item for item in gaps}
    return sorted(unique.values(), key=lambda item: item["id"])


def bounded_slice(starts, edges, limit):
    queue, visited, cut = deque(sorted(set(starts))), set(), False
    while queue:
        item = queue.popleft()
        if item in visited:
            continue
        if len(visited) >= limit:
            cut = True
            break
        visited.add(item)
        queue.extend(sorted(set(edges.get(item, ())) - visited))
    return {"roots": sorted(set(starts)), "items": sorted(visited), "status": "partial" if cut else "complete",
            "missing": ["slice-budget"] if cut else []}


def _assessment_tus(assessment, artifact_to_tu):
    artifacts = set()
    for source in assessment.get("evidence", []):
        if isinstance(source, dict) and source.get("artifact_key"):
            artifacts.add(source["artifact_key"])
    return sorted({artifact_to_tu[item] for item in artifacts if item in artifact_to_tu})


def adapt_formal_assessments(assessments, availabilities, gaps, artifact_to_tu, *, slice_limit,
                             lifecycle_gaps=()):
    """Apply A2 and additive A3 gaps only when they intersect a candidate slice.

    ``lifecycle_gaps`` is optional so the A2 protocol and every pre-A3 caller keep
    their original behavior.  A3 callers pass gap records from the independent
    lifecycle graph; their TU/object/thread/path identities participate in the
    same conservative slice instead of being interpreted as absent threads.
    """
    modes = {item["physical_tu_id"]: item["mode"] for item in availabilities}
    any_degraded = any(mode in {"ast-only", "failed"} for mode in modes.values())
    results = []
    for item in assessments:
        tus = _assessment_tus(item, artifact_to_tu)
        relevant_gaps = [gap for gap in gaps if not gap["physical_tu_ids"] or not tus or set(gap["physical_tu_ids"]) & set(tus)]
        relevant_lifecycle = [gap for gap in lifecycle_gaps
                              if not gap.get("physical_tu_ids") or not tus
                              or set(gap["physical_tu_ids"]) & set(tus)]
        degraded_tus = [tu for tu in tus if modes.get(tu) in {"ast-only", "failed"}]
        conservative_unmapped = not tus and (any_degraded or bool(gaps))
        reasons = []
        if degraded_tus:
            reasons.append("candidate-depends-on-degraded-tu")
        if relevant_gaps:
            reasons.append("candidate-relevant-synchronization-gap")
        if relevant_lifecycle:
            reasons.append("candidate-relevant-cpp-thread-lifecycle-gap")
        if conservative_unmapped:
            reasons.append("candidate-dependency-unresolved")
        effective = "unknown" if reasons and item.get("status") in {"finding", "discharged"} else item.get("status", "unknown")
        gap_ids = sorted(gap["id"] for gap in [*relevant_gaps, *relevant_lifecycle])
        edges = {f"assessment:{item['id']}": [*(f"tu:{tu}" for tu in tus), *(f"gap:{gap}" for gap in gap_ids)]}
        proof_slice = bounded_slice([f"assessment:{item['id']}"], edges, slice_limit)
        seed = {"original_id": item["id"], "effective_status": effective,
                "reasons": reasons, "tus": tus, "gaps": gap_ids, "slice": proof_slice}
        results.append({
            "id": identity(seed), "original_id": item["id"], "original_kind": item.get("kind", "unknown"),
            "original_status": item.get("status", "unknown"), "effective_status": effective,
            "reason_codes": sorted(reasons), "physical_tu_ids": tus, "gap_ids": gap_ids,
            "slice": proof_slice,
            "detail": "候选因相关降级证据转为 unknown" if effective == "unknown" and reasons else item.get("detail", "保留原正式评估"),
            "detail_en": "The candidate is unknown because relevant evidence is degraded" if effective == "unknown" and reasons else item.get("detail_en", "The original formal assessment is preserved"),
            "suggestion": "补齐候选依赖切片中的 IR 或同步证据" if reasons else "复核原正式评估的适用边界",
            "suggestion_en": "Complete IR or synchronization evidence in the candidate dependency slice" if reasons else "Review the applicability boundary of the original formal assessment",
        })
    return sorted(results, key=lambda item: item["id"])


def build_report(scope_id, request, availabilities, candidates, gaps, formal, failures,
                 stage_values, dependencies, *, cache_hits=0, cache_misses=0):
    mode_counts = {name: sum(item["mode"] == name for item in availabilities) for name in ("ast-ir", "ir-only", "ast-only", "failed")}
    mode = request_mode([item["mode"] for item in availabilities]) if availabilities else "failed"
    usable = any(item["mode"] != "failed" for item in availabilities)
    incomplete = (not usable or mode in {"mixed", "ast-only", "failed"} or bool(candidates) or bool(gaps) or
                  bool(failures) or any(item["effective_status"] in {"unknown", "unsupported"} for item in formal))
    status = "failed" if not usable else "partial" if incomplete else "complete"
    finding = any(item["effective_status"] == "finding" for item in formal)
    exit_code = 1 if status == "failed" else 2 if status == "partial" else 3 if finding else 0
    diagnostics = [diagnostic(
        item["code"], item["detail"], item["detail_en"], suggestion=item["suggestion"],
        suggestion_en=item["suggestion_en"], source={"physical_tu_id": item["physical_tu_id"], "stage": item["stage"]})
        for item in failures]
    diagnostics.extend(diagnostic(
        "synchronization-gap", gap["detail"], gap["detail_en"], suggestion=gap["suggestion"],
        suggestion_en=gap["suggestion_en"], source={"gap_id": gap["id"]}) for gap in gaps)
    return degraded_document(
        "DegradedSourceAnalysisReport", scope_id=scope_id, request_hash=identity(request),
        status=status, mode=mode, exit_code=exit_code, safety="not-established",
        stages=stage_values, mode_counts=mode_counts,
        availabilities=sorted((dependency("TUEvidenceAvailability", item["physical_tu_id"], item) for item in availabilities), key=lambda item: (item["kind"], item["id"])),
        source_candidates=sorted((dependency("SourceCandidate", item["id"], item) for item in candidates), key=lambda item: (item["kind"], item["id"])),
        synchronization_gaps=sorted((dependency("SynchronizationGap", item["id"], item) for item in gaps), key=lambda item: (item["kind"], item["id"])),
        formal_assessments=formal,
        dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
        diagnostics=diagnostics, frontier=deepcopy(diagnostics), cache={"hits": cache_hits, "misses": cache_misses},
        semantic_digest=None)
