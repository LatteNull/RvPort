"""Real parsers and published report oracle, outside isolated unit coverage."""
from pathlib import Path
import unittest

from tests import test_cmake_source_component as cmake_component


class MacroBuildEffectComponentTests(unittest.TestCase):
    def scan(self, files, version='2.0'):
        return cmake_component.CMakeSourceComponentTests().scan(files, version)

    def test_default_cli_v2_and_explicit_v1_publish_bilingual_artifacts(self):
        import json
        import tempfile
        from unittest.mock import patch
        from kb_scanner.cli import main
        root = Path(__file__).parent / 'fixtures/macro-build-effects'
        for folder in ('make','cmake'):
            for version in ('1.0','2.0'):
                with self.subTest(folder=folder,version=version), tempfile.TemporaryDirectory() as temp:
                    args = ['scan','--input',str(root/folder),'--rules',str(root.parents[2]/'rulesets/riscv-porting'),'--output',temp]
                    if version == '1.0':
                        args += ['--schema-version',version]
                    with patch('subprocess.run',side_effect=AssertionError('static only')):
                        self.assertEqual(0,main(args))
                    self.assertEqual({'scan-result.json','scan-report.html','scan.log'},{p.name for p in Path(temp).iterdir()})
                    report = json.loads((Path(temp)/'scan-result.json').read_text())
                    self.assertEqual(version,report['schemaVersion'])
                    self.assertTrue(report['findings'])
                    if version == '2.0':
                        for finding in report['findings']:
                            self.assertTrue(finding['conclusion']['suggestion'])
                            self.assertTrue(finding['conclusion']['suggestion_en'])

    def test_conflicting_cmake_definitions_cannot_certify_selection(self):
        report,_ = self.scan({'CMakeLists.txt':'add_library(a INTERFACE)\ntarget_compile_definitions(a INTERFACE ENABLE=1)\nadd_library(b INTERFACE)\ntarget_compile_definitions(b INTERFACE ENABLE=0)\nadd_library(kernel x.cpp)\ntarget_link_libraries(kernel PRIVATE a b)\n',
                             'x.cpp':'#define F(fn) fn()\n#if ENABLE\nint x=F(_mm256_add_epi32);\n#endif\n'})
        finding = next(f for f in report['findings'] if f['fact']['symbol']=='_mm256_add_epi32')
        self.assertTrue(all(o['selectionStatus']=='unknown' for o in finding['occurrences']))
        self.assertNotEqual('complete',finding['evidenceChain']['status'])

    def test_make_and_cmake_to_nested_macro_terminal_original_source_oracle(self):
        root = Path(__file__).parent / 'fixtures/macro-build-effects'
        for folder in ('make', 'cmake'):
            with self.subTest(folder=folder):
                files = {p.relative_to(root/folder).as_posix(): p.read_text() for p in (root/folder).rglob('*') if p.is_file()}
                report, html = self.scan(files)
                found = [f for f in report['findings'] if f['fact']['symbol'] == '_mm256_add_epi32']
                self.assertEqual(1, len(found))
                finding = found[0]
                self.assertEqual('intrinsic_call', finding['fact']['kind'])
                self.assertEqual('high', finding['conclusion']['severity'])
                self.assertEqual({'line':4, 'column':41}, finding['fact']['primaryLocation']['span']['start'])
                self.assertEqual({'line':4, 'column':57}, finding['fact']['primaryLocation']['span']['end'])
                chain = finding['evidenceChain']
                self.assertEqual('complete', chain['status'])
                symbols = {s.get('symbol') for s in chain['steps']}
                self.assertTrue({'OUTER', 'INNER', 'fn', 'ENABLE', 'defined(USE_AVX2) && ENABLE'}.issubset(symbols))
                source_files = {s['source']['file'] for s in chain['steps'] if s.get('source')}
                self.assertTrue({'kernel.cpp','wrapper.h'}.issubset(source_files))
                self.assertIn('flags.mk' if folder == 'make' else 'CMakeLists.txt', source_files)
                self.assertFalse(any(s['kind'] in {'classification','assessment'} for s in chain['steps']))
                self.assertTrue(finding['conclusion']['suggestion_en'])
                for step in chain['steps']:
                    if step.get('source'):
                        self.assertEqual(20,step['source']['context']['budget']['beforeLines'])
                        self.assertEqual(20,step['source']['context']['budget']['afterLines'])
                        self.assertTrue(step['source']['context']['highlights'])
                self.assertIn('_mm256_add_epi32', html)

    def test_passing_or_ignoring_a_terminal_is_not_a_confirmed_call(self):
        for body in ('value', 'store(fn)', '#fn', 'fn ## value', '0 /* fn(value) */', '"fn(value)"'):
            report, _ = self.scan({'x.cpp':f'#define F(fn,value) {body}\nint x=F(_mm256_add_epi32,1);\n'})
            finding = next(f for f in report['findings'] if f['fact']['symbol']=='_mm256_add_epi32')
            self.assertEqual('unknown', finding['conclusion']['status'])
            self.assertFalse(finding['conclusion']['blocking'])

    def test_two_calls_do_not_borrow_each_others_actual_argument(self):
        report, _ = self.scan({'x.cpp':'#define F(fn,value) fn(value)\nint a=F(_mm256_add_epi32,1);\nint b=F(_mm256_sub_epi32,2);\n'})
        for symbol, other in (('_mm256_add_epi32','_mm256_sub_epi32'),('_mm256_sub_epi32','_mm256_add_epi32')):
            finding = next(f for f in report['findings'] if f['fact']['symbol']==symbol)
            self.assertEqual('high',finding['conclusion']['severity'])
            self.assertNotIn(other, {s.get('symbol') for s in finding['evidenceChain']['steps']})

    def test_inactive_and_ordinary_function_arguments_remain_unproven(self):
        for source in ('int f(){return ordinary(_mm256_add_epi32);}',
                       '#define F(fn) fn()\n#if 0\nint x=F(_mm256_add_epi32);\n#endif\n'):
            report, _ = self.scan({'x.cpp':source})
            finding = next(f for f in report['findings'] if f['fact']['symbol']=='_mm256_add_epi32')
            self.assertEqual('unknown',finding['conclusion']['status'])

    def test_shared_header_retains_opposite_translation_unit_occurrences(self):
        files = {'Makefile':'one.o: one.cpp\n\tc++ -DUSE=1 -c $<\ntwo.o: two.cpp\n\tc++ -UUSE -c $<\n',
                 'one.cpp':'#include "shared.h"\n','two.cpp':'#include "shared.h"\n',
                 'shared.h':'#define F(fn) fn()\n#if defined(USE)\nint x=F(_mm256_add_epi32);\n#endif\n'}
        report, _ = self.scan(files)
        finding = next(f for f in report['findings'] if f['fact']['symbol']=='_mm256_add_epi32')
        self.assertEqual({'selected','inactive'},{o['selectionStatus'] for o in finding['occurrences']})
        self.assertEqual(2,len(finding['occurrences']))
        self.assertEqual(2,len({o['configuration'] for o in finding['occurrences']}))
        self.assertEqual('ambiguous',finding['evidenceChain']['status'])
        self.assertTrue(any(b['reasonCode']=='configuration_conflict' for b in finding['evidenceChain']['breaks']))

    def test_many_translation_units_keep_each_primary_path_complete_and_local(self):
        files = {'shared.h':'#define INNER(fn,value) fn(value)\n#define OUTER(fn,value) INNER(fn,value)\n'}
        files['Makefile']=''.join(f'unit{i}.o: unit{i}.cpp\n\tc++ -DENABLE=1 -c $< -o $@\n' for i in range(16))
        for i in range(16):
            files[f'unit{i}.cpp']='#include "shared.h"\n#if ENABLE\nint f(){return OUTER(_mm256_add_epi32,0);}\n#endif\n'
        report,_=self.scan(files)
        found=[f for f in report['findings'] if f['fact']['symbol']=='_mm256_add_epi32']
        self.assertEqual(16,len(found))
        for finding in found:
            chain=finding['evidenceChain']
            self.assertEqual('complete',chain['status'],chain['breaks'])
            steps={s['id']:s for s in chain['steps']}
            self.assertEqual('Makefile',steps[chain['primaryPath'][0]]['source']['file'])
            self.assertTrue({s['source']['file'] for s in chain['steps'] if s.get('source')} <=
                            {'Makefile','shared.h',finding['fact']['primaryLocation']['file']})
