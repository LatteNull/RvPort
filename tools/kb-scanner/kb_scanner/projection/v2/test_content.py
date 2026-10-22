"""测试语境在现有可选 namespace 内展示；保留真实位置与双语说明。"""
from collections import defaultdict
from html import escape

from ...core.metadata import to_json_compatible


NAMESPACE = "org.rvport.kb-scanner.test-content"


class TestContentProjection:
    def __init__(self, index, source_context):
        self.evidence = index.evidence
        self.context = source_context
        self.entries = defaultdict(list)
        self.truncated = False
        for entity in index.entities.values():
            if entity.kind == "test_content_catalog":
                self.truncated |= bool(entity.properties["truncated"])
                for entry in entity.properties["entries"]:
                    self.entries[entry["evidenceId"]].append(entry)

    def finding(self, evidence_ids, *, limit=16, source_limit=64):
        if min(limit, source_limit) < 1:
            raise ValueError("test projection budgets must be positive")
        entries = [entry for eid in sorted(evidence_ids) for entry in self.entries.get(eid, ())]
        if not entries:
            return {}
        sources, uses, omitted = {}, [], self.truncated or len(entries) > limit
        for entry in entries[:limit]:
            ids = []
            for eid in entry["sourceEvidenceIds"]:
                item = self.evidence.get(eid)
                if item is None or item.location is None:
                    omitted = True
                    continue
                if eid not in sources:
                    if len(sources) >= source_limit:
                        omitted = True
                        continue
                    source = self.context.project(item.location)
                    sources[eid] = {"id": eid, "symbol": str(item.value),
                                    "source": source.model_dump(mode="json", exclude_none=True)}
                ids.append(eid)
            content = {key: value for key, value in entry["content"].items()
                       if key not in {"functionEvidenceId", "entryEvidenceId"}}
            assertion = entry["assertion"]
            if assertion:
                assertion = {key: value for key, value in assertion.items() if key != "evidenceIds"}
                assertion["observedConfigurations"] = [
                    {key: value for key, value in profile.items() if key != "evidenceId"}
                    for profile in assertion.get("observedConfigurations", ())]
            uses.append({"testName": entry["testName"], "configuration": entry["configuration"],
                "role": entry["role"], "buildStatus": entry["buildStatus"],
                "registrationStatus": entry["registrationStatus"], "proofStatus": entry["proofStatus"],
                "content": to_json_compatible(content), "assertion": to_json_compatible(assertion),
                "reasonCodes": entry["reasonCodes"], "sourceIds": tuple(dict.fromkeys(ids)),
                "description": "这是原始测试内容的静态关联；编译、注册与内容证明分别展示，不代表测试已执行或通过。",
                "description_en": "Static association with original test content; compilation, registration and content proofs are separate, not evidence of execution or success."})
        return {NAMESPACE: {"uses": uses, "sources": tuple(sources.values()), "totalUses": len(entries),
                            "truncated": omitted, "limit": limit, "sourceLimit": source_limit}}


def render_test_content(extensions):
    view = (extensions or {}).get(NAMESPACE)
    if not view:
        return ""
    lines = []
    for item in view["uses"]:
        lines.append("<li>"+escape(str(item["testName"]))+"："+escape(item["description"])+
                     " 编译="+escape(item["buildStatus"])+"，注册="+escape(item["registrationStatus"])+
                     "，内容="+escape(item["content"].get("relation", "unknown"))+
                     "；原因="+escape(", ".join(item["reasonCodes"]))+"</li>")
    return "<section><h4>原始测试内容</h4><ul>"+"".join(lines)+"</ul>"+(
        "<p>部分测试来源未展示，保持未知。</p>" if view["truncated"] else "")+"</section>"
