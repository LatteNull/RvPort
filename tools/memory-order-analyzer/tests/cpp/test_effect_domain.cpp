#include "effect_domain.h"
#include <gtest/gtest.h>
#include <llvm/AsmParser/Parser.h>
#include <llvm/IR/Instructions.h>
#include <llvm/Support/SourceMgr.h>

using namespace llvm;
using namespace moa;
namespace {
std::unique_ptr<Module> parse(LLVMContext &context, const std::string &text) {
  SMDiagnostic error;
  auto module = parseAssemblyString(text, error, context);
  if (!module) error.print("domain-test", errs());
  return module;
}
Value *named(Function &function, StringRef name) {
  for (auto &arg : function.args()) if (arg.getName() == name) return &arg;
  for (auto &block : function) for (auto &i : block) if (i.getName() == name) return &i;
  return nullptr;
}
json::Object integer(unsigned bits, StringRef hex) { return json::Object{{"kind", "integer"}, {"bits", bits}, {"hex", hex.str()}}; }
json::Object special(StringRef kind) { return json::Object{{"kind", kind.str()}, {"reason", "test"}}; }
}

TEST(EffectDomain, PointerOriginsOffsetsAndConservativeConversions) {
  LLVMContext context;
  auto module = parse(context, R"(
  target datalayout = "e-p:64:64-p1:64:64:64:32-i64:64"
  @g = internal global i32 0
  @defined = dso_local global i32 0
  @outside = external global i32
@tls = internal thread_local global i32 0
@mergeable = private unnamed_addr constant i32 0
@alias = internal alias i32, ptr @g
define void @f(ptr %p, ptr %q, i64 %n, ptr addrspace(1) %as1) {
entry:
 %slot = alloca { i8, i32 }
 %field = getelementptr { i8, i32 }, ptr %slot, i64 0, i32 1
 %negative = getelementptr i32, ptr %slot, i64 -1
 %dynamic = getelementptr i8, ptr %slot, i64 %n
 %through = getelementptr i8, ptr %dynamic, i64 4
 %wide = getelementptr i8, ptr addrspace(1) %as1, i128 4294967300
 %overflow = getelementptr i64, ptr %slot, i64 9223372036854775807
 %max = getelementptr i8, ptr %slot, i64 9223372036854775807
 %sumoverflow = getelementptr i8, ptr %max, i64 1
 %cast = bitcast ptr %slot to ptr
 %convert = addrspacecast ptr %slot to ptr addrspace(1)
 %fromint = inttoptr i64 1 to ptr
 %scalable = getelementptr <vscale x 4 x i32>, ptr %slot, i64 1
 ret void
}
)");
  ASSERT_TRUE(module);
  auto &f = *module->getFunction("f");
  auto rawBefore = extract(*module, std::string(64, 'a'), std::string(64, 'b'));
  auto resolve = [&](Value *v, unsigned steps = 100000) { return pointerValue(v, *module, "a", "scope", "root", Cardinality::Single, GlobalBindings{}, steps); };
  auto field = resolve(named(f, "field"));
  EXPECT_EQ(field.kind, ObjectKind::Local); ASSERT_TRUE(field.offset); EXPECT_EQ(field.offset->getSExtValue(), 4);
  EXPECT_EQ(field.source, resolve(named(f, "slot")).source);
  EXPECT_EQ(resolve(named(f, "negative")).offset->getSExtValue(), -4);
  EXPECT_EQ(resolve(named(f, "wide")).offset->getSExtValue(), 4);
  EXPECT_EQ(resolve(named(f, "wide")).addressSpace, 1u);
  EXPECT_EQ(resolve(named(f, "cast")).source, field.source);
  for (auto name : {"dynamic", "through", "overflow", "sumoverflow", "scalable"}) {
    auto p = resolve(named(f, name)); EXPECT_TRUE(p.known()) << name; EXPECT_FALSE(p.offset) << name;
  }
  EXPECT_EQ(resolve(named(f, "p")).kind, ObjectKind::Parameter);
  EXPECT_EQ(resolve(module->getNamedGlobal("g")).kind, ObjectKind::Global);
  EXPECT_EQ(resolve(module->getNamedGlobal("defined")).kind, ObjectKind::Global);
  EXPECT_EQ(resolve(module->getNamedGlobal("outside")).reason, "unresolved_global_definition");
  for (auto name : {"tls", "mergeable"}) EXPECT_EQ(resolve(module->getNamedGlobal(name)).reason, "unsupported_global_identity");
  EXPECT_FALSE(resolve(module->getNamedAlias("alias")).known());
  for (auto name : {"convert", "fromint"}) EXPECT_EQ(resolve(named(f, name)).reason, "unsupported_pointer_conversion_or_origin");
  EXPECT_EQ(resolve(ConstantPointerNull::get(PointerType::get(context, 0))).reason, "unsupported_pointer_origin");
  EXPECT_EQ(resolve(named(f, "n")).reason, "not_pointer");
  EXPECT_EQ(resolve(named(f, "field"), 1).reason, "pointer_step_budget");
  EXPECT_EQ(resolve(named(f, "slot"), 0).reason, "pointer_step_budget");
  EXPECT_EQ(pointerValue(named(f, "slot"), *module, "a", "scope", "", Cardinality::Single, GlobalBindings{}).reason, "unbound_invocation");
  EXPECT_EQ(pointerValue(named(f, "p"), *module, "a", "scope", "", Cardinality::Single, GlobalBindings{}).reason, "unbound_invocation");
  EXPECT_EQ(json::Value(json::Object(rawBefore)), json::Value(extract(*module, std::string(64, 'a'), std::string(64, 'b'))));
  module->setDataLayout("");
  EXPECT_EQ(resolve(named(f, "slot")).reason, "missing_data_layout");
}

