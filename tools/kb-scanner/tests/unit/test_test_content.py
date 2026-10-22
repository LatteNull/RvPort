from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from kb_scanner.core import AnalysisSnapshot, CompletionStatus, Entity, Evidence, KnowledgeSnapshot, NormalizedSnapshot, SourceLocation, SourceSpan, StageResult, Relation, stable_id
from kb_scanner.analyzers.test_content import TestContentAnalyzer, CATALOG, _assert_states
from kb_scanner.analyzers.macro_state import MacroState
from tests.unit.classification_assessment.support import context
from tests.unit.test_content_support import data, function, straight_rows


def fixture(path="tests/unit.c", registered=True):
    source=Entity(stable_id("file",path),"source_file",path)
    build=Entity(stable_id("build"),"build_file","CMakeLists.txt")
    def evidence(name,kind,value,line=1,column=1,owner=source,metadata=None):
        return Evidence(stable_id(name),kind,owner.id,value,"unit","tree_sitter_baseline","medium",
            SourceSpan(SourceLocation(owner.name,line,column),SourceLocation(owner.name,line,column+2)),
            metadata=metadata or {})
    fn=evidence("main","test_structure","main")
    anchor=evidence("anchor","call_expression","_x",column=21)
    assertion=evidence("assert","call_expression","assert",column=41)
    inv=evidence("inventory","test_content","test-content",metadata={"testContent":data(function(evidenceId=fn.id))})
    details={"target":"app","configuration":"cfg","name":"unit","role":"confirmed",
        "registrationStatus":"selected","buildStatus":"selected","reasonCodes":(),"sourceKeys":("reg",)}
    reg=evidence("reg","build_configuration","add_test",owner=build,
        metadata={"cmake":{"key":"reg","testRegistration":details},"configuration":"cfg"})
    member=evidence("member","build_source",path,owner=build,
        metadata={"cmake":{"key":"member","target":"app"},"selectionStatus":"selected","configuration":"cfg"})
    items=(fn,anchor,assertion,inv,*((reg,member) if registered else ()))
    return NormalizedSnapshot((source,build),items,()),anchor


def catalog(result):
    return next(e for e in result.value.entities if e.kind==CATALOG)


def run(facts, ids, **kwargs):
    return TestContentAnalyzer(lambda *_:ids,**kwargs).analyze(context(),facts,KnowledgeSnapshot(stable_id("kb"),"1"),AnalysisSnapshot())


