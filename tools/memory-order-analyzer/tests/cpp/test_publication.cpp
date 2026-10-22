#include "publication.h"
#include "effects.h"
#include <gtest/gtest.h>
#include <llvm/ADT/StringExtras.h>
#include <llvm/AsmParser/Parser.h>
#include <llvm/Bitcode/BitcodeWriter.h>
#include <llvm/Support/FileSystem.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/SHA256.h>
#include <llvm/Support/SourceMgr.h>
#include <fstream>

using namespace llvm;
namespace {
json::Object budgets() { return *moa::publicationProtocol().getObject("budgets"); }
json::Object origin() {
  return json::Object{{"artifact_key", std::string(64, 'a')},
                      {"module_hash", std::string(64, 'b')},
                      {"facts_hash", std::string(64, 'c')},
                      {"profile", "source-preserving"},
                      {"extractor_version", "0.2.0"},
                      {"llvm_version", "21.1.8"}};
}
std::unique_ptr<Module> parse(LLVMContext &context, const char *text) {
  SMDiagnostic diagnostic;
  auto module = parseAssemblyString(text, diagnostic, context);
  if (!module) diagnostic.print("publication-unit", errs());
  return module;
}
struct Temp {
  SmallString<128> path;
  Temp() { EXPECT_FALSE(sys::fs::createTemporaryFile("moa-publication-unit", "input", path)); }
  ~Temp() { sys::fs::remove(path); }
  void bc(Module &module) {
    std::error_code error;
    raw_fd_ostream stream(path, error);
    EXPECT_FALSE(error);
    WriteBitcodeToFile(module, stream);
  }
  void text(StringRef value) {
    std::ofstream output(path.c_str(), std::ios::binary);
    output << value.str();
  }
};
json::Object job(StringRef path, json::Object input, json::Object limits = budgets()) {
  return json::Object{{"id", "job"}, {"path", path.str()},
                      {"origin", std::move(input)}, {"budgets", std::move(limits)}};
}
json::Object batch(json::Array jobs, json::Object protocol = moa::publicationProtocol()) {
  return json::Object{{"protocol", std::move(protocol)}, {"jobs", std::move(jobs)}};
}
} // namespace

TEST(Publication, ProtocolIsIndependentAndStable) {
  auto protocol = moa::publicationProtocol();
  EXPECT_EQ(protocol.getInteger("protocol_version"), 1);
  EXPECT_EQ(protocol.getString("analysis_version"), "0.1.0");
  EXPECT_EQ(protocol.getString("policy_id"), "single-publication-risks-v1");
  EXPECT_EQ(protocol.getString("model_id"), "c-cpp-single-publication-v1");
  EXPECT_EQ(protocol.getObject("kinds")->size(), 4u);
  EXPECT_EQ(moa::analysisProtocol().getString("policy_id"), "scoped-effects-v1");
}

TEST(Publication, ExtractsValuesObservationsGatesAndReturns) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@flag = global i32 0
@payload = global i32 0
define i1 @ready() {
entry:
  %value = load atomic i32, ptr @flag acquire, align 4
  %ok = icmp ne i32 %value, 0
  ret i1 %ok
}
define void @publish() {
entry:
  store i32 42, ptr @payload, align 4
  store atomic i32 1, ptr @flag release, align 4
  ret void
}
define i32 @consume() {
entry:
  %value = load atomic i32, ptr @flag acquire, align 4
  %ok = icmp eq i32 %value, 1
  br i1 %ok, label %success, label %failure
success:
  %payload.value = load i32, ptr @payload, align 4
  ret i32 %payload.value
failure:
  ret i32 0
}
)");
  ASSERT_TRUE(module);
  auto facts = moa::publicationFacts(*module, origin(), budgets());
  EXPECT_EQ(facts.getString("kind"), "PublicationLocalFacts");
  EXPECT_EQ(facts.getString("status"), "complete");
  ASSERT_EQ(facts.getArray("initializers")->size(), 2u);
  EXPECT_EQ(facts.getArray("accesses")->size(), 5u);
  ASSERT_GE(facts.getArray("observations")->size(), 3u);
  ASSERT_EQ(facts.getArray("gates")->size(), 2u);
  ASSERT_GE(facts.getArray("returns")->size(), 1u);
  EXPECT_FALSE(facts.getArray("order")->empty());
  EXPECT_TRUE(any_of(*facts.getArray("order"), [](const json::Value &value) {
    auto &edge = *value.getAsObject();
    return edge.getString("relation") == "must-before" &&
           edge.getString("reason") == "p4-dominance-order";
  }));
  auto hasExactOne = any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    auto &access = *value.getAsObject();
    auto *scalar = access.getObject("value");
    uint64_t bits = 0;
    return access.getString("kind") == "write" && scalar && scalar->getString("state") == "exact" &&
           !scalar->getString("hex")->getAsInteger(16, bits) && bits == 1;
  });
  EXPECT_TRUE(hasExactOne);
  EXPECT_TRUE(any_of(*facts.getArray("gates"), [](const json::Value &value) {
    return !value.getAsObject()->getArray("controlled_blocks")->empty();
  }));
  EXPECT_FALSE(facts.getArray("analysis_evidence")->empty());
}

