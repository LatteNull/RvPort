"""Optional libclang enrichment tested without loading libclang."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

from kb_scanner.core import CompilationUnitContext, StageResult, WorkspaceSnapshot
from kb_scanner.frontends.cpp.function_semantics import function_semantics
from kb_scanner.frontends.cpp.frontend import CppFrontend
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from tests.unit.frontends.cpp.support import make_context
from tests.unit.frontends.cpp.test_frontend import FakeTree
from tests.unit.test_function_inventory import fixture
from kb_scanner.frontends.cpp.function_inventory import inventory


def cursor(root, path='a.cpp', line=1, column=39):
    item=NS(kind=NS(name='FUNCTION_DECL'),location=NS(file=root/path,line=line,column=column),spelling='f')
    item.canonical=item
    item.type=NS(get_canonical=lambda: NS(spelling='int (int)'))
    item.get_definition=lambda:item
    return item


class FunctionSemanticsTests(unittest.TestCase):
    def fixture(self):
        root=Path('/synthetic').resolve()
        entities={'a.cpp':make_source_file_entity('a.cpp',('cpp',),'1')}
        return root,entities,{'a.cpp':{(1,39)}}

    def test_normalized_identity_configuration_and_definition(self):
        root,entities,targets=self.fixture()
        item=cursor(root)
        first=function_semantics(item,root,entities,targets,'ctx1','fake',False)
        self.assertEqual('complete',first.metadata['functionSemantics']['bindingStatus'])
        self.assertEqual('a.cpp',first.metadata['functionSemantics']['definitionLocation']['path'])
        self.assertEqual('unknown',first.metadata['functionSemantics']['compilerProfile'])
        second=function_semantics(item,root,entities,targets,'ctx2','fake',False)
        self.assertNotEqual(first.id,second.id)
        moved=Path('/relocated').resolve()
        third=function_semantics(cursor(moved),moved,entities,targets,'ctx1','fake',False)
        self.assertEqual(first.id,third.id)
        self.assertEqual(first.metadata,third.metadata)
        item.get_definition=lambda:cursor(root,'hidden.h')
        missing=function_semantics(item,root,entities,targets,'ctx1','fake',False)
        self.assertEqual('unknown',missing.metadata['functionSemantics']['definitionStatus'])
        item.get_definition=lambda:None
        self.assertIsNone(function_semantics(item,root,entities,targets,'ctx1','fake',False).metadata['functionSemantics']['definitionLocation'])

    def test_filtering_and_optional_failures(self):
        root,entities,targets=self.fixture()
        for path,line,column in [('a.cpp',0,39),('a.cpp',1,0),('a.cpp',1,40),('missing.h',1,39),('../outside.cpp',1,39)]:
            self.assertIsNone(function_semantics(cursor(root,path,line,column),root,entities,targets,'ctx','fake',False))
        item=cursor(root)
        item.location.file=None
        self.assertIsNone(function_semantics(item,root,entities,targets,'ctx','fake',False))
        self.assertIsNone(function_semantics(cursor(root),root,entities,{},'ctx','fake',False))
        item.kind.name='CXX_METHOD'
        self.assertIsNone(function_semantics(item,root,entities,targets,'ctx','fake',False))
        item=cursor(root)
        for parse_error in (True,False):
            if not parse_error: del item.canonical
            self.assertEqual('unknown',function_semantics(item,root,entities,targets,'ctx','fake',parse_error).metadata['functionSemantics']['bindingStatus'])
        item=cursor(root)
        item.canonical=cursor(root,'../outside.cpp')
        self.assertIsNone(function_semantics(item,root,entities,targets,'ctx','fake',False).metadata['functionSemantics']['canonicalKey'])
        item.type=NS(get_canonical=lambda:NS(spelling=''))
        item.canonical=item
        self.assertEqual('unknown',function_semantics(item,root,entities,targets,'ctx','fake',False).metadata['functionSemantics']['bindingStatus'])

    def test_frontend_passes_only_related_name_positions(self):
        data=fixture()
        entity=make_source_file_entity('a.cpp',('cpp',),'0.1.0')
        evidence=inventory(data[0],data[1],data[2],entity.id,'fake','cpp',(replace(data[4],subject_id=entity.id),))
        calls=[]
        class Clang:
            def enrich(self,context,workspace,unit,entities,function_targets):
                calls.append(function_targets)
                return StageResult(())
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            context=make_context(root,compile_contexts=(CompilationUnitContext(root/'a.cpp'),))
            result=CppFrontend(FakeTree([StageResult(evidence)]),Clang()).analyze(context,WorkspaceSnapshot(root,('a.cpp',)))
        self.assertEqual(evidence[1].location.start.column,next(iter(calls[0]['a.cpp']))[1])
        self.assertEqual(2,len(result.value.evidence))
