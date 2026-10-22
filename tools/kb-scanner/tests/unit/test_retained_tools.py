"""Retained entry points: fake IO/delegates only, never refresh checked-in facts."""
import argparse
import hashlib
import json
import runpy
import unittest
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from kb_scanner.core import ScanRequest, StageResult, CompletionStatus
from kb_scanner.models import CompileCommandContext, ProjectFacts, Finding
from tests.unit.compatible_cutover.support import context


class RetainedAdapterTests(unittest.TestCase):
    def test_context_roundtrip_modes_manifest_and_entrypoint(self):
        from kb_scanner.adapters import legacy as m
        unit = CompileCommandContext(Path('/input/a.c'), defines={'X': '1'}, compiler='cc')
        self.assertEqual(unit, m._to_legacy_compile_contexts((m._to_core_compile_context(unit),))[str(unit.path)])
        for exists, units, infer, expected in ((False, {}, 'off', 'syntax_scan'), (True, {'a': unit}, 'auto', 'source_context_with_compile_database'), (True, {}, 'auto', 'source_context')):
            with patch.object(Path, 'exists', return_value=exists), patch.object(m, 'load_compile_commands', return_value=(units, ['warning'])), patch.object(m, '_load_manifest', return_value={}):
                built = m.LegacyContextFactory().build(ScanRequest('/input', '/rules', '/out', context_infer=infer))
            self.assertEqual(expected, built.value.scan_mode)
            self.assertEqual(CompletionStatus.PARTIAL, built.status)
            self.assertIn('compile_commands.json', m._context_message(built.value))
        for raw, expected in (('id: test', {'id': 'test'}), ('[]', {})):
            with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'read_text', return_value=raw):
                self.assertEqual(expected, m._load_manifest(Path('/rules')))
        with patch.object(Path, 'exists', return_value=False):
            self.assertEqual({}, m._load_manifest(Path('/rules')))
        with patch.object(Path, 'read_bytes', return_value=b'data'):
            self.assertEqual(hashlib.sha256(b'data').hexdigest(), m._artifact_ref(Path('/out/scan.log')).sha256)
        self.assertIsNotNone(m.create_legacy_application())
        args = NS(input='/in', rules='/r', output='/o', language='c, cpp', exclude='', exclude_path=[' a ', ''], format='json', context_infer='off', target_arch='riscv64', include_inactive_branches=False, no_comment_hints=False, compile_commands=None, locale='en')
        self.assertEqual(('a',), m.scan_request_from_namespace(args).exclude_paths)
        with patch('kb_scanner.cli.main', return_value=7), self.assertRaises(SystemExit) as raised:
            runpy.run_module('kb_scanner', run_name='__main__')
        self.assertEqual(7, raised.exception.code)

    def test_runner_success_failure_and_report_delegation(self):
        from kb_scanner.adapters import legacy as m
        ctx = context(Path('/project'))
        with patch.object(m, 'load_rules', return_value=([], [])), patch.object(m, 'load_generated_entries', return_value=[]), patch.object(m, 'evaluate_rules', return_value=[]), patch.object(m, 'parse_project', side_effect=lambda **_: ProjectFacts(Path('/p'), [], 'syntax_scan')):
            for stage, code in ((StageResult(value=()), 0), (StageResult(value=None, status=CompletionStatus.FAILED), 2)):
                runner = m.LegacyPipelineRunner(NS(project=lambda *_: stage))
                self.assertEqual(code, runner.run(ctx).exit_code)
            with patch.object(m, 'load_rules', return_value=([], ['broken'])):
                self.assertEqual(1, m.LegacyPipelineRunner(NS(project=lambda *_: StageResult(value=()))).run(ctx).exit_code)
        with patch.object(m, 'load_rules', side_effect=ValueError('bad')):
            self.assertEqual('legacy.internal-error', m.LegacyPipelineRunner().run(ctx).diagnostics[0].code)
        with patch.object(m, 'write_reports') as write, patch.object(m, '_artifact_ref', side_effect=lambda p: p.name):
            projector = m._LegacyReportProjectorAdapter()
            state = m._LegacyRunState(ProjectFacts(Path('/p'), [], 'syntax_scan'), [])
            self.assertEqual(('scan-result.json', 'scan-report.html', 'scan.log'), projector.project(ctx, state).value)
            self.assertEqual(('scan.log',), projector.project(replace(ctx, formats=()), state).value)
            self.assertEqual(2, write.call_count)

    def test_retained_report_counts_html_escaping_and_optional_formats(self):
        from kb_scanner import report as m
        finding = Finding('id', 'rule', 'high', 'high', 'title', '', Path('a.c'), 1, 1, '<script>', '<bad>', '', 'fix', '', '<script>', 'source_context')
        findings = [finding, replace(finding, finding_type='hint', is_blocking=False, is_reference_source=False), replace(finding, finding_type='guarded'), replace(finding, finding_type='portability_gap', is_reference_source=False)]
        project = ProjectFacts(Path('/p'), [], 'source_context', compile_commands_path=Path('/p/cc.json'), compile_contexts={'a': CompileCommandContext(Path('a.c'), compiler='/bin/cc'), 'b': CompileCommandContext(Path('b.c'))})
        payload = m.to_json_payload(project, findings, 'rules', '1')
        self.assertEqual(4, payload['summary']['findings'])
        self.assertEqual(1, payload['summary']['hints'])
        self.assertEqual(1, payload['summary']['portabilityGaps'])
        self.assertEqual(1, payload['summary']['references'])
        self.assertNotIn('<script>', m.render_html(payload))
        self.assertIn('&lt;script&gt;', m.render_html(payload))
        self.assertEqual('', m._compatibility_text({}))
        self.assertIn('构建数据库', m._compatibility_text({'compatible_sibling_branch': True, 'alternative_impl': {'has_compatible_alternative': True}, 'build_context': {'source': 'compile_commands.json'}}))
        for formats, count in (([], 1), (['json', 'html'], 3)):
            with patch.object(Path, 'mkdir'), patch.object(Path, 'write_text') as write:
                m.write_reports(project, findings, Path('/out'), formats, 'r', '1')
            self.assertEqual(count, write.call_count)


