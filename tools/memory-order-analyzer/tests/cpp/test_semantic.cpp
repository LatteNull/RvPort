#include "semantic.h"
#include <gtest/gtest.h>
#include <llvm/AsmParser/Parser.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/IR/Verifier.h>

using namespace llvm;
namespace {
struct Sample {
  LLVMContext context;
  std::unique_ptr<Module> module;
  json::Object facts;
  explicit Sample(const char *ir) {
    SMDiagnostic error;
    module = parseAssemblyString(ir, error, context);
    if (!module) { error.print("semantic-unit", errs()); throw std::runtime_error("Invalid test IR"); }
    if (verifyModule(*module, &errs())) throw std::runtime_error("Invalid test module");
    facts = moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'));
  }
  json::Object &find(StringRef category, StringRef field, StringRef value) {
    for (auto &item : *facts.getArray(category))
      if (item.getAsObject()->getString(field) == value) return *item.getAsObject();
    throw std::runtime_error("Missing test fact: " + value.str());
  }
  json::Object &node(StringRef id) { return find("values", "id", id); }
  json::Object &opcode(StringRef opcode) {
    for (auto &item : *facts.getArray("values"))
      if (item.getAsObject()->getObject("details")->getString("opcode") == opcode) return *item.getAsObject();
    throw std::runtime_error("Missing opcode: " + opcode.str());
  }
  json::Object &event(StringRef kind) { return find("events", "kind", kind); }
};
}

TEST(Semantic, CyclicPhiTypedConstantsAndOperations) {
  Sample s(R"(
target datalayout = "e-p:64:64"
@wide = global i128 18446744073709551617
@small = global i8 1
@nil = global ptr null
@u = global i32 undef
@p = global i32 poison
@zero = global {i32, ptr} zeroinitializer
@data = global [2 x i32] [i32 7, i32 8]
@mixed = global {i32, ptr} {i32 3, ptr @wide}
@recursive = global ptr @recursive
@decl = external global i32
define i32 @loop(i32 %arg, i1 %condition) {
entry: br label %loop
loop:
  %p = phi i32 [ %arg, %entry ], [ %next, %loop ]
  %f = freeze i32 %p
  %narrow = trunc i32 %f to i8
  %signed = sext i8 %narrow to i32
  %unsigned = zext i8 %narrow to i32
  %sum = add nsw nuw i32 %signed, %unsigned
  %quot = sdiv exact i32 %sum, 2
  %next = select i1 %condition, i32 %quot, i32 1
  %cmp = icmp ult i32 %next, 20
  br i1 %cmp, label %loop, label %end
end: ret i32 %next
}
)");
  EXPECT_EQ(s.facts.getObject("extraction")->getString("status"), "complete");
  auto &wide = s.node(*s.find("globals", "name", "wide").getObject("initializer")->getString("value_ref"));
  EXPECT_EQ(wide.getInteger("bits"), 128);
  EXPECT_EQ(wide.getObject("details")->getString("hex"), "10000000000000001");
  EXPECT_EQ(s.find("globals", "name", "decl").getObject("initializer")->getString("state"), "declaration");
  for (auto kind : {"null", "undef", "poison", "zero", "aggregate"}) EXPECT_EQ(s.find("values", "kind", kind).getString("status"), "known");
  auto &phi = s.opcode("phi");
  ASSERT_EQ(phi.getArray("operands")->size(), 2u);
  EXPECT_EQ((*phi.getArray("operands"))[1], json::Value(s.opcode("select").getString("id")->str()));
  EXPECT_EQ(phi.getObject("details")->getArray("incoming")->size(), 2u);
  EXPECT_EQ(s.opcode("add").getObject("details")->getBoolean("nsw"), true);
  EXPECT_EQ(s.opcode("add").getObject("details")->getBoolean("nuw"), true);
  EXPECT_EQ(s.opcode("sdiv").getObject("details")->getBoolean("exact"), true);
  EXPECT_EQ(s.opcode("icmp").getObject("details")->getString("predicate"), "ult");
  for (auto op : {"freeze", "trunc", "sext", "zext"}) EXPECT_EQ(s.opcode(op).getString("status"), "known");
  auto &function = s.find("functions", "name", "loop");
  EXPECT_EQ(function.getArray("parameters")->size(), 2u);
  auto *edges = (*function.getArray("blocks"))[1].getAsObject()->getObject("terminator")->getArray("edges");
  EXPECT_EQ((*edges)[0].getAsObject()->getString("kind"), "true");
  EXPECT_EQ((*edges)[1].getAsObject()->getString("kind"), "false");
  EXPECT_EQ(json::Value(json::Object(s.facts)), json::Value(moa::extract(*s.module, std::string(64, 'a'), std::string(64, 'b'))));
}

