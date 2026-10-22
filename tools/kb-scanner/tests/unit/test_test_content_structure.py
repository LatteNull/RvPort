import unittest
from copy import deepcopy
from kb_scanner.analyzers.test_content_structure import FunctionIndex, ContentIndex, contains
from tests.unit.test_content_support import straight_rows, function, data


class TestContentStructureTests(unittest.TestCase):
    def test_prototypes_recursion_and_framework_remain_unknown(self):
        helper=function(name="_x",span=(2,1,3,1))
        result=ContentIndex(data(function(),helper,declaredNames=("_x",),hasIncludes=True)).resolve((2,4))
        self.assertIn("test-function-declaration-binding-unknown",result["reasonCodes"])
        self.assertIn("test-function-include-binding-unknown",result["reasonCodes"])
        self.assertIn("test-recursive-call-unsupported",result["reasonCodes"])
        result=ContentIndex(data(function(name="TEST"))).resolve((1,21))
        self.assertIn("test-framework-unsupported",result["reasonCodes"])

    def test_local_value_binding_and_direct_assert(self):
        idx=FunctionIndex(function())
        result=idx.context((1,21))
        self.assertEqual("local-value-to-assert",result["relation"])
        self.assertEqual((),result["reasonCodes"])
        self.assertEqual((1,41,1,80),result["assertionSpan"])
        self.assertEqual("assert-argument",idx.context((1,49))["relation"])
        self.assertEqual("lexical",idx.context((1,99))["relation"])
        self.assertTrue(contains((1,1,2,1),(1,1)))
        self.assertFalse(contains((1,1,2,1),(2,1)))

    def test_nested_control_partial_and_parent_cycle(self):
        records=straight_rows()
        idx=FunctionIndex(function(records,nestedSpans=((1,20,1,29),)))
        self.assertEqual(("test-nested-callable",),idx.context((1,21))["reasonCodes"])
        records[-2]["kind"]="if_statement"
        idx=FunctionIndex(function(records))
        self.assertIn("test-control-selection-unknown",idx.context((1,49))["reasonCodes"])
        records=straight_rows()
        records[0]["parent"]=records[0]["key"]
        idx=FunctionIndex(function(records))
        self.assertIn("test-binding-budget",idx.context((1,21))["reasonCodes"])
        self.assertFalse(idx.ancestors(records[-1],limit=1)[1])

    def test_non_scalar_missing_use_and_missing_scope(self):
        for mutation in ("pointer","type","scope","no_use","other_block"):
            records=straight_rows()
            if mutation=="pointer": records[5]["kind"]="pointer_declarator"
            if mutation=="type": records[3]["kind"]="type_identifier"
            if mutation=="scope": records[1]["kind"]="if_statement"
            if mutation=="no_use": records[-1]["binding"]["status"]="unknown"
            if mutation=="other_block": records[8]["parent"]=None
            result=FunctionIndex(function(records)).context((1,21))
            if mutation=="no_use":
                self.assertEqual("body",result["relation"])
            else:
                self.assertEqual("unknown",result["relation"])
                self.assertTrue(result["reasonCodes"])

    def test_intervening_statement_reassignment_escape(self):
        for mutation, reason in (("statement","test-binding-intervening-statement"),
                                 ("write","test-binding-reassigned"),("escape","test-binding-escaped")):
            records=straight_rows()
            if mutation=="statement":
                records[1]["children"]=(*records[1]["children"],(32,38,"return_statement"))
                records.append({"key":(32,38,"return_statement"),"kind":"return_statement","parent":records[1]["key"],
                    "fields":{},"children":(),"text":"","span":(1,33,1,39)})
            elif mutation=="write": records[-1]["binding"]["role"]="read_write"
            else: records[-2]["kind"]="pointer_expression"
            result=FunctionIndex(function(records)).context((1,21))
            self.assertIn(reason,result["reasonCodes"])
            self.assertEqual("unknown",result["relation"])

    def test_direct_call_requires_identifier_without_shadow(self):
        records=straight_rows()
        idx=FunctionIndex(function(records))
        self.assertTrue(idx.direct(records[6]))
        records[7]["binding"]={"status":"bound"}
        self.assertFalse(FunctionIndex(function(records)).direct(records[6]))
        records[7]["kind"]="field_expression"
        idx=FunctionIndex(function(records))
        self.assertEqual("",idx.name(records[6]))
        self.assertFalse(idx.direct(records[6]))

    def test_content_index_main_file_boundaries_partial_and_cache(self):
        idx=ContentIndex(data())
        result=idx.resolve((1,21))
        self.assertEqual("complete",result["entryStatus"])
        self.assertEqual("main",result["function"])
        idx.resolve((1,49))
        self.assertEqual(1,len(idx.cache))
        self.assertEqual(2,idx.queries)
        self.assertEqual("file",idx.resolve((2,1))["relation"])
        self.assertEqual("file",idx.resolve((0,1))["relation"])
        for changes in ({"plain":False},{"name":"notmain"},{"nestedSpans":((1,20,1,29),)}):
            result=ContentIndex(data(function(**changes))).resolve((1,21))
            self.assertEqual("unknown",result["entryStatus"])
        result=ContentIndex(data(status="partial",reasonCodes=("budget",))).resolve((1,21))
        self.assertEqual("unknown",result["entryStatus"])
        self.assertIn("budget",result["reasonCodes"])

    def test_unique_helper_call_and_duplicate_name_or_missing_call(self):
        main=function()
        helper=function(records=[],name="_x",span=(2,1,3,1),bodySpan=(2,1,3,1))
        # Helper is lexical-only because its body has no structural anchor.
        result=ContentIndex(data(main,helper)).resolve((2,4))
        self.assertEqual("unknown",result["entryStatus"])
        self.assertIn("callSpan",result)
        self.assertEqual("main",ContentIndex(data(main,helper)).resolve((1,21))["function"])
        duplicated=deepcopy(helper); duplicated["span"]=(4,1,5,1)
        self.assertIn("test-function-name-not-unique",ContentIndex(data(main,helper,duplicated)).resolve((2,4))["reasonCodes"])
        helper["name"]="unused"
        self.assertIn("test-entry-call-not-unique",ContentIndex(data(main,helper)).resolve((2,4))["reasonCodes"])

    def test_helper_call_under_control_and_unknown_callee(self):
        records=straight_rows()
        records[4]["kind"]="if_statement"
        main=function(records)
        helper=function(records=[],name="_x",span=(2,1,3,1))
        result=ContentIndex(data(main,helper)).resolve((2,4))
        self.assertIn("test-control-selection-unknown",result["reasonCodes"])
        records[7]["kind"]="field_expression"
        result=ContentIndex(data(function(records),helper)).resolve((2,4))
        self.assertIn("test-entry-call-not-unique",result["reasonCodes"])
