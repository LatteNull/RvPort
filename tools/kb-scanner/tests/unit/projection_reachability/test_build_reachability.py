from __future__ import annotations

import unittest

from kb_scanner.analyzers import BuildSelectionAnalyzer
from kb_scanner.core import (
    Entity, Evidence, KnowledgeEntry, KnowledgeSnapshot, KnowledgeSource,
    NormalizedFact, NormalizedSnapshot, stable_id,
)
from tests.unit.build_selection.support import context


def fixture(
    *, pattern: bool = True, target_status: str = "selected", target_configuration: str = "cfg",
    pattern_configuration: str = "cfg",
):
    makefile = Entity(stable_id("makefile"), "build_file", "src/Makefile")
    source = Entity(stable_id("source"), "source_file", "src/foo.c")
    records = [
        ("build_target", "foo", {"selectionStatus": target_status, "configuration": target_configuration}),
    ]
    if pattern:
        records.append(("build_source", "%.c", {"selectionStatus": "selected", "target": "$(OBJDIR)/%.o", "configuration": pattern_configuration}))
    records.append(("symbol", "_mm_add_ps", {}))
    evidence = []
    facts = []
    for index, (kind, value, metadata) in enumerate(records):
        subject = source if kind == "symbol" else makefile
        evidence_id = stable_id("evidence", index, kind, value)
        evidence.append(Evidence(evidence_id, "call_expression" if kind == "symbol" else kind, subject.id, value, "unit", "static", "high", metadata=metadata))
        facts.append(NormalizedFact(stable_id("fact", index, kind, value), kind, subject.id, value, f"scope:{index}", (evidence_id,), metadata=metadata))
    knowledge_source = KnowledgeSource(stable_id("knowledge-source"), "unit", "generated", "facts.json", "0" * 64)
    entry = KnowledgeEntry(stable_id("knowledge-entry"), "intrinsics", "x86", "_mm_add_ps", (knowledge_source.id,))
    return NormalizedSnapshot((makefile, source), tuple(evidence), tuple(facts)), KnowledgeSnapshot("unit", "1", (knowledge_source,), (entry,))


class BuildReachabilityTests(unittest.TestCase):
    def test_closes_target_pattern_source_and_x86_dependency(self) -> None:
        facts, knowledge = fixture()
        result = BuildSelectionAnalyzer().analyze(context(), facts, knowledge)
        relations = result.value.relations
        membership = next(item for item in relations if item.kind == "uses_source")
        dependency = next(item for item in relations if item.metadata.get("itemKind") == "source_x86_dependency")
        self.assertEqual("selected", membership.status)
        self.assertEqual("cfg", dependency.metadata["configuration"])
        self.assertEqual((knowledge.entries[0].id,), dependency.metadata["knowledgeIds"])
        proof = next(item for item in result.value.proof_paths if dependency.id in item.relation_ids)
        self.assertEqual("complete", proof.status)
        self.assertIn(membership.id, proof.relation_ids)

    def test_does_not_infer_source_membership_without_pattern_evidence(self) -> None:
        facts, knowledge = fixture(pattern=False)
        result = BuildSelectionAnalyzer().analyze(context(), facts, knowledge)
        self.assertFalse(any(item.kind == "uses_source" for item in result.value.relations))
        self.assertFalse(any(item.metadata.get("itemKind") == "source_x86_dependency" for item in result.value.relations))

    def test_inactive_and_configuration_conflict_are_not_promoted_to_selected(self) -> None:
        inactive_facts, knowledge = fixture(target_status="inactive")
        inactive = BuildSelectionAnalyzer().analyze(context(), inactive_facts, knowledge)
        inactive_dependencies = [
            item for item in inactive.value.relations if item.metadata.get("itemKind") == "source_x86_dependency"
        ]
        self.assertEqual(["inactive"], [item.status for item in inactive_dependencies])
        inactive_proof = next(
            item
            for item in inactive.value.proof_paths
            if any(relation.id in item.relation_ids for relation in inactive_dependencies)
        )
        self.assertEqual("complete", inactive_proof.status)

        conflict_facts, knowledge = fixture(pattern_configuration="other")
        conflict = BuildSelectionAnalyzer().analyze(context(), conflict_facts, knowledge)
        conflict_dependencies = [
            item for item in conflict.value.relations if item.metadata.get("itemKind") == "source_x86_dependency"
        ]
        self.assertEqual(["unknown"], [item.status for item in conflict_dependencies])
        conflict_proof = next(
            item
            for item in conflict.value.proof_paths
            if any(relation.id in item.relation_ids for relation in conflict_dependencies)
        )
        self.assertEqual("unknown", conflict_proof.status)


if __name__ == "__main__":
    unittest.main()
