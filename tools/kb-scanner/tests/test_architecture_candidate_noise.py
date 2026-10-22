from __future__ import annotations

import unittest
import tempfile
import json
from collections import Counter
from pathlib import Path
from time import monotonic

from kb_scanner.analyzers import EvidenceGraphAnalyzer
from kb_scanner.classifiers.migration import MigrationClassifier
from kb_scanner.detectors.local import LocalX86Detector
from kb_scanner.frontends.cpp import CppFrontend, CppWorkspaceCollector
from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from kb_scanner.knowledge.provider import GeneratedFactsKnowledgeProvider
from kb_scanner.normalization import CppEvidenceNormalizer
from tests.unit.knowledge_detection.support import make_context
from tests.test_architecture_enum_analysis import scan

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/architecture-candidate-noise"


class ArchitectureCandidateNoiseTests(unittest.TestCase):
    def test_inventory_explicitly_maps_changed_modules_and_isolated_gate(self):
        inventory = json.loads((ROOT / 'tests/architecture-candidate-noise-test-inventory.json').read_text())
        expected = {'frontends/cpp/tree_sitter_adapter.py', 'analyzers/evidence_graph.py', 'analyzers/architecture_guards.py', 'normalization/cpp.py', 'detectors/local.py', 'core/candidate_contract.py', 'classifiers/migration.py', 'classifiers/policy.py', 'projection/projector.py', 'projection/v2/projector.py'}
        self.assertEqual(expected, set(inventory['modules']))
        self.assertEqual({'linePercent': 90, 'branchPercent': 80}, inventory['coverageThresholds'])
        for name, mapping in inventory['modules'].items():
            self.assertTrue((ROOT / 'kb_scanner' / name).is_file())
            self.assertTrue((ROOT / mapping['unit']).is_file())
        self.assertTrue((ROOT / 'docs/analysis-capabilities.md').is_file())

    def test_locked_c_and_cpp_grammars_keep_whole_asm_and_distinct_columns(self):
        source = (FIXTURE / 'zlib-shape.c').read_bytes()
        entity = make_source_file_entity('test.c', ('c', 'cpp'), '1')
        for language in ('c', 'cpp'):
            result = TreeSitterCppAdapter()._parse_candidate(source, 'test.c', entity, language, 'test', False)
            self.assertEqual(10, sum(x.kind == 'inline_asm' for x in result.evidence))
            self.assertEqual(2, sum(x.kind == 'declaration_attribute' for x in result.evidence))
            same_line = TreeSitterCppAdapter()._parse_candidate(b'void f() { asm("one"); asm("two"); }', 'test.c', entity, language, 'test', False)
            asm = [x for x in same_line.evidence if x.kind == 'inline_asm']
            self.assertEqual(2, len(asm))
            self.assertNotEqual(asm[0].location.start.column, asm[1].location.start.column)
            negated = TreeSitterCppAdapter()._parse_candidate(b'#ifndef __aarch64__\nvoid f() { asm("unknown"); }\n#endif\n', 'test.c', entity, language, 'test', False)
            self.assertTrue(next(x for x in negated.evidence if x.kind == 'preprocessor_condition').metadata['conditionNegated'])

    def test_staged_zlib_counts_and_guards(self):
        start = monotonic()
        context = make_context(FIXTURE, rule_dir=ROOT / "rulesets/riscv-porting")
        knowledge = GeneratedFactsKnowledgeProvider().load(context).value
        workspace = CppWorkspaceCollector().collect(context).value
        frontend = CppFrontend().analyze(context, workspace).value
        facts = CppEvidenceNormalizer().normalize(context, frontend).value
        analysis = EvidenceGraphAnalyzer().analyze(context, facts, knowledge).value
        detection = LocalX86Detector(deferred_capabilities={}).detect(context, facts, analysis, knowledge).value
        classified = MigrationClassifier().classify(context, detection, analysis).value
        counts = Counter(item.kind for item in frontend.evidence)
        self.assertEqual(10, counts['inline_asm'], counts)
        self.assertEqual(2, counts['declaration_attribute'])
        candidates = [item for item in detection.observations if item.kind == 'inline_asm_candidate']
        self.assertEqual(1, len(candidates), Counter(item.kind for item in detection.observations))
        self.assertEqual('unclassified_inline_asm', candidates[0].metadata['candidateBasis'])
        self.assertFalse(any(item.kind == 'target_attribute_candidate' for item in detection.observations))
        self.assertTrue(any(item.kind == 'x86_target_feature' for item in detection.observations))
        for evidence in frontend.evidence:
            if evidence.kind == 'inline_asm' and 'crc32x' in evidence.value:
                self.assertTrue(any(item.kind == 'guarded_by' and evidence.id in item.evidence_ids for item in analysis.relations))
        self.assertLess(len(frontend.evidence), 90)
        self.assertLess(len(detection.observations), 12)
        self.assertLess(len(classified.classifications), 12)
        # The same __x86_64__ condition is fully covered by its confirmed macro
        # observation. Only the duplicate candidate disappears, never the fact.
        self.assertFalse(any(item.kind == 'architecture_identifier_candidate' for item in detection.observations))
        # accelerated owns the existing target attribute; one structural fact,
        # no extra migration observation and no change to the foreign asm filter.
        self.assertEqual(['accelerated'],[e.value for e in frontend.evidence if e.kind=='function_declaration'])
        # Four anchored function spans plus one bounded content inventory are
        # additional structure, never additional migration observations.
        self.assertEqual(4, counts['test_structure'])
        self.assertEqual(1, counts['test_content'])
        self.assertEqual((35, 35, 3, 3), (len(frontend.evidence), len(facts.facts), len(detection.observations), len(classified.classifications)))
        self.assertLess(monotonic() - start, 60)

    def test_unrelated_parse_error_and_undef_do_not_poison_arm_guard(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'recovery.c').write_text('#undef W\n#if defined(__aarch64__) && defined(W) && W == 8\n#define ARMCRC32\n#endif\n#ifdef ARMCRC32\nvoid f(void) { __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(value)); }\n#endif\nint broken( {\n')
            ctx = make_context(root, rule_dir=ROOT / 'rulesets/riscv-porting')
            frontend = CppFrontend().analyze(ctx, CppWorkspaceCollector().collect(ctx).value)
            self.assertTrue(any(x.code == 'tree-sitter.partial-parse' for x in frontend.diagnostics))
            knowledge = GeneratedFactsKnowledgeProvider().load(ctx).value
            facts = CppEvidenceNormalizer().normalize(ctx, frontend.value).value
            analysis = EvidenceGraphAnalyzer().analyze(ctx, facts, knowledge).value
            detection = LocalX86Detector(deferred_capabilities={}).detect(ctx, facts, analysis, knowledge).value
            self.assertEqual(1, sum(x.kind == 'inline_asm' for x in frontend.value.evidence))
            self.assertFalse(any(x.kind == 'inline_asm_candidate' for x in detection.observations))

    def test_default_v2_explicit_v2_and_v1_reports(self):
        for version in (None, '2.0', '1.0'):
            with self.subTest(version=version):
                output, result, report = scan(FIXTURE, version)
                self.addCleanup(output.cleanup)
                self.assertEqual(0, result.exit_code)
                self.assertEqual({'scan-result.json', 'scan-report.html', 'scan.log'}, {x.name for x in result.artifacts})
                # Filter only finding roots; source context deliberately retains neighboring code.
                findings = report['findings']
                html = (Path(output.name) / 'scan-report.html').read_text()
                log = (Path(output.name) / 'scan.log').read_text()
                symbols = [x['symbol'] if version == '1.0' else x['fact']['matchedText'] for x in findings]
                self.assertFalse(any('no_sanitize' in (x or '') or 'crc32x' in (x or '') for x in symbols))
                self.assertEqual(3, len(findings))
                if version != '1.0':
                    self.assertEqual('2.0', report['schemaVersion'])
                    self.assertEqual(3, html.count('<article>'))
                    self.assertEqual(3, sum(line.startswith('finding ') for line in log.splitlines()))
                    self.assertIn('findings=3', log)
                    self.assertEqual(len(findings), report['summary']['findings'])
                    unknown = [x for x in findings if x['conclusion']['findingType'] == 'inline_asm_candidate']
                    self.assertEqual(1, len(unknown))
                    self.assertEqual('medium', unknown[0]['conclusion']['severity'])
                    self.assertFalse(unknown[0]['conclusion']['actionable'])
                    self.assertFalse(unknown[0]['conclusion']['blocking'])
                    root = next(s for s in unknown[0]['evidenceChain']['steps'] if s['id'] == unknown[0]['evidenceChain']['rootStepId'])
                    self.assertIn('vendor_mystery', root['symbol'])
                    self.assertEqual(26, root['source']['span']['start']['line'])
                    self.assertEqual(1, report['summary']['inactiveOrGuarded'])
                else:
                    self.assertEqual('1.0', report['schemaVersion'])
                    self.assertIn('Finding：3', html)
                    self.assertNotIn('no_sanitize', log)
                    self.assertNotIn('crc32x', log)


if __name__ == '__main__':
    unittest.main()