TEST(EffectDomain, AllocationInstancesCyclesAndExternBindings) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64"
@g = private global i32 0
@external = external global i32
define void @f(i1 %c) {
entry:
 %once = alloca i32
 br i1 %c, label %a, label %b
a:
 %repeat = alloca i32
 br label %b
b:
 br i1 %c, label %a, label %exit
exit:
 ret void
}
)");
  ASSERT_TRUE(module);
  auto &f = *module->getFunction("f");
  auto make = [&](StringRef name, StringRef activation, Cardinality card) {
    return pointerValue(named(f, name), *module, "a", "scope", activation, card, GlobalBindings{});
  };
  auto once = make("once", "call-1", Cardinality::Single);
  auto another = make("once", "call-2", Cardinality::Single);
  EXPECT_EQ(once.source, another.source); EXPECT_NE(once.invocation, another.invocation);
  EXPECT_EQ(once.cardinality, Cardinality::Single);
  auto repeated = make("repeat", "call-1", Cardinality::Single);
  EXPECT_EQ(repeated.cardinality, Cardinality::Merged); EXPECT_EQ(repeated.reason, "repeated_allocation");
  EXPECT_EQ(make("repeat", "recursive", Cardinality::Unknown).cardinality, Cardinality::Unknown);
  auto merged = make("once", "recursive", Cardinality::Merged);
  EXPECT_EQ(merged.reason, "non_single_invocation");
  auto global = pointerValue(module->getNamedGlobal("g"), *module, "b", "scope", "", Cardinality::Unknown, GlobalBindings{});
  GlobalBindings bindings; auto *external = module->getNamedGlobal("external"); bindings[external] = global;
  auto bound = pointerValue(external, *module, "a", "scope", "root", Cardinality::Single, bindings);
  EXPECT_EQ(bound.kind, ObjectKind::Global); EXPECT_EQ(bound.source, global.source); EXPECT_EQ(bound.artifact, "b");
  auto staticHere = pointerValue(module->getNamedGlobal("g"), *module, "a", "scope", "", Cardinality::Unknown, GlobalBindings{});
  EXPECT_NE(staticHere.source, global.source);
  EXPECT_EQ(compareRanges(staticHere, APInt(64, 4), global, APInt(64, 4)), RangeRelation::Disjoint);
  for (int mode = 0; mode < 7; ++mode) {
    auto bad = global;
    if (mode == 0) bad.kind = ObjectKind::Local;
    if (mode == 1) bad.scope = "other";
    if (mode == 2) bad.addressSpace = 1;
    if (mode == 3) bad.source.clear();
    if (mode == 4) bad.artifact.clear();
    if (mode == 5) bad.cardinality = Cardinality::Merged;
    if (mode == 6) bad.cardinality = Cardinality::Unknown;
    bindings[external] = bad;
    EXPECT_EQ(pointerValue(external, *module, "a", "scope", "root", Cardinality::Single, bindings).reason, "invalid_global_binding");
  }
  EXPECT_EQ(compareRanges(once, APInt(64, 4), another, APInt(64, 4)), RangeRelation::Disjoint);
  EXPECT_EQ(compareRanges(once, APInt(64, 4), merged, APInt(64, 4)), RangeRelation::Unknown);
  EXPECT_EQ(compareRanges(repeated, APInt(64, 4), repeated, APInt(64, 4)), RangeRelation::Unknown);
}

