#include "provenance.h"
#include "facts.h"

#include <gtest/gtest.h>
#include <llvm/AsmParser/Parser.h>
#include <llvm/Bitcode/BitcodeWriter.h>
#include <llvm/Support/SourceMgr.h>

#include <filesystem>
#include <fstream>
#include <set>

using namespace llvm;

namespace {

json::Object budgets(int64_t values = 1000, int64_t candidates = 64,
                     int64_t aa = 1000, int64_t memory = 1000) {
  return json::Object{{"translation_units", 4}, {"source_nodes", 1000}, {"ir_nodes", 1000},
    {"path_segments", 64}, {"path_depth", 32}, {"values", values},
    {"candidate_targets", candidates}, {"guards", 128}, {"load_hops", 16},
    {"aa_queries", aa}, {"memoryssa_steps", memory}, {"capture_uses", 1000},
    {"call_contexts", 128}, {"recursive_iterations", 16}, {"relations", 1000},
    {"diagnostic_bytes", 4096}, {"worker_seconds", 30},
    {"worker_output_bytes", 1048576}, {"request_seconds", 60},
    {"request_output_bytes", 4194304}};
}

json::Object request(StringRef bitcode = "/tmp/a.bc", int64_t values = 1000,
                     int64_t candidates = 64, int64_t aa = 1000, int64_t memory = 1000) {
  return json::Object{{"schema_version", 1}, {"kind", "LLVMObjectProvenanceRequest"},
    {"analysis_version", "0.1.0"}, {"policy_id", "bounded-object-provenance-v1"},
    {"artifact_key", std::string(64, 'a')}, {"profile_id", std::string(64, 'b')},
    {"physical_tu_id", "tu"},
    {"bitcode", json::Object{{"path", bitcode.str()}, {"sha256", std::string(64, 'c')}}},
    {"dependencies", json::Array{}}, {"budgets", budgets(values, candidates, aa, memory)},
    {"semantic_digest", std::string(64, 'd')}};
}

void writeJson(const std::filesystem::path &path, json::Object value) {
  std::error_code error;
  raw_fd_ostream output(path.string(), error);
  ASSERT_FALSE(error);
  output << json::Value(std::move(value));
}

std::unique_ptr<Module> module(LLVMContext &context) {
  SMDiagnostic error;
  auto result = parseAssemblyString(R"(
    target triple = "x86_64-pc-linux-gnu"
    target datalayout = "e-p:64:64"
    @global = global { ptr, i32 } zeroinitializer
    declare void @escape(ptr)
    define ptr @callee(ptr returned %p) { entry: ret ptr %p }
    define ptr @work(ptr %p, ptr %q, i1 %condition, i64 %index) {
    entry:
      %slot = alloca ptr
      store ptr %p, ptr %slot
      %loaded = load ptr, ptr %slot
      %wide = alloca [16 x i8]
      %wide0 = getelementptr [16 x i8], ptr %wide, i64 0, i64 0
      %wide4 = getelementptr i8, ptr %wide0, i64 4
      store ptr %p, ptr %wide0
      %overlap = load ptr, ptr %wide4
      %field = getelementptr i8, ptr %loaded, i64 4
      %dynamic = getelementptr i8, ptr %q, i64 %index
      %selected = select i1 %condition, ptr %field, ptr %dynamic
      br i1 %condition, label %left, label %right
    left:
      br label %merge
    right:
      br label %merge
    merge:
      %joined = phi ptr [ %selected, %left ], [ %field, %right ]
      %integer = ptrtoint ptr %joined to i64
      %roundtrip = inttoptr i64 %integer to ptr
      call void @escape(ptr %q)
      %result = call ptr @callee(ptr %joined)
      ret ptr %result
    }
  )", error, context);
  if (!result) error.print("test", errs());
  return result;
}

std::unique_ptr<Module> boundaryModule(LLVMContext &context) {
  SMDiagnostic error;
  auto result = parseAssemblyString(R"(
    %S = type { i8 }
    declare void @escape(ptr)
    define void @receiver(ptr sret(%S) %out) { entry: ret void }
    define ptr @boundaries(ptr %p, ptr %q, i1 %condition) {
    entry:
      %slot = alloca ptr
      %empty = load ptr, ptr %slot
      store i32 7, ptr %slot
      %nonpointer-store = load ptr, ptr %slot
      store atomic ptr %p, ptr %slot seq_cst, align 8
      %atomic-load = load atomic ptr, ptr %slot seq_cst, align 8
      %volatile-load = load volatile ptr, ptr %slot
      %selected = select i1 %condition, ptr null, ptr poison
      %converted = addrspacecast ptr %q to ptr addrspace(1)
      %indirect = call ptr %p(ptr %q)
      ret ptr %slot
    }
    define i32 @integer_return() { entry: ret i32 0 }
  )", error, context);
  if (!result) error.print("test", errs());
  return result;
}

const json::Object *findOpcode(const json::Object &facts, StringRef opcode) {
  for (const auto &item : *facts.getArray("values"))
    if (item.getAsObject()->getString("opcode") == opcode) return item.getAsObject();
  return nullptr;
}

} // namespace

