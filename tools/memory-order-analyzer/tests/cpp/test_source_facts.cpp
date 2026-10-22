#include "source_facts.h"
#include <gtest/gtest.h>
#include <filesystem>
#include <fstream>
#include <set>

#define main sourceWorkerProgramMain
#include "../../src/source_worker_main.cpp"
#undef main

using namespace llvm;

namespace {
json::Object budgets() {
  return json::Object{{"translation_units", 4}, {"ast_nodes", 1000}, {"references", 1000},
                      {"diagnostics", 32}, {"entity_groups", 1000}, {"binding_candidates", 1000},
                      {"dependency_items", 1000}, {"worker_seconds", 30},
                      {"worker_output_bytes", 1048576}, {"request_seconds", 60},
                      {"request_output_bytes", 4194304}};
}

json::Object request(const std::filesystem::path &path, StringRef standard = "c11") {
  auto directory = path.parent_path().string();
  json::Object source{{"path", path.string()}, {"sha256", std::string(64, 'a')}};
  json::Array argv; argv.push_back("clang-21"); argv.push_back(("-std=" + standard).str());
  json::Object profile{{"profile_id", std::string(64, 'b')}, {"working_directory", directory},
                       {"source", std::move(source)}, {"argv", std::move(argv)}};
  return json::Object{{"schema_version", 1}, {"kind", "SourceSemanticRequest"},
                      {"profile", std::move(profile)}, {"physical_tu_id", std::string(64, 'c')},
                      {"source_path", path.string()}, {"budgets", budgets()}};
}

json::Object versionedRequest(const std::filesystem::path &path, StringRef standard,
                              StringRef language, StringRef dialect) {
  auto value = request(path, standard);
  value["schema_version"] = 2;
  auto *profile = value.getObject("profile");
  (*profile)["schema_version"] = 2;
  (*profile)["language"] = language;
  (*profile)["standard"] = standard;
  (*profile)["dialect"] = dialect;
  (*profile)["standard_source"] = "explicit";
  (*profile)["standard_option"] = ("-std=" + standard).str();
  return value;
}

json::Object irRequest(const std::filesystem::path &path) {
  json::Object bitcode{{"path", path.string()}, {"sha256", std::string(64, 'd')}};
  return json::Object{{"schema_version", 1}, {"kind", "LLVMSourceBindingRequest"},
                      {"artifact_key", std::string(64, 'e')}, {"profile_id", std::string(64, 'b')},
                      {"physical_tu_id", std::string(64, 'c')}, {"bitcode", std::move(bitcode)},
                      {"budgets", budgets()}};
}

json::Object provenanceBudgets(int64_t pathSegments = 1000, int64_t pathDepth = 32) {
  return json::Object{{"translation_units", 4}, {"source_nodes", 10000}, {"ir_nodes", 10000},
                      {"path_segments", pathSegments}, {"path_depth", pathDepth}, {"values", 10000},
                      {"candidate_targets", 64}, {"guards", 128}, {"load_hops", 16},
                      {"aa_queries", 10000}, {"memoryssa_steps", 10000}, {"capture_uses", 10000},
                      {"call_contexts", 128}, {"recursive_iterations", 16}, {"relations", 10000},
                      {"diagnostic_bytes", 4096}, {"worker_seconds", 30},
                      {"worker_output_bytes", 1048576}, {"request_seconds", 60},
                      {"request_output_bytes", 4194304}};
}

json::Object pathRequest(const std::filesystem::path &path, StringRef standard = "c11",
                         int64_t pathSegments = 1000, int64_t pathDepth = 32) {
  auto directory = path.parent_path().string();
  json::Object source{{"path", path.string()}, {"sha256", std::string(64, 'a')}};
  json::Array argv; argv.push_back("clang-21"); argv.push_back(("-std=" + standard).str());
  json::Object profile{{"profile_id", std::string(64, 'b')}, {"working_directory", directory},
                       {"source", std::move(source)}, {"argv", std::move(argv)}};
  return json::Object{{"schema_version", 1}, {"kind", "SourceObjectPathRequest"},
                      {"analysis_version", "0.1.0"}, {"policy_id", "bounded-object-provenance-v1"},
                      {"profile", std::move(profile)}, {"physical_tu_id", std::string(64, 'c')},
                      {"source_path", path.string()},
                      {"budgets", provenanceBudgets(pathSegments, pathDepth)},
                      {"semantic_digest", std::string(64, 'd')}};
}

void writeJson(const std::filesystem::path &path, json::Object value) {
  std::error_code error;
  raw_fd_ostream output(path.string(), error);
  ASSERT_FALSE(error);
  output << json::Value(std::move(value));
}

std::set<std::string> relationKinds(const json::Object &facts) {
  std::set<std::string> result;
  for (const auto &item : *facts.getArray("relations"))
    result.insert(item.getAsObject()->getString("kind")->str());
  return result;
}

size_t relationKindCount(const json::Object &facts, StringRef kind) {
  size_t result = 0;
  for (const auto &item : *facts.getArray("relations"))
    result += item.getAsObject()->getString("kind") == kind;
  return result;
}
}

TEST(SourceFacts, ProtocolIsPinned) {
  auto protocol = moa::sourceProtocol();
  EXPECT_EQ(*protocol.getInteger("protocol_version"), 2);
  EXPECT_EQ(*protocol.getString("llvm_version"), "21.1.8");
  EXPECT_EQ(*protocol.getString("policy_id"), "ast-cross-tu-evidence-v1");
  EXPECT_EQ(*protocol.getObject("kinds")->getInteger("CompilationProfileIdentity"), 2);
  EXPECT_EQ(*protocol.getObject("kinds")->getInteger("SourceSemanticRequest"), 2);
  EXPECT_EQ(*protocol.getObject("kinds")->getInteger("SourceSemanticFacts"), 1);
}

TEST(SourceFacts, SourceWorkerProgramDispatchesEveryMode) {
  const char *protocol[] = {"memory-order-source-worker", "--source-analysis-protocol"};
  EXPECT_EQ(sourceWorkerProgramMain(2, protocol), 0);
  const char *source[] = {"memory-order-source-worker", "--source-request", "/tmp/missing-source.json"};
  EXPECT_EQ(sourceWorkerProgramMain(3, source), 1);
  const char *binding[] = {"memory-order-source-worker", "--ir-binding-request", "/tmp/missing-ir.json"};
  EXPECT_EQ(sourceWorkerProgramMain(3, binding), 1);
  const char *provenance[] = {"memory-order-source-worker", "--object-provenance-protocol"};
  EXPECT_EQ(sourceWorkerProgramMain(2, provenance), 0);
  const char *paths[] = {"memory-order-source-worker", "--object-path-request", "/tmp/missing-object-path.json"};
  EXPECT_EQ(sourceWorkerProgramMain(3, paths), 1);
  const char *usage[] = {"memory-order-source-worker"};
  EXPECT_EQ(sourceWorkerProgramMain(1, usage), 1);
  const char *unknown[] = {"memory-order-source-worker", "--unknown"};
  EXPECT_EQ(sourceWorkerProgramMain(2, unknown), 1);
}

TEST(SourceFacts, ObjectPathProtocolIsPinned) {
  auto protocol = moa::provenanceProtocol();
  EXPECT_EQ(*protocol.getInteger("protocol_version"), 1);
  EXPECT_EQ(*protocol.getString("llvm_version"), "21.1.8");
  EXPECT_EQ(*protocol.getString("policy_id"), "bounded-object-provenance-v1");
  EXPECT_TRUE(protocol.getObject("kinds")->getInteger("SourceObjectPathFacts"));
}

TEST(SourceFacts, ExtractsCStructUnionPointerMacroArgumentAndReturnPaths) {
  auto path = std::filesystem::temp_directory_path() / "moa-object-paths.c";
  { std::ofstream stream(path); stream << R"(
    struct Inner { int value; };
    union Choice { int left; long right; };
    struct Box { struct Inner inner; struct Inner *pointer; union Choice choice; };
    #define VALUE(x) ((x)->inner.value)
    int read_value(struct Box *box) { return VALUE(box); }
    int *return_pointer(struct Box *box) { return &box->pointer->value; }
    void write_value(struct Box *box, int value) { box->inner.value = value; }
    long union_value(struct Box *box) { return box->choice.right; }
  )"; }
  auto facts = moa::analyzeObjectPaths(pathRequest(path, "c17"));
  std::filesystem::remove(path);
  EXPECT_EQ(*facts.getString("kind"), "SourceObjectPathFacts");
  EXPECT_EQ(*facts.getString("language"), "c");
  EXPECT_EQ(*facts.getString("standard"), "c17");
  EXPECT_EQ(*facts.getString("status"), "complete");
  EXPECT_FALSE(facts.getArray("paths")->empty());
  bool nested = false, arrow = false, overlap = false, spelling = false, write = false, returned = false;
  for (const auto &entry : *facts.getArray("paths")) {
    const auto &item = *entry.getAsObject();
    write |= item.getString("role") == "write";
    returned |= item.getString("role") == "return";
    const auto *source = item.getObject("source");
    spelling |= source && source->getObject("spelling") && source->getObject("expansion");
    auto *segments = item.getArray("segments");
    nested |= segments && segments->size() >= 2;
    if (!segments) continue;
    for (const auto &value : *segments) {
      auto *segment = value.getAsObject();
      arrow |= segment->getString("access") == "arrow";
      overlap |= !segment->get("union_group")->getAsNull().has_value();
    }
  }
  EXPECT_TRUE(nested); EXPECT_TRUE(arrow); EXPECT_TRUE(overlap);
  EXPECT_TRUE(spelling); EXPECT_TRUE(write); EXPECT_TRUE(returned);
}