TEST(Semantic, SwitchCasAggregateAndReturnChain) {
  Sample s(R"(
target datalayout = "e-p:64:64"
@x = global i32 0
define {i32, i1} @cas(i128 %tag) {
entry:
  %cas = cmpxchg weak volatile ptr @x, i32 0, i32 1 acq_rel acquire
  %old = extractvalue {i32, i1} %cas, 0
  %ok = extractvalue {i32, i1} %cas, 1
  br i1 %ok, label %choose, label %end
choose:
  switch i128 %tag, label %end [i128 18446744073709551617, label %end
                               i128 -1, label %end]
end:
  %pair = insertvalue {i32, i1} %cas, i32 %old, 0
  ret {i32, i1} %pair
}
define void @stop() { unreachable }
)");
  auto &event = s.event("cmpxchg");
  EXPECT_EQ(event.getBoolean("volatile"), true);
  EXPECT_EQ(event.getObject("inputs")->size(), 2u);
  EXPECT_EQ(s.node(*event.getString("result_ref")).getObject("details")->getString("opcode"), "cmpxchg");
  EXPECT_EQ(s.opcode("extractvalue").getObject("details")->getArray("indices")->size(), 1u);
  EXPECT_EQ(s.opcode("insertvalue").getObject("details")->getArray("indices")->size(), 1u);
  auto *blocks = s.find("functions", "name", "cas").getArray("blocks");
  auto *edges = (*blocks)[1].getAsObject()->getObject("terminator")->getArray("edges");
  ASSERT_EQ(edges->size(), 3u);
  EXPECT_EQ((*edges)[0].getAsObject()->getString("kind"), "default");
  EXPECT_EQ((*edges)[1].getAsObject()->getString("target"), (*edges)[2].getAsObject()->getString("target"));
  EXPECT_NE((*edges)[1].getAsObject()->getString("case_ref"), (*edges)[2].getAsObject()->getString("case_ref"));
  EXPECT_EQ(s.node(*(*edges)[1].getAsObject()->getString("case_ref")).getInteger("bits"), 128);
  EXPECT_EQ((*blocks)[2].getAsObject()->getObject("terminator")->getString("return_ref"), s.opcode("insertvalue").getString("id"));
}

TEST(Semantic, CallsInvokeBundlesAndUnknowns) {
  Sample s(R"(
declare i32 @personality(...)
declare i32 @callee(i32, ...)
declare void @sink(ptr)
define i32 @calls(ptr %fp) personality ptr @personality {
entry:
  %tail = tail call i32 (i32, ...) @callee(i32 signext 1, i64 2)
  %indirect = call i32 %fp(i32 %tail) [ "deopt"(i32 3) ]
  call void @sink(ptr null)
  %result = invoke i32 (i32, ...) @callee(i32 %indirect) to label %ok unwind label %bad
ok: ret i32 %result
bad:
  %landing = landingpad { ptr, i32 } cleanup
  resume { ptr, i32 } %landing
}
)");
  auto *calls = s.facts.getArray("calls");
  ASSERT_EQ(calls->size(), 4u);
  auto &first = *(*calls)[0].getAsObject();
  EXPECT_EQ(first.getArray("arguments")->size(), 2u);
  EXPECT_NE(first.getString("tail"), "0");
  EXPECT_EQ(first.getString("attribute_status"), "unknown");
  EXPECT_FALSE(first.getString("attributes")->empty());
  EXPECT_EQ((*calls)[1].getAsObject()->getArray("bundles")->size(), 1u);
  EXPECT_EQ((*calls)[1].getAsObject()->getString("status"), "unknown");
  EXPECT_TRUE((*calls)[2].getAsObject()->get("result_ref")->getAsNull().has_value());
  EXPECT_EQ((*calls)[2].getAsObject()->getString("attribute_status"), "not_applicable");
  EXPECT_EQ((*calls)[2].getAsObject()->getString("attributes"), "");
  EXPECT_TRUE((*calls)[3].getAsObject()->getString("normal").has_value());
  EXPECT_TRUE((*calls)[3].getAsObject()->getString("unwind").has_value());
  EXPECT_EQ(s.find("functions", "name", "callee").getBoolean("vararg"), true);
  auto *blocks = s.find("functions", "name", "calls").getArray("blocks");
  EXPECT_EQ((*blocks)[2].getAsObject()->getObject("terminator")->getString("status"), "unknown");
  EXPECT_EQ(s.facts.getObject("extraction")->getString("status"), "partial");
}

