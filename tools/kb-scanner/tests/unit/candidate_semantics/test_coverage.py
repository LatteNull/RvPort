from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as S
import unittest

from kb_scanner.core import AnalysisSnapshot, KnowledgeEntry, NormalizedFact, NormalizedSnapshot, stable_id
from kb_scanner.detectors.candidate_coverage import covered_identifier_candidate
from kb_scanner.detectors.local import LocalX86Detector
from kb_scanner.detectors.matchers import MatchResult
from tests.unit.knowledge_detection.support import make_context, make_entity, make_evidence
from tests.unit.knowledge_detection.test_local_matchers import knowledge


class CandidateCoverageTests(unittest.TestCase):
    def test_complete_identifiers_only(self):
        entries = {"k": S(canonical_value="__i386__")}
        matches = [(None, None), (None, MatchResult(("k", "missing"), "confirmed_local", "exact")), (None, MatchResult((), "candidate", "name"))]
        for text, expected in [("defined(__i386__)", True), ("defined(__i386__) || MY_X86_MODE", False), ("MY_X86_MODE", False), ("normal", False)]:
            self.assertEqual(expected, covered_identifier_candidate(S(canonical_value=text), matches, entries))

    def test_detector_keeps_fact_and_uncovered_occurrences(self):
        entity = make_entity()
        k = knowledge()
        entry = KnowledgeEntry(stable_id("i386"), "platformMacros", "x86", "__i386__", (k.sources[0].id,))
        k = replace(k, entries=(*k.entries, entry))
        evidence = tuple(make_evidence(entity, "preprocessor_condition", text, line=i+1) for i, text in enumerate(("defined(__i386__)", "defined(__i386__) || MY_X86_MODE", "_7Z_X86")))
        facts = tuple(NormalizedFact(stable_id("fact", e.id), "preprocessor", entity.id, e.value, "default", (e.id,), metadata={"configuration": str(i)}) for i, e in enumerate(evidence))
        snapshot = NormalizedSnapshot((entity,), evidence, facts)
        result = LocalX86Detector(deferred_capabilities={}).detect(make_context(Path("/project")), snapshot, AnalysisSnapshot(), k)
        candidates = [o for o in result.value.observations if o.status == "candidate"]
        self.assertEqual(2, len(candidates))
        self.assertEqual({facts[1].id, facts[2].id}, {o.metadata["factId"] for o in candidates})
        self.assertEqual((entity,), snapshot.entities)
        self.assertEqual(evidence, snapshot.evidence)
        self.assertEqual(facts, snapshot.facts)
        self.assertEqual({"1", "2"}, {o.metadata["configuration"] for o in candidates})