TEST(EffectDomain, ByteIntervalsDoNotInventAliasOrLifetimeProofs) {
  PointerValue p;
  p.kind = ObjectKind::Local; p.artifact = "a"; p.source = "alloca"; p.scope = "scope";
  p.invocation = "call"; p.cardinality = Cardinality::Single; p.offset = APInt(128, 0);
  auto q = p;
  EXPECT_EQ(compareRanges(p, APInt(128, 4), q, APInt(32, 4)), RangeRelation::Overlap);
  q.offset = APInt(128, 4);
  EXPECT_EQ(compareRanges(p, APInt(128, 4), q, APInt(64, 4)), RangeRelation::Disjoint);
  q.offset = APInt(128, 2);
  EXPECT_EQ(compareRanges(p, APInt(128, 4), q, APInt(64, 4)), RangeRelation::Overlap);
  q.offset = APInt(128, -2, true);
  EXPECT_EQ(compareRanges(p, APInt(128, 4), q, APInt(64, 4)), RangeRelation::Overlap);
  q.offset = APInt(128, "100000000000000000000", 10);
  EXPECT_EQ(compareRanges(p, APInt(128, 4), q, APInt(64, 4)), RangeRelation::Disjoint);
  q.offset = APInt::getSignedMaxValue(128); p.offset = q.offset;
  EXPECT_EQ(compareRanges(p, APInt::getMaxValue(128), q, APInt(64, 4)), RangeRelation::Overlap);
  for (int mode = 0; mode < 8; ++mode) {
    q = p;
    if (mode == 0) q.kind = ObjectKind::Unknown;
    if (mode == 1) q.scope = "other";
    if (mode == 2) q.addressSpace = 1;
    if (mode == 3) q.cardinality = Cardinality::Unknown;
    if (mode == 4) q.kind = ObjectKind::Parameter;
    if (mode == 5) q.offset.reset();
    if (mode == 6) q.scope.clear();
    if (mode == 7) q.cardinality = Cardinality::Merged;
    EXPECT_EQ(compareRanges(p, APInt(64, 4), q, APInt(64, 4)), RangeRelation::Unknown);
    EXPECT_EQ(compareRanges(q, APInt(64, 4), p, APInt(64, 4)), RangeRelation::Unknown);
  }
  EXPECT_EQ(compareRanges(p, std::nullopt, p, APInt(64, 4)), RangeRelation::Unknown);
  EXPECT_EQ(compareRanges(p, APInt(64, 4), p, std::nullopt), RangeRelation::Unknown);
  EXPECT_EQ(compareRanges(PointerValue{}, APInt(64, 0), PointerValue{}, std::nullopt), RangeRelation::Disjoint);
  EXPECT_EQ(compareRanges(PointerValue{}, std::nullopt, PointerValue{}, APInt(64, 0)), RangeRelation::Disjoint);
}

