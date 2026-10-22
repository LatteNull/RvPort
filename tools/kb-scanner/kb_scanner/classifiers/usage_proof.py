"""消费端复核用途闭包引用和计数，不凭 scopeComplete 布尔值排除候选。"""
from collections.abc import Mapping
from types import MappingProxyType


class UsageProofValidator:
    """在不可变分析快照内复用支持图校验；每根身份与来源仍独立复核。"""

    def __init__(self, entities, relations):
        self.entities = MappingProxyType(dict(entities))
        self.relations = MappingProxyType(dict(relations))
        self.graphs = {}

    def valid(self, role, roots, configuration):
        try:
            return _valid(role, self.entities, self.relations, roots, configuration, self.graphs)
        except (KeyError, TypeError, ValueError):
            return False


def _ids(value, *, nonempty=True):
    return (isinstance(value, tuple) and (bool(value) or not nonempty)
            and all(isinstance(item, str) for item in value) and len(set(value)) == len(value))


def valid_usage_proof(role, entities, relations, roots, configuration):
    try:
        return _valid(role, entities, relations, roots, configuration)
    except (KeyError, TypeError, ValueError):
        # 外部或旧 producer 的不完整标量合同只能拒绝，不能使分类进程退出。
        return False


def _valid(role, entities, relations, roots, configuration, cache=None):
    summary = role.metadata.get("usageProof")
    if not isinstance(summary, Mapping):
        return False
    if (type(summary.get("version")) is not int or summary["version"] != 1
            or summary.get("status") != "complete" or summary.get("truncated") is not False
            or summary.get("reasonCodes") != ()
            or summary.get("factId") != role.metadata.get("factId")
            or summary.get("subjectId") != role.source_id or summary.get("configuration") != configuration):
        return False
    names = ("matchedEvidenceIds", "recordIds", "scopeCoverageIds", "supportingRelationIds", "supportingEvidenceIds", "useRecordIds")
    if any(not _ids(summary.get(name)) for name in names):
        return False
    records, scopes, uses = set(summary["recordIds"]), set(summary["scopeCoverageIds"]), set(summary["useRecordIds"])
    source_ids = set(summary["supportingEvidenceIds"])
    if (set(summary["matchedEvidenceIds"]) != roots or not roots.issubset(source_ids)
            or not source_ids.issubset(role.evidence_ids) or not uses.issubset(records)
            or len(records) > 4096 or len(summary["supportingRelationIds"]) > 8192):
        return False
    for name in ("expectedUseCount", "resolvedUseCount", "unresolvedCount", "conflictCount", "escapeCount"):
        if type(summary.get(name)) is not int:
            return False
    if (summary["expectedUseCount"] != len(uses) or summary["resolvedUseCount"] != len(uses)
            or any(summary[name] != 0 for name in ("unresolvedCount", "conflictCount", "escapeCount"))):
        return False
    bindings = summary.get("rootBindings")
    if (not isinstance(bindings, tuple) or len(bindings) != len(roots)
            or any(not isinstance(binding, Mapping) for binding in bindings)
            or {binding.get("evidenceId") for binding in bindings} != roots
            or any(binding.get("recordId") not in records for binding in bindings)):
        return False
    graph_key = (configuration, *(summary[name] for name in
        ("recordIds", "scopeCoverageIds", "useRecordIds", "supportingRelationIds")))
    if cache is None or graph_key not in cache:
        graph = _support_graph(records, scopes, uses, summary["supportingRelationIds"],
                               configuration, entities, relations)
        if cache is not None:
            cache[graph_key] = graph
    else:
        graph = cache[graph_key]
    if graph is None:
        return False
    required_sources, record_scopes, components = graph
    if not required_sources.issubset(source_ids):
        return False
    for binding in bindings:
        if (record_scopes[binding["recordId"]] != binding.get("scopeId")
                or binding["recordId"] not in uses):
            return False
    return {components[binding["recordId"]] for binding in bindings} == set(components.values())


def _support_graph(records, scopes, uses, relation_ids, configuration, entities, relations):
    """只检查与根无关的支持图，返回实际要求的来源及连通分量。"""
    expected_uses, covered_records, membership = set(), set(), set()
    required_sources, record_scopes = set(), {}
    for identifier in records | scopes:
        entity = entities.get(identifier)
        if (entity is None or entity.location is None
                or entity.properties.get("configuration") != configuration
                or not _ids(entity.properties.get("sourceEvidenceIds"))):
            return None
        required_sources.update(entity.properties["sourceEvidenceIds"])
        if identifier in records:
            if entity.kind != "usage_record" or identifier in uses and (
                    entity.name != "identifier" or entity.properties.get("bindingStatus") != "bound"):
                return None
            record_scopes[identifier] = entity.properties.get("scopeFactId")
        else:
            props = entity.properties
            if (entity.kind != "usage_scope_coverage" or props.get("status") != "complete"
                    or not _ids(props.get("recordIds")) or not _ids(props.get("expectedUseRecordIds"))
                    or type(props.get("expectedUseCount")) is not int
                    or props["expectedUseCount"] != len(props["expectedUseRecordIds"])):
                return None
            expected_uses.update(props["expectedUseRecordIds"])
            covered_records.update(props["recordIds"])
            membership.update((identifier, record) for record in props["recordIds"])
    if expected_uses != uses or covered_records != records:
        return None
    actual_membership, adjacency = set(), {identifier: set() for identifier in records}
    for rid in relation_ids:
        relation = relations.get(rid)
        if (relation is None or relation.status != "complete"
                or relation.metadata.get("semanticRole") != "non_executing_usage"
                or relation.metadata.get("configuration") != configuration
                or not relation.evidence_ids):
            return None
        required_sources.update(relation.evidence_ids)
        if relation.kind == "usage_scope_member":
            actual_membership.add((relation.source_id, relation.target_id))
        elif relation.kind == "usage_dependency" and relation.source_id in records and relation.target_id in records:
            adjacency[relation.source_id].add(relation.target_id)
            adjacency[relation.target_id].add(relation.source_id)
        else:
            return None
    if actual_membership != membership:
        return None
    components = {}
    for start in sorted(records):
        if start in components:
            continue
        pending = [start]
        while pending:
            identifier = pending.pop()
            if identifier not in components:
                components[identifier] = start
                pending.extend(neighbor for neighbor in adjacency[identifier] if neighbor not in components)
    return frozenset(required_sources), record_scopes, components
