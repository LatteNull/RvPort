import unittest
from kb_scanner.frontends.build.cmake.syntax import Token
from kb_scanner.frontends.build.cmake.values import expand, literal, condition, matches, truth, both, either, negate
from .support import command


class ValuesTests(unittest.TestCase):
    def test_literals_and_expansion(self):
        for text, expected in [('abc','abc'), ('"x"','x'), ('[=[a\nb]=]','a\nb'), ('[bad',None), ('a\\b',None),
                               ('$ENV{X}',None), ('$CACHE{X}',None), ('$<IF:X>',None), ('${X}/x','riscv64/x'),
                               ('${MISSING}',None), ('${bad-token}',None), ('^x$','^x$')]:
            with self.subTest(text=text):
                self.assertEqual(expected, expand(Token(text), {'X':'riscv64'}))
        self.assertIsNone(expand(Token('abc'), {}, max_length=1))
        self.assertEqual('${X}',expand(Token('[=[${X}]=]'),{'X':'riscv64'}))
        self.assertIsNone(expand(Token('[[long]]'),{},max_length=1))
        self.assertEqual('abc', literal(Token('abc')))

    def test_boolean_truth_table(self):
        for a in (True, False, None):
            for b in (True, False, None):
                self.assertEqual(False if a is False or b is False else None if None in (a,b) else True, both(a,b))
                self.assertEqual(True if a is True or b is True else None if None in (a,b) else False, either(a,b))
            self.assertEqual(None if a is None else not a, negate(a))
        for text, expected in [('ON',True),('OFF',False),('0',False),('-2',True),('X-NOTFOUND',False),('thing',None),(None,None)]:
            self.assertEqual(expected, truth(text))

    def test_safe_pattern_subset(self):
        for pattern, expected in [('^(x86_64|riscv64)$',True),('^riscv',True),('64$',True),('iscv',True),('^x86$',False),
                                  ('(riscv+)+',None),('riscv.*',None),('[a-z]',None),('',None),('x'*513,None)]:
            self.assertEqual(expected, matches('riscv64',pattern))
        self.assertIsNone(matches(None,'x'))
        self.assertIsNone(matches('x',None))

    def test_condition_composition_and_unknown(self):
        values={'ARCH':'riscv64','UNRESOLVED':None,'OFFVAR':'0'}
        cases=[(('NOT','ARCH','MATCHES','"^(x86_64|AMD64)$"'),True),
               (('(','ARCH','STREQUAL','riscv64',')','AND','NOT','OFFVAR'),True),
               (('ON','OR','OFF','AND','OFF'),False),
               (('UNRESOLVED','STREQUAL','GNU'),None), (('UNRESOLVED','MATCHES','"x"'),None),
               (('"ARCH"','STREQUAL','riscv64'),False), (('OFF','AND','UNRESOLVED'),False),
               (('NOT',),None), (('(', 'ON'),None), (('ARCH','STREQUAL'),None), (('ON','bogus'),None),
               ((),None), (('ON',)*257,None), (('NOT',)*34+('ON',),None)]
        for args,expected in cases:
            with self.subTest(args=args):
                self.assertEqual(expected,condition(command('if',*args).args,values))