TEST(EffectDomain, ExactScalarFlagsAndWideIntegers) {
  struct Case { const char *operation; unsigned bits; const char *left; const char *right; const char *kind; const char *hex; };
  for (const auto &c : std::initializer_list<Case>{
    {"add", 128, "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF", "1", "integer", "0"},
    {"add nsw", 8, "7F", "1", "poison", ""}, {"add nuw", 8, "FF", "1", "poison", ""},
    {"sub nsw", 8, "80", "1", "poison", ""}, {"mul nuw", 8, "80", "2", "poison", ""},
    {"sub nuw", 8, "0", "1", "poison", ""}, {"mul nsw", 8, "40", "2", "poison", ""},
    {"shl nuw", 8, "80", "1", "poison", ""}, {"shl nsw", 8, "40", "1", "poison", ""},
    {"shl nsw nuw", 8, "1", "1", "integer", "2"}, {"add nsw nuw", 8, "1", "1", "integer", "2"},
    {"sub nsw nuw", 8, "2", "1", "integer", "1"}, {"mul nsw nuw", 8, "2", "2", "integer", "4"},
    {"sdiv", 8, "FE", "2", "integer", "FF"}, {"udiv", 8, "FE", "2", "integer", "7F"},
    {"udiv exact", 8, "7", "2", "poison", ""}, {"lshr exact", 8, "3", "1", "poison", ""},
    {"udiv exact", 8, "8", "2", "integer", "4"}, {"udiv exact", 8, "1", "0", "poison", ""},
    {"sdiv exact", 8, "7", "2", "poison", ""}, {"sdiv exact", 8, "8", "2", "integer", "4"},
    {"sdiv exact", 8, "1", "0", "poison", ""}, {"sdiv exact", 8, "80", "FF", "poison", ""},
    {"lshr exact", 8, "8", "1", "integer", "4"}, {"ashr exact", 8, "8", "8", "poison", ""},
    {"or disjoint", 8, "1", "2", "integer", "3"}, {"or disjoint", 8, "1", "1", "poison", ""},
    {"shl", 8, "1", "8", "poison", ""}, {"sdiv", 8, "1", "0", "poison", ""},
    {"and", 32, "F0", "CC", "integer", "C0"}, {"or", 32, "F0", "CC", "integer", "FC"},
    {"xor", 32, "F0", "CC", "integer", "3C"}, {"ashr", 8, "80", "1", "integer", "C0"},
    {"urem", 8, "7", "2", "integer", "1"}, {"srem", 8, "F9", "2", "integer", "FF"}}) {
    LLVMContext context;
    auto type = "i" + std::to_string(c.bits);
    auto module = parse(context, "define " + type + " @f(" + type + " %a, " + type + " %b) { %v = " + c.operation + " " + type + " %a, %b\n ret " + type + " %v }");
    ASSERT_TRUE(module);
    auto result = foldScalar(module->getFunction("f")->front().front(), {integer(c.bits, c.left), integer(c.bits, c.right)});
    EXPECT_EQ(result.getString("kind"), c.kind) << c.operation;
    if (std::string(c.kind) == "integer") EXPECT_EQ(result.getString("hex"), c.hex) << c.operation;
  }
}

