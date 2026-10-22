from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import json
import unittest
from unittest.mock import Mock

from kb_scanner.core import AnalysisSnapshot, DetectionSnapshot, Entity, Evidence, NormalizedFact, NormalizedSnapshot, Observation, ProofPath, Relation, SourceLocation, SourceSpan, StageResult, CompletionStatus, stable_id
from kb_scanner.analyzers.function_multiversion.analysis import FunctionMultiversionAnalyzer, CATALOG_KIND
from kb_scanner.analyzers.function_multiversion.grouping import Budget, discover
from kb_scanner.analyzers.function_multiversion.bindings import associate
from kb_scanner.detectors.function_multiversion import FunctionMultiversionDetector
from kb_scanner.classifiers.policy import DEFAULT_CLASSIFICATION_POLICY as POLICY
from kb_scanner.classifiers.risk import present_risk
from kb_scanner.classifiers.migration import MigrationClassifier
from kb_scanner.assessors.migration import MigrationAssessor
from kb_scanner.projection.v2.multiversion import MultiversionProjection, ProjectionBudget, NAMESPACE, render_multiversion_summary
from kb_scanner.projection.v2.source_chain import SourceChainIndex
from kb_scanner.projection.v2.suggestions import select_suggestion
from kb_scanner.projection.policy import ProjectionPolicy
from kb_scanner.pipeline.composite import CompositeAnalyzer, CompositeDetector
from tests.unit.test_function_multiversion import snapshot, spec, PROFILE


def fixture():
    facts=snapshot([spec('target_clones("avx2,default")')])
    fn=next(f for f in facts.facts if f.kind=='function_declaration')
    span=fn.metadata['function']['bodySpan']
    loc=SourceSpan(SourceLocation('a.cpp',span[0],span[1]+1),SourceLocation('a.cpp',span[0],span[1]+2))
    ev=Evidence(stable_id('call'), 'call_expression',fn.subject_id,'_mm_add_ps','fake','fake','high',loc)
    fact=NormalizedFact(stable_id('call-fact'),'symbol',fn.subject_id,'_mm_add_ps','body',(ev.id,))
    facts=replace(facts,evidence=(*facts.evidence,ev),facts=(*facts.facts,fact))
    base=AnalysisSnapshot(entities=facts.entities)
    return facts,base,fact,ev


def observation(fact,kind='x86_intrinsic_reference',status='confirmed_local'):
    return Observation(stable_id('observation',fact.id,kind),'fake',kind,fact.evidence_ids,status=status,
        knowledge_ids=(stable_id('knowledge'),) if status=='confirmed_local' else (),metadata={'factId':fact.id})