TEST(SourceFacts, ExtractsCppThisAndKeepsSameFieldOnDifferentBasesDistinct) {
  auto path = std::filesystem::temp_directory_path() / "moa-object-paths.cpp";
  { std::ofstream stream(path); stream << R"(
    struct Box { int value; int read() const { return this->value; } };
    int sum(Box *left, Box *right) { return left->value + right->value; }
  )"; }
  auto facts = moa::analyzeObjectPaths(pathRequest(path, "c++20"));
  std::filesystem::remove(path);
  EXPECT_EQ(*facts.getString("language"), "c++");
  EXPECT_EQ(*facts.getString("standard"), "c++20");
  std::set<std::string> bases;
  bool receiver = false;
  for (const auto &entry : *facts.getArray("paths")) {
    auto *base = entry.getAsObject()->getObject("base");
    receiver |= base->getString("kind") == "receiver";
    if (auto id = base->getString("declaration_id")) bases.insert(id->str());
  }
  EXPECT_TRUE(receiver);
  EXPECT_GE(bases.size(), 3u);
}

TEST(SourceFacts, ObjectPathsExposeCandidatesUnknownAndBudgetsWithoutRuntimeAliasClaims) {
  auto path = std::filesystem::temp_directory_path() / "moa-object-path-budget.c";
  { std::ofstream stream(path); stream << R"(
    struct Flex { int n; int data[]; }; struct Bits { unsigned value:3; };
    int read_flex(struct Flex *p, int i) { return p->data[i]; }
    int read_bits(struct Bits *p) { return p->value; }
  )"; }
  auto facts = moa::analyzeObjectPaths(pathRequest(path, "c11", 1, 2));
  std::filesystem::remove(path);
  EXPECT_EQ(*facts.getString("status"), "partial");
  EXPECT_FALSE(facts.getArray("frontier")->empty());
  std::string rendered;
  raw_string_ostream output(rendered); output << json::Value(json::Object(facts)); output.flush();
  EXPECT_EQ(rendered.find("noalias"), std::string::npos);
  EXPECT_EQ(rendered.find("runtime_object"), std::string::npos);
  auto invalid = pathRequest(path, "c11"); invalid["kind"] = "wrong";
  EXPECT_THROW(moa::analyzeObjectPaths(invalid), std::runtime_error);
}

TEST(SourceFacts, ObjectPathsCoverCExpressionLayoutsCastsAndGuards) {
  auto path = std::filesystem::temp_directory_path() / "moa-object-path-expressions.c";
  { std::ofstream stream(path); stream << R"(
    struct Bits { unsigned bit:3; int array[4]; int flexible[]; };
    struct Box { struct Bits bits; int *pointer; };
    union Choice { struct Box box; long other; };
    void consume(void *p);
    long inspect(struct Box *left, struct Box *right, int index, int **indirect) {
      consume((void *)left);
      consume((void *)(long)right);
      consume(*indirect);
      consume(&left->bits.array[2]);
      consume(index ? &left->bits.array[2] : &right->bits.array[index]);
      left->bits.bit = 1;
      return (long)&left->bits.flexible[index];
    }
  )"; }
  auto facts = moa::analyzeObjectPaths(pathRequest(path, "gnu17"));
  std::filesystem::remove(path);
  EXPECT_EQ(*facts.getString("standard"), "c17");
  bool constantIndex = false, dynamicIndex = false, conditional = false;
  bool dereference = false, cast = false, lossy = false, bitfield = false, flexible = false;
  for (const auto &entry : *facts.getArray("paths")) {
    auto *item = entry.getAsObject();
    conditional |= item->getObject("base")->getString("kind") == "conditional";
    lossy |= item->getString("reason") == "lossy-or-address-space-cast";
    bitfield |= item->getString("reason") == "bit-field-layout";
    flexible |= item->getString("reason") == "flexible-array-layout";
    for (const auto &value : *item->getArray("segments")) {
      auto *part = value.getAsObject();
      dereference |= part->getString("kind") == "deref";
      cast |= part->getString("kind") == "cast";
      if (part->getString("kind") == "array-index") {
        constantIndex |= part->getInteger("field_index").has_value();
        dynamicIndex |= part->get("field_index")->getAsNull().has_value();
      }
    }
  }
  EXPECT_TRUE(constantIndex); EXPECT_TRUE(dynamicIndex); EXPECT_TRUE(conditional);
  EXPECT_TRUE(dereference); EXPECT_TRUE(cast); EXPECT_TRUE(lossy);
  EXPECT_TRUE(bitfield); EXPECT_TRUE(flexible);
}

TEST(SourceFacts, ObjectPathsCoverCppMethodAndSegmentBudgetWithoutFalsePrecision) {
  auto path = std::filesystem::temp_directory_path() / "moa-object-path-method.cpp";
  { std::ofstream stream(path); stream << R"(
    struct Inner { int value; };
    struct Box { Inner inner; int method() const { return inner.value; } };
    int inspect(Box *box) { return box->method() + box->inner.value; }
  )"; }
  auto completeFacts = moa::analyzeObjectPaths(pathRequest(path, "gnu++17", 1000, 32));
  auto facts = moa::analyzeObjectPaths(pathRequest(path, "gnu++17", 1, 32));
  std::filesystem::remove(path);
  EXPECT_EQ(*facts.getString("standard"), "c++17");
  EXPECT_EQ(*facts.getString("status"), "partial");
  bool budget = false, nonField = false;
  for (const auto &entry : *completeFacts.getArray("paths")) {
    auto reason = entry.getAsObject()->getString("reason");
    nonField |= reason && *reason == "non-field-member";
  }
  for (const auto &entry : *facts.getArray("paths")) {
    auto *item = entry.getAsObject();
    budget |= item->getString("reason") == "path-segment-budget-exhausted";
    if (item->getString("reason") == "path-segment-budget-exhausted")
      EXPECT_EQ(*item->getString("status"), "unknown");
  }
  EXPECT_TRUE(budget); EXPECT_TRUE(nonField);
}

TEST(SourceFacts, ObjectPathRequestValidationAndReplayFailuresAreClassified) {
  auto path = std::filesystem::temp_directory_path() / "moa-object-path-validation.c";
  { std::ofstream stream(path); stream << "struct S { int x; }; int f(struct S *p) { return p->x; }\n"; }
  auto valid = pathRequest(path);

  auto wrongSchema = pathRequest(path); wrongSchema["schema_version"] = 2;
  EXPECT_THROW(moa::analyzeObjectPaths(wrongSchema), std::runtime_error);
  auto noProfile = pathRequest(path); noProfile.erase("profile");
  EXPECT_THROW(moa::analyzeObjectPaths(noProfile), std::runtime_error);
  auto noBudgets = pathRequest(path); noBudgets.erase("budgets");
  EXPECT_THROW(moa::analyzeObjectPaths(noBudgets), std::runtime_error);
  auto noSource = pathRequest(path); noSource.getObject("profile")->erase("source");
  EXPECT_THROW(moa::analyzeObjectPaths(noSource), std::runtime_error);
  auto mismatch = pathRequest(path); (*mismatch.getObject("profile")->getObject("source"))["path"] = "different.c";
  EXPECT_THROW(moa::analyzeObjectPaths(mismatch), std::runtime_error);
  auto failedReplay = pathRequest(path);
  (*failedReplay.getObject("profile"))["replay"] = json::Object{{"status", "failed"}};
  EXPECT_THROW(moa::analyzeObjectPaths(failedReplay), std::runtime_error);
  auto noArgv = pathRequest(path); noArgv.getObject("profile")->erase("argv");
  EXPECT_THROW(moa::analyzeObjectPaths(noArgv), std::runtime_error);
  auto emptyArgv = pathRequest(path); (*emptyArgv.getObject("profile"))["argv"] = json::Array{};
  EXPECT_THROW(moa::analyzeObjectPaths(emptyArgv), std::runtime_error);
  auto badArgv = pathRequest(path); (*badArgv.getObject("profile"))["argv"] = json::Array{"clang-21", 7};
  EXPECT_THROW(moa::analyzeObjectPaths(badArgv), std::runtime_error);
  auto unsupported = pathRequest(path, "c99");
  EXPECT_THROW(moa::analyzeObjectPaths(unsupported), std::runtime_error);
  auto missingBudget = pathRequest(path); missingBudget.getObject("budgets")->erase("source_nodes");
  EXPECT_THROW(moa::analyzeObjectPaths(missingBudget), std::runtime_error);
  auto zeroBudget = pathRequest(path); (*zeroBudget.getObject("budgets"))["source_nodes"] = 0;
  EXPECT_THROW(moa::analyzeObjectPaths(zeroBudget), std::runtime_error);

  auto replayArgs = pathRequest(path, "gnu11");
  auto *argv = replayArgs.getObject("profile")->getArray("argv");
  argv->push_back("-c"); argv->push_back("-emit-llvm"); argv->push_back(path.string());
  argv->push_back("-o"); argv->push_back("ignored.bc");
  EXPECT_EQ(*moa::analyzeObjectPaths(replayArgs).getString("standard"), "c11");
  auto nodeLimited = pathRequest(path);
  (*nodeLimited.getObject("budgets"))["source_nodes"] = 1;
  EXPECT_EQ(*moa::analyzeObjectPaths(nodeLimited).getString("status"), "partial");

  auto missing = pathRequest(path.parent_path() / "moa-object-path-does-not-exist.c");
  EXPECT_EQ(*moa::analyzeObjectPaths(missing).getString("status"), "failed");
  std::filesystem::remove(path);
}

