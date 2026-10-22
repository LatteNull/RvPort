import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from kb_scanner.frontends.cpp.macro_records import call_records, event_metadata, clang_call_records
from kb_scanner.frontends.cpp.source_positions import SourceByteIndex
from kb_scanner.frontends.cpp.vocabulary import make_evidence, make_source_file_entity
from tests.unit.frontends.cpp.test_tree_sitter_adapter import Node
from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter


class MacroRecordsTests(unittest.TestCase):
    def test_macro_comment_hash_and_ellipsis_are_not_preprocessor_operators(self):
        from kb_scanner.frontends.cpp.tree_sitter_adapter import _macro_attachments
        source=b'#define SET_LEN 6 /* initial # of structs ... */'
        entity=make_source_file_entity('x.c',('c',),'1')
        positions=SourceByteIndex.build('x.c',source)
        definition=make_evidence(kind='macro_definition',subject_id=entity.id,value='SET_LEN',
                                 producer='fake',parse_mode='fake',confidence='high',span=positions.span(0,len(source)))
        node=Node('preproc_def',0,len(source),fields={'name':Node('identifier',8,15)})
        records,unsupported=_macro_attachments(node,source,'x.c',entity.id,definition,'fake','c','suffix',False,positions)
        self.assertEqual((),unsupported)
        self.assertEqual(['6','/* initial # of structs ... */'],[r.value for r in records])
        self.assertEqual('comment',records[-1].metadata['tokenRole'])
        self.assertFalse(records[-1].metadata['unsupportedSemantics'])

    def test_clang_copies_actual_tokens_positions_context_and_native_failures(self):
        from tests.unit.frontends.cpp.test_clang_adapter import Cursor, Token
        from kb_scanner.frontends.cpp.clang_adapter import _token_span
        entity = make_source_file_entity('x.cpp', ('cpp',), '1')
        positions = SourceByteIndex.build('x.cpp',b'F(x)')
        call = make_evidence(kind='call_expression',subject_id=entity.id,value='F',producer='clang',
            parse_mode='clang_enrichment',confidence='high',span=positions.span(0,4),context_id='ctx')
        tokens = tuple(Token(value,(1,index+1),(1,index+2)) for index,value in enumerate('F(x)'))
        cursor = Cursor(tokens=tokens)
        data, records = clang_call_records(cursor,call,lambda token:_token_span('x.cpp',token))
        self.assertEqual('complete',data['status'])
        self.assertEqual('ctx',records[0].metadata['compilationContextId'])
        self.assertEqual(3,records[0].location.start.column)
        self.assertEqual('macro-token-budget',clang_call_records(cursor,call,lambda t:_token_span('x.cpp',t),token_limit=0)[0]['reason'])
        self.assertEqual('unknown',clang_call_records(Cursor(),call,None)[0]['status'])
        self.assertEqual('unknown',clang_call_records(NS(get_tokens=lambda:(_ for _ in ()).throw(RuntimeError())),call,None)[0]['status'])

    def test_adapter_attaches_call_records_before_native_tree_is_released(self):
        source = b'F(intrinsic)'
        name = Node('identifier', 0, 1)
        arg = Node('identifier', 2, 11)
        args = Node('argument_list', 1, 12, children=(arg,))
        call = Node('call_expression', 0, 12, children=(name,args), fields={'function':name,'arguments':args})
        root = Node('translation_unit', 0, 12, children=(call,))
        entity = make_source_file_entity('x.cpp', ('cpp',), '1')
        with patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Parser', return_value=NS(parse=lambda _:NS(root_node=root))), \
             patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Language'), \
             patch('kb_scanner.frontends.cpp.tree_sitter_adapter.version', return_value='fake'):
            result = TreeSitterCppAdapter()._parse_candidate(source,'x.cpp',entity,'cpp','suffix',False)
        item = next(e for e in result.evidence if e.kind=='call_expression')
        token = next(e for e in result.evidence if e.kind=='macro_argument_token')
        self.assertEqual(item.id,token.metadata['callEvidenceId'])
        self.assertEqual(token.id,item.metadata['macroCall']['arguments'][0][0]['evidenceId'])
        self.assertEqual('intrinsic',token.value)
        self.assertEqual('cpp',token.metadata['language'])
        self.assertEqual('suffix',token.metadata['languageSource'])
        with patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Parser', return_value=NS(parse=lambda _:NS(root_node=root))), \
             patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Language'), \
             patch('kb_scanner.frontends.cpp.tree_sitter_adapter.version', return_value='fake'), \
             patch('kb_scanner.frontends.cpp.tree_sitter_adapter.call_records', return_value=({'reason':'macro-token-budget'},())):
            limited = TreeSitterCppAdapter()._parse_candidate(source,'x.cpp',entity,'cpp','suffix',False)
        self.assertTrue(limited.diagnostics)
        self.assertIn('macro-token-budget',limited.diagnostics[-1].details['semantics'])

    def call(self, text, *, shape='identifier', limit=4096, malformed=False):
        source = text.encode()
        positions = SourceByteIndex.build('x.cpp', source)
        function = Node(shape, 0, 1)
        arguments = Node('argument_list', 1, len(source) - int(malformed))
        node = Node('call_expression', 0, len(source), fields={'function': function, 'arguments': arguments})
        call = make_evidence(kind='call_expression', subject_id=make_source_file_entity('x.cpp', ('cpp',), '1').id,
            value='F', producer='fake', parse_mode='fake', confidence='high', span=positions.span(0, len(source)))
        return call_records(node, source, positions, call, token_limit=limit)

    def test_argument_tokens_are_original_and_empty_call_is_valid(self):
        data, records = self.call('F(intrinsic,(x),42)')
        self.assertEqual('complete', data['status'])
        self.assertEqual(['intrinsic', 'x'], [item.value for item in records])
        self.assertEqual((1, 3, 1, 12), data['arguments'][0][0]['range'])
        self.assertEqual(records[0].id, data['arguments'][0][0]['evidenceId'])
        self.assertEqual((), self.call('F()')[0]['arguments'])
        self.assertEqual('complete', self.call('F(0x10)')[0]['status'])
        self.assertEqual((), self.call('F("_mm256_add_epi32")')[1])
        self.assertEqual(['x'], [r.value for r in self.call('F(/* _mm256_add_epi32 */x)')[1]])

    def test_unsupported_shapes_tokens_balance_and_budgets(self):
        for text in ('F(,)', 'F(x,)', 'F(x + y)', 'F("x")', 'F(G(x,y))', 'F())', 'F((x)'):
            self.assertEqual('unknown', self.call(text)[0]['status'], text)
        self.assertEqual('unknown', self.call('F(' + '(' * 33 + 'x' + ')' * 33 + ')')[0]['status'])
        self.assertEqual('unknown', self.call('F(x)', shape='field_expression')[0]['status'])
        self.assertEqual('malformed-call-arguments', self.call('F(x)', malformed=True)[0]['reason'])
        self.assertEqual('macro-token-budget', self.call('F(x,y)', limit=1)[0]['reason'])
        node = Node('call_expression')
        self.assertEqual('unknown', call_records(node, b'', None, None)[0]['status'])

    def test_branch_records_are_scalar_and_retain_alternative_boundaries(self):
        source = b'#if X\n#elif Y\n#else\n#endif\n'
        positions = SourceByteIndex.build('x.cpp', source)
        root = Node('preproc_if', 0, len(source))
        alternative = Node('preproc_elif', 6, len(source)-7, parent=root)
        tail = Node('preproc_else', 14, len(source)-7, parent=alternative)
        root._fields['alternative'] = alternative
        alternative._fields['alternative'] = tail
        for node in (root, alternative, tail):
            data = event_metadata(node, source, positions)
            self.assertEqual(0, data['preprocessorRegion']['groupStart'])
            self.assertEqual(len(source), data['preprocessorRegion']['groupEnd'])
        self.assertEqual(6, event_metadata(root, source, positions)['preprocessorRegion']['bodyEnd'])
        for kind, expected in (('preproc_def', False), ('preproc_function_def', True)):
            self.assertIs(expected, event_metadata(Node(kind), source, positions)['functionLike'])
        self.assertEqual({'sourceOrder': 0}, event_metadata(Node('identifier'), source, positions))
        pragma = b'#pragma pop_macro("X")\n'
        self.assertTrue(event_metadata(Node('preproc_call',0,len(pragma)),pragma,
                        SourceByteIndex.build('x.cpp',pragma))['unsupportedMacroStateDirective'])

    def test_utf8_prefix_crlf_does_not_shift_argument_source_span(self):
        source = '// 中文\r\nF(x)'.encode()
        start = source.index(b'F(')
        node = Node('call_expression',start,len(source),fields={
            'function':Node('identifier',start,start+1), 'arguments':Node('argument_list',start+1,len(source))})
        positions = SourceByteIndex.build('x.cpp',source)
        item = make_evidence(kind='call_expression',subject_id=make_source_file_entity('x.cpp',('cpp',),'1').id,
            value='F',producer='p',parse_mode='m',confidence='high',span=positions.span(start,len(source)))
        data, records = call_records(node,source,positions,item)
        self.assertEqual((2,3,2,4),data['arguments'][0][0]['range'])
        self.assertEqual(2,records[0].location.start.line)