class FunctionBindingTests(unittest.TestCase):
    def test_two_bodies_on_same_line_use_columns(self):
        facts=snapshot([spec('target_clones("avx2,default")','int n'),spec('target_clones("avx2,default")','double n')])
        functions=sorted((f for f in facts.facts if f.kind=='function_declaration'),key=lambda f:f.metadata['function']['bodySpan'])
        changed={f.id:replace(f,metadata={**f.metadata,'function':{**f.metadata['function'],'bodySpan':(1,100+i*100,1,150+i*100)}}) for i,f in enumerate(functions)}
        span=SourceSpan(SourceLocation('a.cpp',1,210),SourceLocation('a.cpp',1,215))
        ev=Evidence(stable_id('same-line-call'),'call_expression',functions[1].subject_id,'external','fake','fake','high',span)
        fact=NormalizedFact(stable_id('same-line-fact'),'symbol',ev.subject_id,'external','body',(ev.id,))
        facts=replace(facts,facts=tuple(changed.get(f.id,f) for f in facts.facts)+(fact,),evidence=(*facts.evidence,ev))
        catalog=discover(facts,Budget())
        links,_=associate(catalog,facts,AnalysisSnapshot(),Budget())
        self.assertEqual([(functions[1].evidence_ids[0],ev.id,'source-unconfigured')],links)
        self.assertEqual(1,sum(len(g['dependencies']) for g in catalog['groups']))

    def test_exact_body_association_and_nonexecuting_graph(self):
        facts,base,fact,ev=fixture()
        result=FunctionMultiversionAnalyzer().analyze(None,facts,None,base)
        self.assertEqual(CompletionStatus.COMPLETE,result.status)
        self.assertEqual(base.proof_paths,result.value.proof_paths)
        self.assertFalse(any(r.kind in {'alternative_to','selects','excludes','calls'} for r in result.value.relations))
        catalog=next(e.properties for e in result.value.entities if e.kind==CATALOG_KIND)
        group=catalog['groups'][0]
        self.assertEqual(1,len(group['dependencies']))
        self.assertEqual(fact.id,group['dependencies'][0]['factId'])
        self.assertEqual('unknown',group['targetSelection'])
        index=SourceChainIndex(NS(entities={e.id:e for e in result.value.entities},relations={r.id:r for r in result.value.relations},evidence={e.id:e for e in facts.evidence},facts={f.id:f for f in facts.facts}))
        query=index.query(ev.id)
        self.assertEqual(3,len(query.evidence_ids))
        self.assertEqual({'defines','contains'},{arc.kind for arc in query.arcs})
        self.assertFalse(any(group['id'] in (a.source,a.target) for a in query.arcs))

    def test_nested_outside_unknown_locations_and_configuration(self):
        facts,base,fact,ev=fixture()
        for changed in (replace(ev,location=None),replace(ev,location=SourceSpan(SourceLocation('other.cpp',1,1),SourceLocation('other.cpp',1,2))),replace(ev,location=SourceSpan(SourceLocation('a.cpp',5,1),SourceLocation('a.cpp',5,2)))):
            modified=replace(facts,evidence=tuple(changed if e.id==ev.id else e for e in facts.evidence))
            catalog=discover(modified,Budget())
            self.assertEqual([],associate(catalog,modified,base,Budget())[0])
        modified=replace(facts,facts=tuple(replace(f,context_ids=(stable_id('other'),)) if f.id==fact.id else f for f in facts.facts))
        self.assertEqual([],associate(discover(modified,Budget()),modified,base,Budget())[0])
        functions=tuple(replace(f,metadata={'function':{**f.metadata['function'],'nestedSpans':(f.metadata['function']['bodySpan'],)}}) if f.kind=='function_declaration' else f for f in facts.facts)
        nested=replace(facts,facts=functions)
        self.assertEqual([],associate(discover(nested,Budget()),nested,base,Budget())[0])
        result=FunctionMultiversionAnalyzer(Budget(associations=0)).analyze(None,facts,None,base)
        self.assertEqual(CompletionStatus.PARTIAL,result.status)
        self.assertIn('multiversion-association-budget-exceeded',{d.code for d in result.diagnostics})

    def test_existing_proof_binding_is_fact_and_config_specific(self):
        facts,base,fact,ev=fixture()
        root=Entity(stable_id('root'),'selector','riscv64')
        relation=Relation(stable_id('relation'),'selects',root.id,fact.subject_id,(ev.id,),status='selected',metadata={'factId':fact.id,'configuration':'source-unconfigured'})
        proof=ProofPath(stable_id('proof'),root.id,fact.subject_id,(relation.id,),'complete')
        base=AnalysisSnapshot((relation,),(*base.entities,root),(proof,))
        catalog=discover(facts,Budget())
        associate(catalog,facts,base,Budget())
        binding=catalog['groups'][0]['bindings'][0]
        self.assertEqual(('selected','unknown'),(binding['selectionStatus'],binding['runtimeVersionSelection']))
        self.assertEqual('unknown',catalog['groups'][0]['targetSelection'])
        analyzed=FunctionMultiversionAnalyzer().analyze(None,facts,None,base).value
        projected=MultiversionProjection(analyzed.entities).report()[NAMESPACE]['groups'][0]
        self.assertEqual('selected',projected['selectionBindings'][0]['selectionStatus'])
        self.assertEqual('unknown',projected['selectionBindings'][0]['runtimeVersionSelection'])
        self.assertEqual('a.cpp',projected['selectionBindings'][0]['sources'][0]['path'])
        for limit in (0, len(projected['sources'])+len(projected['dependencies'])+1):
            clipped=MultiversionProjection(analyzed.entities,budget=ProjectionBudget(sources=limit)).report()[NAMESPACE]
            self.assertGreater(clipped['omittedSources'],0)
        for changed in (replace(relation,metadata={'factId':fact.id,'configuration':'other'}),replace(relation,metadata={})):
            catalog=discover(facts,Budget())
            associate(catalog,facts,replace(base,relations=(changed,)),Budget())
            self.assertEqual([],catalog['groups'][0]['bindings'])
        for bad in (replace(base,entities=()),replace(base,relations=(replace(relation,evidence_ids=()),)),replace(base,relations=(replace(relation,evidence_ids=(stable_id('absent'),)),)),replace(base,proof_paths=(replace(proof,source_id=fact.subject_id),)),replace(base,proof_paths=(replace(proof,relation_ids=(stable_id('missing'),relation.id)),))):
            self.assertIn('multiversion-existing-proof-invalid',associate(discover(facts,Budget()),facts,bad,Budget())[1])
        self.assertEqual(set(),associate(discover(facts,Budget()),facts,replace(base,relations=()),Budget())[1])
        self.assertEqual(set(),associate(discover(facts,Budget()),facts,replace(base,proof_paths=(replace(proof,relation_ids=()),)),Budget())[1])
        partial=discover(facts,Budget())
        associate(partial,facts,replace(base,proof_paths=(replace(proof,status='partial'),)),Budget())
        self.assertEqual('unknown',partial['groups'][0]['bindings'][0]['selectionStatus'])
        self.assertIn('multiversion-association-budget-exceeded',associate(discover(facts,Budget()),facts,base,Budget(associations=1))[1])

    def test_empty_fast_path_and_orphan_source(self):
        base=AnalysisSnapshot()
        self.assertIs(base,FunctionMultiversionAnalyzer().analyze(None,NormalizedSnapshot(),None,base).value)
        facts,base,_,_=fixture()
        facts=replace(facts,facts=tuple(f for f in facts.facts if f.kind=='declaration_attribute'))
        result=FunctionMultiversionAnalyzer().analyze(None,facts,None,base)
        self.assertTrue(any(e.kind==CATALOG_KIND for e in result.value.entities))


