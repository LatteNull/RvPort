#include "effects.h"
#include "ir_identity.h"
#include <gtest/gtest.h>
#include <llvm/AsmParser/Parser.h>
#include <llvm/Bitcode/BitcodeWriter.h>
#include <llvm/IR/IRBuilder.h>
#include <llvm/Support/FileSystem.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/SHA256.h>
#include <llvm/ADT/StringExtras.h>
#include <fstream>
#include <functional>

using namespace llvm;
namespace {
json::Object origin() {
  return json::Object{{"artifact_key", std::string(64, 'a')}, {"module_hash", std::string(64, 'b')},
    {"facts_hash", std::string(64, 'c')}, {"profile", "source-preserving"}, {"extractor_version", "0.2.0"}, {"llvm_version", "21.1.8"}};
}
json::Object budgets() { return *moa::analysisProtocol().getObject("budgets"); }
std::unique_ptr<Module> parse(LLVMContext &context, const char *text) {
  SMDiagnostic error;
  auto result = parseAssemblyString(text, error, context);
  if (!result) error.print("effects-unit", errs());
  return result;
}
struct Temp {
  SmallString<128> path;
  Temp() { EXPECT_FALSE(sys::fs::createTemporaryFile("moa-effects-unit", "input", path)); }
  ~Temp() { sys::fs::remove(path); }
  void text(const std::string &value) { std::ofstream out(path.c_str(), std::ios::binary); out << value; }
  void bc(Module &module) {
    std::error_code error;
    raw_fd_ostream stream(path, error);
    EXPECT_FALSE(error);
    WriteBitcodeToFile(module, stream);
  }
};
json::Object batch(const std::string &path, json::Object input = origin()) {
  return json::Object{{"protocol", moa::analysisProtocol()}, {"jobs", json::Array{json::Object{
    {"id", "job"}, {"path", path}, {"origin", std::move(input)}, {"budgets", budgets()}}}}};
}
std::string stringify(json::Object value) { std::string s; raw_string_ostream out(s); out << json::Value(std::move(value)); return s; }
json::Object evaluation(Module &module, json::Object input) {
  auto artifact = input.getString("artifact_key")->str();
  auto ids = moa::originalIdentities(module, artifact);
  auto *function = module.getFunction("f");
  input["facts_hash"] = moa::analysisDigest(moa::extract(module, artifact, input.getString("module_hash")->str()));
  auto local = moa::localMetadata(module, input, budgets());
  json::Object source{{"artifact_key", artifact}, {"function_id", nullptr}, {"id", ids[function]}};
  json::Array arguments;
  for (auto &arg : function->args()) {
    (void)arg;
    arguments.push_back(json::Object{{"state", "unknown"}, {"candidates", json::Array{}}, {"reason", "test-input"}});
  }
  return json::Object{{"schema_version", 1}, {"kind", "LocalEvaluationRequest"}, {"analysis_version", "0.1.0"},
    {"policy_id", "scoped-effects-v1"}, {"scope_id", std::string(64, 'd')}, {"context_id", "context"},
    {"function", json::Object(source)}, {"invocation_id", "root"}, {"origins", json::Array{json::Object(input)}}, {"arguments", std::move(arguments)},
    {"invocations", json::Array{json::Object{{"id", "root"}, {"context_id", "context"}, {"function", json::Object(source)},
       {"parent_id", nullptr}, {"callsite", nullptr}, {"cardinality", "single"}, {"reason", nullptr}}}},
    {"adoptions", json::Array{}}, {"dependencies", json::Array{}}, {"call_bindings", json::Array{}},
    {"local_dependencies", json::Array{json::Object{{"artifact_key", artifact}, {"digest", moa::analysisDigest(std::move(local))}}}},
    {"budgets", budgets()}};
}
json::Object evaluationEnvelope(const std::string &path, const json::Object &request) {
  return json::Object{{"protocol", moa::analysisProtocol()}, {"jobs", json::Array{json::Object{
    {"id", "eval"}, {"path", path}, {"request", json::Object(request)}, {"summaries", json::Array{}}}}}};
}
} // namespace

TEST(Effects, EvaluationBatchRunsBoundedPlanAndBindsBitcodeFacts) {
  LLVMContext context;
  auto module = parse(context, "define i32 @f(i32 %x) {entry: br label %exit\nexit: ret i32 %x}");
  ASSERT_TRUE(module);
  Temp bc; bc.bc(*module);
  auto data = MemoryBuffer::getFile(bc.path);
  ASSERT_TRUE(data);
  auto input = origin();
  input["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef((*data)->getBuffer())), true);
  auto request = evaluation(*module, input);
  auto envelope = evaluationEnvelope(bc.path.str().str(), request);
  auto result = moa::evaluationBatch(envelope);
  ASSERT_EQ(result.getArray("results")->size(), 1u);
  auto &entry = *(*result.getArray("results"))[0].getAsObject();
  ASSERT_TRUE(entry.get("error")->getAsNull());
  auto &output = *entry.getObject("result");
  EXPECT_EQ(output.getString("kind"), "LocalEvaluationResult");
  EXPECT_EQ(output.getString("request_hash"), moa::analysisDigest(json::Object(request)));
  EXPECT_EQ(output.getString("status"), "partial");
  EXPECT_GT(*output.getInteger("steps"), 0);
  EXPECT_EQ(output.getArray("blocks")->size(), 2u);
  EXPECT_EQ(output.getArray("frontier")->size(), 3u);
  EXPECT_TRUE(output.getArray("effects")->empty());
  EXPECT_EQ((*output.getArray("blocks"))[0].getAsObject()->getString("state"), "reachable");
  EXPECT_EQ((*output.getArray("blocks"))[1].getAsObject()->getString("state"), "pending");
  EXPECT_EQ(json::Value(json::Object(result)), json::Value(moa::evaluationBatch(envelope)));
  EXPECT_EQ((*MemoryBuffer::getFile(bc.path))->getBuffer(), (*data)->getBuffer());
  Temp wire; wire.text(stringify(envelope));
  std::string out, err;
  raw_string_ostream os(out), es(err);
  const char *argv[] = {"worker", "--evaluate-batch", wire.path.c_str()};
  EXPECT_EQ(moa::worker(3, argv, os, es), 0);
  EXPECT_TRUE(err.empty());
  auto parsed = json::parse(out); ASSERT_TRUE(bool(parsed));
  EXPECT_EQ(*parsed, json::Value(json::Object(result)));
  wire.text("[]"); out.clear();
  EXPECT_EQ(moa::worker(3, argv, os, es), 1);
  EXPECT_NE(err.find("analysis_request"), std::string::npos);

  // These are per-job failures; the planned job is never filtered away.
  for (auto field : {"module_hash", "facts_hash"}) {
    auto bad = request;
    (*bad.getArray("origins"))[0].getAsObject()->operator[](field) = std::string(64, 'e');
    auto failed = moa::evaluationBatch(evaluationEnvelope(bc.path.str().str(), bad));
    auto &item = *(*failed.getArray("results"))[0].getAsObject();
    EXPECT_TRUE(item.get("result")->getAsNull());
    EXPECT_EQ(item.getObject("error")->getString("code"), "inputs_changed");
  }
  auto bad = request;
  (*bad.getArray("local_dependencies"))[0].getAsObject()->operator[]("digest") = std::string(64, 'e');
  auto failed = moa::evaluationBatch(evaluationEnvelope(bc.path.str().str(), bad));
  EXPECT_EQ((*failed.getArray("results"))[0].getAsObject()->getObject("error")->getString("code"), "inputs_changed");
}

TEST(Effects, EvaluationExecutesControlPrivateStorageAndBudgets) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"
define i32 @f(i1 %c, i32 %x) {
entry:
 %slot = alloca i32
 store i32 %x, ptr %slot
 br i1 %c, label %left, label %right
left:
 %loaded = load i32, ptr %slot
 br label %join
right:
 store i32 9, ptr %slot
 br label %join
join:
 %value = phi i32 [%loaded, %left], [9, %right]
 ret i32 %value
dead:
 ret i32 0
})");
  ASSERT_TRUE(module);
  auto request = evaluation(*module, origin());
  auto finite = [](unsigned bits, StringRef hex) { return json::Object{{"state", "finite"},
    {"candidates", json::Array{json::Object{{"value", json::Object{{"kind", "integer"}, {"bits", bits}, {"hex", hex.str()}}},
      {"guards", json::Array{}}, {"proof", json::Array{}}}}}, {"reason", nullptr}}; };
  (*request.getArray("arguments"))[0] = finite(1, "1");
  (*request.getArray("arguments"))[1] = finite(32, "7");
  auto result = moa::evaluationPlan(*module, request);
  EXPECT_EQ(result.getString("status"), "complete");
  ASSERT_EQ(result.getArray("effects")->size(), 2u);
  EXPECT_EQ((*result.getArray("effects"))[0].getAsObject()->getString("kind"), "write");
  EXPECT_EQ((*result.getArray("effects"))[1].getAsObject()->getString("kind"), "read");
  EXPECT_EQ((*result.getArray("effects"))[1].getAsObject()->getObject("value")->getString("hex"), "7");
  EXPECT_EQ(result.getArray("returns")->front().getAsObject()->getObject("value")->getString("hex"), "7");
  EXPECT_EQ(result.getArray("blocks")->back().getAsObject()->getString("state"), "unreachable");
  EXPECT_FALSE(result.getArray("blocks")->back().getAsObject()->getArray("proof")->empty());
  EXPECT_FALSE(result.getArray("order")->empty());
  EXPECT_EQ(result, moa::evaluationPlan(*module, request));

  auto alternate = request;
  (*alternate.getArray("arguments"))[0] = finite(1, "0");
  auto other = moa::evaluationPlan(*module, alternate);
  EXPECT_EQ(other.getArray("returns")->front().getAsObject()->getObject("value")->getString("hex"), "9");
  EXPECT_EQ(other.getArray("effects")->size(), 2u);

  auto bounded = request;
  (*bounded.getObject("budgets"))["condition_states"] = 1;
  auto cut = moa::evaluationPlan(*module, bounded);
  EXPECT_EQ(cut.getString("status"), "partial");
  EXPECT_FALSE(cut.getArray("frontier")->empty());
  EXPECT_TRUE(llvm::any_of(*cut.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "condition_states_budget";
  }));
  EXPECT_TRUE(llvm::any_of(*cut.getArray("blocks"), [](const auto &item) {
    return item.getAsObject()->getString("state") == "pending";
  }));
}