TEST(SourceFacts, ObjectPathWorkerCoversSuccessMalformedAndOutputLimits) {
  auto directory = std::filesystem::temp_directory_path();
  auto source = directory / "moa-object-path-worker.c";
  auto requestPath = directory / "moa-object-path-worker.json";
  { std::ofstream stream(source); stream << "struct S { int x; }; int f(struct S *p) { return p->x; }\n"; }
  auto value = pathRequest(source);
  writeJson(requestPath, json::Object(value));
  std::string out, err;
  raw_string_ostream stdoutStream(out), stderrStream(err);
  EXPECT_EQ(moa::objectPathWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 0);
  stdoutStream.flush(); EXPECT_NE(out.find("SourceObjectPathFacts"), std::string::npos);

  (*value.getObject("budgets"))["worker_output_bytes"] = 1;
  writeJson(requestPath, json::Object(value));
  EXPECT_EQ(moa::objectPathWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  { std::ofstream stream(requestPath); stream << "[]"; }
  EXPECT_EQ(moa::objectPathWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  { std::ofstream stream(requestPath); stream << "{"; }
  EXPECT_EQ(moa::objectPathWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  std::filesystem::remove(requestPath);
  EXPECT_EQ(moa::objectPathWorker(requestPath.string().c_str(), stdoutStream, stderrStream), 1);
  std::filesystem::remove(source);
}

TEST(SourceFacts, ExtractsDeclarationsReferencesAndControl) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-facts.c";
  { std::ofstream stream(path); stream << "int flag; int read_flag(void){ if(flag) return flag; return 0; }\n"; }
  auto facts = moa::analyzeSource(request(path));
  std::filesystem::remove(path);
  EXPECT_EQ(*facts.getString("status"), "complete");
  EXPECT_FALSE(facts.getArray("nodes")->empty());
  EXPECT_FALSE(facts.getArray("relations")->empty());
  EXPECT_EQ(*facts.getString("physical_tu_id"), std::string(64, 'c'));
}

TEST(SourceFacts, RejectsInvalidRequestAndReportsMissingFile) {
  json::Object invalid{{"kind", "other"}, {"schema_version", 1}};
  EXPECT_THROW(moa::analyzeSource(invalid), std::runtime_error);
  auto missing = std::filesystem::temp_directory_path() / "moa-source-facts-missing.c";
  auto facts = moa::analyzeSource(request(missing));
  EXPECT_EQ(*facts.getString("status"), "failed");
  EXPECT_FALSE(facts.getArray("diagnostics")->empty());
}

TEST(SourceFacts, ExtractsValueFlowAtomicAndPthreadFacts) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-semantics.c";
  { std::ofstream stream(path); stream << R"(
    #include <pthread.h>
    #include <stdatomic.h>
    _Atomic int flag = 0;
    pthread_t handle;
    void *worker(void *p) { int x = (int)atomic_load(&flag); return p; }
    int start(void) { if (flag == 0) pthread_create(&handle, 0, worker, 0); return (int)flag; }
  )"; }
  auto facts = moa::analyzeSource(request(path));
  std::filesystem::remove(path);
  auto kinds = relationKinds(facts);
  std::string listed;
  for (const auto &kind : kinds) listed += kind + ",";
  EXPECT_TRUE(kinds.count("initialize"));
  EXPECT_TRUE(kinds.count("atomic"));
  EXPECT_TRUE(kinds.count("compare"));
  EXPECT_TRUE(kinds.count("callback"));
  EXPECT_TRUE(kinds.count("pthread_create")) << listed;
  EXPECT_TRUE(kinds.count("return"));
}

TEST(SourceFacts, ExtractsCxxMangledNamesAndCanonicalDeclarations) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-semantics.cpp";
  { std::ofstream stream(path); stream << "namespace n { int f(int); int f(int x) { return x; } }\n"; }
  auto facts = moa::analyzeSource(request(path, "c++17"));
  std::filesystem::remove(path);
  bool mangled = false, canonical = false;
  for (const auto &item : *facts.getArray("nodes")) {
    auto *node = item.getAsObject();
    if (node->getString("qualified_name") == "n::f" && node->getString("mangled_name"))
      mangled = true;
    if (node->getString("qualified_name") == "n::f" &&
        node->getString("canonical_decl") != node->getString("id"))
      canonical = true;
  }
  EXPECT_TRUE(mangled);
  EXPECT_TRUE(canonical);
}

TEST(SourceFacts, ExtractsStdThreadLifecycleAndCallableKinds) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-cpp-thread.cpp";
  { std::ofstream stream(path); stream << R"(
    #include <thread>
    void free_worker(int &) {}
    struct owner { void member() {} };
    struct functor { void operator()() const {} };
    void run() {
      int value = 0; owner instance;
      std::thread first(free_worker, std::ref(value));
      bool active = first.joinable();
      first.join();
      std::thread second([&value] { ++value; });
      second.detach();
      std::thread third(&owner::member, &instance);
      std::thread fourth(functor{});
      std::thread fifth(std::move(fourth));
      fifth = std::move(third);
      (void)active;
    }
  )"; }
  auto facts = moa::analyzeSource(request(path, "c++20"));
  std::filesystem::remove(path);
  auto kinds = relationKinds(facts);
  EXPECT_EQ(*facts.getString("status"), "complete");
  for (StringRef expected : {"cpp-thread-object", "cpp-thread-construct",
                             "cpp-thread-callback", "cpp-thread-argument",
                             "cpp-thread-joinable", "cpp-thread-join",
                             "cpp-thread-detach", "cpp-thread-move-construct",
                             "cpp-thread-move-assign", "cpp-thread-move-source",
                             "cpp-thread-destruct"})
    EXPECT_TRUE(kinds.count(expected.str())) << expected.str();
  EXPECT_GE(relationKindCount(facts, "cpp-thread-callback"), 4u);
}

