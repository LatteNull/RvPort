#include "threads.h"
#include "effects.h"
#include "ir_identity.h"
#include <llvm/Analysis/CFG.h>
#include <llvm/Analysis/LoopInfo.h>
#include <llvm/Analysis/PostDominators.h>
#include <llvm/Analysis/ValueTracking.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/Dominators.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/Metadata.h>
#include <llvm/Support/SHA256.h>
#include <llvm/ADT/StringExtras.h>
#include <algorithm>
#include <set>

using namespace llvm;
namespace moa {
namespace {
std::string typeText(Type *type) {
  std::string text;
  raw_string_ostream out(text);
  type->print(out);
  return text;
}

json::Object sourceRef(StringRef artifact, json::Value function, StringRef id) {
  return json::Object{{"artifact_key", artifact.str()}, {"function_id", std::move(function)}, {"id", id.str()}};
}

json::Object analysisRef(StringRef artifact, StringRef function, StringRef id) {
  return json::Object{{"artifact_key", artifact.str()}, {"function_id", function.str()},
                      {"analysis_id", id.str()}};
}

json::Value valueRef(Value *value, StringRef artifact, StringRef function,
                     const DenseMap<const Value *, std::string> &ids) {
  if (!value) return nullptr;
  Value *base = value->stripPointerCasts();
  if (isa<GlobalValue>(base)) {
    auto id = ids.lookup(base);
    return id.empty() ? json::Value(nullptr) : json::Value(sourceRef(artifact, nullptr, id));
  }
  auto id = ids.lookup(base);
  return id.empty() ? json::Value(nullptr) : json::Value(sourceRef(artifact, function.str(), id));
}

bool callbackTargets(Value *value, StringRef artifact, StringRef function,
                     const DenseMap<const Value *, std::string> &ids,
                     size_t limit, json::Array &result, std::set<std::string> &seen) {
  if (!value) return true;
  Value *base = value->stripPointerCasts();
  if (auto *target = dyn_cast<Function>(base)) {
    auto reference = valueRef(target, artifact, function, ids);
    if (reference.getAsNull()) return false;
    std::string key;
    raw_string_ostream out(key);
    out << reference;
    if (seen.insert(key).second) {
      if (result.size() >= limit) return false;
      result.push_back(std::move(reference));
    }
    return true;
  }
  if (auto *select = dyn_cast<SelectInst>(base))
    return callbackTargets(select->getTrueValue(), artifact, function, ids, limit, result, seen) &&
           callbackTargets(select->getFalseValue(), artifact, function, ids, limit, result, seen);
  if (auto *phi = dyn_cast<PHINode>(base)) {
    for (Value *incoming : phi->incoming_values())
      if (!callbackTargets(incoming, artifact, function, ids, limit, result, seen)) return false;
    return true;
  }
  return false;
}

json::Object bilingual(StringRef code, StringRef detail, StringRef english,
                       json::Value source = nullptr) {
  return json::Object{{"code", code.str()}, {"detail", detail.str()}, {"detail_en", english.str()},
    {"suggestion", nullptr}, {"suggestion_en", nullptr}, {"source", std::move(source)},
    {"thread_context_id", nullptr}, {"thread_instance_id", nullptr}};
}

bool supportedName(StringRef name) {
  return name == "pthread_create" || name == "pthread_join" ||
         name == "pthread_mutex_lock" || name == "pthread_mutex_unlock" ||
         name == "thrd_create";
}

unsigned expectedParameters(StringRef name) {
  if (name == "pthread_create") return 4;
  if (name == "thrd_create") return 3;
  if (name == "pthread_join") return 2;
  return 1;
}

json::Array callbackMetadata(Function *target) {
  json::Array result;
  if (!target) return result;
  auto *metadata = target->getMetadata("callback");
  if (!metadata) return result;
  for (const MDOperand &operand : metadata->operands()) {
    auto *entry = dyn_cast_or_null<MDNode>(operand.get());
    if (!entry) continue;
    json::Array values;
    bool valid = true;
    for (const MDOperand &field : entry->operands()) {
      auto *constant = dyn_cast_or_null<ConstantAsMetadata>(field.get());
      auto *integer = constant ? dyn_cast<ConstantInt>(constant->getValue()) : nullptr;
      if (!integer || !integer->getValue().isSignedIntN(64)) {
        valid = false;
        break;
      }
      values.push_back(integer->getSExtValue());
    }
    if (valid) result.push_back(std::move(values));
  }
  return result;
}

std::string initializerFingerprint(Value *value, Module &module) {
  auto *global = dyn_cast_or_null<GlobalVariable>(getUnderlyingObject(value));
  if (!global || !global->hasInitializer()) return {};
  std::string text;
  raw_string_ostream out(text);
  out << module.getTargetTriple().str() << ';' << module.getDataLayoutStr() << ';';
  global->getInitializer()->print(out);
  out.flush();
  auto digest = toHex(SHA256::hash(arrayRefFromStringRef(text)), true);
  return (global->getInitializer()->isNullValue() ? "zero-static:" : "static:") + digest;
}

struct Limit {
  int64_t remaining;
  bool exhausted = false;
  bool take() {
    if (remaining <= 0) {
      exhausted = true;
      return false;
    }
    --remaining;
    return true;
  }
};

struct Event {
  Instruction *instruction;
  json::Object source;
  json::Object block;
  unsigned index;
  bool repeated;
};

bool relevant(Instruction &instruction) {
  return instruction.mayReadOrWriteMemory() || isa<CallBase>(instruction) ||
         isa<FenceInst>(instruction);
}

json::Object provenance(Instruction &instruction, StringRef kind, json::Value value,
                        json::Value object, StringRef artifact, StringRef function,
                        const DenseMap<const Value *, std::string> &ids,
                        StringRef status, json::Value reason) {
  auto source = sourceRef(artifact, function.str(), ids.lookup(&instruction));
  return json::Object{{"source", json::Object(source)}, {"kind", kind.str()},
    {"value", std::move(value)}, {"object", std::move(object)},
    {"proof", json::Array{json::Object(source)}}, {"status", status.str()},
    {"reason", std::move(reason)}};
}
} // namespace

json::Object threadFacts(Module &module, const json::Object &origin,
                         const json::Object &budgets) {
  const auto artifact = origin.getString("artifact_key")->str();
  auto ids = originalIdentities(module, artifact);
  Limit local{*budgets.getInteger("local_steps")};
  int64_t graphRemaining = *budgets.getInteger("graph_items");
  json::Array calls, provenanceItems, localEvidence, localDiagnostics, localFrontier;
  json::Array orderNodes, orderEdges, orderEvidence, orderDiagnostics, orderFrontier;
  std::vector<Event> events;

  for (auto &global : module.globals()) {
    if (!local.take()) break;
    if (!global.hasInitializer()) continue;
    auto source = sourceRef(artifact, nullptr, ids.lookup(&global));
    auto fingerprint = initializerFingerprint(&global, module);
    provenanceItems.push_back(json::Object{{"source", json::Object(source)}, {"kind", "initializer"},
      {"value", nullptr}, {"object", json::Object(source)}, {"proof", json::Array{json::Object(source)}},
      {"status", fingerprint.starts_with("zero-static:") ? "exact" : "candidate"},
      {"reason", fingerprint.empty() ? json::Value("initializer-unavailable") : json::Value(fingerprint)}});
  }

  for (auto &function : module) {
    if (function.isDeclaration() || local.exhausted) continue;
    const auto fid = ids.lookup(&function);
    DominatorTree dt(function);
    PostDominatorTree pdt(function);
    LoopInfo loops(dt);
    for (auto &block : function) {
      unsigned index = 0;
      for (auto &instruction : block) {
        if (!local.take()) break;
        const auto src = sourceRef(artifact, fid, ids.lookup(&instruction));
        if (relevant(instruction) && graphRemaining > 0) {
          --graphRemaining;
          bool repeated = loops.getLoopFor(&block) != nullptr;
          orderNodes.push_back(json::Object{{"source", json::Object(src)},
            {"block", sourceRef(artifact, fid, ids.lookup(&block))}, {"index", index},
            {"kind", instruction.getOpcodeName()}, {"multiplicity", repeated ? "repeated" : "single"}});
          events.push_back(Event{&instruction, json::Object(src),
            sourceRef(artifact, fid, ids.lookup(&block)), index, repeated});
        }
        ++index;

        if (auto *load = dyn_cast<LoadInst>(&instruction)) {
          provenanceItems.push_back(provenance(instruction, "load", json::Object(src),
            valueRef(load->getPointerOperand(), artifact, fid, ids), artifact, fid, ids,
            valueRef(load->getPointerOperand(), artifact, fid, ids).getAsNull() ? "unknown" : "candidate",
            valueRef(load->getPointerOperand(), artifact, fid, ids).getAsNull() ? json::Value("object-unresolved") : json::Value(nullptr)));
        } else if (auto *store = dyn_cast<StoreInst>(&instruction)) {
          auto value = valueRef(store->getValueOperand(), artifact, fid, ids);
          auto object = valueRef(store->getPointerOperand(), artifact, fid, ids);
          bool exact = !value.getAsNull() && !object.getAsNull();
          provenanceItems.push_back(provenance(instruction, "store", std::move(value), std::move(object),
            artifact, fid, ids, exact ? "exact" : "candidate", exact ? json::Value(nullptr) : json::Value("operand-unresolved")));
        } else if (auto *cast = dyn_cast<CastInst>(&instruction)) {
          auto value = valueRef(cast->getOperand(0), artifact, fid, ids);
          provenanceItems.push_back(provenance(instruction, "cast", std::move(value), nullptr,
            artifact, fid, ids, "candidate", nullptr));
        } else if (auto *phi = dyn_cast<PHINode>(&instruction)) {
          json::Value value = phi->getNumIncomingValues() ? valueRef(phi->getIncomingValue(0), artifact, fid, ids) : json::Value(nullptr);
          provenanceItems.push_back(provenance(instruction, "phi", std::move(value), nullptr,
            artifact, fid, ids, "candidate", "multiple-paths"));
        } else if (auto *select = dyn_cast<SelectInst>(&instruction)) {
          auto value = valueRef(select->getTrueValue(), artifact, fid, ids);
          provenanceItems.push_back(provenance(instruction, "select", std::move(value), nullptr,
            artifact, fid, ids, "candidate", "multiple-paths"));
        }

        auto *call = dyn_cast<CallBase>(&instruction);
        if (!call) continue;
        auto *target = dyn_cast<Function>(call->getCalledOperand()->stripPointerCasts());
        StringRef name = target ? target->getName() : StringRef();
        bool named = target && supportedName(name);
        bool abi = named && call->getCallingConv() == CallingConv::C &&
                   call->getFunctionType()->getReturnType()->isIntegerTy() &&
                   call->arg_size() == expectedParameters(name);
        json::Array arguments;
        for (Value *argument : call->args())
          arguments.push_back(valueRef(argument, artifact, fid, ids));
        json::Array callbacks;
        if ((name == "pthread_create" || name == "thrd_create") &&
            call->arg_size() == expectedParameters(name)) {
          std::set<std::string> seenCallbacks;
          unsigned callbackIndex = name == "pthread_create" ? 2 : 1;
          if (!callbackTargets(call->getArgOperand(callbackIndex), artifact, fid, ids,
                               size_t(*budgets.getInteger("value_candidates")), callbacks, seenCallbacks))
            localDiagnostics.push_back(bilingual(
                "callback-target-unknown", "线程回调候选无法在受限局部传播中唯一解析",
                "The thread callback candidates cannot be resolved by bounded local propagation",
                json::Object(src)));
        }
        if (target && (name.starts_with("pthread_") || name == "thrd_create")) {
          json::Object seed{{"kind", "pthread-call-eligibility"}, {"source", json::Object(src)},
                            {"symbol", name.str()}, {"eligible", abi}};
          auto evidenceId = analysisDigest(json::Value(json::Object(seed)));
          localEvidence.push_back(json::Object{
              {"ref", analysisRef(artifact, fid, evidenceId)}, {"kind", "pthread-call-eligibility"},
              {"source", json::Object(src)}, {"inputs", json::Array{json::Object(src)}},
              {"result", abi ? "candidate" : "unknown"}});
        }
        if (name == "pthread_create" || name == "thrd_create") {
          json::Object seed{{"kind", "callback-propagation"}, {"source", json::Object(src)},
                            {"candidates", json::Array(callbacks)}};
          auto evidenceId = analysisDigest(json::Value(json::Object(seed)));
          json::Array inputs;
          for (const auto &candidate : callbacks) inputs.push_back(candidate);
          localEvidence.push_back(json::Object{
              {"ref", analysisRef(artifact, fid, evidenceId)}, {"kind", "callback-propagation"},
              {"source", json::Object(src)}, {"inputs", std::move(inputs)},
              {"result", callbacks.size() == 1 ? "exact" : callbacks.empty() ? "unknown" : "candidate"}});
        }
        json::Value handle = nullptr, mutex = nullptr;
        if ((name == "pthread_create" || name == "pthread_join" || name == "thrd_create") && call->arg_size())
          handle = valueRef(call->getArgOperand(0), artifact, fid, ids);
        if ((name == "pthread_mutex_lock" || name == "pthread_mutex_unlock") && call->arg_size())
          mutex = valueRef(call->getArgOperand(0), artifact, fid, ids);
        json::Value normal = nullptr, unwind = nullptr;
        if (auto *invoke = dyn_cast<InvokeInst>(call)) {
          normal = sourceRef(artifact, fid, ids.lookup(invoke->getNormalDest()));
          unwind = sourceRef(artifact, fid, ids.lookup(invoke->getUnwindDest()));
        } else if (auto *next = instruction.getNextNode()) {
          normal = sourceRef(artifact, fid, ids.lookup(next));
        }
        std::string initializer;
        if (!mutex.getAsNull()) initializer = initializerFingerprint(call->getArgOperand(0), module);
        json::Value successTest = nullptr;
        for (User *user : call->users()) {
          auto *compare = dyn_cast<ICmpInst>(user);
          if (!compare || (compare->getPredicate() != ICmpInst::ICMP_EQ &&
                           compare->getPredicate() != ICmpInst::ICMP_NE)) continue;
          auto *constant = dyn_cast<ConstantInt>(compare->getOperand(0));
          if (!constant) constant = dyn_cast<ConstantInt>(compare->getOperand(1));
          if (constant && constant->isZero()) {
            successTest = sourceRef(artifact, fid, ids.lookup(compare));
            break;
          }
        }
        calls.push_back(json::Object{{"source", json::Object(src)},
          {"function", sourceRef(artifact, nullptr, fid)}, {"symbol", target ? json::Value(name.str()) : json::Value(nullptr)},
          {"direct", bool(target)}, {"function_type", typeText(call->getFunctionType())},
          {"calling_convention", int64_t(call->getCallingConv())}, {"arguments", std::move(arguments)},
          {"result", json::Object(src)}, {"normal_successor", std::move(normal)}, {"unwind_successor", std::move(unwind)},
          {"noreturn", call->doesNotReturn()}, {"success_test", std::move(successTest)}, {"callback_metadata", callbackMetadata(target)},
          {"callback_targets", std::move(callbacks)}, {"handle_source", std::move(handle)},
          {"mutex_source", std::move(mutex)}, {"mutex_initializer", initializer.empty() ? json::Value(nullptr) : json::Value(initializer)},
          {"status", abi ? "candidate" : "unknown"},
          {"reason", abi ? json::Value(nullptr) : json::Value(named ? (name == "thrd_create" ? "unsupported-thrd-abi" : "unsupported-pthread-abi") : target ? "unmodeled-direct-call" : "indirect-call")}});
        if (target && (name.starts_with("pthread_") || name == "thrd_create") && !abi)
          localDiagnostics.push_back(bilingual(name == "thrd_create" ? "unsupported-thrd-call" : "unsupported-pthread-call",
            name == "thrd_create" ? "thrd_create 调用不满足入口模型资格" : "pthread 调用不满足首版模型资格",
            name == "thrd_create" ? "The thrd_create call is outside the entry model eligibility" :
                                    "The pthread call is outside the initial model eligibility",
            json::Object(src)));
        if (!target || !call->onlyReadsMemory())
          provenanceItems.push_back(provenance(instruction, "clobber", nullptr, nullptr,
            artifact, fid, ids, "unknown", target ? json::Value("call-may-write-memory") : json::Value("indirect-call")));
      }
    }

    std::vector<Event *> functionEvents;
    for (auto &event : events)
      if (event.source.getString("function_id") == fid) functionEvents.push_back(&event);
    for (size_t i = 0; i < functionEvents.size(); ++i) {
      for (size_t j = i + 1; j < functionEvents.size(); ++j) {
        if (graphRemaining <= 0) break;
        Event *left = functionEvents[i], *right = functionEvents[j];
        bool lr = isPotentiallyReachable(left->instruction, right->instruction);
        bool rl = isPotentiallyReachable(right->instruction, left->instruction);
        Event *before = left, *after = right;
        StringRef relation = "unknown", reason = "cfg-order-unknown";
        if (left->instruction->getParent() == right->instruction->getParent()) {
          relation = (left->repeated || right->repeated) ? "may-before" : "must-before";
          reason = (left->repeated || right->repeated) ? "loop-occurrence" : "same-block-order";
        } else if (lr && rl) {
          relation = "may-before"; reason = "cfg-cycle";
        } else if (lr) {
          bool must = !left->repeated && !right->repeated &&
                      dt.dominates(left->instruction, right->instruction) &&
                      pdt.dominates(right->instruction->getParent(), left->instruction->getParent());
          relation = must ? "must-before" : "may-before";
          reason = must ? "dom-postdom-order" : "cfg-reachable";
        } else if (rl) {
          before = right; after = left;
          bool must = !left->repeated && !right->repeated &&
                      dt.dominates(right->instruction, left->instruction) &&
                      pdt.dominates(left->instruction->getParent(), right->instruction->getParent());
          relation = must ? "must-before" : "may-before";
          reason = must ? "dom-postdom-order" : "cfg-reachable";
        } else {
          relation = "mutually-exclusive"; reason = "cfg-disjoint";
        }
        json::Object seed{{"before", json::Object(before->source)}, {"after", json::Object(after->source)},
          {"relation", relation.str()}, {"reason", reason.str()}};
        auto edgeId = analysisDigest(json::Value(json::Object(seed)));
        auto proof = analysisRef(artifact, fid, edgeId);
        orderEvidence.push_back(json::Object{{"ref", json::Object(proof)}, {"kind", "execution-order"},
          {"source", json::Object(before->source)},
          {"inputs", json::Array{json::Object(before->source), json::Object(after->source)}},
          {"result", relation.str()}});
        orderEdges.push_back(json::Object{{"id", edgeId},
          {"before", json::Object(before->source)}, {"after", json::Object(after->source)},
          {"relation", relation.str()}, {"guards", json::Array{}},
          {"proof", json::Array{std::move(proof)}},
          {"reason", reason.str()}});
        --graphRemaining;
      }
      if (graphRemaining <= 0) break;
    }
  }

  if (local.exhausted) {
    auto item = bilingual("thread-local-budget", "LLVM 线程局部事实超过预算",
                          "LLVM thread-local facts exceeded the budget");
    localDiagnostics.push_back(json::Object(item)); localFrontier.push_back(std::move(item));
  }
  if (graphRemaining <= 0) {
    auto item = bilingual("execution-order-budget", "执行顺序图超过预算",
                          "Execution-order graph exceeded the budget");
    orderDiagnostics.push_back(json::Object(item)); orderFrontier.push_back(std::move(item));
  }
  json::Object localResult{{"schema_version", 1}, {"kind", "ThreadLocalFacts"},
    {"analysis_version", "0.1.0"}, {"policy_id", "thread-sync-contexts-v1"},
    {"origin", json::Object(origin)}, {"budgets", json::Object(budgets)}, {"calls", std::move(calls)},
    {"provenance", std::move(provenanceItems)}, {"analysis_evidence", std::move(localEvidence)},
    {"diagnostics", std::move(localDiagnostics)},
    {"frontier", std::move(localFrontier)}, {"status", local.exhausted ? "partial" : "complete"}};
  json::Object orderResult{{"schema_version", 1}, {"kind", "ExecutionOrderFacts"},
    {"analysis_version", "0.1.0"}, {"policy_id", "thread-sync-contexts-v1"},
    {"origin", json::Object(origin)}, {"budgets", json::Object(budgets)}, {"nodes", std::move(orderNodes)},
    {"edges", std::move(orderEdges)}, {"analysis_evidence", std::move(orderEvidence)},
    {"diagnostics", std::move(orderDiagnostics)},
    {"frontier", std::move(orderFrontier)}, {"status", graphRemaining <= 0 ? "partial" : "complete"}};
  return json::Object{{"local", std::move(localResult)}, {"order", std::move(orderResult)}};
}
} // namespace moa