TEST(Publication, LoopsRangesAndBudgetsStayConservative) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@flag = global i32 0
define void @wait() {
entry: br label %retry
retry:
  %value = load atomic i32, ptr @flag monotonic, align 4
  %zero = icmp eq i32 %value, 0
  br i1 %zero, label %retry, label %success
success: ret void
}
define void @dynamic(ptr %pointer, i64 %index, i32 %value) {
entry:
  %element = getelementptr i32, ptr %pointer, i64 %index
  store i32 %value, ptr %element
  ret void
}
)");
  ASSERT_TRUE(module);
  auto facts = moa::publicationFacts(*module, origin(), budgets());
  EXPECT_TRUE(any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    auto &access = *value.getAsObject();
    return access.getString("multiplicity") == "repeated";
  }));
  EXPECT_TRUE(any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    auto &access = *value.getAsObject();
    return access.getString("status") == "unknown" &&
           access.getString("reason") == "object-range-unresolved";
  }));
  EXPECT_TRUE(any_of(*facts.getArray("gates"), [](const json::Value &value) {
    return value.getAsObject()->getBoolean("repeated").value();
  }));
  auto limits = budgets();
  limits["local_steps"] = 1;
  auto partial = moa::publicationFacts(*module, origin(), limits);
  EXPECT_EQ(partial.getString("status"), "partial");
  EXPECT_FALSE(partial.getArray("frontier")->empty());
  EXPECT_FALSE(partial.getArray("diagnostics")->empty());
}

