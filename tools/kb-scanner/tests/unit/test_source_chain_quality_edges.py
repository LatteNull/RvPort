import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from kb_scanner.frontends.build import make
from kb_scanner.projection.v2.models import Break, ContextLine
from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator, V2ValidationError
from tests.unit.schema_v2_projection.support import report


class MakeBoundaryTests(unittest.TestCase):
    def test_unknown_nested_conditions_and_unsupported_expressions_are_retained(self):
        source = "ifeq $(UNKNOWN),x\nifdef X\nA = -mavx\nendif\ninclude $(MISSING)\ntarget: a.c\nendif\n"
        with patch.object(make, "Language"), patch.object(make, "Parser", return_value=NS(parse=lambda _: NS(root_node=NS(has_error=True)))):
            result = make.parse_make(source, "Makefile", "riscv64")
        self.assertTrue(result.partial)
        self.assertTrue(any(r.metadata.get("selectionStatus") == "unknown" for r in result.records))
        self.assertIsNone(make._evaluate_condition("ifeq", "one", {}, "riscv64")[0])
        self.assertIsNone(make._evaluate_condition("ifeq", "$(X),1", {}, "riscv64")[0])
        self.assertEqual("unknown", make._evaluate_expression("x", {}, "riscv64", make.MakeBudgets(max_expansions=1), 2).kind)

    def test_assignment_probe_and_derived_directory_literal_provenance(self):
        source = "A != uname -m\nB != unknown_command\nifdef ABSENT\nC = yes\nendif\nifeq (x,x)\nD = -lfoo\nendif\n"
        with patch.object(make, "Language"), patch.object(make, "Parser", return_value=NS(parse=lambda _: NS(root_node=NS(has_error=False)))):
            result = make.parse_make(source, "Makefile", "riscv64", make.MakeBudgets(max_expansions=1))
        self.assertEqual("riscv64", dict(result.variables)["A"].text)
        self.assertEqual("shell-assignment", dict(result.variables)["B"].reason)
        result = make._derived_records("() src/ -mavx $(X).c", 1, "() src/ -mavx $(X).c", {"reason": "unknown-variable:X", "selectionStatus": "unknown"}, literal_status="selected")
        self.assertEqual(["build_directory", "build_argument", "build_source"], [r.kind for r in result])
        self.assertNotIn("reason", result[0].metadata)
        self.assertEqual("unknown", result[-1].metadata["selectionStatus"])
        self.assertEqual("x86", make._role("avx"))
        self.assertEqual("generic", make._role("scalar"))


class SourceContractBoundaryTests(unittest.TestCase):
    def test_shared_extension_traversal_is_once_per_call_not_across_reports(self):
        validator = V2ReferentialIntegrityValidator()
        source = report().findings[0].fact.primaryLocation
        with patch.object(validator, '_extensions', wraps=validator._extensions) as visit:
            validator._extensions([source] * 100)
            self.assertLess(visit.call_count, 300)
        fact = report().findings[0].fact.model_copy(update={'extensions': {'org.rvport.kb-scanner.test': {}}})
        validator._extensions([fact, fact])
        fact.extensions['invalid namespace'] = {}
        with self.assertRaisesRegex(V2ValidationError, 'result.extension-namespace'):
            validator._extensions([fact, fact])
        # 相同字段的不同对象不能凭值相等复用，末尾非法对象仍被发现。
        with self.assertRaisesRegex(V2ValidationError, 'result.extension-namespace'):
            validator._extensions([source] * 100 + [fact])

    def test_context_budget_and_order_are_enforced_even_for_partial_context(self):
        validator = V2ReferentialIntegrityValidator()
        source = report().findings[0].fact.primaryLocation
        for update, rule in (({"lines": (ContextLine(line=2, text="ab"), ContextLine(line=1, text="ab"))}, "source.context-lines-ordered"),
                             ({"budget": source.context.budget.model_copy(update={"maxCharacters": 1})}, "source.context-budget"),
                             ({"highlights": (source.context.highlights[0].model_copy(update={"endColumn": 99999}),)}, "source.highlight-resolves"),
                             ({"lines": (), "highlights": ()}, "source.complete-context-has-highlight")):
            with self.subTest(rule=rule), self.assertRaisesRegex(V2ValidationError, rule):
                validator._source(source.model_copy(update={"context": source.context.model_copy(update=update)}))

    def test_path_state_break_candidate_and_sorting_contracts(self):
        validator = V2ReferentialIntegrityValidator()
        chain = report().findings[0].evidenceChain
        first = chain.primaryPath[0]
        steps = tuple(s.model_copy(update={"status": "unknown"}) if s.id == first else s for s in chain.steps)
        candidates = [(chain.model_copy(update={"primaryPath": ()}), "chain.primary-path-resolves"),
                      (chain.model_copy(update={"steps": steps}), "chain.complete-has-no-break"),
                      (chain.model_copy(update={"steps": tuple(reversed(chain.steps))}), "result.stable-order"),
                      (chain.model_copy(update={"status": "partial", "breaks": (Break(id="break", status="partial", reasonCode="missing_reference", stage="source", candidateStepIds=("absent",)),)}), "chain.break-references-resolve")]
        for value, rule in candidates:
            with self.subTest(rule=rule), self.assertRaisesRegex(V2ValidationError, rule):
                validator._chain(value)
        validator._chain(chain.model_copy(update={"impactStepIds": ()}))

    def test_finding_and_occurrence_sorting_reject_shuffled_collections(self):
        validator = V2ReferentialIntegrityValidator()
        value = report()
        finding = value.findings[0]
        with self.assertRaisesRegex(V2ValidationError, "result.stable-order"):
            validator.validate(value.model_copy(update={"findings": (finding.model_copy(update={"id": "z"}), finding.model_copy(update={"id": "a"}))}))
        occurrence = finding.occurrences[0]
        later = occurrence.model_copy(update={"id": "later", "location": occurrence.location.model_copy(update={"file": "zzz.c"})})
        with self.assertRaisesRegex(V2ValidationError, "result.stable-order"):
            validator.validate(value.model_copy(update={"findings": (finding.model_copy(update={"occurrences": (later, occurrence)}),)}))
