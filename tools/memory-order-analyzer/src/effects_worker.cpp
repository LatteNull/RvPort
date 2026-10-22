#include "effects.h"
#include <llvm/ADT/StringExtras.h>
#include <llvm/IR/Verifier.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/SHA256.h>
#include <llvm/Support/SourceMgr.h>
#include <set>
#include <stdexcept>

using namespace llvm;
namespace moa {
namespace {
void require(bool condition, const char *message) {
  if (!condition) throw std::runtime_error(message);
}
std::string digest(StringRef bytes) { return toHex(SHA256::hash(arrayRefFromStringRef(bytes)), true); }
std::unique_ptr<MemoryBuffer> buffer(const std::string &path) {
  auto result = MemoryBuffer::getFile(path);
  if (!result) throw std::runtime_error("input_unreadable: " + result.getError().message());
  return std::move(*result);
}
void hashField(const json::Object &object, StringRef field) {
  auto value = object.getString(field);
  require(value && value->size() == 64 && value->find_first_not_of("0123456789abcdef") == StringRef::npos,
          "analysis_request: invalid hash");
}
json::Object failure(const std::exception &error) {
  StringRef message(error.what());
  return json::Object{{"code", message.split(':').first.str()}, {"detail", message.str()}};
}
json::Object readLocal(const json::Object &job, const json::Object *evaluation = nullptr,
                       const json::Array *summaries = nullptr) {
  auto &origin = *job.getObject("origin");
  const auto path = job.getString("path")->str();
  auto before = buffer(path);
  require(digest(before->getBuffer()) == *origin.getString("module_hash"), "inputs_changed: BC hash mismatch");
  require(before->getBuffer().starts_with(StringRef("BC\xc0\xde", 4)), "format_invalid: expected bitcode");
  LLVMContext context;
  SMDiagnostic diagnostic;
  auto module = parseIR(before->getMemBufferRef(), diagnostic, context);
  require(bool(module), "reader_failed: invalid bitcode");
  std::string errors;
  raw_string_ostream stream(errors);
  require(!verifyModule(*module, &stream), "verify_failed: invalid module");
  auto result = localMetadata(*module, origin, *job.getObject("budgets"));
  if (evaluation) {
    // P1 source mapping is enriched by the collector using its input manifest.
    // Its complete digest is checked by the client, not reconstructed from BC.
    const json::Object *dependency = nullptr;
    for (auto &item : *evaluation->getArray("local_dependencies")) {
      const auto *entry = item.getAsObject();
      require(entry && entry->size() == 2, "analysis_request: invalid local dependency");
      hashField(*entry, "artifact_key"); hashField(*entry, "digest");
      if (entry->getString("artifact_key") == origin.getString("artifact_key")) {
        require(!dependency, "analysis_request: duplicate local dependency");
        dependency = entry;
      }
    }
    require(dependency && analysisDigest(json::Object(result)) == *dependency->getString("digest"),
            "inputs_changed: local supplement generation mismatch");
    result = evaluationPlan(*module, *evaluation, summaries);
  }
  require(digest(buffer(path)->getBuffer()) == *origin.getString("module_hash"), "inputs_changed: BC changed during analysis");
  return result;
}
} // namespace

static json::Object localBatchImpl(const json::Object &request, const json::Array *evaluations = nullptr) {
  auto protocol = analysisProtocol();
  auto *provided = request.getObject("protocol");
  auto *jobs = request.getArray("jobs");
  require(request.size() == 2 && provided && json::Value(json::Object(*provided)) == json::Value(json::Object(protocol)) && jobs && !jobs->empty(),
          "analysis_request: invalid batch/protocol");
  auto &limits = *protocol.getObject("budgets");
  require(jobs->size() <= size_t(*limits.getInteger("contexts_per_request")), "analysis_request: job limit");
  std::set<std::string> ids;
  size_t outputLimit = *limits.getInteger("worker_output_bytes");
  for (auto &item : *jobs) {
    auto *job = item.getAsObject();
    require(job && job->size() == 4, "analysis_request: invalid job");
    auto id = job->getString("id"), path = job->getString("path");
    auto *origin = job->getObject("origin"), *budgets = job->getObject("budgets");
    require(id && !id->empty() && ids.insert(id->str()).second && path && !path->empty() && !path->contains('\0') && origin && budgets,
            "analysis_request: invalid job fields");
    require(origin->size() == 6 && origin->getString("extractor_version") == "0.2.0" &&
            origin->getString("llvm_version") == "21.1.8", "analysis_request: origin protocol mismatch");
    for (auto field : {"artifact_key", "module_hash", "facts_hash"}) hashField(*origin, field);
    auto profile = origin->getString("profile");
    require(profile && (*profile == "source-preserving" || *profile == "build-faithful" || *profile == "imported" || *profile == "linked"),
            "analysis_request: invalid profile");
    require(budgets->size() == limits.size(), "analysis_request: invalid budgets");
    for (auto &limit : limits) {
      auto n = budgets->getInteger(limit.first);
      require(n && *n > 0 && *n <= *limit.second.getAsInteger(), "analysis_request: invalid budget value");
    }
    outputLimit = std::min(outputLimit, size_t(*budgets->getInteger("worker_output_bytes")));
    if (evaluations)
      require(jobs->size() <= size_t(*budgets->getInteger("contexts_per_request")), "analysis_request: tightened evaluation job limit");
  }
  json::Array results;
  size_t index = 0;
  for (auto &item : *jobs) {
    auto &job = *item.getAsObject();
    json::Object entry{{"id", job.getString("id")->str()}, {"result", nullptr}, {"error", nullptr}};
    const auto *evaluationJob = evaluations ? (*evaluations)[index++].getAsObject() : nullptr;
    const auto *evaluation = evaluationJob ? evaluationJob->getObject("request") : nullptr;
    const auto *summaries = evaluationJob ? evaluationJob->getArray("summaries") : nullptr;
    try { entry["result"] = readLocal(job, evaluation, summaries); }
    catch (const std::exception &error) { entry["error"] = failure(error); }
    results.push_back(std::move(entry));
  }
  json::Object result{{"protocol_version", 1}, {"results", std::move(results)}, {"error", nullptr}};
  std::string output;
  raw_string_ostream stream(output);
  stream << json::Value(json::Object(result));
  require(output.size() <= outputLimit, "worker_output_limit: batch result exceeds budget");
  return result;
}

json::Object localBatch(const json::Object &request) { return localBatchImpl(request); }

std::string analysisDigest(const json::Value &value) {
  std::string bytes;
  raw_string_ostream out(bytes);
  out << value; // LLVM compact serialization sorts object keys deterministically.
  return digest(bytes);
}

json::Object evaluationBatch(const json::Object &request) {
  const auto *jobs = request.getArray("jobs");
  require(request.size() == 2 && jobs && !jobs->empty(), "analysis_request: invalid evaluation batch");
  auto protocol = analysisProtocol();
  require(request.getObject("protocol") && json::Value(json::Object(*request.getObject("protocol"))) == json::Value(json::Object(protocol)),
          "analysis_request: evaluation protocol mismatch");
  json::Array metadataJobs;
  for (const auto &item : *jobs) {
    const auto *job = item.getAsObject();
    require(job && job->size() == 4 && job->getString("id") && job->getString("path") &&
            job->getObject("request") && job->getArray("summaries"),
            "analysis_request: invalid evaluation job");
    const auto &evaluation = *job->getObject("request");
    require(evaluation.size() == 16 && evaluation.getInteger("schema_version") == 1 &&
            evaluation.getString("kind") == "LocalEvaluationRequest" && evaluation.getString("analysis_version") == "0.1.0" &&
            evaluation.getString("policy_id") == "scoped-effects-v1", "analysis_request: evaluation version or fields");
    for (auto field : {"arguments", "invocations", "origins", "local_dependencies", "dependencies", "adoptions", "call_bindings"})
      require(evaluation.getArray(field), "analysis_request: missing evaluation array");
    require(evaluation.getObject("budgets") && evaluation.getObject("function") && evaluation.getString("context_id") &&
            !evaluation.getString("context_id")->empty() && evaluation.getString("invocation_id") &&
            !evaluation.getString("invocation_id")->empty() && !evaluation.getArray("invocations")->empty(),
            "analysis_request: invalid evaluation bindings");
    hashField(evaluation, "scope_id");
    const auto &function = *evaluation.getObject("function");
    hashField(function, "artifact_key");
    require(function.size() == 3 && function.getString("id") && function.get("function_id") &&
            function.get("function_id")->getAsNull(), "analysis_request: invalid evaluation function");
    const json::Object *origin = nullptr;
    std::set<std::string> seen;
    for (const auto &entry : *evaluation.getArray("origins")) {
      const auto *candidate = entry.getAsObject();
      require(candidate, "analysis_request: invalid evaluation origin");
      hashField(*candidate, "artifact_key");
      require(seen.insert(candidate->getString("artifact_key")->str()).second, "analysis_request: duplicate evaluation origin");
      if (candidate->getString("artifact_key") == function.getString("artifact_key")) origin = candidate;
    }
    require(origin, "analysis_request: missing evaluation origin");
    metadataJobs.push_back(json::Object{{"id", *job->get("id")}, {"path", *job->get("path")},
       {"origin", json::Object(*origin)}, {"budgets", json::Object(*evaluation.getObject("budgets"))}});
  }
  // Reuse the strict metadata envelope validation, without reading any BC twice.
  json::Object metadata{{"protocol", std::move(protocol)}, {"jobs", std::move(metadataJobs)}};
  return localBatchImpl(metadata, jobs);
}

int analysisWorker(const std::string &path, raw_ostream &out, raw_ostream &err, bool evaluate) {
  try {
    auto input = buffer(path);
    require(input->getBufferSize() <= 16777216, "analysis_request: request exceeds transport limit");
    auto parsed = json::parse(input->getBuffer());
    if (!parsed) { consumeError(parsed.takeError()); throw std::runtime_error("analysis_request: invalid JSON"); }
    require(parsed->getAsObject(), "analysis_request: expected object");
    out << json::Value(evaluate ? evaluationBatch(*parsed->getAsObject()) : localBatch(*parsed->getAsObject())) << "\n";
    return 0;
  } catch (const std::exception &error) {
    out << json::Value(json::Object{{"protocol_version", 1}, {"results", json::Array{}}, {"error", failure(error)}}) << "\n";
    err << error.what() << "\n";
    return 1;
  }
}
} // namespace moa
