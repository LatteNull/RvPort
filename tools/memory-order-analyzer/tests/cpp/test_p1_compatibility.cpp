#include "semantic.h"
#include <gtest/gtest.h>
#include <llvm/AsmParser/Parser.h>
#include <llvm/IR/Verifier.h>
#include <llvm/Support/SourceMgr.h>

using namespace llvm;

TEST(P1Compatibility, OriginalInstructionsAttributesAndLinkageRemainRaw) {
  LLVMContext context;
  SMDiagnostic error;
  auto module = parseAssemblyString(R"(
target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-p:64:64"
$helper = comdat any
@x = global i32 0
define linkonce_odr dso_local i32 @helper(i32 noundef %order) nounwind comdat {
entry:
  %slot = alloca i32
  store i32 %order, ptr %slot
  %value = load i32, ptr %slot
  ret i32 %value
}
define void @publish() {
entry:
  %order = call i32 @helper(i32 noundef 3)
  switch i32 %order, label %relaxed [i32 3, label %release]
relaxed:
  store atomic i32 1, ptr @x monotonic, align 4
  ret void
release:
  store atomic i32 1, ptr @x release, align 4
  ret void
}
)", error, context);
  ASSERT_NE(module, nullptr);
  ASSERT_FALSE(verifyModule(*module, &errs()));
  std::string original;
  raw_string_ostream ir(original);
  module->print(ir, nullptr);
  auto facts = moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'));
  EXPECT_EQ(facts.getInteger("schema_version"), 2);
  EXPECT_EQ(facts.getObject("protocol")->getString("extractor_version"), "0.2.0");
  EXPECT_EQ(facts.getObject("protocol")->getString("llvm_version"), "21.1.8");
  EXPECT_EQ(facts.getObject("extraction")->getString("status"), "partial");
  auto &functions = *facts.getArray("functions");
  ASSERT_EQ(functions.size(), 2u);
  EXPECT_EQ(functions[0].getAsObject()->getString("linkage"), "linkonce");
  EXPECT_EQ(functions[0].getAsObject()->getString("id"), std::string(64, 'a') + ":symbol:helper");
  auto &calls = *facts.getArray("calls");
  ASSERT_EQ(calls.size(), 1u);
  EXPECT_EQ(calls[0].getAsObject()->getString("attribute_status"), "unknown");
  EXPECT_EQ(calls[0].getAsObject()->getString("id"), std::string(64, 'a') + ":symbol:publish:b0:i0");
  auto &events = *facts.getArray("events");
  ASSERT_EQ(events.size(), 4u);
  EXPECT_EQ(events[0].getAsObject()->getString("kind"), "store");
  EXPECT_EQ(events[1].getAsObject()->getString("kind"), "load");
  EXPECT_EQ(events[2].getAsObject()->getString("ordering"), "monotonic");
  EXPECT_EQ(events[3].getAsObject()->getString("ordering"), "release");
  for (auto capability : {"effect_propagation", "callsite_specialization", "points_to", "threads", "memory_model"})
    EXPECT_EQ(facts.getObject("capabilities")->getBoolean(capability), false);
  std::string after;
  raw_string_ostream afterIR(after);
  module->print(afterIR, nullptr);
  EXPECT_EQ(original, after);
  EXPECT_EQ(json::Value(std::move(facts)), json::Value(moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'))));
}
