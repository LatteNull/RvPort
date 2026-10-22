"""Fake syntax trees: exercise enum/asm integration without native parsing."""
from pathlib import Path
import unittest

from kb_scanner.core import FrontendSnapshot, KnowledgeSnapshot, KnowledgeEntry, stable_id
from kb_scanner.frontends.cpp.tree_sitter_adapter import _enum_evidence
from kb_scanner.frontends.cpp.source_positions import SourceByteIndex
from kb_scanner.analyzers.evidence_graph import EvidenceGraphAnalyzer
from kb_scanner.detectors.local import LocalX86Detector
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from tests.unit.frontends.cpp.test_tree_sitter_adapter import Node
from tests.unit.knowledge_detection.support import make_context, make_entity, make_evidence


class FakeEnumGraphTests(unittest.TestCase):
    def test_fake_selection_shapes_bind_enum_and_link_downstream_asm(self):
        for construct in ('if', 'if constexpr', 'switch', 'case'):
            for partial in (False, True):
                for qualified in (False, True):
                    declaration = 'enum class Backend { avx2 }; '
                    reference = 'Backend::avx2' if qualified else 'avx2'
                    source = (declaration + construct + ' (' + reference + ') { asm("pause"); }').encode()
                    decl_name = Node('type_identifier', 11, 18)
                    member = Node('identifier', 21, 25)
                    enum = Node('enum_specifier', 0, len(declaration), children=(decl_name, Node('enumerator', 21, 25, children=(member,), fields={'name': member})), fields={'name': decl_name})
                    start = source.index(reference.encode(), len(declaration))
                    terminal = Node('identifier', start + (9 if qualified else 0), start + len(reference))
                    ref = Node('qualified_identifier', start, start + len(reference), children=(terminal,), fields={'scope': Node('namespace_identifier', start, start + 7), 'name': terminal}) if qualified else terminal
                    condition = Node('condition_clause', start - 1, start + len(reference) + 1, children=(ref,))
                    selection = Node('case_statement' if construct == 'case' else 'switch_statement' if construct == 'switch' else 'if_statement', len(declaration), len(source), children=(condition,), fields={'value' if construct == 'case' else 'condition': condition})
                    root = Node('translation_unit', 0, len(source), children=(enum, Node('template_declaration', len(declaration), len(source), children=(selection,))))
                    subject = make_entity()
                    values = _enum_evidence(root, source, SourceByteIndex.build(subject.name, source), subject.id, 'fake', 'cpp', 'suffix', partial)
                    self.assertEqual(4, len(values))
                    self.assertEqual('partial' if partial else 'complete', values[2].metadata['bindingStatus'])
                    self.assertTrue(values[2].metadata['templateDependent'])
                    asm = make_evidence(subject, 'inline_asm', 'asm("pause")')
                    snapshot = FrontendSnapshot((subject,), (*values, asm))
                    ctx = make_context(Path('/tmp'))
                    facts = CppEvidenceNormalizer().normalize(ctx, snapshot).value
                    knowledge = KnowledgeSnapshot(stable_id('k'), '1', entries=(KnowledgeEntry(stable_id('pause'), 'assemblyInstructions', 'x86', 'pause', (stable_id('source'),)),))
                    analysis = EvidenceGraphAnalyzer().analyze(ctx, facts, knowledge).value
                    self.assertIsNotNone(analysis)
                    self.assertTrue(any(x.metadata.get('enumDependency') for x in analysis.relations))
                    detections = LocalX86Detector(deferred_capabilities={}).detect(ctx, facts, analysis, knowledge).value
                    self.assertTrue(detections.observations)
