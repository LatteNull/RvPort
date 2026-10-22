#include "effect_control.h"
#include <gtest/gtest.h>
#include <llvm/AsmParser/Parser.h>
#include <llvm/Support/SourceMgr.h>

using namespace llvm;
using namespace moa;
namespace {
std::unique_ptr<Module> parse(LLVMContext &context, const char *ir) {
  SMDiagnostic error;
  auto result = parseAssemblyString(ir, error, context);
  if (!result) error.print("control-test", errs());
  return result;
}
ControlDomain scalar(unsigned bits, StringRef hex) {
  return {{{json::Object{{"kind", "integer"}, {"bits", bits}, {"hex", hex.str()}}, {}, {}}}, {}};
}
json::Object source(StringRef id = "term") {
  return json::Object{{"artifact_key", std::string(64, 'a')}, {"function_id", "f"}, {"id", id.str()}};
}
json::Object guard(unsigned edge, StringRef multiplicity = "single", StringRef invocation = "root", StringRef id = "term") {
  return json::Object{{"source", source(id)}, {"edge", edge}, {"invocation_id", invocation.str()}, {"multiplicity", multiplicity.str()}};
}
ControlDomain guarded(unsigned edge, StringRef multiplicity = "single", StringRef invocation = "root", StringRef id = "term") {
  auto value = scalar(8, "A");
  value.candidates[0].guards.push_back(guard(edge, multiplicity, invocation, id));
  value.candidates[0].proof.push_back(source("input"));
  return value;
}
} // namespace

TEST(EffectControl, JoinKeepsDisjunctionBottomAndUnknown) {
  ControlBudget budget;
  auto left = guarded(0), right = guarded(1);
  auto joined = joinControl(left, right, budget);
  ASSERT_EQ(joined.candidates.size(), 2u);
  EXPECT_EQ(joined.candidates[0].guards.size(), 1u);
  EXPECT_EQ(joined.candidates[1].guards[0].getAsObject()->getInteger("edge"), 1);
  EXPECT_EQ(joinControl(left, left, budget).candidates.size(), 1u);
  EXPECT_EQ(joinControl({}, left, budget).candidates.size(), 1u);
  EXPECT_TRUE(joinControl({}, {}, budget).candidates.empty());
  EXPECT_EQ(joinControl({{}, "unknown-input"}, left, budget).unknown, "unknown-input");
  EXPECT_EQ(joinControl(left, {{}, "unknown-input"}, budget).unknown, "unknown-input");
  ControlBudget tight{0, 100, 1};
  auto lost = joinControl(joined, right, tight);
  EXPECT_EQ(lost.unknown, "value_candidate_budget"); EXPECT_TRUE(lost.candidates.empty());
  tight = {0, 1, 8};
  EXPECT_EQ(joinControl(left, right, tight).unknown, "local_steps_budget"); EXPECT_EQ(tight.steps, 1u);
  auto changed = left;
  changed.candidates[0].value["hex"] = "B";
  EXPECT_EQ(joinControl(left, changed, budget).candidates.size(), 2u);
  changed = left; changed.candidates[0].proof.push_back(source("different-proof"));
  EXPECT_EQ(joinControl(left, changed, budget).candidates.size(), 2u);
}

