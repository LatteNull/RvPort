#include "threads.h"
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
std::string digest(StringRef bytes) {
  return toHex(SHA256::hash(arrayRefFromStringRef(bytes)), true);
}
std::unique_ptr<MemoryBuffer> buffer(const std::string &path) {
  auto result = MemoryBuffer::getFile(path);
  if (!result) throw std::runtime_error("input_unreadable: " + result.getError().message());
  return std::move(*result);
}
void hashField(const json::Object &object, StringRef field) {
  auto value = object.getString(field);
  require(value && value->size() == 64 && value->find_first_not_of("0123456789abcdef") == StringRef::npos,
          "thread_request: invalid hash");
}
json::Object failure(const std::exception &error) {
  StringRef message(error.what());
  return json::Object{{"code", message.split(':').first.str()}, {"detail", message.str()}};
}
json::Object readJob(const json::Object &job) {
  const auto path = job.getString("path")->str();
  const auto &origin = *job.getObject("origin");
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
  auto result = threadFacts(*module, origin, *job.getObject("budgets"));
  require(digest(buffer(path)->getBuffer()) == *origin.getString("module_hash"), "inputs_changed: BC changed during analysis");
  return result;
}
} // namespace

json::Object threadBatch(const json::Object &request) {
  auto protocol = threadProtocol();
  auto *provided = request.getObject("protocol");
  auto *jobs = request.getArray("jobs");
  require(request.size() == 2 && provided &&
          json::Value(json::Object(*provided)) == json::Value(json::Object(protocol)) &&
          jobs && !jobs->empty(), "thread_request: invalid batch/protocol");
  auto &limits = *protocol.getObject("budgets");
  require(jobs->size() <= size_t(*limits.getInteger("thread_contexts")), "thread_request: job limit");
  std::set<std::string> ids;
  size_t outputLimit = *limits.getInteger("worker_output_bytes");
  for (auto &item : *jobs) {
    auto *job = item.getAsObject();
    require(job && job->size() == 4, "thread_request: invalid job");
    auto id = job->getString("id"), path = job->getString("path");
    auto *origin = job->getObject("origin"), *budgets = job->getObject("budgets");
    require(id && !id->empty() && ids.insert(id->str()).second && path && !path->empty() &&
            !path->contains('\0') && origin && budgets, "thread_request: invalid job fields");
    require(origin->size() == 6 && origin->getString("extractor_version") == "0.2.0" &&
            origin->getString("llvm_version") == "21.1.8", "thread_request: origin protocol mismatch");
    for (auto field : {"artifact_key", "module_hash", "facts_hash"}) hashField(*origin, field);
    auto profile = origin->getString("profile");
    require(profile && (*profile == "source-preserving" || *profile == "build-faithful" ||
            *profile == "imported" || *profile == "linked"), "thread_request: invalid profile");
    require(budgets->size() == limits.size(), "thread_request: invalid budgets");
    for (auto &limit : limits) {
      auto value = budgets->getInteger(limit.first);
      require(value && *value > 0 && *value <= *limit.second.getAsInteger(), "thread_request: invalid budget value");
    }
    outputLimit = std::min(outputLimit, size_t(*budgets->getInteger("worker_output_bytes")));
  }
  json::Array results;
  for (auto &item : *jobs) {
    auto &job = *item.getAsObject();
    json::Object entry{{"id", job.getString("id")->str()}, {"result", nullptr}, {"error", nullptr}};
    try { entry["result"] = readJob(job); }
    catch (const std::exception &error) { entry["error"] = failure(error); }
    results.push_back(std::move(entry));
  }
  json::Object result{{"protocol_version", 1}, {"results", std::move(results)}, {"error", nullptr}};
  std::string output;
  raw_string_ostream stream(output);
  stream << json::Value(json::Object(result));
  require(output.size() <= outputLimit, "worker_output_limit: thread batch exceeds budget");
  return result;
}

int threadWorker(const std::string &path, raw_ostream &out, raw_ostream &err) {
  try {
    auto input = MemoryBuffer::getFile(path);
    require(bool(input), "input_unreadable: cannot read thread request");
    auto parsed = json::parse((*input)->getBuffer());
    require(bool(parsed) && parsed->getAsObject(), "thread_request: expected JSON object");
    out << json::Value(threadBatch(*parsed->getAsObject())) << "\n";
    return 0;
  } catch (const std::exception &error) {
    err << error.what() << "\n";
    return 1;
  }
}
} // namespace moa
