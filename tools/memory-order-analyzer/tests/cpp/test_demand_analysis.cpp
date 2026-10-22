#include "demand_analysis.h"
#include "ir_identity.h"

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
std::unique_ptr<Module> parse(LLVMContext &context, const char *text) {
  SMDiagnostic error;
  auto module = parseAssemblyString(text, error, context);
  if (!module) error.print("demand-unit", errs());
  return module;
}

struct Temp {
  SmallString<128> path;
  Temp() { EXPECT_FALSE(sys::fs::createTemporaryFile("moa-demand-unit", "input", path)); }
  ~Temp() { sys::fs::remove(path); }
  void text(const std::string &value) { std::ofstream out(path.c_str(), std::ios::binary); out << value; }
  void bc(Module &module) {
    std::error_code error;
    raw_fd_ostream stream(path, error);
    EXPECT_FALSE(error);
    WriteBitcodeToFile(module, stream);
  }
  std::string hash() const {
    auto data = MemoryBuffer::getFile(path);
    EXPECT_TRUE(bool(data));
    return toHex(SHA256::hash(arrayRefFromStringRef((*data)->getBuffer())), true);
  }
};

json::Object job(StringRef path, StringRef hash, StringRef id = "job") {
  const std::string artifact(64, 'a');
  auto protocol = moa::demandProtocol();
  json::Object limits(*protocol.getObject("budgets"));
  json::Array layers{"effect", "semantic", "thread"};
  json::Array demands{json::Object{{"function_id", artifact + ":symbol:main"},
    {"function_name", "main"}, {"context_id", "root:main"}, {"layers", std::move(layers)}}};
  return json::Object{{"id", id.str()}, {"path", path.str()}, {"artifact_key", artifact},
    {"bc_digest", hash.str()}, {"physical_tu_id", "tu"}, {"profile_id", "clang-c11"},
    {"target", "x86_64-pc-linux-gnu"}, {"data_layout", "e-p:64:64-i128:128"},
    {"abi", "itanium"}, {"demands", std::move(demands)}, {"budgets", std::move(limits)}};
}

json::Object batch(json::Array jobs, json::Object protocol = moa::demandProtocol()) {
  return json::Object{{"protocol", std::move(protocol)}, {"jobs", std::move(jobs)}};
}
json::Object advancedBatch(json::Array jobs) {
  return json::Object{{"protocol", moa::advancedAtomicProtocol()},
    {"demand_protocol", moa::demandProtocol()}, {"jobs", std::move(jobs)}};
}
std::string stringify(const json::Object &value) {
  std::string text;
  raw_string_ostream out(text);
  out << json::Value(json::Object(value));
  return text;
}

std::string errorCode(json::Object value) {
  auto output = moa::demandBatch(batch(json::Array{std::move(value)}));
  auto *error = (*output.getArray("results"))[0].getAsObject()->getObject("error");
  return error ? error->getString("code")->str() : "";
}
}

