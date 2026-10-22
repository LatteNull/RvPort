import unittest
from unittest.mock import patch
from kb_scanner.frontends.build.rpm.parser import parse


class RpmParserTests(unittest.TestCase):
    def test_layout_is_branch_local_and_executable_macros_taint_later_selection(self):
        text='%if 0\n%build\necho ignore\n%endif\nRequires: foo(x86-64)'
        self.assertEqual({'foo(x86-64)':'selected'}, self.deps(text))
        text='%if %{external}\n%package addon\n%endif\nRequires: foo(x86-64)'
        self.assertEqual({'foo(x86-64)':'unknown'}, self.deps(text))
        text='%global injected %{lua:rpm.define("_arch x86_64")}\nRequires: foo(x86-64)'
        self.assertEqual({'foo(x86-64)':'unknown'}, self.deps(text))
        records, diagnostics = self.scan('%{?external:Requires: manufactured}\n')
        self.assertTrue(diagnostics)
        self.assertEqual('rpm-directive-unsupported', records[-1].metadata['reason'])

    def scan(self,text,**kwargs):
        with patch('kb_scanner.frontends.build.rpm.shell.parse_scripts'):
            return parse(text,'a.spec','riscv64',**kwargs)

    def deps(self,text):
        items,diags=self.scan(text)
        return {x.value:x.metadata['selectionStatus'] for x in items if x.kind=='build_dependency'}

    def test_if_else_elif_and_nesting(self):
        s='%if "%{_arch}" == "x86_64"\nRequires: x86\n%elif 1\nRequires: riscv\n%else\nRequires: other\n%endif\n'
        self.assertEqual({'x86':'inactive','riscv':'selected','other':'inactive'},self.deps(s))
        s='%ifarch x86_64\n%if %{external}\nRequires: excluded\n%endif\n%endif\n%ifnarch x86_64\nRequires: common\n%endif'
        self.assertEqual({'excluded':'inactive','common':'selected'},self.deps(s))
        s='%if 0\n%define value x86\n%endif\nRequires: pkg%{value}'
        self.assertEqual({'pkg%{value}':'unknown'},self.deps(s))

    def test_branch_definitions(self):
        for condition,expected in [('1','selected'),('%{external}','unknown')]:
            s=f'%if {condition}\n%global cpu riscv64\n%else\n%define cpu x86_64\n%endif\n%if "%{{cpu}}" == "riscv64"\nRequires: pkg\n%endif'
            self.assertEqual(expected,self.deps(s)['pkg'])
        s='%if %{external}\n%global cpu riscv64\n%else\n%global cpu riscv64\n%endif\nRequires: pkg%{cpu}'
        self.assertEqual('selected',self.deps(s)['pkg%{cpu}'])

    def test_structure_damage_and_budget(self):
        for s in ('%endif\nRequires: p','%else\nRequires: p','%if 1\nRequires: p',
                  '%if 1\n%else\n%else\nRequires: p\n%endif'):
            records,diags=self.scan(s)
            self.assertTrue(diags)
            self.assertEqual('unknown',next(x for x in records if x.kind=='build_dependency').metadata['selectionStatus'])
        records,diags=self.scan('%if 1\n%if 1\nRequires: p\n%endif\n%endif',max_depth=1)
        self.assertTrue(diags)
        self.assertTrue(all(x.metadata['selectionStatus']=='unknown' for x in records))

    def test_sections_constraints_and_unknown_constructs(self):
        text='\n%dnl ignored\n# comment\n# %{_arch}\n# %{lua:bad}\n%package addon\nRequires(post): foo >= 1\nExclusiveArch: %{_arch}\nExcludeArch: x86_64\n%description addon\nwords\n%build\necho hello\n%files addon\n/usr/a\n%include other\n'
        records,diags=self.scan(text)
        self.assertTrue(diags)
        dep=next(x for x in records if x.kind=='build_dependency')
        self.assertEqual('addon',dep.metadata['rpm']['package'])
        self.assertEqual('(post)',dep.metadata['rpm']['qualifier'])
        self.assertTrue(any(x.kind=='build_arch_constraint' for x in records))
        for s in ('%define func(x) body\nRequires: foo%{func}', '%define many one\\\nRequires: foo%{many}',
                  '%undefine _arch\nRequires: foo%{_arch}','BuildArch: noarch\nRequires: foo%{_isa}'):
            self.assertEqual('unknown',next(iter(self.deps(s).values())))

    def test_adapter_and_source_span(self):
        from kb_scanner.frontends.build.adapters import parse_rpm
        with patch('kb_scanner.frontends.build.rpm.shell.parse_scripts'):
            r=parse_rpm('  Requires: foo%{?_isa}\r\n','x.spec','riscv64')
        item=next(x for x in r.records if x.kind=='build_dependency')
        self.assertEqual(13,item.start_column)
        self.assertEqual('foo%{?_isa}',item.value)
        self.assertFalse(r.partial)
