import unittest
from kb_scanner.frontends.build.rpm.dependencies import parse_dependency,parse_constraint
from kb_scanner.frontends.build.rpm.macros import MacroEnv
from kb_scanner.frontends.build.rpm.records import Records


class RpmDependencyTests(unittest.TestCase):
    def test_fields_versions_macros_and_rich(self):
        env=MacroEnv('riscv64'); records=Records('x.spec')
        for line,text in enumerate(['Requires: foo%{?_isa}, bar >= 2 baz', 'Recommends: foo(x86-64)',
                                   'BuildRequires(pre): avx-codec', 'Requires: (foo and bar)',
                                   'Requires: pkg%{external}%{_arch}', 'Requires: foo%{?_arch: %{_arch}}'],1):
            self.assertTrue(parse_dependency(text,line,env,records))
        self.assertFalse(parse_dependency('Summary: hi',7,env,records))
        deps=[x for x in records.items if x.kind=='build_dependency']
        self.assertEqual('bar >= 2',deps[1].value)
        self.assertTrue(deps[0].metadata['rpm']['targetAdaptive'])
        self.assertTrue(deps[3].metadata['rpm']['softDependency'])
        self.assertTrue(deps[3].metadata['rpm']['x86Confirmed'])
        self.assertEqual('unknown',deps[5].metadata['selectionStatus'])
        self.assertFalse(deps[6].metadata['rpm']['targetAdaptive'])
        self.assertEqual('foo%{?_arch: %{_arch}}',deps[7].value)
        self.assertEqual('foo riscv64',deps[7].metadata['rpm']['resolvedValue'])
        env.define('_arch','x86_64','override')
        parse_dependency('Requires: foo%{_arch}',9,env,records)
        self.assertFalse(records.items[-1].metadata['rpm']['targetAdaptive'])

    def test_constraints_preserve_activation(self):
        records=Records('x.spec'); env=MacroEnv('riscv64')
        self.assertFalse(parse_constraint('Name: foo',1,env,records))
        for text,expected in [('ExclusiveArch: x86_64',False),('ExclusiveArch: riscv',True),
                              ('ExcludeArch: x86_64',True),('ExclusiveArch: %{external}',None)]:
            parse_constraint(text,1,env,records,active=False)
            self.assertIs(expected,records.items[-1].metadata['rpm']['targetAllowed'])
            self.assertEqual('inactive',records.items[-1].metadata['selectionStatus'])

    def test_records_preserve_unknown_and_damage(self):
        records=Records('x.spec'); env=MacroEnv('riscv64')
        records.expand(env,'%{external}',1,1)
        records.unknown('',2,'unsupported')
        records.emit('build_assignment','',3,0)
        records.damage(0,'broken')
        self.assertTrue(all(x.metadata['selectionStatus']=='unknown' for x in records.items))
        self.assertEqual('<empty>',records.items[-1].value)
