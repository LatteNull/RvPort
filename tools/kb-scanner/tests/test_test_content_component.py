"""真实语法/静态 CLI 组件审校；不作为隔离单元覆盖率。"""
import gc
import json
from pathlib import Path
import tempfile
import unittest

from tests import test_cmake_source_component as support
from kb_scanner.frontends.cpp.assert_profile import capture
from kb_scanner.projection.v2.test_content import NAMESPACE


class OriginalTestContentComponentTests(unittest.TestCase):
    scan = support.CMakeSourceComponentTests.scan

    def test_compile_argument_is_not_implicitly_exercised_by_ctest_source_membership(self):
        from tests.test_compatible_cutover_differential import run
        from kb_scanner.pipeline.default import create_default_application
        from unittest.mock import patch
        root=Path(__file__).resolve().parents[1]/"tests/fixtures/build-selection/project"
        with patch("subprocess.run",side_effect=AssertionError("不得执行项目命令")):
            result,report=run(create_default_application(),root)
        self.assertEqual(0,result.exit_code)
        self.assertEqual((8,1),(report["summary"]["findings"],report["summary"]["blocking"]))
        test=next(f for f in report["findings"] if f["rule_id"]=="TEST.X86.SELECTION")
        self.assertEqual("ctest-v1.json",test["symbol"])
        self.assertEqual(1,test["trace"]["occurrenceCount"])
        self.assertFalse(any(e["producer"]=="compilation-database-reader" and e["value"]=="-march=rv64gc"
                             for e in test["trace"]["evidence"]))
        self.assertFalse(any(r["kind"]=="exercises" and r["target"]=="-march=rv64gc"
                             for r in test["trace"]["relations"]))
        flag=next(f for f in report["findings"] if f["symbol"]=="-march=rv64gc" and f["source_kind"]=="compile_command")
        self.assertEqual("medium",flag["severity"])
        self.assertTrue(any(e["value"]=="-march=rv64gc" for e in flag["trace"]["evidence"]))
        self.assertTrue(flag["trace"]["relations"])
        self.assertEqual({"adds_argument"},
                         {r["kind"] for r in flag["trace"]["relations"]})

    def project(self, source, extra="", name="test.c"):
        return {"CMakeLists.txt": "enable_testing()\nadd_executable(unit "+name+")\nadd_test(NAME verify COMMAND unit)\n"+extra,
                name: source}

    def usages(self, report, symbol="_mm_setzero_si128"):
        return [use for finding in report["findings"] if finding["fact"]["symbol"]==symbol
                for use in finding["fact"].get("extensions",{}).get(NAMESPACE,{}).get("uses",())]

    def test_direct_and_scalar_asserts_are_relations_not_success(self):
        for source, expected in (("int main(){assert(_mm_setzero_si128());}","assert-argument"),
                ("int main(){int value=_mm_setzero_si128(); assert(value);}","local-value-to-assert")):
            report,html=self.scan(self.project(source))
            uses=self.usages(report)
            self.assertTrue(uses)
            self.assertTrue(all(u["content"]["relation"]==expected for u in uses))
            self.assertTrue(all(u["assertion"]["status"]=="unknown" for u in uses))
            self.assertIn("原始测试内容",html)
            self.assertTrue(all(u["description_en"] for u in uses))

    def test_disabled_registration_does_not_remove_compilation_risk(self):
        report,_=self.scan(self.project("int main(){return _mm_setzero_si128();}",
                            "set_tests_properties(verify PROPERTIES DISABLED TRUE)\n"))
        finding=next(f for f in report["findings"] if f["fact"]["symbol"]=="_mm_setzero_si128")
        use,=self.usages(report)
        self.assertEqual(("selected","not_selected"),(use["buildStatus"],use["registrationStatus"]))
        self.assertEqual("high",finding["conclusion"]["severity"])
        self.assertTrue(finding["conclusion"]["blocking"])

    def test_architecture_isolation_and_data_enum_are_not_runtime_blockers(self):
        files=self.project("int main(){return _mm_setzero_si128();}")
        files["CMakeLists.txt"]="if(CMAKE_SYSTEM_PROCESSOR STREQUAL x86_64)\n"+files["CMakeLists.txt"]+"endif()\n"
        report,_=self.scan(files)
        finding=next(f for f in report["findings"] if f["fact"]["symbol"]=="_mm_setzero_si128")
        self.assertFalse(finding["conclusion"]["blocking"])
        self.assertEqual("inactive",finding["conclusion"]["status"])
        report,_=self.scan(self.project("int main(){enum Codec { X86_FILTER=4 }; int codec=X86_FILTER; assert(codec==X86_FILTER);}"))
        self.assertTrue(report["findings"])
        self.assertFalse(any(f["conclusion"]["blocking"] for f in report["findings"]))
        self.assertTrue(all(f["conclusion"]["status"]!="complete" for f in report["findings"]))

    def test_framework_macro_is_not_a_confirmed_entry(self):
        report,_=self.scan(self.project("TEST(Suite, Feature) { assert(_mm_setzero_si128()); }",name="test.cpp"))
        uses=self.usages(report)
        self.assertTrue(uses)
        self.assertTrue(all(u["content"]["entryStatus"]=="unknown" for u in uses))

    def test_unique_one_hop_unused_overload_and_runtime_condition(self):
        for source, status, reason in (
            ("int helper(){return _mm_setzero_si128();} int main(){helper();}","complete",None),
            ("int helper(){return _mm_setzero_si128();} int main(){return 0;}","unknown","test-entry-call-not-unique"),
            ("int helper(int); int helper(){return _mm_setzero_si128();} int main(){helper();}","unknown","test-function-declaration-binding-unknown"),
            ("int helper(){return _mm_setzero_si128();} int main(){if(flag) helper();}","unknown","test-control-selection-unknown")):
            report,_=self.scan(self.project(source,name="test.cpp"))
            uses=self.usages(report)
            self.assertTrue(uses)
            self.assertEqual(status,uses[0]["content"]["entryStatus"])
            if reason: self.assertIn(reason,uses[0]["reasonCodes"])

    def test_rewrite_escape_and_nested_callable_do_not_prove_binding(self):
        for middle in ("value=0;", "escape(&value);", "if(flag) value=1;"):
            report,_=self.scan(self.project("int main(){int value=_mm_setzero_si128();"+middle+"assert(value);}"))
            self.assertEqual("unknown",self.usages(report)[0]["content"]["relation"])
        report,_=self.scan(self.project("int main(){auto unused=[](){return _mm_setzero_si128();};}",name="test.cpp"))
        self.assertIn("test-nested-callable",self.usages(report)[0]["reasonCodes"])

    def test_standard_observed_assert_profiles_survive_tu_lifetime(self):
        # Uses the installed parser, not a project command/preprocessor subprocess.
        from clang import cindex
        profiles=[]
        for args,status in ((["-xc"],"enabled"),(["-xc","-DNDEBUG"],"disabled"),(["-xc++"],"enabled")):
            tu=cindex.Index.create().parse("sample.c",args=args,
                unsaved_files=[("sample.c","#include <assert.h>\nint main(){assert(1);}")],
                options=cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
            self.assertFalse(list(tu.diagnostics))
            profiles.extend(capture(c,str(args),False) for c in tu.cursor.get_children()
                if c.kind.name=="MACRO_INSTANTIATION" and c.spelling=="assert")
            self.assertEqual(status,profiles[-1]["standardAssert"]["status"])
            del tu
        gc.collect()
        self.assertIn("observed-compilation-unit",json.dumps(profiles))

    def test_regular_asserts_do_not_create_architecture_findings_and_v1_still_publishes(self):
        source="#include <assert.h>\nint main(){int value=42; assert(value==42); assert(sizeof(long)==8);}"
        report,_=self.scan(self.project(source))
        self.assertFalse(report["findings"])
        report,html=self.scan(self.project("int main(){return _mm_setzero_si128();}"),version="1.0")
        self.assertEqual("1.0",report["schemaVersion"])
        self.assertTrue(html)

    def test_ndebug_custom_assert_partial_and_legacy_registration_remain_unknown(self):
        for source in ("#define NDEBUG\n#include <assert.h>\nint main(){assert(_mm_setzero_si128());}",
                       "#define assert(x) custom(x)\nint main(){assert(_mm_setzero_si128());}",
                       "int main(){assert(_mm_setzero_si128()); broken(}"):
            report,_=self.scan(self.project(source))
            uses=self.usages(report)
            self.assertTrue(uses)
            self.assertEqual("unknown",uses[0]["proofStatus"])
        files=self.project("int main(){return _mm_setzero_si128();}")
        files["CMakeLists.txt"]=files["CMakeLists.txt"].replace("NAME verify COMMAND unit","verify unit")
        report,_=self.scan(files)
        self.assertTrue(all(u["role"]=="candidate" for u in self.usages(report)))

    def test_finding_sources_are_closed_and_keep_twenty_line_context(self):
        source="\n"*25+"int main(){assert(_mm_setzero_si128());}"+"\n"*25
        report,_=self.scan(self.project(source))
        finding=next(f for f in report["findings"] if f["fact"]["symbol"]=="_mm_setzero_si128")
        view=finding["fact"]["extensions"][NAMESPACE]
        ids={s["id"] for s in view["sources"]}
        self.assertTrue(all(set(u["sourceIds"]).issubset(ids) for u in view["uses"]))
        self.assertIn("assert",json.dumps(view))
        contexts=[s["source"] for s in view["sources"] if s["source"]["file"]=="test.c"]
        self.assertTrue(contexts)
        for context in contexts:
            self.assertEqual(6,context["context"]["lines"][0]["line"])
            self.assertEqual(46,context["context"]["lines"][-1]["line"])
