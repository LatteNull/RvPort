"""消费者独立变异测试；拒绝伪完整摘要及悬空/跨配置支持引用。"""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from kb_scanner.classifiers.usage_proof import valid_usage_proof, UsageProofValidator, _support_graph
from kb_scanner.classifiers.semantic_admission import SemanticAdmissionIndex
from kb_scanner.core import stable_id
from tests.unit.candidate_semantics.test_admission import inputs


class UsageProofValidationTests(unittest.TestCase):
    def test_cached_support_graph_rechecks_root_identity_provenance_and_configuration(self):
        obs, analysis = inputs()
        role = analysis.relations[0]
        entities = {item.id: item for item in analysis.entities}
        relations = {item.id: item for item in analysis.relations}
        roots = set(obs.metadata['matchedEvidenceIds'])
        validator = UsageProofValidator(entities, relations)
        with patch('kb_scanner.classifiers.usage_proof._support_graph', wraps=_support_graph) as graph:
            self.assertTrue(validator.valid(role, roots, 'default'))
            self.assertTrue(validator.valid(role, roots, 'default'))
            self.assertEqual(1, graph.call_count)
            original = role.metadata['usageProof']
            binding = original['rootBindings'][0]
            for updates in ({'subjectId': stable_id('other')}, {'truncated': True},
                            {'supportingEvidenceIds': tuple(roots)},
                            {'rootBindings': ({**binding, 'scopeId': stable_id('other')},)},
                            {'rootBindings': ({'evidenceId': {}},)}):
                altered = replace(role, metadata={**role.metadata, 'usageProof': {**original, **updates}})
                self.assertFalse(validator.valid(altered, roots, 'default'))
                self.assertEqual(valid_usage_proof(altered, entities, relations, roots, 'default'),
                                 validator.valid(altered, roots, 'default'))
            self.assertFalse(validator.valid(role, {stable_id('other-root')}, 'default'))
            self.assertFalse(validator.valid(role, roots, 'other'))
        # 缓存快照与调用者字典隔离；新的损坏快照不能借用旧成功结果。
        entities.clear()
        self.assertTrue(validator.valid(role, roots, 'default'))
        broken = UsageProofValidator(entities, relations)
        self.assertFalse(broken.valid(role, roots, 'default'))
        self.assertFalse(broken.valid(role, roots, 'default'))

    def test_complete_contract_and_summary_shape_mutations(self):
        obs, analysis = inputs("non_execution_data")
        role = analysis.relations[0]
        entities = {item.id: item for item in analysis.entities}
        relations = {item.id: item for item in analysis.relations}
        roots = set(obs.metadata["matchedEvidenceIds"])
        check = lambda value: valid_usage_proof(value, entities, relations, roots, "default")
        self.assertTrue(check(role))
        for summary in (None, {}, {**role.metadata["usageProof"], "version": True},
                        {**role.metadata["usageProof"], "rootBindings": ({"evidenceId": {}},)}):
            self.assertFalse(check(replace(role, metadata={**role.metadata, "usageProof": summary})))
        updates = {"version": 2, "status": "unknown", "truncated": True, "reasonCodes": ("partial",),
                   "factId": stable_id("other"), "subjectId": stable_id("other"), "configuration": "other",
                   "expectedUseCount": 99, "resolvedUseCount": True, "unresolvedCount": 1,
                   "conflictCount": 1, "escapeCount": 1, "rootBindings": ()}
        for key, value in updates.items():
            with self.subTest(key=key):
                summary = {**role.metadata["usageProof"], key: value}
                self.assertFalse(check(replace(role, metadata={**role.metadata, "usageProof": summary})))
        for name in ("matchedEvidenceIds", "recordIds", "scopeCoverageIds", "supportingRelationIds", "supportingEvidenceIds", "useRecordIds"):
            for value in ((), (1,), (stable_id("same"),)*2, (stable_id("missing"),)):
                with self.subTest(name=name, value=value):
                    summary = {**role.metadata["usageProof"], name: value}
                    self.assertFalse(check(replace(role, metadata={**role.metadata, "usageProof": summary})))

    def test_record_and_scope_provenance_must_be_complete(self):
        obs, analysis = inputs()
        role = analysis.relations[0]
        entities = {item.id: item for item in analysis.entities}
        relations = {item.id: item for item in analysis.relations}
        roots = set(obs.metadata["matchedEvidenceIds"])
        records = [entity for entity in analysis.entities if entity.kind == "usage_record" and entity.name == "identifier"]
        scope = next(entity for entity in analysis.entities if entity.kind == "usage_scope_coverage")
        record = records[0]
        invalid = [replace(record, location=None), replace(record, kind="source_file"),
            replace(record, properties={**record.properties, "configuration": "other"}),
            replace(record, properties={**record.properties, "sourceEvidenceIds": ()}),
            replace(record, properties={**record.properties, "sourceEvidenceIds": (stable_id("missing"),)}),
            replace(record, properties={**record.properties, "bindingStatus": "unknown"}),
            replace(scope, kind="source_file")]
        for name, value in (("status", "partial"), ("recordIds", ()), ("expectedUseCount", True),
                            ("expectedUseCount", 99), ("expectedUseRecordIds", ())):
            invalid.append(replace(scope, properties={**scope.properties, name: value}))
        for changed in invalid:
            with self.subTest(entity=changed):
                self.assertFalse(valid_usage_proof(role, {**entities, changed.id: changed}, relations, roots, "default"))
        missing = {key: value for key, value in entities.items() if key != record.id}
        self.assertFalse(valid_usage_proof(role, missing, relations, roots, "default"))

    def test_support_links_and_actual_connectivity_are_required(self):
        obs, analysis = inputs()
        role = analysis.relations[0]
        entities = {item.id: item for item in analysis.entities}
        relations = {item.id: item for item in analysis.relations}
        roots = set(obs.metadata["matchedEvidenceIds"])
        link = next(r for r in analysis.relations if r.kind == "usage_dependency")
        for changed in (replace(link, kind="selects"), replace(link, status="partial"),
                        replace(link, source_id=stable_id("missing")), replace(link, evidence_ids=()),
                        replace(link, metadata={**link.metadata, "configuration": "other"}),
                        replace(link, metadata={**link.metadata, "semanticRole": "execution"}),
                        replace(link, evidence_ids=(stable_id("missing"),))):
            self.assertFalse(valid_usage_proof(role, entities, {**relations, link.id: changed}, roots, "default"))
        for kind in ("usage_scope_member", "usage_dependency"):
            summary = {**role.metadata["usageProof"], "supportingRelationIds": tuple(
                rid for rid in role.metadata["usageProof"]["supportingRelationIds"] if relations[rid].kind != kind)}
            changed = replace(role, metadata={**role.metadata, "usageProof": summary})
            self.assertFalse(valid_usage_proof(changed, entities, relations, roots, "default"))
        binding = role.metadata["usageProof"]["rootBindings"][0]
        for key, value in (("scopeId", stable_id("other")), ("recordId", role.source_id)):
            summary = {**role.metadata["usageProof"], "rootBindings": ({**binding, key: value},)}
            self.assertFalse(valid_usage_proof(replace(role, metadata={**role.metadata, "usageProof": summary}), entities, relations, roots, "default"))

    def test_paths_cannot_be_empty_truncated_or_miss_role_edge(self):
        obs, analysis = inputs()
        role, proof = analysis.relations[0], analysis.proof_paths[0]
        index = SemanticAdmissionIndex(analysis)
        self.assertFalse(index._complete(replace(proof, relation_ids=()), role))
        fake = SimpleNamespace(status="complete", truncated=True, relation_ids=proof.relation_ids,
                               source_id=proof.source_id, target_id=proof.target_id)
        self.assertFalse(index._complete(fake, role))
        self.assertEqual("excluded", index.decide(obs).status)
