import unittest
from dataclasses import replace

from kb_scanner.frontends.build.cmake.macro_conflicts import macro_conflicts
from kb_scanner.frontends.build.cmake.usage import bind_usage
from kb_scanner.frontends.build.vocabulary import BuildRecord
from .support import command as c, project


def item(value, *, path='CMakeLists.txt', order=1, command='target_compile_definitions', status='selected'):
    return path, BuildRecord('build_argument', value, order, 1, len(value)+1,
        {'selectionStatus': status, 'cmake': {'target': 'a', 'order': order, 'commandName': command}}), ()


class MacroConflictTests(unittest.TestCase):
    def test_equivalent_inactive_nonmacro_and_ordered_options(self):
        self.assertEqual({}, macro_conflicts([item('-DA'), item('-DA=1'), item('-DA=0', status='inactive'), item('-mavx')]))
        self.assertEqual({}, macro_conflicts([item('-DA=0', command='target_compile_options'),
                                             item('-DA=1', command='target_compile_options')]))
        self.assertEqual({}, macro_conflicts([]))

    def test_conflicting_definitions_and_unknown_define_undef_order(self):
        for values, reason in (([item('-DA=0'), item('-DA=1')], 'conflicting-build-macro'),
                ([item('-DA'), item('-UA')], 'unknown-argument-order'),
                ([item('-DA=0', command='target_compile_options'),
                  item('-DA=1', command='target_compile_options', path='sub/CMakeLists.txt')], 'conflicting-build-macro'),
                ([item('-DA=0', command='target_compile_options'),
                  item('-DA=1', command='target_compile_options', order=2)], 'conflicting-build-macro')):
            self.assertEqual({'A': reason}, macro_conflicts(values))
            self.assertEqual({'A': reason}, macro_conflicts(list(reversed(values))))

    def test_usage_conflict_closes_no_proven_recipe_and_preserves_sources(self):
        raw = project(c('add_library','api','INTERFACE'),
            c('target_compile_definitions','api','INTERFACE','A=1',line=2),
            c('add_library','other','INTERFACE',line=3),
            c('target_compile_definitions','other','INTERFACE','A=0',line=4),
            c('add_library','app','a.cpp',line=5),
            c('target_link_libraries','app','PRIVATE','api','other',line=6))
        result = bind_usage(raw)['CMakeLists.txt']
        recipe = next(r.metadata['sourceChain'] for r in result.records
                      if r.metadata.get('sourceChain',{}).get('role') == 'recipe')
        self.assertFalse(recipe['proven'])
        self.assertEqual({'A':'conflicting-build-macro'}, recipe['macroConflicts'])
        self.assertEqual({'1','0'}, {arg['value'] for arg in recipe['arguments']})
        effective = [r for r in result.records if r.metadata['cmake'].get('effective')]
        self.assertEqual(2,len(effective))
        self.assertTrue(all(len(r.metadata['cmake']['parents']) >= 3 for r in effective))
        self.assertTrue(result.partial)
        self.assertIn('conflicting-build-macro',result.diagnostics)
