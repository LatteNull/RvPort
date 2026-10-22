from dataclasses import replace
from pathlib import Path
import unittest

from kb_scanner.analyzers.architecture_guards import foreign_guard_proof, required_foreign, _matching_end
from kb_scanner.analyzers.evidence_graph import EvidenceGraphAnalyzer, _branch_role
from kb_scanner.core import stable_id
from .support import file, evidence, snapshot, knowledge, context


class ArchitectureGuardTests(unittest.TestCase):
    def test_boolean_necessity_not_substring_or_negation(self):
        for text in ('__aarch64__', 'defined __arm__', '(defined(_M_ARM64))', '(__arm__ && OTHER)', '__arm__ || __aarch64__', '__aarch64__ /* hi */ && \\\n+ OTHER'):
            self.assertTrue(required_foreign(text), text)
        for text in ('!defined(__arm__)', '(__arm__ || __x86_64__)', 'ARMCRC32', '__arm__ == 0', 'OTHER', '(__arm__', '__arm__ || !OTHER', '__riscv'):
            self.assertFalse(required_foreign(text), text)
        self.assertEqual(-1, _matching_end('(x'))

    def inputs(self):
        f = file('a.c')
        parent = evidence(f, 'preprocessor_condition', 'defined(__aarch64__) && defined(EXTRA)', 1, end_line=4, metadata={'nodeType': 'preproc_if'})
        define = evidence(f, 'macro_definition', 'ARMCRC32', 2)
        guard = evidence(f, 'preprocessor_condition', 'ARMCRC32', 8, end_line=20, metadata={'nodeType': 'preproc_ifdef'})
        asm = evidence(f, 'inline_asm', 'asm("mystery")', 10)
        return f, parent, define, guard, asm

    def test_macro_provenance_is_required_and_attached_to_guard(self):
        f, parent, define, guard, asm = self.inputs()
        items = (parent, define, guard, asm)
        self.assertEqual({parent.id, define.id, guard.id}, set(foreign_guard_proof(guard, items)))
        result = EvidenceGraphAnalyzer().analyze(context(Path('/tmp')), snapshot(f, evidence_items=items), knowledge()).value
        guards = [x for x in result.relations if x.kind == 'guarded_by' and asm.id in x.evidence_ids]
        self.assertEqual(1, len(guards))
        self.assertEqual('foreign', guards[0].metadata['architectureDisposition'])
        self.assertTrue({parent.id, define.id}.issubset(guards[0].evidence_ids))
        unrelated_undef = evidence(f, 'macro_expansion', '#undef', 5, metadata={'macroUndefName': 'W'})
        self.assertTrue(foreign_guard_proof(guard, (*items, unrelated_undef)))
        self.assertFalse(foreign_guard_proof(guard, (*items, replace(unrelated_undef, metadata={'macroUndefName': 'ARMCRC32'}))))
        self.assertFalse(foreign_guard_proof(parent, (*items, replace(define, value='__aarch64__'))))
        self.assertFalse(foreign_guard_proof(parent, (*items, replace(unrelated_undef, metadata={'macroUndefName': '__aarch64__'}))))

    def test_mixed_unknown_negation_and_elif_do_not_borrow_another_branch(self):
        for expression, role in (('__x86_64__ || __aarch64__', 'x86'), ('__x86_64__ || FEATURE', 'unknown'), ('__x86_64__ && FEATURE', 'x86'), ('!__x86_64__', 'unknown')):
            self.assertEqual(role, _branch_role(expression, knowledge(), fallback=False)[0])
        f, parent, define, guard, asm = self.inputs()
        root = replace(parent, location=guard.location, value='FEATURE')
        branch = replace(guard, id=stable_id('elif'), metadata={'nodeType': 'preproc_elif'}, value='__arm__', location=replace(guard.location, start=replace(guard.location.start, line=9)))
        result = EvidenceGraphAnalyzer().analyze(context(Path('/tmp')), snapshot(f, evidence_items=(root, branch, asm)), knowledge()).value
        self.assertTrue(any(x.kind == 'guarded_by' and asm.id in x.evidence_ids and x.metadata.get('architectureDisposition') == 'foreign' for x in result.relations))

    def test_foreign_guard_confidence_is_local_not_whole_file(self):
        f, parent, define, guard, asm = self.inputs()
        originals = (parent, define, guard, asm)
        complete = tuple(replace(x, confidence='medium', metadata={**x.metadata, 'structureComplete': True}) for x in originals)
        for items, expected in ((complete, 'complete'), (tuple(replace(x, metadata={**x.metadata, 'structureComplete': False}) if x.id == parent.id else x for x in complete), 'partial')):
            result = EvidenceGraphAnalyzer().analyze(context(Path('/tmp')), snapshot(f, evidence_items=items), knowledge()).value
            links = [x for x in result.relations if x.kind == 'guarded_by' and asm.id in x.evidence_ids]
            self.assertEqual(expected, links[0].status)

    def test_ambiguous_forward_else_undef_cycles_and_incomplete_guards_remain_unknown(self):
        f, parent, define, guard, asm = self.inputs()
        base = (parent, define, guard)
        cases = [(), (define, guard), (parent, guard), base + (evidence(f, 'macro_definition', 'ARMCRC32', 6),),
                 (parent, replace(define, location=asm.location), guard),
                 (replace(parent, kind='preprocessor_branch'), define, guard),
                 (replace(parent, metadata={'nodeType': 'preproc_elif'}), define, guard),
                 base + (evidence(f, 'macro_expansion', '#undef', 5),),
                 (replace(parent, value='ARMCRC32'), define, guard)]
        for items in cases:
            self.assertEqual((), foreign_guard_proof(guard, items), items)
        for modified in (replace(guard, location=None), replace(guard, metadata={'conditionNegated': True}), replace(guard, metadata={'nodeType': 'preproc_ifndef'})):
            self.assertEqual((), foreign_guard_proof(modified, base))
        self.assertEqual((), foreign_guard_proof(guard, base, frozenset({guard.id})))
        self.assertEqual((), foreign_guard_proof(guard, base, frozenset(str(i) for i in range(8))))

    def test_asm_attribute_link_smallest_branch_and_partial_not_complete(self):
        f, parent, define, guard, asm = self.inputs()
        outer = replace(guard, value='__aarch64__', location=replace(guard.location, end=replace(guard.location.end, line=40)))
        inner = evidence(f, 'preprocessor_condition', 'UNRESOLVED', 9, end_line=15, metadata={'nodeType': 'preproc_if'})
        attr = replace(asm, id=stable_id('attr'), kind='declaration_attribute')
        result = EvidenceGraphAnalyzer().analyze(context(Path('/tmp')), snapshot(f, evidence_items=(outer, inner, asm, attr)), knowledge()).value
        for identifier in (asm.id, attr.id):
            links = [x for x in result.relations if x.kind == 'guarded_by' and identifier in x.evidence_ids]
            self.assertEqual(1, len(links))
            self.assertIn(inner.id, links[0].evidence_ids)
            self.assertEqual('unknown', links[0].metadata['architectureDisposition'])
