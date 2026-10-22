"""Bounded, self-contained path descriptions without fake code locations."""
from collections import defaultdict
from dataclasses import dataclass
import html

from ...core.metadata import to_json_compatible
from ...analyzers.architecture_family.analyzer import CATALOG_KIND

NAMESPACE = "org.rvport.kb-scanner.architecture-family"


@dataclass(frozen=True)
class ProjectionBudget:
    families: int = 1000
    members: int = 10000
    finding_families: int = 8
    finding_members: int = 128
    bindings: int = 32
    sources: int = 64

    def __post_init__(self):
        if any(v < 0 for v in vars(self).values()):
            raise ValueError("family projection budgets must be nonnegative")


class FamilyProjection:
    def __init__(self, entities, budget=None):
        self.budget = budget or ProjectionBudget()
        catalogs = [e for e in entities if e.kind == CATALOG_KIND]
        if len(catalogs) > 1:
            raise ValueError("multiple architecture family catalogs")
        self.catalog = to_json_compatible(catalogs[0].properties) if catalogs else None
        self.by_file = defaultdict(list)
        if self.catalog:
            for family in self.catalog["families"]:
                for member in family["members"]:
                    self.by_file[member["fileId"]].append(family)

    def report(self):
        if self.catalog is None:
            return None
        return {NAMESPACE: self._view(self.catalog["families"], self.budget.families, self.budget.members)}

    def finding(self, file_ids):
        found = {f["id"]: f for fid in file_ids for f in self.by_file.get(fid, ())}
        if not found:
            return {}
        return {NAMESPACE: self._view(sorted(found.values(), key=lambda f: f["id"]),
                                     self.budget.finding_families, self.budget.finding_members)}

    def _view(self, families, family_limit, member_limit):
        selected, remaining, omitted_bindings, omitted_sources = [], member_limit, 0, 0
        for family in families[:family_limit]:
            projected = []
            for member in family["members"][:remaining]:
                bindings = []
                omitted_bindings += max(0, len(member["bindings"]) - self.budget.bindings)
                for binding in member["bindings"][:self.budget.bindings]:
                    # Plain source descriptions are independently verifiable. Internal
                    # proof/relation IDs are not serialized as dangling typed refs.
                    omitted_sources += max(0, len(binding["sources"]) - self.budget.sources)
                    bindings.append({key: binding[key] for key in ("configuration", "selectionStatus", "proofStatus", "kind")}
                                    | {"sources": binding["sources"][:self.budget.sources]})
                projected.append({key: member[key] for key in ("path", "roleHint", "candidateStatus", "token", "rule", "observation")}
                                 | {"bindings": bindings})
            remaining -= len(projected)
            selected.append({key: family[key] for key in ("id", "template", "status", "memberCount", "alternativeStatus", "candidateAbsence", "reasonCodes")}
                            | {"members": projected, "omittedMembers": family["memberCount"] - len(projected)})
        omitted_families = len(families) - len(selected)
        clipped = omitted_families or omitted_bindings or omitted_sources or any(f["omittedMembers"] for f in selected)
        return {"version": self.catalog["version"], "scope": self.catalog["scope"],
                "discoveryStatus": self.catalog["discoveryStatus"], "discoveryReasonCodes": self.catalog["reasonCodes"],
                "pathCount": self.catalog["pathCount"], "pathsProcessed": self.catalog["pathsProcessed"],
                "observedFamilyCount": self.catalog["familyCount"], "familyCount": len(families),
                "families": selected, "projectionStatus": "partial" if clipped else "complete",
                "omittedFamilies": omitted_families, "omittedBindings": omitted_bindings, "omittedSources": omitted_sources,
                "reasonCodes": ["family-output-budget"] if clipped else [],
                "explanation": "文件命名仅提示候选实现；不能证明行为等价、目标选中或缺少通用实现。",
                "explanation_en": "File names only suggest candidate implementations; they do not prove equivalence, target selection, or absence of portable code."}


def render_family_summary(extensions):
    catalog = (extensions or {}).get(NAMESPACE)
    if not catalog:
        return ""
    rows = []
    for family in catalog["families"]:
        members = "".join(f"<li>{html.escape(m['path'], quote=True)} · {html.escape(m['roleHint'])} · 待核查</li>" for m in family["members"])
        rows.append(f"<li>{html.escape(family['template'], quote=True)}<ul>{members}</ul></li>")
    return ("<section><h2>架构实现候选家族</h2><p>" + html.escape(catalog["explanation"])
            + f"</p><p>发现状态：{html.escape(catalog['discoveryStatus'])}；展示状态：{html.escape(catalog['projectionStatus'])}</p><ul>"
            + "".join(rows) + "</ul></section>")