class FunctionDetectorPolicyTests(unittest.TestCase):
    def test_complete_guards_foreign_scope_and_candidate_provenance(self):
        facts,base,_,_=fixture()
        attr=next(f for f in facts.facts if f.kind=='declaration_attribute')
        branch=Entity(stable_id('branch'),'conditional_branch','defined(__x86_64__)')
        implementation=Entity(stable_id('impl'),'implementation','x86',properties={'role':'x86'})
        guard=Relation(stable_id('guard'),'guarded_by',implementation.id,branch.id,attr.evidence_ids,status='complete')
        candidate=observation(attr,'target_attribute_candidate','candidate')
        for status,metadata,expected in (
            ('complete',{},'guarded_inactive'),
            ('unknown',{},'unknown'),
            ('complete',{'configuration':'another'},'unknown'),
            ('complete',{'architectureDisposition':'foreign'},None)):
            guarded=replace(base,entities=(*base.entities,branch,implementation),relations=(replace(guard,status=status,metadata=metadata),))
            analysis=FunctionMultiversionAnalyzer().analyze(None,facts,None,guarded).value
            result=FunctionMultiversionDetector().detect(None,facts,analysis,None,DetectionSnapshot((candidate,))).value
            classified=MigrationClassifier().classify(None,result,analysis).value
            if expected is None:
                self.assertFalse(classified.classifications)
            else:
                self.assertEqual(expected,classified.classifications[0].impact)
                self.assertEqual(candidate.metadata,result.observations[0].metadata['mergedProvenance'][0]['metadata'])
                severity='low' if expected=='guarded_inactive' else 'medium'
                self.assertEqual(severity,present_risk(classified.classifications[0],result.observations[0]).severity)

    def test_exact_binding_exclusion_requires_every_attribute(self):
        facts=snapshot([spec('target("avx2")'),spec('target("default")')])
        base=AnalysisSnapshot(entities=facts.entities)
        attrs=[f for f in facts.facts if f.kind=='declaration_attribute']
        selector=Entity(stable_id('selector'),'selector','riscv64')
        relations=tuple(Relation(stable_id('exclusion',f.id),'excludes',selector.id,f.subject_id,f.evidence_ids,status='inactive',
            metadata={'factId':f.id,'itemKind':'source_x86_dependency','configuration':'source-unconfigured'}) for f in attrs)
        proofs=tuple(ProofPath(stable_id('excluded-proof',r.id),r.source_id,r.target_id,(r.id,),'complete') for r in relations)
        for selected in (1,2):
            supplied=replace(base,entities=(*base.entities,selector),relations=relations[:selected],proof_paths=proofs[:selected])
            analysis=FunctionMultiversionAnalyzer().analyze(None,facts,None,supplied).value
            detected=FunctionMultiversionDetector().detect(None,facts,analysis,None,DetectionSnapshot()).value
            result=MigrationClassifier().classify(None,detected,analysis).value.classifications[0]
            self.assertEqual('guarded_inactive' if selected==2 else 'unknown',result.impact)
        selected_relation=replace(relations[0],status='selected')
        supplied=replace(base,entities=(*base.entities,selector),relations=(selected_relation,relations[1]),proof_paths=proofs)
        analysis=FunctionMultiversionAnalyzer().analyze(None,facts,None,supplied).value
        detected=FunctionMultiversionDetector().detect(None,facts,analysis,None,DetectionSnapshot()).value
        self.assertEqual('unknown',MigrationClassifier().classify(None,detected,analysis).value.classifications[0].impact)

    def test_confirmed_intrinsic_preserved_and_generic_candidate_merged(self):
        facts,base,fact,ev=fixture()
        attr=next(f for f in facts.facts if f.kind=='declaration_attribute')
        dependency=observation(fact)
        candidate=observation(attr,'target_attribute_candidate','candidate')
        unrelated=replace(dependency,id=stable_id('unrelated'),metadata={'factId':stable_id('unrelated-fact')})
        analysis=FunctionMultiversionAnalyzer().analyze(None,facts,None,base).value
        original=DetectionSnapshot((dependency,candidate,unrelated))
        result=FunctionMultiversionDetector().detect(None,facts,analysis,None,original)
        self.assertEqual(3,len(result.value.observations))
        kept=next(o for o in result.value.observations if o.id==dependency.id)
        self.assertEqual(dependency.evidence_ids,kept.evidence_ids)
        self.assertEqual(dependency.knowledge_ids,kept.knowledge_ids)
        group=next(o for o in result.value.observations if o.kind=='function_multiversion_unknown')
        self.assertEqual((candidate.id,),group.metadata['mergedObservationIds'])
        classified=MigrationClassifier().classify(None,result.value,analysis)
        old=next(c for c in classified.value.classifications if dependency.id in c.observation_ids)
        self.assertEqual('high',present_risk(old,kept).severity)
        self.assertFalse(any(c.metadata['portabilityGap'] for c in classified.value.classifications))
        assessment=MigrationAssessor().assess(None,classified.value,analysis)
        self.assertFalse(any(a.state=='ready' for a in assessment.value.assessments))
        empty=FunctionMultiversionDetector().detect(None,facts,base,None,original)
        self.assertIs(original,empty.value)

    def test_default_cannot_remove_selected_intrinsic_blocker(self):
        facts,base,fact,ev=fixture()
        root=Entity(stable_id('selected-root'),'selector','riscv64')
        relation=Relation(stable_id('selected-intrinsic'),'selects',root.id,fact.subject_id,(ev.id,),status='selected',
            metadata={'factId':fact.id,'itemKind':'source_x86_dependency','configuration':'source-unconfigured'})
        proof=ProofPath(stable_id('selected-proof'),root.id,fact.subject_id,(relation.id,),'complete')
        base=replace(base,entities=(*base.entities,root),relations=(relation,),proof_paths=(proof,))
        original=replace(observation(fact),relation_ids=(relation.id,),metadata={'factId':fact.id,'proofPathIds':(proof.id,)})
        analysis=FunctionMultiversionAnalyzer().analyze(None,facts,None,base).value
        detected=FunctionMultiversionDetector().detect(None,facts,analysis,None,DetectionSnapshot((original,))).value
        result=MigrationClassifier().classify(None,detected,analysis).value
        classified=next(c for c in result.classifications if original.id in c.observation_ids)
        self.assertEqual('blocking_issue',classified.impact)
        self.assertTrue(present_risk(classified,original).blocking)

    def test_single_target_and_completed_default_do_not_add_issue(self):
        for attr in ('target("avx2")','target_version("sve")','target_clones("avx2,default")'):
            facts=snapshot([spec(attr)])
            analysis=FunctionMultiversionAnalyzer(profiles={'source-unconfigured':PROFILE}).analyze(None,facts,None,AnalysisSnapshot(entities=facts.entities)).value
            result=FunctionMultiversionDetector().detect(None,facts,analysis,None,DetectionSnapshot())
            self.assertEqual((),result.value.observations)

    def test_gap_medium_unknown_and_inactive_rules(self):
        facts=snapshot([spec('target_clones("avx2,sse4.2")')])
        analysis=FunctionMultiversionAnalyzer(profiles={'source-unconfigured':PROFILE}).analyze(None,facts,None,AnalysisSnapshot(entities=facts.entities)).value
        obs=FunctionMultiversionDetector().detect(None,facts,analysis,None,DetectionSnapshot()).value.observations[0]
        classification=MigrationClassifier().classify(None,DetectionSnapshot((obs,)),analysis).value.classifications[0]
        self.assertEqual('actionable_non_blocking',classification.impact)
        self.assertEqual(('medium',False),(present_risk(classification,obs).severity,present_risk(classification,obs).blocking))
        self.assertFalse(classification.metadata['portabilityGap'])
        presentation = ProjectionPolicy().present(obs, classification)
        self.assertEqual('C_CPP.X86.FUNCTION_MULTIVERSION', presentation.rule_id)
        self.assertIn('缺口', presentation.title)
        self.assertIn('bounded scope', presentation.suggestion_en)
        self.assertEqual('issue', ProjectionPolicy().fields(obs, classification)['finding_type'])
        pending = replace(obs, kind='function_multiversion_unknown')
        pending_classification = replace(classification, impact='unknown', metadata={'completeness':'unknown'})
        self.assertIn('待补齐', ProjectionPolicy().present(pending, pending_classification).title)
        self.assertIn('不足', ProjectionPolicy().present(pending, pending_classification).suggestion)
        self.assertEqual('guarded_inactive',POLICY.decide(obs,proof_complete=True,relation_unknown=False,inactive_reachable=True).impact)
        unknown=replace(obs,metadata={'functionMultiversion':{}})
        self.assertEqual('unknown',POLICY.decide(unknown,proof_complete=True,relation_unknown=False).impact)
        for impact,status,kind in [('unknown','unknown','function_multiversion_unknown'),('actionable_non_blocking','complete','function_multiversion_fallback_gap'),('guarded_inactive','inactive','function_multiversion_unknown')]:
            text=select_suggestion(impact,status,kind)
            self.assertTrue(text.zh)
            self.assertTrue(text.en)


