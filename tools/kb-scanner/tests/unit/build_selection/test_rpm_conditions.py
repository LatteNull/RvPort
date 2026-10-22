import unittest
from kb_scanner.frontends.build.rpm.conditions import conjunction, negate, status, evaluate


class RpmConditionTests(unittest.TestCase):
    def test_three_values(self):
        for a in (True,False,None):
            for b in (True,False,None):
                expected = False if a is False or b is False else True if a is True and b is True else None
                self.assertIs(expected, conjunction(a,b))
        self.assertIsNone(negate(None)); self.assertTrue(negate(False)); self.assertFalse(negate(True))
        self.assertEqual(['selected','inactive','unknown'],[status(x) for x in (True,False,None)])

    def test_bounded_expression_language(self):
        for expression, expected in [('1',True),('0',False),('!0',True),('1 || 0 && 0',True),
                                      ('(1 || 0) && 0',False),('"rv" == "rv"',True),
                                      ('"rv" != "x86"',True),('1 == 1',True),('01 != 1',False),
                                      ('!(1 == 1)',False)]:
            self.assertIs(expected,evaluate(expression),expression)
        for expression in (None,'', '1 2','1 + 2','1 &&','"a"','"a" == 1','(1','1)2',
                           '__import__("os")','x'*65537,'1 || '*513+'1', '('*200+'1'+')'*200):
            self.assertIsNone(evaluate(expression),expression)