TEST(SourceFacts, ExtractsCanonicalThreadEntryTypesAndRejectsSameNameTypes) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-thread-entry-types.cpp";
  { std::ofstream stream(path); stream << R"(
    #include <future>
    #include <thread>
    using worker_thread = std::thread;
    void worker() {}
    std::thread make_worker() { return std::thread(worker); }
    namespace custom { struct thread { template<class F> thread(F) {} }; }
    void run() {
      worker_thread alias(worker);
      std::thread idle;
      std::thread moved(std::move(alias));
      std::thread from_factory = make_worker();
      auto explicit_async = std::async(std::launch::async, worker);
      auto deferred = std::async(std::launch::deferred, worker);
      auto implementation_choice = std::async(worker);
      auto combined = std::async(std::launch::async | std::launch::deferred, worker);
      custom::thread not_standard(worker);
      (void)idle; (void)moved; (void)from_factory; (void)not_standard;
    }
  )"; }
  auto facts = moa::analyzeSource(request(path, "c++20"));
  std::filesystem::remove(path);
  auto kinds = relationKinds(facts);
  EXPECT_TRUE(kinds.count("cpp-thread-construct"));
  EXPECT_TRUE(kinds.count("cpp-thread-move-construct"));
  EXPECT_TRUE(kinds.count("cpp-thread-factory-return"));
  EXPECT_EQ(relationKindCount(facts, "cpp-async-call"), 4u);

  std::set<std::string> constructorKinds, policies, canonicalRecords;
  bool concreteCanonicalType = false, aliasPreserved = false;
  for (const auto &item : *facts.getArray("nodes")) {
    auto *node = item.getAsObject();
    for (const auto &attribute : *node->getArray("attributes")) {
      auto value = attribute.getAsString();
      if (!value) continue;
      if (value->starts_with("thread-entry:constructor-kind="))
        constructorKinds.insert(value->drop_front(strlen("thread-entry:constructor-kind=")).str());
      if (value->starts_with("thread-entry:launch-policy="))
        policies.insert(value->drop_front(strlen("thread-entry:launch-policy=")).str());
      if (value->starts_with("thread-entry:canonical-record="))
        canonicalRecords.insert(value->drop_front(strlen("thread-entry:canonical-record=")).str());
      aliasPreserved |= *value == "thread-entry:declared-spelled-type=worker_thread";
    }
    if (node->getString("kind") == "cpp-thread-construction")
      concreteCanonicalType |= node->getString("canonical_type") != "expression";
  }
  EXPECT_TRUE(concreteCanonicalType);
  EXPECT_TRUE(aliasPreserved);
  EXPECT_TRUE(constructorKinds.count("default"));
  EXPECT_TRUE(constructorKinds.count("callable-construction"));
  EXPECT_TRUE(constructorKinds.count("move-construction"));
  EXPECT_TRUE(constructorKinds.count("factory-return"));
  EXPECT_TRUE(policies.count("async"));
  EXPECT_TRUE(policies.count("deferred"));
  EXPECT_TRUE(policies.count("default"));
  EXPECT_TRUE(policies.count("both"));
  EXPECT_TRUE(canonicalRecords.count("std::thread"));
  EXPECT_TRUE(canonicalRecords.count("std::async"));
  EXPECT_FALSE(canonicalRecords.count("custom::thread"));
}

TEST(SourceFacts, ExtractsJthreadStopTokenAndC11ThreadEntryFacts) {
  auto cpp = std::filesystem::temp_directory_path() / "moa-source-jthread-entry.cpp";
  { std::ofstream stream(cpp); stream << R"(
    #include <thread>
    void run() {
      std::jthread with_token([](std::stop_token) {});
      std::jthread plain([] {});
      std::jthread moved(std::move(plain));
      with_token.join();
      (void)moved;
    }
  )"; }
  auto cppFacts = moa::analyzeSource(request(cpp, "c++20"));
  std::filesystem::remove(cpp);
  auto cppKinds = relationKinds(cppFacts);
  EXPECT_TRUE(cppKinds.count("cpp-jthread-construct"));
  EXPECT_TRUE(cppKinds.count("cpp-jthread-callback"));
  EXPECT_TRUE(cppKinds.count("cpp-jthread-move-construct"));
  EXPECT_TRUE(cppKinds.count("cpp-jthread-join"));
  bool injected = false;
  for (const auto &item : *cppFacts.getArray("nodes"))
    for (const auto &attribute : *item.getAsObject()->getArray("attributes"))
      injected |= attribute.getAsString() == "thread-entry:stop-token-injected=true";
  EXPECT_TRUE(injected);

  auto c = std::filesystem::temp_directory_path() / "moa-source-c11-thread-entry.c";
  { std::ofstream stream(c); stream << R"(
    #include <threads.h>
    int worker(void *value) { return value != 0; }
    int run(void) { thrd_t handle; return thrd_create(&handle, worker, 0); }
  )"; }
  auto cFacts = moa::analyzeSource(request(c, "c11"));
  std::filesystem::remove(c);
  auto cKinds = relationKinds(cFacts);
  EXPECT_TRUE(cKinds.count("thrd_create"));
  EXPECT_TRUE(cKinds.count("thrd-callback"));
  EXPECT_FALSE(cKinds.count("cpp-thread-construct"));
}

TEST(SourceFacts, KeepsUnregisteredFrameworkAndPlatformThreadApisUnsupported) {
  auto cpp = std::filesystem::temp_directory_path() / "moa-source-unsupported-thread-apis.cpp";
  { std::ofstream stream(cpp); stream << R"(
    namespace boost { struct thread { template<class F> thread(F) {} }; }
    struct Form { template<class F> void submit(F) {} };
    void worker() {}
    void run() { boost::thread value(worker); Form form; form.submit(worker); }
  )"; }
  auto cppFacts = moa::analyzeSource(request(cpp, "c++20"));
  std::filesystem::remove(cpp);
  EXPECT_EQ(relationKindCount(cppFacts, "unsupported-thread-api"), 2u);
  EXPECT_EQ(relationKindCount(cppFacts, "cpp-thread-construct"), 0u);

  auto c = std::filesystem::temp_directory_path() / "moa-source-clone-unsupported.c";
  { std::ofstream stream(c); stream << R"(
    int clone(int (*callback)(void *), void *stack, int flags, void *argument);
    int worker(void *value) { return value != 0; }
    int run(void) { return clone(worker, 0, 0, 0); }
  )"; }
  auto cFacts = moa::analyzeSource(request(c, "c11"));
  std::filesystem::remove(c);
  EXPECT_EQ(relationKindCount(cFacts, "unsupported-thread-api"), 1u);
}

TEST(SourceFacts, CoversThreadEntryAlternativeAndUnknownSemanticPaths) {
  auto cpp = std::filesystem::temp_directory_path() / "moa-source-thread-entry-alternatives.cpp";
  { std::ofstream stream(cpp); stream << R"(
    #include <future>
    #include <thread>
    void worker(int) {}
    std::jthread make_jthread() { return std::jthread(worker, 1); }
    struct Queue { template<class F> void enqueue(F) {} template<class F> void post(F) {} };
    void run() {
      std::jthread idle;
      std::jthread first(worker, 1);
      std::jthread second;
      second = std::move(first);
      if (second.joinable()) second.detach();
      (void)second.get_id();
      std::jthread factory = make_jthread();
      auto pointer = &worker;
      auto unknown_callable = std::async(std::launch::async, pointer, 1);
      auto unknown_policy = std::async(static_cast<std::launch>(0), worker, 1);
      auto reversed = std::async(std::launch::deferred | std::launch::async, worker, 1);
      auto nested_left = std::async((std::launch::async | std::launch::deferred) | std::launch::async, worker, 1);
      auto nested_right = std::async(std::launch::deferred | (std::launch::async | std::launch::deferred), worker, 1);
      auto deeply_nested = std::async(
          std::launch::async | std::launch::deferred | std::launch::async |
          std::launch::deferred | std::launch::async | std::launch::deferred |
          std::launch::async | std::launch::deferred | std::launch::async |
          std::launch::deferred, worker, 1);
      Queue queue; queue.enqueue(worker); queue.post(worker);
      (void)idle; (void)factory; (void)unknown_callable; (void)reversed;
      (void)unknown_policy; (void)nested_left; (void)nested_right; (void)deeply_nested;
    }
  )"; }
  auto facts = moa::analyzeSource(request(cpp, "c++20"));
  std::filesystem::remove(cpp);
  auto kinds = relationKinds(facts);
  EXPECT_TRUE(kinds.count("cpp-jthread-construct"));
  EXPECT_TRUE(kinds.count("cpp-jthread-move-assign"));
  EXPECT_TRUE(kinds.count("cpp-jthread-move-source"));
  EXPECT_TRUE(kinds.count("cpp-jthread-joinable"));
  EXPECT_TRUE(kinds.count("cpp-jthread-detach"));
  EXPECT_TRUE(kinds.count("cpp-jthread-factory-return"));
  EXPECT_GE(relationKindCount(facts, "unsupported-thread-api"), 2u);
  EXPECT_GE(relationKindCount(facts, "cpp-async-call"), 4u);

  bool jthreadArgument = false, unknownAsync = false;
  for (const auto &item : *facts.getArray("relations")) {
    auto *relation = item.getAsObject();
    jthreadArgument |= relation->getString("kind") == "cpp-jthread-argument";
    unknownAsync |= relation->getString("kind") == "cpp-async-callback" &&
                    relation->getString("status") == "unknown";
  }
  EXPECT_TRUE(jthreadArgument);
  EXPECT_TRUE(unknownAsync);

  auto c = std::filesystem::temp_directory_path() / "moa-source-c11-thread-entry-alternatives.c";
  { std::ofstream stream(c); stream << R"(
    #include <threads.h>
    int left(void *value) { return value != 0; }
    int right(void *value) { return value == 0; }
    int run(int choose) {
      thrd_t handle;
      return thrd_create(&handle, choose ? left : right, 0);
    }
  )"; }
  auto cFacts = moa::analyzeSource(request(c, "c11"));
  std::filesystem::remove(c);
  bool unknownThrd = false;
  for (const auto &item : *cFacts.getArray("relations")) {
    auto *relation = item.getAsObject();
    unknownThrd |= relation->getString("kind") == "thrd-callback" &&
                   relation->getString("status") == "unknown";
  }
  EXPECT_TRUE(unknownThrd);
}

