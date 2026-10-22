"""Maintenance orchestration with fake extraction, pipeline and IO boundaries."""
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from kb_scanner.core import StageResult
from kb_scanner.knowledge.extractors import ExtractionResult
from kb_scanner.knowledge.schema import GeneratedFactV2Model
from tests.unit.compatible_cutover.support import graph


class RetainedMeasurementTests(unittest.TestCase):
    def test_graph_measurement_counts_and_cli_delegation(self):
        from scripts import measure_evidence_graph_qualification as m
        values = graph(Path('/p'))
        constructors = {'CppWorkspaceCollector': ('collect', values[1]), 'CppFrontend': ('analyze', values[3]),
                        'GeneratedFactsKnowledgeProvider': ('load', values[2]), 'CppEvidenceNormalizer': ('normalize', values[4]),
                        'EvidenceGraphAnalyzer': ('analyze', values[5]), 'LocalX86Detector': ('detect', values[6])}
        with ExitStack() as stack:
            for name, (method, snapshot) in constructors.items():
                stack.enter_context(patch.object(m, name, return_value=NS(**{method: lambda *_, s=snapshot: StageResult(value=s)})))
            measured = m.measure(Path('/fake'))
        self.assertEqual(1, measured['files'])
        self.assertEqual(1, measured['evidence'])
        self.assertEqual(1, measured['relations'])
        self.assertEqual([], measured['diagnostics'])
        with patch.object(m, 'measure', return_value={'files': 7}) as measure, patch('builtins.print') as output, patch.dict('os.environ', {'KB_SCANNER_AVX_FIXTURE': '/fake'}):
            self.assertEqual(0, m.main())
        self.assertEqual({'files': 7}, json.loads(output.call_args.args[0]))
        measure.assert_called_once_with(Path('/fake'))

    def test_knowledge_measurement_sample_limit_and_missing_fact(self):
        from scripts import measure_knowledge_qualification as m
        observations = [NS(kind='x86_target_feature', status='confirmed_local', metadata={'factId': str(i)}) for i in range(10)]
        observations += [NS(kind='ignored', status='unknown', metadata={}), NS(kind='x86_target_feature', status='unknown', metadata={})]
        facts = tuple(NS(id=str(i), canonical_value='x'*200) for i in range(10))
        values = {'workspace_collector': ('collect', NS(files=())), 'knowledge_provider': ('load', NS()),
                  'frontend': ('analyze', NS(evidence=())), 'normalizer': ('normalize', NS(facts=facts)),
                  'analyzer': ('analyze', NS()), 'detector': ('detect', NS(observations=observations))}
        profile = NS(**{name: NS(**{method: lambda *_, v=v: StageResult(value=v)}) for name, (method, v) in values.items()})
        with patch.object(m, 'create_knowledge_detection_qualification_profile', return_value=profile):
            measured = m.measure(Path('/fake'), Path('/rules'))
        self.assertEqual(12, measured['observations'])
        self.assertEqual(8, len(measured['samples']))
        self.assertEqual(160, len(measured['samples'][0]['value']))
        with patch('sys.argv', ['measure', '--rule-dir', '/r', '/p']), patch.object(m, 'measure', return_value={}) as measure, patch('builtins.print'):
            self.assertEqual(0, m.main())
        measure.assert_called_once_with(Path('/p'), Path('/r'))

    def test_refresh_builds_models_without_writing_real_compiler_facts(self):
        from scripts import refresh_knowledge_sources as m
        fact = GeneratedFactV2Model(factKind='registerNames', architectureFamily='x86', canonicalValue='rax', semanticScope='x86-only')
        extraction = ExtractionResult((fact,), ('input.tbl',), ('b'*64,))
        roots = tuple(Path('/'+p) for p in ('llvm', 'gcc', 'binutils', 'out'))
        with ExitStack() as stack:
            for name in ('extract_llvm', 'extract_gcc', 'extract_binutils'):
                stack.enter_context(patch.object(m, name, return_value=extraction))
            stack.enter_context(patch.object(Path, 'glob', return_value=iter(())))
            stack.enter_context(patch.object(m, '_sha', return_value='a'*64))
            write = stack.enter_context(patch.object(m, '_write'))
            m.refresh(*roots)
            self.assertEqual(6, write.call_count)
            self.assertEqual({'generated/binutils-2.42-x86.json', 'generated/gcc-14.2.0-x86-target.json', 'generated/llvm-18.1.8-x86.json', 'curated/source-references.json', 'curated/x86-migration-semantics.json', 'audit/candidate-decisions.json'}, {call.args[1] for call in write.call_args_list})
            with patch.object(m, 'extract_gcc', return_value=ExtractionResult()), self.assertRaises(RuntimeError):
                m.refresh(*roots)
        with patch.object(Path, 'read_bytes', return_value=b'data'):
            self.assertEqual(64, len(m._sha(Path('/fake'))))
        with patch.object(Path, 'mkdir'), patch.object(Path, 'write_bytes') as write, patch.object(m, 'render_model', return_value=b'{}'):
            m._write(Path('/fake'), 'nested/output.json', NS())
        write.assert_called_once_with(b'{}')
        with patch('sys.argv', ['refresh', '--llvm-root', '/llvm', '--gcc-root', '/gcc', '--binutils-root', '/binutils', '--output-root', '/out']), patch.object(m, 'refresh') as refresh:
            self.assertEqual(0, m.main())
        refresh.assert_called_once_with(*roots)
