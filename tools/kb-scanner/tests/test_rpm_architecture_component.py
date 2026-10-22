"""Real grammar/components and manual oracle; excluded from isolated coverage."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from kb_scanner.core import ScanRequest
from kb_scanner.frontends.build.adapters import parse_rpm
from kb_scanner.pipeline.default import create_default_application
from tests.schema_v2_contract import reference_errors

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/rpm-architecture'
RULES = ROOT / 'rulesets/riscv-porting'


class RpmArchitectureComponentTests(unittest.TestCase):
    def test_html_escapes_spec_payload(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as out:
            token = 'lib(x86-64)<script>RPM_UNSAFE</script>'
            (Path(project)/'<rpm&>.spec').write_text('Requires: '+token+'\n')
            result = create_default_application().run(ScanRequest(project,str(RULES),out))
            self.assertEqual(0,result.exit_code)
            html = (Path(out)/'scan-report.html').read_text()
            self.assertNotIn('<script>RPM_UNSAFE</script>',html)
            self.assertIn('&lt;rpm&amp;&gt;.spec:1',html)
            report = json.loads((Path(out)/'scan-result.json').read_text())
            self.assertEqual(token,report['findings'][0]['fact']['symbol'])

    def test_manual_frontend_oracle_and_original_positions(self):
        source = (FIXTURE / 'demo.spec').read_text()
        oracle = json.loads((FIXTURE / 'oracle.json').read_text())
        result = parse_rpm(source, 'demo.spec', oracle['target'])
        selected = [r for r in result.records if r.kind in {'build_dependency', 'build_argument'}]
        actual = [(r.line, r.kind, r.value, r.metadata['selectionStatus']) for r in selected]
        expected = [(r['line'], r['kind'], r['value'], r['selection']) for r in oracle['occurrences']]
        self.assertEqual(expected, actual)
        for item, wanted in zip(selected, oracle['occurrences']):
            self.assertEqual(item.value, source.splitlines()[item.line-1][item.start_column-1:item.end_column-1])
            for key in ('targetAdaptive', 'softDependency'):
                if key in wanted:
                    self.assertEqual(wanted[key], item.metadata['rpm'][key])

    def test_default_v2_explicit_v1_and_immutable_facts(self):
        oracle = json.loads((FIXTURE / 'oracle.json').read_text())
        payloads = []
        for version in (None, '2.0', '1.0'):
            with tempfile.TemporaryDirectory() as out:
                result = create_default_application().run(ScanRequest(str(FIXTURE), str(RULES), out,
                    **({} if version is None else {'schema_version':version})))
                self.assertEqual(0, result.exit_code, result.diagnostics)
                self.assertEqual({'scan-result.json', 'scan-report.html', 'scan.log'}, {p.name for p in Path(out).iterdir()})
                payloads.append(json.loads((Path(out)/'scan-result.json').read_text()))
        self.assertEqual(payloads[0], payloads[1])
        self.assertEqual('1.0', payloads[2]['schemaVersion'])
        v2 = payloads[0]
        schema = json.loads((ROOT/'schemas/scan-result-v2.schema.json').read_text())
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(v2)))
        self.assertEqual([], reference_errors(v2))
        findings = {f['fact']['symbol']:f for f in v2['findings']}
        self.assertEqual({'x86-only', '-mavx', 'liboptional(x86-64)', *oracle['unknown']}, set(findings))
        for name in oracle['notFindings']:
            self.assertNotIn(name, findings)
        for name in oracle['notBlocking']:
            self.assertFalse(findings[name]['conclusion']['blocking'])
        for name in oracle['unknown']:
            self.assertEqual('unknown', findings[name]['conclusion']['status'])
            self.assertTrue(findings[name]['evidenceChain']['breaks'])
        for name, digest in {'clang':'adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7',
                             'gcc':'22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191'}.items():
            self.assertEqual(digest, hashlib.sha256((RULES/f'generated/{name}-x86-entries.json').read_bytes()).hexdigest())

    def test_real_shell_first_match_and_unicode_crlf(self):
        multiline='%build\nCFLAGS="-mavx\n  -msse %{_arch}"\n'
        multi=parse_rpm(multiline,'multiline.spec','riscv64').records
        self.assertEqual([('-mavx',2,9),('-msse',3,3)],[(r.value,r.line,r.start_column) for r in multi if r.kind=='build_argument'])
        for item in multi:
            self.assertEqual(item.value,multiline.splitlines()[item.line-1][item.start_column-1:item.end_column-1])
        source = '%global machine %(uname -m)\r\n%build\r\n# 中文\r\nmachine="$(uname -m)"\r\nif [ "$machine" = x86_64 ]; then\r\n CFLAGS=-mavx\r\nelif [ "`uname -m`" = riscv64 ]; then\r\n CFLAGS=-O2\r\nelse\r\n CFLAGS=-msse\r\nfi\r\n'
        records = parse_rpm(source,'unicode.spec','riscv64').records
        self.assertEqual([('-mavx','inactive'),('-O2','selected'),('-msse','inactive')],
                         [(r.value,r.metadata['selectionStatus']) for r in records if r.kind=='build_argument'])
        for r in records:
            self.assertEqual(r.value,source.splitlines()[r.line-1][r.start_column-1:r.end_column-1])

    def test_unknown_commands_here_document_and_hostile_macros_never_execute(self):
        source = '%global bad %(touch /tmp/RPM-MUST-NOT-EXIST)\n%{lua:os.execute("touch /tmp/RPM-MUST-NOT-EXIST")}\n%include /etc/passwd\nRequires: lib%{_arch}\n%build\ncat <<EOF\nCFLAGS=-mavx\nEOF\nmachine=$(uname -m | touch /tmp/RPM-MUST-NOT-EXIST)\nif [ "$machine" = x86_64 ]; then\n CFLAGS=-msse\nfi\n'
        import builtins
        with patch('subprocess.Popen', side_effect=AssertionError('project process forbidden')), \
             patch.object(builtins, 'open', side_effect=AssertionError('project/include read forbidden')):
            result = parse_rpm(source,'hostile.spec','riscv64')
        self.assertTrue(result.partial)
        self.assertFalse(Path('/tmp/RPM-MUST-NOT-EXIST').exists())
        flags = [r for r in result.records if r.kind=='build_argument']
        self.assertEqual(['-msse'], [r.value for r in flags])
        self.assertEqual('unknown', flags[0].metadata['selectionStatus'])

    def test_packages_groups_fixed_isa_and_optional_optimization(self):
        source = '%if 0\nExclusiveArch: x86_64\n%endif\n%package one\nRequires: same(x86-64)\n%package two\n%ifarch x86_64\nRequires: same(x86-64)\n%endif\n%build\ncase $(uname -m) in\nx86_64) CFLAGS=-mavx ;;\nesac\n'
        result = parse_rpm(source,'packages.spec','riscv64')
        deps = [r for r in result.records if r.kind=='build_dependency']
        self.assertEqual([('one','selected'),('two','inactive')],[(r.metadata['rpm']['package'],r.metadata['selectionStatus']) for r in deps])
        self.assertTrue(all(r.metadata['rpm']['x86Confirmed'] for r in deps))
        self.assertEqual('inactive', next(r for r in result.records if r.kind=='build_arch_constraint').metadata['selectionStatus'])
