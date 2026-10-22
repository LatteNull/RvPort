"""按需采集边界单元测试：纯 Evidence、fake normalizer/adapter，无 native parser。"""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from kb_scanner.core import CompletionStatus, FrontendSnapshot, KnowledgeSnapshot, StageResult, WorkspaceSnapshot, stable_id
from kb_scanner.pipeline.usage_frontend import UsageAnchorSelector
from kb_scanner.pipeline.composite import CompositeProjectFrontend
from kb_scanner.frontends.cpp.frontend import CppFrontend
from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter
from kb_scanner.frontends.cpp.vocabulary import make_evidence, make_source_file_entity
from tests.unit.frontends.cpp.support import make_context, span
from tests.unit.test_usage_inventory import fixture


class UsageFrontendTests(unittest.TestCase):
    def setUp(self):
        self.context = make_context(Path('/tmp'))
        self.entity = make_source_file_entity('a.cpp', ('cpp',), '1')
        self.knowledge = KnowledgeSnapshot(stable_id('knowledge'), '1')

    def test_formal_normalizer_and_matcher_select_only_candidate_and_preserve_identity(self):
        candidate = make_evidence(kind='macro_expansion', subject_id=self.entity.id, value='FORMAT_X86',
            producer='fake', parse_mode='base', confidence='high', span=span('a.cpp'))
        ordinary = make_evidence(kind='macro_expansion', subject_id=self.entity.id, value='FORMAT_LOCAL',
            producer='fake', parse_mode='base', confidence='high', span=span('a.cpp', 2))
        selector = UsageAnchorSelector(self.context, self.knowledge)
        selected = selector.select(self.entity, (ordinary, candidate))
        self.assertEqual((candidate,), selected)
        self.assertIs(candidate, selected[0])
        self.assertEqual((), selector.select(self.entity, (ordinary,)))
        self.assertEqual((candidate,), selector.select(self.entity, (candidate, ordinary)))

    def test_failed_or_unavailable_normalization_never_collects(self):
        for status, value in ((CompletionStatus.FAILED, None), (CompletionStatus.UNAVAILABLE, FrontendSnapshot())):
            normalizer = Mock()
            normalizer.normalize.return_value = StageResult(value, status)
            demand = Mock()
            selector = UsageAnchorSelector(self.context, self.knowledge, normalizer=normalizer, demand=demand)
            self.assertEqual((), selector.select(self.entity, ()))
            demand.select.assert_not_called()

    def test_deduplication_only_reduces_preselection_and_expands_all_original_occurrences(self):
        from dataclasses import replace
        from kb_scanner.normalization import CppEvidenceNormalizer
        first = make_evidence(kind='macro_expansion', subject_id=self.entity.id, value='FORMAT_X86',
            producer='fake', parse_mode='base', confidence='high', span=span('a.cpp'))
        second = replace(first, id=stable_id('second'), location=span('a.cpp', 2))
        unrelated = replace(first, id=stable_id('comment'), kind='comment')
        declaration = replace(first, id=stable_id('definition'), kind='macro_definition')
        normalizer = Mock(wraps=CppEvidenceNormalizer())
        selector = UsageAnchorSelector(self.context, self.knowledge, normalizer=normalizer)
        selected = selector.select(self.entity, (first, unrelated, second, declaration))
        self.assertEqual((first, second, declaration), selected)
        self.assertEqual((first, declaration), normalizer.normalize.call_args.args[1].evidence)
        self.assertIs(second, selected[1])

    def test_partial_normalization_retains_valid_roots_and_reuses_prepared_index(self):
        original = SimpleNamespace(id='a', kind='macro_expansion', value='X86')
        normalizer, demand = Mock(), Mock()
        facts = object()
        normalizer.normalize.return_value = StageResult(facts, CompletionStatus.PARTIAL)
        demand.select.return_value = (SimpleNamespace(matched_evidence_ids=('a', 'missing')),)
        selector = UsageAnchorSelector(self.context, self.knowledge, normalizer=normalizer, demand=demand)
        for _ in range(2):
            self.assertEqual((original,), selector.select(self.entity, (original,)))
        demand.prepare.assert_called_once_with(self.knowledge)
        demand.select.assert_called_with(facts, self.knowledge, prepared=demand.prepare.return_value)

    def test_composite_passes_scan_local_selector_to_cpp(self):
        cpp, build = Mock(), Mock()
        cpp.analyze.return_value = build.analyze.return_value = StageResult(FrontendSnapshot())
        frontend = CompositeProjectFrontend(cpp, build)
        workspace = WorkspaceSnapshot(Path('/tmp'), ('a.cpp',))
        result = frontend.analyze_with_knowledge(self.context, workspace, self.knowledge)
        self.assertIsNotNone(result.value)
        selector = cpp.analyze.call_args.kwargs['usage_selector']
        self.assertIs(self.context, selector.context)
        self.assertIs(self.knowledge, selector.knowledge)
        adapter = Mock()
        adapter.analyze_file.return_value = StageResult(())
        CppFrontend(adapter).analyze(self.context, workspace, usage_selector=selector)
        self.assertIs(selector, adapter.analyze_file.call_args.kwargs['usage_selector'])

    def test_adapter_uses_only_selected_anchors_during_same_tree_lifetime(self):
        root, source, positions, anchor, _ = fixture()
        selector = Mock()
        selector.select.return_value = ()
        selector.test_anchors.return_value = ()
        with patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Parser') as parser, patch(
            'kb_scanner.frontends.cpp.tree_sitter_adapter.Language'), patch(
            'kb_scanner.frontends.cpp.tree_sitter_adapter._enum_evidence', return_value=(anchor,)), patch(
            'kb_scanner.frontends.cpp.tree_sitter_adapter.inventory', side_effect=lambda *args: args[-2]), patch(
            'kb_scanner.frontends.cpp.tree_sitter_adapter.collect_usage', return_value=()) as collector:
            parser.return_value.parse.return_value = SimpleNamespace(root_node=root)
            parsed = TreeSitterCppAdapter()._parse_candidate(source, 'a.cpp', self.entity, 'cpp', 'suffix', False,
                usage_selector=selector)
        self.assertIn(anchor, parsed.evidence)
        self.assertEqual((), collector.call_args.args[-1])
        selector.select.assert_called_once()
        self.assertIs(self.entity, selector.select.call_args.args[0])
        parser.return_value.parse.assert_called_once_with(source)

    def test_runner_passes_loaded_knowledge_and_stops_at_each_failed_stage(self):
        from tests.test_core_pipeline import _RecordingStages, make_profile
        from kb_scanner.pipeline import StagedPipelineRunner
        from dataclasses import replace
        stages = _RecordingStages()
        frontend = SimpleNamespace(analyze_with_knowledge=Mock(return_value=StageResult(FrontendSnapshot())))
        runner = StagedPipelineRunner(replace(make_profile(stages), frontend=frontend))
        result = runner.run(self.context)
        self.assertTrue(result.success)
        args = frontend.analyze_with_knowledge.call_args.args
        self.assertIs(self.context, args[0])
        self.assertIsInstance(args[1], WorkspaceSnapshot)
        self.assertIsInstance(args[2], KnowledgeSnapshot)
        order = ('workspace', 'knowledge', 'frontend', 'normalizer', 'analyzer', 'detector', 'classifier', 'assessor', 'projector')
        for stop in order:
            with self.subTest(stop=stop):
                stages = _RecordingStages(stop_at=stop)
                result = StagedPipelineRunner(make_profile(stages)).run(self.context)
                self.assertFalse(result.success)
                self.assertEqual(CompletionStatus.UNAVAILABLE, result.status)
                self.assertEqual(list(order[:order.index(stop)+1]), stages.calls)
                self.assertEqual((), result.artifacts)


if __name__ == '__main__':
    unittest.main()
