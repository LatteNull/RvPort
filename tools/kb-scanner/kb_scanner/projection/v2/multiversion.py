"""有界自包含版本描述，不为编译器生成的 clone 伪造源码。"""
from collections import defaultdict
from dataclasses import dataclass
import html

from ...core import SourceLocation, SourceSpan
from ...core.metadata import to_json_compatible
from ...analyzers.function_multiversion.analysis import CATALOG_KIND
from ...classifiers.risk import confirmed_dependency

NAMESPACE = "org.rvport.kb-scanner.function-multiversion"


@dataclass(frozen=True)
class ProjectionBudget:
    groups: int = 1000
    versions: int = 10000
    finding_groups: int = 4
    finding_versions: int = 64
    sources: int = 256

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in vars(self).values()):
            raise ValueError("multiversion projection budgets must be nonnegative integers")


class MultiversionProjection:
    def __init__(self, entities, observations=(), context=None, budget=None):
        catalogs = [e for e in entities if e.kind == CATALOG_KIND]
        if len(catalogs) > 1:
            raise ValueError("multiple function multiversion catalogs")
        self.catalog = to_json_compatible(catalogs[0].properties) if catalogs else None
        self.context, self.budget = context, budget or ProjectionBudget()
        self.by_evidence = defaultdict(list)
        self.confirmed = {o.metadata.get("factId") for o in observations if confirmed_dependency(o)}
        if self.catalog:
            for group in self.catalog["groups"]:
                ids = {*group["evidenceIds"], *(d["evidenceId"] for d in group["dependencies"]),
                       *(eid for d in group["declarations"] for eid in d["evidenceIds"])}
                for eid in ids:
                    self.by_evidence[eid].append(group)

    def report(self):
        return {NAMESPACE: self._view(self.catalog["groups"], self.budget.groups, self.budget.versions)} if self.catalog else {}

    def finding(self, evidence_ids):
        groups = {g["id"]: g for eid in evidence_ids for g in self.by_evidence.get(eid, ())}
        return {NAMESPACE: self._view(sorted(groups.values(), key=lambda g: g["id"]),
            self.budget.finding_groups, self.budget.finding_versions)} if groups else {}

    def _view(self, groups, group_limit, version_limit):
        rows, remaining, remaining_sources = [], version_limit, self.budget.sources
        omitted_versions, omitted_sources = 0, 0
        for group in groups[:group_limit]:
            versions = [{key: version[key] for key in ("option", "definition", "conditional", "bodySpan", "path")}
                        for version in group["versions"][:remaining]]
            remaining -= len(versions)
            omitted_versions += group["versionCount"] - len(versions)
            sources = []
            for description in group["sources"][:remaining_sources]:
                projected = dict(description)
                if self.context is not None:
                    span = SourceSpan(SourceLocation(description["path"], description["startLine"], description["startColumn"]),
                                      SourceLocation(description["path"], description["endLine"], description["endColumn"]))
                    projected["context"] = self.context.project(span).model_dump(mode="json")
                sources.append(projected)
            remaining_sources -= len(sources)
            omitted_sources += len(group["sources"]) - len(sources)
            # No unclosed fact/Evidence/proof IDs are exposed. Each reference is a real source description.
            dependencies = group["dependencies"][:remaining_sources]
            remaining_sources -= len(dependencies)
            omitted_sources += len(group["dependencies"]) - len(dependencies)
            semantics = group.get("semanticBindings", ())[:remaining_sources]
            remaining_sources -= len(semantics)
            omitted_sources += len(group.get("semanticBindings", ())) - len(semantics)
            bindings = []
            for binding in group["bindings"]:
                # Count each binding as well as each source against the same shared budget.
                if not remaining_sources:
                    omitted_sources += 1 + len(binding["sources"])
                    continue
                remaining_sources -= 1
                origins = binding["sources"][:remaining_sources]
                remaining_sources -= len(origins)
                omitted_sources += len(binding["sources"]) - len(origins)
                bindings.append({key: binding[key] for key in ("configuration", "selectionStatus", "scope", "runtimeVersionSelection")}
                    | {"sources": list(origins), "sourceStatus": "complete" if len(origins) == len(binding["sources"]) else "partial"})
            row = {key: group[key] for key in ("id", "path", "signature", "configuration", "mechanism", "groupCompleteness",
                "defaultPresence", "defaultDefinition", "semanticRule", "targetApplicability", "targetSelection", "reasonCodes")}
            row.update(versions=versions, versionCount=group["versionCount"], sources=sources,
                semanticBindings=[{k:v for k,v in hint.items() if k != "canonicalKey"} for hint in semantics],
                selectionBindings=bindings,
                dependencies=[{"source": dep["source"], "status": "confirmed_x86" if dep["factId"] in self.confirmed else "unknown"} for dep in dependencies],
                bodyDependency="confirmed_x86" if any(d["factId"] in self.confirmed for d in group["dependencies"]) else "unknown",
                title="函数版本与 default 实现", title_en="Function versions and default implementation")
            rows.append(row)
        clipped = len(groups) > len(rows) or omitted_versions or omitted_sources
        return {"version": 1, "groups": rows, "groupCount": len(groups), "observedGroupCount": self.catalog["groupCount"],
                "discoveryStatus": self.catalog["discoveryStatus"], "discoveryReasonCodes": self.catalog["reasonCodes"],
                "projectionStatus": "partial" if clipped else "complete", "omittedGroups": len(groups)-len(rows),
                "omittedVersions": omitted_versions, "omittedSources": omitted_sources,
                "explanation": "default 仅表示源工具链的基线版本，不能证明 RISC-V 可用；自动 clone 共用真实源码位置。",
                "explanation_en": "Default denotes the source toolchain baseline, not RISC-V suitability; generated clones share real source locations."}


def render_multiversion_summary(extensions):
    catalog = (extensions or {}).get(NAMESPACE)
    if not catalog:
        return ""
    rows = "".join("<li>" + html.escape(g["signature"]) + " · default：" + html.escape(g["defaultPresence"])
                   + " · 定义：" + html.escape(g["defaultDefinition"]) + "</li>" for g in catalog["groups"])
    return "<section><h2>函数多版本</h2><p>" + html.escape(catalog["explanation"]) + "</p><ul>" + rows + "</ul></section>"
