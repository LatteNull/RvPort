import unittest
from dataclasses import replace

from kb_scanner.core import FrontendSnapshot
from kb_scanner.normalization import BuildEvidenceNormalizer
from tests.unit.test_build_macro_binding import facts
from tests.unit.build_selection.support import context


class BuildMacroNormalizationTests(unittest.TestCase):
    def test_argument_order_configuration_and_references_survive_normalization(self):
        source = facts(flags="-DX=0 -UX -DX=1")
        result = BuildEvidenceNormalizer().normalize(context(), FrontendSnapshot(source.entities, source.evidence)).value
        self.assertEqual(5, len(result.facts))  # 三参数、实际变量引用、recipe。
        by_id = {e.id: e for e in source.evidence}
        for fact in result.facts:
            self.assertEqual(1, len(fact.evidence_ids))
            original = by_id[fact.evidence_ids[0]]
            self.assertEqual(original.metadata["sourceChain"], fact.metadata["sourceChain"])
        arguments = sorted((f for f in result.facts if f.kind == "build_argument"), key=lambda f: f.metadata["sourceChain"]["order"])
        self.assertEqual(["0", "1", "1"], [f.metadata["sourceChain"]["value"] for f in arguments])
        self.assertEqual(["-D", "-U", "-D"], [f.metadata["sourceChain"]["operation"] for f in arguments])
        self.assertEqual(5, len({f.scope for f in result.facts}))

    def test_same_location_in_different_recipes_does_not_merge_occurrences(self):
        source = facts()
        original = source.evidence[0]
        from kb_scanner.core import stable_id
        other = replace(original, id=stable_id("another-recipe"), metadata={**original.metadata,
            "sourceChain": {**original.metadata["sourceChain"], "recipeLine": 10}})
        result = BuildEvidenceNormalizer().normalize(context(), FrontendSnapshot(source.entities, (original, other))).value
        self.assertEqual(2, len(result.facts))
        self.assertEqual({3, 10}, {f.metadata["sourceChain"]["recipeLine"] for f in result.facts})