TEST(Publication, BatchWorkerAndInputValidationAreIsolated) {
  LLVMContext context;
  auto module = parse(context, "define i32 @main() { entry: ret i32 0 }");
  ASSERT_TRUE(module);
  Temp file;
  file.bc(*module);
  auto bytes = MemoryBuffer::getFile(file.path);
  ASSERT_TRUE(bytes);
  auto input = origin();
  input["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef((*bytes)->getBuffer())), true);
  json::Object request = batch(json::Array{job(file.path, json::Object(input))});
  auto response = moa::publicationBatch(request);
  ASSERT_EQ(response.getArray("results")->size(), 1u);
  EXPECT_TRUE(response.getArray("results")->front().getAsObject()->get("error")->getAsNull());
  EXPECT_TRUE(response.getArray("results")->front().getAsObject()->getObject("result"));
  EXPECT_EQ(response, moa::publicationBatch(request));

  input["module_hash"] = std::string(64, 'd');
  auto changed = moa::publicationBatch(batch(json::Array{job(file.path, std::move(input))}));
  EXPECT_EQ(changed.getArray("results")->front().getAsObject()->getObject("error")->getString("code"),
            "inputs_changed");
  EXPECT_THROW(moa::publicationBatch(json::Object{}), std::runtime_error);
  EXPECT_THROW(moa::publicationBatch(batch(json::Array{})), std::runtime_error);

  Temp text;
  text.text("not bitcode");
  input = origin();
  input["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef("not bitcode")), true);
  auto invalid = moa::publicationBatch(batch(json::Array{job(text.path, std::move(input))}));
  EXPECT_EQ(invalid.getArray("results")->front().getAsObject()->getObject("error")->getString("code"),
            "format_invalid");

  std::string out, error;
  raw_string_ostream output(out), errors(error);
  EXPECT_EQ(moa::publicationWorker("/definitely/absent.json", output, errors), 1);
  EXPECT_NE(error.find("input_unreadable"), std::string::npos);
}

TEST(Publication, FiniteLLVMTransferDomainCoversSupportedAndUnknownForms) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@flag = global i32 0
@small = global i8 0
@array = global [4 x i32] zeroinitializer
@aggregate = global { i32, i8 } { i32 1, i8 2 }
@pointer = global ptr null
@external = external global i32
declare i1 @ready()

define void @accesses(i64 %index, i32 %runtime) {
entry:
  %local = alloca i32
  store i32 7, ptr %local
  store ptr %local, ptr @pointer
  %spilled = load i32, ptr %local
  store i32 %spilled, ptr @flag
  %runtime.slot = alloca i32
  store i32 %runtime, ptr %runtime.slot
  %runtime.loaded = load i32, ptr %runtime.slot
  store i32 %runtime.loaded, ptr @flag
  store i32 3, ptr inttoptr (i64 4096 to ptr)
  %constant.gep = getelementptr [4 x i32], ptr @array, i64 0, i64 1
  store i32 2, ptr %constant.gep
  %dynamic.gep = getelementptr [4 x i32], ptr @array, i64 0, i64 %index
  store i32 %runtime, ptr %dynamic.gep
  %truncated = trunc i64 257 to i8
  store i8 %truncated, ptr @small
  %extended = zext i8 1 to i32
  store i32 %extended, ptr @flag
  %signed = sext i8 -1 to i32
  store i32 %signed, ptr @flag
  %old = atomicrmw volatile add ptr @flag, i32 1 monotonic
  %pair = cmpxchg volatile ptr @flag, i32 1, i32 2 acq_rel monotonic
  fence syncscope("singlethread") seq_cst
  ret void
}

define i1 @compare_left() {
entry:
  %raw = load atomic i8, ptr @small monotonic, align 1
  %wide = zext i8 %raw to i32
  %cmp = icmp ne i32 0, %wide
  ret i1 %cmp
}

define void @call_gate() {
entry:
  %value = call i1 @ready()
  br i1 %value, label %success, label %failure
success: ret void
failure: ret void
}

define void @invert_gate() {
entry:
  %raw = load atomic i32, ptr @flag acquire, align 4
  %cmp = icmp eq i32 %raw, 1
  %inverse = xor i1 %cmp, true
  br i1 %inverse, label %failure, label %success
success: ret void
failure: ret void
}

define void @phi_select_gate(i1 %choice) {
entry:
  %one = load atomic i32, ptr @flag acquire, align 4
  %two = load atomic i32, ptr @flag acquire, align 4
  %selected = select i1 %choice, i32 %one, i32 %two
  br i1 %choice, label %left, label %right
left: br label %merge
right: br label %merge
merge:
  %joined = phi i32 [ %selected, %left ], [ %two, %right ]
  %ok = icmp ne i32 %joined, 0
  br i1 %ok, label %success, label %failure
success: ret void
failure: ret void
}

define void @unsupported_conditions(i32 %runtime) {
entry:
  %a = load i32, ptr @flag
  %b = load i32, ptr @flag
  %less = icmp slt i32 %a, 0
  br i1 %less, label %left, label %next
left: ret void
next:
  %both = icmp eq i32 %a, %b
  br i1 %both, label %same, label %different
same: ret void
different: ret void
}

define void @spill_and_duplicate_gate(i1 %choice) {
entry:
  %slot = alloca i32
  %raw = load atomic i32, ptr @flag acquire, align 4
  store i32 %raw, ptr %slot
  %spilled = load i32, ptr %slot
  %duplicate = select i1 %choice, i32 %spilled, i32 %spilled
  %ok = icmp eq i32 %duplicate, 1
  br i1 %ok, label %success, label %failure
success: ret void
failure: ret void
}

define void @scalar_unknowns(i1 %choice) {
entry:
  %slot = alloca i32
  br i1 %choice, label %left, label %right
left:
  store i32 1, ptr %slot
  br label %merge
right:
  store i32 2, ptr %slot
  br label %merge
merge:
  %ambiguous = load i32, ptr %slot
  store i32 %ambiguous, ptr @flag
  %global.value = load i32, ptr @flag
  store i32 %global.value, ptr @flag
  store i32 poison, ptr @flag
  ret void
}

define void @direct_boolean_gate() {
entry:
  %raw = load atomic i1, ptr @small acquire, align 1
  br i1 %raw, label %success, label %failure
success: ret void
failure: ret void
}

define void @direct_boolean_inverse() {
entry:
  %raw = load atomic i1, ptr @small acquire, align 1
  %inverse = xor i1 %raw, true
  br i1 %inverse, label %failure, label %success
success: ret void
failure: ret void
}

define ptr @return_pointer() {
entry:
  %raw = load ptr, ptr @pointer
  ret ptr %raw
}

define i1 @return_call() {
entry:
  %raw = call i1 @ready()
  ret i1 %raw
}

define i1 @return_inverse() {
entry:
  %raw = load atomic i1, ptr @small acquire, align 1
  %inverse = xor i1 %raw, true
  ret i1 %inverse
}

define void @loop_fence_and_call() {
entry: br label %loop
loop:
  fence acquire
  %raw = call i1 @ready()
  br i1 %raw, label %done, label %loop
done: ret void
}

define void @unsupported_transforms(ptr %pointer) {
entry:
  %raw = load atomic i32, ptr @flag acquire, align 4
  %bad.xor = xor i32 %raw, 1
  %bad = icmp ne i32 %bad.xor, 0
  br i1 %bad, label %left, label %next
left: ret void
next:
  %as.int = ptrtoint ptr %pointer to i64
  %ptr.cond = icmp ne i64 %as.int, 0
  br i1 %ptr.cond, label %yes, label %no
yes: ret void
no: ret void
}

define void @unstored_local_gate() {
entry:
  %slot = alloca i1
  %raw = load i1, ptr %slot
  br i1 %raw, label %yes, label %no
yes: ret void
no: ret void
}

define void @pointer_spill() {
entry:
  %slot = alloca ptr
  store ptr @flag, ptr %slot
  %pointer = load ptr, ptr %slot
  store atomic i32 1, ptr %pointer release, align 4
  ret void
}
)");
  ASSERT_TRUE(module);
  auto facts = moa::publicationFacts(*module, origin(), budgets());
  EXPECT_EQ(facts.getString("status"), "complete");
  std::set<StringRef> kinds;
  for (const auto &value : *facts.getArray("accesses"))
    kinds.insert(*value.getAsObject()->getString("kind"));
  EXPECT_TRUE(kinds.contains("rmw"));
  EXPECT_TRUE(kinds.contains("cas"));
  EXPECT_TRUE(kinds.contains("fence"));
  EXPECT_TRUE(kinds.contains("call"));
  EXPECT_TRUE(any_of(*facts.getArray("initializers"), [](const json::Value &value) {
    return value.getAsObject()->getString("status") == "unknown";
  }));
  EXPECT_TRUE(any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    auto &item = *value.getAsObject();
    return item.getString("status") == "unknown" || item.getString("syncscope") == "singlethread";
  }));
  EXPECT_GT(facts.getArray("observations")->size(), 4u);
  EXPECT_FALSE(facts.getArray("returns")->empty());
  EXPECT_TRUE(any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    auto &item = *value.getAsObject();
    return !*item.getBoolean("atomic") && !item.getString("ordering") && !item.getString("syncscope");
  }));
  EXPECT_TRUE(any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    auto *written = value.getAsObject()->getObject("value");
    return written && written->getString("state") == "unknown";
  }));
  EXPECT_TRUE(any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    auto &item = *value.getAsObject();
    auto *object = item.getObject("range")->getObject("object");
    return item.getString("ordering") == "release" && object && object->get("function_id")->getAsNull();
  }));
}

