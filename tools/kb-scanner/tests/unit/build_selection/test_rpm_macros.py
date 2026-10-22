import unittest
from kb_scanner.frontends.build.rpm.macros import MacroEnv, Definition, Value


class RpmMacroTests(unittest.TestCase):
    def test_expansion_work_budget_bounds_repeated_aliases(self):
        env = MacroEnv('riscv64')
        env.define('v0', 'x', 'zero')
        for i in range(1, 24):
            env.define(f'v{i}', f'%{{v{i-1}}}%{{v{i-1}}}', str(i), lazy=True)
        value = env.expand('%{v23}')
        self.assertIsNone(value.text)
        self.assertIn('rpm-macro-budget', value.reason)

    def test_target_profile_and_overrides(self):
        env = MacroEnv('rv64')
        self.assertEqual('(riscv-64)', env.expand('%{_isa}').text)
        self.assertEqual('riscv64', env.expand('%{_arch}').text)
        self.assertIsNone(MacroEnv('riscv32').expand('%{_isa}').text)
        env.define('__isa_name', 'x86', 'def:1')
        self.assertEqual('(x86-64)', env.expand('%{_isa}').text)
        env.define('__isa', 'x86-32', 'def:2')
        self.assertEqual('(x86-32)', env.expand('%{_isa}').text)
        self.assertIn('def:2', env.expand('%{_isa}').refs)

    def test_global_define_and_cycle(self):
        env = MacroEnv('riscv64')
        env.define('base', 'one', '1')
        env.define('immediate', '%{base}', '2')
        env.define('delayed', '%{base}', '3', lazy=True)
        env.define('base', 'two', '4')
        self.assertEqual('one', env.expand('%{immediate}').text)
        self.assertEqual('two', env.expand('%{delayed}').text)
        self.assertEqual({'3','4'}, set(env.expand('%{delayed}').refs))
        env.define('cycle', '%{cycle}', '5', lazy=True)
        self.assertEqual('rpm-macro-cycle', env.expand('%{cycle}').reason)

    def test_definedness_and_nested_alternatives(self):
        env = MacroEnv('riscv64')
        env.values['absent'] = Definition(Value(''), False)
        for expression, expected in [('%{?absent}', ''), ('%{!?absent:yes}', 'yes'),
                                      ('%{?_arch:%{_target_cpu}}', 'riscv64'), ('%{!?_arch:no}', '')]:
            self.assertEqual(expected, env.expand(expression).text)
        self.assertIsNone(env.expand('%{absent}').text)
        self.assertIsNone(env.expand('%{?external}').text)
        self.assertIsNone(env.expand('%{external}').text)
        env.values['known_unknown'] = Definition(Value(reason='dynamic'))
        self.assertEqual('yes', env.expand('%{?known_unknown:yes}').text)

    def test_merge_preserves_all_definitions(self):
        env = MacroEnv('riscv64'); a = env.copy(); b = env.copy()
        a.define('same', 'ok', 'a'); b.define('same', 'ok', 'b')
        a.define('different', 'one', 'a'); b.define('different', 'two', 'b')
        a.define('maybe', 'one', 'c')
        env.merge([a,b]); env.merge([])
        self.assertEqual('ok', env.expand('%{same}').text)
        self.assertEqual({'a','b'}, set(env.expand('%{same}').refs))
        self.assertIsNone(env.expand('%{different}').text)
        self.assertEqual('1',env.expand('%{?different:1}').text)
        self.assertIsNone(env.expand('%{?maybe}').text)
        env.invalidate('tainted')
        self.assertIsNone(env.expand('%{_arch}').text)

    def test_safe_shapes_budgets_and_escaping(self):
        env = MacroEnv('riscv64')
        self.assertEqual('%{_arch}',env.expand('%%{_arch}').text)
        self.assertEqual('riscv64',env.expand('%(uname -m)').text)
        for s in ('%(touch marker)', '%{lua:bad}', '%{!_arch}', '%{a(}', '%{unclosed', '%bare', '%[1]', '%_arch'):
            self.assertIsNone(env.expand(s).text, s)
        self.assertEqual('literal %.',env.expand('literal %.').text)
        self.assertIsNone(MacroEnv('riscv64',max_depth=1).expand('%{?_arch:%{_arch}}').text)
        short = MacroEnv('riscv64',max_chars=10)
        self.assertIsNone(short.expand('x'*11).text)
        short.define('xx','0123456789','key')
        self.assertIsNone(short.expand('%{xx}abc').text)
        self.assertIsNone(short.expand('%{xx}',depth=32).text)
        with self.assertRaises(ValueError): MacroEnv('riscv64',max_chars=0)

class RpmValueTests(unittest.TestCase):
    def test_reference_order_is_stable(self):
        self.assertEqual(('b','a'), Value('x',('b',)).with_refs('a','b').refs)