TEST(SourceFacts, MarksUnsupportedStdThreadCallableUnknownWithoutAffectingC) {
  auto cpp = std::filesystem::temp_directory_path() / "moa-source-cpp-thread-unknown.cpp";
  { std::ofstream stream(cpp); stream << R"(
    #include <thread>
    struct ambiguous { void operator()() {} void operator()(int) {} };
    void run() { std::thread thread(ambiguous{}); thread.join(); }
  )"; }
  auto facts = moa::analyzeSource(request(cpp, "c++17"));
  std::filesystem::remove(cpp);
  bool unknown = false;
  for (const auto &item : *facts.getArray("relations")) {
    auto *relation = item.getAsObject();
    if (relation->getString("kind") == "cpp-thread-callback" &&
        relation->getString("status") == "unknown")
      unknown = true;
  }
  EXPECT_TRUE(unknown);

  auto c = std::filesystem::temp_directory_path() / "moa-source-pthread-regression.c";
  { std::ofstream stream(c); stream << R"(
    #include <pthread.h>
    pthread_t handle; void *worker(void *p) { return p; }
    void run(void) { pthread_create(&handle, 0, worker, 0); pthread_join(handle, 0); }
  )"; }
  auto cFacts = moa::analyzeSource(request(c, "c17"));
  std::filesystem::remove(c);
  auto cKinds = relationKinds(cFacts);
  EXPECT_TRUE(cKinds.count("pthread_create"));
  EXPECT_TRUE(cKinds.count("pthread_join"));
  for (const auto &kind : cKinds) EXPECT_FALSE(StringRef(kind).starts_with("cpp-thread-"));
}

TEST(SourceFacts, ExtractsLibcxxInlineNamespaceThread) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-libcxx-thread.cpp";
  { std::ofstream stream(path); stream << R"(
    #include <thread>
    #include <atomic>
    void worker() {}
    std::atomic<int> flag{0};
    void run() { std::thread thread(worker); (void)flag.load(std::memory_order_acquire); thread.join(); }
  )"; }
  auto input = request(path, "c++20");
  input.getObject("profile")->getArray("argv")->push_back("-stdlib=libc++");
  auto facts = moa::analyzeSource(input);
  std::filesystem::remove(path);
  auto kinds = relationKinds(facts);
  EXPECT_EQ(*facts.getString("status"), "complete");
  EXPECT_TRUE(kinds.count("cpp-thread-construct"));
  EXPECT_TRUE(kinds.count("cpp-thread-join"));
  EXPECT_TRUE(kinds.count("atomic-cpp-load"));
}

TEST(SourceFacts, KeepsUnsupportedAndUnresolvedCppThreadOperationsConservative) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-cpp-thread-boundaries.cpp";
  { std::ofstream stream(path); stream << R"(
    #include <thread>
    void worker() {}
    std::thread make_thread() { return std::thread(worker); }
    struct holder { std::thread value; };
    struct virtual_functor { virtual void operator()() {} };
    struct ordinary {
      void join() {}
      ordinary &operator=(const ordinary &) = default;
    };
    void run() {
      std::thread idle;
      holder owned;
      bool member_active = owned.value.joinable();
      bool temporary_active = std::thread{}.joinable();
      void (*pointer)() = worker;
      std::thread indirect(pointer);
      virtual_functor callable;
      std::thread virtual_call(callable);
      std::thread target;
      target = make_thread();
      ordinary first, second;
      first.join();
      first = second;
      (void)idle;
      (void)member_active;
      (void)temporary_active;
      (void)indirect;
      (void)virtual_call;
      (void)target;
    }
  )"; }
  auto facts = moa::analyzeSource(request(path, "c++20"));
  std::filesystem::remove(path);
  EXPECT_EQ(*facts.getString("status"), "complete");

  std::set<std::string> unknownReasons;
  bool memberObject = false;
  bool unresolvedTemporary = false;
  bool unresolvedMoveSource = false;
  for (const auto &item : *facts.getArray("relations")) {
    auto *relation = item.getAsObject();
    auto status = relation->getString("status");
    auto reason = relation->getString("reason");
    if (status && *status == "unknown" && reason) unknownReasons.insert(reason->str());
    if (relation->getString("kind") == "cpp-thread-joinable") {
      if (relation->getString("to")) memberObject = true;
      else unresolvedTemporary = true;
    }
    if (relation->getString("kind") == "cpp-thread-move-source" &&
        status && *status == "unknown")
      unresolvedMoveSource = true;
  }
  EXPECT_TRUE(memberObject);
  EXPECT_TRUE(unresolvedTemporary);
  EXPECT_TRUE(unresolvedMoveSource);
  EXPECT_TRUE(unknownReasons.count("unsupported-cpp-thread-callable"));
  EXPECT_TRUE(unknownReasons.count("unresolved-thread-object"));
  EXPECT_TRUE(unknownReasons.count("unresolved-move-object"));
  EXPECT_EQ(relationKindCount(facts, "cpp-thread-construct"), 6u);
  EXPECT_EQ(relationKindCount(facts, "cpp-thread-join"), 0u)
      << "ordinary::join must not be modeled as std::thread::join";
}

TEST(SourceFacts, ExtractsAdjacentCompoundStatementSequence) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-sequence.cpp";
  { std::ofstream stream(path); stream << "int a; int b; void run(){ a = 1; b = 2; }\n"; }
  auto facts = moa::analyzeSource(request(path, "c++20"));
  std::filesystem::remove(path);
  EXPECT_EQ(relationKindCount(facts, "sequenced-before"), 1u);
}

TEST(SourceFacts, DoesNotSequenceAcrossControlStatements) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-control-sequence.cpp";
  { std::ofstream stream(path); stream << "int a; int b; void run(){ a = 1; if (a) b = 2; a = 3; }\n"; }
  auto facts = moa::analyzeSource(request(path, "c++20"));
  std::filesystem::remove(path);
  EXPECT_EQ(relationKindCount(facts, "sequenced-before"), 0u);
}

TEST(SourceFacts, DeduplicatesRedeclarationsWithTheSamePresumedLocation) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-same-location.c";
  { std::ofstream stream(path); stream << R"(
    #line 1 "generated.h"
    int same(int);
    #line 1 "generated.h"
    int same(int value) { return value; }
  )"; }
  auto facts = moa::analyzeSource(request(path));
  std::set<std::string> identities;
  for (const auto &item : *facts.getArray("nodes"))
    EXPECT_TRUE(identities.insert(item.getAsObject()->getString("id")->str()).second);
  std::filesystem::remove(path);
}

TEST(SourceFacts, EnforcesNodeAndOutputBudgets) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-budget.c";
  { std::ofstream stream(path); stream << "int a; int b; int c;\n"; }
  auto limited = request(path);
  (*limited.getObject("budgets"))["ast_nodes"] = 1;
  auto facts = moa::analyzeSource(limited);
  EXPECT_EQ(*facts.getString("status"), "partial");
  EXPECT_FALSE(facts.getArray("frontier")->empty());

  (*limited.getObject("budgets"))["worker_output_bytes"] = 1;
  auto requestPath = path; requestPath += ".json";
  std::string serialized;
  { raw_string_ostream stream(serialized); stream << json::Value(std::move(limited)); }
  { std::ofstream stream(requestPath); stream << serialized; }
  std::string output, errors;
  raw_string_ostream out(output), err(errors);
  EXPECT_EQ(moa::sourceWorker(requestPath.c_str(), out, err), 1);
  err.flush();
  EXPECT_NE(errors.find("output_limit"), std::string::npos);
  std::filesystem::remove(path); std::filesystem::remove(requestPath);
}

TEST(SourceFacts, WorkerRejectsBrokenJsonAndFailedReplayProfile) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-worker-broken.json";
  { std::ofstream stream(path); stream << "not-json"; }
  std::string output, errors;
  raw_string_ostream out(output), err(errors);
  EXPECT_EQ(moa::sourceWorker(path.c_str(), out, err), 1);
  auto source = std::filesystem::temp_directory_path() / "moa-source-replay.c";
  { std::ofstream stream(source); stream << "int x;\n"; }
  auto failed = request(source);
  (*failed.getObject("profile"))["replay"] = json::Object{
      {"clang_version", "21.1.8"}, {"status", "failed"}, {"diagnostics", json::Array{}}};
  EXPECT_THROW(moa::analyzeSource(failed), std::runtime_error);
  std::filesystem::remove(path); std::filesystem::remove(source);
}

