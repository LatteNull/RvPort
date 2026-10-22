"""受影响 Clang adapter 的隔离边界和历史分支覆盖。"""
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import patch

from kb_scanner.core import CompilationUnitContext, WorkspaceSnapshot, stable_id
from kb_scanner.frontends.cpp.clang_adapter import ClangCppAdapter, _cursor_kind, _enum_cursor_metadata, _macro_attachments, _clang_macro_token_role, _load_cindex
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity, make_evidence
from tests.unit.frontends.cpp.test_clang_adapter import Cursor, TranslationUnit, FakeCIndex, Token
from tests.unit.frontends.cpp.support import make_context, span


class FunctionClangContractTests(unittest.TestCase):
    def test_scalar_functions_and_enum_cursor_provenance(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            entity=make_source_file_entity('a.cpp',('cpp',),'1')
            enum=Cursor('ENUM_DECL',file=root/'a.cpp',spelling='Mode')
            enum.get_usr=lambda:'enum'
            member=Cursor('ENUM_CONSTANT_DECL',file=root/'a.cpp',spelling='avx2',start=(2,1),end=(2,5))
            member.get_usr=lambda:'member'
            member.semantic_parent=enum
            use=Cursor('DECL_REF_EXPR',file=root/'a.cpp',spelling='avx2',start=(3,1),end=(3,5))
            use.referenced=member
            fn=Cursor('FUNCTION_DECL',file=root/'a.cpp',spelling='f',start=(4,1),end=(4,2))
            fn.canonical=fn
            fn.type=NS(get_canonical=lambda:NS(spelling='int ()'))
            fn.get_definition=lambda:fn
            excluded=Cursor('CALL_EXPR',file=root/'excluded.h')
            fake=FakeCIndex(TranslationUnit(Cursor('ROOT',children=(enum,member,use,fn,excluded))))
            result=ClangCppAdapter(lambda:fake).enrich(make_context(root),WorkspaceSnapshot(root,('a.cpp',)),CompilationUnitContext(root/'a.cpp',tokens=('clang++','a.cpp')),{'a.cpp':entity},function_targets={'a.cpp':{(4,1)}})
        kinds={item.kind:item for item in result.value}
        self.assertEqual('complete',kinds['function_semantics'].metadata['functionSemantics']['bindingStatus'])
        self.assertEqual(kinds['enum_declaration'].id,kinds['enum_member_declaration'].metadata['enumDeclarationEvidenceId'])
        self.assertEqual((kinds['enum_member_declaration'].id,),kinds['enum_member_reference'].metadata['enumMemberDeclarationEvidenceIds'])
        self.assertEqual('Mode::avx2',kinds['enum_member_reference'].metadata['qualifiedName'])

    def test_partial_unknown_enum_and_non_enum_reference(self):
        item=Cursor('ENUM_DECL',spelling='E')
        self.assertEqual('partial',_enum_cursor_metadata(item,'enum_declaration',{}, {},True)['bindingStatus'])
        item=Cursor('DECL_REF_EXPR',spelling='value')
        self.assertEqual('unknown',_enum_cursor_metadata(item,'enum_member_reference',{}, {},False)['bindingStatus'])
        item.referenced=Cursor('VAR_DECL')
        self.assertIsNone(_cursor_kind(item))
        member=Cursor('ENUM_CONSTANT_DECL',spelling='value')
        self.assertEqual('partial',_enum_cursor_metadata(member,'enum_member_declaration',{}, {},False)['bindingStatus'])
        item.referenced=member
        self.assertEqual('partial',_enum_cursor_metadata(item,'enum_member_reference',{}, {},False)['bindingStatus'])
        self.assertEqual('value',_enum_cursor_metadata(item,'enum_member_reference',{}, {},False)['qualifiedName'])

    def test_macro_error_and_token_boundaries(self):
        eid=stable_id('file')
        definition=make_evidence(kind='macro_definition',subject_id=eid,value='M',producer='fake',parse_mode='clang_enrichment',confidence='high',span=span())
        def attachments(cursor): return _macro_attachments(cursor,'a.cpp',eid,definition,stable_id('context'),0,False)
        self.assertEqual(((),()),attachments(NS()))
        malformed=Cursor('MACRO_DEFINITION',tokens=(Token('M',(1,1),(1,2)),Token('(',(1,2),(1,3))))
        self.assertEqual(('unparseable-parameters',),attachments(malformed)[1])
        macro=Cursor('MACRO_DEFINITION',tokens=tuple(Token(t,(1,i+1),(1,i+2)) for i,t in enumerate(('M','#','x','##','y','7','"s"'))))
        values,unsupported=attachments(macro)
        self.assertEqual({'stringification','token-pasting'},set(unsupported))
        self.assertEqual(6,len(values))
        self.assertEqual('number',_clang_macro_token_role('7',None,set()))
        self.assertEqual('string',_clang_macro_token_role('"s"',None,set()))
        with patch.dict('sys.modules',{'clang':NS(cindex='fake')}):
            self.assertEqual('fake',_load_cindex())
