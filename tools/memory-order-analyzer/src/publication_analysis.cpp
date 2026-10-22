#include "publication.h"
#include "effects.h"
#include "ir_identity.h"
#include <llvm/ADT/SCCIterator.h>
#include <llvm/Analysis/CFG.h>
#include <llvm/Analysis/LoopInfo.h>
#include <llvm/IR/CFG.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/Dominators.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/Operator.h>
#include <algorithm>
#include <set>

using namespace llvm;
namespace moa {
namespace {
json::Object sourceRef(StringRef artifact, json::Value function, StringRef id) {
  return json::Object{{"artifact_key", artifact.str()}, {"function_id", std::move(function)}, {"id", id.str()}};
}
json::Object analysisRef(StringRef artifact, json::Value function, StringRef id) {
  return json::Object{{"artifact_key", artifact.str()}, {"function_id", std::move(function)}, {"analysis_id", id.str()}};
}
std::string hex(const APInt &value) {
  SmallString<64> text;
  value.toString(text, 16, false, false);
  std::string result = text.str().str();
  std::transform(result.begin(), result.end(), result.begin(), [](unsigned char c) { return char(std::toupper(c)); });
  return result;
}
json::Object exact(const APInt &value) {
  return json::Object{{"state", "exact"}, {"bits", int64_t(value.getBitWidth())}, {"hex", hex(value)}};
}
json::Object unknown(StringRef reason) { return json::Object{{"state", "unknown"}, {"reason", reason.str()}}; }
std::string ordering(AtomicOrdering value) { return toIRString(value); }
std::string syncscope(LLVMContext &context, SyncScope::ID id) {
  SmallVector<StringRef> names;
  context.getSyncScopeNames(names);
  return names[id].str();
}
json::Object bilingual(StringRef code, StringRef detail, StringRef english, json::Value source = nullptr) {
  return json::Object{{"code", code.str()}, {"detail", detail.str()}, {"detail_en", english.str()},
    {"suggestion", nullptr}, {"suggestion_en", nullptr}, {"source", std::move(source)},
    {"thread_context_id", nullptr}, {"thread_instance_id", nullptr}};
}
struct Limit {
  int64_t remaining;
  bool exhausted = false;
  bool take() { if (remaining <= 0) { exhausted = true; return false; } --remaining; return true; }
};
struct Range {
  json::Value object = nullptr;
  std::optional<int64_t> offset;
  std::optional<uint64_t> size;
  std::optional<unsigned> addressSpace;
};
Range objectRange(Value *pointer, Type *type, Module &module, StringRef artifact, StringRef function,
                  const DenseMap<const Value *, std::string> &ids) {
  Range result;
  result.addressSpace = pointer->getType()->getPointerAddressSpace();
  if (!module.getDataLayoutStr().empty()) {
    auto bytes = module.getDataLayout().getTypeStoreSize(type);
    if (!bytes.isScalable()) result.size = bytes.getFixedValue();
  }
  Value *base = pointer->stripPointerCasts();
  int64_t total = 0;
  for (unsigned depth = 0; depth <= 16; ++depth) {
    if (auto *gep = dyn_cast<GEPOperator>(base)) {
      if (module.getDataLayoutStr().empty()) return result;
      unsigned width = module.getDataLayout().getIndexSizeInBits(gep->getPointerAddressSpace());
      APInt offset(width, 0);
      if (!gep->accumulateConstantOffset(module.getDataLayout(), offset) || !offset.isSignedIntN(64)) return result;
      int64_t part = offset.getSExtValue();
      if (__builtin_add_overflow(total, part, &total)) return result;
      base = gep->getPointerOperand()->stripPointerCasts();
      continue;
    }
    auto *load = dyn_cast<LoadInst>(base);
    auto *slot = load ? dyn_cast<AllocaInst>(load->getPointerOperand()->stripPointerCasts()) : nullptr;
    if (!slot) break;
    Value *stored = nullptr;
    for (User *user : slot->users()) {
      auto *store = dyn_cast<StoreInst>(user);
      if (!store || store->getPointerOperand()->stripPointerCasts() != slot ||
          !store->getValueOperand()->getType()->isPointerTy()) continue;
      Value *candidate = store->getValueOperand()->stripPointerCasts();
      if (stored && stored != candidate) return result;
      stored = candidate;
    }
    if (!stored) break;
    base = stored;
  }
  auto found = ids.find(base);
  if (found == ids.end()) return result;
  json::Value owner = nullptr;
  if (isa<GlobalValue>(base)) owner = sourceRef(artifact, nullptr, found->second);
  else owner = sourceRef(artifact, function.str(), found->second);
  result.object = std::move(owner); result.offset = total;
  return result;
}
json::Object rangeJson(const Range &value) {
  return json::Object{{"object", value.object},
    {"offset_bytes", value.offset ? json::Value(std::to_string(*value.offset)) : json::Value(nullptr)},
    {"size_bytes", value.size ? json::Value(std::to_string(*value.size)) : json::Value(nullptr)},
    {"address_space", value.addressSpace ? json::Value(int64_t(*value.addressSpace)) : json::Value(nullptr)}};
}
std::optional<APInt> scalarBits(Value *value, unsigned depth = 0) {
  if (depth > 16 || isa<PoisonValue, UndefValue>(value)) return std::nullopt;
  if (auto *integer = dyn_cast<ConstantInt>(value)) return integer->getValue();
  if (auto *cast = dyn_cast<CastInst>(value))
    if (auto input = scalarBits(cast->getOperand(0), depth + 1)) {
      APInt result = *input;
      unsigned width = cast->getType()->getIntegerBitWidth();
      if (cast->getOpcode() == Instruction::Trunc) result = result.trunc(width);
      else if (cast->getOpcode() == Instruction::ZExt) result = result.zext(width);
      else if (cast->getOpcode() == Instruction::SExt) result = result.sext(width);
      else return std::nullopt;
      return result;
    }
  if (auto *load = dyn_cast<LoadInst>(value)) {
    auto *slot = dyn_cast<AllocaInst>(load->getPointerOperand()->stripPointerCasts());
    if (!slot) return std::nullopt;
    std::optional<APInt> result;
    for (User *user : slot->users()) {
      auto *store = dyn_cast<StoreInst>(user);
      if (!store || store->getPointerOperand()->stripPointerCasts() != slot) continue;
      auto candidate = scalarBits(store->getValueOperand(), depth + 1);
      if (!candidate || (result && *result != *candidate)) return std::nullopt;
      result = *candidate;
    }
    return result;
  }
  return std::nullopt;
}
json::Object scalar(Value *value) {
  if (auto result = scalarBits(value)) return exact(*result);
  return unknown("non-constant-value");
}
bool repeated(const Instruction &instruction, LoopInfo &loops) {
  return loops.getLoopFor(instruction.getParent()) != nullptr;
}
struct Trace { Value *origin; bool inverted; };
void appendTrace(std::vector<Trace> &result, Value *origin, bool inverted) {
  if (llvm::none_of(result, [&](const Trace &old) { return old.origin == origin && old.inverted == inverted; }))
    result.push_back({origin, inverted});
}
void traces(Value *value, std::vector<Trace> &result, bool inverted, unsigned depth, size_t limit) {
  if (depth > 16 || result.size() >= limit) return;
  if (auto *load = dyn_cast<LoadInst>(value)) {
    // Clang -O0 commonly spills an atomic/library result into an alloca before
    // comparing it.  Follow only the bounded, function-local storage cell;
    // shared/global loads remain the observation origin.
    auto *slot = dyn_cast<AllocaInst>(load->getPointerOperand()->stripPointerCasts());
    if (slot) {
      bool found = false;
      for (User *user : slot->users()) {
        auto *store = dyn_cast<StoreInst>(user);
        if (!store || store->getPointerOperand()->stripPointerCasts() != slot) continue;
        found = true;
        traces(store->getValueOperand(), result, inverted, depth + 1, limit);
      }
      if (found) return;
    }
    appendTrace(result, value, inverted); return;
  }
  if (isa<CallBase>(value)) { appendTrace(result, value, inverted); return; }
  if (auto *cast = dyn_cast<CastInst>(value)) {
    if (cast->getSrcTy()->isIntegerTy() && cast->getDestTy()->isIntegerTy())
      traces(cast->getOperand(0), result, inverted, depth + 1, limit);
    return;
  }
  if (auto *binary = dyn_cast<BinaryOperator>(value)) {
    if (binary->getOpcode() == Instruction::Xor && binary->getType()->isIntegerTy(1)) {
      auto *constant = dyn_cast<ConstantInt>(binary->getOperand(1));
      if (constant && constant->isOne()) traces(binary->getOperand(0), result, !inverted, depth + 1, limit);
    }
    return;
  }
  if (auto *phi = dyn_cast<PHINode>(value)) {
    for (Value *incoming : phi->incoming_values()) traces(incoming, result, inverted, depth + 1, limit);
    return;
  }
  if (auto *select = dyn_cast<SelectInst>(value)) {
    traces(select->getTrueValue(), result, inverted, depth + 1, limit);
    traces(select->getFalseValue(), result, inverted, depth + 1, limit);
  }
}
json::Object predicate(StringRef kind, unsigned bits, const APInt *constant = nullptr) {
  return json::Object{{"kind", kind.str()}, {"bits", int64_t(bits)},
    {"hex", constant ? json::Value(hex(*constant)) : json::Value(nullptr)}, {"negated", false}};
}
json::Object invert(json::Object value) {
  auto kind = value.getString("kind");
  if (kind == "eq") value["kind"] = "ne";
  else if (kind == "ne") value["kind"] = "eq";
  else if (kind == "zero") value["kind"] = "nonzero";
  else value["kind"] = "zero";
  return value;
}
struct Condition {
  std::vector<Trace> sources;
  json::Object whenTrue;
  bool supported = false;
};
Condition condition(Value *value, size_t limit) {
  Condition result;
  bool booleanInverted = false;
  if (auto *binary = dyn_cast<BinaryOperator>(value)) {
    if (binary->getOpcode() == Instruction::Xor && binary->getType()->isIntegerTy(1)) {
      if (auto *constant = dyn_cast<ConstantInt>(binary->getOperand(1)); constant && constant->isOne()) {
        value = binary->getOperand(0);
        booleanInverted = true;
      }
    }
  }
  if (auto *compare = dyn_cast<ICmpInst>(value)) {
    if (compare->getPredicate() != ICmpInst::ICMP_EQ && compare->getPredicate() != ICmpInst::ICMP_NE) return result;
    ConstantInt *constant = dyn_cast<ConstantInt>(compare->getOperand(1));
    Value *input = compare->getOperand(0);
    if (!constant) { constant = dyn_cast<ConstantInt>(compare->getOperand(0)); input = compare->getOperand(1); }
    if (!constant) return result;
    traces(input, result.sources, false, 0, limit);
    result.whenTrue = predicate(compare->getPredicate() == ICmpInst::ICMP_EQ ? "eq" : "ne",
                                constant->getBitWidth(), &constant->getValue());
    if (booleanInverted) result.whenTrue = invert(std::move(result.whenTrue));
    result.supported = !result.sources.empty();
    return result;
  }
  traces(value, result.sources, booleanInverted, 0, limit);
  if (!result.sources.empty() && value->getType()->isIntegerTy()) {
    result.whenTrue = predicate("nonzero", value->getType()->getIntegerBitWidth());
    result.supported = true;
  }
  return result;
}
json::Object accessFor(Instruction &instruction, StringRef kind, Value *pointer, Type *type, Value *written,
                       bool atomic, bool volatileFlag, StringRef order, StringRef scope,
                       bool isRepeated, Module &module, StringRef artifact, StringRef function,
                       const DenseMap<const Value *, std::string> &ids) {
  auto source = sourceRef(artifact, function.str(), ids.lookup(&instruction));
  auto range = objectRange(pointer, type, module, artifact, function, ids);
  bool exactRange = !range.object.getAsNull() && range.size.has_value();
  return json::Object{{"id", ids.lookup(&instruction)}, {"source", json::Object(source)}, {"kind", kind.str()},
    {"atomic", atomic}, {"volatile", volatileFlag}, {"ordering", order.empty() ? json::Value(nullptr) : json::Value(order.str())},
    {"syncscope", scope.empty() ? json::Value(nullptr) : json::Value(scope.str())}, {"range", rangeJson(range)},
    {"value", written ? json::Value(scalar(written)) : json::Value(unknown("read-value-runtime"))},
    {"multiplicity", isRepeated ? "repeated" : "single"}, {"proof", json::Array{json::Object(source)}},
    {"status", exactRange ? "exact" : "unknown"}, {"reason", exactRange ? json::Value(nullptr) : json::Value("object-range-unresolved")}};
}
} // namespace

json::Object publicationFacts(Module &module, const json::Object &origin, const json::Object &budgets) {
  const auto artifact = origin.getString("artifact_key")->str();
  auto ids = originalIdentities(module, artifact);
  Limit limit{*budgets.getInteger("local_steps")};
  size_t candidates = size_t(*budgets.getInteger("value_candidates"));
  json::Array accesses, initializers, observations, gates, returns, order, evidence, diagnostics, frontier;
  std::map<const Instruction *, std::string> accessIds;

  for (auto &global : module.globals()) {
    if (!limit.take()) break;
    if (!global.hasInitializer() || module.getDataLayoutStr().empty()) continue;
    auto bytes = module.getDataLayout().getTypeStoreSize(global.getValueType());
    if (bytes.isScalable()) continue;
    auto source = sourceRef(artifact, nullptr, ids.lookup(&global));
    Range range{json::Object(source), 0, bytes.getFixedValue(), global.getAddressSpace()};
    json::Object value = unknown("non-scalar-initializer");
    StringRef status = "unknown"; json::Value reason = "non-scalar-initializer";
    if (auto *integer = dyn_cast<ConstantInt>(global.getInitializer())) {
      value = exact(integer->getValue()); status = "exact"; reason = nullptr;
    } else if (global.getInitializer()->isNullValue()) {
      value = exact(APInt(unsigned(bytes.getFixedValue() * 8), 0)); status = "exact"; reason = nullptr;
    }
    json::Object seed{{"kind", "initializer"}, {"source", json::Object(source)}, {"range", rangeJson(range)}};
    initializers.push_back(json::Object{{"id", analysisDigest(json::Value(json::Object(seed)))},
      {"source", json::Object(source)}, {"range", rangeJson(range)}, {"value", std::move(value)},
      {"proof", json::Array{json::Object(source)}}, {"status", status.str()}, {"reason", std::move(reason)}});
  }

  for (auto &function : module) {
    if (function.isDeclaration() || limit.exhausted) continue;
    const auto fid = ids.lookup(&function);
    DominatorTree dominators(function);
    LoopInfo loops(dominators);
    std::vector<Instruction *> functionAccesses;
    for (auto &block : function) for (auto &instruction : block) {
      if (!limit.take()) break;
      json::Object access;
      if (auto *load = dyn_cast<LoadInst>(&instruction))
        access = accessFor(instruction, "read", load->getPointerOperand(), load->getType(), nullptr,
          load->isAtomic(), load->isVolatile(), load->isAtomic() ? ordering(load->getOrdering()) : StringRef{},
          load->isAtomic() ? syncscope(module.getContext(), load->getSyncScopeID()) : StringRef{}, repeated(instruction, loops),
          module, artifact, fid, ids);
      else if (auto *store = dyn_cast<StoreInst>(&instruction))
        access = accessFor(instruction, "write", store->getPointerOperand(), store->getValueOperand()->getType(), store->getValueOperand(),
          store->isAtomic(), store->isVolatile(), store->isAtomic() ? ordering(store->getOrdering()) : StringRef{},
          store->isAtomic() ? syncscope(module.getContext(), store->getSyncScopeID()) : StringRef{}, repeated(instruction, loops),
          module, artifact, fid, ids);
      else if (auto *rmw = dyn_cast<AtomicRMWInst>(&instruction))
        access = accessFor(instruction, "rmw", rmw->getPointerOperand(), rmw->getValOperand()->getType(), rmw->getValOperand(),
          true, rmw->isVolatile(), ordering(rmw->getOrdering()), syncscope(module.getContext(), rmw->getSyncScopeID()),
          repeated(instruction, loops), module, artifact, fid, ids);
      else if (auto *cas = dyn_cast<AtomicCmpXchgInst>(&instruction))
        access = accessFor(instruction, "cas", cas->getPointerOperand(), cas->getCompareOperand()->getType(), cas->getNewValOperand(),
          true, cas->isVolatile(), ordering(cas->getSuccessOrdering()), syncscope(module.getContext(), cas->getSyncScopeID()),
          repeated(instruction, loops), module, artifact, fid, ids);
      else if (auto *fence = dyn_cast<FenceInst>(&instruction)) {
        auto source = sourceRef(artifact, fid, ids.lookup(fence));
        access = json::Object{{"id", ids.lookup(fence)}, {"source", json::Object(source)}, {"kind", "fence"},
          {"atomic", true}, {"volatile", false}, {"ordering", ordering(fence->getOrdering())},
          {"syncscope", syncscope(module.getContext(), fence->getSyncScopeID())}, {"range", rangeJson(Range{})},
          {"value", unknown("not-applicable")}, {"multiplicity", repeated(instruction, loops) ? "repeated" : "single"},
          {"proof", json::Array{json::Object(source)}}, {"status", "exact"}, {"reason", nullptr}};
      }
      if (!access.empty()) {
        accessIds[&instruction] = access.getString("id")->str();
        functionAccesses.push_back(&instruction);
        accesses.push_back(std::move(access));
      }
    }

    // This P4-local proof is intentionally independent of EffectSummary.order.
    // Restrict cross-block dominance to non-repeated accesses: instruction
    // dominance then proves that every occurrence of `after` is preceded by
    // the unique occurrence of `before`, without inventing loop-instance
    // ordering.  Same-block order is covered by the same dominance query.
    for (Instruction *before : functionAccesses) {
      if (repeated(*before, loops)) continue;
      for (Instruction *after : functionAccesses) {
        if (before == after || repeated(*after, loops)) continue;
        if (!limit.take()) break;
        if (!dominators.dominates(before, after)) continue;
        auto beforeSource = sourceRef(artifact, fid, ids.lookup(before));
        auto afterSource = sourceRef(artifact, fid, ids.lookup(after));
        json::Object seed{{"kind", "p4-dominance-order"},
          {"before", json::Object(beforeSource)}, {"after", json::Object(afterSource)}};
        auto edgeId = analysisDigest(json::Value(json::Object(seed)));
        auto proof = analysisRef(artifact, fid, edgeId);
        evidence.push_back(json::Object{{"ref", json::Object(proof)}, {"kind", "publication-order"},
          {"source", json::Object(afterSource)},
          {"inputs", json::Array{json::Object(beforeSource), json::Object(afterSource)}},
          {"result", "must-before"}});
        order.push_back(json::Object{{"id", edgeId}, {"before", json::Object(beforeSource)},
          {"after", json::Object(afterSource)}, {"relation", "must-before"},
          {"proof", json::Array{std::move(proof)}}, {"reason", "p4-dominance-order"}});
      }
      if (limit.exhausted) break;
    }

    // Calls used as conditions are registered as boundary accesses.  They are
    // rebound to a verified callee ReturnDependency by the Python composer.
    for (auto &block : function) for (auto &instruction : block) {
      auto *branch = dyn_cast<BranchInst>(&instruction);
      if (!branch || !branch->isConditional() || !limit.take()) continue;
      auto info = condition(branch->getCondition(), candidates);
      if (!info.supported) continue;
      for (const auto &trace : info.sources) {
        auto *originInstruction = cast<Instruction>(trace.origin);
        if (!accessIds.count(originInstruction)) {
          assert(isa<CallBase>(originInstruction) && "unregistered observation origin must be a call");
          auto source = sourceRef(artifact, fid, ids.lookup(originInstruction));
          json::Object callAccess{{"id", ids.lookup(originInstruction)}, {"source", json::Object(source)}, {"kind", "call"},
            {"atomic", false}, {"volatile", false}, {"ordering", nullptr}, {"syncscope", nullptr},
            {"range", rangeJson(Range{})}, {"value", unknown("callee-return")},
            {"multiplicity", repeated(*originInstruction, loops) ? "repeated" : "single"},
            {"proof", json::Array{json::Object(source)}}, {"status", "candidate"}, {"reason", "callee-return"}};
          accessIds[originInstruction] = ids.lookup(originInstruction); accesses.push_back(std::move(callAccess));
        }
        for (unsigned edge = 0; edge < 2; ++edge) {
          json::Object pred = edge == 0 ? json::Object(info.whenTrue) : invert(json::Object(info.whenTrue));
          if (trace.inverted) pred = invert(std::move(pred));
          auto originSource = sourceRef(artifact, fid, ids.lookup(originInstruction));
          auto termSource = sourceRef(artifact, fid, ids.lookup(branch));
          auto targetSource = sourceRef(artifact, fid, ids.lookup(branch->getSuccessor(edge)));
          json::Object obsSeed{{"kind", "observation"}, {"source", json::Object(originSource)},
            {"terminator", json::Object(termSource)}, {"edge", int64_t(edge)}, {"predicate", json::Object(pred)}};
          auto observationId = analysisDigest(json::Value(json::Object(obsSeed)));
          observations.push_back(json::Object{{"id", observationId}, {"source", json::Object(originSource)},
            {"access_id", accessIds[originInstruction]}, {"predicate", json::Object(pred)},
            {"result_source", json::Object(termSource)}, {"proof", json::Array{json::Object(originSource), json::Object(termSource)}},
            {"status", "exact"}, {"reason", nullptr}});
          json::Array controlled;
          BasicBlock *target = branch->getSuccessor(edge);
          bool exactEdge = target->getUniquePredecessor() == branch->getParent();
          for (auto &candidate : function)
            if (dominators.dominates(target, &candidate))
              controlled.push_back(sourceRef(artifact, fid, ids.lookup(&candidate)));
          unsigned other = edge ? 0 : 1;
          bool retry = isPotentiallyReachable(branch->getSuccessor(other), originInstruction->getParent());
          json::Object gateSeed{{"kind", "gate"}, {"observation", observationId}, {"edge", int64_t(edge)}};
          auto gateId = analysisDigest(json::Value(json::Object(gateSeed)));
          auto proof = analysisRef(artifact, fid, gateId);
          evidence.push_back(json::Object{{"ref", json::Object(proof)}, {"kind", "publication-gate"},
            {"source", json::Object(termSource)}, {"inputs", json::Array{json::Object(originSource), json::Object(termSource)}},
            {"result", exactEdge ? "exact" : "candidate"}});
          gates.push_back(json::Object{{"id", gateId}, {"observation_id", observationId},
            {"terminator", json::Object(termSource)}, {"success_edge", int64_t(edge)},
            {"success_target", json::Object(targetSource)}, {"retry_edge", retry ? json::Value(int64_t(other)) : json::Value(nullptr)},
            {"controlled_blocks", std::move(controlled)}, {"repeated", repeated(*originInstruction, loops)},
            {"proof", json::Array{std::move(proof)}}, {"status", exactEdge ? "exact" : "candidate"},
            {"reason", exactEdge ? json::Value(nullptr) : json::Value("non-unique-success-edge")}});
        }
      }
    }

    for (auto &block : function) for (auto &instruction : block) {
      auto *ret = dyn_cast<ReturnInst>(&instruction);
      if (!ret || !ret->getReturnValue() || !limit.take()) continue;
      auto returnCondition = condition(ret->getReturnValue(), candidates);
      std::vector<Trace> sources = returnCondition.sources;
      if (sources.empty()) traces(ret->getReturnValue(), sources, false, 0, candidates);
      for (const auto &trace : sources) {
        auto *originInstruction = cast<Instruction>(trace.origin);
        if (!isa<LoadInst>(originInstruction) || !accessIds.count(originInstruction)) continue;
        auto originSource = sourceRef(artifact, fid, ids.lookup(originInstruction));
        auto returnSource = sourceRef(artifact, fid, ids.lookup(ret));
        json::Value returnPredicate = nullptr;
        if (returnCondition.supported) {
          auto normalized = json::Object(returnCondition.whenTrue);
          if (trace.inverted) normalized = invert(std::move(normalized));
          returnPredicate = std::move(normalized);
        }
        json::Object seed{{"kind", "return-observation"}, {"source", json::Object(originSource)},
          {"return", json::Object(returnSource)}};
        auto observationId = analysisDigest(json::Value(json::Object(seed)));
        observations.push_back(json::Object{{"id", observationId}, {"source", json::Object(originSource)},
          {"access_id", accessIds[originInstruction]}, {"predicate", returnPredicate}, {"result_source", json::Object(returnSource)},
          {"proof", json::Array{json::Object(originSource), json::Object(returnSource)}}, {"status", "exact"}, {"reason", nullptr}});
        auto returnId = analysisDigest(json::Value(json::Object{{"observation", observationId}, {"return", json::Object(returnSource)}}));
        returns.push_back(json::Object{{"id", returnId}, {"observation_id", observationId}, {"source", json::Object(returnSource)},
          {"predicate", std::move(returnPredicate)}, {"proof", json::Array{json::Object(originSource), json::Object(returnSource)}},
          {"status", "exact"}, {"reason", nullptr}});
      }
    }
  }
  if (limit.exhausted) {
    auto item = bilingual("publication-local-budget", "LLVM 发布局部事实超过预算",
                          "LLVM publication-local facts exceeded the budget");
    diagnostics.push_back(json::Object(item)); frontier.push_back(std::move(item));
  }
  return json::Object{{"schema_version", 1}, {"kind", "PublicationLocalFacts"},
    {"analysis_version", "0.1.0"}, {"policy_id", "single-publication-risks-v1"},
    {"origin", json::Object(origin)}, {"budgets", json::Object(budgets)},
    {"accesses", std::move(accesses)}, {"initializers", std::move(initializers)},
    {"observations", std::move(observations)}, {"gates", std::move(gates)}, {"returns", std::move(returns)},
    {"order", std::move(order)},
    {"analysis_evidence", std::move(evidence)}, {"diagnostics", std::move(diagnostics)},
    {"frontier", std::move(frontier)}, {"status", limit.exhausted ? "partial" : "complete"}};
}
} // namespace moa