TEST(EffectControl, SelectConditionsAreConjoinedOnlyWhenCompatible) {
  LLVMContext context;
  auto module = parse(context, "define i8 @f(i1 %c,i8 %a,i8 %b){ %s = select i1 %c,i8 %a,i8 %b\nret i8 %s }");
  ASSERT_TRUE(module);
  auto &select = cast<SelectInst>(module->getFunction("f")->getEntryBlock().front());
  ControlBudget budget;
  auto yes = scalar(1, "1"), no = scalar(1, "0"), a = scalar(8, "A"), b = scalar(8, "B");
  EXPECT_EQ(selectControl(select, yes, a, {{}, "untaken"}, budget).candidates[0].value.getString("hex"), "A");
  EXPECT_EQ(selectControl(select, no, {{}, "untaken"}, b, budget).candidates[0].value.getString("hex"), "B");
  auto condition = joinControl(yes, no, budget);
  EXPECT_EQ(selectControl(select, condition, a, b, budget).candidates.size(), 2u);
  EXPECT_EQ(selectControl(select, {{}, "unknown"}, a, b, budget).unknown, "unknown_select_condition");
  EXPECT_EQ(selectControl(select, yes, {{}, "selected-unknown"}, b, budget).unknown, "selected-unknown");
  EXPECT_TRUE(selectControl(select, {}, a, b, budget).candidates.empty());
  for (auto kind : {"poison", "undef", "freeze", "parameter"}) {
    auto special = yes; special.candidates[0].value = json::Object{{"kind", kind}, {"reason", "test"}};
    auto result = selectControl(select, special, a, b, budget);
    if (StringRef(kind) == "poison") EXPECT_EQ(result.candidates[0].value.getString("kind"), "poison");
    else EXPECT_EQ(result.unknown, "unknown_select_condition");
  }
  auto constrained = yes;
  constrained.candidates[0].guards.push_back(guard(0));
  constrained.candidates[0].proof.push_back(source("input"));
  EXPECT_TRUE(selectControl(select, constrained, guarded(1), b, budget).candidates.empty());
  auto compatible = selectControl(select, constrained, guarded(0), b, budget);
  ASSERT_EQ(compatible.candidates.size(), 1u);
  EXPECT_EQ(compatible.candidates[0].guards.size(), 1u); EXPECT_EQ(compatible.candidates[0].proof.size(), 1u);
  for (auto alternate : {guarded(1, "repeated"), guarded(1, "single", "other"), guarded(1, "single", "root", "other-term")})
    EXPECT_EQ(selectControl(select, constrained, alternate, b, budget).candidates.size(), 1u);
  constrained.candidates[0].guards[0] = guard(0, "unknown");
  EXPECT_EQ(selectControl(select, constrained, guarded(1), b, budget).candidates.size(), 1u);
  for (unsigned limit : {0u, 1u}) {
    ControlBudget tight{0, limit, 8};
    EXPECT_EQ(selectControl(select, yes, a, b, tight).unknown, "local_steps_budget");
    EXPECT_EQ(tight.steps, limit);
  }
  ControlBudget tight{0, 100, 1};
  EXPECT_EQ(selectControl(select, condition, a, b, tight).unknown, "value_candidate_budget");
}

TEST(EffectControl, ExactEdgesSharedTargetsAndRepeatedObservations) {
  LLVMContext context;
  auto module = parse(context, R"(
define void @f(i8 %x) {
entry: switch i8 %x,label %exit [i8 1,label %same i8 2,label %same]
same: br label %loop
loop: br i1 true,label %loop,label %exit
exit: ret void
dead: br label %dead
}
define void @g(i1 %c) { br i1 %c,label %same,label %same
same: ret void }
)");
  ASSERT_TRUE(module);
  auto *function = module->getFunction("f");
  auto *sw = function->getEntryBlock().getTerminator();
  ControlBudget budget;
  auto alternatives = joinControl(scalar(8, "1"), scalar(8, "2"), budget);
  auto choices = chooseControl(*sw, alternatives, source(), "root", Cardinality::Single, budget);
  ASSERT_EQ(choices.edges.size(), 2u);
  EXPECT_EQ(choices.edges[0].ordinal, 1u); EXPECT_EQ(choices.edges[1].ordinal, 2u);
  EXPECT_EQ(sw->getSuccessor(1), sw->getSuccessor(2));
  EXPECT_EQ(choices.edges[0].guard.getString("multiplicity"), "single");
  EXPECT_EQ(choices.edges[0].condition.candidates[0].value.getString("hex"), "1");
  EXPECT_EQ(chooseControl(*sw, scalar(8, "FF"), source(), "root", Cardinality::Single, budget).edges[0].ordinal, 0u);
  auto bottom = chooseControl(*sw, {}, source(), "root", Cardinality::Single, budget);
  EXPECT_TRUE(bottom.edges.empty()); EXPECT_EQ(bottom.pending, "condition_pending");
  EXPECT_EQ(chooseControl(*sw, {{}, "unknown"}, source(), "root", Cardinality::Single, budget).edges.size(), 3u);
  auto *unconditional = sw->getSuccessor(1)->getTerminator();
  EXPECT_EQ(chooseControl(*unconditional, {}, source(), "root", Cardinality::Merged, budget).edges[0].guard.getString("multiplicity"), "unknown");
  auto *loop = unconditional->getSuccessor(0)->getTerminator();
  auto repeated = chooseControl(*loop, scalar(1, "1"), source(), "root", Cardinality::Single, budget);
  EXPECT_EQ(repeated.edges[0].guard.getString("multiplicity"), "repeated");
  EXPECT_TRUE(repeatedCondition(function->back()));
  auto *br = module->getFunction("g")->getEntryBlock().getTerminator();
  auto binary = joinControl(scalar(1, "0"), scalar(1, "1"), budget);
  EXPECT_EQ(chooseControl(*br, binary, source(), "root", Cardinality::Single, budget).edges.size(), 2u);
  EXPECT_EQ(chooseControl(*br, scalar(1, "0"), source(), "root", Cardinality::Single, budget).edges[0].ordinal, 1u);
  EXPECT_EQ(chooseControl(*function->back().getTerminator(), {}, source(), "root", Cardinality::Unknown, budget).edges.size(), 1u);
  EXPECT_EQ(chooseControl(*sw->getSuccessor(0)->getTerminator(), {}, source(), "root", Cardinality::Single, budget).pending, "unsupported_control");
  for (unsigned limit : {0u, 1u, 3u}) {
    ControlBudget tight{0, limit, 8};
    auto cut = chooseControl(*sw, alternatives, source(), "root", Cardinality::Single, tight);
    EXPECT_EQ(cut.pending, "local_steps_budget"); EXPECT_EQ(tight.steps, limit);
  }
  for (auto bad : {json::Object{{"kind", "undef"}}, json::Object{{"kind", "integer"}, {"bits", 1}, {"hex", "1"}},
                  json::Object{{"kind", "integer"}, {"bits", 8}}, json::Object{{"kind", "integer"}, {"bits", 8}, {"hex", ""}},
                  json::Object{{"kind", "integer"}, {"bits", 8}, {"hex", "Z"}}, json::Object{{"kind", "integer"}, {"bits", 8}, {"hex", "100"}}}) {
    ControlDomain invalid{{{bad, {}, {}}}, {}};
    auto unknown = chooseControl(*sw, invalid, source(), "root", Cardinality::Single, budget);
    ASSERT_EQ(unknown.edges.size(), 3u);
    EXPECT_EQ(unknown.edges[0].condition.unknown, "indeterminate_control");
  }
}

