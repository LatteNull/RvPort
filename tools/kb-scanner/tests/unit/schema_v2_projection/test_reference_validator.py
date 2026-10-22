from __future__ import annotations

import unittest

from kb_scanner.projection.v2.models import Break
from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator, V2ValidationError
from .support import report


class ReferenceValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = V2ReferentialIntegrityValidator()

    def test_complete_fixture_is_valid(self):
        self.validator.validate(report())

    def test_primary_occurrence_and_edge_fail_with_stable_rules(self):
        value = report()
        finding = value.findings[0].model_copy(update={"primaryOccurrenceId": "missing"})
        with self.assertRaisesRegex(V2ValidationError, "finding.primary-occurrence-resolves"):
            self.validator.validate(value.model_copy(update={"findings": (finding,)}))
        chain = value.findings[0].evidenceChain
        edge = chain.edges[0].model_copy(update={"fromStepId": "missing"})
        broken_chain = chain.model_copy(update={"edges": (edge, *chain.edges[1:])})
        with self.assertRaisesRegex(V2ValidationError, "chain.edge-endpoints-resolve"):
            self.validator.validate(value.model_copy(update={"findings": (value.findings[0].model_copy(update={"evidenceChain": broken_chain}),)}))

    def test_incomplete_chain_requires_break_and_extensions_are_namespaced(self):
        value = report()
        chain = value.findings[0].evidenceChain.model_copy(update={"status": "partial", "reasonCodes": ("missing_input",)})
        with self.assertRaisesRegex(V2ValidationError, "chain.incomplete-has-break"):
            self.validator.validate(value.model_copy(update={"findings": (value.findings[0].model_copy(update={"evidenceChain": chain}),)}))
        with self.assertRaisesRegex(V2ValidationError, "result.extension-namespace"):
            self.validator.validate(value.model_copy(update={"extensions": {"free": {}}}))

    def test_chain_reference_source_and_order_rules(self):
        value = report()
        finding = value.findings[0]
        chain = finding.evidenceChain
        cases = []
        cases.append(("chain.root-step-resolves", chain.model_copy(update={"rootStepId": "missing"})))
        cases.append(("chain.primary-path-resolves", chain.model_copy(update={"primaryPath": (chain.primaryPath[0], chain.primaryPath[0])})))
        cases.append(("chain.primary-path-connected", chain.model_copy(update={"edges": chain.edges[1:]})))
        cases.append(("chain.impact-step-resolves", chain.model_copy(update={"impactStepIds": (chain.rootStepId,)})))
        invalid_break = Break(id="break-x", status="partial", reasonCode="missing_reference", stage="x", fromStepId="missing", candidateStepIds=())
        cases.append(("chain.break-references-resolve", chain.model_copy(update={"status": "partial", "reasonCodes": ("missing_reference",), "breaks": (invalid_break,)})))
        cases.append(("chain.complete-has-no-break", chain.model_copy(update={"breaks": (Break(id="break-x", status="partial", reasonCode="missing_input", stage="x", candidateStepIds=()),)})))
        for rule, candidate in cases:
            with self.subTest(rule=rule), self.assertRaisesRegex(V2ValidationError, rule):
                self.validator.validate(value.model_copy(update={"findings": (finding.model_copy(update={"evidenceChain": candidate}),)}))

    def test_code_non_code_and_source_rules(self):
        value = report()
        finding = value.findings[0]
        chain = finding.evidenceChain
        code = chain.steps[0].model_copy(update={"source": None})
        with self.assertRaisesRegex(V2ValidationError, "step.code-kind-has-source"):
            self.validator.validate(value.model_copy(update={"findings": (finding.model_copy(update={"evidenceChain": chain.model_copy(update={"steps": (code, *chain.steps[1:])})}),)}))
        non_code_index = next(i for i, step in enumerate(chain.steps) if step.kind == "classification")
        steps = list(chain.steps)
        steps[non_code_index] = steps[non_code_index].model_copy(update={"source": finding.fact.primaryLocation})
        with self.assertRaisesRegex(V2ValidationError, "step.non-code-kind-has-no-source"):
            self.validator.validate(value.model_copy(update={"findings": (finding.model_copy(update={"evidenceChain": chain.model_copy(update={"steps": tuple(steps)})}),)}))
        source = finding.fact.primaryLocation.model_copy(update={"file": "../escape.c"})
        with self.assertRaisesRegex(V2ValidationError, "source.path-project-relative"):
            self.validator.validate(value.model_copy(update={"findings": (finding.model_copy(update={"fact": finding.fact.model_copy(update={"primaryLocation": source})}),)}))

        knowledge_index = next(i for i, step in enumerate(chain.steps) if step.kind == "knowledge_match")
        steps = list(chain.steps)
        steps[knowledge_index] = steps[knowledge_index].model_copy(update={"knowledge": None})
        with self.assertRaisesRegex(V2ValidationError, "step.knowledge-projection-complete"):
            self.validator.validate(value.model_copy(update={"findings": (finding.model_copy(update={"evidenceChain": chain.model_copy(update={"steps": tuple(steps)})}),)}))
