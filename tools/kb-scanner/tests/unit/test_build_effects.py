import unittest
from dataclasses import replace

from kb_scanner.core import FrontendSnapshot, stable_id
from kb_scanner.frontends.build.macro_arguments import parse_macro_recipes
from kb_scanner.frontends.build.vocabulary import make_build_evidence, BuildInputKind
from kb_scanner.normalization.build_effects import validate_effects
from kb_scanner.normalization.build import BuildEvidenceNormalizer
from tests.unit.test_build_macro_binding import facts
from tests.unit.build_selection.support import context


class BuildEffectTests(unittest.TestCase):
    def evidence(self):
        entity=facts().entities[-1]
        records=parse_macro_recipes('F=-D\nV=X\nx.o: x.cpp\n\tc++ $(F) $(V) -c x.cpp\n','Makefile')
        return entity,tuple(make_build_evidence(r,path='Makefile',subject_id=entity.id,producer='fake',input_kind=BuildInputKind.MAKE) for r in records)

    def test_multisource_validation_and_stable_normalization(self):
        entity,items=self.evidence()
        self.assertEqual(frozenset(),validate_effects(items))
        first=BuildEvidenceNormalizer().normalize(context(),FrontendSnapshot((entity,),items))
        second=BuildEvidenceNormalizer().normalize(context(),FrontendSnapshot((entity,),tuple(reversed(items))))
        self.assertEqual(first,second)
        self.assertEqual({e.id for e in items},{e.id for e in first.value.evidence})

    def test_missing_conflicting_and_cross_use_provenance(self):
        entity,items=self.evidence()
        arg=next(e for e in items if e.kind=='build_argument')
        origins=[e for e in items if e.kind=='build_assignment']
        for replacement in ({'useId':None},{'order':-1},{'order':True},{'originKeys':('missing',)}):
            broken=replace(arg,metadata={**arg.metadata,'sourceChain':{**arg.metadata['sourceChain'],**replacement}})
            self.assertEqual({arg.id},set(validate_effects((broken,*origins))))
        self.assertEqual({arg.id},set(validate_effects((arg,))))
        origin=origins[0]
        changed = replace(origin,metadata={**origin.metadata,'configuration':'other'})
        self.assertIn(arg.id,validate_effects(tuple(changed if e.id==origin.id else e for e in items)))
        for change in ({'location':None},{'metadata':{**origin.metadata,'configuration':'other'}}):
            other=replace(origin,id=stable_id('other'),**change)
            self.assertIn(arg.id,validate_effects((*items,other)))
        result=BuildEvidenceNormalizer().normalize(context(),FrontendSnapshot((entity,),(arg,)))
        self.assertEqual('unknown',result.value.facts[0].metadata['effectProvenanceStatus'])
        self.assertTrue(result.diagnostics)

    def test_use_identity_does_not_merge_same_location(self):
        entity,items=self.evidence()
        arg=next(e for e in items if e.kind=='build_argument')
        other=replace(arg,id=stable_id('second-use'),metadata={**arg.metadata,'sourceChain':{**arg.metadata['sourceChain'],'useId':'other'}})
        result=BuildEvidenceNormalizer().normalize(context(),FrontendSnapshot((entity,),(*items,other)))
        args=[f for f in result.value.facts if f.kind=='build_argument']
        self.assertEqual(2,len(args))
        self.assertEqual(2,len({f.scope for f in args}))
