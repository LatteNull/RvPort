#include "threads.h"
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
#include <vector>

using namespace llvm;
namespace {
json::Object budgets() { return *moa::threadProtocol().getObject("budgets"); }
json::Object origin() {
  return json::Object{{"artifact_key", std::string(64, 'a')}, {"module_hash", std::string(64, 'b')},
    {"facts_hash", std::string(64, 'c')}, {"profile", "source-preserving"},
    {"extractor_version", "0.2.0"}, {"llvm_version", "21.1.8"}};
}
std::unique_ptr<Module> parse(LLVMContext &context, const char *text) {
  SMDiagnostic error;
  auto module = parseAssemblyString(text, error, context);
  if (!module) error.print("thread-unit", errs());
  return module;
}
struct Temp {
  SmallString<128> path;
  Temp() { EXPECT_FALSE(sys::fs::createTemporaryFile("moa-thread-unit", "input", path)); }
  ~Temp() { sys::fs::remove(path); }
  void text(const std::string &value) { std::ofstream out(path.c_str(), std::ios::binary); out << value; }
  void bc(Module &module) {
    std::error_code error;
    raw_fd_ostream stream(path, error);
    EXPECT_FALSE(error);
    WriteBitcodeToFile(module, stream);
  }
};
std::string stringify(json::Object value) {
  std::string text;
  raw_string_ostream out(text);
  out << json::Value(std::move(value));
  return text;
}
json::Object job(StringRef path, json::Object input, json::Object limits = budgets(),
                 StringRef id = "job") {
  return json::Object{{"id", id.str()}, {"path", path.str()},
                      {"origin", std::move(input)}, {"budgets", std::move(limits)}};
}
json::Object batch(json::Array jobs, json::Object protocol = moa::threadProtocol()) {
  return json::Object{{"protocol", std::move(protocol)}, {"jobs", std::move(jobs)}};
}
} // namespace

TEST(Threads, ProtocolAndPthreadFactsAreIndependent) {
  auto protocol = moa::threadProtocol();
  EXPECT_EQ(protocol.getString("policy_id"), "thread-sync-contexts-v1");
  EXPECT_EQ(protocol.getString("model_id"), "posix-pthread-v1");
  EXPECT_EQ(protocol.getObject("kinds")->size(), 5u);
  EXPECT_EQ(moa::analysisProtocol().getString("policy_id"), "scoped-effects-v1");

  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"
@mutex = global [5 x i64] zeroinitializer
@flag = global i32 0
declare !callback !0 i32 @pthread_create(ptr, ptr, ptr, ptr)
declare i32 @pthread_join(i64, ptr)
declare i32 @pthread_mutex_lock(ptr)
declare i32 @pthread_mutex_unlock(ptr)
define ptr @worker(ptr %arg) {
entry:
  %v = load atomic i32, ptr @flag acquire, align 4
  ret ptr null
}
define i32 @main() {
entry:
  %tid = alloca i64
  %created = call i32 @pthread_create(ptr %tid, ptr null, ptr @worker, ptr null)
  %ok = icmp eq i32 %created, 0
  br i1 %ok, label %body, label %exit
body:
  %handle = load i64, ptr %tid
  %locked = call i32 @pthread_mutex_lock(ptr @mutex)
  store atomic i32 1, ptr @flag release, align 4
  %unlocked = call i32 @pthread_mutex_unlock(ptr @mutex)
  %joined = call i32 @pthread_join(i64 %handle, ptr null)
  br label %exit
exit:
  ret i32 0
}
!0 = !{!1}
!1 = !{i64 2, i64 3, i1 false}
)");
  ASSERT_TRUE(module);
  auto result = moa::threadFacts(*module, origin(), budgets());
  auto &local = *result.getObject("local");
  auto &order = *result.getObject("order");
  EXPECT_EQ(local.getString("kind"), "ThreadLocalFacts");
  EXPECT_EQ(order.getString("kind"), "ExecutionOrderFacts");
  EXPECT_EQ(local.getString("status"), "complete");
  EXPECT_FALSE(local.getArray("provenance")->empty());
  ASSERT_EQ(local.getArray("calls")->size(), 4u);
  auto *create = (*local.getArray("calls"))[0].getAsObject();
  ASSERT_TRUE(create);
  EXPECT_EQ(create->getString("symbol"), "pthread_create");
  EXPECT_EQ(create->getString("status"), "candidate");
  EXPECT_EQ(create->getArray("callback_targets")->size(), 1u);
  EXPECT_EQ(create->getArray("callback_metadata")->size(), 1u);
  EXPECT_TRUE(create->getObject("success_test"));
  EXPECT_FALSE(order.getArray("nodes")->empty());
  EXPECT_FALSE(order.getArray("edges")->empty());
  EXPECT_TRUE(any_of(*local.getArray("calls"), [](const json::Value &value) {
    auto *call = value.getAsObject();
    return call->getString("symbol") == "pthread_mutex_lock" &&
           call->getString("mutex_initializer") &&
           call->getString("mutex_initializer")->starts_with("zero-static:");
  }));
}