class TestContentAnalysisTests(unittest.TestCase):
    def test_observed_assert_configs_are_separate_and_references_close(self):
        facts,anchor=fixture()
        assertion=next(e for e in facts.evidence if e.value=="assert")
        profiles=tuple(replace(assertion,id=stable_id("profile",cfg),parse_mode="clang_enrichment",
            metadata={"standardAssert":{"configuration":cfg,"status":status}})
            for cfg,status in (("debug","enabled"),("release","disabled")))
        facts=replace(facts,evidence=(*facts.evidence,*profiles))
        entry=catalog(run(facts,(anchor.id,))).properties["entries"][0]
        self.assertEqual(["enabled","disabled"],[v["status"] for v in entry["assertion"]["observedConfigurations"]])
        self.assertEqual("unknown",entry["assertion"]["status"])
        self.assertIn("test-assert-target-configuration-unproven",entry["reasonCodes"])
        self.assertTrue({e.id for e in profiles}.issubset(entry["sourceEvidenceIds"]))
        direct=_assert_states(facts.evidence,{facts.entities[0].name:facts.entities[0]},facts.entities[0])
        self.assertEqual(2,len(direct[(1,41)]["observedConfigurations"]))

    def test_producer_conflict_and_existing_explicit_assets(self):
        facts,anchor=fixture(registered=False)
        inv=next(e for e in facts.evidence if e.kind=="test_content")
        duplicate=replace(inv,id=stable_id("conflict"),metadata={"testContent":data(status="partial")})
        facts=replace(facts,evidence=(*facts.evidence,duplicate))
        entry=catalog(run(facts,(anchor.id,))).properties["entries"][0]
        self.assertIn("test-content-producer-conflict",entry["reasonCodes"])
        self.assertEqual("unknown",entry["proofStatus"])
        target=Entity(stable_id("test-target"),"test_target","%check",properties={"configuration":"rpm"})
        relation=Relation(stable_id("member"),"contains_test",target.id,facts.entities[0].id,(anchor.id,),"medium","unknown")
        result=TestContentAnalyzer(lambda *_:(anchor.id,)).analyze(context(),facts,KnowledgeSnapshot(stable_id("kb"),"1"),
            AnalysisSnapshot((relation,),(target,)))
        entry=catalog(result).properties["entries"][0]
        self.assertEqual("rpm",entry["configuration"])
        self.assertIn("test-entry-registration-unproven",entry["reasonCodes"])

    def test_registered_local_binding_preserves_original_facts_and_real_edges(self):
        facts,anchor=fixture()
        result=run(facts,(anchor.id,))
        view=catalog(result).properties
        entry,=view["entries"]
        self.assertEqual("local-value-to-assert",entry["content"]["relation"])
        self.assertEqual("selected",entry["buildStatus"])
        self.assertEqual("unknown",entry["assertion"]["status"])
        self.assertEqual(1,view["indexedFiles"])
        self.assertEqual(1,view["queries"])
        self.assertEqual("unknown",entry["proofStatus"])
        self.assertGreater(len(result.value.relations),0)
        self.assertTrue(all(set(r.evidence_ids).issubset({e.id for e in facts.evidence}) for r in result.value.relations))
        self.assertIn(anchor,facts.evidence)
        self.assertEqual(result,run(facts,(anchor.id,)))

    def test_empty_missing_and_non_test_inputs_do_not_invent_assets(self):
        empty=NormalizedSnapshot()
        self.assertEqual(AnalysisSnapshot(),run(empty,()).value)
        facts,anchor=fixture(path="src/plain.c",registered=False)
        self.assertEqual(AnalysisSnapshot(),run(facts,(anchor.id,)).value)
        self.assertEqual(AnalysisSnapshot(),run(facts,(stable_id("absent"),)).value)
        missing=replace(anchor,location=None)
        altered=replace(facts,evidence=tuple(missing if e.id==anchor.id else e for e in facts.evidence))
        self.assertEqual(AnalysisSnapshot(),run(altered,(anchor.id,)).value)
        altered=replace(facts,entities=())
        self.assertEqual(AnalysisSnapshot(),run(altered,(anchor.id,)).value)

    def test_candidate_role_missing_assert_call_and_body_context(self):
        facts,anchor=fixture(registered=False)
        result=run(facts,(anchor.id,))
        entry=catalog(result).properties["entries"][0]
        self.assertEqual("candidate",entry["role"])
        self.assertIn("test-registration-missing",entry["reasonCodes"])
        facts=replace(facts,evidence=tuple(e for e in facts.evidence if e.value!="assert"))
        entry=catalog(run(facts,(anchor.id,))).properties["entries"][0]
        self.assertIn("test-assert-environment-unavailable",entry["reasonCodes"])
        entries=[]
        for item in facts.evidence:
            if item.kind=="test_content":
                records=straight_rows()
                records[-1]["binding"]["status"]="unknown"
                item=replace(item,metadata={"testContent":data(function(records,evidenceId=stable_id("main")))})
            entries.append(item)
        entry=catalog(run(replace(facts,evidence=tuple(entries)),(anchor.id,))).properties["entries"][0]
        self.assertIsNone(entry["assertion"])
        self.assertEqual("body",entry["content"]["relation"])

    def test_each_budget_retains_unknown_and_never_complete_inventory(self):
        facts,anchor=fixture()
        extra=replace(anchor,id=stable_id("extra"))
        facts=replace(facts,evidence=(*facts.evidence,extra))
        for kwargs in ({"limit":1},{"visit_limit":1},{"relation_limit":1}):
            result=run(facts,(anchor.id,extra.id),**kwargs)
            self.assertEqual(CompletionStatus.PARTIAL,result.status)
            self.assertTrue(catalog(result).properties["truncated"])
            self.assertTrue(result.diagnostics)
            self.assertNotIn("testInventoryComplete",catalog(result).properties)
        for kwargs in ({"limit":0},{"visit_limit":0},{"relation_limit":0}):
            with self.assertRaises(ValueError): TestContentAnalyzer(**kwargs)

    def test_multi_registration_truncation_and_unbound_structure(self):
        facts,anchor=fixture()
        reg=next(e for e in facts.evidence if e.id==stable_id("reg"))
        info=dict(reg.metadata["cmake"])
        info["testRegistration"]={**info["testRegistration"],"name":"second"}
        other=replace(reg,id=stable_id("reg2"),metadata={"cmake":info,"configuration":"cfg"})
        facts=replace(facts,evidence=(*facts.evidence,other))
        self.assertTrue(catalog(run(facts,(anchor.id,),limit=1)).properties["truncated"])
        facts=replace(facts,evidence=tuple(replace(e,metadata={"testContent":data(function(plain=False))})
                    if e.kind=="test_content" else e for e in facts.evidence))
        entry=catalog(run(facts,(anchor.id,))).properties["entries"][0]
        self.assertEqual("unknown",entry["content"]["entryStatus"])

    def test_one_hop_and_unknown_content_connections(self):
        facts,anchor=fixture()
        fn=next(e for e in facts.evidence if e.id==stable_id("main"))
        helper=replace(fn,id=stable_id("helper"),value="helper")
        facts=replace(facts,evidence=(*facts.evidence,helper))
        resolved={"relation":"body","entryStatus":"complete","reasonCodes":(),
                  "functionEvidenceId":helper.id,"entryEvidenceId":fn.id,"callSpan":(1,21,1,29)}
        with patch("kb_scanner.analyzers.test_content.ContentIndex") as cls:
            cls.return_value.resolve.return_value=resolved
            cls.return_value.queries=1
            result=run(facts,(anchor.id,))
        self.assertTrue(any(r.kind=="calls" for r in result.value.relations))
        with patch("kb_scanner.analyzers.test_content.ContentIndex") as cls:
            cls.return_value.resolve.return_value={"relation":"unknown","reasonCodes":("broken",),"entryStatus":"unknown"}
            cls.return_value.queries=1
            result=run(facts,(anchor.id,))
        self.assertFalse(result.value.relations)

    def test_assert_macro_state_evidence_is_not_a_standard_identity_proof(self):
        facts,anchor=fixture()
        assertion=next(e for e in facts.evidence if e.value=="assert")
        source=facts.entities[0]
        for state in (True,False,None):
            def fake_run(_file,env,callback):
                callback(anchor,{},True,None)
                callback(assertion,{"NDEBUG":MacroState(state,None,anchor.id),
                                    "assert":MacroState(True,"custom",assertion.id)},False,None)
            with patch("kb_scanner.analyzers.test_content.MacroSession") as session:
                session.return_value.run.side_effect=fake_run
                result=_assert_states(facts.evidence,{source.name:source},source)
            view=result[(1,41)]
            self.assertEqual("unknown",view["status"])
            self.assertEqual(state,view["ndebugDefined"])
            self.assertIn("test-assert-macro-overridden",view["reasonCodes"])

    def test_pipeline_propagates_content_stage_failure_and_partial(self):
        from kb_scanner.pipeline.composite import CompositeAnalyzer
        class Stage:
            def __init__(self,result): self.result=result
            def analyze(self,*_): return self.result
        empty=Stage(StageResult(AnalysisSnapshot()))
        for status in (CompletionStatus.FAILED,CompletionStatus.UNAVAILABLE,CompletionStatus.PARTIAL):
            stage=Stage(StageResult(None if status!=CompletionStatus.PARTIAL else AnalysisSnapshot(),status))
            result=CompositeAnalyzer(empty,empty,empty,empty,empty,empty,empty,stage).analyze(
                context(),NormalizedSnapshot(),KnowledgeSnapshot(stable_id("kb"),"1"))
            self.assertEqual(status,result.status)