TEST(Effects, EvaluationMergesGuardedPhiCandidatesAndWidensAtCandidateLimit) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
define i32 @f(i1 %condition) {
entry: br i1 %condition, label %left, label %right
left: br label %join
right: br label %join
join: %value = phi i32 [7, %left], [9, %right]
 ret i32 %value
})");
  ASSERT_TRUE(module);
  auto request = evaluation(*module, origin());
  auto result = moa::evaluationPlan(*module, request);
  auto ids = moa::originalIdentities(*module, std::string(64, 'a'));
  auto *phi = &*module->getFunction("f")->back().begin();
  auto found = llvm::find_if(*result.getArray("values"), [&](const auto &item) {
    return item.getAsObject()->getObject("source")->getString("id") == ids[phi];
  });
  ASSERT_NE(found, result.getArray("values")->end());
  auto *domain = found->getAsObject()->getObject("domain");
  EXPECT_EQ(domain->getString("state"), "finite");
  ASSERT_EQ(domain->getArray("candidates")->size(), 2u);
  std::set<int64_t> edges;
  for (const auto &candidate : *domain->getArray("candidates"))
    edges.insert(*candidate.getAsObject()->getArray("guards")->front().getAsObject()->getInteger("edge"));
  EXPECT_EQ(edges, (std::set<int64_t>{0, 1}));

  auto tight = request;
  (*tight.getObject("budgets"))["value_candidates"] = 1;
  auto widened = moa::evaluationPlan(*module, tight);
  EXPECT_TRUE(llvm::any_of(*widened.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "value_candidate_budget";
  }));
}

TEST(Effects, EvaluationLoopPathsNeverDuplicateGuards) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
declare void @external()
define void @f(i1 %again) {
entry: br label %loop
loop:
 call void @external()
 br i1 %again, label %loop, label %exit
exit:
 ret void
})");
  ASSERT_TRUE(module);
  auto result = moa::evaluationPlan(*module, evaluation(*module, origin()));
  ASSERT_EQ(result.getArray("call_requests")->size(), 1u);
  for (const auto &value : *result.getArray("call_requests")) {
    std::set<std::string> seen;
    for (const auto &guard : *value.getAsObject()->getArray("guards"))
      EXPECT_TRUE(seen.insert(moa::analysisDigest(guard)).second);
  }
}

TEST(Effects, EvaluationInvalidatesOnlyTouchedStorageAndKeepsAtomicUnknown) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"
@shared = internal global i32 0
declare void @escape(ptr)
define i32 @f() {
entry:
 %a = alloca i32
 %b = alloca i32
 store i32 1, ptr %a
 store i32 2, ptr %b
 call void @escape(ptr %a)
 %still = load i32, ptr %b
 %observed = load atomic i32, ptr @shared acquire, align 4
 ret i32 %still
})");
  ASSERT_TRUE(module);
  auto result = moa::evaluationPlan(*module, evaluation(*module, origin()));
  EXPECT_EQ(result.getString("status"), "partial");
  ASSERT_EQ(result.getArray("effects")->size(), 5u);
  auto *localRead = (*result.getArray("effects"))[3].getAsObject();
  EXPECT_EQ(localRead->getString("kind"), "read");
  EXPECT_EQ(localRead->getObject("value")->getString("hex"), "2");
  auto *atomicRead = (*result.getArray("effects"))[4].getAsObject();
  EXPECT_EQ(atomicRead->getBoolean("atomic"), true);
  EXPECT_EQ(atomicRead->getString("ordering"), "acquire");
  EXPECT_EQ(atomicRead->getObject("value")->getString("kind"), "unknown");
  EXPECT_EQ(result.getArray("returns")->front().getAsObject()->getObject("value")->getString("hex"), "2");
  EXPECT_TRUE(llvm::any_of(*result.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "unknown_call_effect";
  }));
  EXPECT_TRUE(llvm::any_of(*result.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "shared_or_atomic_load";
  }));
}

TEST(Effects, EvaluationRecordsEscapedStorageAndRejectsExpiredLocalReturn) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@sink = internal global ptr null
define ptr @f() {
entry:
 %slot = alloca i32
 store i32 7, ptr %slot
 store ptr %slot, ptr @sink
 %invalid = load i32, ptr %slot
 ret ptr %slot
})");
  ASSERT_TRUE(module);
  auto result = moa::evaluationPlan(*module, evaluation(*module, origin()));
  EXPECT_EQ(result.getString("status"), "partial");
  EXPECT_FALSE(result.getArray("escape")->empty());
  EXPECT_TRUE(llvm::any_of(*result.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "uninitialized_load";
  }));
  EXPECT_TRUE(llvm::any_of(*result.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "expired_local_return";
  })) << stringify(json::Object(result));
  EXPECT_TRUE(result.getArray("returns")->front().getAsObject()->get("value")->getAsNull().has_value());
}

TEST(Effects, EvaluationConsumesBoundCalleeReturnAndPreservesCallerObject) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"
@object = internal global [8 x i8] zeroinitializer
define ptr @g(ptr %p) { entry: %field = getelementptr i8, ptr %p, i64 4
 ret ptr %field }
define void @f(ptr %p) { entry: %q = call ptr @g(ptr %p)
 store i32 7, ptr %q
 ret void }
)");
  ASSERT_TRUE(module);
  auto request = evaluation(*module, origin());
  auto ids = moa::originalIdentities(*module, std::string(64, 'a'));
  auto *caller = module->getFunction("f"), *callee = module->getFunction("g");
  auto *call = cast<CallBase>(&*caller->getEntryBlock().begin());
  auto global = module->getGlobalVariable("object", true);
  (*request.getArray("arguments"))[0] = json::Object{{"state", "finite"}, {"candidates", json::Array{
    json::Object{{"value", json::Object{{"kind", "object"},
      {"source", json::Object{{"artifact_key", std::string(64, 'a')}, {"function_id", nullptr}, {"id", ids[global]}}},
      {"offset", "0"}, {"address_space", 0}, {"allocation", nullptr}}},
      {"guards", json::Array{}}, {"proof", json::Array{}}}}}, {"reason", nullptr}};
  json::Object calleeSource{{"artifact_key", std::string(64, 'a')}, {"function_id", nullptr}, {"id", ids[callee]}};
  json::Object callSource{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[caller]}, {"id", ids[call]}};
  json::Object formalSource{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[callee]},
                            {"id", ids[callee->getArg(0)]}};
  auto *field = &*callee->getEntryBlock().begin();
  json::Object summary{{"kind", "EffectSummary"}, {"context_id", "child"},
    {"root", json::Object{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[callee]},
      {"arguments", json::Array{json::Object{{"kind", "parameter"}, {"source", json::Object(formalSource)},
                                              {"invocation_id", nullptr}}}}}},
    {"returns", json::Array{json::Object{{"source", json::Object{{"artifact_key", std::string(64, 'a')},
      {"function_id", ids[callee]}, {"id", ids[callee->getEntryBlock().getTerminator()]}}}, {"invocation_id", "child-inv"},
      {"value", json::Object{{"kind", "expression"}, {"source", json::Object{{"artifact_key", std::string(64, 'a')},
        {"function_id", ids[callee]}, {"id", ids[field]}}}, {"invocation_id", "child-inv"},
        {"operands", json::Array{json::Object{{"kind", "parameter"}, {"source", json::Object(formalSource)},
          {"invocation_id", "child-inv"}}, json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "4"}}}}}},
      {"guards", json::Array{}}, {"exit", "normal"}}}},
    {"effects", json::Array{}}, {"escape", json::Array{}}, {"status", "complete"}};
  request.getArray("adoptions")->push_back(json::Object{{"call", json::Object(callSource)},
    {"target", json::Object(calleeSource)}, {"kind", "unique-definition"}, {"reason", "exact"}, {"assumptions", json::Array{}}});
  request.getArray("dependencies")->push_back(json::Object{{"context_id", "child"},
    {"digest", moa::analysisDigest(json::Object(summary))}});
  request.getArray("call_bindings")->push_back(json::Object{{"source", json::Object(callSource)},
    {"context_id", "child"}});
  json::Array summaries{json::Object(summary)};
  auto result = moa::evaluationPlan(*module, request, &summaries);
  EXPECT_EQ(result.getString("status"), "complete");
  EXPECT_TRUE(result.getArray("call_requests")->empty());
  ASSERT_EQ(result.getArray("effects")->size(), 1u);
  auto *address = result.getArray("effects")->front().getAsObject()->getObject("address");
  ASSERT_TRUE(address);
  EXPECT_EQ(address->getObject("source")->getString("id"), ids[global]);
  EXPECT_EQ(address->getString("offset"), "4");
  (*request.getArray("dependencies"))[0].getAsObject()->operator[]("digest") = std::string(64, 'e');
  EXPECT_THROW(moa::evaluationPlan(*module, request, &summaries), std::runtime_error);
}

