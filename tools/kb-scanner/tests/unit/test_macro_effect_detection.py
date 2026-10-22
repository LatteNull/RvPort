from dataclasses import replace
import unittest

from kb_scanner.core import AnalysisSnapshot, FrontendSnapshot
from kb_scanner.analyzers.build_macro_binding import bind_build_macros
from kb_scanner.detectors import LocalX86Detector
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from tests.unit.test_build_macro_binding import facts
from tests.unit.test_macro_effects import macro, invocation
from tests.unit.knowledge_detection.test_local_detector import inputs


class MacroEffectDetectionTests(unittest.TestCase):
    def test_normalizer_keeps_configured_argument_producers_separate(self):
        from types import SimpleNamespace as NS
        from kb_scanner.core import stable_id
        call,args = invocation()
        raw = facts((call,*args))
        first = replace(args[0],metadata={**args[0].metadata,'compilationContextId':stable_id('x86-observed')})
        second = replace(first,id=stable_id('another-producer-context'),producer='clang',
                         metadata={**first.metadata,'compilationContextId':stable_id('riscv-target')})
        frontend = FrontendSnapshot(raw.entities,(first,second))
        result = CppEvidenceNormalizer().normalize(NS(compile_contexts=()),frontend).value
        self.assertEqual(2,len(result.facts))
        self.assertEqual({(stable_id('x86-observed'),),(stable_id('riscv-target'),)},{f.context_ids for f in result.facts})
        self.assertEqual({first.id,second.id},{e.id for e in result.evidence})

    def test_formal_knowledge_promotes_only_a_proven_terminal_and_keeps_raw_facts(self):
        from types import SimpleNamespace as NS
        for body, expected in ((('fn','(','a',')'),'confirmed_local'),(('a',),'candidate')):
            definitions = macro('OUTER', ('fn','a'), body)
            call, arguments = invocation()
            arguments = tuple(replace(item, metadata={**item.metadata,'callEvidenceId':call.id}) for item in arguments)
            raw = facts((*definitions,call,*arguments))
            frontend = FrontendSnapshot(tuple(e for e in raw.entities if e.kind=='source_file'),
                tuple(e for e in raw.evidence if not e.kind.startswith('build_')))
            normalized = CppEvidenceNormalizer().normalize(NS(compile_contexts=()), frontend).value
            normalized = replace(normalized, entities=raw.entities, evidence=raw.evidence)
            before = normalized
            entities, relations = {}, {}
            bind_build_macros(normalized, entities, relations, max_relations=1000)
            _, knowledge = inputs('intrinsic')
            knowledge = replace(knowledge, entries=(replace(knowledge.entries[0], fact_kind='intrinsics'),))
            analysis = AnalysisSnapshot(entities=tuple(entities.values()), relations=tuple(relations.values()))
            result = LocalX86Detector(deferred_capabilities={}).detect(None, normalized, analysis, knowledge)
            found = [o for o in result.value.observations if o.metadata['factKind']=='macro_argument']
            self.assertEqual(1,len(found))
            self.assertEqual(expected,found[0].status)
            self.assertEqual((arguments[0].id,),found[0].evidence_ids)
            self.assertEqual(before,normalized)

    def test_inherited_graph_does_not_spend_new_effect_budget(self):
        definitions = macro('OUTER', ('fn','a'), ('fn','(','a',')'))
        call, arguments = invocation()
        raw = facts((*definitions,call,*arguments))
        entities, relations = {}, {str(i):object() for i in range(1000)}
        self.assertFalse(bind_build_macros(raw, entities, relations, max_relations=100))
        self.assertGreater(len(relations),1000)
        entities, relations = {}, {}
        self.assertTrue(bind_build_macros(raw, entities, relations, max_relations=1))
        self.assertEqual(1,len(relations))
        self.assertLessEqual(len(entities),2)

    def test_source_only_macro_call_needs_no_existing_finding_or_build_file(self):
        call, arguments = invocation()
        raw = facts((*macro('OUTER', ('fn','a'), ('fn','(','a',')')),call,*arguments))
        raw = replace(raw,evidence=tuple(e for e in raw.evidence if not e.kind.startswith('build_')))
        entities, relations = {}, {}
        self.assertFalse(bind_build_macros(raw,entities,relations,max_relations=100))
        self.assertTrue(relations)
        self.assertTrue(all(r.metadata['configuration']=='source:x.cpp' for r in relations.values()))
        from unittest.mock import patch
        with patch('kb_scanner.analyzers.build_macro_binding.MacroSession',side_effect=AssertionError('no demand')):
            self.assertFalse(bind_build_macros(raw,{}, {},max_relations=100,demand_symbols=set()))