class FunctionProjectionPipelineTests(unittest.TestCase):
    def test_projection_self_contained_bounded_and_escaped(self):
        facts,base,fact,ev=fixture()
        analysis=FunctionMultiversionAnalyzer().analyze(None,facts,None,base).value
        view=MultiversionProjection(analysis.entities,(observation(fact),))
        report=view.report()[NAMESPACE]
        finding=view.finding((ev.id,))[NAMESPACE]
        self.assertEqual(report['groups'],finding['groups'])
        self.assertEqual('confirmed_x86',finding['groups'][0]['bodyDependency'])
        for forbidden in ('functionFactId','factId','evidenceId','proofId','relationIds'):
            self.assertNotIn('"'+forbidden+'"',json.dumps(finding))
        self.assertEqual({},view.finding((stable_id('absent'),)))
        self.assertEqual({},MultiversionProjection(()).report())
        self.assertEqual('',render_multiversion_summary(None))
        root=next(e for e in analysis.entities if e.kind==CATALOG_KIND)
        with self.assertRaises(ValueError): MultiversionProjection((root,root))
        with self.assertRaises(ValueError): ProjectionBudget(groups=-1)
        for budget in (ProjectionBudget(groups=0),ProjectionBudget(versions=0),ProjectionBudget(sources=0)):
            result=MultiversionProjection(analysis.entities,budget=budget).report()[NAMESPACE]
            self.assertEqual('partial',result['projectionStatus'])
        report['groups'][0]['signature']='<script>bad</script>'
        rendered=render_multiversion_summary({NAMESPACE:report})
        self.assertNotIn('<script>',rendered)
        self.assertIn('&lt;script&gt;',rendered)
        context=Mock(project=Mock(return_value=NS(model_dump=lambda **kwargs:{'context':{'budget':{'beforeLines':20,'afterLines':20}}})))
        projected=MultiversionProjection(analysis.entities,context=context).report()[NAMESPACE]
        self.assertEqual(20,projected['groups'][0]['sources'][0]['context']['context']['budget']['beforeLines'])

    def test_fake_stage_order_failures_and_partial(self):
        for status in (CompletionStatus.COMPLETE,CompletionStatus.PARTIAL,CompletionStatus.FAILED,CompletionStatus.UNAVAILABLE):
            stages=[Mock(analyze=Mock(return_value=StageResult(AnalysisSnapshot()))) for _ in range(6)]
            stages[-1].analyze.return_value=StageResult(None if status in {CompletionStatus.FAILED,CompletionStatus.UNAVAILABLE} else AnalysisSnapshot(),status)
            usage=Mock(analyze=Mock(return_value=StageResult(AnalysisSnapshot())))
            result=CompositeAnalyzer(*stages,usage=usage).analyze(None,NormalizedSnapshot(),None)
            self.assertEqual(status,result.status)
            for stage in stages: stage.analyze.assert_called_once()
            if status in {CompletionStatus.FAILED,CompletionStatus.UNAVAILABLE}:
                usage.analyze.assert_not_called()
            else:
                usage.analyze.assert_called_once()
            detectors=[Mock(detect=Mock(return_value=StageResult(DetectionSnapshot()))) for _ in range(4)]
            detectors[-1].detect.return_value=StageResult(None if status in {CompletionStatus.FAILED,CompletionStatus.UNAVAILABLE} else DetectionSnapshot(),status)
            result=CompositeDetector(*detectors).detect(None,NormalizedSnapshot(),AnalysisSnapshot(),None)
            self.assertEqual(status,result.status)
        stages=[Mock(analyze=Mock(return_value=StageResult(AnalysisSnapshot()))) for _ in range(6)]
        stages[4].analyze.return_value=StageResult(None,CompletionStatus.FAILED)
        usage=Mock(analyze=Mock(return_value=StageResult(AnalysisSnapshot())))
        CompositeAnalyzer(*stages,usage=usage).analyze(None,NormalizedSnapshot(),None)
        stages[-1].analyze.assert_not_called()
        usage.analyze.assert_not_called()