TEST(ObjectProvenance, ProtocolIsPinnedAndRequestValidationIsStrict) {
  auto protocol = moa::objectProvenanceProtocol();
  EXPECT_EQ(*protocol.getInteger("protocol_version"), 1);
  EXPECT_EQ(*protocol.getString("llvm_version"), "21.1.8");
  EXPECT_EQ(*protocol.getString("policy_id"), "bounded-object-provenance-v1");
  LLVMContext context;
  auto input = module(context);
  auto invalid = request(); invalid["kind"] = "wrong";
  EXPECT_THROW(moa::localObjectProvenance(*input, invalid), std::runtime_error);
  auto noBudgets = request(); noBudgets.erase("budgets");
  EXPECT_THROW(moa::localObjectProvenance(*input, noBudgets), std::runtime_error);
  auto wrongSchema = request(); wrongSchema["schema_version"] = 2;
  EXPECT_THROW(moa::localObjectProvenance(*input, wrongSchema), std::runtime_error);
  auto noArtifact = request(); noArtifact.erase("artifact_key");
  EXPECT_THROW(moa::localObjectProvenance(*input, noArtifact), std::runtime_error);
  auto emptyProfile = request(); emptyProfile["profile_id"] = "";
  EXPECT_THROW(moa::localObjectProvenance(*input, emptyProfile), std::runtime_error);
  auto noBitcode = request(); noBitcode.erase("bitcode");
  EXPECT_THROW(moa::localObjectProvenance(*input, noBitcode), std::runtime_error);
  auto missingBudget = request(); missingBudget.getObject("budgets")->erase("values");
  EXPECT_THROW(moa::localObjectProvenance(*input, missingBudget), std::runtime_error);
  auto zeroBudget = request(); (*zeroBudget.getObject("budgets"))["values"] = 0;
  EXPECT_THROW(moa::localObjectProvenance(*input, zeroBudget), std::runtime_error);
}

