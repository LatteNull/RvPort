from dataclasses import replace
from pathlib import Path
import unittest

from kb_scanner.core import Entity, FrontendSnapshot, CompletionStatus, stable_id
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from kb_scanner.normalization.functions import valid_function, valid_owner, merge_metadata
from kb_scanner.frontends.cpp.function_inventory import inventory
from tests.unit.test_function_inventory import fixture
from tests.unit.frontends.cpp.support import make_context, span


class FunctionNormalizationTests(unittest.TestCase):
    def fixture(self):
        data=fixture()
        items=inventory(data[0],data[1],data[2],data[3],'fake','cpp',(data[4],))
        return data,items

    def test_range_contract_rejects_malformed_records(self):
        _,(_,fn)=self.fixture()
        self.assertTrue(valid_function(fn))
        self.assertFalse(valid_function(replace(fn,metadata={})))
        self.assertFalse(valid_function(replace(fn,location=None)))
        for key,value in [('declarationBytes',(-1,5)),('nameBytes',(2,1)),('attributes',None),('nestedBytes',None),('attributes',((0,10000),)),('bodyBytes',(0,10000)),('nestedBytes',((0,10000),)),('declarationSpan',(0,)),('bodySpan',None)]:
            with self.subTest(key=key,value=value):
                record={**fn.metadata['function'],key:value}
                self.assertFalse(valid_function(replace(fn,metadata={'function':record})))
        record={**fn.metadata['function'],'bodyBytes':None,'bodySpan':None}
        self.assertTrue(valid_function(replace(fn,metadata={'function':record})))
        record['nestedBytes']=((1,2),)
        self.assertFalse(valid_function(replace(fn,metadata={'function':record})))

    def test_owner_subject_location_configuration_and_type(self):
        _,(attr,fn)=self.fixture()
        functions={fn.id:fn}
        self.assertTrue(valid_owner(attr,functions))
        self.assertTrue(valid_owner(fn,functions))
        for value in (None,(),{},'missing'):
            self.assertFalse(valid_owner(replace(attr,metadata={'functionOwnerEvidenceId':value}),functions))
        for changed in (replace(attr,kind='comment'),replace(attr,subject_id=stable_id('other')),replace(attr,location=None),replace(attr,location=span('other.cpp')),replace(attr,location=span('a.cpp',2)),replace(attr,metadata={**attr.metadata,'compilationContextId':stable_id('other')})):
            self.assertFalse(valid_owner(changed,functions))
        self.assertFalse(valid_owner(attr,{fn.id:replace(fn,location=None)}))

    def test_producer_merge_conflicts_and_normalizer_failure(self):
        data,(attr,fn)=self.fixture()
        second=replace(fn,id=stable_id('another'),producer='other')
        metadata,conflict=merge_metadata((fn,second),fn.metadata)
        self.assertFalse(conflict)
        second=replace(second,metadata={'function':{**fn.metadata['function'],'returnType':'double'}})
        frontend=FrontendSnapshot((Entity(data[3],'source_file','a.cpp'),),(attr,fn,second))
        result=CppEvidenceNormalizer().normalize(make_context(Path('/synthetic')),frontend)
        self.assertEqual(CompletionStatus.PARTIAL,result.status)
        fact=next(f for f in result.value.facts if f.kind=='function_declaration')
        self.assertEqual('unknown',fact.metadata['function']['bindingStatus'])
        self.assertEqual(2,len(fact.metadata['functionProvenance']))
        invalid=replace(fn,metadata={})
        failed=CppEvidenceNormalizer().normalize(make_context(Path('/synthetic')),replace(frontend,evidence=(invalid,)))
        self.assertEqual(CompletionStatus.FAILED,failed.status)
        self.assertEqual('normalization.invalid-function-structure',failed.diagnostics[0].code)
        result=CppEvidenceNormalizer().normalize(make_context(Path('/synthetic')),replace(frontend,evidence=(fn,replace(second,metadata=fn.metadata))))
        self.assertEqual(CompletionStatus.COMPLETE,result.status)
        self.assertEqual(('fake','other'),result.value.facts[0].producers)

    def test_configuration_separation_and_input_immutability(self):
        data,(_,fn)=self.fixture()
        other=replace(fn,id=stable_id('config-other'),metadata={**fn.metadata,'compilationContextId':stable_id('other')})
        frontend=FrontendSnapshot((Entity(data[3],'source_file','a.cpp'),),(fn,other))
        result=CppEvidenceNormalizer().normalize(make_context(Path('/synthetic')),frontend)
        self.assertEqual(2,len(result.value.facts))
        self.assertNotIn('producerConflict',fn.metadata['function'])