TEST(Effects, EvaluationBoundReturnVariantsRemainConservative) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@object = internal global [32 x i8] zeroinitializer
define ptr @g(ptr %p) { entry: ret ptr %p }
define ptr @f(ptr %p) { entry: %q = call ptr @g(ptr %p)
 ret ptr %q }
)");
  ASSERT_TRUE(module);
  auto base = evaluation(*module, origin());
  auto ids = moa::originalIdentities(*module, std::string(64, 'a'));
  auto *caller = module->getFunction("f"), *callee = module->getFunction("g");
  auto *call = cast<CallBase>(&*caller->getEntryBlock().begin());
  auto *global = module->getGlobalVariable("object", true);
  json::Object callSource{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[caller]}, {"id", ids[call]}};
  json::Object formalSource{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[callee]}, {"id", ids[callee->getArg(0)]}};
  json::Object returnSource{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[callee]},
                            {"id", ids[callee->getEntryBlock().getTerminator()]}};
  auto finite = [](json::Object value) { return json::Object{{"state", "finite"}, {"candidates", json::Array{
    json::Object{{"value", std::move(value)}, {"guards", json::Array{}}, {"proof", json::Array{}}}}}, {"reason", nullptr}}; };
  auto run = [&](json::Object argument, json::Array returns, json::Array effects = {}, json::Array escape = {},
                 StringRef status = "complete", std::optional<json::Array> formals = std::nullopt) {
    auto request = base;
    (*request.getArray("arguments"))[0] = finite(std::move(argument));
    json::Object summary{{"kind", "EffectSummary"}, {"context_id", "child"},
      {"root", json::Object{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[callee]},
        {"arguments", formals ? json::Value(std::move(*formals)) : json::Value(json::Array{
          json::Object{{"kind", "parameter"}, {"source", json::Object(formalSource)}, {"invocation_id", nullptr}}})}}},
      {"returns", std::move(returns)}, {"effects", std::move(effects)}, {"escape", std::move(escape)},
      {"status", status.str()}};
    request.getArray("dependencies")->push_back(json::Object{{"context_id", "child"},
      {"digest", moa::analysisDigest(json::Object(summary))}});
    request.getArray("call_bindings")->push_back(json::Object{{"source", json::Object(callSource)}, {"context_id", "child"}});
    json::Array summaries{json::Object(summary)};
    return moa::evaluationPlan(*module, request, &summaries);
  };
  auto returned = [&](json::Object value, StringRef exit = "normal") { return json::Object{{"source", json::Object(returnSource)},
    {"invocation_id", "child-inv"}, {"value", std::move(value)}, {"guards", json::Array{}}, {"exit", exit.str()}}; };
  auto parameter = [&] { return json::Object{{"kind", "parameter"}, {"source", json::Object(formalSource)},
                                             {"invocation_id", "child-inv"}}; };
  auto object = [&](std::optional<StringRef> offset) {
    json::Object value{{"kind", "object"}, {"source", json::Object(formalSource)}, {"address_space", 0}, {"allocation", nullptr}};
    value["offset"] = offset ? json::Value(offset->str()) : json::Value(nullptr);
    return value;
  };
  json::Object actualGlobal{{"kind", "object"}, {"source", json::Object{{"artifact_key", std::string(64, 'a')},
    {"function_id", nullptr}, {"id", ids[global]}}}, {"offset", "3"}, {"address_space", 0}, {"allocation", nullptr}};

  auto direct = run(json::Object(actualGlobal), json::Array{returned(parameter())});
  EXPECT_EQ(direct.getArray("returns")->front().getAsObject()->getObject("value")->getString("offset"), "3");
  auto zero = run(parameter(), json::Array{returned(object("0"))});
  EXPECT_EQ(zero.getArray("returns")->front().getAsObject()->getObject("value")->getString("kind"), "parameter");
  auto field = run(parameter(), json::Array{returned(object("4"))});
  EXPECT_EQ(field.getArray("returns")->front().getAsObject()->getObject("value")->getString("offset"), "4");
  auto accumulated = run(json::Object(actualGlobal), json::Array{returned(object("4"))});
  EXPECT_EQ(accumulated.getArray("returns")->front().getAsObject()->getObject("value")->getString("offset"), "7");

  auto expectPartial = [&](json::Object result, StringRef code) {
    EXPECT_EQ(result.getString("status"), "partial");
    EXPECT_TRUE(llvm::any_of(*result.getArray("frontier"), [&](const auto &item) {
      return item.getAsObject()->getString("code") == code;
    })) << stringify(json::Object(result));
  };
  expectPartial(run(parameter(), json::Array{returned(object(std::nullopt))}), "callee_return_offset_unknown");
  auto actualWithoutOffset = json::Object(actualGlobal); actualWithoutOffset["offset"] = nullptr;
  expectPartial(run(std::move(actualWithoutOffset), json::Array{returned(object("4"))}), "callee_return_object_unknown");
  expectPartial(run(json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}},
                    json::Array{returned(object("4"))}), "callee_return_object_unknown");
  auto huge = json::Object(actualGlobal); huge["offset"] = "9223372036854775807";
  expectPartial(run(std::move(huge), json::Array{returned(object("1"))}), "callee_return_offset_overflow");
  expectPartial(run(parameter(), json::Array{returned(json::Object{{"kind", "expression"},
    {"source", json::Object(returnSource)}, {"invocation_id", "child-inv"}})}), "callee_return_expression_invalid");
  expectPartial(run(parameter(), json::Array{returned(json::Object{{"kind", "expression"},
    {"source", json::Object(returnSource)}, {"invocation_id", "child-inv"}, {"operands", json::Array{json::Value(nullptr)}}})}),
    "callee_return_expression_invalid");
  expectPartial(run(parameter(), json::Array{}), "callee_has_no_normal_return");
  expectPartial(run(parameter(), json::Array{returned(parameter(), "unwind")}), "callee_has_no_normal_return");

  json::Array mixedReturns{json::Value(nullptr), json::Object{{"source", json::Object(returnSource)},
    {"invocation_id", "child-inv"}, {"value", nullptr}, {"guards", json::Array{}}, {"exit", "normal"}},
    returned(parameter()), returned(parameter())};
  auto joined = run(parameter(), std::move(mixedReturns));
  EXPECT_EQ(joined.getString("status"), "complete");

  auto plainExpression = run(parameter(), json::Array{returned(json::Object{{"kind", "expression"},
    {"source", json::Object(returnSource)}, {"invocation_id", "child-inv"},
    {"operands", json::Array{parameter(), json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}},
                              json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "2"}}}}})});
  EXPECT_EQ(plainExpression.getArray("returns")->front().getAsObject()->getObject("value")->getString("kind"), "expression");

  auto expression = [&](json::Object left, json::Object right) { return json::Object{{"kind", "expression"},
    {"source", json::Object(returnSource)}, {"invocation_id", "child-inv"},
    {"operands", json::Array{std::move(left), std::move(right)}}}; };
  auto baseIsParameter = run(parameter(), json::Array{returned(expression(parameter(),
    json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}}))});
  EXPECT_EQ(baseIsParameter.getArray("returns")->front().getAsObject()->getObject("value")->getString("kind"), "expression");
  auto deltaNotInteger = run(json::Object(actualGlobal), json::Array{returned(expression(parameter(),
    json::Object{{"kind", "null"}, {"address_space", 0}}))});
  EXPECT_EQ(deltaNotInteger.getArray("returns")->front().getAsObject()->getObject("value")->getString("kind"), "expression");
  for (auto delta : {json::Object{{"kind", "integer"}, {"hex", "1"}},
                     json::Object{{"kind", "integer"}, {"bits", 64}},
                     json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "not-hex"}},
                     json::Object{{"kind", "integer"}, {"bits", 65}, {"hex", "1"}}}) {
    auto uncollapsed = run(json::Object(actualGlobal), json::Array{returned(expression(parameter(), std::move(delta)))});
    EXPECT_EQ(uncollapsed.getArray("returns")->front().getAsObject()->getObject("value")->getString("kind"), "expression");
  }
  auto badBase = json::Object(actualGlobal); badBase["offset"] = "not-decimal";
  auto badBaseResult = run(std::move(badBase), json::Array{returned(expression(parameter(),
    json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}}))});
  EXPECT_EQ(badBaseResult.getArray("returns")->front().getAsObject()->getObject("value")->getString("kind"), "expression");
  expectPartial(run(json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}},
    json::Array{returned(expression(object("4"), json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}}))}),
    "callee_return_expression_unknown");

  json::Object harmless{{"kind", "read"}};
  json::Object mutating{{"kind", "write"}};
  auto invalidating = run(parameter(), json::Array{returned(parameter())}, json::Array{json::Object(harmless), json::Object(mutating)},
                          json::Array{parameter()}, "partial");
  expectPartial(std::move(invalidating), "callee_summary_partial");
  for (auto kind : {"rmw", "cas", "unknown"}) {
    auto variant = run(parameter(), json::Array{returned(parameter())},
                       json::Array{json::Object{{"kind", kind}}});
    EXPECT_EQ(variant.getString("status"), "complete");
  }

  auto wrongArity = run(parameter(), json::Array{returned(parameter())}, {}, {}, "complete", json::Array{});
  expectPartial(std::move(wrongArity), "callee_return_binding_mismatch");
  json::Object foreignSource(formalSource); foreignSource["id"] = "foreign-formal";
  auto foreignParameter = json::Object{{"kind", "parameter"}, {"source", json::Object(foreignSource)},
                                       {"invocation_id", "child-inv"}};
  EXPECT_EQ(run(parameter(), json::Array{returned(json::Object(foreignParameter))})
              .getArray("returns")->front().getAsObject()->getObject("value")->getString("kind"), "parameter");
  EXPECT_EQ(run(parameter(), json::Array{returned(json::Object{{"kind", "object"},
      {"source", json::Object(foreignSource)}, {"offset", "0"}, {"address_space", 0}, {"allocation", nullptr}})})
              .getArray("returns")->front().getAsObject()->getObject("value")->getString("kind"), "object");
  for (json::Array formals : {json::Array{json::Value(nullptr)},
                              json::Array{json::Object{{"kind", "integer"}, {"bits", 32}, {"hex", "1"}}},
                              json::Array{json::Object{{"kind", "parameter"}, {"invocation_id", nullptr}}}}) {
    auto unbound = run(parameter(), json::Array{returned(json::Object(foreignParameter))}, {}, {}, "complete",
                       std::move(formals));
    EXPECT_EQ(unbound.getString("status"), "complete");
  }
}

