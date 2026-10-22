from dataclasses import replace
from types import SimpleNamespace
import unittest

from kb_scanner.projection.v2.test_content import TestContentProjection, NAMESPACE, render_test_content
from kb_scanner.core import Entity, stable_id
from tests.unit.test_test_content import fixture, run, catalog


class Source:
    def project(self, span):
        return SimpleNamespace(model_dump=lambda **_: {"file":span.start.path,
            "span":{"start":{"line":span.start.line,"column":span.start.column}},
            "context":{"budget":{"beforeLines":20,"afterLines":20}}})


class TestContentProjectionTests(unittest.TestCase):
    def setup(self):
        facts,anchor=fixture()
        result=run(facts,(anchor.id,))
        index=SimpleNamespace(evidence={e.id:e for e in facts.evidence},entities={e.id:e for e in result.value.entities})
        return index,anchor

    def test_self_contained_sources_bilingual_and_empty(self):
        index,anchor=self.setup()
        projection=TestContentProjection(index,Source())
        self.assertEqual({},projection.finding(()))
        extension=projection.finding((anchor.id,))
        view=extension[NAMESPACE]
        self.assertEqual(1,view["totalUses"])
        self.assertFalse(view["truncated"])
        self.assertTrue(view["uses"][0]["description_en"])
        self.assertEqual("selected",view["uses"][0]["buildStatus"])
        self.assertTrue(set(view["uses"][0]["sourceIds"]).issubset({s["id"] for s in view["sources"]}))
        self.assertTrue(all(s["source"]["context"]["budget"]["beforeLines"]==20 for s in view["sources"]))
        self.assertNotIn("functionEvidenceId",view["uses"][0]["content"])
        self.assertNotIn("evidenceIds",view["uses"][0]["assertion"])
        self.assertIn("原始测试内容",render_test_content(extension))
        self.assertEqual("",render_test_content(None))

    def test_budget_missing_location_and_html_escaping(self):
        index,anchor=self.setup()
        view=TestContentProjection(index,Source()).finding((anchor.id,),source_limit=1)[NAMESPACE]
        self.assertTrue(view["truncated"])
        self.assertEqual(1,len(view["sources"]))
        cat=next(e for e in index.entities.values() if e.kind=="test_content_catalog")
        entry={**cat.properties["entries"][0],"testName":"<img src=x onerror=1>","assertion":None,
               "sourceEvidenceIds":(stable_id("missing"),anchor.id)}
        modified=replace(cat,properties={**cat.properties,"entries":(entry,entry),"truncated":True})
        index.entities[cat.id]=modified
        index.evidence[anchor.id]=replace(index.evidence[anchor.id],location=None)
        extension=TestContentProjection(index,Source()).finding((anchor.id,),limit=1)
        self.assertTrue(extension[NAMESPACE]["truncated"])
        self.assertEqual((),extension[NAMESPACE]["sources"])
        html=render_test_content(extension)
        self.assertIn("&lt;img",html)
        self.assertNotIn("<img",html)
        self.assertIn("部分测试来源",html)
        self.assertIsNone(extension[NAMESPACE]["uses"][0]["assertion"])
        for kwargs in ({"limit":0},{"source_limit":0}):
            with self.assertRaises(ValueError): TestContentProjection(index,Source()).finding((anchor.id,),**kwargs)

    def test_reused_source_cache_and_absent_catalog(self):
        index,anchor=self.setup()
        cat=next(e for e in index.entities.values() if e.kind=="test_content_catalog")
        entry=cat.properties["entries"][0]
        index.entities[cat.id]=replace(cat,properties={**cat.properties,"entries":(entry,entry)})
        projection=TestContentProjection(index,Source())
        view=projection.finding((anchor.id,))[NAMESPACE]
        self.assertEqual(2,len(view["uses"]))
        self.assertEqual(len(set(entry["sourceEvidenceIds"])),len(view["sources"]))
        index.entities={}
        self.assertEqual({},TestContentProjection(index,Source()).finding((anchor.id,)))
