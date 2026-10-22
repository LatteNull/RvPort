import unittest

from kb_scanner.analyzers.macro_state import MacroState, evaluate, join


class MacroStateTests(unittest.TestCase):
    def test_values_late_alias_precedence_and_definedness(self):
        env = {'X': MacroState(True, '0', 'x'), 'OFF': MacroState(False, None, 'off'),
               'A': MacroState(True, 'X || 1', 'a'), 'LATE': MacroState(True, 'X', 'late')}
        for text, expected in [('defined(X)', True), ('defined OFF', False), ('!OFF', True),
                               ('X == 0 && (A)', True), ('A && 0', False),
                               ('010 == 0x8', True), ('X != -1', True), ('LATE', False),
                               ('MISSING && 0', False), ('MISSING || 1', True),
                               ('MISSING || 0', None), ('MISSING && 1', None),
                               ('!MISSING', None), ('MISSING == 0', None)]:
            with self.subTest(text=text):
                self.assertIs(expected, evaluate(text, env).truth)
        env['X'] = MacroState(True, '1', 'new-x')
        result = evaluate('LATE', env)
        self.assertIs(True, result.truth)
        self.assertEqual(('late', 'new-x'), result.evidence_ids)
        # Object macros are textual substitution, not implicit parenthesized values.
        env['A'] = MacroState(True, '1 || 0', 'a')
        self.assertIs(True, evaluate('A && 0', env).truth)

    def test_unknown_invalid_and_bounded_input(self):
        env = {'X': MacroState(None, None, 'x'), 'V': MacroState(True, None, 'v'),
               'E': MacroState(True, '', 'e'), 'F': MacroState(True, '1', 'f', function_like=True),
               'LOOP': MacroState(True, 'LOOP', 'loop'), 'A': MacroState(True, 'B', 'a'),
               'B': MacroState(True, '1', 'b')}
        for text in ('X', 'V', 'F', 'E', 'LOOP', 'defined(X)', 'defined MISSING', '',
                     'defined(', 'defined(1)', 'defined(X', 'defined(X 1)', '08',
                     '1 + 2', '1 2', '(1', '-X', '-', '!', ')', 'F(1)', '0 && system(1)'):
            with self.subTest(text=text):
                self.assertIsNone(evaluate(text, env).truth)
        self.assertIsNone(evaluate('A', env, depth_limit=1).truth)
        self.assertIsNone(evaluate('((1))', env, depth_limit=1).truth)
        self.assertIsNone(evaluate('A', env, token_limit=2).truth)
        self.assertIsNone(evaluate('1 || 0', env, token_limit=2).truth)

    def test_feasible_arm_join_is_deterministic_and_keeps_all_origins(self):
        left = {'X': MacroState(True, '1', 'left'), 'Y': MacroState(False, None, 'y'),
                'DIFF': MacroState(True, '1', 'd1')}
        right = {'X': MacroState(True, '1', 'right'), 'Y': MacroState(True, '1', 'y2'),
                 'DIFF': MacroState(True, '0', 'd2'), 'NEW': MacroState(True, '1', '')}
        result = join((left, right))
        self.assertEqual(result, join((right, left)))
        self.assertIs(True, evaluate('X', result).truth)
        self.assertEqual(('left', 'right'), result['X'].evidence_ids)
        self.assertIsNone(evaluate('Y', result).truth)
        self.assertIsNone(evaluate('NEW', result).truth)
        self.assertIs(True, evaluate('defined(DIFF)', result).truth)
        self.assertIsNone(evaluate('DIFF', result).truth)
        self.assertEqual({}, join(()))
        self.assertEqual(left, join((left,)))
        self.assertIsNot(left, join((left,)))
        self.assertIs(left['X'], join((left,dict(left)))['X'])
