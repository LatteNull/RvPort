"""原始项目测试语境与静态内容关联；不产生第二份迁移结论。"""
from collections import defaultdict

from ..core import AnalysisSnapshot, CompletionStatus, Diagnostic, DiagnosticSeverity, Entity, Relation, StageResult, candidate_test_path, stable_id
from ..detectors.demand import FactProofDemand
from .test_content_structure import ContentIndex
from .macro_session import MacroSession


CATALOG = "test_content_catalog"


def _assert_states(evidence, files, source, *, session=None, observed=None):
    states = {}
    if observed is None:
        observed = defaultdict(list)
        for item in evidence:
            profile = item.metadata.get("standardAssert")
            if item.subject_id == source.id and item.location and profile:
                observed[(item.location.start.line, item.location.start.column)].append({**profile, "evidenceId": item.id})
    session = session or MacroSession(evidence, files)
    session.events, session.visits = 0, 0
    session.reasons.clear()
    def consume(item, environment, active, evaluation):
        if item.kind != "call_expression" or item.value != "assert":
            return
        state = environment.get("NDEBUG")
        macro = environment.get("assert")
        # An unresolved system include/name alone does not establish standard
        # macro identity. Preserve the shape, explicit overrides and uncertainty.
        reasons = {"test-standard-assert-not-proven"}
        if macro is not None:
            reasons.add("test-assert-macro-overridden")
        if state is None or state.defined is None:
            reasons.add("test-assert-ndebug-unknown")
        point = (item.location.start.line, item.location.start.column)
        profiles = sorted(observed.get(point, ()), key=lambda p: (p["configuration"], p["evidenceId"]))
        if profiles:
            reasons.discard("test-standard-assert-not-proven")
            reasons.add("test-assert-target-configuration-unproven")
        states[point] = {
            "status": "unknown", "active": active, "ndebugDefined": state.defined if state else None,
            "observedConfigurations": tuple(profiles),
            "reasonCodes": tuple(sorted(reasons)),
            "evidenceIds": tuple(sorted({item.id, *(p["evidenceId"] for p in profiles), *(state.evidence_ids if state else ()), *(macro.evidence_ids if macro else ())}))}
    session.run(source, {}, consume)
    return states