TEST(Threads, ExtractsDirectC11ThrdCreateWithoutChangingPthreadModel) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"
declare i32 @thrd_create(ptr, ptr, ptr)
define i32 @worker(ptr %arg) { entry: ret i32 0 }
define i32 @main() {
entry:
  %handle = alloca i64
  %created = call i32 @thrd_create(ptr %handle, ptr @worker, ptr null)
  %ok = icmp eq i32 %created, 0
  ret i32 %created
}
)");
  ASSERT_TRUE(module);
  auto result = moa::threadFacts(*module, origin(), budgets());
  auto &local = *result.getObject("local");
  json::Object *create = nullptr;
  for (auto &value : *local.getArray("calls"))
    if (value.getAsObject()->getString("symbol") == "thrd_create") create = value.getAsObject();
  ASSERT_TRUE(create);
  EXPECT_EQ(create->getString("status"), "candidate");
  EXPECT_EQ(create->getArray("callback_targets")->size(), 1u);
  EXPECT_TRUE(create->getObject("handle_source"));
  EXPECT_TRUE(create->getObject("success_test"));
}

TEST(Threads, LoopEventsAreNeverPromotedToSingleMustOrder) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@x = global i32 0
define void @loop(i1 %again) {
entry: br label %body
body:
  store i32 1, ptr @x
  %v = load i32, ptr @x
  br i1 %again, label %body, label %exit
exit: ret void
})");
  ASSERT_TRUE(module);
  auto result = moa::threadFacts(*module, origin(), budgets());
  auto &order = *result.getObject("order");
  ASSERT_EQ(order.getArray("nodes")->size(), 2u);
  for (const auto &node : *order.getArray("nodes"))
    EXPECT_EQ(node.getAsObject()->getString("multiplicity"), "repeated");
  ASSERT_FALSE(order.getArray("edges")->empty());
  EXPECT_EQ(order.getArray("edges")->front().getAsObject()->getString("relation"), "may-before");
}

