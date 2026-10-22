import json
import unittest
from dataclasses import replace
from pathlib import Path

from kb_scanner.core import Evidence, FrontendSnapshot, StageResult, WorkspaceSnapshot, stable_id
from kb_scanner.core.metadata import to_json_compatible
from kb_scanner.frontends.cpp.test_inventory import collect, cap_records
from kb_scanner.frontends.cpp.source_positions import SourceByteIndex
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from kb_scanner.frontends.cpp.frontend import CppFrontend
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from tests.unit.frontends.cpp.test_tree_sitter_adapter import Node
from tests.unit.frontends.cpp.test_frontend import FakeTree
from tests.unit.frontends.cpp.support import make_context


def sample(name="main", prefix=b""):
    source = prefix + ("int "+name+"(){return _x();}").encode()
    offset = len(prefix)
    ident = Node("identifier", offset+4, offset+4+len(name))
    decl = Node("function_declarator", ident.start_byte, ident.end_byte+2, children=(ident,),
                fields={"declarator": ident})
    start = source.index(b"_x")
    symbol = Node("identifier", start, start+2)
    args = Node("argument_list", start+2, start+4)
    call = Node("call_expression", start, start+4, children=(symbol,args),
                fields={"function":symbol,"arguments":args})
    ret = Node("return_statement", source.index(b"return"), len(source)-1, children=(call,))
    body = Node("compound_statement", source.index(b"{"), len(source), children=(ret,))
    fn = Node("function_definition", offset, len(source), children=(decl,body),
              fields={"declarator":decl,"body":body})
    root = Node("translation_unit", 0, len(source), children=(fn,))
    pos = SourceByteIndex.build("test.c", source)
    entity = make_source_file_entity("test.c", ("c",), "1")
    anchor = Evidence(stable_id("x"), "call_expression", entity.id, "_x", "fake", "fake",
                      "medium", pos.span(start,start+2))
    return root, source, pos, entity, anchor


def extract(data, **kw):
    return tuple(e for e in collect(*data[:3], data[3].id, "fake", (data[4],), **kw) if e.kind == "test_content")