TEST(Publication, MissingLayoutAndCandidateLimitRemainExplicit) {
  LLVMContext context;
  auto module = parse(context, R"(
@flag = global i32 0
define void @limited(i1 %choice) {
entry:
  %element = getelementptr [2 x i32], ptr @pair, i64 0, i64 1
  store i32 1, ptr %element
  %one = load i32, ptr @flag
  %two = load i32, ptr @flag
  %selected = select i1 %choice, i32 %one, i32 %two
  %ok = icmp ne i32 %selected, 0
  br i1 %ok, label %yes, label %no
yes: ret void
no: ret void
}

@pair = global [2 x i32] zeroinitializer
)");
  ASSERT_TRUE(module);
  auto limits = budgets(); limits["value_candidates"] = 1;
  auto facts = moa::publicationFacts(*module, origin(), limits);
  EXPECT_TRUE(any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    return value.getAsObject()->getString("status") == "unknown";
  }));
  EXPECT_LE(facts.getArray("observations")->size(), 2u);

  auto noSteps = budgets(); noSteps["local_steps"] = 0;
  auto exhausted = moa::publicationFacts(*module, origin(), noSteps);
  EXPECT_EQ(exhausted.getString("status"), "partial");
  EXPECT_FALSE(exhausted.getArray("frontier")->empty());

  auto oneStepModule = parse(context, "define i32 @one() { entry: ret i32 0 }");
  ASSERT_TRUE(oneStepModule);
  auto oneStep = budgets(); oneStep["local_steps"] = 1;
  auto returnLimited = moa::publicationFacts(*oneStepModule, origin(), oneStep);
  EXPECT_EQ(returnLimited.getString("status"), "partial");
}