TEST(Effects, EvaluationRejectsMalformedDependencySummariesAndBindings) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64"
define ptr @g(ptr %p) { ret ptr %p }
define ptr @f(ptr %p) { %q = call ptr @g(ptr %p)
 ret ptr %q }
)");
  ASSERT_TRUE(module);
  auto base = evaluation(*module, origin());
  auto ids = moa::originalIdentities(*module, std::string(64, 'a'));
  auto *caller = module->getFunction("f"), *callee = module->getFunction("g");
  auto *call = cast<CallBase>(&*caller->getEntryBlock().begin());
  json::Object source{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[caller]}, {"id", ids[call]}};
  json::Object summary{{"kind", "EffectSummary"}, {"context_id", "child"}, {"root", json::Object{{"arguments", json::Array{}}}},
                       {"returns", json::Array{}}, {"effects", json::Array{}}, {"escape", json::Array{}}, {"status", "complete"}};
  auto rejectsSummary = [&](json::Array summaries) {
    EXPECT_THROW(moa::evaluationPlan(*module, base, &summaries), std::runtime_error);
  };
  rejectsSummary(json::Array{json::Value(nullptr)});
  auto wrongKind = summary; wrongKind["kind"] = "Other"; rejectsSummary(json::Array{json::Object(wrongKind)});
  auto noContext = summary; noContext.erase("context_id"); rejectsSummary(json::Array{json::Object(noContext)});

  auto validRequest = base;
  validRequest.getArray("dependencies")->push_back(json::Object{{"context_id", "child"},
    {"digest", moa::analysisDigest(json::Object(summary))}});
  json::Array summaries{json::Object(summary)};
  for (int mode = 0; mode < 3; ++mode) {
    auto bad = validRequest;
    if (mode == 0) (*bad.getArray("dependencies"))[0] = nullptr;
    if (mode == 1) bad.getArray("dependencies")->front().getAsObject()->erase("context_id");
    if (mode == 2) (*bad.getArray("dependencies"))[0].getAsObject()->operator[]("context_id") = "missing";
    EXPECT_THROW(moa::evaluationPlan(*module, bad, &summaries), std::runtime_error);
  }
  for (int mode = 0; mode < 4; ++mode) {
    auto bad = validRequest;
    bad.getArray("call_bindings")->push_back(json::Object{{"source", json::Object(source)}, {"context_id", "child"}});
    if (mode == 0) (*bad.getArray("call_bindings"))[0] = nullptr;
    if (mode == 1) bad.getArray("call_bindings")->front().getAsObject()->erase("context_id");
    if (mode == 2) bad.getArray("call_bindings")->front().getAsObject()->erase("source");
    if (mode == 3) (*bad.getArray("call_bindings"))[0].getAsObject()->operator[]("context_id") = "missing";
    EXPECT_THROW(moa::evaluationPlan(*module, bad, &summaries), std::runtime_error);
  }
  (void)callee;
}

TEST(Effects, EvaluationConservativeStorageEscapeScalarAndWorkBudgets) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@sink = internal global ptr null
declare void @escape(ptr)
define i32 @f(ptr %p, i32 %x) {
entry:
 %slot = alloca i64
 store i64 1, ptr %slot
 %partial = load i32, ptr %slot
 call void @escape(ptr %p)
 call void @escape(ptr %p)
 store ptr %p, ptr @sink
 %sum = add i32 %x, 1
 ret i32 %sum
}
)");
  ASSERT_TRUE(module);
  auto request = evaluation(*module, origin());
  (*request.getArray("arguments"))[0] = json::Object{{"state", "unknown"}, {"candidates", json::Array{}}, {"reason", "opaque_pointer"}};
  (*request.getArray("arguments"))[1] = json::Object{{"state", "finite"}, {"candidates", json::Array{
    json::Object{{"value", json::Object{{"kind", "integer"}, {"bits", 32}, {"hex", "1"}}}, {"guards", json::Array{}}, {"proof", json::Array{}}},
    json::Object{{"value", json::Object{{"kind", "integer"}, {"bits", 32}, {"hex", "2"}}}, {"guards", json::Array{}}, {"proof", json::Array{}}}}}, {"reason", nullptr}};
  auto result = moa::evaluationPlan(*module, request);
  for (auto code : {"partial_overlap_load", "opaque_pointer", "non_single_scalar_input"})
    EXPECT_TRUE(llvm::any_of(*result.getArray("frontier"), [&](const auto &item) {
      return item.getAsObject()->getString("code") == code;
    })) << code << stringify(json::Object(result));
  EXPECT_TRUE(llvm::any_of(*result.getArray("escape"), [](const auto &item) {
    return item.getAsObject()->getString("kind") == "unknown";
  }));

  auto nonObjectEscape = request;
  (*nonObjectEscape.getArray("arguments"))[0] = json::Object{{"state", "finite"}, {"candidates", json::Array{
    json::Object{{"value", json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}}},
                 {"guards", json::Array{}}, {"proof", json::Array{}}}}}, {"reason", nullptr}};
  auto escapedScalar = moa::evaluationPlan(*module, nonObjectEscape);
  EXPECT_TRUE(llvm::any_of(*escapedScalar.getArray("escape"), [](const auto &item) {
    return item.getAsObject()->getString("kind") == "unknown";
  }));

  auto parameterEscape = request;
  auto callerIds = moa::originalIdentities(*module, std::string(64, 'a'));
  auto *argument = module->getFunction("f")->getArg(0);
  (*parameterEscape.getArray("arguments"))[0] = json::Object{{"state", "finite"}, {"candidates", json::Array{
    json::Object{{"value", json::Object{{"kind", "parameter"}, {"source", json::Object{
      {"artifact_key", std::string(64, 'a')}, {"function_id", callerIds[module->getFunction("f")]}, {"id", callerIds[argument]}}},
      {"invocation_id", nullptr}}}, {"guards", json::Array{}}, {"proof", json::Array{}}}}}, {"reason", nullptr}};
  auto escapedParameter = moa::evaluationPlan(*module, parameterEscape);
  EXPECT_TRUE(llvm::any_of(*escapedParameter.getArray("escape"), [](const auto &item) {
    return item.getAsObject()->getString("kind") == "parameter";
  }));
  auto missingInvocation = parameterEscape;
  (*missingInvocation.getArray("arguments"))[0].getAsObject()->getArray("candidates")->front()
    .getAsObject()->getObject("value")->erase("invocation_id");
  EXPECT_EQ(moa::evaluationPlan(*module, missingInvocation).getString("status"), "partial");
  auto unknownScalar = parameterEscape;
  (*unknownScalar.getArray("arguments"))[1] = json::Object{{"state", "unknown"}, {"candidates", json::Array{}},
                                                           {"reason", "opaque_scalar"}};
  EXPECT_TRUE(llvm::any_of(*moa::evaluationPlan(*module, unknownScalar).getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "opaque_scalar";
  }));
  auto unknownCardinality = parameterEscape;
  unknownCardinality.getArray("invocations")->front().getAsObject()->operator[]("cardinality") = "unknown";
  EXPECT_EQ(moa::evaluationPlan(*module, unknownCardinality).getString("status"), "partial");

  LLVMContext pointerContext;
  auto pointers = parse(pointerContext, R"(
target datalayout = "e-p:64:64"
define ptr @f(ptr %p, i64 %n) {
 %constant = getelementptr i8, ptr %p, i64 4
 %dynamic = getelementptr i8, ptr %p, i64 %n
 ret ptr %constant
}
)");
  ASSERT_TRUE(pointers);
  auto pointerRequest = evaluation(*pointers, origin());
  auto unknownBase = moa::evaluationPlan(*pointers, pointerRequest);
  EXPECT_TRUE(llvm::any_of(*unknownBase.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "dynamic_pointer_offset";
  }));
  (*pointerRequest.getArray("arguments"))[0] = json::Object{{"state", "finite"}, {"candidates", json::Array{
    json::Object{{"value", json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}}},
                 {"guards", json::Array{}}, {"proof", json::Array{}}}}}, {"reason", nullptr}};
  auto wrongBase = moa::evaluationPlan(*pointers, pointerRequest);
  EXPECT_TRUE(llvm::any_of(*wrongBase.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "unsupported_pointer_origin";
  }));

  LLVMContext loopContext;
  auto loop = parse(loopContext, "define void @f() { entry: br label %entry }");
  ASSERT_TRUE(loop);
  auto loopResult = moa::evaluationPlan(*loop, evaluation(*loop, origin()));
  EXPECT_EQ(loopResult.getString("status"), "complete");
  EXPECT_FALSE(llvm::any_of(*loopResult.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "condition_states_budget";
  }));

  LLVMContext cutoffContext;
  auto cutoff = parse(cutoffContext, R"(
target datalayout = "e-p:64:64"
@g = internal global i32 0
define void @f() { entry: store i32 1, ptr @g
 ret void }
)");
  ASSERT_TRUE(cutoff);
  auto tight = evaluation(*cutoff, origin());
  (*tight.getObject("budgets"))["effect_items"] = 0;
  auto stopped = moa::evaluationPlan(*cutoff, tight);
  EXPECT_TRUE(llvm::any_of(*stopped.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "effect_items_budget";
  }));

  LLVMContext chainContext;
  auto chain = parse(chainContext, "define void @f() { a: br label %b\nb: br label %c\nc: br label %d\nd: ret void }");
  ASSERT_TRUE(chain);
  bool observedWorkLimit = false;
  for (int64_t limit = 1; limit <= 6; ++limit) {
    auto bounded = evaluation(*chain, origin());
    (*bounded.getObject("budgets"))["local_steps"] = limit;
    auto limited = moa::evaluationPlan(*chain, bounded);
    observedWorkLimit |= llvm::any_of(*limited.getArray("frontier"), [](const auto &item) {
      return item.getAsObject()->getString("code") == "local_steps_budget";
    });
  }
  EXPECT_TRUE(observedWorkLimit);
}

