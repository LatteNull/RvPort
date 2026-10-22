from dataclasses import replace
import unittest
from unittest.mock import patch

from kb_scanner.analyzers import BuildSelectionAnalyzer
from kb_scanner.analyzers.build_selection import _knowledge_matches
from kb_scanner.core import Entity, stable_id
from tests.unit.build_selection.support import context
from tests.unit.projection_reachability.test_build_reachability import fixture


class BuildQueryTests(unittest.TestCase):
    def test_unreferenced_facts_are_not_matched(self):
        facts, knowledge = fixture(pattern=False)
        with patch('kb_scanner.analyzers.build_selection._knowledge_matches', side_effect=AssertionError('no reachable source')):
            result = BuildSelectionAnalyzer().analyze(context(), facts, knowledge)
        self.assertFalse(any(r.kind == 'uses_source' for r in result.value.relations))

    def test_reachable_matches_keep_all_ids_and_skip_unrelated_sources(self):
        facts, knowledge = fixture()
        unused = Entity(stable_id('unused'), 'source_file', 'unused.c')
        symbol = facts.facts[-1]
        other = replace(symbol, id=stable_id('unused-fact'), subject_id=unused.id)
        facts = replace(facts, entities=(*facts.entities, unused), facts=(*facts.facts, other))
        entry = knowledge.entries[0]
        duplicate = replace(entry, id=stable_id('second-entry'))
        arm = replace(entry, id=stable_id('arm-entry'), architecture_family='arm')
        unrelated = replace(entry, id=stable_id('unrelated-entry'), fact_kind='headers')
        miss = replace(entry, id=stable_id('miss-entry'), canonical_value='ordinary')
        knowledge = replace(knowledge, entries=(entry, duplicate, arm, unrelated, miss))
        with patch('kb_scanner.analyzers.build_selection._knowledge_matches', wraps=_knowledge_matches) as matcher:
            result = BuildSelectionAnalyzer().analyze(context(), facts, knowledge)
        self.assertEqual(3, matcher.call_count)
        dependency = next(r for r in result.value.relations if r.metadata.get('itemKind') == 'source_x86_dependency')
        self.assertEqual(tuple(sorted((entry.id, duplicate.id))), dependency.metadata['knowledgeIds'])
        self.assertEqual(symbol.id, dependency.metadata['factId'])