class TestContentAnalyzer:
    def __init__(self, demand=None, *, limit=4096, relation_limit=10000, visit_limit=20000):
        if min(limit, relation_limit, visit_limit) < 1:
            raise ValueError("test content budgets must be positive")
        self.demand = demand or FactProofDemand()
        self.limit, self.relation_limit, self.visit_limit = limit, relation_limit, visit_limit

    def analyze(self, context, facts, knowledge, base):
        inventories, conflicts = {}, set()
        for item in sorted(facts.evidence, key=lambda e: e.id):
            if item.kind != "test_content":
                continue
            previous = inventories.get(item.subject_id)
            if previous is not None and previous.metadata != item.metadata:
                conflicts.add(item.subject_id)
            inventories.setdefault(item.subject_id, item)
        if not inventories:
            return StageResult(base)
        requested = self.demand(facts, knowledge)
        evidence = {e.id: e for e in facts.evidence}
        files = {e.name: e for e in facts.entities if e.kind == "source_file"}
        files_by_id = {e.id: e for e in files.values()}
        registrations, members, build_keys = defaultdict(list), defaultdict(list), {}
        for item in facts.evidence:
            data = item.metadata.get("cmake", {})
            if "key" in data:
                build_keys[data["key"]] = item
            registration = data.get("testRegistration")
            if registration:
                registrations[registration["target"], registration["configuration"]].append((item, registration))
            if item.kind == "build_source":
                target = data.get("target") or item.metadata.get("target")
                cfg = item.metadata.get("configuration", "default")
                members[str(item.value).removeprefix("./")].append((item, target, cfg))
        entities = {e.id: e for e in (*facts.entities, *base.entities)}
        relations = {r.id: r for r in base.relations}
        indexes, assertion_cache, macro_session = {}, {}, None
        observed = defaultdict(lambda: defaultdict(list))
        legacy_members = defaultdict(list)
        for relation in base.relations:
            target = entities.get(relation.source_id)
            if relation.kind == "contains_test" and target and target.kind == "test_target":
                legacy_members[relation.target_id].append((target, relation))
        entries, truncated, visits = [], False, 0
        partial_sources = {}
        location_ids = {}
        for item in facts.evidence:
            profile = item.metadata.get("standardAssert")
            if item.location and profile:
                observed[item.subject_id][item.location.start.line, item.location.start.column].append({**profile, "evidenceId": item.id})
            if item.location and item.kind == "call_expression":
                location_ids[item.subject_id, item.location.start.line, item.location.start.column] = item.id

        def connect(left_id, right_id, configuration, kind="contains", status="unknown"):
            nonlocal truncated
            if not left_id or not right_id or left_id == right_id or left_id not in evidence or right_id not in evidence:
                return
            if len(relations) - len(base.relations) >= self.relation_limit:
                truncated = True
                return
            for eid in (left_id, right_id):
                identifier = stable_id("test-content-source", eid, configuration)
                entities[identifier] = Entity(identifier, "source_occurrence", str(evidence[eid].value),
                    evidence[eid].location, {"sourceEvidenceId": eid, "configuration": configuration})
            source, target = (stable_id("test-content-source", eid, configuration) for eid in (left_id, right_id))
            rid = stable_id("test-content-relation", source, target, kind)
            relations[rid] = Relation(rid, kind, source, target, (left_id, right_id),
                "medium", status, {"configuration": configuration, "testContent": True})

        for eid in sorted(requested):
            item = evidence.get(eid)
            if item is None or item.location is None or item.subject_id not in inventories or item.subject_id not in files_by_id:
                continue
            visits += 1
            if visits > self.visit_limit or len(entries) >= self.limit:
                truncated = True
                break
            source = files_by_id[item.subject_id]
            contexts = []
            for member, target, cfg in members.get(source.name, ()):
                for registration, data in registrations.get((target, cfg), ()):
                    contexts.append((member, registration, data))
            if not contexts:
                for target, relation in legacy_members.get(source.id, ()):
                    member = next((evidence[e] for e in relation.evidence_ids if e in evidence), None)
                    contexts.append((member, None, {"name": target.name, "role": "candidate",
                        "configuration": target.properties.get("configuration", "default"),
                        "registrationStatus": "unknown", "sourceKeys": (),
                        "reasonCodes": ("test-entry-registration-unproven",)}))
            if not contexts and candidate_test_path(source.name):
                contexts = [(None, None, {"name": source.name, "role": "candidate",
                    "configuration": "default", "registrationStatus": "unknown", "buildStatus": "unknown",
                    "sourceKeys": (), "reasonCodes": ("test-registration-missing",)})]
            if not contexts:
                continue
            if inventories[source.id].metadata["testContent"]["status"] != "complete":
                partial_sources[source.id] = source
            if item.subject_id not in indexes:
                indexes[item.subject_id] = ContentIndex(inventories[item.subject_id].metadata["testContent"])
            result = indexes[item.subject_id].resolve((item.location.start.line, item.location.start.column))
            for member, registration, data in contexts:
                if len(entries) >= self.limit:
                    truncated = True
                    break
                reasons = set(result["reasonCodes"]) | set(data["reasonCodes"])
                if result.get("entryStatus") == "complete" and any(
                        result.get(key) not in evidence for key in ("entryEvidenceId", "functionEvidenceId")):
                    reasons.add("test-content-source-reference-missing")
                if source.id in conflicts:
                    reasons.add("test-content-producer-conflict")
                state = None
                if "assertionSpan" in result:
                    if source.id not in assertion_cache:
                        if macro_session is None:
                            macro_session = MacroSession(facts.evidence, files)
                        assertion_cache[source.id] = _assert_states(facts.evidence, files, source,
                            session=macro_session, observed=observed[source.id])
                    state = assertion_cache[source.id].get(tuple(result["assertionSpan"][:2]),
                        {"status": "unknown", "reasonCodes": ("test-assert-environment-unavailable",), "evidenceIds": ()})
                    reasons.update(state["reasonCodes"])
                origins = [build_keys[key].id for key in data["sourceKeys"] if key in build_keys]
                if member:
                    origins.append(member.id)
                for key in ("entryEvidenceId", "functionEvidenceId"):
                    if result.get(key) in evidence:
                        origins.append(result[key])
                for key in ("callSpan", "assertionSpan"):
                    if key in result:
                        origin = location_ids.get((source.id, *result[key][:2]))
                        if origin:
                            origins.append(origin)
                origins.append(item.id)
                if state:
                    origins.extend(e for e in state["evidenceIds"] if e in evidence)
                entry = {"evidenceId": eid, "configuration": data["configuration"],
                    "testName": data["name"], "role": data["role"], "source": source.name,
                    "buildStatus": member.metadata.get("selectionStatus", "unknown") if member else "unknown",
                    "registrationStatus": data["registrationStatus"], "content": result,
                    "assertion": state, "reasonCodes": tuple(sorted(reasons)),
                    "sourceEvidenceIds": tuple(dict.fromkeys(origins)),
                    "proofStatus": "complete" if not reasons and data["role"] == "confirmed" else "unknown"}
                entries.append(entry)
                # Only actual connected pairs become graph edges; catalog order
                # is not a path. Unknown applicability is explicit on new edges.
                cfg = data["configuration"]
                if registration and result.get("entryEvidenceId"):
                    connect(registration.id, result["entryEvidenceId"], cfg)
                if result.get("callSpan"):
                    call_id = location_ids.get((source.id, *result["callSpan"][:2]))
                    connect(result.get("entryEvidenceId"), call_id, cfg)
                    connect(call_id, result.get("functionEvidenceId"), cfg, "calls")
                parent_id = result.get("functionEvidenceId")
                if result.get("assertionSpan"):
                    assert_id = location_ids.get((source.id, *result["assertionSpan"][:2]))
                    connect(parent_id, assert_id, cfg)
                    parent_id = assert_id
                if result["relation"] != "unknown":
                    connect(parent_id, eid, cfg)
        if not entries and not truncated:
            return StageResult(base)
        if truncated:
            for entry in entries:
                entry["proofStatus"] = "unknown"
                entry["reasonCodes"] = tuple(sorted(set(entry["reasonCodes"]) | {"test-content-budget"}))
        catalog = Entity(stable_id(CATALOG, 1), CATALOG, "原始测试内容", properties={
            "version": 1, "entries": entries, "truncated": truncated,
            "limit": self.limit, "queries": sum(index.queries for index in indexes.values()),
            "indexedFiles": len(indexes), "visitedFacts": visits})
        entities[catalog.id] = catalog
        diagnostics = (Diagnostic("test-content.budget", "analysis.test-content", DiagnosticSeverity.WARNING,
            "测试内容证明达到预算，未处理部分保持未知 / Test content budget exceeded; omitted relations remain unknown",
            producer="test-content", details={"reason": "test-content-budget"}),) if truncated else ()
        diagnostics += tuple(Diagnostic("test-content.partial", "analysis.test-content", DiagnosticSeverity.WARNING,
            "相关测试内容清单不完整 / Relevant test content inventory is incomplete", producer="test-content",
            location=inventories[subject].location.start if inventories[subject].location else None,
            details={"reasonCodes": inventories[subject].metadata["testContent"]["reasonCodes"]})
            for subject in sorted(partial_sources))
        return StageResult(AnalysisSnapshot(tuple(sorted(relations.values(), key=lambda r:r.id)),
            tuple(sorted(entities.values(), key=lambda e:e.id)), base.proof_paths),
            CompletionStatus.PARTIAL if diagnostics else CompletionStatus.COMPLETE, diagnostics)
