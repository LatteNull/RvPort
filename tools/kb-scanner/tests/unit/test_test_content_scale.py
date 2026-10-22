import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from contextlib import ExitStack

from tools import test_content_scale as scale
from kb_scanner.core import AnalysisSnapshot, Entity, StageResult, stable_id


class TestContentScaleTests(unittest.TestCase):
    def test_generator_and_acceptance_do_not_allow_empty_dense_success(self):
        for count in (10000,20000):
            for density in ("plain","sparse","dense"):
                source=scale.source(count,density)
                self.assertEqual(count,source.count("assert("))
                self.assertEqual(0 if density=="plain" else 1 if density=="sparse" else count//100,
                                 source.count("_mm_setzero_si128"))
        for count,density in ((0,"plain"),(101,"plain"),(100,"bad")):
            with self.assertRaises(ValueError): scale.source(count,density)
        good={"exitCode":0,"artifactCount":3,"queries":2,"visitedFacts":2,"contentRecords":10000,"partialInventories":1}
        self.assertTrue(scale.accept(good,"dense"))
        self.assertFalse(scale.accept({**good,"partialInventories":0},"dense"))
        for key,value in (("exitCode",1),("artifactCount",2),("queries",3),("visitedFacts",20001),("contentRecords",100001)):
            self.assertFalse(scale.accept({**good,key:value},"sparse"))
        self.assertTrue(scale.accept({**good,"queries":0},"plain"))
        self.assertFalse(scale.accept({**good,"queries":0},"sparse"))

    def test_runner_captures_stages_and_failures_without_real_scanner(self):
        for density,code in (("dense",0),("plain",0),("sparse",1)):
            with TemporaryDirectory() as temporary, ExitStack() as guards:
                output=Path(temporary)/"case"
                queries=0 if density=="plain" else 2
                catalog=Entity(stable_id("catalog"),scale.CATALOG,"catalog",properties={"queries":queries,"visitedFacts":queries})
                source_entity=Entity(stable_id("ordinary"),"source_file","unit.c")
                stage=StageResult(AnalysisSnapshot(entities=(source_entity,*((catalog,) if density!="plain" else ()))))
                guards.enter_context(patch.object(scale.TestContentAnalyzer,"analyze",return_value=stage))
                def fake_main(argv):
                    target=output/"report"; target.mkdir()
                    for name in ("scan-result.json","scan-report.html","scan.log"):
                        (target/name).write_text("fixture")
                    facts=NS(evidence=(NS(kind="test_content",metadata={"testContent":{"recordCount":42,"status":"partial"}}),))
                    scale.TestContentAnalyzer().analyze(None,facts,None,None)
                    from kb_scanner.pipeline import default
                    default.create_default_profile()
                    return code
                guards.enter_context(patch.object(scale,"main",side_effect=fake_main))
                guards.enter_context(patch.object(scale,"verify_limits",side_effect=lambda read:(read(Path(__file__)),{})[1]))
                guards.enter_context(patch.object(scale,"observe",side_effect=lambda profile,emit:emit({"stage":"fake"})))
                guards.enter_context(patch.object(scale,"create_default_profile",return_value=NS()))
                guards.enter_context(patch("builtins.print"))
                self.assertEqual(code,scale.run(output,100,density))
                metrics=json.loads((output/"metrics.json").read_text())
                self.assertEqual(queries,metrics["queries"])
                self.assertEqual(42,metrics["contentRecords"])
                self.assertEqual([{"stage":"fake"}],metrics["stages"])
                self.assertTrue(metrics["inputHash"])
                with self.assertRaises(FileExistsError): scale.run(output,100,density)