TEST(Effects, EvaluationModelsNoReturnAndInvokeUnwindConservatively) {
  LLVMContext context;
  auto noreturn = parse(context, R"(
declare void @die() noreturn nounwind
define void @f() { entry: call void @die()
 unreachable }
)");
  ASSERT_TRUE(noreturn);
  auto stopped = moa::evaluationPlan(*noreturn, evaluation(*noreturn, origin()));
  ASSERT_EQ(stopped.getArray("returns")->size(), 1u);
  EXPECT_EQ(stopped.getArray("returns")->front().getAsObject()->getString("exit"), "noreturn");

  LLVMContext second;
  auto invoke = parse(second, R"(
declare void @may()
define void @f() personality ptr null {
entry: invoke void @may() to label %ok unwind label %bad
ok: ret void
bad: %lp = landingpad {ptr, i32} cleanup
 resume {ptr, i32} %lp
})");
  ASSERT_TRUE(invoke);
  auto uncertain = moa::evaluationPlan(*invoke, evaluation(*invoke, origin()));
  EXPECT_EQ(uncertain.getString("status"), "partial");
  EXPECT_TRUE(llvm::any_of(*uncertain.getArray("returns"), [](const auto &item) {
    return item.getAsObject()->getString("exit") == "normal";
  }));
  EXPECT_TRUE(llvm::any_of(*uncertain.getArray("returns"), [](const auto &item) {
    return item.getAsObject()->getString("exit") == "unwind";
  }));
}

TEST(Effects, EvaluationCoversAtomicKindsSelectSwitchIntrinsicsAndMultiplicity) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"
@g = internal global i32 0
declare i32 @returns()
declare i32 @llvm.bswap.i32(i32)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture)
define i32 @f(i1 %c, i32 %x) {
entry:
 %slot = alloca i64
 store volatile i32 %x, ptr %slot
 %volatile = load volatile i32, ptr %slot
 store atomic i32 %x, ptr @g syncscope("singlethread") release, align 4
 %unordered = load atomic i32, ptr @g unordered, align 4
 %rmw = atomicrmw add ptr @g, i32 1 monotonic
 %cas = cmpxchg ptr @g, i32 1, i32 2 acq_rel acquire
 fence syncscope("agent") seq_cst
 %swapped = call i32 @llvm.bswap.i32(i32 %x)
 %selected = select i1 %c, i32 %swapped, i32 %volatile
 switch i32 %selected, label %other [i32 1, label %one]
one:
 call void @llvm.lifetime.end.p0(i64 8, ptr %slot)
 %after = load i32, ptr %slot
 ret i32 %after
other:
 %unknown = call i32 @returns()
 ret i32 %unknown
})");
  ASSERT_TRUE(module);
  auto request = evaluation(*module, origin());
  auto finite = [](unsigned bits, StringRef hex) { return json::Object{{"state", "finite"},
    {"candidates", json::Array{json::Object{{"value", json::Object{{"kind", "integer"}, {"bits", bits}, {"hex", hex.str()}}},
      {"guards", json::Array{}}, {"proof", json::Array{}}}}}, {"reason", nullptr}}; };
  (*request.getArray("arguments"))[0] = finite(1, "1");
  (*request.getArray("arguments"))[1] = finite(32, "1");
  auto result = moa::evaluationPlan(*module, request);
  std::set<std::string> kinds, orders;
  for (const auto &item : *result.getArray("effects")) {
    auto *effect = item.getAsObject(); kinds.insert(effect->getString("kind")->str());
    if (auto order = effect->getString("ordering")) orders.insert(order->str());
  }
  EXPECT_TRUE(kinds.contains("read")); EXPECT_TRUE(kinds.contains("write"));
  EXPECT_TRUE(kinds.contains("rmw")); EXPECT_TRUE(kinds.contains("cas")); EXPECT_TRUE(kinds.contains("fence"));
  EXPECT_TRUE(orders.contains("unordered")); EXPECT_TRUE(orders.contains("monotonic"));
  EXPECT_TRUE(orders.contains("release")); EXPECT_TRUE(orders.contains("acq_rel")); EXPECT_TRUE(orders.contains("seq_cst"));
  EXPECT_TRUE(llvm::any_of(*result.getArray("effects"), [](const auto &item) {
    return item.getAsObject()->getString("syncscope") == "singlethread";
  }));
  EXPECT_TRUE(llvm::any_of(*result.getArray("effects"), [](const auto &item) {
    return item.getAsObject()->getString("syncscope") == "agent";
  }));
  EXPECT_TRUE(llvm::any_of(*result.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "uninitialized_load";
  }));

  auto merged = request;
  auto *activation = (*merged.getArray("invocations"))[0].getAsObject();
  (*activation)["cardinality"] = "merged"; (*activation)["reason"] = "recursive-scc";
  auto abstract = moa::evaluationPlan(*module, merged);
  EXPECT_TRUE(llvm::any_of(*abstract.getArray("effects"), [](const auto &item) {
    return item.getAsObject()->getString("multiplicity") == "unknown";
  }));
  auto limited = request; (*limited.getObject("budgets"))["effect_items"] = 1;
  auto cut = moa::evaluationPlan(*module, limited);
  EXPECT_TRUE(llvm::any_of(*cut.getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "effect_items_budget";
  }));
}

TEST(Effects, EvaluationCoversMalformedDomainsPartialRangesAndMissingLayout) {
  LLVMContext context;
  auto module = parse(context, R"(
define i16 @f(i64 %x, i64 %n) {
entry:
 %slot = alloca i64
 %dynamic = getelementptr i8, ptr %slot, i64 %n
 store i64 %x, ptr %slot
 %partial = getelementptr i8, ptr %slot, i64 1
 %short = load i16, ptr %partial
 store i16 %short, ptr %dynamic
 ret i16 %short
})");
  ASSERT_TRUE(module);
  auto request = evaluation(*module, origin());
  (*request.getArray("arguments"))[0] = nullptr;
  (*request.getArray("arguments"))[1] = json::Object{{"state", "finite"}, {"candidates", json::Array{}}, {"reason", nullptr}};
  auto malformed = moa::evaluationPlan(*module, request);
  EXPECT_EQ(malformed.getString("status"), "partial");
  EXPECT_TRUE(llvm::any_of(*malformed.getArray("frontier"), [](const auto &item) {
    auto code = item.getAsObject()->getString("code"); return code == "unknown_argument" || code == "empty_argument_domain";
  }));
  auto candidate = request;
  (*candidate.getArray("arguments"))[0] = json::Object{{"state", "finite"}, {"candidates", json::Array{nullptr}}, {"reason", nullptr}};
  (*candidate.getArray("arguments"))[1] = json::Object{{"state", "finite"}, {"candidates", json::Array{
    json::Object{{"value", json::Object{{"kind", "integer"}, {"bits", 64}, {"hex", "1"}}}}}}, {"reason", nullptr}};
  EXPECT_EQ(moa::evaluationPlan(*module, candidate).getString("status"), "partial");
  LLVMContext second;
  auto shortBudget = parse(second, "define void @f(){entry: br label %exit\nexit: ret void}");
  ASSERT_TRUE(shortBudget);
  auto tight = evaluation(*shortBudget, origin()); (*tight.getObject("budgets"))["local_steps"] = 1;
  EXPECT_TRUE(llvm::any_of(*moa::evaluationPlan(*shortBudget, tight).getArray("frontier"), [](const auto &item) {
    return item.getAsObject()->getString("code") == "local_steps_budget";
  }));
}

TEST(Effects, EvaluationCoversPointerScalarLifetimeAndExitTransferVariants) {
  auto finite = [](json::Object value) { return json::Object{{"state", "finite"},
    {"candidates", json::Array{json::Object{{"value", std::move(value)}, {"guards", json::Array{}},
                                            {"proof", json::Array{}}}}}, {"reason", nullptr}}; };
  {
    LLVMContext context;
    auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
define ptr @f(ptr %p) { entry: %field = getelementptr i8, ptr %p, i64 4
 ret ptr %field }
)");
    ASSERT_TRUE(module);
    auto ids = moa::originalIdentities(*module, std::string(64, 'a'));
    auto *function = module->getFunction("f");
    auto request = evaluation(*module, origin());
    (*request.getArray("arguments"))[0] = finite(json::Object{{"kind", "parameter"},
      {"source", json::Object{{"artifact_key", std::string(64, 'a')}, {"function_id", ids[function]},
                               {"id", ids[function->getArg(0)]}}}, {"invocation_id", nullptr}});
    auto symbolic = moa::evaluationPlan(*module, request);
    auto *returned = symbolic.getArray("returns")->front().getAsObject()->getObject("value");
    ASSERT_TRUE(returned); EXPECT_EQ(returned->getString("kind"), "expression");
    EXPECT_EQ(returned->getArray("operands")->back().getAsObject()->getString("hex"), "4");
  }
  {
    LLVMContext context;
    auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
@g = internal global [16 x i8] zeroinitializer
define ptr @f(ptr %p) { entry: %a = getelementptr i8, ptr %p, i64 4
 %b = getelementptr i8, ptr %a, i64 4
 ret ptr %b }
)");
    ASSERT_TRUE(module);
    auto ids = moa::originalIdentities(*module, std::string(64, 'a'));
    auto request = evaluation(*module, origin());
    (*request.getArray("arguments"))[0] = finite(json::Object{{"kind", "object"},
      {"source", json::Object{{"artifact_key", std::string(64, 'a')}, {"function_id", nullptr},
                               {"id", ids[module->getGlobalVariable("g", true)]}}},
      {"offset", "0"}, {"address_space", 0}, {"allocation", nullptr}});
    auto concrete = moa::evaluationPlan(*module, request);
    EXPECT_EQ(concrete.getArray("returns")->front().getAsObject()->getObject("value")->getString("offset"), "8");
  }
  {
    LLVMContext context;
    auto module = parse(context, "define i32 @f(i32 %x){entry:%sum=add i32 %x,1\nret i32 %sum}");
    ASSERT_TRUE(module);
    auto request = evaluation(*module, origin());
    (*request.getArray("arguments"))[0] = finite(json::Object{{"kind", "integer"}, {"bits", 32}, {"hex", "2"}});
    auto result = moa::evaluationPlan(*module, request);
    EXPECT_EQ(result.getArray("returns")->front().getAsObject()->getObject("value")->getString("hex"), "3");
  }
  for (const char *constant : {"null", "poison", "undef"}) {
    LLVMContext context;
    std::string ir = std::string("define ptr @f(){entry:ret ptr ") + constant + "}";
    auto module = parse(context, ir.c_str()); ASSERT_TRUE(module);
    EXPECT_EQ(moa::evaluationPlan(*module, evaluation(*module, origin())).getString("status"), "complete");
  }
  {
    LLVMContext context;
    auto module = parse(context, R"(
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture)
define void @f() { entry: %slot=alloca i32
 call void @llvm.lifetime.start.p0(i64 4, ptr %slot)
 call void @llvm.lifetime.end.p0(i64 4, ptr %slot)
 unreachable }
)");
    ASSERT_TRUE(module);
    auto result = moa::evaluationPlan(*module, evaluation(*module, origin()));
    EXPECT_EQ(result.getString("status"), "complete");
    EXPECT_EQ(result.getArray("returns")->front().getAsObject()->getString("exit"), "noreturn");
  }
  {
    LLVMContext context;
    auto module = parse(context, R"(
declare void @safe() nounwind
define void @f() personality ptr null {entry: invoke void @safe() to label %ok unwind label %bad
ok: ret void
bad: %lp=landingpad {ptr,i32} cleanup
resume {ptr,i32} %lp}
)");
    ASSERT_TRUE(module);
    auto result = moa::evaluationPlan(*module, evaluation(*module, origin()));
    EXPECT_FALSE(llvm::any_of(*result.getArray("returns"), [](const auto &item) {
      return item.getAsObject()->getString("exit") == "unwind";
    }));
  }
  {
    LLVMContext context;
    auto module = parse(context, R"(
define void @f(ptr %target) personality ptr null {entry: invoke void %target() to label %ok unwind label %bad
ok: ret void
bad: %lp=landingpad {ptr,i32} cleanup
resume {ptr,i32} %lp}
)");
    ASSERT_TRUE(module);
    auto result = moa::evaluationPlan(*module, evaluation(*module, origin()));
    EXPECT_TRUE(llvm::any_of(*result.getArray("returns"), [](const auto &item) {
      return item.getAsObject()->getString("exit") == "unwind";
    }));
  }
}