TEST(DemandAnalysis, LazyIndexAndFunctionShardsPreserveIdentity) {
  LLVMContext context;
  auto detached = std::unique_ptr<Function>(Function::Create(
      FunctionType::get(Type::getVoidTy(context), false), GlobalValue::ExternalLinkage, "detached"));
  DenseMap<const Value *, std::string> detachedIds;
  moa::registerFunctionIdentities(*detached, std::string(64, 'a'), detachedIds);
  EXPECT_EQ(detachedIds.lookup(detached.get()), std::string(64, 'a') + ":symbol:detached");
  EXPECT_EQ(moa::functionIdentities(*detached, std::string(64, 'a')).lookup(detached.get()),
            std::string(64, 'a') + ":symbol:detached");
  auto module = parse(context, R"(
target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-p:64:64-i128:128"
@value = global i32 0
declare i32 @pthread_create(ptr, ptr, ptr, ptr)
define ptr @worker(ptr %arg) {
entry:
  %v = load i32, ptr @value
  ret ptr null
}
define i32 @main() {
entry:
  %tid = alloca i64
  store i32 1, ptr @value
  %created = call i32 @pthread_create(ptr %tid, ptr null, ptr @worker, ptr null)
  ret i32 %created
}
define void @unreachable() {
entry:
  store i32 99, ptr @value
  ret void
}
)");
  ASSERT_TRUE(module);
  auto eager = moa::originalIdentities(*module, std::string(64, 'a'));
  std::set<std::string> mainIds;
  for (auto &block : *module->getFunction("main"))
    for (auto &instruction : block) mainIds.insert(eager.lookup(&instruction));
  Temp input; input.bc(*module);
  auto output = moa::demandBatch(batch(json::Array{job(input.path, input.hash())}));
  ASSERT_TRUE(output.get("error")->getAsNull());
  ASSERT_EQ(output.getArray("results")->size(), 1u);
  auto &result = *(*output.getArray("results"))[0].getAsObject();
  ASSERT_TRUE(result.get("error")->getAsNull()) << stringify(output);
  auto &index = *result.getObject("index");
  EXPECT_EQ(index.getObject("counts")->getInteger("materialized_functions"), 0);
  EXPECT_EQ(index.getObject("counts")->getInteger("materialized_instructions"), 0);
  EXPECT_GE(*index.getObject("counts")->getInteger("indexed_functions"), 4);
  ASSERT_EQ(result.getArray("shards")->size(), 3u);
  std::set<std::string> lazyIds;
  for (auto &item : *result.getArray("shards")) {
    auto &shard = *item.getAsObject();
    EXPECT_EQ(shard.getString("status"), "completed");
    EXPECT_EQ(shard.getObject("facts")->getBoolean("reference_closed"), true);
    EXPECT_FALSE(shard.getObject("facts")->getArray("instructions")->empty());
    if (shard.getString("layer") == "semantic")
      for (auto &instruction : *shard.getObject("facts")->getArray("instructions"))
        lazyIds.insert(instruction.getAsObject()->getString("id")->str());
  }
  EXPECT_EQ(lazyIds, mainIds);
  EXPECT_EQ(result.getObject("metrics")->getInteger("module_parses"), 1);
  EXPECT_EQ(result.getObject("metrics")->getInteger("materialized_functions"), 1);
  for (auto &item : *index.getArray("symbols"))
    if (item.getAsObject()->getString("name") == "unreachable")
      EXPECT_EQ(item.getAsObject()->getBoolean("materializable"), true);
}

TEST(DemandAnalysis, BudgetFailureAndBatchIsolationRemainExplicit) {
  LLVMContext context;
  auto module = parse(context, R"(
target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-p:64:64-i128:128"
define i32 @main() { entry: %x = add i32 1, 2
  ret i32 %x }
)");
  ASSERT_TRUE(module);
  Temp input; input.bc(*module);
  auto limited = job(input.path, input.hash(), "limited");
  limited.getObject("budgets")->operator[]("materialized_instructions") = 1;
  auto missing = job(input.path, std::string(64, 'b'), "changed");
  auto output = moa::demandBatch(batch(json::Array{std::move(limited), std::move(missing)}));
  ASSERT_EQ(output.getArray("results")->size(), 2u);
  auto &first = *(*output.getArray("results"))[0].getAsObject();
  ASSERT_TRUE(first.get("error")->getAsNull()) << stringify(output);
  EXPECT_TRUE(any_of(*first.getArray("shards"), [](const json::Value &item) {
    return item.getAsObject()->getString("status") == "partial";
  }));
  auto &second = *(*output.getArray("results"))[1].getAsObject();
  ASSERT_TRUE(second.getObject("error"));
  EXPECT_EQ(second.getObject("error")->getString("code"), "inputs_changed");
}

TEST(DemandAnalysis, WorkerProtocolAndInvalidTransport) {
  EXPECT_EQ(moa::demandProtocol().getString("policy_id"), "demand-driven-function-analysis-v1");
  std::string output, error;
  raw_string_ostream out(output), err(error);
  const char *protocol[] = {"worker", "--demand-analysis-protocol"};
  EXPECT_EQ(moa::worker(2, protocol, out, err), 0);
  EXPECT_NE(output.find("demand-driven-function-analysis-v1"), std::string::npos);
  output.clear(); error.clear();
  const char *advancedProtocol[] = {"worker", "--advanced-atomic-protocol"};
  EXPECT_EQ(moa::worker(2, advancedProtocol, out, err), 0);
  EXPECT_NE(output.find("fence-rmw-publication-v1"), std::string::npos);
  Temp request; request.text("[]"); output.clear(); error.clear();
  const char *argv[] = {"worker", "--demand-batch", request.path.c_str()};
  EXPECT_EQ(moa::worker(3, argv, out, err), 1);
  EXPECT_NE(error.find("demand_request"), std::string::npos);
  output.clear(); error.clear();
  const char *advancedArgv[] = {"worker", "--advanced-atomic-batch", request.path.c_str()};
  EXPECT_EQ(moa::worker(3, advancedArgv, out, err), 1);
  EXPECT_NE(error.find("advanced_atomic_request"), std::string::npos);
}