TEST(ObjectProvenance, UsesLLVMAnalysesAndPreservesMustMayUnknownEvidence) {
  LLVMContext context;
  auto input = module(context);
  auto facts = moa::localObjectProvenance(*input, request());
  EXPECT_EQ(*facts.getString("status"), "complete");
  EXPECT_EQ(*facts.getString("mode"), "ir-only");
  EXPECT_EQ(*facts.getString("target"), "x86_64-pc-linux-gnu");
  EXPECT_FALSE(facts.getArray("values")->empty());
  EXPECT_FALSE(facts.getArray("queries")->empty());
  EXPECT_FALSE(facts.getArray("call_edges")->empty());
  EXPECT_FALSE(facts.getArray("returns")->empty());
  std::set<std::string> states, queryKinds, queryResults;
  bool strong = false, conservative = false, guarded = false, dynamicUnknown = false;
  for (const auto &entry : *facts.getArray("values")) {
    auto *domain = entry.getAsObject()->getObject("domain");
    states.insert(domain->getString("state")->str());
    auto name = entry.getAsObject()->getString("ir_name");
    dynamicUnknown |= name && name->contains("%dynamic") &&
                      domain->getString("reason") == "dynamic-index-unbounded";
    for (const auto &candidate : *domain->getArray("candidates")) {
      auto *item = candidate.getAsObject();
      guarded |= !item->getArray("guards")->empty();
      for (const auto &proof : *item->getArray("proof"))
        strong |= proof.getAsString() == "memoryssa-unique-dominating-store";
      for (const auto &opposed : *item->getArray("opposed"))
        conservative |= opposed.getAsString() == "llvm-pointer-may-be-captured" ||
                        opposed.getAsString() == "llvm-unknown-storage-kind";
    }
  }
  for (const auto &entry : *facts.getArray("queries")) {
    auto *item = entry.getAsObject();
    queryKinds.insert(item->getString("kind")->str());
    queryResults.insert(item->getString("result")->str());
  }
  EXPECT_TRUE(states.count("must"));
  EXPECT_TRUE(states.count("may") || states.count("unknown"));
  EXPECT_TRUE(strong);
  EXPECT_TRUE(conservative);
  EXPECT_TRUE(guarded);
  EXPECT_TRUE(dynamicUnknown);
  EXPECT_TRUE(queryKinds.count("underlying-object"));
  EXPECT_TRUE(queryKinds.count("constant-base-offset"));
  EXPECT_TRUE(queryKinds.count("capture-tracking"));
  EXPECT_TRUE(queryKinds.count("memoryssa-clobber"));
  EXPECT_TRUE(queryKinds.count("dominance"));
  EXPECT_TRUE(queryKinds.count("aa-memory-location"));
  EXPECT_TRUE(queryResults.count("must-alias"));
  EXPECT_TRUE(queryResults.count("may-alias"));
  EXPECT_TRUE(queryResults.count("no-alias"));
  EXPECT_TRUE(queryResults.count("partial-alias"));
  EXPECT_EQ(findOpcode(facts, "ptrtoint"), nullptr);
  auto *roundtrip = findOpcode(facts, "inttoptr");
  ASSERT_NE(roundtrip, nullptr);
  EXPECT_EQ(*roundtrip->getObject("domain")->getString("state"), "unknown");
  EXPECT_EQ(*roundtrip->getObject("domain")->getString("reason"), "ptr-int-origin");
}

TEST(ObjectProvenance, BudgetLimitsArePartialAndNeverSilentlyTruncate) {
  LLVMContext context;
  auto input = module(context);
  auto facts = moa::localObjectProvenance(*input, request("/tmp/a.bc", 1, 1, 1, 1));
  EXPECT_EQ(*facts.getString("status"), "partial");
  EXPECT_EQ(facts.getArray("values")->size(), 1u);
  ASSERT_FALSE(facts.getArray("frontier")->empty());
  EXPECT_EQ(*facts.getArray("frontier")->front().getAsObject()->getString("code"),
            "llvm-provenance-budget-exhausted");
}

TEST(ObjectProvenance, ConservativeBoundariesRemainUnknownAndAuditable) {
  LLVMContext context;
  auto input = boundaryModule(context);
  ASSERT_NE(input, nullptr);
  auto facts = moa::localObjectProvenance(*input, request("/tmp/boundaries.bc", 1000, 64, 1000, 1000));
  EXPECT_EQ(*facts.getString("status"), "partial");
  EXPECT_EQ(*facts.getString("target"), "unknown");
  EXPECT_TRUE(facts.getString("data_layout")->empty());
  bool receiver = false, addressSpace = false, expired = false, indirect = false;
  bool atomic = false, volatileLoad = false;
  for (const auto &entry : *facts.getArray("values")) {
    auto *item = entry.getAsObject();
    auto opcode = item->getString("opcode");
    if (opcode == "load") {
      auto name = item->getString("ir_name");
      atomic |= name && name->contains("atomic-load");
      volatileLoad |= name && name->contains("volatile-load");
    }
    addressSpace |= item->getInteger("address_space") == 1;
    auto *domain = item->getObject("domain");
    for (const auto &candidateValue : *domain->getArray("candidates"))
      receiver |= candidateValue.getAsObject()->getObject("object")->getObject("storage")->getString("kind") == "receiver";
  }
  for (const auto &entry : *facts.getArray("returns"))
    expired |= entry.getAsObject()->getString("lifetime") == "expired";
  for (const auto &entry : *facts.getArray("call_edges"))
    indirect |= entry.getAsObject()->getString("status") == "indirect";
  EXPECT_TRUE(receiver); EXPECT_TRUE(addressSpace); EXPECT_TRUE(expired); EXPECT_TRUE(indirect);
  EXPECT_TRUE(atomic); EXPECT_TRUE(volatileLoad);
  EXPECT_FALSE(facts.getArray("frontier")->empty());

  auto memoryLimited = moa::localObjectProvenance(*input, request("/tmp/a.bc", 1000, 64, 1000, 1));
  EXPECT_EQ(*memoryLimited.getString("status"), "partial");
  auto aaLimited = moa::localObjectProvenance(*input, request("/tmp/a.bc", 1000, 64, 1, 1000));
  EXPECT_EQ(*aaLimited.getString("status"), "partial");
}