TEST(Effects, EvaluationRejectsMalformedEnvelopesAndConsumedFields) {
  LLVMContext context;
  auto module = parse(context, "define void @f() {ret void}");
  ASSERT_TRUE(module);
  auto request = evaluation(*module, origin());
  auto envelope = evaluationEnvelope("unused.bc", request);
  for (auto field : {"protocol", "jobs"}) {
    auto bad = envelope; bad.erase(field);
    EXPECT_THROW(moa::evaluationBatch(bad), std::runtime_error);
  }
  std::vector<std::function<void(json::Object &)>> mutations{
    [](auto &r) { r["jobs"] = json::Array{}; },
    [](auto &r) { r["protocol"] = nullptr; },
    [](auto &r) { (*r.getObject("protocol"))["policy_id"] = "old"; },
    [](auto &r) { r["jobs"] = json::Array{nullptr}; },
    [](auto &r) { (*r.getArray("jobs"))[0].getAsObject()->erase("path"); },
    [](auto &r) { (*(*r.getArray("jobs"))[0].getAsObject())["path"] = 1; },
    [](auto &r) { (*(*r.getArray("jobs"))[0].getAsObject())["id"] = false; },
    [](auto &r) { (*(*r.getArray("jobs"))[0].getAsObject())["request"] = nullptr; }};
  for (auto &mutate : mutations) { auto bad = envelope; mutate(bad); EXPECT_THROW(moa::evaluationBatch(bad), std::runtime_error); }
  for (auto field : {"schema_version", "kind", "analysis_version", "policy_id", "arguments", "invocations", "origins",
                     "local_dependencies", "dependencies", "adoptions", "call_bindings", "budgets", "function", "context_id", "invocation_id", "scope_id"}) {
    auto bad = request; bad[field] = nullptr;
    EXPECT_THROW(moa::evaluationBatch(evaluationEnvelope("unused.bc", bad)), std::runtime_error) << field;
  }
  std::vector<std::function<void(json::Object &)>> fields{
    [](auto &r) { r["extra"] = true; }, [](auto &r) { r["context_id"] = ""; }, [](auto &r) { r["invocation_id"] = ""; },
    [](auto &r) { r["invocations"] = json::Array{}; }, [](auto &r) { r["origins"] = json::Array{}; },
    [](auto &r) { r["origins"] = json::Array{1}; },
    [](auto &r) { r.getArray("origins")->push_back((*r.getArray("origins"))[0]); },
    [](auto &r) { (*r.getObject("function"))["artifact_key"] = "bad"; },
    [](auto &r) { (*r.getObject("function"))["function_id"] = "foreign"; },
    [](auto &r) { r.getObject("function")->erase("function_id"); },
    [](auto &r) { (*r.getObject("function"))["id"] = nullptr; }};
  for (auto &mutate : fields) { auto bad = request; mutate(bad); EXPECT_THROW(moa::evaluationBatch(evaluationEnvelope("unused.bc", bad)), std::runtime_error); }
  auto tight = request; (*tight.getObject("budgets"))["contexts_per_request"] = 1;
  auto duplicate = evaluationEnvelope("unused.bc", tight);
  auto second = *(*duplicate.getArray("jobs"))[0].getAsObject(); second["id"] = "second";
  duplicate.getArray("jobs")->push_back(std::move(second));
  EXPECT_THROW(moa::evaluationBatch(duplicate), std::runtime_error);
}

