"""Real grammar and report regression; separate from isolated unit coverage."""
import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_application
from kb_scanner.frontends.build.cmake.syntax import parse
from kb_scanner.frontends.build.cmake.project import analyze_project
from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator
from kb_scanner.projection.v2.models import SchemaV2Report


ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/cmake-demo-test1'


class CMakeSourceComponentTests(unittest.TestCase):
    def test_architecture_shaped_filename_is_only_a_candidate(self):
        report,_=self.scan({'CMakeLists.txt':'add_library(v avx.cpp)\n','avx.cpp':'int portable(int a){ return a+1; }\n'})
        self.assertTrue(report['findings'])
        self.assertFalse(any(f['conclusion']['blocking'] for f in report['findings']))
        self.assertTrue(all(f['conclusion']['status']=='unknown' for f in report['findings']))

    def test_x86_machine_metadata_does_not_prove_unknown_target_configuration(self):
        machine={'name':'x86-observed','architecture':'x86_64','targets':[{'name':'v','sources':['v.cpp'],'compile_args':['-mavx2']}]}
        report,_=self.scan({'CMakeLists.txt':'option(USE "choice" ON)\nif(USE)\nadd_library(v v.cpp)\nendif()\n',
                            '.cmake/api/v1/reply/codemodel-v2.json':json.dumps(machine),
                            'v.cpp':'void f() { _mm256_setzero_ps(); }\n'})
        finding=next(f for f in report['findings'] if f['fact']['symbol']=='_mm256_setzero_ps')
        self.assertEqual('high',finding['conclusion']['severity'])
        self.assertFalse(finding['conclusion']['blocking'])
        self.assertNotIn(finding['conclusion']['status'],{'inactive','complete'})

    def test_generic_sibling_is_not_an_x86_target_and_orphan_fatal_not_required(self):
        cmake='if(CMAKE_SYSTEM_PROCESSOR MATCHES "^x86_64$")\nadd_library(v avx.cpp)\ntarget_compile_options(v PRIVATE -mavx2)\nelse()\nadd_library(v generic.cpp)\nendif()\n'
        report,_=self.scan({'CMakeLists.txt':cmake,'avx.cpp':'void f(){ _mm256_setzero_ps(); }\n',
                            'generic.cpp':'int sum(int a,int b){ return a+b; }\n','unused.cmake':'message(FATAL_ERROR no)\n'})
        self.assertFalse(any(f['conclusion']['blocking'] for f in report['findings']))
        finding=next(f for f in report['findings'] if f['fact']['symbol']=='_mm256_setzero_ps')
        self.assertEqual('inactive',finding['conclusion']['status'])

    def test_shared_march_argument_is_not_high_x86_dependency(self):
        report,_=self.scan({'CMakeLists.txt':'add_library(v v.cpp)\ntarget_compile_options(v PRIVATE -march=rv64gc)\n',
                            'v.cpp':'int v;\n'})
        for f in report['findings']:
            if f['fact']['symbol']=='-march=rv64gc':
                self.assertEqual(('medium','unknown',False),(f['conclusion']['severity'],f['conclusion']['status'],f['conclusion']['blocking']))

    def scan(self,files,version='2.0'):
        with tempfile.TemporaryDirectory() as temporary:
            root,output=Path(temporary)/'input',Path(temporary)/'output'
            root.mkdir()
            for name,text in files.items():
                path=root/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(text,encoding='utf-8')
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch('subprocess.run',side_effect=AssertionError('project execution forbidden')):
                result=create_default_application().run(ScanRequest(str(root),str(ROOT/'rulesets/riscv-porting'),str(output),schema_version=version))
            self.assertEqual(0,result.exit_code,result.diagnostics)
            self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})
            self.assertEqual({'scan-result.json','scan-report.html','scan.log'},{p.name for p in output.iterdir()})
            payload=json.loads((output/'scan-result.json').read_text())
            if version=='2.0':
                V2ReferentialIntegrityValidator().validate(SchemaV2Report.model_validate(payload))
            return payload,(output/'scan-report.html').read_text()

    def test_demo_first_source_oracle_and_rejection_chain(self):
        files={str(p.relative_to(FIXTURE)):p.read_text() for p in FIXTURE.rglob('*') if p.is_file()}
        baseline=json.loads((ROOT/'tests/fixtures/cmake-demo-test1-baseline.json').read_text())
        self.assertEqual(set(files),set(baseline['fixtureHashes']))
        for name,hashes in baseline['fixtureHashes'].items():
            data=(FIXTURE/name).read_bytes()
            self.assertTrue(data.endswith(b'\n') and not data.endswith(b'\n\n'),name)
            self.assertEqual(hashes['normalizedSha256'],sha256(data).hexdigest(),name)
            self.assertEqual(hashes['originalSha256'],sha256(data+b'\n').hexdigest(),name)
        report,html=self.scan(files)
        for old in baseline['findings']:
            found=[f for f in report['findings'] if f['fact']['symbol']==old['symbol'] and f['fact']['primaryLocation']['span']['start']['line']==old['location']['start']['line']]
            self.assertEqual(1,len(found),old['symbol'])
            conclusion=found[0]['conclusion']
            if old['symbol']=='__AVX2__':
                self.assertEqual(('medium','unknown'),(conclusion['severity'],conclusion['status']))
            else:
                self.assertEqual(('high','partial'),(conclusion['severity'],conclusion['status']))
            self.assertFalse(conclusion['blocking'])
        blockers=[f for f in report['findings'] if f['conclusion']['blocking']]
        self.assertEqual(1,len(blockers))
        self.assertEqual('FATAL_ERROR',blockers[0]['fact']['symbol'])
        chain=blockers[0]['evidenceChain']
        self.assertEqual('complete',chain['status'])
        primary=[s for s in chain['steps'] if s['id'] in chain['primaryPath']]
        self.assertEqual({7,8},{s['source']['span']['start']['line'] for s in primary})
        self.assertFalse(any(s['kind'] in {'classification','assessment'} for s in chain['steps']))
        self.assertTrue(all(s['source']['context']['highlights'] for s in primary))
        self.assertIn('静态证据',blockers[0]['conclusion']['suggestion'])
        self.assertIn('CMake',html)
        self.assertTrue(any(any(o['location']['file']=='CMakeLists.txt' and o['location']['span']['start']['line']==39 for o in f['occurrences']) for f in report['findings']))

    def test_without_rejection_target_flags_have_complete_selection(self):
        report,_=self.scan({'CMakeLists.txt':'add_library(v v.cpp)\ntarget_compile_options(v PRIVATE -mavx2)\n',
                            'v.cpp':'void f() { _mm256_setzero_ps(); }\n'})
        flag=next(f for f in report['findings'] if f['fact']['symbol']=='-mavx2')
        self.assertTrue(flag['conclusion']['blocking'])
        self.assertEqual('complete',flag['conclusion']['status'])
        dependency=next(f for f in report['findings'] if f['fact']['symbol']=='_mm256_setzero_ps')
        self.assertTrue(dependency['conclusion']['blocking'])

    def test_macro_scope_not_other_target(self):
        source='#if defined(USE_AVX)\nvoid f() { _mm256_setzero_ps(); }\n#endif\n'
        for target in ('v','other'):
            report,_=self.scan({'CMakeLists.txt':f'add_library(v v.cpp)\nadd_library(other other.cpp)\ntarget_compile_definitions({target} PRIVATE USE_AVX=1)\n',
                                'v.cpp':source,'other.cpp':'int other;\n'})
            dependency=next(f for f in report['findings'] if f['fact']['symbol']=='_mm256_setzero_ps')
            steps=dependency['evidenceChain']['steps']
            primary=[s for s in steps if s['id'] in dependency['evidenceChain']['primaryPath']]
            self.assertEqual(target=='v',any(s.get('source',{}).get('file')=='CMakeLists.txt' and 'USE_AVX' in s.get('symbol','') for s in primary))

    def test_unknown_constructs_do_not_make_false_blockers(self):
        cases=['option(OPT "desc" OFF)\nif(OPT)\nmessage(FATAL_ERROR nope)\nendif()\n',
               'function(f)\nmessage(FATAL_ERROR nope)\nendfunction()\n',
               'execute_process(COMMAND touch /tmp/cmake-forbidden)\nif(CMAKE_SYSTEM_PROCESSOR STREQUAL riscv64)\nmessage(FATAL_ERROR nope)\nendif()\n',
               'include(../escape.cmake)\nmessage(FATAL_ERROR nope)\n',
               'if(OFF)\nmessage(FATAL_ERROR nope)\nendif()\n']
        for source in cases:
            report,_=self.scan({'CMakeLists.txt':source,'v.cpp':'int a;\n'})
            self.assertFalse(any(f['conclusion']['blocking'] for f in report['findings']),source)
        self.assertFalse(Path('/tmp/cmake-forbidden').exists())

    def test_native_syntax_positions_comments_and_bad_input(self):
        commands=parse('# fake(FATAL_ERROR)\nset(X [=[中\n文]=])\nif((X STREQUAL other) AND NOT OFF)\nendif()\n')
        self.assertEqual(['set','if','endif'],[c.name for c in commands])
        self.assertEqual((2,3),(commands[0].args[1].line,commands[0].args[1].end_line))
        result=analyze_project({'CMakeLists.txt':'if(broken'},'riscv64')
        self.assertTrue(result['CMakeLists.txt'].partial)

    def test_v1_fields_and_v2_shape_preserved(self):
        files={'CMakeLists.txt':'if(NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^x86_64$")\nmessage(FATAL_ERROR nope)\nendif()\n',
               'v.cpp':'void f() { _mm256_setzero_ps(); }\n'}
        first,_=self.scan(files,'1.0')
        second,_=self.scan(files)
        self.assertEqual('1.0',first['schemaVersion'])
        self.assertEqual('2.0',second['schemaVersion'])
        self.assertEqual(1,sum(f['is_blocking'] for f in first['findings']))
        self.assertEqual(1,sum(f['conclusion']['blocking'] for f in second['findings']))
        for f in second['findings']:
            self.assertRegex(f['conclusion']['suggestion'],r'[\u4e00-\u9fff]')
            self.assertTrue(f['conclusion']['suggestion_en'].isascii())