TEST(ObjectProvenance, WorkerReadsBitcodeAndRejectsMissingInvalidAndOutputLimit) {
  LLVMContext context;
  auto input = module(context);
  auto directory = std::filesystem::temp_directory_path();
  auto bitcode = directory / "moa-provenance.bc";
  auto requestPath = directory / "moa-provenance-request.json";
  {
    std::error_code error;
    raw_fd_ostream output(bitcode.string(), error);
    ASSERT_FALSE(error);
    WriteBitcodeToFile(*input, output);
  }
  auto value = request(bitcode.string());
  {
    std::error_code error;
    raw_fd_ostream output(requestPath.string(), error);
    ASSERT_FALSE(error);
    output << json::Value(json::Object(value));
  }
  std::string out, err;
  raw_string_ostream stdoutStream(out), stderrStream(err);
  EXPECT_EQ(moa::objectProvenanceWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 0);
  stdoutStream.flush(); stderrStream.flush();
  EXPECT_NE(out.find("LLVMObjectProvenanceFacts"), std::string::npos);
  const char *protocolArgs[] = {"worker", "--object-provenance-protocol"};
  EXPECT_EQ(moa::worker(2, protocolArgs, stdoutStream, stderrStream), 0);
  std::string requestName = requestPath.string();
  const char *requestArgs[] = {"worker", "--object-provenance-request", requestName.c_str()};
  EXPECT_EQ(moa::worker(3, requestArgs, stdoutStream, stderrStream), 0);

  auto outputLimited = request(bitcode.string());
  (*outputLimited.getObject("budgets"))["worker_output_bytes"] = 1;
  writeJson(requestPath, std::move(outputLimited));
  EXPECT_EQ(moa::objectProvenanceWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  { std::ofstream stream(requestPath); stream << "[]"; }
  EXPECT_EQ(moa::objectProvenanceWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  { std::ofstream stream(requestPath); stream << R"({"schema_version":1,"kind":"LLVMObjectProvenanceRequest"})"; }
  EXPECT_EQ(moa::objectProvenanceWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  { std::ofstream stream(requestPath); stream << "{"; }
  EXPECT_EQ(moa::objectProvenanceWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  auto missingBitcode = request((directory / "moa-provenance-missing.bc").string());
  writeJson(requestPath, std::move(missingBitcode));
  EXPECT_EQ(moa::objectProvenanceWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  auto invalidBitcodePath = directory / "moa-provenance-invalid.bc";
  { std::ofstream stream(invalidBitcodePath); stream << "not bitcode"; }
  auto invalidBitcode = request(invalidBitcodePath.string());
  writeJson(requestPath, std::move(invalidBitcode));
  EXPECT_EQ(moa::objectProvenanceWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  std::filesystem::remove(invalidBitcodePath);
  std::filesystem::remove(requestPath);
  out.clear(); err.clear();
  EXPECT_EQ(moa::objectProvenanceWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  std::filesystem::remove(bitcode);
}