class TestContentInventoryTests(unittest.TestCase):
    def test_scan_quota_is_forwarded_before_collecting_next_file(self):
        data=sample()
        item=extract(data)[0]
        item=replace(item,subject_id=make_source_file_entity("test.c",("c",),"0.1.0").id,
                     metadata={"testContent":{**item.metadata["testContent"],"recordCount":100000}})
        class Tree:
            calls=[]
            def analyze_file(self,*args,**kwargs):
                self.calls.append(kwargs)
                return StageResult((item,)) if len(self.calls)==1 else StageResult(())
        adapter=Tree()
        root=Path("/tmp")
        result=CppFrontend(adapter).analyze(make_context(root),WorkspaceSnapshot(root,("test.c","b.c")))
        self.assertIsNotNone(result.value)
        self.assertEqual({},adapter.calls[0])
        self.assertEqual({"test_record_limit":0},adapter.calls[1])

    def test_outside_prototype_names_are_retained_conservatively(self):
        data=sample()
        name=Node("identifier",4,8)
        prototype=Node("function_declarator",4,10,children=(name,),fields={"declarator":name})
        data[0].children.append(prototype)
        self.assertEqual(("main",),extract(data)[0].metadata["testContent"]["declaredNames"])
        prototype._fields["declarator"]=None
        self.assertEqual((),extract(data)[0].metadata["testContent"]["declaredNames"])

    def test_scalar_structure_stable_identity_and_utf8(self):
        data = sample(prefix="// 中文\n".encode())
        item, = extract(data)
        view = item.metadata["testContent"]
        self.assertEqual("complete", view["status"])
        self.assertEqual("main", view["functions"][0]["name"])
        self.assertTrue(view["functions"][0]["plain"])
        self.assertEqual(2,view["functions"][0]["nameSpan"][0])
        self.assertGreater(view["recordCount"],1)
        self.assertEqual(item,extract(data)[0])
        self.assertIn("call_expression",json.dumps(to_json_compatible(item.metadata)))
        context=make_context(Path("/tmp"))
        result=CppEvidenceNormalizer().normalize(context,FrontendSnapshot((data[3],),(data[4],item)))
        self.assertTrue(any(f.kind=="test_content" for f in result.value.facts))
        self.assertIn(item,result.value.evidence)

    def test_no_anchors_and_no_functions(self):
        data=sample()
        self.assertEqual((),collect(*data[:3],data[3].id,"fake",()))
        self.assertEqual((),collect(*data[:3],data[3].id,"fake",(replace(data[4],location=None),)))
        data[0].children=[]
        self.assertEqual((),extract(data))

    def test_only_main_or_anchored_body_is_materialized(self):
        data=sample("helper")
        anchored=extract(data)[0].metadata["testContent"]
        self.assertTrue(anchored["functions"][0]["records"])
        before=replace(data[4],location=data[2].span(len(data[1]),len(data[1])))
        data=(*data[:4],before)
        detail=extract(data)[0].metadata["testContent"]["functions"][0]
        self.assertEqual((),detail["records"])
        self.assertEqual("helper",detail["name"])

    def test_unsafe_owner_missing_shape_and_nested_exclusion(self):
        data=sample()
        fn=data[0].children[0]
        data[0].children=[Node("template_declaration",0,len(data[1]),children=(fn,))]
        detail=extract(data)[0].metadata["testContent"]["functions"][0]
        self.assertFalse(detail["plain"])
        self.assertEqual("partial",detail["status"])
        data=sample()
        fn=data[0].children[0]
        body=fn._fields["body"]
        body.children=[Node("lambda_expression",body.start_byte+1,body.end_byte-1)]
        self.assertEqual(1,len(extract(data)[0].metadata["testContent"]["functions"][0]["nestedSpans"]))
        fn._fields["declarator"]=None
        item=extract(data)[0]
        self.assertIn("test-content-function-shape-unknown",item.metadata["testContent"]["reasonCodes"])

    def test_budget_validation_and_scan_cap(self):
        data=sample()
        for limit in (-1,True,1.5,10001):
            with self.assertRaises(ValueError): extract(data,limit=limit)
        for limit in (0,1,3):
            item=extract(data,limit=limit)[0]
            self.assertEqual("partial",item.metadata["testContent"]["status"])
            self.assertLessEqual(item.metadata["testContent"]["recordCount"],limit)
        item=extract(data)[0]
        count=item.metadata["testContent"]["recordCount"]
        self.assertEqual((item,0),cap_records(item,count))
        trimmed,left=cap_records(item,count-1)
        self.assertEqual(0,left)
        self.assertEqual((),trimmed.metadata["testContent"]["functions"])
        self.assertEqual(item.id,trimmed.id)
        self.assertIn("test-content-scan-budget",trimmed.metadata["testContent"]["reasonCodes"])
        self.assertEqual((data[4],2),cap_records(data[4],2))

    def test_partial_parse_never_complete(self):
        data=sample()
        data[0].children[0]._fields["body"].is_error=True
        view=extract(data)[0].metadata["testContent"]
        self.assertEqual("partial",view["status"])
        self.assertIn("usage-partial-parse",view["reasonCodes"])

    def test_frontend_retains_test_records_and_counts_independently(self):
        data=sample()
        scope=extract(data)[0]
        root=Path("/tmp")
        entity=make_source_file_entity("test.c",("c",),"0.1.0")
        original=replace(data[4],subject_id=entity.id)
        scope=replace(scope,subject_id=entity.id)
        result=CppFrontend(FakeTree([StageResult((original,scope))])).analyze(
            make_context(root),WorkspaceSnapshot(root,("test.c",)))
        self.assertIn(scope,result.value.evidence)
        self.assertIn(original,result.value.evidence)
