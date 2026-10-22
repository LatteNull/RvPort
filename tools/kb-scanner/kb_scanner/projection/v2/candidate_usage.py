"""用途审计的有界、自包含视图；不把抽象语义角色伪装为源码。"""
from dataclasses import dataclass
import html

from ...analyzers.candidate_usage.analysis import CATALOG_KIND
from ...analyzers.candidate_usage.proofs import NAMESPACE
from ...classifiers.semantic_admission import SemanticAdmissionIndex
from ...core import AnalysisSnapshot
from ...core.metadata import to_json_compatible


@dataclass(frozen=True)
class ProjectionBudget:
    excluded: int = 100
    sources: int = 64
    roots: int = 64

    def __post_init__(self):
        if any(type(value) is not int or value < 0 for value in vars(self).values()):
            raise ValueError("usage projection budgets must be nonnegative integers")
        if self.excluded > 100 or self.sources > 64 or self.roots > 64:
            raise ValueError("usage projection budgets exceed hard limits")


def _key(value):
    return (value.get("factId"), value.get("subjectId"), value.get("configuration", "default"),
            tuple(sorted(value.get("matchedEvidenceIds", ()))))


class CandidateUsageProjection:
    def __init__(self, index, context, budget=None):
        self.index, self.context = index, context
        self._source_views, self._line_views = {}, {}
        self.budget = budget or ProjectionBudget()
        catalogs = [entity for entity in index.entities.values() if entity.kind == CATALOG_KIND]
        if len(catalogs) > 1:
            raise ValueError("multiple candidate usage catalogs")
        self.catalog = catalogs[0].properties if catalogs else None
        self.entries = {}
        for entry in self.catalog.get("entries", ()) if self.catalog else ():
            key = _key(entry)
            if key in self.entries:
                raise ValueError("duplicate candidate usage root")
            self.entries[key] = entry
        self.decisions = {}
        self.gate, self.classified = None, set()
        if self.catalog is not None:
            self.gate = SemanticAdmissionIndex(AnalysisSnapshot(tuple(index.relations.values()),
                tuple(index.entities.values()), tuple(index.proofs.values())))
            self.classified = {oid for classification in index.classifications.values() for oid in classification.observation_ids}

    def _decision(self, observation):
        if observation.id not in self.decisions:
            self.decisions[observation.id] = self.gate.decide(observation)
        return self.decisions[observation.id]

    def _sources(self, entry, limit):
        # 所有原始 occurrence 优先，其次为具体 usage record；不引用整函数冒充每个使用。
        roots = [self.index.evidence.get(eid) for eid in entry["matchedEvidenceIds"]]
        records = [self.index.entities.get(rid) for rid in entry.get("recordIds", ())]
        values, seen, missing = [], set(), 0
        for item in (*roots, *records):
            location = getattr(item, "location", None)
            if location is None:
                missing += 1
                continue
            key = (location.start.path, location.start.line, location.start.column,
                   location.end.line, location.end.column)
            if key in seen:
                continue
            seen.add(key)
            values.append(location)
        return ({"sourceCount": len(values), "omittedSources": max(0, len(values)-limit),
                 "missingSources": missing,
                 "sources": [self._source_view(span) for span in values[:limit]]})

    def _source_view(self, span):
        # 投影期间只读共享；避免每个根重复复制同一源码窗口的 JSON 字典。
        if span not in self._source_views:
            source = self.context.project(span)
            view = source.model_dump(mode="json", exclude_none=True, exclude={"context"})
            context = source.context.model_dump(mode="json", exclude_none=True, exclude={"lines"})
            lines = []
            for line in source.context.lines:
                key = source.file, line.line, line.text
                if key not in self._line_views:
                    self._line_views[key] = line.model_dump(mode="json", exclude_none=True)
                lines.append(self._line_views[key])
            view["context"] = {**context, "lines": lines}
            self._source_views[span] = view
        return self._source_views[span]

    def _view(self, observation, entry, source_limit):
        decision = self._decision(observation)
        excluded = observation.id not in self.classified and decision.status == "excluded"
        reasons = set(entry.get("reasonCodes", ()))
        if not excluded:
            reasons.add(decision.reason)
        root_fact = self.index.facts.get(entry["factId"])
        sources = self._sources(entry, source_limit)
        return {"symbol": root_fact.canonical_value if root_fact else "",
                "configuration": entry["configuration"], "rootCount": len(entry["matchedEvidenceIds"]),
                "status": "excluded" if excluded else "unknown", "producerStatus": entry["status"],
                "reasonCodes": sorted(reasons), "reason": decision.reason,
                "explanation": "完整局部用途证明已通过准入；仅省略迁移分类，原始事实保留。" if excluded else "用途证据尚不足以排除迁移候选；保留原结论及待补证据。",
                "explanation_en": "A complete local usage proof passed admission; only migration classification is omitted, while facts are retained." if excluded else "Usage evidence cannot exclude this migration candidate; the original conclusion and unresolved evidence are retained.",
                "statistics": {key: entry.get(key, 0) for key in ("expectedUseCount", "resolvedUseCount", "unresolvedCount", "conflictCount", "escapeCount")},
                "analysisTruncated": bool(entry.get("truncated")),
                "analysisBudget": to_json_compatible(entry.get("budget", {})),
                "projectionStatus": "partial" if sources["omittedSources"] or sources["missingSources"] else "complete",
                **sources}

    def finding(self, observations):
        pairs = [(obs, self.entries[_key(obs.metadata)]) for obs in sorted(observations, key=lambda item: item.id)
                 if _key(obs.metadata) in self.entries]
        if not pairs:
            return {}
        roots, remaining = [], self.budget.sources
        for obs, entry in pairs[:self.budget.roots]:
            root = self._view(obs, entry, remaining)
            roots.append(root)
            remaining -= len(root["sources"])
        return {NAMESPACE: {"version": 1, "rootCount": len(pairs),
            "omittedRoots": max(0, len(pairs)-self.budget.roots),
            "roots": roots}}

    def report(self):
        if self.catalog is None:
            return {}
        excluded = [(obs, self.entries[_key(obs.metadata)]) for obs in sorted(self.index.observations.values(), key=lambda item: item.id)
                    if _key(obs.metadata) in self.entries and obs.id not in self.classified
                    and self._decision(obs).status == "excluded"]
        return {NAMESPACE: {"version": 1, "excludedCount": len(excluded),
            "omittedExcludedCandidates": max(0, len(excluded)-self.budget.excluded),
            "excludedCandidates": [self._view(obs, entry, self.budget.sources) for obs, entry in excluded[:self.budget.excluded]],
            "statistics": {key: self.catalog[key] for key in ("rootCount", "scopeIndexes", "recordCount", "visits", "cacheHits")},
            "explanation": "排除仅针对已证明的局部非执行用途，不证明替代实现或项目已可迁移。",
            "explanation_en": "Exclusions concern proven local non-execution usage only, not alternative implementations or project readiness."}}


