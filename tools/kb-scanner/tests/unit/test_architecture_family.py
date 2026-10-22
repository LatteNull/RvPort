"""Synthetic snapshots only: no native parser, project command or source read."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from kb_scanner.core import (AnalysisSnapshot, CompletionStatus, Entity, Evidence, FrontendSnapshot,
    KnowledgeSnapshot, NormalizedFact, NormalizedSnapshot, ProofPath, Relation, SourceLocation, SourceSpan,
    StageResult, WorkspaceSnapshot, stable_id)
from kb_scanner.frontends.family_inventory import annotate_inventory
from kb_scanner.analyzers.architecture_family.paths import candidates
from kb_scanner.analyzers.architecture_family.grouping import FamilyBudget, discover
from kb_scanner.analyzers.architecture_family.bindings import bind
from kb_scanner.analyzers.architecture_family.analyzer import ArchitectureFamilyAnalyzer, CATALOG_KIND
from kb_scanner.projection.v2.families import FamilyProjection, ProjectionBudget, NAMESPACE, render_family_summary
from kb_scanner.projection.v2.source_chain import SourceChainIndex
from kb_scanner.pipeline.composite import CompositeAnalyzer, CompositeDetector


def sources(*paths):
    return tuple(Entity(stable_id("file", p), "source_file", p, properties={"pathObservation": {
        "path": p, "scope": "authorized-file-list", "parseStatus": "unknown"}}) for p in paths)


def proof_fixture(state="selected", configuration="rv"):
    files = sources("foo_x86.cpp", "foo_generic.cpp")
    root = Entity(stable_id("root"), "architecture_selector", "riscv64")
    span = SourceSpan(SourceLocation("Makefile", 1, 1), SourceLocation("Makefile", 1, 15))
    ev = Evidence(stable_id("ev"), "build_source", root.id, files[0].name, "fake", "fake", "high", span)
    fact = NormalizedFact(stable_id("fact"), "build_source", root.id, files[0].name, "unit", (ev.id,))
    relation = Relation(stable_id("select", configuration), "selects", root.id, files[0].id, (ev.id,), status=state,
                        metadata={"configuration": configuration, "factId": fact.id})
    proof = ProofPath(stable_id("proof", configuration), root.id, files[0].id, (relation.id,), "complete")
    facts = NormalizedSnapshot((*files, root), (ev,), (fact,))
    base = AnalysisSnapshot((relation,), (*files, root), (proof,))
    return files, facts, base


class FamilyTests(unittest.TestCase):
    def test_manual_oracle(self):
        data = json.loads((Path(__file__).parents[1]/"fixtures/architecture-family-oracle.json").read_text())
        for case in data["cases"]:
            with self.subTest(case=case):
                result = discover(sources(*case["paths"]), FamilyBudget())
                self.assertEqual(case["sizes"], [f["memberCount"] for f in result["families"]])
                if "status" in case:
                    self.assertEqual(case["status"], result["families"][0]["status"])

    def test_path_boundaries(self):
        for path in ("", "/a_x86.cpp", "../a_x86.cpp", "a//b.cpp", "C:/a.cpp", "./a.cpp"):
            self.assertEqual((), candidates(path))
        for path in ("foo_x86_64.cpp", "x86_64_foo.cpp", "foo-sse4_2.cpp", "foo.AVX2.cpp", "x64/foo.cpp"):
            self.assertEqual("x86", candidates(path)[0].role)
        self.assertEqual("filename:d/foo.cpp", candidates("d\\foo_x86.cpp")[0].key)
        self.assertEqual("foreign", candidates("arm/foo.cpp")[0].role)
        self.assertEqual("unlabelled", candidates("myx86helper.cpp")[0].role)
        self.assertTrue(candidates("x86/foo_generic.cpp")[0].ambiguous)
        self.assertEqual("unknown", candidates("arm/foo_generic.cpp")[0].role)

    def test_inventory_preserves_ids_and_never_adds_evidence(self):
        ctx = SimpleNamespace(excludes=("build",), exclude_paths=("vendor/a",))
        files = sources("foo_x86.cpp", "not_authorized.cpp")
        other = Entity(stable_id("build"), "build_file", "Makefile")
        result = StageResult(FrontendSnapshot((*files, other)), CompletionStatus.PARTIAL)
        value = annotate_inventory(result, WorkspaceSnapshot(Path("/tmp"), (files[0].name,)), ctx)
        self.assertEqual(files[0].id, value.value.entities[0].id)
        self.assertEqual("unknown", value.value.entities[0].properties["pathObservation"]["parseStatus"])
        self.assertEqual(files[1], value.value.entities[1])
        self.assertEqual((), value.value.evidence)
        self.assertEqual(other, value.value.entities[-1])
        complete = annotate_inventory(replace(result, status=CompletionStatus.COMPLETE), WorkspaceSnapshot(Path("/tmp"), (files[0].name,)), ctx)
        self.assertEqual("complete", complete.value.entities[0].properties["pathObservation"]["parseStatus"])
        failed = StageResult(None, CompletionStatus.FAILED)
        self.assertIs(failed, annotate_inventory(failed, None, None))

    def test_budgets_determinism_and_no_input_mutation(self):
        files = sources("b_x86.cpp", "b_generic.cpp", "a_x86.cpp", "a_generic.cpp")
        self.assertEqual(discover(files, FamilyBudget()), discover(reversed(files), FamilyBudget()))
        result = discover(files, FamilyBudget(paths=3, families=1, members=1))
        self.assertEqual(["family-member-budget", "family-path-budget"], result["reasonCodes"])
        self.assertIn("family-count-budget", discover(files, FamilyBudget(families=1))["reasonCodes"])
        self.assertEqual(3, result["bucketOperations"])
        self.assertEqual(2, result["families"][0]["memberCount"])
        self.assertEqual(1, len(result["families"][0]["members"]))
        self.assertEqual([], discover(files, FamilyBudget(paths=0))["families"])
        with self.assertRaises(ValueError):
            FamilyBudget(paths=-1)
        self.assertNotIn("bindings", files[0].properties)

    def test_binding_provenance_and_multiple_configurations(self):
        files, facts, base = proof_fixture()
        _, _, alternate = proof_fixture("inactive", "other")
        base = replace(base, relations=(*base.relations, *alternate.relations), proof_paths=(*base.proof_paths, *alternate.proof_paths))
        catalog = discover(files, FamilyBudget())
        self.assertEqual((), bind(catalog, facts, base, FamilyBudget()))
        member = next(m for m in catalog["families"][0]["members"] if m["roleHint"] == "x86")
        self.assertEqual({("rv", "selected"), ("other", "inactive")}, {(b["configuration"], b["selectionStatus"]) for b in member["bindings"]})
        self.assertTrue(all(b["sources"][0]["path"] == "Makefile" for b in member["bindings"]))
        self.assertEqual("unknown", catalog["families"][0]["alternativeStatus"])

    def test_binding_unknown_limits_and_invalid_proofs(self):
        files, facts, base = proof_fixture()
        for budget in (FamilyBudget(bindings=0), FamilyBudget(proof_steps=0)):
            self.assertEqual(("family-binding-budget",), bind(discover(files, budget), facts, base, budget))
        proof, edge = base.proof_paths[0], base.relations[0]
        cases = [replace(base, relations=()), replace(base, proof_paths=(replace(proof, source_id=files[1].id),)),
                 replace(base, relations=(replace(edge, evidence_ids=()),)),
                 replace(base, relations=(replace(edge, evidence_ids=(stable_id("absent"),)),)),
                 replace(base, entities=files)]
        for invalid in cases:
            self.assertIn("family-invalid-proof", bind(discover(files, FamilyBudget()), facts, invalid, FamilyBudget()))
        unknown = replace(base, proof_paths=(replace(proof, status="partial"),))
        catalog = discover(files, FamilyBudget())
        bind(catalog, facts, unknown, FamilyBudget())
        self.assertEqual("unknown", next(m for m in catalog["families"][0]["members"] if m["bindings"])["bindings"][0]["selectionStatus"])
        self.assertEqual((), bind(discover((), FamilyBudget()), facts, base, FamilyBudget()))
        self.assertEqual((), bind(discover(files, FamilyBudget()), facts, replace(base, proof_paths=(replace(proof, relation_ids=()),)), FamilyBudget()))

    def test_graph_candidate_edges_have_no_source_or_executable_proof(self):
        files, facts, base = proof_fixture()
        result = ArchitectureFamilyAnalyzer().analyze(None, facts, None, base)
        self.assertEqual(CompletionStatus.COMPLETE, result.status)
        self.assertEqual(base.proof_paths, result.value.proof_paths)
        edges = [r for r in result.value.relations if r.kind == "candidate_member_of"]
        self.assertEqual(2, len(edges))
        self.assertTrue(all(not r.evidence_ids and r.status == "unknown" for r in edges))
        snapshot = SimpleNamespace(entities={e.id:e for e in result.value.entities}, relations={r.id:r for r in edges}, evidence={e.id:e for e in facts.evidence}, facts={})
        index = SourceChainIndex(snapshot)
        self.assertFalse(index.incoming)
        self.assertFalse(index.outgoing)
        empty = AnalysisSnapshot()
        self.assertIs(empty, ArchitectureFamilyAnalyzer().analyze(None, NormalizedSnapshot(), None, empty).value)
        for budget, original, reason in ((FamilyBudget(relations=0), base, "family-relation-budget"),
                                          (FamilyBudget(), empty, "family-member-unavailable"),
                                          (FamilyBudget(paths=0), base, "family-path-budget")):
            partial = ArchitectureFamilyAnalyzer(budget).analyze(None, facts, None, original)
            self.assertEqual(CompletionStatus.PARTIAL, partial.status)
            self.assertIn(reason, {d.code for d in partial.diagnostics})

    def test_binding_rejects_config_conflicts_and_preserves_alternative_kind(self):
        files, facts, base = proof_fixture()
        edge, proof = base.relations[0], base.proof_paths[0]
        first = replace(edge, id=stable_id("first"), target_id=edge.source_id, metadata={"configuration": "other"})
        conflicted = replace(base, relations=(first, edge), proof_paths=(replace(proof, relation_ids=(first.id, edge.id)),))
        self.assertIn("family-invalid-proof", bind(discover(files, FamilyBudget()), facts, conflicted, FamilyBudget()))
        alternatives = replace(base, relations=(replace(edge, kind="alternative_to", status="complete", metadata={}),))
        catalog = discover(files, FamilyBudget())
        self.assertEqual((), bind(catalog, facts, alternatives, FamilyBudget()))
        record = next(m for m in catalog["families"][0]["members"] if m["bindings"])["bindings"][0]
        self.assertEqual(("default", "unknown", "alternative_to"), (record["configuration"], record["selectionStatus"], record["kind"]))
        no_location = replace(facts, evidence=(replace(facts.evidence[0], location=None),))
        self.assertIn("family-invalid-proof", bind(discover(files, FamilyBudget()), no_location, base, FamilyBudget()))
        broken = replace(base, proof_paths=(replace(proof, relation_ids=(stable_id("missing-prefix"), edge.id)),))
        self.assertIn("family-invalid-proof", bind(discover(files, FamilyBudget()), facts, broken, FamilyBudget()))

    def test_mapper_merges_namespace_and_publisher_receives_catalog(self):
        from kb_scanner.projection.v2.mapper import V2FindingMapper
        from kb_scanner.projection.v2.index import SnapshotIndex
        from kb_scanner.projection.v2.projector import SchemaV2ReportProjector
        from tests.unit.schema_v2_projection.support import graph, report
        from unittest.mock import patch
        values = list(graph(Path("/synthetic")))
        ev = values[3].evidence[0]
        files = (Entity(ev.subject_id, "source_file", "foo_x86.cpp", properties={"pathObservation":{"path":"foo_x86.cpp"}}), *sources("foo_generic.cpp"))
        facts = NormalizedSnapshot(files)
        analysis = ArchitectureFamilyAnalyzer().analyze(None, facts, None, replace(values[5], entities=files)).value
        ev = replace(ev, metadata={"rpm":{"source":"test"}})
        values[3] = replace(values[3], evidence=(ev,))
        values[5] = analysis
        index = SnapshotIndex.build(values[2], values[3], values[4], analysis, values[6], values[7], values[8])
        source = Mock(project=Mock(return_value=report().findings[0].fact.primaryLocation))
        chain = Mock(build=Mock(return_value=report().findings[0].evidenceChain))
        finding = V2FindingMapper(index, chain, source).map(values[7])[0]
        self.assertEqual({NAMESPACE, "org.rvport.kb-scanner.rpm"}, set(finding.fact.extensions))
        publisher = Mock(publish=Mock(return_value=()))
        with patch("kb_scanner.projection.v2.projector.V2FindingMapper") as mapper, patch("kb_scanner.projection.v2.projector.V2ReferentialIntegrityValidator"):
            mapper.return_value.map.return_value = (finding,)
            result = SchemaV2ReportProjector(publisher).project(*values)
        self.assertEqual(CompletionStatus.COMPLETE, result.status)
        data = json.loads(publisher.publish.call_args.args[1]["scan-result.json"])
        self.assertIn(NAMESPACE, data["extensions"])
        self.assertEqual(2, data["extensions"][NAMESPACE]["families"][0]["memberCount"])

    def test_pipeline_family_stage_failure_and_partial(self):
        facts = NormalizedSnapshot()
        for status in (CompletionStatus.COMPLETE, CompletionStatus.PARTIAL, CompletionStatus.FAILED, CompletionStatus.UNAVAILABLE):
            source = Mock(analyze=Mock(return_value=StageResult(AnalysisSnapshot())))
            family = Mock(analyze=Mock(return_value=StageResult(None if status in {CompletionStatus.FAILED, CompletionStatus.UNAVAILABLE} else AnalysisSnapshot(), status)))
            result = CompositeAnalyzer(source, source, source, source, family).analyze(None, facts, KnowledgeSnapshot("k", "1"))
            self.assertEqual(status, result.status)
            family.analyze.assert_called_once()

    def test_upstream_failures_short_circuit_family_and_test_detector(self):
        from kb_scanner.core import DetectionSnapshot
        for failing_index in (2, 3):
            stages = [Mock(analyze=Mock(return_value=StageResult(AnalysisSnapshot()))) for _ in range(5)]
            stages[failing_index].analyze.return_value = StageResult(None, CompletionStatus.UNAVAILABLE)
            result = CompositeAnalyzer(*stages).analyze(None, NormalizedSnapshot(), KnowledgeSnapshot("k", "1"))
            self.assertEqual(CompletionStatus.UNAVAILABLE, result.status)
            stages[4].analyze.assert_not_called()
        stages = [Mock(detect=Mock(return_value=StageResult(DetectionSnapshot()))) for _ in range(3)]
        stages[2].detect.return_value = StageResult(None, CompletionStatus.FAILED)
        result = CompositeDetector(*stages).detect(None, NormalizedSnapshot(), AnalysisSnapshot(), KnowledgeSnapshot("k", "1"))
        self.assertEqual(CompletionStatus.FAILED, result.status)

    def test_classifier_and_assessor_ignore_structural_membership(self):
        from kb_scanner.classifiers import MigrationClassifier
        from kb_scanner.assessors import MigrationAssessor
        from tests.unit.compatible_cutover.support import graph
        values = graph(Path("/synthetic"))
        original_entity = values[5].entities[0]
        files = (Entity(original_entity.id, "source_file", "foo_x86.cpp", properties={"pathObservation":{"path":"foo_x86.cpp"}}), *sources("foo_generic.cpp"))
        base = replace(values[5], entities=files)
        extended = ArchitectureFamilyAnalyzer().analyze(None, NormalizedSnapshot(files), None, base).value
        classifier, assessor = MigrationClassifier(), MigrationAssessor()
        old = classifier.classify(None, values[6], base)
        new = classifier.classify(None, values[6], extended)
        self.assertEqual(old, new)
        self.assertEqual(assessor.assess(None, old.value, base), assessor.assess(None, new.value, extended))

    def test_projection_no_fake_locations_or_internal_refs(self):
        files, facts, base = proof_fixture()
        analysis = ArchitectureFamilyAnalyzer().analyze(None, facts, None, base).value
        view = FamilyProjection(analysis.entities)
        catalog = view.report()[NAMESPACE]
        finding = view.finding((files[0].id,))[NAMESPACE]
        self.assertEqual(catalog["families"], finding["families"])
        self.assertEqual({}, view.finding((stable_id("absent"),)))
        encoded = json.dumps(finding)
        for forbidden in ("fileId", "proofId", "relationIds", "primaryLocation", "highlights"):
            self.assertNotIn(forbidden, encoded)
        self.assertTrue(finding["explanation_en"])
        self.assertEqual("complete", catalog["projectionStatus"])
        self.assertIsNone(FamilyProjection(()).report())
        with self.assertRaises(ValueError):
            ProjectionBudget(members=-1)
        root = next(e for e in analysis.entities if e.kind == CATALOG_KIND)
        with self.assertRaises(ValueError):
            FamilyProjection((root, root))

    def test_projection_limits_and_html_escaping(self):
        files, facts, base = proof_fixture()
        analysis = ArchitectureFamilyAnalyzer().analyze(None, facts, None, base).value
        for budget in (ProjectionBudget(families=0), ProjectionBudget(members=0), ProjectionBudget(bindings=0), ProjectionBudget(sources=0)):
            view = FamilyProjection(analysis.entities, budget).report()[NAMESPACE]
            self.assertEqual("partial", view["projectionStatus"])
            self.assertIn("family-output-budget", view["reasonCodes"])
        extension = FamilyProjection(analysis.entities).report()
        extension[NAMESPACE]["families"][0]["members"][0]["path"] = '<script>alert("x")</script>_x86.cpp'
        rendered = render_family_summary(extension)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("href=", rendered)
        self.assertEqual("", render_family_summary(None))


if __name__ == "__main__":
    unittest.main()