TEST(EffectDomain, ScalarSelectFreezeCastsComparisonsAndUnknowns) {
  LLVMContext context;
  auto module = parse(context, R"(
define i32 @f(i32 %a, i32 %b, i1 %c, ptr %p) {
 %sum = add i32 %a, %b
 %choice = select i1 %c, i32 %a, i32 %b
 %frozen = freeze i32 %a
 %small = trunc i32 %a to i8
 %signed = sext i32 %a to i64
 %unsigned = zext i32 %a to i64
 %nonneg = zext nneg i32 %a to i64
 %truncnuw = trunc nuw i32 %a to i8
 %truncnsw = trunc nsw i32 %a to i8
 %cmp = icmp slt i32 %a, %b
 %samesign = icmp samesign slt i32 %a, %b
 %read = load i32, ptr %p
 %ptrcmp = icmp eq ptr %p, null
 ret i32 %sum
}
)");
  ASSERT_TRUE(module); auto &f = *module->getFunction("f");
  auto fold = [&](StringRef name, ArrayRef<json::Object> args) { return foldScalar(*cast<Instruction>(named(f, name)), args); };
  EXPECT_EQ(fold("choice", {integer(1, "1"), integer(32, "3"), special("poison")}).getString("hex"), "3");
  EXPECT_EQ(fold("choice", {integer(1, "0"), special("undef"), integer(32, "4")}).getString("hex"), "4");
  EXPECT_EQ(fold("choice", {integer(1, "0"), integer(32, "4"), special("unknown")}).getString("kind"), "unknown");
  EXPECT_EQ(fold("choice", {special("undef"), integer(32, "4"), integer(32, "4")}).getString("kind"), "unknown");
  EXPECT_EQ(fold("choice", {special("poison"), integer(32, "4"), integer(32, "4")}).getString("kind"), "poison");
  EXPECT_EQ(fold("frozen", {integer(32, "3")}).getString("hex"), "3");
  EXPECT_EQ(fold("frozen", {special("poison")}).getString("kind"), "freeze");
  EXPECT_EQ(fold("frozen", {special("undef")}).getString("kind"), "freeze");
  EXPECT_EQ(fold("small", {integer(32, "1234")}).getString("hex"), "34");
  EXPECT_EQ(fold("signed", {integer(32, "FFFFFFFF")}).getString("hex"), "FFFFFFFFFFFFFFFF");
  EXPECT_EQ(fold("unsigned", {integer(32, "FFFFFFFF")}).getString("hex"), "FFFFFFFF");
  EXPECT_EQ(fold("nonneg", {integer(32, "FFFFFFFF")}).getString("kind"), "poison");
  EXPECT_EQ(fold("nonneg", {integer(32, "3")}).getString("hex"), "3");
  EXPECT_EQ(fold("truncnuw", {integer(32, "100")}).getString("kind"), "poison");
  EXPECT_EQ(fold("truncnuw", {integer(32, "FF")}).getString("hex"), "FF");
  EXPECT_EQ(fold("truncnsw", {integer(32, "80")}).getString("kind"), "poison");
  EXPECT_EQ(fold("truncnsw", {integer(32, "FFFFFFFF")}).getString("hex"), "FF");
  EXPECT_EQ(fold("samesign", {integer(32, "FFFFFFFF"), integer(32, "1")}).getString("kind"), "poison");
  EXPECT_EQ(fold("samesign", {integer(32, "1"), integer(32, "2")}).getString("hex"), "1");
  EXPECT_EQ(fold("cmp", {integer(32, "FFFFFFFF"), integer(32, "1")}).getString("hex"), "1");
  EXPECT_EQ(fold("sum", {special("poison"), integer(32, "1")}).getString("kind"), "poison");
  EXPECT_EQ(fold("sum", {integer(32, "1"), special("poison")}).getString("kind"), "poison");
  EXPECT_EQ(fold("sum", {special("undef"), integer(32, "1")}).getString("kind"), "unknown");
  EXPECT_EQ(fold("read", {integer(32, "1")}).getString("reason"), "unsupported_scalar_operation");
  EXPECT_EQ(fold("sum", {}).getString("reason"), "operand_count_mismatch");
  for (auto bad : {integer(8, "1"), integer(32, ""), integer(32, "GG"), integer(32, "100000000"),
                  json::Object{{"kind", "integer"}}, json::Object{{"kind", "integer"}, {"bits", 32}}})
    EXPECT_EQ(fold("sum", {std::move(bad), integer(32, "1")}).getString("kind"), "unknown");
  EXPECT_EQ(fold("ptrcmp", {integer(64, "0"), integer(64, "0")}).getString("reason"), "operand_type_mismatch");
  EXPECT_TRUE(mergeScalars({}, 8).empty());
  EXPECT_EQ(mergeScalars({integer(8, "1"), integer(8, "1"), integer(8, "2")}, 2).size(), 2u);
  auto overflow = mergeScalars({integer(8, "1"), integer(8, "2")}, 1);
  ASSERT_EQ(overflow.size(), 1u); EXPECT_EQ(overflow[0].getString("reason"), "value_candidate_budget");
  auto unknown = mergeScalars({integer(8, "1"), special("unknown")}, 8);
  ASSERT_EQ(unknown.size(), 1u); EXPECT_EQ(unknown[0].getString("kind"), "unknown");
  json::Object source{{"artifact_key", std::string(64, 'a')}, {"function_id", "f"}, {"id", "f:b0:i0"}};
  json::Object parameter{{"kind", "parameter"}, {"source", json::Object(source)}, {"invocation_id", "root"}};
  auto *sum = cast<Instruction>(named(f, "sum"));
  auto symbolic = symbolicScalar(*sum, {parameter, integer(32, "1")}, source, "root");
  EXPECT_EQ(symbolic.getString("kind"), "expression"); EXPECT_EQ(symbolic.getString("invocation_id"), "root");
  ASSERT_EQ(symbolic.getArray("operands")->size(), 2u);
  EXPECT_EQ(symbolic.getArray("operands")->front(), json::Value(json::Object(parameter)));
  EXPECT_EQ(symbolicScalar(*sum, {symbolic, parameter}, source, "root").getString("kind"), "expression");
  EXPECT_EQ(symbolicScalar(*sum, {integer(32, "1"), integer(32, "2")}, source, "root").getString("hex"), "3");
  EXPECT_EQ(symbolicScalar(*sum, {parameter, special("unknown")}, source, "root").getString("kind"), "unknown");
  EXPECT_EQ(symbolicScalar(*sum, {parameter, integer(32, "1")}, source, "").getString("reason"), "unbound_scalar_expression");
  EXPECT_EQ(symbolicScalar(*cast<Instruction>(named(f, "choice")), {parameter, integer(32, "1"), integer(32, "2")}, source, "root").getString("kind"), "expression");
}
