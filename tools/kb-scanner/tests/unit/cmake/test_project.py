import unittest
from kb_scanner.frontends.build.cmake.project import analyze_project
from .support import command as c, project, selected


class ProjectTests(unittest.TestCase):
    def test_mutually_exclusive_same_named_targets_do_not_conflict(self):
        result=project(c('if','OFF'),c('add_library','v','avx.cpp',line=2),c('else',line=3),
                       c('add_library','v','generic.cpp',line=4),c('endif',line=5))
        self.assertEqual([('avx.cpp','inactive'),('generic.cpp','selected')],selected(result,'build_source'))

    def test_include_list_directory_source_directory_and_provenance(self):
        extra={'cmake/defs.cmake':(c('set','FILES','v.cpp'),c('add_library','v','${FILES}',line=2)),
               'sub/CMakeLists.txt':(c('set','FILES','child.cpp'),)}
        result=project(c('include','cmake/defs.cmake'),c('add_subdirectory','sub',line=2),
                       c('add_library','app','${FILES}',line=3),extra=extra)
        self.assertEqual([('v.cpp','selected'),('v.cpp','selected')],selected(result,'build_source'))
        owner=next(r for r in result['CMakeLists.txt'].records if r.kind=='build_target')
        self.assertTrue(any(k.startswith('cmake/defs.cmake:') for k in owner.metadata['cmake']['parents']))
        included=next(r for r in result['cmake/defs.cmake'].records if r.kind=='build_target')
        self.assertEqual('.',included.metadata['cmake']['directory'])

    def test_unknown_side_effect_survives_endif_and_budget_poison(self):
        for tail in [(c('if','ON',line=2),c('unknown_command',line=3),c('endif',line=4)),
                     (c('include','missing',line=2),)]:
            result=project(c('add_library','v','a.cpp'),*tail,c('add_library','app','b.cpp',line=5))
            self.assertTrue(all(state=='unknown' for _,state in selected(result,'build_source')))
        result=project(c('add_library','v','v.cpp'),c('unknown',line=2),max_commands=1)
        self.assertEqual([('v.cpp','unknown')],selected(result,'build_source'))
        from kb_scanner.frontends.build.cmake.syntax import PartialSyntaxError
        def recover(_): raise PartialSyntaxError((c('add_library','v','v.cpp'),))
        result=analyze_project({'CMakeLists.txt':'bad'},'riscv64',parser=recover)
        self.assertEqual([('v.cpp','unknown')],selected(result,'build_source'))
        result=project(c('include','child.cmake'),c('unknown',line=2),
                       extra={'child.cmake':(c('add_library','v','v.cpp'),)})
        self.assertEqual([('v.cpp','unknown')],selected(result,'build_source'))

    def test_rejection_precedes_target_and_keeps_later_facts_unknown(self):
        result=project(c('if','NOT','CMAKE_SYSTEM_PROCESSOR','MATCHES','"^(x86_64|AMD64)$"'),
                       c('message','FATAL_ERROR','"x86 only"',line=2), c('endif',line=3),
                       c('add_library','v','v.cpp',line=4),c('target_compile_options','v','PRIVATE','-mavx2',line=5),
                       c('if','OFF',line=6),c('target_sources','v','PRIVATE','late.cpp',line=7),c('endif',line=8))
        self.assertEqual([('FATAL_ERROR','selected')],selected(result,'build_arch_constraint'))
        self.assertEqual([('v.cpp','unknown'),('late.cpp','unknown')],selected(result,'build_source'))
        self.assertEqual([('-mavx2','unknown')],selected(result,'build_argument'))

    def test_targets_variables_and_explicit_macro_parameters(self):
        result=project(c('set','FILES','a.cpp'),c('list','APPEND','FILES','b.cpp',line=2),
                       c('add_library','v','STATIC','${FILES}',line=3),
                       c('target_compile_definitions','v','PUBLIC','USE_AVX=0',line=4),
                       c('target_compile_options','v','PRIVATE','-UUSE_AVX',line=5),
                       c('target_include_directories','v','INTERFACE','${CMAKE_CURRENT_SOURCE_DIR}/include',line=6),
                       c('add_executable','app','main.cpp',line=7),c('target_link_libraries','app','PRIVATE','v',line=8))
        self.assertEqual([('a.cpp','selected'),('b.cpp','selected'),('main.cpp','selected')],selected(result,'build_source'))
        self.assertEqual([('-DUSE_AVX=0','selected'),('-UUSE_AVX','selected')],selected(result,'build_argument'))
        self.assertEqual([('include','selected')],selected(result,'build_directory'))
        self.assertEqual([('v','selected')],selected(result,'build_dependency'))

    def test_branches_option_and_inactive_fatal(self):
        result=project(c('option','OPT','"desc"','OFF'),c('if','OPT',line=2),c('message','FATAL_ERROR',line=3),
                       c('else',line=4),c('set','A','a.cpp',line=5),c('endif',line=6),c('add_library','v','${A}',line=7))
        self.assertEqual([('FATAL_ERROR','unknown')],selected(result,'build_arch_constraint'))
        self.assertEqual([('${A}','unknown')],selected(result,'build_source'))
        result=project(c('if','OFF'),c('message','FATAL_ERROR',line=2),c('elseif','ON',line=3),
                       c('add_library','v','v.cpp',line=4),c('else',line=5),c('add_library','x','x.cpp',line=6),c('endif',line=7))
        self.assertEqual([('FATAL_ERROR','inactive')],selected(result,'build_arch_constraint'))
        self.assertEqual([('v.cpp','selected'),('x.cpp','inactive')],selected(result,'build_source'))

    def test_include_child_scope_and_unreferenced_fragment(self):
        extra={'defs.cmake':(c('set','FILES','v.cpp'),), 'sub/CMakeLists.txt':(c('set','FILES','child.cpp'),c('add_library','child','${FILES}',line=2)),
               'loose.cmake':(c('message','FATAL_ERROR'),)}
        result=project(c('include','defs'),c('add_subdirectory','sub',line=2),c('add_library','v','${FILES}',line=3),extra=extra)
        self.assertEqual([('v.cpp','selected'),('sub/child.cpp','selected')],selected(result,'build_source'))
        fatal=next(r for r in result['loose.cmake'].records if r.kind=='build_arch_constraint')
        self.assertEqual('unknown',fatal.metadata['selectionStatus'])
        self.assertFalse(fatal.metadata['cmake']['required'])

    def test_root_escape_missing_and_cyclic_inputs(self):
        for path in ('../escape','/etc/passwd','C:/private','back\\slash','missing','${MISSING}'):
            result=project(c('include',path),c('add_library','v','v.cpp',line=2))
            self.assertEqual([('v.cpp','unknown')],selected(result,'build_source'))
            self.assertTrue(result['CMakeLists.txt'].partial)
        result=project(c('include','cycle.cmake'),extra={'cycle.cmake':(c('include','cycle.cmake'),)})
        self.assertTrue(result['CMakeLists.txt'].partial)
        result=project(c('include','a.cmake'),extra={'a.cmake':(c('set','A','a.cpp'),)},max_depth=1)
        self.assertTrue(result['CMakeLists.txt'].partial)

    def test_unknown_commands_and_control_bodies_do_not_execute(self):
        for name in ('execute_process','find_package','function','macro','foreach','while','block'):
            cmds=[c('set','X','ON'),c(name,'X',line=2)]
            if name in ('function','macro','foreach','while','block'):
                cmds += [c('message','FATAL_ERROR',line=3),c('end'+name,line=4)]
            cmds += [c('if','X',line=5),c('add_library','v','v.cpp',line=6),c('endif',line=7)]
            result=project(*cmds)
            self.assertEqual([('v.cpp','unknown')],selected(result,'build_source'))
            self.assertEqual([],selected(result,'build_arch_constraint'))
            self.assertTrue(result['CMakeLists.txt'].partial)

    def test_assignment_target_edge_cases(self):
        result=project(c('set','CACHEVAR','ON','CACHE','BOOL','desc'),c('unset','CACHEVAR',line=2),
                       c('add_library','v','a.cpp',line=3),c('add_library','v','b.cpp',line=4),
                       c('target_sources','missing','PRIVATE','c.cpp',line=5),
                       c('target_sources','v','PRIVATE','$<IF:...>',line=6),
                       c('add_compile_options','-mavx2',line=7),c('add_compile_definitions','USE_AVX',line=8))
        self.assertEqual([('a.cpp','selected'),('b.cpp','unknown'),('c.cpp','unknown'),('$<IF:...>','unknown')],selected(result,'build_source'))
        self.assertEqual([('-mavx2','selected'),('-DUSE_AVX','selected')],selected(result,'build_argument'))
        self.assertTrue(result['CMakeLists.txt'].partial)

    def test_unsupported_parent_scope_and_malformed_boundaries(self):
        result=project(c('set','X','ON','PARENT_SCOPE'),c('add_library','v','v.cpp',line=2))
        self.assertEqual([('v.cpp','unknown')],selected(result,'build_source'))
        for name in ('else','elseif','endif'):
            result=project(c(name),c('add_library','v','v.cpp',line=2))
            self.assertTrue(result['CMakeLists.txt'].partial)
        result=project(c('set','X','ON'),c('project','p',line=2),max_commands=1)
        self.assertIn('cmake-command-budget',result['CMakeLists.txt'].diagnostics)
        with self.assertRaises(ValueError): project(max_depth=0)
        result=analyze_project({'bad.cmake':'bad'},'riscv64',parser=lambda _: (_ for _ in ()).throw(ValueError('parse')))
        self.assertTrue(result['bad.cmake'].partial)

    def test_safe_metadata_and_unsupported_values(self):
        result=project(c('cmake_minimum_required','VERSION','3.20'),c('project','P'),c('enable_testing'),c('add_test','NAME','x'),
                       c('set_tests_properties','x','PROPERTIES','PASS_REGULAR_EXPRESSION','x'),c('message','STATUS','ok'),
                       c('set','${UNKNOWN}','X'),c('set','EMPTY',''),c('list','APPEND','UNKNOWN','x'),
                       c('add_library'),c('include'),c('endmacro'),c('set','ROOT','${CMAKE_SOURCE_DIR}'),
                       c('add_library','imp','IMPORTED','x.cpp',line=8))
        self.assertTrue(result['CMakeLists.txt'].partial)
        self.assertEqual([],selected(result,'build_arch_constraint'))
