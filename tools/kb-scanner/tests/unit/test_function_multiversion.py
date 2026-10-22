"""纯数据多版本语义测试；不加载原生 parser 或执行项目。"""
from dataclasses import replace
from pathlib import Path
import unittest

from kb_scanner.core import Entity, FrontendSnapshot, NormalizedSnapshot, stable_id
from kb_scanner.frontends.cpp.function_inventory import inventory, walk
from kb_scanner.frontends.cpp.source_positions import SourceByteIndex
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from kb_scanner.analyzers.function_multiversion.attributes import decode, CompilerProfile, semantic_rule
from kb_scanner.analyzers.function_multiversion.grouping import Budget, discover, source
from tests.unit.test_function_inventory import fixture
from tests.unit.frontends.cpp.test_tree_sitter_adapter import Node
from tests.unit.frontends.cpp.support import make_context


PROFILE = CompilerProfile('clang','18.1.8','cpp','x86_64','trusted-test-profile')


def snapshot(specs, *, path='a.cpp', configuration=None):
    """spec: attribute, parameter, body, conditional; all nodes have coherent parents."""
    nodes, attrs, chunks = [], [], []
    offset=0
    eid=stable_id('test-file',path)
    for attribute, parameter, body, conditional in specs:
        data=fixture(attribute or 'target("default")',parameter,body)
        node=data[5]
        if attribute is None:
            node.children.pop(0)
        for child in walk(node):
            child.start_byte+=offset
            child.end_byte+=offset
        node.parent=None
        if conditional:
            node=Node('preproc_if',node.start_byte,node.end_byte,children=(node,))
        nodes.append(node)
        if attribute is not None:
            attrs.append((offset,len(data[4].value),data[4].value))
        chunks.append(data[1]+b'\n')
        offset+=len(chunks[-1])
    raw=b''.join(chunks)
    positions=SourceByteIndex.build(path,raw)
    root=Node('translation_unit',0,len(raw),children=nodes)
    from kb_scanner.frontends.cpp.vocabulary import make_evidence
    evidence=tuple(make_evidence(kind='declaration_attribute',subject_id=eid,value=value,producer='fake',
        parse_mode='tree_sitter_baseline',confidence='high',span=positions.span(start,start+length))
        for start,length,value in attrs)
    evidence=inventory(root,raw,positions,eid,'fake','cpp',evidence)
    if configuration:
        # Metadata changes alone must not change baseline owner references.
        evidence=tuple(replace(item,metadata={**item.metadata,'compilationContextId':configuration}) for item in evidence)
    frontend=FrontendSnapshot((Entity(eid,'source_file',path),),evidence)
    result=CppEvidenceNormalizer().normalize(make_context(Path('/synthetic')),frontend)
    if result.value is None:
        raise AssertionError(result.diagnostics)
    return result.value


def spec(attribute='target("avx2")', parameter='int n', body=True, conditional=False):
    return attribute,parameter,body,conditional


class AttributeTests(unittest.TestCase):
    def test_literals_and_exact_default(self):
        for value in ('__attribute__((target_clones("avx2,default")))','[[gnu::target_clones("avx2", "def" "ault")]]','__target_clones__("avx2", "default")'):
            self.assertEqual(('avx2','default'),decode(value)['options'])
            self.assertEqual('complete',decode(value)['status'])
        self.assertEqual(('avx2,sse4.2',),decode('target("sse4.2,avx2")')['options'])
        self.assertEqual(('defaultish',),decode('target("defaultish")')['options'])
        self.assertEqual(('a"b',),decode('target("a\\"b")')['options'])
        self.assertEqual('unknown',decode('target("default,avx2")')['status'])

    def test_malformed_foreign_unsupported_and_budgets(self):
        for value in (None,'','target()', 'target("a",)', 'target(,"a")', 'target("a",,"b")',
                      'target("a"','target(FEATURES)','target("\\x61")','target("")',
                      'target("a") target("b")','[[vendor::target("a")]]','target_version("sve")','cpu_dispatch(ivybridge)'):
            with self.subTest(value=value): self.assertEqual('unknown',decode(value)['status'])
        self.assertEqual('multiversion-budget-exceeded',decode('target("a")',max_chars=0)['reason'])
        self.assertEqual('multiversion-budget-exceeded',decode('target_clones("a,b")',max_options=1)['reason'])
        with self.assertRaises(ValueError): decode('',max_chars=-1)

    def test_profile_is_not_inferred_and_is_versioned(self):
        self.assertEqual('unknown',semantic_rule(None,'target')['status'])
        for profile in (replace(PROFILE,family='gcc'),replace(PROFILE,version='19.1'),replace(PROFILE,language='c',source_target='aarch64'),replace(PROFILE,provenance=''),replace(PROFILE,language='c'),replace(PROFILE,source_target='riscv64')):
            self.assertEqual('unknown',semantic_rule(profile,'target')['status'])
        self.assertEqual('unknown',semantic_rule(PROFILE,'single_target')['status'])
        self.assertTrue(semantic_rule(PROFILE,'target')['requiresDefault'])
        self.assertEqual('applicable',semantic_rule(replace(PROFILE,language='c'),'target_clones')['status'])
        self.assertEqual('unknown',semantic_rule(PROFILE,'target_clones')['targetApplicability'])