class RetainedCollectorTests(unittest.TestCase):
    def test_clang_gcc_collection_uses_fake_upstream_and_fake_output(self):
        from tools import collect_clang_x86_entries as clang, collect_gcc_x86_entries as gcc
        header = '_mm_add_ps(); _mm_add_ps(); __rdtsc(); __builtin_ia32_addps; __m128; __AVX2__\n'
        for module in (clang, gcc):
            output = MagicMock()
            with ExitStack() as stack:
                stack.enter_context(patch.object(module, 'OUT', output))
                stack.enter_context(patch('builtins.print'))
                stack.enter_context(patch.object(Path, 'exists', return_value=True))
                stack.enter_context(patch.object(Path, 'is_file', return_value=True))
                stack.enter_context(patch.object(Path, 'read_text', autospec=True, side_effect=lambda p, **_: ';comment\n\nmavx\nmarch=\nnot-option\n' if p.name == 'i386.opt' else header))
                if module is clang:
                    stack.enter_context(patch.object(clang, 'list_headers', return_value=['immintrin.h']))
                    stack.enter_context(patch.object(clang, 'collect_compiler_flags', return_value=['-mavx']))
                else:
                    stack.enter_context(patch.object(Path, 'iterdir', return_value=iter([Path('immintrin.h'), Path('readme.txt')])))
                self.assertEqual(0, module.main())
            payload = json.loads(output.write_text.call_args.args[0])
            self.assertEqual(['_mm_add_ps'], payload['intrinsics'])
            self.assertEqual(['__m128'], payload['vectorTypes'])
            self.assertIn('-mavx', payload['compilerFlags'])
        with patch.object(Path, 'exists', return_value=False):
            for fn in (clang.list_headers, clang.collect_compiler_flags, gcc.main):
                with self.assertRaises(SystemExit): fn()
        options = 'def A: Flag<["-"], "mavx">, Group<m_x86_Features_Group>; def B: Flag<["-"], "other">; def C: Group<m_x86_AVX10_Features_Group>;'
        with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'read_text', return_value=options):
            self.assertEqual(['-mavx'], clang.collect_compiler_flags())
        with patch.object(clang, 'SEED_HEADERS', {'immintrin.h'}), patch.object(Path, 'exists', autospec=True, side_effect=lambda p: p.name != 'missingintrin.h'), patch.object(Path, 'read_text', return_value='#include "immintrin.h"\n#include "missingintrin.h"\n#include "other.txt"'):
            self.assertEqual(['immintrin.h'], clang.list_headers())