TEST(Threads, BatchAndWorkerRejectInvalidOrChangedInputs) {
  LLVMContext context;
  auto module = parse(context, "define i32 @main() { entry: ret i32 0 }");
  ASSERT_TRUE(module);
  Temp file;
  file.bc(*module);
  auto data = MemoryBuffer::getFile(file.path);
  ASSERT_TRUE(data);
  auto input = origin();
  input["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef((*data)->getBuffer())), true);
  json::Object job{{"id", "job"}, {"path", file.path.str().str()},
                   {"origin", json::Object(input)}, {"budgets", budgets()}};
  json::Object request{{"protocol", moa::threadProtocol()},
                       {"jobs", json::Array{std::move(job)}}};
  auto response = moa::threadBatch(request);
  ASSERT_EQ(response.getArray("results")->size(), 1u);
  auto &entry = *response.getArray("results")->front().getAsObject();
  EXPECT_TRUE(entry.get("error")->getAsNull());
  EXPECT_TRUE(entry.getObject("result")->getObject("local"));
  EXPECT_EQ(response, moa::threadBatch(request));

  Temp wire;
  wire.text(stringify(json::Object(request)));
  std::string out, err;
  raw_string_ostream os(out), es(err);
  const char *argv[] = {"worker", "--thread-batch", wire.path.c_str()};
  EXPECT_EQ(moa::worker(3, argv, os, es), 0);
  EXPECT_TRUE(err.empty());
  auto parsed = json::parse(out);
  EXPECT_TRUE(bool(parsed));
  input["module_hash"] = std::string(64, 'd');
  json::Object changedJob{{"id", "job"}, {"path", file.path.str().str()},
                          {"origin", std::move(input)}, {"budgets", budgets()}};
  json::Object changed{{"protocol", moa::threadProtocol()},
                       {"jobs", json::Array{std::move(changedJob)}}};
  auto failed = moa::threadBatch(changed);
  EXPECT_EQ(failed.getArray("results")->front().getAsObject()->getObject("error")->getString("code"), "inputs_changed");
  EXPECT_THROW(moa::threadBatch(json::Object{}), std::runtime_error);

  wire.text("[]"); out.clear(); err.clear();
  EXPECT_EQ(moa::worker(3, argv, os, es), 1);
  EXPECT_NE(err.find("thread_request"), std::string::npos);
  out.clear(); err.clear();
  const char *protocolArgv[] = {"worker", "--thread-analysis-protocol"};
  EXPECT_EQ(moa::worker(2, protocolArgv, os, es), 0);
  auto parsedProtocol = json::parse(out);
  EXPECT_TRUE(bool(parsedProtocol));
}

TEST(Threads, BatchEnvelopeValidationCoversEveryIndependentField) {
  auto validJob = job("/does/not/matter", origin());
  EXPECT_THROW(moa::threadBatch(json::Object{{"protocol", moa::threadProtocol()}}), std::runtime_error);
  EXPECT_THROW(moa::threadBatch(json::Object{{"protocol", json::Object{}},
                                             {"jobs", json::Array{json::Object(validJob)}}}), std::runtime_error);
  EXPECT_THROW(moa::threadBatch(batch(json::Array{})), std::runtime_error);
  EXPECT_THROW(moa::threadBatch(batch(json::Array{1})), std::runtime_error);
  EXPECT_THROW(moa::threadBatch(batch(json::Array{json::Object{{"id", "x"}}})), std::runtime_error);

  auto expectJobFailure = [&](json::Object changed) {
    EXPECT_THROW(moa::threadBatch(batch(json::Array{std::move(changed)})), std::runtime_error);
  };
  for (auto field : {"id", "path", "origin", "budgets"}) {
    auto changed = json::Object(validJob);
    changed.erase(field);
    expectJobFailure(std::move(changed));
  }
  for (auto field : {"id", "path"}) {
    auto changed = json::Object(validJob);
    changed[field] = "";
    expectJobFailure(std::move(changed));
  }
  auto nulPath = json::Object(validJob);
  nulPath["path"] = std::string("a\0b", 3);
  expectJobFailure(std::move(nulPath));

  auto duplicate = json::Array{json::Object(validJob), json::Object(validJob)};
  EXPECT_THROW(moa::threadBatch(batch(std::move(duplicate))), std::runtime_error);
  const std::vector<std::string> invalidHashes{"", "short", std::string(64, 'z')};
  for (auto field : {"artifact_key", "module_hash", "facts_hash"}) {
    for (const std::string &value : invalidHashes) {
      SCOPED_TRACE(std::string(field) + ":" + value);
      auto changed = json::Object(validJob);
      (*changed.getObject("origin"))[field] = value;
      expectJobFailure(std::move(changed));
    }
  }
  for (auto field : {"extractor_version", "llvm_version"}) {
    auto changed = json::Object(validJob);
    (*changed.getObject("origin"))[field] = "future";
    expectJobFailure(std::move(changed));
  }
  auto extraOrigin = json::Object(validJob);
  (*extraOrigin.getObject("origin"))["extra"] = true;
  expectJobFailure(std::move(extraOrigin));
  for (StringRef profile : {"source-preserving", "build-faithful", "imported", "linked"}) {
    auto changed = json::Object(validJob);
    (*changed.getObject("origin"))["profile"] = profile.str();
    auto response = moa::threadBatch(batch(json::Array{std::move(changed)}));
    EXPECT_EQ(response.getArray("results")->size(), 1u);
  }
  auto invalidProfile = json::Object(validJob);
  (*invalidProfile.getObject("origin"))["profile"] = "future";
  expectJobFailure(std::move(invalidProfile));

  auto extraBudget = json::Object(validJob);
  (*extraBudget.getObject("budgets"))["extra"] = 1;
  expectJobFailure(std::move(extraBudget));
  for (auto field : {"local_steps", "value_candidates"}) {
    for (int64_t value : {int64_t(0), int64_t(100001)}) {
      auto changed = json::Object(validJob);
      (*changed.getObject("budgets"))[field] = value;
      expectJobFailure(std::move(changed));
    }
  }

  json::Array tooMany;
  for (unsigned index = 0; index < 4097; ++index) tooMany.push_back(json::Object(validJob));
  EXPECT_THROW(moa::threadBatch(batch(std::move(tooMany))), std::runtime_error);
}

TEST(Threads, BatchInputAndTransportFailuresAreClassified) {
  Temp text;
  text.text("not bitcode");
  auto input = origin();
  input["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef("not bitcode")), true);
  auto invalidFormat = moa::threadBatch(batch(json::Array{job(text.path, json::Object(input))}));
  EXPECT_EQ(invalidFormat.getArray("results")->front().getAsObject()->getObject("error")->getString("code"),
            "format_invalid");

  auto unreadable = moa::threadBatch(batch(json::Array{job("/definitely/absent.bc", origin())}));
  EXPECT_EQ(unreadable.getArray("results")->front().getAsObject()->getObject("error")->getString("code"),
            "input_unreadable");

  LLVMContext context;
  auto module = parse(context, "define i32 @main() { entry: ret i32 0 }");
  ASSERT_TRUE(module);
  Temp file;
  file.bc(*module);
  auto bytes = MemoryBuffer::getFile(file.path);
  ASSERT_TRUE(bytes);
  input = origin();
  input["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef((*bytes)->getBuffer())), true);
  auto limits = budgets();
  limits["worker_output_bytes"] = 1024;
  EXPECT_THROW(moa::threadBatch(batch(json::Array{job(file.path, std::move(input), std::move(limits))})),
               std::runtime_error);

  std::string out, err;
  raw_string_ostream os(out), es(err);
  EXPECT_EQ(moa::threadWorker("/definitely/absent.json", os, es), 1);
  EXPECT_NE(err.find("input_unreadable"), std::string::npos);
}

TEST(Threads, LocalFactsCoverConservativeProvenanceCallsAndControlFlow) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"
@external = external global i32
@nonzero = global i64 1
declare !callback !0 fastcc i32 @pthread_create(ptr, ptr, ptr, ptr)
declare i32 @pthread_mutex_lock(ptr)
declare i32 @pthread_mutex_unlock(ptr)
declare i32 @pthread_future(ptr)
declare void @read_only(ptr) memory(read)
declare i32 @pure_i32() memory(none)
declare void @may_throw()
declare void @never_returns() noreturn

define void @worker() { entry: ret void }

define void @calls(ptr %fp, i1 %choose) personality ptr null {
entry:
  %slot = alloca ptr
  %other = alloca ptr
  store ptr %other, ptr %slot
  %loaded = load ptr, ptr %slot
  %asint = ptrtoint ptr %loaded to i64
  %selected = select i1 %choose, ptr %loaded, ptr %other
  br i1 %choose, label %left, label %right
left:
  store i32 1, ptr @external
  br label %merge
right:
  store i32 2, ptr @external
  br label %merge
merge:
  %joined = phi ptr [ %loaded, %left ], [ %selected, %right ]
  %unresolved = load i32, ptr inttoptr (i64 1 to ptr)
  store i32 7, ptr inttoptr (i64 8 to ptr)
  store ptr %slot, ptr inttoptr (i64 16 to ptr)
  fence seq_cst
  %created = call fastcc i32 @pthread_create(ptr %slot, ptr null, ptr %joined, ptr null)
  %sum = add i32 %created, 1
  %bad = icmp eq i32 %created, 7
  %good = icmp ne i32 0, %created
  %locked = call i32 @pthread_mutex_lock(ptr @nonzero)
  %unlocked = call i32 @pthread_mutex_unlock(ptr %slot)
  %external_lock = call i32 @pthread_mutex_lock(ptr @external)
  %future = call i32 @pthread_future(ptr %slot)
  call void @read_only(ptr %slot)
  %onlyadd = call i32 @pure_i32()
  %used = add i32 %onlyadd, 1
  %ordered = call i32 @pure_i32()
  %less = icmp slt i32 %ordered, 0
  %both1 = call i32 @pure_i32()
  %both2 = call i32 @pure_i32()
  %both = icmp eq i32 %both1, %both2
  %nonzero = call i32 @pure_i32()
  %seven = icmp eq i32 %nonzero, 7
  call void %fp()
  invoke void @may_throw() to label %normal unwind label %unwind
normal:
  call void @never_returns()
  unreachable
unwind:
  ret void
}

define void @reverse(i1 %take) {
entry:
  br label %pred
later:
  store i32 1, ptr @external
  ret void
pred:
  %v = load i32, ptr @external
  br i1 %take, label %later, label %exit
exit:
  ret void
}

define void @cycle(i1 %again) {
entry: br label %one
one:
  store i32 1, ptr @external
  br label %two
two:
  %v = load i32, ptr @external
  br i1 %again, label %one, label %exit
exit:
  %last = load i32, ptr @external
  ret void
}
!0 = !{!1, !"not-a-node", !2}
!1 = !{!"not-an-integer"}
!2 = !{i128 18446744073709551616}
)");
  ASSERT_TRUE(module);
  auto result = moa::threadFacts(*module, origin(), budgets());
  auto &local = *result.getObject("local");
  auto &orderFacts = *result.getObject("order");
  EXPECT_TRUE(any_of(*local.getArray("provenance"), [](const json::Value &value) {
    return value.getAsObject()->getString("kind") == "cast";
  }));
  for (StringRef kind : {"phi", "select", "load", "store", "clobber", "initializer"})
    EXPECT_TRUE(any_of(*local.getArray("provenance"), [kind](const json::Value &value) {
      return value.getAsObject()->getString("kind") == kind;
    }));
  EXPECT_TRUE(any_of(*local.getArray("calls"), [](const json::Value &value) {
    auto &item = *value.getAsObject();
    return item.getString("symbol") == "pthread_create" && item.getString("status") == "unknown" &&
           item.getString("reason") == "unsupported-pthread-abi";
  }));
  EXPECT_TRUE(any_of(*local.getArray("calls"), [](const json::Value &value) {
    auto &item = *value.getAsObject();
    return !item.getBoolean("direct").value() && item.getString("reason") == "indirect-call";
  }));
  EXPECT_TRUE(any_of(*local.getArray("calls"), [](const json::Value &value) {
    auto &item = *value.getAsObject();
    return item.getObject("unwind_successor") && item.getObject("normal_successor");
  }));
  EXPECT_FALSE(local.getArray("diagnostics")->empty());
  std::set<StringRef> relations;
  for (const auto &value : *orderFacts.getArray("edges"))
    relations.insert(*value.getAsObject()->getString("relation"));
  EXPECT_TRUE(relations.contains("may-before"));
  EXPECT_TRUE(relations.contains("mutually-exclusive"));
}

TEST(Threads, LocalAndGraphBudgetsPublishPartialFrontiers) {
  LLVMContext localContext;
  auto globals = parse(localContext, R"(
@one = global i32 1
@two = external global i32
define void @work() { entry: ret void }
)");
  ASSERT_TRUE(globals);
  auto localLimits = budgets();
  localLimits["local_steps"] = 1;
  auto localResult = moa::threadFacts(*globals, origin(), localLimits);
  EXPECT_EQ(localResult.getObject("local")->getString("status"), "partial");
  EXPECT_FALSE(localResult.getObject("local")->getArray("frontier")->empty());

  LLVMContext graphContext;
  auto events = parse(graphContext, R"(
@x = global i32 0
define void @work() {
entry:
  %v = load i32, ptr @x
  store i32 %v, ptr @x
  ret void
}
)");
  ASSERT_TRUE(events);
  auto graphLimits = budgets();
  graphLimits["graph_items"] = 1;
  auto graphResult = moa::threadFacts(*events, origin(), graphLimits);
  EXPECT_EQ(graphResult.getObject("order")->getString("status"), "partial");
  EXPECT_FALSE(graphResult.getObject("order")->getArray("frontier")->empty());

  LLVMContext instructionContext;
  auto instructions = parse(instructionContext, R"(
define void @work(i32 %v, ptr %p) {
entry:
  store i32 %v, ptr %p
  store i32 %v, ptr %p
  ret void
}
)");
  ASSERT_TRUE(instructions);
  auto instructionLimits = budgets();
  instructionLimits["local_steps"] = 1;
  auto instructionResult = moa::threadFacts(*instructions, origin(), instructionLimits);
  EXPECT_EQ(instructionResult.getObject("local")->getString("status"), "partial");

  auto pairLimits = budgets();
  pairLimits["graph_items"] = 2;
  auto pairResult = moa::threadFacts(*events, origin(), pairLimits);
  EXPECT_EQ(pairResult.getObject("order")->getString("status"), "partial");
}

TEST(Threads, SupportedNamesStillRequireEveryAbiAndCallbackCondition) {
  const std::vector<const char *> modules = {
    "declare void @pthread_join(i64, ptr) define void @f(i64 %h) { call void @pthread_join(i64 %h, ptr null) ret void }",
    "declare i32 @pthread_create(ptr, ptr, ptr) define void @f(ptr %p) { %r = call i32 @pthread_create(ptr %p, ptr null, ptr null) ret void }",
    "declare i32 @pthread_mutex_lock(ptr, ptr) define void @f(ptr %p) { %r = call i32 @pthread_mutex_lock(ptr %p, ptr null) ret void }",
    "declare i32 @pthread_create(ptr, ptr, ptr, ptr) define void @f(ptr %p) { %r = call i32 @pthread_create(ptr %p, ptr null, ptr null, ptr null) ret void }",
    "declare i32 @pthread_join() define void @f() { %r = call i32 @pthread_join() ret void }",
    "declare i32 @pthread_mutex_unlock() define void @f() { %r = call i32 @pthread_mutex_unlock() ret void }",
  };
  unsigned candidate = 0, unknown = 0, callbackMissing = 0;
  for (const char *text : modules) {
    LLVMContext context;
    auto module = parse(context, text);
    ASSERT_TRUE(module);
    auto result = moa::threadFacts(*module, origin(), budgets());
    auto &fact = *result.getObject("local")->getArray("calls")->front().getAsObject();
    candidate += fact.getString("status") == "candidate";
    unknown += fact.getString("status") == "unknown";
    callbackMissing += fact.getString("symbol") == "pthread_create" &&
                       fact.getArray("callback_targets")->empty();
  }
  EXPECT_EQ(candidate, 1u);
  EXPECT_EQ(unknown, 5u);
  EXPECT_EQ(callbackMissing, 2u);
}

TEST(Threads, CallbackCandidatesFollowBoundedBitcastSelectAndPhi) {
  LLVMContext context;
  auto module = parse(context, R"(
declare !callback !0 i32 @pthread_create(ptr, ptr, ptr, ptr)
define ptr @one(ptr %p) { ret ptr null }
define ptr @two(ptr %p) { ret ptr null }
define void @start(ptr %tid, i1 %choose) {
entry:
  %selected = select i1 %choose, ptr @one, ptr @two
  br i1 %choose, label %left, label %right
left: br label %merge
right: br label %merge
merge:
  %joined = phi ptr [ @one, %left ], [ %selected, %right ]
  %first = call i32 @pthread_create(ptr %tid, ptr null, ptr %selected, ptr null)
  %second = call i32 @pthread_create(ptr %tid, ptr null, ptr %joined, ptr null)
  ret void
}
!0 = !{!1}
!1 = !{i64 2, i64 3, i1 false}
)");
  ASSERT_TRUE(module);
  auto result = moa::threadFacts(*module, origin(), budgets());
  auto &calls = *result.getObject("local")->getArray("calls");
  ASSERT_EQ(calls.size(), 2u);
  EXPECT_EQ(calls[0].getAsObject()->getArray("callback_targets")->size(), 2u);
  EXPECT_EQ(calls[1].getAsObject()->getArray("callback_targets")->size(), 2u);
  auto limits = budgets();
  limits["value_candidates"] = 1;
  auto limited = moa::threadFacts(*module, origin(), limits);
  EXPECT_FALSE(limited.getObject("local")->getArray("diagnostics")->empty());
}