TEST(Semantic, DataLayoutRangesOffsetsAndIntrinsics) {
  Sample s(R"(
target datalayout = "e-p:64:64-p1:128:128:128:128-i64:64"
@object = global {i8, i32} zeroinitializer
declare void @llvm.memcpy.p0.p1.i64(ptr, ptr addrspace(1), i64, i1)
declare void @llvm.memmove.p0.p0.i64(ptr, ptr, i64, i1)
declare void @llvm.memset.p0.i64(ptr, i8, i64, i1)
define void @ranges(ptr %p, ptr addrspace(1) %q, i64 %index) {
  %value = load {i8, i32}, ptr @object, align 4
  store {i8, i32} %value, ptr %p, align 1
  %neg = getelementptr i32, ptr %p, i64 -1
  %a = load i32, ptr %neg, align 2
  %wide = getelementptr i8, ptr addrspace(1) %q, i128 18446744073709551617
  %b = load i8, ptr addrspace(1) %wide
  %dynamic = getelementptr i8, ptr %p, i64 %index
  %c = load i8, ptr %dynamic
  %cast = addrspacecast ptr addrspace(1) %q to ptr
  %d = load i8, ptr %cast
  %int = inttoptr i64 %index to ptr
  %e = load i8, ptr %int
  %r = atomicrmw add ptr %p, i32 1 monotonic
  fence seq_cst
  call void @llvm.memcpy.p0.p1.i64(ptr align 2 %p, ptr addrspace(1) align 16 %q, i64 0, i1 false)
  call void @llvm.memmove.p0.p0.i64(ptr %p, ptr %neg, i64 %index, i1 false)
  call void @llvm.memset.p0.i64(ptr %p, i8 42, i64 3, i1 false)
  ret void
}
)");
  auto &load = s.event("load");
  auto *range = (*load.getArray("ranges"))[0].getAsObject();
  EXPECT_EQ(range->getObject("size")->getString("bytes"), "8");
  EXPECT_EQ(range->getInteger("alignment"), 4);
  auto &fence = s.event("fence");
  EXPECT_EQ(fence.getString("range_status"), "not_applicable");
  EXPECT_TRUE(fence.getArray("ranges")->empty());
  bool negative = false, wide = false, dynamic = false;
  for (auto &value : *s.facts.getArray("values")) {
    auto *detail = value.getAsObject()->getObject("details");
    if (auto *offset = detail->getObject("offset")) {
      negative |= offset->getString("signed_decimal") == "-4";
      wide |= offset->getString("signed_decimal") == "18446744073709551617" && offset->getInteger("bits") == 128;
      dynamic |= offset->getString("status") == "unknown";
    }
  }
  EXPECT_TRUE(negative && wide && dynamic);
  EXPECT_EQ(s.opcode("addrspacecast").getString("status"), "unknown");
  EXPECT_EQ(s.opcode("inttoptr").getString("status"), "unknown");
  auto *copy = s.event("llvm.memcpy.p0.p1.i64").getArray("ranges");
  ASSERT_EQ(copy->size(), 2u);
  EXPECT_EQ((*copy)[0].getAsObject()->getObject("size")->getString("bytes"), "0");
  EXPECT_EQ((*copy)[1].getAsObject()->getInteger("address_space"), 1);
  EXPECT_EQ((*copy)[1].getAsObject()->getInteger("alignment"), 16);
  EXPECT_EQ((*s.event("llvm.memmove.p0.p0.i64").getArray("ranges"))[0].getAsObject()->getObject("size")->getString("reason"), "dynamic_length");
  EXPECT_EQ(s.node(*s.event("llvm.memset.p0.i64").getObject("inputs")->getString("fill")).getObject("details")->getString("hex"), "2A");
  EXPECT_EQ(s.event("atomicrmw").getObject("inputs")->size(), 1u);
}

TEST(Semantic, MissingScalableLayoutAndUnsupportedValues) {
  Sample noLayout(R"(
@float = global double 1.25
define double @f(ptr %p) {
 %g = getelementptr i32, ptr %p, i64 1
 %i = load i32, ptr %g
 %a = fadd double 1.0, 2.0
 ret double %a
}
)");
  EXPECT_EQ((*noLayout.event("load").getArray("ranges"))[0].getAsObject()->getObject("size")->getString("reason"), "layout_unavailable");
  EXPECT_EQ(noLayout.opcode("getelementptr").getObject("details")->getObject("offset")->getString("reason"), "layout_unavailable");
  EXPECT_EQ(noLayout.opcode("fadd").getString("status"), "unknown");
  EXPECT_EQ(noLayout.find("values", "kind", "unknown").getString("reason"), "unsupported_value");
  Sample scalable(R"(
target datalayout = "e-p:64:64"
define void @f(ptr %p) {
 %v = load <vscale x 4 x i32>, ptr %p
 store <vscale x 4 x i32> %v, ptr %p
 ret void
}
)");
  EXPECT_EQ((*scalable.event("load").getArray("ranges"))[0].getAsObject()->getObject("size")->getString("reason"), "scalable_size");
}

