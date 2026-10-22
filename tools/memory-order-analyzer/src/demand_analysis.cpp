#include "demand_analysis.h"
#include "ir_identity.h"

#include <llvm/ADT/StringExtras.h>
#include <llvm/Analysis/AssumptionCache.h>
#include <llvm/Analysis/BasicAliasAnalysis.h>
#include <llvm/Analysis/LoopInfo.h>
#include <llvm/Analysis/MemorySSA.h>
#include <llvm/Analysis/PostDominators.h>
#include <llvm/Analysis/TargetLibraryInfo.h>
#include <llvm/Bitcode/BitcodeReader.h>
#include <llvm/IR/DebugInfoMetadata.h>
#include <llvm/IR/CFG.h>
#include <llvm/IR/Dominators.h>
#include <llvm/IR/Instructions.h>
#include <llvm/Support/Error.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/SHA256.h>

#include <algorithm>
#include <chrono>
#include <set>
#include <stdexcept>

using namespace llvm;
namespace moa {
namespace {
void require(bool condition, const std::string &message) {
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

json::Object failure(const std::exception &error) {
  StringRef message(error.what());
  return json::Object{{"code", message.split(':').first.str()}, {"detail", message.str()}};
}

std::string typeText(Type *type) {
  std::string result;
  raw_string_ostream out(result);
  type->print(out);
  return result;
}

std::string linkage(const GlobalValue &value) {
  switch (value.getLinkage()) {
  case GlobalValue::ExternalLinkage: return "external";
  case GlobalValue::AvailableExternallyLinkage: return "available_externally";
  case GlobalValue::LinkOnceAnyLinkage: return "linkonce";
  case GlobalValue::LinkOnceODRLinkage: return "linkonce_odr";
  case GlobalValue::WeakAnyLinkage: return "weak";
  case GlobalValue::WeakODRLinkage: return "weak_odr";
  case GlobalValue::AppendingLinkage: return "appending";
  case GlobalValue::InternalLinkage: return "internal";
  case GlobalValue::PrivateLinkage: return "private";
  case GlobalValue::ExternalWeakLinkage: return "extern_weak";
  case GlobalValue::CommonLinkage: return "common";
  }
  return "unknown";
}

std::string visibility(const GlobalValue &value) {
  switch (value.getVisibility()) {
  case GlobalValue::DefaultVisibility: return "default";
  case GlobalValue::HiddenVisibility: return "hidden";
  case GlobalValue::ProtectedVisibility: return "protected";
  }
  return "unknown";
}

json::Object location(const Instruction &instruction) {
  json::Array chain;
  for (auto *loc = instruction.getDebugLoc().get(); loc; loc = loc->getInlinedAt())
    chain.push_back(json::Object{{"file", loc->getFilename().str()},
      {"directory", loc->getDirectory().str()}, {"line", int64_t(loc->getLine())},
      {"column", int64_t(loc->getColumn())}});
  return json::Object{{"inline_chain", std::move(chain)}};
}

json::Value valueIdentity(Value *value, const DenseMap<const Value *, std::string> &ids) {
  if (!value) return nullptr;
  Value *base = value->stripPointerCasts();
  auto found = ids.find(base);
  if (found != ids.end()) return found->second;
  std::string text;
  raw_string_ostream out(text);
  base->printAsOperand(out, false);
  return text;
}

std::string accessKind(Instruction &instruction) {
  if (isa<LoadInst>(instruction)) return "read";
  if (isa<StoreInst>(instruction)) return "write";
  if (isa<AtomicRMWInst>(instruction)) return "rmw";
  if (isa<AtomicCmpXchgInst>(instruction)) return "cas";
  if (isa<FenceInst>(instruction)) return "fence";
  return "call";
}

Value *accessPointer(Instruction &instruction) {
  if (auto *load = dyn_cast<LoadInst>(&instruction)) return load->getPointerOperand();
  if (auto *store = dyn_cast<StoreInst>(&instruction)) return store->getPointerOperand();
  if (auto *rmw = dyn_cast<AtomicRMWInst>(&instruction)) return rmw->getPointerOperand();
  if (auto *cas = dyn_cast<AtomicCmpXchgInst>(&instruction)) return cas->getPointerOperand();
  return nullptr;
}

std::string atomicOrdering(Instruction &instruction) {
  if (auto *load = dyn_cast<LoadInst>(&instruction))
    return load->isAtomic() ? toIRString(load->getOrdering()) : "not_atomic";
  if (auto *store = dyn_cast<StoreInst>(&instruction))
    return store->isAtomic() ? toIRString(store->getOrdering()) : "not_atomic";
  if (auto *rmw = dyn_cast<AtomicRMWInst>(&instruction)) return toIRString(rmw->getOrdering());
  if (auto *cas = dyn_cast<AtomicCmpXchgInst>(&instruction))
    return std::string(toIRString(cas->getSuccessOrdering())) + "/" +
           toIRString(cas->getFailureOrdering());
  if (auto *fence = dyn_cast<FenceInst>(&instruction)) return toIRString(fence->getOrdering());
  return "not_atomic";
}

SyncScope::ID atomicSyncScope(Instruction &instruction) {
  if (auto *load = dyn_cast<LoadInst>(&instruction)) return load->getSyncScopeID();
  if (auto *store = dyn_cast<StoreInst>(&instruction)) return store->getSyncScopeID();
  if (auto *rmw = dyn_cast<AtomicRMWInst>(&instruction)) return rmw->getSyncScopeID();
  if (auto *cas = dyn_cast<AtomicCmpXchgInst>(&instruction)) return cas->getSyncScopeID();
  if (auto *fence = dyn_cast<FenceInst>(&instruction)) return fence->getSyncScopeID();
  return SyncScope::System;
}

json::Object callFact(CallBase &call, StringRef fid,
                      const DenseMap<const Value *, std::string> &ids) {
  auto *target = dyn_cast<Function>(call.getCalledOperand()->stripPointerCasts());
  json::Array arguments;
  for (Value *argument : call.args()) arguments.push_back(valueIdentity(argument, ids));
  return json::Object{{"id", ids.lookup(&call)}, {"function_id", fid.str()},
    {"target", target ? json::Value(ids.lookup(target)) : json::Value(nullptr)},
    {"target_name", target ? json::Value(target->getName().str()) : json::Value(nullptr)},
    {"binding", target ? "exact" : "indirect"}, {"arguments", std::move(arguments)},
    {"location", location(call)}};
}

json::Object commonFacts(Function &function, StringRef artifact, StringRef layer,
                         int64_t &instructionsRemaining, int64_t &queriesRemaining) {
  auto ids = functionIdentities(function, artifact.str());
  const auto fid = ids.lookup(&function);
  json::Array arguments, blocks, instructions, calls, accesses;
  for (auto &argument : function.args())
    arguments.push_back(json::Object{{"id", ids.lookup(&argument)},
      {"index", int64_t(argument.getArgNo())}, {"type", typeText(argument.getType())}});
  for (auto &block : function) {
    json::Array successorIds;
    for (auto *successor : llvm::successors(&block)) successorIds.push_back(ids.lookup(successor));
    blocks.push_back(json::Object{{"id", ids.lookup(&block)}, {"successors", std::move(successorIds)}});
    for (auto &instruction : block) {
      require(--instructionsRemaining >= 0, "materialized-instruction-budget: function shard exceeded budget");
      instructions.push_back(json::Object{{"id", ids.lookup(&instruction)},
        {"block", ids.lookup(&block)}, {"opcode", instruction.getOpcodeName()},
        {"type", typeText(instruction.getType())}, {"location", location(instruction)}});
      if (auto *call = dyn_cast<CallBase>(&instruction)) calls.push_back(callFact(*call, fid, ids));
      if (instruction.mayReadOrWriteMemory() || isa<FenceInst>(instruction)) {
        auto *pointer = accessPointer(instruction);
        accesses.push_back(json::Object{{"id", ids.lookup(&instruction)},
          {"kind", accessKind(instruction)}, {"object", valueIdentity(pointer, ids)},
          {"atomic_order", atomicOrdering(instruction)}, {"location", location(instruction)}});
      }
    }
  }
  require(--queriesRemaining >= 0, "analysis-query-budget: function shard exceeded budget");
  return json::Object{{"reference_closed", true}, {"layer", layer.str()},
    {"function", json::Object{{"id", fid}, {"name", function.getName().str()},
      {"type", typeText(function.getFunctionType())}, {"linkage", linkage(function)}}},
    {"arguments", std::move(arguments)}, {"blocks", std::move(blocks)},
    {"instructions", std::move(instructions)}, {"calls", std::move(calls)},
    {"accesses", std::move(accesses)}};
}

json::Object semanticFacts(Function &function, StringRef artifact,
                           int64_t &instructionsRemaining, int64_t &queriesRemaining) {
  auto result = commonFacts(function, artifact, "semantic", instructionsRemaining, queriesRemaining);
  json::Array returns, conditions;
  auto ids = functionIdentities(function, artifact.str());
  for (auto &block : function) for (auto &instruction : block) {
    if (auto *ret = dyn_cast<ReturnInst>(&instruction))
      returns.push_back(json::Object{{"source", ids.lookup(ret)},
        {"value", valueIdentity(ret->getReturnValue(), ids)}});
    if (auto *branch = dyn_cast<BranchInst>(&instruction); branch && branch->isConditional())
      conditions.push_back(json::Object{{"source", ids.lookup(branch)},
        {"condition", valueIdentity(branch->getCondition(), ids)}});
    if (auto *select = dyn_cast<SelectInst>(&instruction))
      conditions.push_back(json::Object{{"source", ids.lookup(select)},
        {"condition", valueIdentity(select->getCondition(), ids)}});
  }
  result["returns"] = std::move(returns);
  result["conditions"] = std::move(conditions);
  return result;
}

json::Object advancedAtomicFacts(Function &function, StringRef artifact,
                                 int64_t &instructionsRemaining, int64_t &queriesRemaining) {
  auto result = commonFacts(function, artifact, "advanced-atomic", instructionsRemaining, queriesRemaining);
  json::Array atomicEvents;
  auto ids = functionIdentities(function, artifact.str());
  DominatorTree dt(function);
  LoopInfo loops(dt);
  for (auto &block : function) for (auto &instruction : block) {
    if (!(isa<FenceInst>(instruction) || isa<AtomicRMWInst>(instruction) ||
          isa<AtomicCmpXchgInst>(instruction) ||
          (isa<LoadInst>(instruction) && cast<LoadInst>(instruction).isAtomic()) ||
          (isa<StoreInst>(instruction) && cast<StoreInst>(instruction).isAtomic())))
      continue;
    auto *pointer = accessPointer(instruction);
    Type *valueType = nullptr;
    json::Object inputs;
    std::string failureOrdering;
    std::string operation;
    bool weak = false;
    if (auto *load = dyn_cast<LoadInst>(&instruction)) valueType = load->getType();
    if (auto *store = dyn_cast<StoreInst>(&instruction)) {
      valueType = store->getValueOperand()->getType();
      inputs["value"] = valueIdentity(store->getValueOperand(), ids);
    }
    if (auto *rmw = dyn_cast<AtomicRMWInst>(&instruction)) {
      valueType = rmw->getValOperand()->getType();
      inputs["value"] = valueIdentity(rmw->getValOperand(), ids);
      operation = AtomicRMWInst::getOperationName(rmw->getOperation()).str();
    }
    if (auto *cas = dyn_cast<AtomicCmpXchgInst>(&instruction)) {
      valueType = cas->getCompareOperand()->getType();
      inputs["compare"] = valueIdentity(cas->getCompareOperand(), ids);
      inputs["new"] = valueIdentity(cas->getNewValOperand(), ids);
      failureOrdering = toIRString(cas->getFailureOrdering());
      weak = cas->isWeak();
    }
    json::Value size = nullptr;
    if (valueType && valueType->isSized()) {
      auto storeSize = function.getParent()->getDataLayout().getTypeStoreSize(valueType);
      if (!storeSize.isScalable()) size = int64_t(storeSize.getFixedValue());
    }
    auto scope = atomicSyncScope(instruction);
    std::string syncscope = "system";
    if (scope == SyncScope::SingleThread) syncscope = "singlethread";
    else if (scope != SyncScope::System) syncscope = "target-specific";
    atomicEvents.push_back(json::Object{
      {"id", ids.lookup(&instruction)}, {"kind", accessKind(instruction)},
      {"function", ids.lookup(&function)}, {"block", ids.lookup(&block)},
      {"object", valueIdentity(pointer, ids)}, {"size_bytes", std::move(size)},
      {"address_space", pointer ? int64_t(pointer->getType()->getPointerAddressSpace()) : int64_t(0)},
      {"ordering", isa<AtomicCmpXchgInst>(instruction) ?
        toIRString(cast<AtomicCmpXchgInst>(instruction).getSuccessOrdering()) : atomicOrdering(instruction)},
      {"failure_ordering", failureOrdering.empty() ? json::Value(nullptr) : json::Value(failureOrdering)},
      {"syncscope", syncscope}, {"operation", operation.empty() ? json::Value(nullptr) : json::Value(operation)},
      {"weak", weak}, {"inputs", std::move(inputs)}, {"result_ref", ids.lookup(&instruction)},
      {"guards", json::Array{}}, {"multiplicity", loops.getLoopFor(&block) ? "repeated" : "single"},
      {"location", location(instruction)}});
  }
  result["atomic_events"] = std::move(atomicEvents);
  return result;
}

json::Object effectFacts(Function &function, StringRef artifact,
                         int64_t &instructionsRemaining, int64_t &queriesRemaining) {
  auto result = commonFacts(function, artifact, "effect", instructionsRemaining, queriesRemaining);
  auto ids = functionIdentities(function, artifact.str());
  DominatorTree dt(function);
  TargetLibraryInfoImpl impl(function.getParent()->getTargetTriple());
  TargetLibraryInfo tli(impl, &function);
  AssumptionCache ac(function);
  BasicAAResult basic(function.getParent()->getDataLayout(), function, tli, ac, &dt);
  AAResults aa(tli);
  if (!function.getParent()->getDataLayoutStr().empty()) aa.addAAResult(basic);
  MemorySSA mssa(function, &aa, &dt);
  json::Array effects, evidence;
  int64_t memoryAccesses = 0;
  for (auto &block : function) {
    evidence.push_back(json::Object{{"kind", "dominance"}, {"block", ids.lookup(&block)},
      {"reachable", dt.isReachableFromEntry(&block)}});
    for (auto &instruction : block) {
      if (instruction.mayReadOrWriteMemory() || isa<FenceInst>(instruction)) {
        effects.push_back(json::Object{{"source", ids.lookup(&instruction)},
          {"kind", accessKind(instruction)}, {"object", valueIdentity(accessPointer(instruction), ids)},
          {"guard", nullptr}, {"binding", "local-candidate"}, {"atomic_order", atomicOrdering(instruction)}});
      }
      if (auto *access = mssa.getMemoryAccess(&instruction)) {
        require(--queriesRemaining >= 0, "analysis-query-budget: effect shard exceeded budget");
        ++memoryAccesses;
        auto *clobber = mssa.getWalker()->getClobberingMemoryAccess(access);
        evidence.push_back(json::Object{{"kind", isa<MemoryDef>(access) ? "memory-def" : "memory-use"},
          {"source", ids.lookup(&instruction)}, {"clobber_available", clobber != nullptr}});
      }
    }
  }
  result["effects"] = std::move(effects);
  result["analysis_evidence"] = std::move(evidence);
  result["analysis"] = json::Object{{"dominator_tree", true}, {"basic_aa", true},
    {"memory_ssa", true}, {"memory_accesses", memoryAccesses}};
  return result;
}

bool threadApi(StringRef name) {
  return name == "pthread_create" || name == "pthread_join" || name == "pthread_mutex_lock" ||
         name == "pthread_mutex_unlock" || name == "thrd_create" || name.contains("_M_start_thread") ||
         name.contains("__thread_proxy") || name.contains("async");
}

json::Object threadFactsForFunction(Function &function, StringRef artifact,
                                    int64_t &instructionsRemaining, int64_t &queriesRemaining) {
  auto result = commonFacts(function, artifact, "thread", instructionsRemaining, queriesRemaining);
  auto ids = functionIdentities(function, artifact.str());
  DominatorTree dt(function);
  PostDominatorTree pdt(function);
  LoopInfo loops(dt);
  json::Array nodes, edges, threadCalls, evidence;
  for (auto &block : function) {
    const Instruction *previous = nullptr;
    for (auto &instruction : block) {
      bool relevant = instruction.mayReadOrWriteMemory() || isa<CallBase>(instruction) || isa<FenceInst>(instruction);
      if (relevant) {
        bool repeated = loops.getLoopFor(&block) != nullptr;
        nodes.push_back(json::Object{{"id", ids.lookup(&instruction)}, {"block", ids.lookup(&block)},
          {"kind", instruction.getOpcodeName()}, {"multiplicity", repeated ? "repeated" : "single"}});
        if (previous) edges.push_back(json::Object{{"source", ids.lookup(previous)},
          {"target", ids.lookup(&instruction)}, {"proof", "same-block-sequence"}});
        previous = &instruction;
      }
      if (auto *call = dyn_cast<CallBase>(&instruction)) {
        auto *target = dyn_cast<Function>(call->getCalledOperand()->stripPointerCasts());
        if (target && threadApi(target->getName())) {
          json::Array callbacks;
          if ((target->getName() == "pthread_create" && call->arg_size() == 4) ||
              (target->getName() == "thrd_create" && call->arg_size() == 3)) {
            unsigned index = target->getName() == "pthread_create" ? 2 : 1;
            if (auto *callback = dyn_cast<Function>(call->getArgOperand(index)->stripPointerCasts()))
              callbacks.push_back(ids.lookup(callback));
          }
          threadCalls.push_back(json::Object{{"source", ids.lookup(call)},
            {"api", target->getName().str()}, {"target", ids.lookup(target)},
            {"callbacks", std::move(callbacks)}, {"binding", "exact"}});
        }
      }
    }
    require(--queriesRemaining >= 0, "analysis-query-budget: thread shard exceeded budget");
    evidence.push_back(json::Object{{"block", ids.lookup(&block)},
      {"reachable", dt.isReachableFromEntry(&block)},
      {"postdom_node", pdt.getNode(&block) != nullptr}, {"loop", loops.getLoopFor(&block) != nullptr}});
  }
  result["order_nodes"] = std::move(nodes);
  result["order_edges"] = std::move(edges);
  result["thread_calls"] = std::move(threadCalls);
  result["analysis_evidence"] = std::move(evidence);
  result["analysis"] = json::Object{{"dominator_tree", true}, {"postdominator_tree", true}, {"loop_info", true}};
  return result;
}

json::Object indexModule(Module &module, const json::Object &job) {
  const auto artifact = job.getString("artifact_key")->str();
  json::Array symbols;
  int64_t functions = 0, definitions = 0;
  for (auto &global : module.global_values()) {
    bool materializable = global.isMaterializable();
    bool declaration = !materializable && global.isDeclaration();
    if (isa<Function>(global)) {
      ++functions;
      if (materializable || !declaration) ++definitions;
    }
    auto *object = dyn_cast<GlobalObject>(&global);
    symbols.push_back(json::Object{{"id", symbolId(global, artifact)},
      {"name", global.getName().str()}, {"declaration", declaration},
      {"materializable", materializable}, {"linkage", linkage(global)},
      {"visibility", visibility(global)},
      {"comdat", object && object->hasComdat() ? json::Value(object->getComdat()->getName().str()) : json::Value(nullptr)}});
  }
  std::sort(symbols.begin(), symbols.end(), [](const json::Value &left, const json::Value &right) {
    return *left.getAsObject()->getString("id") < *right.getAsObject()->getString("id");
  });
  auto indexedSymbols = int64_t(symbols.size());
  return json::Object{{"artifact_key", artifact},
    {"physical_tu_id", job.getString("physical_tu_id")->str()},
    {"bc_digest", job.getString("bc_digest")->str()},
    {"profile_id", job.getString("profile_id")->str()}, {"target", module.getTargetTriple().str()},
    {"data_layout", module.getDataLayoutStr()}, {"abi", job.getString("abi")->str()},
    {"symbols", std::move(symbols)}, {"source_bindings", json::Array{}},
    {"counts", json::Object{{"indexed_symbols", indexedSymbols},
      {"indexed_functions", functions}, {"defined_functions", definitions},
      {"materialized_functions", 0}, {"materialized_instructions", 0}}}};
}

void validateBudgets(const json::Object &provided, const json::Object &limits) {
  require(provided.size() == limits.size(), "demand_request: invalid budgets");
  for (auto &limit : limits) {
    auto value = provided.getInteger(limit.first);
    require(value && *value > 0 && *value <= *limit.second.getAsInteger(),
            "demand_request: invalid budget value");
  }
}

json::Object readJob(const json::Object &job, const json::Object &limits, bool advancedAtomic = false) {
  for (auto field : {"id", "path", "artifact_key", "bc_digest", "physical_tu_id", "profile_id", "target", "data_layout", "abi"})
    require(job.getString(field) && !job.getString(field)->empty(), "demand_request: missing job field");
  auto *demands = job.getArray("demands");
  auto *budgets = job.getObject("budgets");
  require(demands && budgets, "demand_request: invalid job demands/budgets");
  validateBudgets(*budgets, limits);
  require(demands->size() <= size_t(*budgets->getInteger("demands")), "demand-budget: too many demands");
  auto contents = buffer(job.getString("path")->str());
  require(digest(contents->getBuffer()) == *job.getString("bc_digest"), "inputs_changed: BC hash mismatch");
  require(contents->getBuffer().starts_with(StringRef("BC\xc0\xde", 4)), "format_invalid: expected bitcode");
  LLVMContext context;
  auto lazy = getLazyBitcodeModule(contents->getMemBufferRef(), context, true);
  if (!lazy) throw std::runtime_error("reader_failed: " + toString(lazy.takeError()));
  auto module = std::move(*lazy);
  require(module->getTargetTriple().str() == *job.getString("target"), "profile_conflict: target mismatch");
  require(module->getDataLayoutStr() == *job.getString("data_layout"),
          "profile_conflict: DataLayout mismatch (observed=" + module->getDataLayoutStr() +
          ", expected=" + job.getString("data_layout")->str() + ")");
  auto index = indexModule(*module, job);
  int64_t instructionsRemaining = *budgets->getInteger("materialized_instructions");
  int64_t queriesRemaining = *budgets->getInteger("analysis_queries");
  int64_t materializedInstructions = 0;
  std::set<std::string> materializedFunctions;
  json::Array shards;
  std::string previous;
  auto started = std::chrono::steady_clock::now();
  for (auto &item : *demands) {
    auto *demand = item.getAsObject();
    require(demand && demand->getString("function_id") && demand->getString("function_name") &&
            demand->getString("context_id") && demand->getArray("layers"), "demand_request: invalid demand");
    std::string sortKey = demand->getString("function_id")->str() + "\0" + demand->getString("context_id")->str();
    require(previous.empty() || previous < sortKey, "demand_request: demands must be unique and sorted");
    previous = sortKey;
    auto *function = module->getFunction(*demand->getString("function_name"));
    require(function && symbolId(*function, job.getString("artifact_key")->str()) == *demand->getString("function_id"),
            "function_not_found: demanded function identity is unavailable");
    require(function->isMaterializable() || !function->isDeclaration(),
            "function_declaration: demanded function has no body");
    if (function->isMaterializable()) {
      if (Error error = function->materialize())
        throw std::runtime_error("materialize_failed: " + toString(std::move(error)));
    }
    if (materializedFunctions.insert(demand->getString("function_id")->str()).second)
      for (auto &block : *function) materializedInstructions += int64_t(block.size());
    if (advancedAtomic) {
      json::Object shard{{"schema_version", 1}, {"kind", "AdvancedAtomicFunctionFacts"},
        {"analysis_version", "0.1.0"}, {"policy_id", "fence-rmw-publication-v1"},
        {"artifact_key", job.getString("artifact_key")->str()},
        {"function_id", demand->getString("function_id")->str()},
        {"function_name", demand->getString("function_name")->str()},
        {"context_id", demand->getString("context_id")->str()}, {"layer", "advanced-atomic"},
        {"status", "complete"}, {"facts", nullptr}, {"counts", json::Object{}}, {"error", nullptr}};
      try {
        auto facts = advancedAtomicFacts(*function, *job.getString("artifact_key"),
                                         instructionsRemaining, queriesRemaining);
        shard["counts"] = json::Object{
          {"instructions", int64_t(facts.getArray("instructions")->size())},
          {"calls", int64_t(facts.getArray("calls")->size())},
          {"accesses", int64_t(facts.getArray("accesses")->size())},
          {"atomic_events", int64_t(facts.getArray("atomic_events")->size())}};
        shard["facts"] = std::move(facts);
      } catch (const std::exception &error) {
        shard["status"] = StringRef(error.what()).starts_with("materialized-instruction-budget") ||
                                  StringRef(error.what()).starts_with("analysis-query-budget") ? "partial" : "failed";
        shard["facts"] = json::Object{{"reference_closed", false}, {"atomic_events", json::Array{}}};
        shard["error"] = failure(error);
      }
      shards.push_back(std::move(shard));
      continue;
    }
    for (auto &layerValue : *demand->getArray("layers")) {
      auto layer = layerValue.getAsString();
      require(layer && (*layer == "semantic" || *layer == "effect" || *layer == "thread"),
              "demand_request: invalid layer");
      json::Object shard{{"function_id", demand->getString("function_id")->str()},
        {"function_name", demand->getString("function_name")->str()},
        {"context_id", demand->getString("context_id")->str()}, {"layer", layer->str()},
        {"status", "completed"}, {"facts", nullptr}, {"counts", json::Object{}}, {"error", nullptr}};
      try {
        json::Object facts = *layer == "semantic" ? semanticFacts(*function, *job.getString("artifact_key"), instructionsRemaining, queriesRemaining) :
          *layer == "effect" ? effectFacts(*function, *job.getString("artifact_key"), instructionsRemaining, queriesRemaining) :
          threadFactsForFunction(*function, *job.getString("artifact_key"), instructionsRemaining, queriesRemaining);
        auto instructionCount = int64_t(facts.getArray("instructions")->size());
        shard["counts"] = json::Object{{"instructions", instructionCount},
          {"calls", int64_t(facts.getArray("calls")->size())},
          {"accesses", int64_t(facts.getArray("accesses")->size())}};
        shard["facts"] = std::move(facts);
      } catch (const std::exception &error) {
        shard["status"] = StringRef(error.what()).starts_with("materialized-instruction-budget") ||
                                  StringRef(error.what()).starts_with("analysis-query-budget") ? "partial" : "failed";
        shard["facts"] = json::Object{{"reference_closed", false}};
        shard["error"] = failure(error);
      }
      shards.push_back(std::move(shard));
    }
  }
  auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
  return json::Object{{"id", job.getString("id")->str()}, {"index", std::move(index)},
    {"shards", std::move(shards)}, {"metrics", json::Object{{"module_parses", 1},
      {"materialized_functions", int64_t(materializedFunctions.size())},
      {"materialized_instructions", materializedInstructions},
      {"analysis_queries", *budgets->getInteger("analysis_queries") - queriesRemaining},
      {"wall_seconds", elapsed}, {"cpu_seconds", elapsed}, {"peak_rss_bytes", 0},
      {"output_bytes", 0}}}, {"error", nullptr}};
}
} // namespace

namespace {
json::Object batchRequest(const json::Object &request, bool advancedAtomic) {
  auto protocol = advancedAtomic ? advancedAtomicProtocol() : demandProtocol();
  auto *provided = request.getObject("protocol");
  auto *providedDemand = request.getObject("demand_protocol");
  auto *jobs = request.getArray("jobs");
  require(request.size() == (advancedAtomic ? 3u : 2u) && provided && jobs && !jobs->empty() &&
          json::Value(json::Object(*provided)) == json::Value(json::Object(protocol)),
          advancedAtomic ? "advanced_atomic_request: invalid batch/protocol"
                         : "demand_request: invalid batch/protocol");
  auto demand = demandProtocol();
  if (advancedAtomic)
    require(providedDemand && json::Value(json::Object(*providedDemand)) == json::Value(json::Object(demand)),
            "advanced_atomic_request: invalid demand protocol");
  auto &limits = *demand.getObject("budgets");
  require(jobs->size() <= size_t(*limits.getInteger("translation_units")), "demand_request: job limit");
  json::Array results;
  size_t outputLimit = *limits.getInteger("worker_output_bytes");
  std::set<std::string> ids;
  for (auto &item : *jobs) {
    auto *job = item.getAsObject();
    require(job && job->getString("id") && ids.insert(job->getString("id")->str()).second,
            "demand_request: duplicate or invalid job");
    if (auto *budgets = job->getObject("budgets"))
      outputLimit = std::min(outputLimit, size_t(*budgets->getInteger("worker_output_bytes")));
    json::Object result{{"id", job->getString("id")->str()}, {"index", nullptr},
      {"shards", json::Array{}}, {"metrics", json::Object{}}, {"error", nullptr}};
    try { result = readJob(*job, limits, advancedAtomic); }
    catch (const std::exception &error) { result["error"] = failure(error); }
    results.push_back(std::move(result));
  }
  json::Object output{{"protocol_version", 1}, {"results", std::move(results)}, {"error", nullptr}};
  if (advancedAtomic) output["policy_id"] = "fence-rmw-publication-v1";
  std::string bytes;
  raw_string_ostream stream(bytes);
  stream << json::Value(json::Object(output));
  require(bytes.size() <= outputLimit, "worker_output_limit: demand batch exceeds budget");
  return output;
}

int batchWorker(const std::string &path, raw_ostream &out, raw_ostream &err, bool advancedAtomic) {
  try {
    auto input = buffer(path);
    require(input->getBufferSize() <= 16777216,
            advancedAtomic ? "advanced_atomic_request: request exceeds transport limit"
                           : "demand_request: request exceeds transport limit");
    auto parsed = json::parse(input->getBuffer());
    if (!parsed) {
      consumeError(parsed.takeError());
      throw std::runtime_error(advancedAtomic ? "advanced_atomic_request: invalid JSON"
                                              : "demand_request: invalid JSON");
    }
    require(parsed->getAsObject(), advancedAtomic ? "advanced_atomic_request: expected object"
                                                  : "demand_request: expected object");
    out << json::Value(batchRequest(*parsed->getAsObject(), advancedAtomic)) << "\n";
    return 0;
  } catch (const std::exception &error) {
    json::Object output{{"protocol_version", 1}, {"results", json::Array{}}, {"error", failure(error)}};
    if (advancedAtomic) output["policy_id"] = "fence-rmw-publication-v1";
    out << json::Value(std::move(output)) << "\n";
    err << error.what() << "\n";
    return 1;
  }
}
} // namespace

json::Object demandBatch(const json::Object &request) {
  return batchRequest(request, false);
}

json::Object advancedAtomicDemandBatch(const json::Object &request) {
  return batchRequest(request, true);
}

int demandWorker(const std::string &path, raw_ostream &out, raw_ostream &err) {
  return batchWorker(path, out, err, false);
}

int advancedAtomicDemandWorker(const std::string &path, raw_ostream &out, raw_ostream &err) {
  return batchWorker(path, out, err, true);
}
} // namespace moa
