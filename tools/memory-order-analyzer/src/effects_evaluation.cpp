#include "effects.h"
#include "effect_interpreter.h"
#include "ir_identity.h"
#include <stdexcept>
#include <vector>

using namespace llvm;
namespace moa {
namespace {
void require(bool condition, const char *message) {
  if (!condition) throw std::runtime_error(message);
}
void bounded(const json::Object &request) {
  struct Pending { const json::Value *value; unsigned depth, values; };
  std::vector<Pending> work;
  for (auto &field : request) work.push_back({&field.second, 1, 0});
  auto limit = *request.getObject("budgets")->getInteger("local_steps");
  size_t count = 0;
  while (!work.empty()) {
    auto [item, depth, values] = work.back(); work.pop_back();
    require(depth <= 256, "evaluation_budget: nested input");
    if (auto *object = item->getAsObject()) {
      auto kind = object->getString("kind");
      if (kind && (*kind == "integer" || *kind == "object" || *kind == "parameter" || *kind == "null" ||
                   *kind == "poison" || *kind == "undef" || *kind == "freeze" || *kind == "expression" ||
                   (*kind == "unknown" && !object->get("call")))) {
        require(++count <= size_t(limit) && ++values <= std::min(int64_t(64), limit), "evaluation_budget: value tree");
      }
      for (const auto &field : *object) work.push_back({&field.second, depth + 1, values});
    } else if (auto *array = item->getAsArray()) {
      for (const auto &child : *array) work.push_back({&child, depth + 1, values});
    }
  }
}
} // namespace

json::Object evaluationPlan(Module &module, const json::Object &request, const json::Array *summaries) {
  // Envelope/consumed-field validation is done by evaluationBatch. Full schema,
  // dependency closure and binding validation also run in the Python client.
  bounded(request);
  const auto &reference = *request.getObject("function");
  const auto artifact = reference.getString("artifact_key")->str();
  const auto context = request.getString("context_id")->str();
  const auto activation = request.getString("invocation_id")->str();
  auto ids = originalIdentities(module, artifact);
  Function *function = nullptr;
  for (auto &candidate : module)
    if (ids[&candidate] == reference.getString("id")) function = &candidate;
  require(function && !function->isDeclaration(), "analysis_request: missing evaluation definition");
  require(function->arg_size() == request.getArray("arguments")->size(), "analysis_request: argument count mismatch");
  bool bound = false;
  for (const auto &item : *request.getArray("invocations")) {
    auto *entry = item.getAsObject();
    require(entry && entry->getString("id"), "analysis_request: invalid invocation entry");
    if (entry->getString("id") == activation) {
      require(!bound && entry->getString("context_id") == context && entry->getObject("function") &&
              json::Value(json::Object(*entry->getObject("function"))) == json::Value(json::Object(reference)),
              "analysis_request: activation mismatch");
      bound = true;
    }
  }
  require(bound, "analysis_request: missing activation");
  auto result = interpretLocal(module, *function, request, ids, summaries);
  result["schema_version"] = 1; result["kind"] = "LocalEvaluationResult"; result["analysis_version"] = "0.1.0";
  result["policy_id"] = "scoped-effects-v1"; result["request"] = json::Object(request);
  result["request_hash"] = analysisDigest(json::Object(request)); result["scope_id"] = *request.get("scope_id");
  result["context_id"] = context; result["budgets"] = json::Object(*request.getObject("budgets"));
  return result;
}
} // namespace moa