TEST(SourceFacts, CoversLinkageStorageVisibilityAndUnsupportedCalls) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-variants.c";
  { std::ofstream stream(path); stream << R"(
    #include <pthread.h>
    static int internal_value;
    extern int external_value;
    _Thread_local int tls_value;
    int weak_value __attribute__((weak));
    int hidden_value __attribute__((visibility("hidden")));
    int protected_value __attribute__((visibility("protected")));
    struct Box { int field; };
    static inline int inline_fn(int x) { return x; }
    int weak_fn(void) __attribute__((weak));
    int weak_fn(void) { return 1; }
    void *callback(void *p) { return p; }
    void *(*choose(void))(void *);
    int flow(int (*fp)(void), pthread_mutex_t *mutex) {
      auto int automatic = 0;
      register int registered = 1;
      while (automatic < registered) automatic = registered;
      fp();
      pthread_mutex_lock(mutex);
      pthread_mutex_unlock(mutex);
      pthread_join((pthread_t)0, 0);
      pthread_create((pthread_t *)0, 0, &callback, 0);
      pthread_create((pthread_t *)0, 0, choose(), 0);
      return internal_value;
    }
  )"; }
  auto facts = moa::analyzeSource(request(path));
  std::filesystem::remove(path);
  auto kinds = relationKinds(facts);
  EXPECT_TRUE(kinds.count("write"));
  EXPECT_TRUE(kinds.count("thread-handle"));
  EXPECT_TRUE(kinds.count("pthread_mutex_lock"));
  EXPECT_TRUE(kinds.count("pthread_mutex_unlock"));
  EXPECT_TRUE(kinds.count("pthread_join"));
  EXPECT_TRUE(kinds.count("control"));
  bool internal = false, tls = false, field = false, hidden = false, protectedValue = false;
  bool automatic = false, registered = false, weak = false, inlined = false;
  for (const auto &item : *facts.getArray("nodes")) {
    auto *value = item.getAsObject();
    internal |= value->getString("linkage") == "internal";
    tls |= value->getBoolean("tls").value_or(false);
    field |= value->getString("kind") == "field";
    hidden |= value->getString("visibility") == "hidden";
    protectedValue |= value->getString("visibility") == "protected";
    automatic |= value->getString("storage") == "auto";
    registered |= value->getString("storage") == "register";
    weak |= value->getString("definition_kind") == "weak";
    inlined |= value->getString("definition_kind") == "inline";
  }
  EXPECT_TRUE(internal && tls && field && hidden && protectedValue);
  EXPECT_TRUE(automatic && registered && weak && inlined);
}

TEST(SourceFacts, CoversTemplatesAnonymousNamespaceAndRelationBudget) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-template.cpp";
  { std::ofstream stream(path); stream << R"(
    namespace { int local; }
    template <typename T> T twice(T value) { return value + value; }
    int run(void) { int x = twice(2); x = local; while (x) --x; return x; }
    void done(void) { return; }
  )"; }
  auto limited = request(path, "c++20");
  (*limited.getObject("budgets"))["references"] = 1;
  auto facts = moa::analyzeSource(limited);
  std::filesystem::remove(path);
  EXPECT_EQ(*facts.getString("status"), "partial");
  auto *relationCounts = facts.getObject("counts")->getObject("relations");
  EXPECT_EQ(*relationCounts->getInteger("failed"), 1);
  bool anonymous = false, templated = false;
  for (const auto &item : *facts.getArray("nodes")) {
    auto *value = item.getAsObject();
    auto *attributes = value->getArray("attributes");
    anonymous |= std::any_of(attributes->begin(), attributes->end(), [](const json::Value &entry) {
      return entry.getAsString() == "anonymous-namespace";
    });
    templated |= value->getString("definition_kind") == "template";
  }
  EXPECT_TRUE(anonymous && templated);
}

TEST(SourceFacts, RejectsMalformedRequestFieldsAndCompilerArguments) {
  json::Object empty;
  EXPECT_THROW(moa::analyzeSource(empty), std::runtime_error);
  auto source = std::filesystem::temp_directory_path() / "moa-source-request.c";
  { std::ofstream stream(source); stream << "int x;\n"; }
  auto wrongVersion = request(source); wrongVersion["schema_version"] = 3;
  EXPECT_THROW(moa::analyzeSource(wrongVersion), std::runtime_error);
  auto v2 = versionedRequest(source, "c99", "c", "iso");
  EXPECT_EQ(*moa::analyzeSource(v2).getString("status"), "complete");
  auto mismatchedV2 = v2; (*mismatchedV2.getObject("profile"))["schema_version"] = 1;
  EXPECT_THROW(moa::analyzeSource(mismatchedV2), std::runtime_error);
  auto v1WithV2Fields = request(source);
  (*v1WithV2Fields.getObject("profile"))["dialect"] = "iso";
  EXPECT_THROW(moa::analyzeSource(v1WithV2Fields), std::runtime_error);
  auto emptyKind = request(source); emptyKind["kind"] = "";
  EXPECT_THROW(moa::analyzeSource(emptyKind), std::runtime_error);
  auto missingProfile = request(source); missingProfile.erase("profile");
  EXPECT_THROW(moa::analyzeSource(missingProfile), std::runtime_error);
  auto missingBudgets = request(source); missingBudgets.erase("budgets");
  EXPECT_THROW(moa::analyzeSource(missingBudgets), std::runtime_error);
  auto missingSource = request(source); missingSource.getObject("profile")->erase("source");
  EXPECT_THROW(moa::analyzeSource(missingSource), std::runtime_error);
  auto mismatch = request(source); mismatch["source_path"] = "/different.c";
  EXPECT_THROW(moa::analyzeSource(mismatch), std::runtime_error);
  auto noBudget = request(source); noBudget.getObject("budgets")->erase("ast_nodes");
  EXPECT_THROW(moa::analyzeSource(noBudget), std::runtime_error);
  auto zeroBudget = request(source); (*zeroBudget.getObject("budgets"))["ast_nodes"] = 0;
  EXPECT_THROW(moa::analyzeSource(zeroBudget), std::runtime_error);
  auto noArgv = request(source); (*noArgv.getObject("profile"))["argv"] = json::Array{};
  EXPECT_THROW(moa::analyzeSource(noArgv), std::runtime_error);
  auto badArgv = request(source); (*badArgv.getObject("profile"))["argv"] = json::Array{"clang-21", 7};
  EXPECT_THROW(moa::analyzeSource(badArgv), std::runtime_error);
  auto options = request(source);
  (*options.getObject("profile"))["argv"] = json::Array{
      "clang-21", "-emit-llvm", "-c", source.filename().string(), "-o", "ignored.bc", "-std=c11"};
  EXPECT_EQ(*moa::analyzeSource(options).getString("status"), "complete");
  auto absoluteSource = request(source);
  (*absoluteSource.getObject("profile"))["argv"] = json::Array{
      "clang-21", "-c", source.string(), "-std=c11"};
  EXPECT_EQ(*moa::analyzeSource(absoluteSource).getString("status"), "complete");
  std::filesystem::remove(source);
}

TEST(SourceFacts, ExtractsMacroRangesStableOrdinalsAndAbi) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-macros.c";
  { std::ofstream stream(path); stream << R"(
    #define READ(v) ((v) != 0)
    #define NESTED(v) READ(v)
    struct Pair { long left; int right; };
    int flag;
    int observe(void) { if (NESTED(flag)) return flag; return 0; }
  )"; }
  auto facts = moa::analyzeSource(request(path));
  std::filesystem::remove(path);
  bool range = false, macro = false, abi = false, ordinal = false;
  for (const auto &item : *facts.getArray("nodes")) {
    auto *node = item.getAsObject();
    auto *source = node->getObject("source");
    range |= source && source->getObject("spelling_end") && source->getObject("expansion_end");
    ordinal |= source && source->getInteger("ordinal").has_value();
    macro |= !node->getArray("macro_stack")->empty();
    auto *layout = node->getObject("abi");
    abi |= layout && layout->getBoolean("complete").value_or(false) &&
           layout->getInteger("size_bits").value_or(0) > 0 &&
           layout->getInteger("align_bits").value_or(0) > 0;
  }
  EXPECT_TRUE(range && ordinal && macro && abi);
}

TEST(SourceFacts, CoversIncompleteWeakAtomicAndConservativeExpressionCases) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-edge-cases.c";
  { std::ofstream stream(path); stream << R"(
    struct Forward;
    extern struct Forward unresolved_object;
    int weak_initialized __attribute__((weak)) = 1;
    struct Box { int field; } box;
    int my_atomic_helper(void) { return 1; }
    int edge(void) { box.field = my_atomic_helper(); return box.field; }
  )"; }
  auto facts = moa::analyzeSource(request(path));
  bool incomplete = false, weak = false, atomic = relationKinds(facts).count("atomic");
  for (const auto &item : *facts.getArray("nodes")) {
    auto *node = item.getAsObject();
    auto *layout = node->getObject("abi");
    incomplete |= layout && !layout->getBoolean("complete").value_or(true);
    weak |= node->getString("definition_kind") == "weak";
  }
  EXPECT_TRUE(incomplete && weak && atomic);

  auto limited = request(path);
  (*limited.getObject("budgets"))["ast_nodes"] = 1;
  EXPECT_EQ(*moa::analyzeSource(limited).getString("status"), "partial");
  std::filesystem::remove(path);
}