class GroupingTests(unittest.TestCase):
    def groups(self, specs, **kwargs):
        return discover(snapshot(specs),Budget(),**kwargs)['groups']

    def test_single_target_no_missing_default_and_explicit_default(self):
        group=self.groups([spec()])[0]
        self.assertEqual(('single_target','not_applicable',False),(group['mechanism'],group['defaultPresence'],group['defaultGap']))
        default=self.groups([spec('target("default")')])[0]
        self.assertEqual(('present','present'),(default['defaultPresence'],default['defaultDefinition']))

    def test_multi_definitions_declarations_and_shared_clone_body(self):
        group=self.groups([spec(),spec('target("default")',body=False)])[0]
        self.assertEqual(('target','present','declaration_only'),(group['mechanism'],group['defaultPresence'],group['defaultDefinition']))
        self.assertEqual(2,len(group['versions']))
        group=self.groups([spec('target_clones("avx2,default")')])[0]
        self.assertEqual(1,len(group['declarations']))
        self.assertEqual(2,len(group['versions']))
        self.assertEqual(group['versions'][0]['bodySpan'],group['versions'][1]['bodySpan'])
        self.assertEqual(1,len(group['evidenceIds']))

    def test_unknown_profile_does_not_prove_absence(self):
        specs=[spec('target_clones("avx2,sse4.2")')]
        group=self.groups(specs)[0]
        self.assertEqual('unknown',group['defaultPresence'])
        self.assertFalse(group['defaultGap'])
        group=self.groups(specs,profiles={'source-unconfigured':PROFILE})[0]
        self.assertEqual('absent_in_scope',group['defaultPresence'])
        self.assertTrue(group['defaultGap'])
        self.assertEqual('unknown',group['targetApplicability'])

    def test_overloads_conditions_aliases_and_nonliteral(self):
        self.assertEqual(2,len(self.groups([spec(),spec('target("default")','double n')])))
        group=self.groups([spec(),spec('target("default")',conditional=True)])[0]
        self.assertEqual(('unknown','unknown'),(group['groupCompleteness'],group['defaultPresence']))
        group=self.groups([spec('target_clones(FEATURES)')])[0]
        self.assertEqual('unknown',group['defaultPresence'])
        self.assertIn('multiversion-nonliteral-attribute',group['reasonCodes'])

    def test_order_configuration_path_and_input_immutability(self):
        facts=snapshot([spec(),spec('target("default")')])
        first=discover(facts,Budget())
        self.assertEqual(first,discover(replace(facts,facts=tuple(reversed(facts.facts)),evidence=tuple(reversed(facts.evidence))),Budget()))
        other=snapshot([spec(),spec('target("default")')],path='other.cpp')
        self.assertNotEqual(first['groups'][0]['id'],discover(other,Budget())['groups'][0]['id'])
        configured=snapshot([spec(),spec('target("default")')],configuration=stable_id('config'))
        self.assertNotEqual(first['groups'][0]['id'],discover(configured,Budget())['groups'][0]['id'])
        self.assertTrue(all('defaultPresence' not in f.metadata for f in facts.facts))

    def test_budgets_zero_and_orphan_attributes(self):
        facts=snapshot([spec('target_clones("avx2,default")')])
        for budget in (Budget(groups=0),Budget(declarations=0),Budget(versions=0)):
            result=discover(facts,budget)
            self.assertFalse(any(g['defaultGap'] for g in result['groups']))
        self.assertEqual([],discover(facts,Budget(groups=0))['groups'])
        orphan=replace(facts,facts=tuple(f for f in facts.facts if f.kind=='declaration_attribute'))
        self.assertEqual('unknown',discover(orphan,Budget())['groups'][0]['groupCompleteness'])
        with self.assertRaises(ValueError): Budget(groups=True)
        self.assertIsNone(source(replace(facts.evidence[0],location=None)))

    def test_unrelated_and_return_type_conflict(self):
        facts=snapshot([spec('target("avx2")'),spec('target("default")')])
        altered=[]
        changed=False
        for fact in facts.facts:
            if fact.kind=='function_declaration' and not changed:
                fact=replace(fact,metadata={**fact.metadata,'function':{**fact.metadata['function'],'returnType':'double'}})
                changed=True
            altered.append(fact)
        self.assertEqual('unknown',discover(replace(facts,facts=tuple(altered)),Budget())['groups'][0]['groupCompleteness'])
        self.assertEqual([],discover(NormalizedSnapshot((),(),()),Budget())['groups'])

    def test_semantic_hints_are_configured_and_conflicts_do_not_override_baseline(self):
        from kb_scanner.core import NormalizedFact
        facts=snapshot([spec('target_clones("avx2,sse4.2")')])
        fn=next(f for f in facts.facts if f.kind=='function_declaration')
        original=next(e for e in facts.evidence if e.id in fn.evidence_ids)
        config=stable_id('config')
        def hint(label, key, contexts=(config,)):
            record={'bindingStatus':'complete' if key else 'unknown','canonicalKey':key,'signature':'int (int)','definitionLocation':{'path':'other.cpp','line':1,'column':1}}
            ev=replace(original,id=stable_id(label),kind='function_semantics',metadata={'functionSemantics':record})
            fact=NormalizedFact(stable_id('fact',label),'function_semantics',fn.subject_id,'f',label,(ev.id,),context_ids=contexts,metadata={'functionSemantics':record})
            return ev,fact
        ev,semantic=hint('one',stable_id('canonical'))
        enriched=replace(facts,evidence=(*facts.evidence,ev),facts=(*facts.facts,semantic))
        group=discover(enriched,Budget())['groups'][0]
        self.assertEqual(1,len(group['semanticBindings']))
        self.assertEqual('other.cpp',group['semanticBindings'][0]['definitionLocation']['path'])
        bad_ev,bad_fact=hint('two',None)
        conflicted=replace(enriched,evidence=(*enriched.evidence,bad_ev),facts=(*enriched.facts,bad_fact))
        group=discover(conflicted,Budget(),{'source-unconfigured':PROFILE})['groups'][0]
        self.assertEqual('unknown',group['defaultPresence'])
        self.assertFalse(group['defaultGap'])
        self.assertIn('multiversion-semantic-binding-ambiguous',group['reasonCodes'])
        ev,semantic=hint('none',None,())
        self.assertEqual([],discover(replace(facts,evidence=(*facts.evidence,ev),facts=(*facts.facts,semantic)),Budget())['groups'][0]['semanticBindings'])
        self.assertEqual('unknown',discover(conflicted,Budget(declarations=1))['groups'][0]['groupCompleteness'])

    def test_unattributed_members_and_unrelated_attributes_stay_conservative(self):
        group=self.groups([spec(),spec(None)])[0]
        self.assertIn('multiversion-unclassified-declaration',group['reasonCodes'])
        facts=snapshot([spec()])
        ev=next(e for e in facts.evidence if e.kind=='declaration_attribute')
        attr=next(f for f in facts.facts if f.kind=='declaration_attribute')
        from kb_scanner.core import NormalizedFact
        unrelated=replace(ev,id=stable_id('unrelated'),value='no_sanitize("memory")',metadata={})
        uf=NormalizedFact(stable_id('unrelated-fact'),'declaration_attribute',ev.subject_id,unrelated.value,'unrelated',(unrelated.id,))
        mixed=replace(facts,evidence=(*facts.evidence,unrelated),facts=(*facts.facts,uf))
        self.assertEqual(1,len(discover(mixed,Budget())['groups']))