TEST(Effects, EvaluationIdentityAndTreeFailuresPreserveJob) {
  LLVMContext context;
  auto module = parse(context, "declare void @decl()\ndefine void @f(i32 %x) {ret void}");
  ASSERT_TRUE(module);
  Temp bc; bc.bc(*module);
  auto bytes = MemoryBuffer::getFile(bc.path); ASSERT_TRUE(bytes);
  auto input = origin(); input["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef((*bytes)->getBuffer())), true);
  auto request = evaluation(*module, input);
  std::vector<std::function<void(json::Object &)>> mutations{
    [](auto &r) { r["local_dependencies"] = json::Array{}; },
    [](auto &r) { r["local_dependencies"] = json::Array{1}; },
    [](auto &r) { r.getArray("local_dependencies")->push_back((*r.getArray("local_dependencies"))[0]); },
    [](auto &r) { (*(*r.getArray("local_dependencies"))[0].getAsObject())["artifact_key"] = std::string(64, 'e'); },
    [](auto &r) { (*r.getObject("function"))["id"] = "missing"; },
    [](auto &r) { (*r.getObject("function"))["id"] = std::string(64, 'a') + ":symbol:decl"; },
    [](auto &r) { r["arguments"] = json::Array{}; },
    [](auto &r) { r["invocations"] = json::Array{1}; },
    [](auto &r) { (*(*r.getArray("invocations"))[0].getAsObject())["id"] = 1; },
    [](auto &r) { (*(*r.getArray("invocations"))[0].getAsObject())["id"] = "foreign"; },
    [](auto &r) { (*(*r.getArray("invocations"))[0].getAsObject())["context_id"] = "other"; },
    [](auto &r) { (*(*r.getArray("invocations"))[0].getAsObject())["function"] = nullptr; },
    [](auto &r) { r.getArray("invocations")->push_back((*r.getArray("invocations"))[0]); }};
  for (auto &mutate : mutations) {
    auto bad = request; mutate(bad);
    auto result = moa::evaluationBatch(evaluationEnvelope(bc.path.str().str(), bad));
    auto &entry = *(*result.getArray("results"))[0].getAsObject();
    EXPECT_TRUE(entry.get("result")->getAsNull()); ASSERT_TRUE(entry.getObject("error"));
  }
  for (auto kind : {"integer", "object", "parameter", "null", "poison", "undef", "freeze", "expression", "unknown"}) {
    auto bounded = request;
    (*bounded.getArray("arguments"))[0] = json::Object{{"kind", kind}};
    // C++ transport traverses payload safely; full Value schema is a client boundary.
    auto result = moa::evaluationBatch(evaluationEnvelope(bc.path.str().str(), bounded));
    EXPECT_TRUE((*result.getArray("results"))[0].getAsObject()->getObject("result"));
  }
  for (bool values : {false, true}) {
    auto deep = request;
    json::Value nested = json::Object{{"kind", "unknown"}, {"reason", "leaf"}};
    for (unsigned i = 0; i < (values ? 65 : 260); ++i)
      nested = values ? json::Object{{"kind", "expression"}, {"operands", json::Array{std::move(nested)}}} :
                        json::Object{{"nested", std::move(nested)}};
    (*deep.getArray("arguments"))[0] = std::move(nested);
    auto result = moa::evaluationBatch(evaluationEnvelope(bc.path.str().str(), deep));
    EXPECT_EQ((*result.getArray("results"))[0].getAsObject()->getObject("error")->getString("code"), "evaluation_budget");
  }
}

TEST(Effects, ExactMetadataAndOriginalFactsUnchanged) {
  LLVMContext context;
  auto module = parse(context, R"(
target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-p:64:64"
$a = comdat any
$b = comdat exactmatch
$c = comdat largest
$d = comdat nodeduplicate
$e = comdat samesize
define dso_local void @strong() { ret void }
define available_externally void @available() { ret void }
define linkonce void @once() { ret void }
define linkonce_odr void @odr() comdat($a) { ret void }
define weak void @weak() comdat($b) { ret void }
define weak_odr void @weakodr() comdat($c) { ret void }
define internal void @internal() { ret void }
define private void @private() { ret void }
declare extern_weak void @externalweak()
define hidden void @hidden() comdat($d) { ret void }
define protected void @protected() comdat($e) { ret void }
)");
  ASSERT_TRUE(module);
  auto input = origin();
  auto raw = moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'));
  std::string before; raw_string_ostream ir(before); module->print(ir, nullptr);
  auto facts = moa::localMetadata(*module, input, budgets());
  auto &functions = *facts.getArray("functions");
  const char *expected[] = {"external", "available_externally", "linkonce", "linkonce_odr", "weak", "weak_odr", "internal", "private", "extern_weak", "external", "external"};
  unsigned i = 0;
  for (auto &function : *module) {
    auto &item = *functions[i].getAsObject();
    EXPECT_EQ(item.getString("linkage"), expected[i++]);
    EXPECT_EQ(item.getBoolean("exact_definition"), function.hasExactDefinition());
    EXPECT_EQ(item.getBoolean("interposable"), function.isInterposable());
    EXPECT_EQ(item.getBoolean("dso_local"), function.isDSOLocal());
    EXPECT_EQ(item.getBoolean("declaration"), function.isDeclaration());
    EXPECT_EQ(item.getObject("source")->getString("id"), moa::symbolId(function, std::string(64, 'a')));
    EXPECT_EQ(bool(item.getString("body_fingerprint")), !function.isDeclaration());
  }
  EXPECT_EQ(functions[3].getAsObject()->getString("selection"), "any");
  EXPECT_EQ(functions[9].getAsObject()->getString("visibility"), "hidden");
  EXPECT_EQ(functions[10].getAsObject()->getString("visibility"), "protected");
  EXPECT_EQ(facts.getString("status"), "partial");
  EXPECT_FALSE(facts.getArray("diagnostics")->empty());
  EXPECT_EQ(json::Value(json::Object(facts)), json::Value(moa::localMetadata(*module, input, budgets())));
  EXPECT_EQ(json::Value(std::move(raw)), json::Value(moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'))));
  std::string after; raw_string_ostream printed(after); module->print(printed, nullptr);
  EXPECT_EQ(before, after);
}

TEST(Effects, NormalizedBodyFingerprintMatchesEquivalentOdrCopies) {
  LLVMContext context;
  auto module = parse(context, R"(
$a = comdat any
$b = comdat any
$c = comdat any
define linkonce_odr i32 @a(i32 %left) comdat($a) { %r = add i32 %left, 1
 ret i32 %r }
define linkonce_odr i32 @b(i32 %right) comdat($b) { %value = add i32 %right, 1
 ret i32 %value }
define linkonce_odr i32 @c(i32 %right) comdat($c) { %value = add i32 %right, 2
 ret i32 %value }
)");
  ASSERT_TRUE(module);
  auto facts = moa::localMetadata(*module, origin(), budgets());
  auto functions = facts.getArray("functions");
  ASSERT_EQ(functions->size(), 3u);
  EXPECT_EQ((*functions)[0].getAsObject()->getString("body_fingerprint"),
            (*functions)[1].getAsObject()->getString("body_fingerprint"));
  EXPECT_NE((*functions)[0].getAsObject()->getString("body_fingerprint"),
            (*functions)[2].getAsObject()->getString("body_fingerprint"));

  LLVMContext leftContext, rightContext;
  auto left = parse(leftContext, R"(
@private_object = internal global i32 1
$f = comdat any
define linkonce_odr ptr @f() comdat($f) { ret ptr @private_object }
)");
  auto right = parse(rightContext, R"(
@private_object = internal global i32 1
$f = comdat any
define linkonce_odr ptr @f() comdat($f) { ret ptr @private_object }
)");
  ASSERT_TRUE(left); ASSERT_TRUE(right);
  auto leftFacts = moa::localMetadata(*left, origin(), budgets());
  auto rightOrigin = origin(); rightOrigin["artifact_key"] = std::string(64, 'e');
  auto rightFacts = moa::localMetadata(*right, rightOrigin, budgets());
  EXPECT_NE(leftFacts.getArray("functions")->front().getAsObject()->getString("body_fingerprint"),
            rightFacts.getArray("functions")->front().getAsObject()->getString("body_fingerprint"));
}

TEST(Effects, AbiClassificationAndCallInterfaces) {
  LLVMContext context;
  auto module = parse(context, R"(
declare noundef i32 @good(ptr noundef nonnull align 4 dereferenceable(4), i32 noundef) nounwind readonly
declare void @vararg(i32, ...)
declare float @floatreturn()
declare void @floatarg(float)
declare fastcc void @fast()
declare void @byval(ptr byval(i32))
declare void @sret(ptr sret(i32))
declare void @inalloca(ptr inalloca(i32))
declare void @preallocated(ptr preallocated(i32))
declare void @unknown() "future-abi"="yes"
declare void @codegen() noinline optnone "target-cpu"="generic"
declare void @die() noreturn nounwind
declare i32 @personality(...)
define i32 @caller(ptr %p, ptr %fp) personality ptr @personality {
entry:
  %a = call noundef i32 @good(ptr noundef %p, i32 noundef 1) nounwind
  %b = tail call i32 @good(ptr %p, i32 2)
  call void %fp()
  call void @codegen() [ "deopt"(i32 1) ]
  %c = invoke i32 @good(ptr %p, i32 3) to label %ok unwind label %error
ok: ret i32 %c
error:
  %lp = landingpad {ptr, i32} cleanup
  resume {ptr, i32} %lp
}
define i32 @tailer(ptr %p, i32 %n) {
  %v = musttail call i32 @good(ptr %p, i32 %n)
  ret i32 %v
}
declare void @spoof() "nounwind"="yes"
)");
  ASSERT_TRUE(module);
  auto facts = moa::localMetadata(*module, origin(), budgets());
  auto &functions = *facts.getArray("functions");
  EXPECT_EQ(functions[0].getAsObject()->getObject("interface")->getString("status"), "supported");
  bool modeled = false, ignored = false;
  for (auto &attr : *functions[0].getAsObject()->getObject("interface")->getArray("attributes")) {
    modeled |= attr.getAsObject()->getString("status") == "modeled";
    ignored |= attr.getAsObject()->getString("status") == "conservatively-ignored";
  }
  EXPECT_TRUE(modeled && ignored);
  for (unsigned i = 1; i <= 9; ++i)
    EXPECT_EQ(functions[i].getAsObject()->getObject("interface")->getString("status"), "unsupported");
  EXPECT_EQ(functions[10].getAsObject()->getObject("interface")->getString("status"), "supported");
  EXPECT_TRUE(*functions[11].getAsObject()->getObject("interface")->getBoolean("noreturn"));
  auto &calls = *facts.getArray("calls");
  ASSERT_EQ(calls.size(), 6u);
  EXPECT_EQ(calls[0].getAsObject()->getObject("interface")->getString("status"), "supported");
  EXPECT_EQ(calls[1].getAsObject()->getString("tail"), "tail");
  EXPECT_TRUE(calls[2].getAsObject()->get("target")->getAsNull());
  EXPECT_EQ(calls[3].getAsObject()->getObject("interface")->getString("status"), "unsupported");
  EXPECT_EQ(calls[4].getAsObject()->getString("tail"), "none");
  EXPECT_EQ(calls[5].getAsObject()->getString("tail"), "musttail");
  EXPECT_EQ(calls[5].getAsObject()->getObject("interface")->getString("status"), "unsupported");
  auto *spoof = functions.back().getAsObject()->getObject("interface");
  EXPECT_EQ(spoof->getString("status"), "unsupported");
  EXPECT_FALSE(*spoof->getBoolean("nounwind"));
}

TEST(Effects, BatchReadsBitcodeAndReportsIndividualFailures) {
  LLVMContext context;
  auto module = parse(context, "define void @f() { ret void }");
  ASSERT_TRUE(module);
  Temp input; input.bc(*module);
  auto info = origin();
  info["module_hash"] = moa::read(input.path.str().str(), std::string(64, 'a')).getString("module_hash")->str();
  auto request = batch(input.path.str().str(), info);
  auto other = *(*request.getArray("jobs"))[0].getAsObject();
  other["id"] = "missing"; other["path"] = "/missing-bc";
  request.getArray("jobs")->push_back(std::move(other));
  auto result = moa::localBatch(request);
  EXPECT_TRUE((*result.getArray("results"))[0].getAsObject()->getObject("result"));
  EXPECT_EQ((*result.getArray("results"))[1].getAsObject()->getObject("error")->getString("code"), "input_unreadable");
  auto mismatch = batch(input.path.str().str());
  EXPECT_EQ((*moa::localBatch(mismatch).getArray("results"))[0].getAsObject()->getObject("error")->getString("code"), "inputs_changed");
  for (const auto &bytes : {std::string("text"), std::string("BC\xc0\xde", 4)}) {
    input.text(bytes);
    // Derive the hash without requiring a valid bitcode parse.
    auto hash = SHA256::hash(arrayRefFromStringRef(bytes));
    auto badInfo = origin(); badInfo["module_hash"] = toHex(hash, true);
    auto response = moa::localBatch(batch(input.path.str().str(), badInfo));
    EXPECT_TRUE((*response.getArray("results"))[0].getAsObject()->getObject("error"));
  }
  auto *ret = module->getFunction("f")->front().getTerminator(); ret->eraseFromParent();
  IRBuilder<> builder(&module->getFunction("f")->front()); builder.CreateRet(builder.getInt32(1));
  input.bc(*module);
  auto bytes = MemoryBuffer::getFile(input.path); ASSERT_TRUE(bytes);
  info["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef((*bytes)->getBuffer())), true);
  EXPECT_EQ((*moa::localBatch(batch(input.path.str().str(), info)).getArray("results"))[0].getAsObject()->getObject("error")->getString("code"), "verify_failed");
}

TEST(Effects, BatchRejectsMalformedProtocolJobsAndBudgets) {
  auto valid = batch("/missing-bc");
  const std::vector<std::function<void(json::Object &)>> invalid = {
    [](auto &v) { v["extra"] = true; }, [](auto &v) { v.erase("protocol"); },
    [](auto &v) { (*v.getObject("protocol"))["policy_id"] = "future"; },
    [](auto &v) { v.erase("jobs"); }, [](auto &v) { v["jobs"] = json::Array{}; },
    [](auto &v) { v["jobs"] = json::Array{nullptr}; },
    [](auto &v) { v["jobs"] = json::Array{json::Object{}}; },
    [](auto &v) { v.getArray("jobs")->push_back((*v.getArray("jobs"))[0]); },
  };
  for (auto &mutate : invalid) { auto value = valid; mutate(value); EXPECT_THROW(moa::localBatch(value), std::runtime_error); }
  auto many = valid; while (many.getArray("jobs")->size() <= 4096) many.getArray("jobs")->push_back(nullptr);
  EXPECT_THROW(moa::localBatch(many), std::runtime_error);
  for (auto field : {"id", "path", "origin", "budgets"}) {
    auto value = valid; (*(*value.getArray("jobs"))[0].getAsObject())[field] = nullptr;
    EXPECT_THROW(moa::localBatch(value), std::runtime_error);
  }
  for (auto field : {"id", "path"}) {
    auto value = valid; (*(*value.getArray("jobs"))[0].getAsObject())[field] = "";
    EXPECT_THROW(moa::localBatch(value), std::runtime_error);
  }
  for (auto field : {"artifact_key", "module_hash", "facts_hash", "extractor_version", "llvm_version", "profile"}) {
    for (auto bad : {std::string("bad"), std::string(64, 'z')}) {
      auto value = valid; (*(*value.getArray("jobs"))[0].getAsObject()->getObject("origin"))[field] = bad;
      EXPECT_THROW(moa::localBatch(value), std::runtime_error);
    }
  }
  auto limit = budgets();
  for (auto &field : limit) for (auto bad : {int64_t(0), *field.second.getAsInteger() + 1}) {
    auto value = valid; (*(*value.getArray("jobs"))[0].getAsObject()->getObject("budgets"))[field.first] = bad;
    EXPECT_THROW(moa::localBatch(value), std::runtime_error);
  }
  auto tight = valid; (*(*tight.getArray("jobs"))[0].getAsObject()->getObject("budgets"))["worker_output_bytes"] = 1;
  EXPECT_THROW(moa::localBatch(tight), std::runtime_error);
  for (auto profile : {"build-faithful", "imported", "linked"}) {
    auto value = valid; (*(*value.getArray("jobs"))[0].getAsObject()->getObject("origin"))["profile"] = profile;
    EXPECT_NO_THROW(moa::localBatch(value));
  }
}

TEST(Effects, WorkerProtocolAndJsonLogSeparation) {
  Temp request;
  request.text(stringify(batch("/missing-bc")));
  std::string output, error; raw_string_ostream out(output), err(error);
  const char *args[] = {"worker", "--local-batch", request.path.c_str()};
  EXPECT_EQ(moa::worker(3, args, out, err), 0);
  EXPECT_TRUE(bool(json::parse(output))); EXPECT_TRUE(error.empty());
  for (const auto &bad : {std::string("bad"), std::string("null"), std::string("{}"), std::string(16777217, ' ')}) {
    request.text(bad); output.clear(); error.clear();
    EXPECT_EQ(moa::worker(3, args, out, err), 1);
    auto parsed = json::parse(output); ASSERT_TRUE(bool(parsed));
    EXPECT_TRUE(parsed->getAsObject()->getObject("error")); EXPECT_FALSE(error.empty());
  }
  output.clear(); error.clear();
  const char *protocol[] = {"worker", "--analysis-protocol"};
  EXPECT_EQ(moa::worker(2, protocol, out, err), 0);
  EXPECT_EQ(*json::parse(output), json::Value(moa::analysisProtocol()));
}

TEST(Effects, RegisteredInstructionDoesNotNecessarilyHaveAP1ValueNode) {
  LLVMContext context;
  auto module = parse(context, "define void @f() { %unused = alloca i32\n ret void }");
  ASSERT_TRUE(module);
  const std::string key(64, 'a');
  auto ids = moa::originalIdentities(*module, key);
  auto &allocation = module->getFunction("f")->front().front();
  EXPECT_EQ(ids.lookup(&allocation), key + ":symbol:f:b0:i0");
  auto raw = moa::extract(*module, key, std::string(64, 'b'));
  EXPECT_TRUE(raw.getArray("values")->empty());
  EXPECT_TRUE(raw.getArray("events")->empty());
  auto local = moa::localMetadata(*module, origin(), budgets());
  ASSERT_EQ(local.getArray("ir_nodes")->size(), 2u);
  ASSERT_EQ(local.getArray("objects")->size(), 1u);
  auto *object = local.getArray("objects")->front().getAsObject();
  EXPECT_EQ(object->getObject("source")->getString("id"), ids.lookup(&allocation));
  EXPECT_EQ(object->getString("reason"), "missing_data_layout");
  EXPECT_EQ(object->getBoolean("private"), true);
  EXPECT_EQ(stringify(raw), stringify(moa::extract(*module, key, std::string(64, 'b'))));
  EXPECT_EQ(raw.getArray("functions")->size(), 1u);
  EXPECT_EQ(raw.getInteger("schema_version"), 2);
}

TEST(Effects, LocalQueriesPreservePhiBackedgesAndAliasCandidates) {
  LLVMContext context;
  auto module = parse(context, R"(
target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"
declare void @escape(ptr)
define i32 @f(i1 %c, i64 %n, ptr %p) noinline optnone {
entry:
 %unused = alloca i32
 %slot = alloca i32
 %dynamic = alloca i8, i64 %n
 %escaped = alloca i32
 store i32 7, ptr %slot
 call void @escape(ptr %escaped)
 br i1 %c, label %left, label %right
left:
 store i32 1, ptr %p
 br label %loop
right:
 store i32 2, ptr %p
 br label %loop
loop:
 %v = load i32, ptr %p
 store i32 %v, ptr %p
 br i1 %c, label %loop, label %exit
exit:
 %local = load i32, ptr %slot
 ret i32 %local
dead:
 ret i32 0
}
define void @scalable() {
 %s = alloca <vscale x 4 x i32>
 call void @escape(ptr %s)
 ret void
}
)");
  ASSERT_TRUE(module);
  auto before = stringify(moa::extract(*module, std::string(64, 'a'), std::string(64, 'b')));
  auto local = moa::localMetadata(*module, origin(), budgets());
  EXPECT_EQ(stringify(local), stringify(moa::localMetadata(*module, origin(), budgets())));
  EXPECT_EQ(before, stringify(moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'))));
  auto *objects = local.getArray("objects"); ASSERT_EQ(objects->size(), 5u);
  EXPECT_EQ((*objects)[0].getAsObject()->getString("size_bytes"), "4");
  EXPECT_EQ((*objects)[1].getAsObject()->getBoolean("private"), true);
  EXPECT_EQ((*objects)[2].getAsObject()->getString("reason"), "dynamic_or_scalable_allocation");
  EXPECT_EQ((*objects)[3].getAsObject()->getString("reason"), "not_promotable");
  EXPECT_EQ((*objects)[4].getAsObject()->getString("reason"), "dynamic_or_scalable_allocation;not_promotable");
  std::map<std::string, const json::Object *> table;
  for (auto &item : *local.getArray("analysis_evidence")) {
    auto *entry = item.getAsObject();
    auto id = entry->getObject("ref")->getString("analysis_id")->str();
    EXPECT_TRUE(table.emplace(id, entry).second);
    EXPECT_NE(id.find(":p2:"), std::string::npos);
  }
  bool phiSeen = false, backedge = false, dead = false, aaSkippedOtherObject = false;
  for (auto &[id, entry] : table) {
    auto kind = *entry->getString("kind");
    for (auto &input : *entry->getArray("inputs")) if (auto ref = input.getAsObject()->getString("analysis_id"))
      EXPECT_TRUE(table.contains(ref->str()));
    if (kind == "dominance" && entry->getString("result") == "unreachable") {
      dead = true; EXPECT_TRUE(entry->getArray("inputs")->empty());
    }
    if (kind == "memory_phi") {
      phiSeen = true;
      auto *inputs = entry->getArray("inputs"); EXPECT_EQ(inputs->size(), 6u);
      for (unsigned i = 0; i < inputs->size(); i += 2) if ((*inputs)[i] == json::Value(json::Object(*entry->getObject("source")))) {
        auto incoming = (*inputs)[i + 1].getAsObject()->getString("analysis_id")->str();
        auto *definition = table.at(incoming);
        backedge = definition->getString("kind") == "memory_def" &&
          definition->getArray("inputs")->front().getAsObject()->getString("analysis_id") == id;
      }
    }
    if (kind == "aa_clobber" && entry->getObject("source")->getString("id")->ends_with(":b4:i0")) {
      auto ref = (*entry->getArray("inputs"))[1].getAsObject()->getString("analysis_id")->str();
      aaSkippedOtherObject = table.at(ref)->getObject("source")->getString("id")->ends_with(":b0:i4");
    }
    if (kind != "dominance") EXPECT_EQ(entry->getString("result"), "candidate");
  }
  EXPECT_TRUE(phiSeen); EXPECT_TRUE(backedge); EXPECT_TRUE(dead); EXPECT_TRUE(aaSkippedOtherObject);
}

TEST(Effects, RegistryBudgetFailureIsAnExplicitJobError) {
  LLVMContext context;
  auto module = parse(context, "define void @f() { %unused = alloca i32\n ret void }"); ASSERT_TRUE(module);
  auto limit = budgets(); limit["local_steps"] = 1;
  EXPECT_THROW(moa::localMetadata(*module, origin(), limit), std::runtime_error);
  Temp file; file.bc(*module);
  auto bytes = MemoryBuffer::getFile(file.path); ASSERT_TRUE(bool(bytes));
  auto request = batch(file.path.str().str());
  auto *job = request.getArray("jobs")->front().getAsObject();
  (*job->getObject("origin"))["module_hash"] = toHex(SHA256::hash(arrayRefFromStringRef((*bytes)->getBuffer())), true);
  (*job->getObject("budgets"))["local_steps"] = 1;
  auto result = moa::localBatch(request);
  auto *entry = result.getArray("results")->front().getAsObject();
  EXPECT_TRUE(entry->get("result")->getAsNull().has_value());
  EXPECT_EQ(entry->getObject("error")->getString("code"), "local_budget_exceeded");
  limit["local_steps"] = 5;
  EXPECT_NO_THROW(moa::localMetadata(*module, origin(), limit));
  limit["local_steps"] = 4;
  EXPECT_THROW(moa::localMetadata(*module, origin(), limit), std::runtime_error);
}
