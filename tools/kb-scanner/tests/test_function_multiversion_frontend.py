"""真实 grammar 组件，不能计入隔离单元覆盖率。"""
import unittest
from pathlib import Path
import json
import tempfile

from kb_scanner.core import FrontendSnapshot, CompletionStatus
from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from tests.unit.frontends.cpp.support import make_context
from kb_scanner.analyzers.function_multiversion.grouping import discover, Budget


class MultiversionFrontendComponents(unittest.TestCase):
    def parse(self,source,language='cpp'):
        path='a.cpp' if language=='cpp' else 'a.c'
        entity=make_source_file_entity(path,(language,),'1')
        parsed=TreeSitterCppAdapter()._parse_candidate(source.encode(),path,entity,language,'suffix',False)
        result=CppEvidenceNormalizer().normalize(make_context(Path('/synthetic')),FrontendSnapshot((entity,),parsed.evidence))
        self.assertNotEqual(CompletionStatus.FAILED,result.status)
        return parsed,result.value

    def test_attribute_positions_gnu_standard_and_c(self):
        for language,source in (
            ('cpp','__attribute__((target("avx2"))) int f(int n){return n;}'),
            ('cpp','int f(int n) __attribute__((target("avx2"))) {return n;}'),
            ('cpp','[[gnu::target_clones("avx2","default")]] int f(int n){return n;}'),
            ('c','__attribute__((target_clones("avx2,default"))) int f(void){return 0;}')):
            with self.subTest(source=source):
                parsed,facts=self.parse(source,language)
                function=next(f for f in facts.facts if f.kind=='function_declaration')
                attr=next(e for e in parsed.evidence if e.kind=='declaration_attribute')
                self.assertIn(attr.metadata['functionOwnerEvidenceId'],function.evidence_ids)
                self.assertEqual('complete',function.metadata['function']['bindingStatus'])
                self.assertEqual(1,len([e for e in parsed.evidence if e.kind=='declaration_attribute']))

    def test_scopes_templates_nested_utf8_and_damage(self):
        source='// 中文\r\nnamespace A { __attribute__((target("avx2"))) int f(int n){auto x=[](){return 1;}; return n;} }\nnamespace B { __attribute__((target("default"))) int f(double n){return 0;} }'
        _,facts=self.parse(source)
        functions=[f.metadata['function'] for f in facts.facts if f.kind=='function_declaration']
        self.assertEqual({'A::f(int)','B::f(double)'},{f['signature'] for f in functions})
        self.assertEqual(1,sum(len(f['nestedSpans']) for f in functions))
        _,facts=self.parse('template<class T> __attribute__((target("avx2"))) int f(int n){return n;}')
        self.assertEqual('unknown',next(f for f in facts.facts if f.kind=='function_declaration').metadata['function']['bindingStatus'])
        parsed,_=self.parse('__attribute__((target("avx2"))) int f(int n){return @; }')
        self.assertGreater(parsed.error_count,0)

    def test_extern_c_and_no_attribute_fast_path(self):
        _,facts=self.parse('extern "C" { __attribute__((target("avx2"))) int f(int n){return n;} }')
        self.assertEqual('C',next(f for f in facts.facts if f.kind=='function_declaration').metadata['function']['linkage'])
        parsed,_=self.parse('int f(int n){return n;}')
        self.assertFalse(any(e.kind=='function_declaration' for e in parsed.evidence))

    def test_manual_structural_oracle(self):
        cases=json.loads((Path(__file__).parent/'fixtures/function-multiversion-oracle.json').read_text())['cases']
        for case in cases:
            with self.subTest(case=case['name']):
                _,facts=self.parse(case['source'])
                groups=discover(facts,Budget())['groups']
                if 'groups' in case:
                    self.assertEqual(case['groups'],len(groups))
                if not groups:
                    continue
                for key in ('mechanism','defaultPresence','defaultDefinition','groupCompleteness','targetApplicability','bodyDependency'):
                    if key in case: self.assertEqual(case[key],groups[0][key])
                if 'bodyCount' in case:
                    self.assertEqual(case['bodyCount'],sum(d['record']['bodySpan'] is not None for d in groups[0]['declarations']))

    def test_cli_v2_v1_preserves_intrinsic_and_real_source_chain(self):
        from tests.tree_sitter_native_support import run_scanner_process
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as raw:
            project=Path(raw)/'input'
            project.mkdir()
            code='\n'*22+'__attribute__((target_clones("avx2,default"))) void f(){_mm256_setzero_ps();}\n'+'\n'*22
            (project/'a.cpp').write_text(code)
            for version in ('2.0','1.0'):
                output=Path(raw)/('out-'+version)
                outcome=run_scanner_process(project,root/'rulesets/riscv-porting',output,schema_version=version,timeout_seconds=45)
                self.assertEqual(0,outcome.returncode,outcome)
                payload=json.loads((output/'scan-result.json').read_text())
                self.assertEqual(version,payload['schemaVersion'])
                self.assertEqual({'scan-result.json','scan-report.html','scan.log'},{p.name for p in output.iterdir()})
                if version=='1.0':
                    continue
                namespace='org.rvport.kb-scanner.function-multiversion'
                self.assertIn(namespace,payload['extensions'])
                intrinsic=next(f for f in payload['findings'] if f['fact']['kind']=='intrinsic_call')
                self.assertEqual('high',intrinsic['conclusion']['severity'])
                self.assertEqual(1,len(intrinsic['occurrences']))
                group=intrinsic['fact']['extensions'][namespace]['groups'][0]
                self.assertEqual('confirmed_x86',group['bodyDependency'])
                self.assertEqual('present',group['defaultDefinition'])
                self.assertEqual(2,len(group['versions']))
                steps=intrinsic['evidenceChain']['steps']
                self.assertGreaterEqual(len(steps),3)
                self.assertFalse(any(s['kind'] in {'classification','assessment'} for s in steps))
                context=intrinsic['fact']['primaryLocation']['context']
                self.assertEqual((20,20),(context['budget']['beforeLines'],context['budget']['afterLines']))
                self.assertTrue(intrinsic['conclusion']['suggestion_en'])

    def test_manual_report_fact_and_risk_oracle(self):
        from tests.tree_sitter_native_support import run_scanner_process
        root=Path(__file__).resolve().parents[1]
        oracle=json.loads((root/'tests/fixtures/function-multiversion-oracle.json').read_text())
        for case in oracle['cases']:
            with self.subTest(case=case['name']), tempfile.TemporaryDirectory() as raw:
                project=Path(raw)/'input'
                project.mkdir()
                (project/'a.cpp').write_text(case['source'])
                output=Path(raw)/'out'
                result=run_scanner_process(project,root/'rulesets/riscv-porting',output,timeout_seconds=45)
                self.assertEqual(0,result.returncode,result)
                report=json.loads((output/'scan-result.json').read_text())
                expected=oracle['reportExpectations'][case['name']]
                conclusions=[f['conclusion'] for f in report['findings']]
                kinds=[c['findingType'] for c in conclusions]
                self.assertEqual(expected['multiversionUnknown'],kinds.count('function_multiversion_unknown'))
                self.assertTrue(set(expected['requiredFindingTypes']) <= set(kinds))
                self.assertNotIn(oracle['reportForbidden']['findingType'],kinds)
                for conclusion in conclusions:
                    self.assertFalse(conclusion['blocking'])
                    if conclusion['findingType'] in expected['highTypes']:
                        self.assertEqual('high',conclusion['severity'])
                    if conclusion['findingType']=='function_multiversion_unknown':
                        self.assertEqual('medium',conclusion['severity'])
                if expected['multiversionUnknown']:
                    self.assertNotEqual('ready',report['summary']['readiness'])
