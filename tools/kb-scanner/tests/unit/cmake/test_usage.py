import unittest
from kb_scanner.frontends.build.cmake.usage import bind_usage
from .support import command as c, project


def effective(result):
    return [r for p in result.values() for r in p.records if r.metadata['cmake'].get('effective')]


class UsageTests(unittest.TestCase):
    def test_inactive_link_and_bounded_diamond_do_not_leak(self):
        result=bind_usage(project(c('add_library','a','a.cpp'),c('add_library','b','b.cpp',line=2),
            c('target_compile_options','a','PUBLIC','-DA',line=3),c('if','OFF',line=4),
            c('target_link_libraries','b','PRIVATE','a',line=5),c('endif',line=6)))
        self.assertEqual([('a.cpp','-DA')],[(r.metadata['cmake']['source'],r.value) for r in effective(result)])
        raw=project(c('add_library','api','INTERFACE','api.cpp'),c('target_compile_options','api','INTERFACE','-DA',line=2))
        self.assertEqual('unknown',next(r for r in raw['CMakeLists.txt'].records if r.kind=='build_source').metadata['selectionStatus'])
        self.assertEqual([],effective(bind_usage(raw)))

    def test_late_directory_definitions_apply_to_existing_current_targets(self):
        raw=project(c('add_library','a','a.cpp'),c('add_compile_definitions','LATE=1',line=2))
        self.assertEqual([('-DLATE=1','selected')],[(r.value,r.metadata['selectionStatus']) for r in effective(bind_usage(raw))])

    def test_private_public_interface_and_macro_identity(self):
        result=bind_usage(project(c('add_library','lib','lib.cpp'),c('add_executable','app','app.cpp',line=2),
            c('target_compile_options','lib','PRIVATE','-DPRIVATE=0','PUBLIC','-DPUBLIC','INTERFACE','-DCLIENT',line=3),
            c('target_link_libraries','app','PRIVATE','lib',line=4)))
        values={(r.metadata['cmake']['source'],r.value) for r in effective(result)}
        self.assertEqual({('lib.cpp','-DPRIVATE=0'),('lib.cpp','-DPUBLIC'),('app.cpp','-DPUBLIC'),('app.cpp','-DCLIENT')},values)
        for r in effective(result):
            self.assertEqual('selected',r.metadata['selectionStatus'])
            self.assertEqual('argument',r.metadata['sourceChain']['role'])
        bindings=[r for p in result.values() for r in p.records if r.metadata.get('sourceChain',{}).get('role')=='recipe']
        self.assertTrue(all(r.metadata['sourceChain']['proven'] for r in bindings))

    def test_transitive_usage_and_directory_order(self):
        result=bind_usage(project(c('add_compile_options','-mavx2'),c('add_library','a','a.cpp',line=2),
            c('add_library','b','b.cpp',line=3),c('add_library','c','c.cpp',line=4),
            c('target_compile_options','a','INTERFACE','-DUSE',line=5),
            c('target_link_libraries','b','PUBLIC','a',line=6),c('target_link_libraries','c','PRIVATE','b',line=7),
            c('add_compile_options','-DLATE',line=8)))
        values={(r.metadata['cmake']['source'],r.value) for r in effective(result)}
        self.assertIn(('c.cpp','-DUSE'),values)
        self.assertNotIn(('a.cpp','-DUSE'),values)
        self.assertFalse(any(value=='-DLATE' for _,value in values))
        self.assertEqual(3,sum(value=='-mavx2' for _,value in values))

    def test_unknown_links_cycles_and_budgets(self):
        for links in [('missing',),('v',)]:
            result=bind_usage(project(c('add_library','v','v.cpp'),c('target_compile_options','v','PRIVATE','-DUSE',line=2),
                                     c('target_link_libraries','v','PRIVATE',*links,line=3)))
            self.assertEqual('unknown',effective(result)[0].metadata['selectionStatus'])
        raw=project(c('add_library','v','v.cpp'),c('target_compile_options','v','PRIVATE','-DA','-DB',line=2))
        self.assertTrue(bind_usage(raw,max_items=1)['CMakeLists.txt'].partial)
        self.assertEqual([],effective(bind_usage(raw,max_depth=0)))

    def test_inactive_and_dynamic_options_never_bind_macros(self):
        raw=project(c('add_library','v','v.cpp'),c('if','OFF',line=2),c('target_compile_options','v','PRIVATE','-DA',line=3),
                    c('endif',line=4),c('target_compile_options','v','PRIVATE','-UFOO=1','-include','bad.h','$<x>','-DB',line=5),
                    c('target_sources','v','INTERFACE','interface.cpp',line=6))
        result=bind_usage(raw)
        self.assertNotIn('-DA',[r.value for r in effective(result)])
        bindings=[r.metadata['sourceChain'] for p in result.values() for r in p.records if r.metadata.get('sourceChain',{}).get('role')=='recipe']
        self.assertEqual(1,len(bindings))
        self.assertFalse(bindings[0]['proven'])
        self.assertTrue(any(r.metadata['selectionStatus']=='unknown' for r in effective(result)))