TEST(Publication, LocalOrderAndTransferBudgetsRemainConservative) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@flag = global i8 0
define void @deep() {
entry:
  %v0 = zext i8 1 to i16
  %v1 = trunc i16 %v0 to i8
  %v2 = zext i8 %v1 to i16
  %v3 = trunc i16 %v2 to i8
  %v4 = zext i8 %v3 to i16
  %v5 = trunc i16 %v4 to i8
  %v6 = zext i8 %v5 to i16
  %v7 = trunc i16 %v6 to i8
  %v8 = zext i8 %v7 to i16
  %v9 = trunc i16 %v8 to i8
  %v10 = zext i8 %v9 to i16
  %v11 = trunc i16 %v10 to i8
  %v12 = zext i8 %v11 to i16
  %v13 = trunc i16 %v12 to i8
  %v14 = zext i8 %v13 to i16
  %v15 = trunc i16 %v14 to i8
  %v16 = zext i8 %v15 to i16
  %v17 = trunc i16 %v16 to i8
  store i8 %v17, ptr @flag
  ret void
}
define void @loop(ptr %a, ptr %b) {
entry:
  store i32 1, ptr %a
  br label %retry
retry:
  %value = load i32, ptr %b
  br label %retry
}
)");
  ASSERT_TRUE(module);
  auto facts = moa::publicationFacts(*module, origin(), budgets());
  EXPECT_TRUE(any_of(*facts.getArray("accesses"), [](const json::Value &value) {
    auto &access = *value.getAsObject();
    return access.getString("kind") == "write" &&
           access.getObject("value")->getString("state") == "unknown";
  }));

  LLVMContext budgetContext;
  auto budgetModule = parse(budgetContext, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
define void @f(ptr %a, ptr %b) {
entry:
  store i32 1, ptr %a
  store i32 2, ptr %b
  ret void
}
)");
  ASSERT_TRUE(budgetModule);
  auto limits = budgets();
  limits["local_steps"] = 4;
  auto partial = moa::publicationFacts(*budgetModule, origin(), limits);
  EXPECT_EQ(partial.getString("status"), "partial");
  EXPECT_FALSE(partial.getArray("order")->empty());
  EXPECT_FALSE(partial.getArray("frontier")->empty());
}