def render_usage_summary(extensions):
    view = (extensions or {}).get(NAMESPACE)
    if not view:
        return ""
    escape = lambda value: html.escape(str(value), quote=True)
    records = view.get("roots", view.get("excludedCandidates", ()))
    items, source_html = [], {}
    for record in records:
        sources = []
        for source in record["sources"]:
            identity = id(source)
            if identity in source_html:
                sources.append(source_html[identity])
                continue
            context = source["context"]
            highlighted = {item["line"] for item in context["highlights"]}
            lines = []
            for line in context["lines"]:
                text = f"{line['line']}: {escape(line['text'])}"
                lines.append(f"<mark>{text}</mark>" if line["line"] in highlighted else text)
            rendered = f"<details><summary>{escape(source['file'])}:{source['span']['start']['line']}</summary><pre>{chr(10).join(lines)}</pre></details>"
            source_html[identity] = rendered
            sources.append(rendered)
        items.append(f"<li>{escape(record['symbol'])} · {escape(record['configuration'])}<p>{escape(record['explanation'])}</p>"
                     f"<p>{escape(', '.join(record['reasonCodes']))}</p><p>来源总数 {record['sourceCount']}；省略 {record['omittedSources']}；缺失 {record['missingSources']}</p>{''.join(sources)}</li>")
    counts = (f"排除总数 {view['excludedCount']}；省略 {view['omittedExcludedCandidates']}"
              if "excludedCount" in view else f"候选根 {view['rootCount']}；省略 {view['omittedRoots']}")
    return f"<section><h3>候选用途审计</h3><p>{escape(view.get('explanation', ''))}</p><p>{counts}</p><ul>{''.join(items)}</ul></section>"