TEST(EffectControl, PhiUsesThePredecessorStateAndKeepsBottomInternal) {
  LLVMContext context;
  auto module = parse(context, R"(
define i8 @f(i1 %c,i8 %a,i8 %b) {
entry: br i1 %c,label %left,label %right
left: br label %join
right: br label %join
join: %p = phi i8 [%a,%left],[%b,%right]
ret i8 %p
}
define void @g(){ ret void }
)");
  ASSERT_TRUE(module);
  auto *function = module->getFunction("f");
  auto &phi = cast<PHINode>(function->back().front());
  auto *term = function->getEntryBlock().getTerminator();
  DenseMap<const Value *, ControlDomain> values;
  values[function->getArg(1)] = scalar(8, "A"); values[function->getArg(2)] = scalar(8, "B");
  ControlBudget budget;
  EXPECT_EQ(phiControl(phi, *term->getSuccessor(0), 0, values, budget).candidates[0].value.getString("hex"), "A");
  EXPECT_EQ(phiControl(phi, *term->getSuccessor(1), 0, values, budget).candidates[0].value.getString("hex"), "B");
  EXPECT_TRUE(phiControl(phi, *term->getSuccessor(0), 0, DenseMap<const Value *, ControlDomain>{}, budget).candidates.empty());
  EXPECT_EQ(phiControl(phi, *term->getSuccessor(0), 1, values, budget).unknown, "invalid_phi_edge");
  EXPECT_EQ(phiControl(phi, function->getEntryBlock(), 0, values, budget).unknown, "invalid_phi_edge");
  EXPECT_EQ(phiControl(phi, module->getFunction("g")->getEntryBlock(), 0, values, budget).unknown, "invalid_phi_edge");
  ControlBudget tight{0, 0, 8};
  EXPECT_EQ(phiControl(phi, *term->getSuccessor(0), 0, values, tight).unknown, "local_steps_budget");
  // Malformed PHI defense, not a valid input accepted by the BC verifier.
  phi.removeIncomingValue(0u, false);
  EXPECT_EQ(phiControl(phi, *term->getSuccessor(0), 0, values, budget).unknown, "invalid_phi_predecessor");
}
