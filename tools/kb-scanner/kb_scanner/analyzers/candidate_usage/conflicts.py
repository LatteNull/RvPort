"""按配置和源码位置索引已确认依赖，只补充用途冲突，不生成执行关系。"""
from bisect import bisect_left
from collections import defaultdict
from dataclasses import replace

from ...classifiers.risk import DEPENDENCIES
from ...detectors.definitions import DEFAULT_DEFINITIONS
from ...detectors.matchers import KnowledgeIndex, match_fact


class ExecutionConflictIndex:
    def __init__(self, facts, knowledge, roots):
        self.locations = defaultdict(list)
        self.cache = {}
        demanded = {(root.subject_id, root.configuration) for root in roots}
        evidence = {item.id: item for item in facts.evidence}
        definitions = defaultdict(list)
        for definition in DEFAULT_DEFINITIONS.values():
            if definition.observation_kind in DEPENDENCIES and definition.input_kind != "compiler_argument":
                definitions[definition.input_kind].append(definition)
        relevant = []
        for fact in facts.facts:
            configuration = fact.metadata.get("compilationContextId") or fact.metadata.get("configuration", "default")
            if (fact.kind not in definitions or (fact.subject_id, configuration) not in demanded
                    or fact.context_ids and fact.context_ids != (configuration,)):
                continue
            relevant.append((fact, configuration))
        kinds = {kind for fact, _ in relevant for definition in definitions[fact.kind]
                 for kind in definition.knowledge_kinds}
        index = KnowledgeIndex(replace(knowledge, entries=tuple(entry for entry in knowledge.entries
            if entry.fact_kind in kinds))) if relevant else None
        for fact, configuration in relevant:
            if not any((match := match_fact(definition, fact, index)) is not None
                       and match.status == "confirmed_local" for definition in definitions.get(fact.kind, ())):
                continue
            for identifier in fact.evidence_ids:
                item = evidence.get(identifier)
                if item is None or item.location is None or item.subject_id != fact.subject_id:
                    continue
                span = item.location
                if span.start.column is None or span.end.column is None:
                    continue
                key = fact.subject_id, configuration, span.start.path
                self.locations[key].append(((span.start.line, span.start.column),
                    (span.end.line, span.end.column), identifier))
        self.locations = {key: tuple(sorted(set(values))) for key, values in self.locations.items()}
        self.starts = {key: tuple(value[0] for value in values) for key, values in self.locations.items()}

    def annotate(self, root, resolution, session, scope_facts):
        conflicts = set()
        for scope_id, query in resolution["queries"]:
            cache_key = root.subject_id, root.configuration, scope_id, query["recordKeys"]
            if cache_key not in self.cache:
                source = session.evidence[scope_facts[scope_id].evidence_ids[0]]
                key = root.subject_id, root.configuration, source.location.start.path
                values, starts = self.locations.get(key, ()), self.starts.get(key, ())
                found = set()
                for record_key in query["recordKeys"]:
                    span = session.indexes[scope_id].rows[record_key]["span"]
                    start, end = span[:2], span[2:]
                    first, last = bisect_left(starts, start), bisect_left(starts, end)
                    found.update(identifier for _, finish, identifier in values[first:last] if finish <= end)
                self.cache[cache_key] = tuple(sorted(found))
            conflicts.update(self.cache[cache_key])
        reasons = set(resolution["reasonCodes"])
        if conflicts:
            reasons.add("usage-known-execution-conflict")
        return {**resolution, "status": "unknown" if conflicts else resolution["status"],
            "reasonCodes": tuple(sorted(reasons)), "conflictEvidenceIds": tuple(sorted(conflicts))}