TEST(SourceFacts, ExtractsCanonicalCAtomicOperationsAndOrderRelations) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-c-atomics.c";
  { std::ofstream stream(path); stream << R"(
    #include <stdatomic.h>
    _Atomic int flag;
    struct atomic_holder { _Atomic int field; } holder;
    void init_flag(void) { atomic_init(&flag, 0); }
    int load_flag(void) { return atomic_load_explicit(&flag, memory_order_acquire); }
    int load_pointer(_Atomic int *pointer) { return atomic_load_explicit(pointer, memory_order_acquire); }
    int load_field(void) { return atomic_load_explicit(&holder.field, memory_order_acquire); }
    void store_flag(void) { atomic_store_explicit(&flag, 1, memory_order_release); }
    int exchange_flag(void) { return atomic_exchange_explicit(&flag, 3, memory_order_acq_rel); }
    int lock_free_flag(void) { return atomic_is_lock_free(&flag); }
    int add_flag(void) { return atomic_fetch_add_explicit(&flag, 1, memory_order_relaxed); }
    int cas_flag(void) { int old = 1; return atomic_compare_exchange_weak_explicit(
      &flag, &old, 2, memory_order_acq_rel, memory_order_acquire); }
    void fences(void) { atomic_thread_fence(memory_order_release); atomic_signal_fence(memory_order_acquire); }
  )"; }
  auto facts = moa::analyzeSource(request(path, "c17"));
  std::filesystem::remove(path);
  auto kinds = relationKinds(facts);
  for (StringRef expected : {"atomic-c-load", "atomic-c-store", "atomic-c-rmw", "atomic-c-cas",
                             "atomic-c-thread-fence", "atomic-c-signal-fence", "atomic-order",
                             "atomic-failure-order"})
    EXPECT_TRUE(kinds.count(expected.str())) << expected.str();
  bool canonical = false, cProfile = false, order = false, failureOrder = false;
  for (const auto &entry : *facts.getArray("nodes")) {
    auto *node = entry.getAsObject();
    if (node->getString("kind") != "atomic-expression") continue;
    for (const auto &attribute : *node->getArray("attributes")) {
      auto text = attribute.getAsString().value_or("");
      canonical |= text.starts_with("atomic-operation:");
      cProfile |= text == "atomic-profile:c";
      order |= text == "atomic-order:acq_rel";
      failureOrder |= text == "atomic-failure-order:acquire";
    }
  }
  EXPECT_TRUE(canonical && cProfile && order && failureOrder);
}

TEST(SourceFacts, NormalizesNumericCAtomicOrderConstants) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-c-numeric-orders.c";
  { std::ofstream stream(path); stream << R"(
    #include <stdatomic.h>
    enum other_order { other_acquire = 2 };
    void numeric_orders(void) {
      atomic_thread_fence((memory_order)0);
      atomic_thread_fence((memory_order)1);
      atomic_thread_fence((memory_order)2);
      atomic_thread_fence((memory_order)3);
      atomic_thread_fence((memory_order)4);
      atomic_thread_fence((memory_order)5);
      atomic_thread_fence((memory_order)99);
      atomic_thread_fence(other_acquire);
    }
    void dynamic_order(memory_order order) { atomic_thread_fence(order); }
  )"; }
  auto facts = moa::analyzeSource(request(path, "c17"));
  std::filesystem::remove(path);
  std::set<std::string> orders;
  for (const auto &entry : *facts.getArray("nodes"))
    for (const auto &attribute : *entry.getAsObject()->getArray("attributes")) {
      auto text = attribute.getAsString().value_or("");
      if (text.starts_with("atomic-order:")) orders.insert(text.str());
    }
  for (StringRef expected : {"atomic-order:relaxed", "atomic-order:consume",
                             "atomic-order:acquire", "atomic-order:release",
                             "atomic-order:acq_rel", "atomic-order:seq_cst"})
    EXPECT_TRUE(orders.count(expected.str())) << expected.str();
}

TEST(SourceFacts, AcceptsOnlyCanonicalSystemStdAtomicDeclarations) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-cpp-atomics.cpp";
  { std::ofstream stream(path); stream << R"(
    #include <atomic>
    std::atomic<int> flag{0};
    struct atomic_user { int atomic_load() { return 0; } } user;
    int operations() {
      int expected = 0;
      flag.store(1, std::memory_order_release);
      int value = flag.load(std::memory_order_acquire);
      value += flag.fetch_add(1, std::memory_order_relaxed);
      value += flag.exchange(3, std::memory_order_acq_rel);
      value += flag.compare_exchange_weak(expected, 2, std::memory_order_acq_rel,
                                          std::memory_order_acquire);
      value += std::atomic_load_explicit(&flag, std::memory_order_acquire);
      std::atomic_store_explicit(&flag, value, std::memory_order_release);
      value += std::atomic_fetch_xor_explicit(&flag, 1, std::memory_order_relaxed);
      value += std::atomic_is_lock_free(&flag);
      value += user.atomic_load();
      std::atomic_thread_fence(std::memory_order_release);
      std::atomic_signal_fence(std::memory_order_acquire);
      return value;
    }
  )"; }
  auto facts = moa::analyzeSource(request(path, "c++20"));
  std::filesystem::remove(path);
  auto kinds = relationKinds(facts);
  for (StringRef expected : {"atomic-cpp-load", "atomic-cpp-store", "atomic-cpp-rmw",
                             "atomic-cpp-cas", "atomic-cpp-thread-fence",
                             "atomic-cpp-signal-fence"})
    EXPECT_TRUE(kinds.count(expected.str())) << expected.str();
  // The unsupported std::atomic_is_lock_free operation and the user method
  // remain candidates; neither is promoted to a canonical A6 operation.
  EXPECT_EQ(relationKindCount(facts, "atomic"), 2u);
  bool selected = false, profile = false, order = false, failureOrder = false;
  for (const auto &entry : *facts.getArray("nodes"))
    for (const auto &attribute : *entry.getAsObject()->getArray("attributes")) {
      auto text = attribute.getAsString().value_or("");
      selected |= text.starts_with("selected-declaration:std::");
      profile |= text == "atomic-profile:libstdc++" || text == "atomic-profile:libc++";
      order |= text == "atomic-order:acq_rel";
      failureOrder |= text == "atomic-failure-order:acquire";
    }
  EXPECT_TRUE(selected && profile && order && failureOrder);
}

TEST(SourceFacts, ExtractsCStructUnionFieldReadsWritesAndUpdates) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-c-fields.c";
  { std::ofstream stream(path); stream << R"(
    struct Shared { int flag; int payload; } shared;
    union Value { int word; unsigned raw; } value;
    int update(void) {
      int *payload = &shared.payload;
      shared.payload = value.word;
      ++shared.flag;
      ++*payload;
      *payload = value.word;
      value.raw = (unsigned)shared.flag;
      return shared.payload;
    }
  )"; }
  auto facts = moa::analyzeSource(request(path, "c17"));
  std::filesystem::remove(path);
  size_t fieldReads = 0, fieldWrites = 0;
  std::set<std::string> fieldNames;
  for (const auto &item : *facts.getArray("nodes")) {
    auto *node = item.getAsObject();
    if (node->getString("kind") == "field") fieldNames.insert(node->getString("name")->str());
  }
  for (const auto &item : *facts.getArray("relations")) {
    auto *relation = item.getAsObject();
    auto target = relation->getString("to");
    if (!target) continue;
    bool fieldTarget = std::any_of(facts.getArray("nodes")->begin(), facts.getArray("nodes")->end(),
      [&](const json::Value &entry) {
        auto *node = entry.getAsObject();
        return node->getString("id") == target && node->getString("kind") == "field";
      });
    if (fieldTarget && relation->getString("kind") == "read") ++fieldReads;
    if (fieldTarget && relation->getString("kind") == "write") ++fieldWrites;
  }
  EXPECT_EQ(fieldNames, (std::set<std::string>{"flag", "payload", "raw", "word"}));
  EXPECT_GT(fieldReads, 0u);
  EXPECT_GT(fieldWrites, 0u);
}

TEST(SourceFacts, HandlesPthreadPrototypeWithoutTrackedArgument) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-pthread-prototype.c";
  { std::ofstream stream(path); stream << "int pthread_join(void); int call_join(void) { return pthread_join(); }\n"; }
  auto facts = moa::analyzeSource(request(path));
  std::filesystem::remove(path);
  EXPECT_TRUE(relationKinds(facts).count("pthread_join"));
  EXPECT_EQ(*facts.getString("status"), "complete");
}

