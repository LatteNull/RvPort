from __future__ import annotations

import copy
import hashlib
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tests.schema_v2_contract import (
    FIXTURE_ROOT,
    ROOT,
    apply_operations,
    canonical_json,
    load_json,
    materialize_variants,
    reference_errors,
    validate_document,
)


class SchemaV2DesignContractTest(unittest.TestCase):
    def test_schema_is_valid(self) -> None:
        Draft202012Validator.check_schema(load_json(ROOT / "schemas" / "scan-result-v2.schema.json"))

    def test_all_completion_state_examples_are_valid(self) -> None:
        variants = materialize_variants(FIXTURE_ROOT / "state-variants.json")
        self.assertEqual({"complete", "partial", "ambiguous", "inactive", "unknown"}, set(variants))
        for name, document in variants.items():
            with self.subTest(name=name):
                self.assertEqual(name, document["findings"][0]["evidenceChain"]["status"])
                self.assertEqual([], validate_document(document))
                if name in {"partial", "ambiguous", "unknown"}:
                    self.assertTrue(document["findings"][0]["evidenceChain"]["breaks"])
                    self.assertFalse(document["findings"][0]["conclusion"]["blocking"] if name != "partial" else False)

    def test_directed_invalid_cases(self) -> None:
        manifest = load_json(FIXTURE_ROOT / "invalid-cases.json")
        base = load_json(FIXTURE_ROOT / manifest["base"])
        for case in manifest["cases"]:
            with self.subTest(name=case["name"]):
                document = apply_operations(base, case["operations"])
                self.assertIn(case["expectedRule"], validate_document(document))

    def test_historical_example_is_readable_with_self_contained_source_context(self) -> None:
        document = load_json(FIXTURE_ROOT / "avx-macro-finding.json")
        self.assertEqual([], validate_document(document))
        finding = document["findings"][0]
        self.assertNotIn("Catalog", document)
        self.assertNotIn("Explanation", document)
        self.assertNotIn("trace", finding)
        chain = finding["evidenceChain"]
        self.assertEqual(
            [
                "compiler_flag",
                "macro_invocation",
                "macro_definition",
                "macro_replacement",
                "knowledge_match",
                "classification",
                "assessment",
            ],
            [{step["id"]: step for step in chain["steps"]}[step_id]["kind"] for step_id in chain["primaryPath"]],
        )
        self.assertEqual(8, len(chain["steps"]))
        self.assertEqual(2, chain["budget"]["paths"])

        sources = [finding["fact"]["primaryLocation"]]
        sources.extend(occurrence["location"] for occurrence in finding["occurrences"])
        sources.extend(step["source"] for step in chain["steps"] if "source" in step)
        for source in sources:
            file_lines = {line["line"]: line["text"] for line in source["context"]["lines"]}
            for highlight in source["context"]["highlights"]:
                actual_line = file_lines[highlight["line"]]
                token = actual_line[highlight["startColumn"] - 1 : highlight["endColumn"] - 1]
                self.assertTrue(token.startswith(("-mavx", "_mm256_")), token)

    def test_compiler_fact_files_are_frozen(self) -> None:
        baseline = load_json(ROOT / "tests/fixtures/open-source-regression-baseline.json")
        for expected in baseline["compilerFactFiles"]:
            with self.subTest(path=expected["path"]):
                path = ROOT / expected["path"]
                raw = path.read_bytes()
                data = load_json(path)
                self.assertEqual(expected["bytes"], len(raw))
                self.assertEqual(expected["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(expected["counts"], {key: len(data[key]) for key in expected["counts"]})
                self.assertEqual(expected["source"], data["source"])

    def test_v2_is_projected_directly_from_staged_snapshots(self) -> None:
        contract = load_json(FIXTURE_ROOT / "contract-differences.json")
        model = contract["generationModel"]
        self.assertEqual("independent-projectors-from-staged-snapshots", model["kind"])
        self.assertEqual({"Evidence", "Relation", "ProofPath", "Classification", "Assessment"}, set(model["snapshotInputs"]))
        self.assertEqual(["v1", "v2"], model["projectors"])
        self.assertFalse(model["v2ReadsV1Result"])
        self.assertFalse(model["v2ConvertsV1Finding"])
        self.assertFalse(model["v2ConvertsV1Trace"])
        self.assertFalse(model["v2FallsBackToV1"])

    def test_consumer_contract_uses_one_self_contained_finding(self) -> None:
        contract = load_json(FIXTURE_ROOT / "consumer-contract.json")
        detail = contract["detailProjection"]
        self.assertEqual("one findings[] object", detail["source"])
        self.assertFalse(detail["externalAssemblyRequired"])
        self.assertIn("evidenceChain.primaryPath", detail["initialRenderOrder"])
        self.assertEqual(["Catalog", "Explanation", "trace"], detail["mustNotLoad"])

    def test_rollout_contract_uses_v2_default_without_fallback(self) -> None:
        contract = load_json(FIXTURE_ROOT / "rollout-contract.json")
        self.assertEqual(1, contract["selection"]["cardinalityPerScan"])
        self.assertEqual("2.0", contract["selection"]["defaultSchemaVersion"])
        self.assertEqual("staged-snapshots", contract["selection"]["projectorInput"])
        self.assertTrue(contract["selection"]["projectorsAreIndependent"])
        self.assertFalse(contract["failure"]["v2ProjectionFailureFallsBackToV1"])
        self.assertEqual(["scan-result.json", "scan-report.html", "scan.log"], contract["artifacts"])
        self.assertFalse(contract["rollback"]["requiresV2ToV1Conversion"])

    def test_canonicalization_is_deterministic(self) -> None:
        document = load_json(FIXTURE_ROOT / "avx-macro-finding.json")
        perturbed = copy.deepcopy(document)
        perturbed["findings"][0]["evidenceChain"]["steps"].reverse()
        perturbed["findings"][0]["evidenceChain"]["edges"].reverse()
        for step in perturbed["findings"][0]["evidenceChain"]["steps"]:
            if "source" in step:
                step["source"]["context"]["lines"].reverse()
        self.assertIn("result.stable-order", reference_errors(perturbed))
        self.assertEqual(canonical_json(document), canonical_json(perturbed))

    def test_vocabulary_matches_schema_and_reference_rules(self) -> None:
        vocabulary = load_json(ROOT / "schemas" / "scan-result-v2-vocabulary.json")
        schema = load_json(ROOT / "schemas" / "scan-result-v2.schema.json")
        rules = load_json(ROOT / "schemas" / "scan-result-v2-reference-rules.json")
        self.assertEqual(vocabulary["completionStatuses"], schema["$defs"]["completionStatus"]["enum"])
        self.assertEqual(vocabulary["selectionStatuses"], schema["$defs"]["selectionStatus"]["enum"])
        self.assertEqual(vocabulary["stepKinds"], schema["$defs"]["step"]["properties"]["kind"]["enum"])
        self.assertEqual(vocabulary["edgeKinds"], schema["$defs"]["edge"]["properties"]["kind"]["enum"])
        self.assertEqual(vocabulary["reasonCodes"], schema["$defs"]["reasonCode"]["enum"])
        self.assertEqual(
            {rule["id"] for rule in rules["rules"]},
            {
                "result.finding-id-unique", "finding.occurrence-id-unique", "finding.primary-occurrence-resolves",
                "chain.step-id-unique", "chain.root-step-resolves", "chain.primary-path-resolves",
                "chain.primary-path-connected", "chain.edge-endpoints-resolve", "chain.impact-step-resolves",
                "chain.break-references-resolve", "chain.complete-has-no-break", "chain.incomplete-has-break",
                "source.path-project-relative", "source.context-lines-ordered", "source.highlight-resolves",
                "source.complete-context-has-highlight", "source.context-budget", "step.code-kind-has-source",
                "step.non-code-kind-has-no-source", "step.knowledge-projection-complete",
                "result.static-scope", "result.stable-order",
            },
        )

    def test_source_chain_revision_has_new_defaults_and_accepts_historical_kinds(self):
        vocabulary = load_json(ROOT / "schemas/scan-result-v2-vocabulary.json")
        self.assertEqual(20, vocabulary["contextBudget"]["defaultBeforeLines"])
        self.assertEqual(20, vocabulary["contextBudget"]["defaultAfterLines"])
        self.assertEqual(256, vocabulary["contextBudget"]["maximumLinesPerLocation"])
        self.assertEqual(65536, vocabulary["contextBudget"]["maximumCharactersPerLocation"])
        self.assertEqual([], vocabulary["sourceChainRevision"]["impactStepIds"])
        self.assertTrue(vocabulary["sourceChainRevision"]["historicalStageChainsAccepted"])

    def test_current_source_chain_examples_keep_code_path_and_all_five_states(self):
        from kb_scanner.projection.v2.models import SchemaV2Report
        from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator
        examples = materialize_variants(ROOT / 'tests/fixtures/source-evidence-chain/state-variants.json')
        self.assertEqual({'complete', 'partial', 'ambiguous', 'inactive', 'unknown'}, set(examples))
        for status, document in examples.items():
            with self.subTest(status=status):
                self.assertEqual([], validate_document(document))
                V2ReferentialIntegrityValidator().validate(SchemaV2Report.model_validate(document))
                chain = document['findings'][0]['evidenceChain']
                self.assertEqual(status, chain['status'])
                self.assertEqual([], chain['impactStepIds'])
                self.assertFalse({'classification', 'assessment'} & {s['kind'] for s in chain['steps']})
                self.assertFalse({s['id'] for s in chain['steps'] if s['kind'] == 'knowledge_match'} & set(chain['primaryPath']))

    def test_current_avx_enum_rpm_examples_have_resolved_non_stage_paths(self):
        from kb_scanner.projection.v2.models import SchemaV2Report
        from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator
        for name in ('avx', 'enum', 'rpm'):
            document = load_json(ROOT / f'tests/fixtures/source-evidence-chain/{name}-report.json')
            self.assertEqual([], validate_document(document))
            V2ReferentialIntegrityValidator().validate(SchemaV2Report.model_validate(document))
            chain = document['findings'][0]['evidenceChain']
            self.assertEqual([], chain['impactStepIds'])
            self.assertFalse({'classification', 'assessment'} & {s['kind'] for s in chain['steps']})


if __name__ == "__main__":
    unittest.main()
