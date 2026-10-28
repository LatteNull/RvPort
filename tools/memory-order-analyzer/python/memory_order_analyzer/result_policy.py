"""统一结果的候选准入与诊断归并；不修改原始分析产物。"""

from copy import deepcopy

from .contracts import canonical
from .unified_contracts import diagnostic


SIGNAL_SHAPES = {"atomic", "pthread-create", "pthread-join", "pthread-mutex",
                 "unknown-raii", "unknown-sync-wrapper"}


def evidence_complete(documents):
    """已生成的文件仍可能仅包含 partial/unknown 证据。"""
    return bool(documents) and all(item.get("status") == "complete" and
                                   not item.get("frontier") for item in documents)


def stage_applicability(stage, records, source_facts):
    tokens = {"cpp-thread-lifecycle": ("thread", "async", "future", "promise"),
              "raii-synchronization": ("lock", "mutex", "synchron"),
              "advanced-atomic": ("atomic", "fence")}.get(stage)
    if tokens is None:
        return None
    relevant = records if stage == "advanced-atomic" else [item for item in records if item["language"] == "c++"]
    if not relevant:
        return False
    if any(item["record_id"] not in source_facts or
           source_facts[item["record_id"]].get("status") != "complete" for item in relevant):
        return None
    return any(any(token in canonical(source_facts[item["record_id"]]).lower() for token in tokens) for item in relevant)


def admit_candidates(candidates):
    """Only admit explicit concurrency shapes or directly related scoped accesses."""
    anchors = {}
    for item in candidates:
        if item.get("shape") in SIGNAL_SHAPES:
            key = (item.get("scope_id"), tuple(item.get("physical_tu_ids", [])), tuple(item.get("profile_ids", [])))
            anchors.setdefault(key, set()).update(item.get("node_ids", []))
    admitted, decisions, seen = [], [], set()
    for item in sorted(candidates, key=lambda value: value["id"]):
        key = (item.get("scope_id"), tuple(item.get("physical_tu_ids", [])), tuple(item.get("profile_ids", [])))
        reason = ("explicit-concurrency-shape" if item.get("shape") in SIGNAL_SHAPES else
                  "direct-concurrency-relation" if item.get("shape") in {"memory-access", "control"}
                  and set(item.get("node_ids", [])) & anchors.get(key, set()) else "no-concurrency-anchor")
        # SourceCandidate identity includes TU/profile, relation and node identities.
        identity = canonical({name: item.get(name) for name in (
            "scope_id", "physical_tu_ids", "profile_ids", "shape", "node_ids", "relation_ids")})
        accepted = reason != "no-concurrency-anchor"
        duplicate = accepted and identity in seen
        if accepted and not duplicate:
            admitted.append(item)
            seen.add(identity)
        decisions.append({"id": item["id"], "admitted": accepted and not duplicate,
                          "reason": "duplicate-identity" if duplicate else reason})
    return admitted, {"raw": len(candidates), "admitted": len(admitted),
                      "excluded": len(candidates) - len(admitted), "decisions": decisions}


def adapt_diagnostics(items, *, stage=None, scope_id=None):
    result = []
    for item in items:
        references = list(item.get("references", []))
        for key in ("record_id", "physical_tu_id", "artifact_key"):
            if item.get(key):
                references.append(str(item[key]))
        source = item.get("source") or {}
        if isinstance(source, dict):
            references.extend(str(source[key]) for key in ("physical_tu_id", "artifact_key") if source.get(key))
        result.append(diagnostic(
            item.get("code", "analysis-incomplete"), item.get("detail") or "分析证据不完整",
            item.get("detail_en") or "Analysis evidence is incomplete",
            suggestion=item.get("suggestion") or "检查所引用的输入和上游证据",
            suggestion_en=item.get("suggestion_en") or "Inspect the referenced inputs and upstream evidence",
            stage=item.get("stage") or stage, scope_id=item.get("scope_id") or scope_id,
            relevant=item.get("relevant", True), references=references))
    return result


def merge_diagnostics(items):
    """Merge the same root cause without collapsing distinct scope/TU identities."""
    result = {}
    for item in items:
        refs = sorted(ref for ref in item["references"] if not ref.startswith("stage:"))
        key = canonical([item["scope_id"], item["code"], refs, item["detail"], item["detail_en"]])
        if key not in result:
            result[key] = deepcopy(item)
        current = result[key]
        current["references"] = sorted(set(current["references"] + item["references"] +
                                           (["stage:" + item["stage"]] if item["stage"] else [])))
    return [result[key] for key in sorted(result)]


def bound_diagnostics(items, limit, reference):
    """预算内保留显式截断记录，完整明细由调用方写入审计制品。"""
    if len(items) <= limit:
        return items
    return items[:limit - 1] + [diagnostic(
        "diagnostic-budget-exhausted", f"诊断展示已截断，共 {len(items)} 条；请查看完整制品",
        f"Diagnostic display truncated from {len(items)} items; inspect the full artifact",
        stage="coordinator", references=[reference])]