TEST(SourceFacts, ExtractsCppRaiiMutexOwnerLifecycleAndUnsupportedCalls) {
  auto path = std::filesystem::temp_directory_path() / "moa-source-cpp-raii.cpp";
  { std::ofstream stream(path); stream << R"(
    #include <mutex>
    std::mutex global_mutex;
    struct Holder { int ordinary; std::mutex field; } holder;
    extern std::unique_lock<std::mutex> external_owner;
    std::unique_lock<std::mutex> make_empty() { return {}; }
    void guarded() { std::lock_guard<std::mutex> guard(global_mutex); }
    void deferred() {
      std::unique_lock<std::mutex> owner(global_mutex, std::defer_lock);
      std::unique_lock<std::mutex> empty;
      owner.lock(); (void)owner.owns_lock(); (void)owner.mutex(); owner.unlock();
      owner.swap(empty); owner.release();
      (void)std::unique_lock<std::mutex>(global_mutex).owns_lock();
    }
    void grouped(std::mutex &other) { std::scoped_lock lock(global_mutex, other); }
    void ownership_boundaries() {
      std::unique_lock<std::mutex> empty;
      std::unique_lock<std::mutex> deferred_owner(global_mutex, std::defer_lock);
      std::unique_lock<std::mutex> moved(std::move(deferred_owner));
      std::unique_lock<std::mutex> unresolved_move(
          static_cast<std::unique_lock<std::mutex>&&>(make_empty()));
      auto returned_owner = make_empty();
      empty = std::move(moved);
      empty = make_empty();
      std::unique_lock<std::mutex> adopted(global_mutex, std::adopt_lock);
      std::unique_lock<std::mutex> attempted(global_mutex, std::try_to_lock);
    }
  )"; }
  auto facts = moa::analyzeSource(request(path, "c++17"));
  std::filesystem::remove(path);
  auto kinds = relationKinds(facts);
  for (StringRef expected : {"cpp-raii-mutex-object", "cpp-raii-owner-object",
                             "cpp-raii-owner-construct", "cpp-raii-owner-destruct",
                             "cpp-raii-mutex-argument", "cpp-raii-owner-lock",
                             "cpp-raii-owner-unlock", "cpp-raii-owner-owns-lock",
                             "cpp-raii-owner-unsupported"})
    EXPECT_TRUE(kinds.count(expected.str())) << expected.str();
  EXPECT_GE(relationKindCount(facts, "cpp-raii-mutex-argument"), 3u);
  EXPECT_GE(relationKindCount(facts, "cpp-raii-owner-move"), 2u);
  EXPECT_GE(relationKindCount(facts, "cpp-raii-owner-unsupported"), 2u);
  EXPECT_EQ(*facts.getString("status"), "complete");
}

TEST(SourceFacts, WorkerCoversMissingNonObjectAndSuccessfulOutput) {
  std::string output, errors;
  raw_string_ostream out(output), err(errors);
  EXPECT_EQ(moa::sourceWorker("/tmp/definitely-missing-source-request.json", out, err), 1);
  auto arrayPath = std::filesystem::temp_directory_path() / "moa-source-array.json";
  { std::ofstream stream(arrayPath); stream << "[]"; }
  EXPECT_EQ(moa::sourceWorker(arrayPath.c_str(), out, err), 1);
  auto source = std::filesystem::temp_directory_path() / "moa-source-worker-success.c";
  { std::ofstream stream(source); stream << "int x;\n"; }
  auto valid = request(source);
  auto requestPath = source; requestPath += ".json";
  std::string serialized;
  { raw_string_ostream stream(serialized); stream << json::Value(std::move(valid)); }
  { std::ofstream stream(requestPath); stream << serialized; }
  std::string successOutput, successErrors;
  raw_string_ostream successOut(successOutput), successErr(successErrors);
  EXPECT_EQ(moa::sourceWorker(requestPath.c_str(), successOut, successErr), 0);
  successOut.flush();
  EXPECT_NE(successOutput.find("SourceSemanticFacts"), std::string::npos);
  std::filesystem::remove(arrayPath); std::filesystem::remove(source);
  std::filesystem::remove(requestPath);
}

TEST(SourceFacts, ExtractsTypedLlvmBindingSymbolsAndBudgetFrontier) {
  auto path = std::filesystem::temp_directory_path() / "moa-binding-facts.ll";
  { std::ofstream stream(path); stream << R"(
    target triple = "x86_64-pc-linux-gnu"
    target datalayout = "e-p:64:64-i64:64-n8:16:32:64-S128"
    $group = comdat any
    @flag = hidden thread_local global i32 0, align 4
    @internal_value = internal global i32 0
    @external_weak_value = extern_weak global i32
    @common_value = common global i32 0, align 4
    @available_value = available_externally global i32 0
    @linkonce_value = linkonce global i32 0
    @weak_value = weak global i64 0, comdat($group), align 8
    declare i32 @declared(i32)
    define protected i32 @defined(i32 %x) { ret i32 %x }
  )"; }
  auto facts = moa::analyzeLLVMSourceBinding(irRequest(path));
  EXPECT_EQ(*facts.getString("status"), "complete");
  EXPECT_EQ(*facts.getString("target"), "x86_64-pc-linux-gnu");
  EXPECT_EQ(facts.getArray("symbols")->size(), 9u);
  bool tls = false, comdat = false, declaration = false, typed = false;
  for (const auto &item : *facts.getArray("symbols")) {
    auto *symbol = item.getAsObject();
    tls |= symbol->getBoolean("tls").value_or(false);
    comdat |= symbol->getBoolean("comdat").value_or(false);
    declaration |= !symbol->getBoolean("definition").value_or(true);
    typed |= symbol->getString("canonical_type") == "i32";
  }
  EXPECT_TRUE(tls && comdat && declaration && typed);
  auto limited = irRequest(path);
  (*limited.getObject("budgets"))["binding_candidates"] = 1;
  auto partial = moa::analyzeLLVMSourceBinding(limited);
  EXPECT_EQ(*partial.getString("status"), "partial");
  EXPECT_FALSE(partial.getArray("frontier")->empty());
  std::filesystem::remove(path);
}

TEST(SourceFacts, LlvmBindingWorkerRejectsInvalidInputsAndWritesFacts) {
  json::Object invalid{{"schema_version", 1}, {"kind", "other"}};
  EXPECT_THROW(moa::analyzeLLVMSourceBinding(invalid), std::runtime_error);
  auto wrongVersion = irRequest("/tmp/unused.ll"); wrongVersion["schema_version"] = 2;
  EXPECT_THROW(moa::analyzeLLVMSourceBinding(wrongVersion), std::runtime_error);
  auto noBitcode = irRequest("/tmp/unused.ll"); noBitcode.erase("bitcode");
  EXPECT_THROW(moa::analyzeLLVMSourceBinding(noBitcode), std::runtime_error);
  auto noBudgets = irRequest("/tmp/unused.ll"); noBudgets.erase("budgets");
  EXPECT_THROW(moa::analyzeLLVMSourceBinding(noBudgets), std::runtime_error);
  auto missing = irRequest("/tmp/moa-missing-binding.bc");
  EXPECT_THROW(moa::analyzeLLVMSourceBinding(missing), std::runtime_error);

  auto ir = std::filesystem::temp_directory_path() / "moa-binding-worker.ll";
  { std::ofstream stream(ir); stream << "target triple = \"\"\n@x = global i32 0\n"; }
  EXPECT_EQ(*moa::analyzeLLVMSourceBinding(irRequest(ir)).getString("target"), "unknown");
  auto requestPath = ir; requestPath += ".json";
  std::string serialized;
  { raw_string_ostream stream(serialized); stream << json::Value(irRequest(ir)); }
  { std::ofstream stream(requestPath); stream << serialized; }
  std::string output, errors;
  raw_string_ostream out(output), err(errors);
  EXPECT_EQ(moa::irBindingWorker(requestPath.c_str(), out, err), 0);
  out.flush();
  EXPECT_NE(output.find("LLVMSourceBindingFacts"), std::string::npos);
  auto limited = irRequest(ir);
  (*limited.getObject("budgets"))["worker_output_bytes"] = 1;
  serialized.clear();
  { raw_string_ostream stream(serialized); stream << json::Value(std::move(limited)); }
  { std::ofstream stream(requestPath); stream << serialized; }
  EXPECT_EQ(moa::irBindingWorker(requestPath.c_str(), out, err), 1);
  EXPECT_EQ(moa::irBindingWorker("/tmp/moa-missing-ir-request.json", out, err), 1);
  { std::ofstream stream(requestPath); stream << "[]"; }
  EXPECT_EQ(moa::irBindingWorker(requestPath.c_str(), out, err), 1);
  std::filesystem::remove(ir); std::filesystem::remove(requestPath);
}