TEST(DemandAnalysis, RichControlAtomicThreadAndSymbolVariantsAreExplicit) {
  LLVMContext context;
  auto module = parse(context, R"(
target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-p:64:64-i128:128"
@value = hidden global i32 0
@other = protected global i32 0
@common = common global i32 0, align 4
@weak_g = weak global i32 0
@append = appending global [1 x ptr] [ptr @worker]
@private_g = private global i8 0
$group = comdat any
@comdat_g = linkonce_odr global i32 0, comdat($group)
declare extern_weak void @external_weak()
declare i32 @pure() memory(none)
declare i32 @pthread_create(ptr, ptr, ptr, ptr)
declare i32 @pthread_join(i64, ptr)
declare i32 @pthread_mutex_lock(ptr)
declare i32 @pthread_mutex_unlock(ptr)
declare i32 @thrd_create(ptr, ptr, ptr)
declare void @_M_start_thread()
declare void @__thread_proxy()
declare void @async_runtime()
define available_externally void @available() { ret void }
define linkonce void @once() { ret void }
define linkonce_odr void @once_odr() { ret void }
define weak void @weak_f() { ret void }
define weak_odr void @weak_odr_f() { ret void }
define internal void @internal_f() { ret void }
define private void @private_f() { ret void }
define ptr @worker(ptr %arg) { ret ptr %arg }
define i32 @main(i1 %cond, ptr %fp) {
entry:
  %chosen = select i1 %cond, i32 1, i32 2
  br i1 %cond, label %loop, label %exit
loop:
  %plain = load i32, ptr @other
  %old = load atomic i32, ptr @value acquire, align 4
  store atomic i32 %chosen, ptr @value release, align 4
  %rmw = atomicrmw add ptr @value, i32 1 acq_rel
  %cas = cmpxchg ptr @value, i32 %rmw, i32 3 acq_rel acquire
  fence seq_cst
  %indirect = call i32 %fp()
  %p = call i32 @pure()
  %tc = call i32 @thrd_create(ptr null, ptr @worker, ptr null)
  %tc_unknown = call i32 @thrd_create(ptr null, ptr null, ptr null)
  %pc = call i32 @pthread_create(ptr null, ptr null, ptr @worker, ptr null)
  %pc_unknown = call i32 @pthread_create(ptr null, ptr null, ptr null, ptr null)
  %pj = call i32 @pthread_join(i64 0, ptr null)
  %ml = call i32 @pthread_mutex_lock(ptr @other)
  %mu = call i32 @pthread_mutex_unlock(ptr @other)
  call void @_M_start_thread()
  call void @__thread_proxy()
  call void @async_runtime()
  br i1 false, label %loop, label %exit
exit:
  ret i32 %chosen
}
)");
  ASSERT_TRUE(module);
  Temp input; input.bc(*module);
  auto output = moa::demandBatch(batch(json::Array{job(input.path, input.hash())}));
  auto &result = *(*output.getArray("results"))[0].getAsObject();
  ASSERT_TRUE(result.get("error")->getAsNull()) << stringify(output);
  auto &symbols = *result.getObject("index")->getArray("symbols");
  std::set<std::string> linkages, visibilities;
  for (auto &item : symbols) {
    linkages.insert(item.getAsObject()->getString("linkage")->str());
    visibilities.insert(item.getAsObject()->getString("visibility")->str());
  }
  for (auto expected : {"available_externally", "linkonce", "linkonce_odr", "weak", "weak_odr",
                        "appending", "internal", "private", "extern_weak", "common"})
    EXPECT_TRUE(linkages.count(expected)) << expected;
  EXPECT_TRUE(visibilities.count("hidden"));
  EXPECT_TRUE(visibilities.count("protected"));
  for (auto &item : *result.getArray("shards")) {
    auto *shard = item.getAsObject();
    ASSERT_EQ(shard->getString("status"), "completed") << stringify(result);
    auto *facts = shard->getObject("facts");
    EXPECT_GT(facts->getArray("arguments")->size(), 0u);
    EXPECT_GT(facts->getArray("accesses")->size(), 5u);
    if (shard->getString("layer") == "semantic") {
      EXPECT_GT(facts->getArray("conditions")->size(), 1u);
      EXPECT_FALSE(facts->getArray("atomic_events"));
    }
    if (shard->getString("layer") == "thread") {
      EXPECT_GE(facts->getArray("thread_calls")->size(), 5u);
      EXPECT_TRUE(any_of(*facts->getArray("order_nodes"), [](const json::Value &value) {
        return value.getAsObject()->getString("multiplicity") == "repeated";
      }));
    }
  }

  auto advanced = moa::advancedAtomicDemandBatch(advancedBatch(
      json::Array{job(input.path, input.hash(), "advanced")}));
  auto &advancedResult = *(*advanced.getArray("results"))[0].getAsObject();
  ASSERT_TRUE(advancedResult.get("error")->getAsNull()) << stringify(advanced);
  ASSERT_EQ(advancedResult.getArray("shards")->size(), 1u);
  auto &advancedShard = *(*advancedResult.getArray("shards"))[0].getAsObject();
  EXPECT_EQ(advancedShard.getString("kind"), "AdvancedAtomicFunctionFacts");
  EXPECT_EQ(advancedShard.getString("layer"), "advanced-atomic");
  EXPECT_EQ(advancedShard.getString("status"), "complete");
  auto *atomicEvents = advancedShard.getObject("facts")->getArray("atomic_events");
  ASSERT_EQ(atomicEvents->size(), 5u);
  EXPECT_TRUE(any_of(*atomicEvents, [](const json::Value &value) {
    auto *event = value.getAsObject();
    return event->getString("kind") == "cas" && event->getString("ordering") == "acq_rel" &&
           event->getString("failure_ordering") == "acquire" &&
           event->getString("multiplicity") == "repeated";
  }));
  EXPECT_TRUE(any_of(*atomicEvents, [](const json::Value &value) {
    auto *event = value.getAsObject();
    return event->getString("kind") == "rmw" && event->getString("operation") == "add" &&
           event->getInteger("size_bytes") == 4;
  }));
}

