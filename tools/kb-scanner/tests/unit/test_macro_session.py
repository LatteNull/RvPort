from dataclasses import replace
import unittest

from kb_scanner.core import Entity, stable_id
from kb_scanner.analyzers.macro_session import MacroSession, condition, conjunction
from kb_scanner.analyzers.macro_state import MacroState, evaluate
from tests.unit.test_build_macro_binding import ev


def event(name, kind, value, line, **metadata):
    return ev(name, kind, value, line, sourceOrder=line*10, **metadata)


def definition(name, value, line, **metadata):
    return (event(name + str(line), 'macro_definition', name, line, **metadata),
            event('token' + str(line), 'macro_replacement_token', value, line,
                  macroDefinitionEvidenceId=name + str(line), ordinal=0))


def branch(name, kind, value, line, start=10, end=70):
    return event(name, 'preprocessor_branch' if kind == 'preproc_else' else 'preprocessor_condition', value, line,
                 nodeType=kind, preprocessorRegion={'groupStart': start, 'groupEnd': end})


class MacroSessionTests(unittest.TestCase):
    def run_session(self, items, env=None, **budgets):
        source = Entity(stable_id('cpp'), 'source_file', 'x.cpp')
        header = Entity(stable_id('header'), 'source_file', 'h.h')
        session = MacroSession(items, {'x.cpp': source, 'h.h': header}, **budgets)
        seen = []
        result = session.run(source, env or {}, lambda item, env, active, result: seen.append((item, active, result)))
        return result, seen, session

    def test_unknown_same_value_conflict_and_missing_else_join(self):
        for second, expected in (('1', True), ('0', None)):
            items = (branch('if', 'preproc_if', 'X', 1), *definition('A', '1', 2),
                     branch('else', 'preproc_else', 'else', 4), *definition('A', second, 5),
                     event('use', 'call_expression', 'USE', 8))
            env, seen, session = self.run_session(items)
            self.assertIs(expected, evaluate('A', env).truth)
            self.assertEqual(2, len(env['A'].evidence_ids))
            self.assertEqual([None, None, True], [state for _, state, _ in seen])
            self.assertFalse(session.reasons)
        env, _, _ = self.run_session((branch('if', 'preproc_if', 'X', 1), *definition('A', '1', 2)))
        self.assertIsNone(evaluate('defined(A)', env).truth)

    def test_elif_and_inactive_arms_do_not_apply_side_effects(self):
        items = (branch('if', 'preproc_if', '0', 1), *definition('A', '0', 2),
                 branch('elif', 'preproc_elif', '1', 3), *definition('A', '1', 4),
                 branch('else', 'preproc_else', 'else', 5), *definition('A', '0', 6))
        env, seen, _ = self.run_session(items)
        self.assertIs(True, evaluate('A', env).truth)
        self.assertEqual([False, True, False], [state for _, state, _ in seen])
        self.assertEqual((stable_id('A4'),), env['A'].evidence_ids)

    def test_nested_unknown_conditions_join_from_pre_branch_environment(self):
        items = (branch('outer', 'preproc_if', 'X', 1, end=100),
                 branch('inner', 'preproc_if', '1', 2, start=20, end=50), *definition('A', '1', 3),
                 branch('else', 'preproc_else', 'else', 6, end=100), *definition('A', '1', 7))
        env, seen, _ = self.run_session(items)
        self.assertIs(True, evaluate('A', env).truth)
        self.assertEqual([None, None, None], [state for _, state, _ in seen])

    def test_include_order_reentry_undef_and_separate_tu_state(self):
        header = event('headerdef', 'macro_definition', 'A', 1, subject='header')
        token = event('headertoken', 'macro_replacement_token', 'X', 1, subject='header', macroDefinitionEvidenceId='headerdef')
        items = (event('include', 'include', '"h.h"', 1), header, token,
                 event('undef', 'macro_expansion', '#undef X', 3, macroUndefName='X'),
                 event('second-include', 'include', '"h.h"', 5))
        env, _, session = self.run_session(items, {'X': MacroState(True, '1', 'initial')})
        self.assertIs(False, evaluate('A', env).truth)
        self.assertEqual(3, session.visits)
        env2, _, _ = self.run_session(items[:3], {'X': MacroState(True, '1', 'other')})
        self.assertIs(True, evaluate('A', env2).truth)

    def test_unsupported_includes_cycles_budgets_and_partial_definitions(self):
        for include in ('<h.h>', 'missing.h', '../h.h', '/h.h', 'x.cpp'):
            env, _, session = self.run_session((event('inc', 'include', include, 1),), {'X': MacroState(True, '1', 'initial')})
            self.assertIsNone(evaluate('X', env).truth)
            self.assertTrue(session.reasons)
        for budget in ({'include_limit': 0}, {'include_depth': 0}, {'event_limit': 0}):
            _, _, session = self.run_session((event('call', 'call_expression', 'F', 1),), **budget)
            self.assertTrue(session.reasons)
        env, _, _ = self.run_session(definition('X', '1', 1, structureComplete=False))
        self.assertIsNone(evaluate('defined(X)', env).truth)
        env, _, _ = self.run_session(definition('F', '1', 1, functionLike=True))
        self.assertIsNone(evaluate('F', env).truth)
        env, _, _ = self.run_session((event('orphan', 'preprocessor_branch', 'else', 1),), {'X': MacroState(True, '1', 'initial')})
        self.assertIsNone(evaluate('X', env).truth)

    def test_native_enrichment_does_not_override_ordered_baseline(self):
        original = definition('X', '1', 1)
        baseline = tuple(replace(item, parse_mode='tree_sitter_baseline') for item in original)
        clang = tuple(replace(item, parse_mode='clang_enrichment') for item in definition('X', '0', 2))
        env, _, session = self.run_session((*clang, *baseline))
        self.assertIs(True, evaluate('X', env).truth)
        source = session.files['x.cpp']
        self.assertEqual({}, session.run(source, {}, lambda *args: self.fail('inactive callback'), active=False))
        self.assertIsNone(condition(event('partial', 'preprocessor_condition', '1', 1, structureComplete=False), {}).truth)
        self.assertIsNone(conjunction(True, None))

    def test_inactive_occurrences_are_visible_without_side_effects_and_budgeted(self):
        items = (branch('if','preproc_if','0',1), *definition('X','0',2),
                 event('call','call_expression','F',3), event('include','include','missing.h',4))
        env, seen, session = self.run_session(items, {'X':MacroState(True,'1','initial')})
        self.assertIs(True,evaluate('X',env).truth)
        self.assertEqual([False,False],[active for _,active,_ in seen])
        self.assertFalse(session.reasons)
        _, _, limited = self.run_session(items,event_limit=1)
        self.assertIn('macro-event-budget',limited.reasons)
        env, _, _ = self.run_session((event('pragma','macro_expansion','#pragma',1,
            unsupportedMacroStateDirective=True),),{'X':MacroState(True,'1','initial')})
        self.assertIsNone(evaluate('X',env).truth)
