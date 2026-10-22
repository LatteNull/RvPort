"""Synthetic grammar nodes; native parsing is only a component test."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from kb_scanner.frontends.cpp.function_inventory import inventory, walk
from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter
from kb_scanner.frontends.cpp.source_positions import SourceByteIndex
from kb_scanner.frontends.cpp.vocabulary import make_evidence
from kb_scanner.core import FrontendSnapshot, Entity, CompletionStatus, stable_id
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from tests.unit.frontends.cpp.test_tree_sitter_adapter import Node
from tests.unit.frontends.cpp.support import make_context


def fixture(attribute='target("default")', parameter='int n', body=True):
    source = ('__attribute__((' + attribute + ')) int f(' + parameter + ')' + ('{return 0;}' if body else ';')).encode()
    attr_end = source.index(b' int f')
    attr = Node('attribute_specifier', 0, attr_end)
    typ_start = attr_end + 1
    typ = Node('primitive_type', typ_start, typ_start+3)
    name_start = source.index(b'f(')
    name = Node('identifier', name_start, name_start+1)
    p_start = name_start+2
    p_type = Node('primitive_type', p_start, p_start+3)
    p_name = Node('identifier', p_start+4, p_start+5)
    param = Node('parameter_declaration', p_start, p_start+len(parameter), children=(p_type,p_name), fields={'type':p_type,'declarator':p_name})
    params = Node('parameter_list', name_start+1, p_start+len(parameter)+1, children=(param,))
    decl = Node('function_declarator', name_start, params.end_byte, children=(name,params), fields={'declarator':name,'parameters':params})
    block = Node('compound_statement', params.end_byte,len(source)) if body else None
    node = Node('function_definition' if body else 'declaration',0,len(source), children=tuple(n for n in (attr,typ,decl,block) if n is not None), fields={'type':typ,'declarator':decl,'body':block})
    root = Node('translation_unit',0,len(source),children=(node,))
    pos = SourceByteIndex.build('a.cpp',source)
    eid = stable_id('file')
    ev = make_evidence(kind='declaration_attribute',subject_id=eid,value=source[:attr_end].decode(),producer='fake',parse_mode='tree_sitter_baseline',confidence='high',span=pos.span(0,attr_end))
    return root,source,pos,eid,ev,node,decl,param


class FunctionInventoryTests(unittest.TestCase):
    def collect(self, data, **kwargs):
        root,source,pos,eid,ev,*_ = data
        return inventory(root,source,pos,eid,'fake','cpp',(ev,),**kwargs)

    def test_owner_binding_and_original_identity(self):
        data = fixture()
        result = self.collect(data)
        self.assertEqual(2,len(result))
        self.assertEqual(data[4].id,result[0].id)
        self.assertEqual(data[4].value,result[0].value)
        self.assertEqual(result[1].id,result[0].metadata['functionOwnerEvidenceId'])
        record = result[1].metadata['function']
        self.assertEqual('f(int)',record['signature'])
        self.assertEqual('complete',record['bindingStatus'])
        self.assertIsNotNone(record['bodyBytes'])
        self.assertEqual('unknown',self.collect(data,errors=((0,1,'ERROR'),))[1].metadata['function']['bindingStatus'])

    def test_declaration_limits_and_non_attribute(self):
        self.assertIsNone(self.collect(fixture(body=False))[1].metadata['function']['bodyBytes'])
        self.assertEqual(1,len(self.collect(fixture(),limit=0)))
        self.assertTrue(self.collect(fixture(),limit=0)[0].metadata['functionInventory']['truncated'])
        self.assertEqual(0,self.collect(fixture(),limit=0)[0].metadata['functionInventory']['retainedDeclarationCount'])
        with self.assertRaises(ValueError):
            self.collect(fixture(),limit=-1)
        self.assertEqual(1,len(self.collect(fixture('no_sanitize("memory")'))))

    def test_budget_type_validation_and_unowned_attributes(self):
        for budget in (True, 1.5, '1'):
            with self.assertRaises(ValueError):
                self.collect(fixture(),limit=budget)
        data=fixture()
        data[6].type='pointer_declarator'
        result=self.collect(data)
        self.assertEqual(1,len(result))
        self.assertEqual('unknown',result[0].metadata['functionInventory']['bindingStatus'])
        self.assertNotIn('functionOwnerEvidenceId',result[0].metadata)

    def test_parameter_attribute_is_not_function_attribute(self):
        data=fixture()
        attr=data[5].children.pop(0)
        data[7].children.append(attr)
        attr.parent=data[7]
        result=self.collect(data)
        self.assertEqual(1,len(result))
        self.assertEqual('unknown',result[0].metadata['functionInventory']['bindingStatus'])

    def test_linkage_nested_exclusions_and_unknown_linkage(self):
        data=fixture()
        linkage=Node('linkage_specification',0,len(data[1]),children=(data[5],))
        data[5].parent=linkage
        linkage.parent=data[0]
        data[0].children=[linkage]
        self.assertEqual('unknown',self.collect(data)[1].metadata['function']['bindingStatus'])
        # Reuse real byte text for the synthetic linkage token, without reading Point.
        start=data[1].index(b'default')
        linkage._fields['value']=Node('string_literal',start,start+7)
        self.assertEqual('default',self.collect(data)[1].metadata['function']['linkage'])
        block=data[5]._fields['body']
        inner=Node('lambda_expression',block.start_byte+1,block.end_byte-1)
        inner.children=[Node('lambda_expression',inner.start_byte+1,inner.end_byte-1)]
        block.children=[Node('expression_statement',inner.start_byte,inner.end_byte,children=(inner,))]
        record=self.collect(data)[1].metadata['function']
        self.assertEqual(((inner.start_byte,inner.end_byte),),record['nestedBytes'])
        self.assertEqual(1,len(record['nestedSpans']))

    def test_malformed_and_complex_parameters_are_unknown(self):
        for mutation in ('missing_type','pointer','variadic','missing_return','missing_parameters'):
            with self.subTest(mutation=mutation):
                data=fixture()
                if mutation=='missing_type': data[7]._fields['type']=None
                if mutation=='pointer': data[7]._fields['declarator'].type='pointer_declarator'
                if mutation=='variadic': data[7].type='variadic_parameter'
                if mutation=='missing_return': data[5]._fields['type']=None
                if mutation=='missing_parameters': data[6]._fields['parameters']=None
                result=self.collect(data)
                if mutation=='missing_parameters': self.assertEqual(1,len(result))
                else: self.assertEqual('unknown',result[1].metadata['function']['bindingStatus'])

    def test_same_name_without_attribute_is_materialized_and_others_are_not(self):
        data=fixture()
        plain=fixture()[5]
        plain.children.pop(0)
        plain.parent=data[0]
        data[0].children.append(plain)
        self.assertEqual(3,len(self.collect(data)))
        plain._fields['declarator']._fields['declarator'].start_byte += 1
        self.assertEqual(2,len(self.collect(data)))
        data=fixture()
        normal=replace(data[4],kind='call_expression',value='external')
        result=inventory(data[0],data[1],data[2],data[3],'fake','cpp',(normal,data[4]))
        self.assertIs(normal,result[0])

    def test_utf8_crlf_bytes_and_adapter_facade(self):
        data=list(fixture())
        prefix='// 中文\r\n'.encode()
        for node in walk(data[0]):
            node.start_byte+=len(prefix)
            node.end_byte+=len(prefix)
        data[1]=prefix+data[1]
        data[2]=SourceByteIndex.build('a.cpp',data[1])
        data[4]=replace(data[4],location=data[2].span(len(prefix),len(prefix)+len(data[4].value)))
        result=self.collect(data)
        self.assertEqual(2,result[1].location.start.line)
        self.assertEqual(2,result[1].metadata['function']['bodySpan'][0])
        grammar=SimpleNamespace(language=lambda: 'fake')
        parser=lambda language: SimpleNamespace(parse=lambda source: SimpleNamespace(root_node=data[0]))
        with patch('kb_scanner.frontends.cpp.tree_sitter_adapter.tree_sitter_cpp',grammar), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Language',lambda value:value), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Parser',parser), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.version',return_value='test'):
            parsed=TreeSitterCppAdapter()._parse_candidate(data[1],'a.cpp',Entity(data[3],'source_file','a.cpp'),'cpp','suffix',False)
        functions=[item for item in parsed.evidence if item.kind=='function_declaration']
        attrs=[item for item in parsed.evidence if item.kind=='declaration_attribute']
        self.assertEqual(1,len(functions))
        self.assertEqual(functions[0].id,attrs[0].metadata['functionOwnerEvidenceId'])

    def test_scope_conditions_and_unsupported_parameters(self):
        data = fixture()
        node = data[5]
        ns = Node('namespace_definition',0,len(data[1]),children=(node,))
        pre = Node('preproc_if',0,len(data[1]),children=(ns,))
        data[0].children = [pre]
        node.parent, ns.parent, pre.parent = ns, pre, data[0]
        param = data[7]
        param._fields['type'].type = 'type_identifier'
        record = self.collect(data)[1].metadata['function']
        self.assertTrue(record['conditional'])
        self.assertTrue(record['signature'].startswith('anonymous@0::'))
        self.assertEqual('unknown',record['bindingStatus'])

    def test_invalid_shape_and_template_are_conservative(self):
        data = fixture()
        data[6]._fields['declarator'] = None
        self.assertEqual(1,len(self.collect(data)))
        data = fixture()
        template = Node('template_declaration',0,len(data[1]),children=(data[5],))
        data[0].children=[template]
        data[5].parent, template.parent = template, data[0]
        self.assertEqual('unknown',self.collect(data)[1].metadata['function']['bindingStatus'])

    def test_normalizer_validates_owner(self):
        data = fixture()
        evidence = self.collect(data)
        frontend = FrontendSnapshot((Entity(data[3],'source_file','a.cpp'),),evidence)
        context=make_context(Path('/synthetic'))
        result=CppEvidenceNormalizer().normalize(context,frontend)
        self.assertEqual(CompletionStatus.COMPLETE,result.status)
        self.assertEqual({'function_declaration','declaration_attribute'},{f.kind for f in result.value.facts})
        invalid=replace(frontend,evidence=(evidence[0],))
        self.assertEqual(CompletionStatus.FAILED,CppEvidenceNormalizer().normalize(context,invalid).status)
