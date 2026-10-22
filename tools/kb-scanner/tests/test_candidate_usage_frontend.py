"""真实 grammar 组件验证，不计入隔离单元覆盖率。"""
import json
from pathlib import Path
import unittest

from kb_scanner.core import FrontendSnapshot, KnowledgeSnapshot, stable_id
from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from kb_scanner.analyzers.candidate_usage.demand import CandidateUsageDemand
from kb_scanner.analyzers.candidate_usage.session import UsageSession
from tests.unit.knowledge_detection.support import make_context


ROOT = Path(__file__).resolve().parents[1]


def analyze(source):
    entity = make_source_file_entity("usage.cpp", ("cpp",), "1")
    original = TreeSitterCppAdapter()._parse_candidate(source, "usage.cpp", entity, "cpp", "fixture", True)
    scopes = tuple(item for item in original.evidence if item.kind == "usage_scope")
    normalized = CppEvidenceNormalizer().normalize(make_context(Path("/tmp")), FrontendSnapshot(
        (entity,), original.evidence))
    if normalized.value is None:
        raise AssertionError(normalized.diagnostics)
    roots = CandidateUsageDemand().select(normalized.value, KnowledgeSnapshot(stable_id("empty"), "1"))
    session = UsageSession(normalized.value, roots)
    return original, scopes, normalized, roots, tuple(session.resolve(root) for root in roots)


class CandidateUsageFrontendTests(unittest.TestCase):
    def test_demanded_inventory_ignores_ordinary_functions_without_losing_base_facts(self):
        from kb_scanner.pipeline.usage_frontend import UsageAnchorSelector
        context = make_context(Path('/tmp'))
        entity = make_source_file_entity('usage.cpp', ('cpp',), '1')
        knowledge = KnowledgeSnapshot(stable_id('empty'), '1')
        source = '\n'.join(f'void f{i}() {{ enum E{i} {{ FORMAT_{name}=1 }}; int n=FORMAT_{name}; if(n==FORMAT_{name}) {{}} }}'
            for i, name in enumerate(('LOCAL', 'X86', 'LOCAL2', 'LOCAL3'))).encode()
        adapter = TreeSitterCppAdapter()
        baseline = adapter._parse_candidate(source, 'usage.cpp', entity, 'cpp', 'fixture', True)
        demanded = adapter._parse_candidate(source, 'usage.cpp', entity, 'cpp', 'fixture', True,
            usage_selector=UsageAnchorSelector(context, knowledge))
        self.assertEqual(4, sum(item.kind == 'usage_scope' for item in baseline.evidence))
        scopes = [item for item in demanded.evidence if item.kind == 'usage_scope']
        self.assertEqual(1, len(scopes))
        self.assertEqual(2, scopes[0].location.start.line)
        self.assertIn(scopes[0], baseline.evidence)
        supplemental = {'usage_scope', 'test_content', 'test_structure'}
        self.assertEqual(tuple(item for item in baseline.evidence if item.kind not in supplemental),
                         tuple(item for item in demanded.evidence if item.kind not in supplemental))
        self.assertEqual(1, sum(e.kind == 'test_structure' for e in demanded.evidence))
        snapshots = [CppEvidenceNormalizer().normalize(context, FrontendSnapshot((entity,), parse.evidence)).value
                     for parse in (baseline, demanded)]
        self.assertEqual(tuple(f for f in snapshots[0].facts if f.kind not in supplemental),
                         tuple(f for f in snapshots[1].facts if f.kind not in supplemental))
        self.assertEqual(CandidateUsageDemand().select(snapshots[0], knowledge),
                         CandidateUsageDemand().select(snapshots[1], knowledge))

    def test_real_parser_local_closed_data_and_escape_oracle(self):
        oracle = json.loads((ROOT / "tests/fixtures/candidate-usage-oracle.json").read_text())
        for case in oracle["cases"]:
            with self.subTest(case=case["name"]):
                original, scopes, normalized, roots, results = analyze(case["source"].encode())
                self.assertTrue(set(item.id for item in original.evidence).issubset(
                    item.id for item in normalized.value.evidence))
                if case["expected"] == "excluded":
                    self.assertTrue(roots)
                    self.assertTrue(scopes)
                    self.assertTrue(any(result["status"] == "complete" for result in results), results)
                else:
                    self.assertTrue(all(result["status"] == "unknown" for result in results), results)

    def test_utf8_crlf_and_name_mutation_preserve_structural_decision(self):
        case = json.loads((ROOT / "tests/fixtures/candidate-usage-oracle.json").read_text())["cases"][0]
        source = ("// 中文\r\n"+case["source"].replace("FORMAT_X86", "FORMAT_I386")).encode()
        _, scopes, _, roots, results = analyze(source)
        self.assertTrue(roots)
        self.assertEqual(2, scopes[0].location.start.line)
        self.assertTrue(all(result["status"] == "complete" for result in results), results)