TEST(Semantic, BudgetsProtocolEmptyAndLifetime) {
  Sample empty("declare void @empty()\n");
  EXPECT_EQ(empty.facts.getObject("extraction")->getInteger("roots"), 0);
  EXPECT_EQ(empty.facts.getObject("extraction")->getInteger("nodes"), 0);
  EXPECT_EQ(empty.facts.getObject("extraction")->getString("status"), "complete");
  Sample s("@a = global [2 x i32] [i32 1, i32 2]\n");
  auto budget = moa::defaultBudget();
  budget.nodes = *s.facts.getObject("extraction")->getInteger("nodes");
  budget.references = *s.facts.getObject("extraction")->getInteger("references");
  EXPECT_NO_THROW(moa::enrich(*s.module, s.facts, budget));
  auto nodes = budget; nodes.nodes--;
  EXPECT_THROW(moa::enrich(*s.module, s.facts, nodes), std::runtime_error);
  auto references = budget; references.references--;
  EXPECT_THROW(moa::enrich(*s.module, s.facts, references), std::runtime_error);
  auto output = budget; output.output = 1;
  EXPECT_THROW(moa::enrich(*s.module, s.facts, output), std::runtime_error);
  auto depth = budget; depth.depth = 0;
  moa::enrich(*s.module, s.facts, depth);
  EXPECT_EQ(s.facts.getObject("extraction")->getString("status"), "partial");
  EXPECT_EQ(s.find("values", "kind", "unknown").getString("reason"), "constant_depth");
  json::Value before(json::Object(s.facts));
  s.module.reset();
  std::vector<std::string> overwrite(10000, std::string(128, 'x'));
  EXPECT_EQ(before, json::Value(json::Object(s.facts)));
  const char *args[] = {"worker", "--protocol"};
  std::string text, errors;
  raw_string_ostream out(text), err(errors);
  EXPECT_EQ(moa::worker(2, args, out, err), 0);
  auto parsed = cantFail(json::parse(text));
  EXPECT_EQ(parsed, json::Value(moa::protocol()));
  EXPECT_EQ(moa::protocol().getInteger("facts_version"), 2);
}

TEST(Semantic, UnnamedSymbolsAndPaddingFieldOffsets) {
  Sample s(R"(
target datalayout = "e-p:64:64"
@0 = internal global i32 1
@1 = internal global i32 2
@obj = global {i8, i32} zeroinitializer
define i32 @2() {
 %a = load i32, ptr @0
 %b = load i32, ptr @1
 %field = getelementptr inbounds {i8, i32}, ptr @obj, i64 0, i32 1
 %c = load i32, ptr %field
 %sum = add i32 %a, %b
 %result = add i32 %sum, %c
 ret i32 %result
}

)");
  auto *globals = s.facts.getArray("globals");
  EXPECT_NE((*globals)[0].getAsObject()->getString("id"), (*globals)[1].getAsObject()->getString("id"));
  EXPECT_NE((*globals)[0].getAsObject()->getObject("initializer")->getString("value_ref"), (*globals)[1].getAsObject()->getObject("initializer")->getString("value_ref"));
  auto &gep = s.opcode("getelementptr");
  EXPECT_EQ(gep.getObject("details")->getObject("offset")->getString("signed_decimal"), "4");
  EXPECT_EQ(gep.getObject("details")->getBoolean("inbounds"), true);
  EXPECT_EQ((*(*s.facts.getArray("events"))[2].getAsObject()->getArray("ranges"))[0].getAsObject()->getObject("size")->getString("bytes"), "4");
  EXPECT_EQ(json::Value(json::Object(s.facts)), json::Value(moa::extract(*s.module, std::string(64, 'a'), std::string(64, 'b'))));
}

TEST(Semantic, InstructionDepthIsNotConstantNesting) {
  std::string ir = "define i32 @chain(i32 %arg) {\n";
  std::string previous = "%arg";
  for (int n = 0; n < 80; ++n) {
    auto current = "%v" + std::to_string(n);
    ir += current + " = add i32 " + previous + ", 1\n";
    previous = current;
  }
  ir += "ret i32 " + previous + "\n}";
  Sample s(ir.c_str());
  auto budget = moa::defaultBudget(); budget.depth = 1;
  moa::enrich(*s.module, s.facts, budget);
  EXPECT_EQ(s.facts.getObject("extraction")->getString("status"), "complete");
  EXPECT_EQ(s.facts.getObject("extraction")->getInteger("nodes"), 82);
}