TEST(Publication, BatchEnvelopeValidatesEveryIndependentFieldAndLimit) {
  auto valid = job("/does/not/matter", origin());
  EXPECT_THROW(moa::publicationBatch(json::Object{{"protocol", moa::publicationProtocol()}}), std::runtime_error);
  EXPECT_THROW(moa::publicationBatch(json::Object{{"protocol", json::Object{}},
                                                  {"jobs", json::Array{json::Object(valid)}}}), std::runtime_error);
  EXPECT_THROW(moa::publicationBatch(batch(json::Array{1})), std::runtime_error);
  EXPECT_THROW(moa::publicationBatch(batch(json::Array{json::Object{{"id", "x"}}})), std::runtime_error);
  auto expectFailure = [&](json::Object changed) {
    EXPECT_THROW(moa::publicationBatch(batch(json::Array{std::move(changed)})), std::runtime_error);
  };
  for (auto field : {"id", "path", "origin", "budgets"}) {
    auto changed = json::Object(valid); changed.erase(field); expectFailure(std::move(changed));
  }
  for (auto field : {"id", "path"}) {
    auto changed = json::Object(valid); changed[field] = ""; expectFailure(std::move(changed));
  }
  auto nul = json::Object(valid); nul["path"] = std::string("a\0b", 3); expectFailure(std::move(nul));
  EXPECT_THROW(moa::publicationBatch(batch(json::Array{json::Object(valid), json::Object(valid)})), std::runtime_error);
  for (auto field : {"artifact_key", "module_hash", "facts_hash"}) {
    for (const std::string &value : {std::string(), std::string("short"), std::string(64, 'z')}) {
      auto changed = json::Object(valid); (*changed.getObject("origin"))[field] = value;
      expectFailure(std::move(changed));
    }
  }
  for (auto field : {"extractor_version", "llvm_version"}) {
    auto changed = json::Object(valid); (*changed.getObject("origin"))[field] = "future";
    expectFailure(std::move(changed));
  }
  auto extraOrigin = json::Object(valid); (*extraOrigin.getObject("origin"))["extra"] = true;
  expectFailure(std::move(extraOrigin));
  auto missingHash = json::Object(valid);
  missingHash.getObject("origin")->erase("artifact_key");
  (*missingHash.getObject("origin"))["replacement"] = std::string(64, 'a');
  expectFailure(std::move(missingHash));
  for (StringRef profile : {"source-preserving", "build-faithful", "imported", "linked"}) {
    auto changed = json::Object(valid); (*changed.getObject("origin"))["profile"] = profile.str();
    EXPECT_EQ(moa::publicationBatch(batch(json::Array{std::move(changed)})).getArray("results")->size(), 1u);
  }
  auto badProfile = json::Object(valid); (*badProfile.getObject("origin"))["profile"] = "future";
  expectFailure(std::move(badProfile));
  auto extraBudget = json::Object(valid); (*extraBudget.getObject("budgets"))["extra"] = 1;
  expectFailure(std::move(extraBudget));
  for (auto field : {"local_steps", "value_candidates", "protocol_candidates", "assessments",
                     "scc_iterations", "worker_seconds", "worker_output_bytes",
                     "request_seconds", "request_output_bytes"}) {
    auto zero = json::Object(valid); (*zero.getObject("budgets"))[field] = 0; expectFailure(std::move(zero));
    auto excessive = json::Object(valid);
    (*excessive.getObject("budgets"))[field] = *budgets().getInteger(field) + 1;
    expectFailure(std::move(excessive));
  }
  json::Array tooMany;
  for (unsigned index = 0; index < 10001; ++index) {
    auto changed = json::Object(valid); changed["id"] = "job-" + std::to_string(index);
    tooMany.push_back(std::move(changed));
  }
  EXPECT_THROW(moa::publicationBatch(batch(std::move(tooMany))), std::runtime_error);
}

TEST(Publication, WorkerClassifiesReaderVerifierAndOutputFailures) {
  auto unreadable = moa::publicationBatch(batch(json::Array{job("/definitely/absent.bc", origin())}));
  EXPECT_EQ(unreadable.getArray("results")->front().getAsObject()->getObject("error")->getString("code"),
            "input_unreadable");
  LLVMContext context;
  auto module = parse(context, "define i32 @main() { entry: ret i32 0 }");
  ASSERT_TRUE(module);
  Temp file; file.bc(*module);
  auto bytes = MemoryBuffer::getFile(file.path); ASSERT_TRUE(bytes);
  auto input = origin();
  input["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef((*bytes)->getBuffer())), true);
  auto limits = budgets(); limits["worker_output_bytes"] = 1;
  EXPECT_THROW(moa::publicationBatch(batch(json::Array{job(file.path, std::move(input), std::move(limits))})),
               std::runtime_error);
  Temp malformed; malformed.text("[]");
  std::string output, error; raw_string_ostream out(output), err(error);
  EXPECT_EQ(moa::publicationWorker(malformed.path.str().str(), out, err), 1);
  EXPECT_NE(error.find("expected JSON object"), std::string::npos);
}