TEST(DemandAnalysis, ValidationAndReaderFailuresStayClassified) {
  LLVMContext context;
  auto module = parse(context, R"(
target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-p:64:64-i128:128"
declare void @declared()
define i32 @main() { ret i32 0 }
)");
  ASSERT_TRUE(module);
  Temp input; input.bc(*module);
  auto good = job(input.path, input.hash());

  for (auto field : {"id", "path", "artifact_key", "bc_digest", "physical_tu_id", "profile_id",
                     "target", "data_layout", "abi"}) {
    auto invalid = json::Object(good);
    invalid[field] = "";
    EXPECT_EQ(errorCode(std::move(invalid)), "demand_request") << field;
  }
  auto noDemands = json::Object(good); noDemands.erase("demands");
  EXPECT_EQ(errorCode(std::move(noDemands)), "demand_request");
  auto noBudgets = json::Object(good); noBudgets.erase("budgets");
  EXPECT_EQ(errorCode(std::move(noBudgets)), "demand_request");
  auto shortBudgets = json::Object(good); shortBudgets.getObject("budgets")->erase("workers");
  EXPECT_EQ(errorCode(std::move(shortBudgets)), "demand_request");
  for (int64_t invalidValue : {int64_t(0), int64_t(999999999)}) {
    auto invalid = json::Object(good); (*invalid.getObject("budgets"))["workers"] = invalidValue;
    EXPECT_EQ(errorCode(std::move(invalid)), "demand_request");
  }
  auto missing = json::Object(good); missing["path"] = "/does/not/exist.bc";
  EXPECT_EQ(errorCode(std::move(missing)), "input_unreadable");
  Temp text; text.text("not bitcode");
  auto wrongFormat = job(text.path, text.hash());
  EXPECT_EQ(errorCode(std::move(wrongFormat)), "format_invalid");
  auto wrongTarget = json::Object(good); wrongTarget["target"] = "aarch64-linux-gnu";
  EXPECT_EQ(errorCode(std::move(wrongTarget)), "profile_conflict");
  auto wrongLayout = json::Object(good); wrongLayout["data_layout"] = "e-p:32:32";
  EXPECT_EQ(errorCode(std::move(wrongLayout)), "profile_conflict");
  Temp corrupt; corrupt.text(std::string("BC\xc0\xde", 4) + "broken");
  auto brokenBc = job(corrupt.path, corrupt.hash());
  EXPECT_EQ(errorCode(std::move(brokenBc)), "reader_failed");

  auto absent = json::Object(good);
  auto *demand = (*absent.getArray("demands"))[0].getAsObject();
  (*demand)["function_name"] = "absent";
  EXPECT_EQ(errorCode(std::move(absent)), "function_not_found");
  auto wrongIdentity = json::Object(good);
  (*(*wrongIdentity.getArray("demands"))[0].getAsObject())["function_id"] = std::string(64, 'b') + ":symbol:main";
  EXPECT_EQ(errorCode(std::move(wrongIdentity)), "function_not_found");
  auto declaration = json::Object(good);
  demand = (*declaration.getArray("demands"))[0].getAsObject();
  (*demand)["function_name"] = "declared";
  (*demand)["function_id"] = std::string(64, 'a') + ":symbol:declared";
  EXPECT_EQ(errorCode(std::move(declaration)), "function_declaration");
  auto badLayer = json::Object(good);
  (*(*badLayer.getArray("demands"))[0].getAsObject()->getArray("layers"))[0] = "unknown";
  EXPECT_EQ(errorCode(std::move(badLayer)), "demand_request");
  auto nonStringLayer = json::Object(good);
  (*(*nonStringLayer.getArray("demands"))[0].getAsObject()->getArray("layers"))[0] = nullptr;
  EXPECT_EQ(errorCode(std::move(nonStringLayer)), "demand_request");
  auto duplicate = json::Object(good);
  duplicate.getArray("demands")->push_back(json::Value((*duplicate.getArray("demands"))[0]));
  EXPECT_EQ(errorCode(std::move(duplicate)), "demand_request");
  auto twoContexts = json::Object(good);
  auto second = json::Object(*(*twoContexts.getArray("demands"))[0].getAsObject());
  second["context_id"] = "root:other";
  twoContexts.getArray("demands")->push_back(std::move(second));
  auto repeatedOutput = moa::demandBatch(batch(json::Array{std::move(twoContexts)}));
  EXPECT_FALSE((*repeatedOutput.getArray("results"))[0].getAsObject()->getObject("error"));

  for (const char *missingField : {"function_id", "function_name", "context_id", "layers"}) {
    auto invalidDemand = json::Object(good);
    (*invalidDemand.getArray("demands"))[0].getAsObject()->erase(missingField);
    EXPECT_EQ(errorCode(std::move(invalidDemand)), "demand_request") << missingField;
  }

  EXPECT_THROW(moa::demandBatch(json::Object{}), std::runtime_error);
  EXPECT_THROW(moa::demandBatch(batch(json::Array{})), std::runtime_error);
  EXPECT_THROW(moa::demandBatch(json::Object{{"protocol", moa::demandProtocol()}}), std::runtime_error);
  EXPECT_THROW(moa::demandBatch(json::Object{{"jobs", json::Array{json::Object(good)}}}), std::runtime_error);
  auto invalidProtocol = moa::demandProtocol(); invalidProtocol["policy_id"] = "other";
  EXPECT_THROW(moa::demandBatch(batch(json::Array{json::Object(good)}, std::move(invalidProtocol))), std::runtime_error);
  auto duplicateJob = json::Object(good);
  EXPECT_THROW(moa::demandBatch(batch(json::Array{json::Object(duplicateJob), json::Object(duplicateJob)})), std::runtime_error);
  auto withoutJobBudgets = json::Object(good); withoutJobBudgets.erase("budgets");
  auto noBudgetOutput = moa::demandBatch(batch(json::Array{std::move(withoutJobBudgets)}));
  EXPECT_EQ((*noBudgetOutput.getArray("results"))[0].getAsObject()->getObject("error")->getString("code"),
            "demand_request");

  Temp request; request.text("{");
  std::string output, error;
  raw_string_ostream out(output), err(error);
  EXPECT_EQ(moa::demandWorker(request.path.c_str(), out, err), 1);
  EXPECT_NE(error.find("invalid JSON"), std::string::npos);
  output.clear(); error.clear();
  EXPECT_EQ(moa::demandWorker("/does/not/exist.json", out, err), 1);
  EXPECT_NE(error.find("input_unreadable"), std::string::npos);
}
