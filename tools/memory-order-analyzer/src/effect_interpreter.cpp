#include "effect_interpreter.h"
#include "effect_control.h"
#include <llvm/ADT/DenseSet.h>
#include <llvm/ADT/SmallString.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/DataLayout.h>
#include <llvm/IR/IntrinsicInst.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/Dominators.h>
#include <llvm/Support/raw_ostream.h>
#include <algorithm>
#include <cctype>
#include <deque>
#include <map>
#include <set>

using namespace llvm;
namespace moa {
namespace {

struct Slot {
  PointerValue pointer;
  std::optional<APInt> size;
  ControlDomain value;
  json::Object proof;
};
struct State {
  DenseMap<const Value *, ControlDomain> values;
  std::vector<Slot> slots;
  json::Array guards;
};
struct Work {
  BasicBlock *block;
  BasicBlock *predecessor;
  unsigned edge;
  State state;
};

bool equal(const json::Value &a, const json::Value &b) { return a == b; }
void appendUnique(json::Array &target, const json::Array &items) {
  for (const auto &item : items)
    if (!llvm::any_of(target, [&](const auto &old) { return equal(old, item); }))
      target.push_back(item);
}
json::Object source(StringRef artifact, StringRef function, StringRef id) {
  return json::Object{{"artifact_key", artifact.str()},
                      {"function_id", function.empty() ? json::Value(nullptr) : json::Value(function.str())},
                      {"id", id.str()}};
}
std::string signedText(const APInt &value) {
  SmallString<64> text;
  value.toStringSigned(text);
  return text.str().str();
}
std::string hexText(const APInt &value) {
  SmallString<64> text;
  value.toString(text, 16, false, false);
  std::string result = text.str().str();
  std::transform(result.begin(), result.end(), result.begin(), [](unsigned char c) { return char(std::toupper(c)); });
  return result.empty() ? "0" : result;
}
json::Object integer(const APInt &value) {
  return json::Object{{"kind", "integer"}, {"bits", value.getBitWidth()}, {"hex", hexText(value)}};
}
ControlDomain one(json::Object value, json::Array guards = {}, json::Array proof = {}) {
  ControlDomain result;
  result.candidates.push_back({std::move(value), std::move(guards), std::move(proof)});
  return result;
}
ControlDomain top(StringRef reason) { return {{}, reason.str()}; }

ControlDomain fromJson(const json::Value &value) {
  auto *domain = value.getAsObject();
  if (!domain || domain->getString("state") != "finite") {
    auto reason = domain ? domain->getString("reason") : std::optional<StringRef>{};
    return top(reason && !reason->empty() ? *reason : "unknown_argument");
  }
  ControlDomain result;
  auto *candidates = domain->getArray("candidates");
  if (!candidates || candidates->empty()) return top("empty_argument_domain");
  for (const auto &item : *candidates) {
    auto *candidate = item.getAsObject();
    if (!candidate || !candidate->getObject("value")) return top("invalid_argument_domain");
    result.candidates.push_back({json::Object(*candidate->getObject("value")),
      candidate->getArray("guards") ? json::Array(*candidate->getArray("guards")) : json::Array{},
      candidate->getArray("proof") ? json::Array(*candidate->getArray("proof")) : json::Array{}});
  }
  return result;
}
json::Object toJson(const ControlDomain &domain) {
  json::Array candidates;
  for (const auto &candidate : domain.candidates)
    candidates.push_back(json::Object{{"value", json::Object(candidate.value)},
      {"guards", json::Array(candidate.guards)}, {"proof", json::Array(candidate.proof)}});
  if (!domain.unknown.empty())
    return json::Object{{"state", "unknown"}, {"candidates", json::Array{}}, {"reason", domain.unknown}};
  if (candidates.empty())
    return json::Object{{"state", "unknown"}, {"candidates", json::Array{}}, {"reason", "internal_bottom"}};
  return json::Object{{"state", "finite"}, {"candidates", std::move(candidates)}, {"reason", nullptr}};
}
ControlDomain withPath(ControlDomain domain, const json::Array &guards) {
  if (!domain.unknown.empty()) return domain;
  for (auto &candidate : domain.candidates) appendUnique(candidate.guards, guards);
  return domain;
}

std::optional<APInt> byteSize(Type *type, const DataLayout &layout) {
  if (!type->isSized()) return {};
  auto size = layout.getTypeStoreSize(type);
  if (size.isScalable()) return {};
  return APInt(64, size.getFixedValue());
}
json::Object pointerJson(const PointerValue &pointer) {
  // Parameters are installed from the request before interpretation.  A GEP
  // rooted at one is serialized in resolve(), where the GEP instruction can
  // be retained as expression evidence.  This helper therefore only receives
  // allocation/global objects from pointerValue().
  json::Value allocation = nullptr;
  if (pointer.kind == ObjectKind::Local) {
    const char *cardinality = pointer.cardinality == Cardinality::Single ? "single" :
                              pointer.cardinality == Cardinality::Merged ? "merged" : "unknown";
    allocation = json::Object{{"invocation_id", pointer.invocation}, {"cardinality", cardinality},
      {"reason", pointer.reason.empty() ? json::Value(nullptr) : json::Value(pointer.reason)}};
  }
  return json::Object{{"kind", "object"},
    {"source", source(pointer.artifact, pointer.function, pointer.source)},
    {"offset", pointer.offset ? json::Value(signedText(*pointer.offset)) : json::Value(nullptr)},
    {"address_space", pointer.addressSpace}, {"allocation", std::move(allocation)}};
}

std::string ordering(AtomicOrdering value) {
  switch (value) {
  case AtomicOrdering::NotAtomic: return "not_atomic";
  case AtomicOrdering::Unordered: return "unordered";
  case AtomicOrdering::Monotonic: return "monotonic";
  case AtomicOrdering::Acquire: return "acquire";
  case AtomicOrdering::Release: return "release";
  case AtomicOrdering::AcquireRelease: return "acq_rel";
  case AtomicOrdering::SequentiallyConsistent: return "seq_cst";
  }
  return "unknown";
}
std::string syncScope(LLVMContext &context, SyncScope::ID id) {
  if (id == SyncScope::System) return "system";
  if (id == SyncScope::SingleThread) return "singlethread";
  SmallVector<StringRef> names;
  context.getSyncScopeNames(names);
  return id < names.size() ? names[id].str() : "unknown";
}

class Interpreter {
public:
  Interpreter(Module &module, Function &function, const json::Object &request,
              const DenseMap<const Value *, std::string> &ids, const json::Array *summaries)
      : module(module), function(function), request(request), ids(ids),
        artifact(request.getObject("function")->getString("artifact_key")->str()),
        fid(ids.lookup(&function)), context(request.getString("context_id")->str()),
        invocation(request.getString("invocation_id")->str()), dominators(function) {
    auto *b = request.getObject("budgets");
    budget.limit = unsigned(*b->getInteger("local_steps"));
    budget.candidates = unsigned(*b->getInteger("value_candidates"));
    stateLimit = unsigned(*b->getInteger("condition_states"));
    effectLimit = unsigned(*b->getInteger("effect_items"));
    for (const auto &item : *request.getArray("invocations")) {
      auto *entry = item.getAsObject();
      if (entry && entry->getString("id") == invocation) {
        auto cardinality = entry->getString("cardinality");
        invocationCardinality = cardinality == "single" ? Cardinality::Single :
                                cardinality == "merged" ? Cardinality::Merged : Cardinality::Unknown;
      }
    }
    if (summaries) {
      std::map<std::string, const json::Object *> byContext;
      for (const auto &item : *summaries) {
        const auto *summary = item.getAsObject();
        if (!summary || summary->getString("kind") != "EffectSummary" || !summary->getString("context_id"))
          throw std::runtime_error("analysis_request: invalid dependency summary");
        byContext[summary->getString("context_id")->str()] = summary;
      }
      for (const auto &dependency : *request.getArray("dependencies")) {
        const auto *item = dependency.getAsObject();
        auto found = item && item->getString("context_id") ? byContext.find(item->getString("context_id")->str()) : byContext.end();
        if (!item || found == byContext.end() || item->getString("digest") != analysisDigest(json::Object(*found->second)))
          throw std::runtime_error("analysis_request: dependency summary mismatch");
      }
      for (const auto &binding : *request.getArray("call_bindings")) {
        const auto *item = binding.getAsObject();
        auto found = item && item->getString("context_id") ? byContext.find(item->getString("context_id")->str()) : byContext.end();
        if (!item || !item->getObject("source") || found == byContext.end())
          throw std::runtime_error("analysis_request: invalid call binding");
        boundCalls[item->getObject("source")->getString("id")->str()] = found->second;
      }
    }
  }

  json::Object run() {
    State initial;
    unsigned index = 0;
    for (auto &argument : function.args()) {
      initial.values[&argument] = fromJson((*request.getArray("arguments"))[index++]);
      for (auto &candidate : initial.values[&argument].candidates)
        if (candidate.value.getString("kind") == "parameter" && candidate.value.get("invocation_id") &&
            candidate.value.get("invocation_id")->getAsNull())
          candidate.value["invocation_id"] = invocation;
      if (!initial.values[&argument].unknown.empty()) pending(&argument, initial.values[&argument].unknown);
    }
    queue.push_back({&function.getEntryBlock(), nullptr, 0, std::move(initial)});
    while (!queue.empty() && !cutoff) {
      Work item = std::move(queue.front()); queue.pop_front();
      if (!budget.spend()) { pending(item.block, "local_steps_budget"); break; }
      auto signature = stateKey(item);
      if (!seen.insert(signature).second) continue;
      if (++states > stateLimit) { pending(item.block, "condition_states_budget"); break; }
      reachable.insert(item.block);
      execute(item);
    }
    if (cutoff) for (const auto &item : queue) pending(item.block, cutoffReason);
    publishValues();
    publishBlocks();
    auto status = frontier.empty() ? "complete" : "partial";
    return json::Object{{"values", std::move(values)}, {"blocks", std::move(blocks)},
      {"call_requests", std::move(calls)}, {"effects", std::move(effects)},
      {"order", std::move(order)}, {"returns", std::move(returns)}, {"escape", std::move(escape)},
      {"resolutions", std::move(resolutions)}, {"diagnostics", json::Array(diagnostics)},
      {"frontier", std::move(frontier)}, {"status", status}, {"steps", budget.steps}};
  }

private:
  Module &module;
  Function &function;
  const json::Object &request;
  const DenseMap<const Value *, std::string> &ids;
  std::string artifact, fid, context, invocation;
  Cardinality invocationCardinality = Cardinality::Unknown;
  DominatorTree dominators;
  ControlBudget budget;
  unsigned stateLimit = 32, effectLimit = 10000, states = 0;
  bool cutoff = false;
  std::string cutoffReason;
  std::deque<Work> queue;
  std::set<std::string> seen;
  DenseSet<const BasicBlock *> reachable, pendingBlocks;
  json::Array values, blocks, calls, effects, order, returns, escape, resolutions, diagnostics, frontier;
  std::map<std::string, std::pair<json::Object, ControlDomain>> outputValues;
  std::map<std::string, const json::Object *> boundCalls;
  std::set<std::string> frontierKeys, escapedValues;
  std::string previousEffect;

  json::Object ref(const Value *value) const {
    return source(artifact, isa<GlobalValue>(value) ? StringRef{} : StringRef(fid), ids.lookup(value));
  }
  void pending(const Value *value, StringRef reason) {
    auto *block = dyn_cast<BasicBlock>(value);
    if (!block) block = dyn_cast<Instruction>(value) ? cast<Instruction>(value)->getParent() : nullptr;
    if (block) pendingBlocks.insert(block);
    std::string key = ids.lookup(value) + ":" + reason.str();
    if (!frontierKeys.insert(key).second) return;
    json::Object diagnostic{{"code", reason.str()}, {"detail", "bounded local evaluation retained unknown work"},
      {"source", ref(value)}, {"context_id", context}};
    frontier.push_back(json::Object(diagnostic)); diagnostics.push_back(std::move(diagnostic));
  }
  void stop(const Value *value, StringRef reason) {
    cutoff = true; cutoffReason = reason.str(); pending(value, reason);
  }
  std::string stateKey(const Work &work) {
    std::vector<std::string> parts;
    parts.push_back(ids.lookup(work.block));
    parts.push_back(work.predecessor ? ids.lookup(work.predecessor) : "entry");
    parts.push_back(std::to_string(work.edge));
    for (const auto &entry : work.state.values)
      if (auto id = ids.lookup(entry.first); !id.empty())
        parts.push_back(id + analysisDigest(toJson(entry.second)));
    for (const auto &slot : work.state.slots)
      parts.push_back(slot.pointer.source + ":" + (slot.pointer.offset ? signedText(*slot.pointer.offset) : "?") +
                      ":" + analysisDigest(toJson(slot.value)));
    for (const auto &guard : work.state.guards) parts.push_back(analysisDigest(guard));
    std::sort(parts.begin() + 3, parts.end());
    std::string result;
    for (const auto &part : parts) result += part + "|";
    return result;
  }
  void emitValue(const Value *value, const ControlDomain &domain) {
    auto id = ids.lookup(value);
    if (id.empty()) return;
    auto found = outputValues.find(id);
    if (found == outputValues.end()) {
      outputValues.emplace(id, std::make_pair(ref(value), domain));
      return;
    }
    found->second.second = joinControl(found->second.second, domain, budget);
    if (!found->second.second.unknown.empty()) pending(value, found->second.second.unknown);
  }
  void publishValues() {
    for (auto &[id, entry] : outputValues) {
      (void)id;
      values.push_back(json::Object{{"source", std::move(entry.first)},
                                    {"domain", toJson(entry.second)}});
    }
  }
  ControlDomain resolve(const Value *value, State &state) {
    if (auto found = state.values.find(value); found != state.values.end())
      return withPath(found->second, state.guards);
    ControlDomain result;
    if (auto *constant = dyn_cast<ConstantInt>(value)) result = one(integer(constant->getValue()));
    else if (isa<ConstantPointerNull>(value)) result = one(json::Object{{"kind", "null"},
      {"address_space", value->getType()->getPointerAddressSpace()}});
    else if (isa<PoisonValue>(value)) result = one(json::Object{{"kind", "poison"}, {"reason", "llvm_poison"}});
    else if (isa<UndefValue>(value)) result = one(json::Object{{"kind", "undef"}, {"reason", "llvm_undef"}});
    else if (auto *gep = dyn_cast<GEPOperator>(value)) {
      if (module.getDataLayoutStr().empty()) result = top("missing_data_layout");
      else if (auto offset = constantByteOffset(*gep, module.getDataLayout())) {
        auto base = resolve(gep->getPointerOperand(), state);
        if (!base.unknown.empty()) result = base;
        else {
          for (auto candidate : base.candidates) {
            if (candidate.value.getString("kind") == "parameter") {
              candidate.value = json::Object{{"kind", "expression"}, {"source", ref(value)},
                {"invocation_id", invocation},
                {"operands", json::Array{json::Object(candidate.value), integer(*offset)}}};
              result.candidates.push_back(std::move(candidate));
              continue;
            }
            auto text = candidate.value.getString("offset");
            if (candidate.value.getString("kind") != "object" || !text) { result = top("unsupported_pointer_origin"); break; }
            int64_t oldOffset = 0;
            if (text->getAsInteger(10, oldOffset) || !offset->isSignedIntN(64)) { result = top("pointer_offset_overflow"); break; }
            int64_t sum = 0;
            if (__builtin_add_overflow(oldOffset, offset->getSExtValue(), &sum)) { result = top("pointer_offset_overflow"); break; }
            candidate.value["offset"] = std::to_string(sum);
            result.candidates.push_back(std::move(candidate));
          }
        }
      } else result = top("dynamic_pointer_offset");
    } else if (value->getType()->isPointerTy()) {
      GlobalBindings bindings;
      auto pointer = pointerValue(value, module, artifact, *request.getString("scope_id"), invocation,
                                  invocationCardinality, bindings, budget.limit - budget.steps);
      result = pointer.known() ? one(pointerJson(pointer), {}, json::Array{ref(value)}) : top(pointer.reason);
    } else result = top("unresolved_value");
    state.values[value] = result;
    return withPath(result, state.guards);
  }
  ControlDomain scalar(Instruction &instruction, State &state) {
    SmallVector<json::Object> operands;
    json::Array guards, proof;
    for (const auto &operand : instruction.operands()) {
      auto domain = resolve(operand, state);
      if (!domain.unknown.empty() || domain.candidates.size() != 1)
        return top(domain.unknown.empty() ? "non_single_scalar_input" : domain.unknown);
      operands.push_back(json::Object(domain.candidates[0].value));
      appendUnique(guards, domain.candidates[0].guards); appendUnique(proof, domain.candidates[0].proof);
    }
    if (!budget.spend()) return top("local_steps_budget");
    auto value = foldScalar(instruction, operands);
    if (value.getString("kind") == "unknown")
      value = symbolicScalar(instruction, operands, ref(&instruction), invocation);
    if (value.getString("kind") == "unknown")
      return top(value.getString("reason").value_or("unsupported_scalar_operation"));
    proof.push_back(ref(&instruction));
    return one(std::move(value), std::move(guards), std::move(proof));
  }
  PointerValue pointer(const Value *value) {
    GlobalBindings bindings;
    return pointerValue(value, module, artifact, *request.getString("scope_id"), invocation,
                        invocationCardinality, bindings, budget.limit - budget.steps);
  }
  bool privatePointer(const PointerValue &value) const {
    return value.kind == ObjectKind::Local && value.cardinality == Cardinality::Single && value.offset.has_value();
  }
  void storePrivate(const PointerValue &target, std::optional<APInt> size, ControlDomain value,
                    const json::Object &proof, State &state) {
    if (!privatePointer(target) || !size) return;
    for (auto &slot : state.slots) {
      auto relation = compareRanges(target, size, slot.pointer, slot.size);
      if (relation == RangeRelation::Unknown) slot.value = top("possible_alias_overwrite");
    }
    state.slots.erase(std::remove_if(state.slots.begin(), state.slots.end(), [&](const Slot &slot) {
      return compareRanges(target, size, slot.pointer, slot.size) == RangeRelation::Overlap;
    }), state.slots.end());
    state.slots.push_back({target, size, std::move(value), json::Object(proof)});
  }
  ControlDomain loadPrivate(const PointerValue &target, std::optional<APInt> size, State &state, Instruction &load) {
    if (!privatePointer(target) || !size) return top("non_private_load");
    for (const auto &slot : state.slots) {
      auto relation = compareRanges(target, size, slot.pointer, slot.size);
      if (relation != RangeRelation::Overlap) continue;
      if (slot.pointer.source == target.source && slot.pointer.offset == target.offset && slot.size == size) {
        auto result = slot.value;
        for (auto &candidate : result.candidates) candidate.proof.push_back(ref(&load));
        return result;
      }
      return top("partial_overlap_load");
    }
    return top("uninitialized_load");
  }
  void invalidateTouched(CallBase &call, State &state) {
    for (const auto &argument : call.args()) {
      if (!argument->getType()->isPointerTy()) continue;
      recordEscape(resolve(argument, state), "unknown_call_escape");
      auto target = pointer(argument);
      state.slots.erase(std::remove_if(state.slots.begin(), state.slots.end(), [&](const Slot &slot) {
        return compareRanges(target, {}, slot.pointer, slot.size) != RangeRelation::Disjoint;
      }), state.slots.end());
    }
  }
  void recordEscape(const ControlDomain &domain, StringRef reason) {
    bool recorded = false;
    for (const auto &candidate : domain.candidates) {
      auto kind = candidate.value.getString("kind");
      if (kind != "object" && kind != "parameter") continue;
      auto key = analysisDigest(json::Object(candidate.value));
      if (escapedValues.insert(key).second) escape.push_back(json::Object(candidate.value));
      recorded = true;
    }
    if ((!domain.unknown.empty() || !recorded) && escapedValues.insert("unknown:" + reason.str()).second)
      escape.push_back(json::Object{{"kind", "unknown"}, {"reason", reason.str()}});
  }
  void invalidateEscaped(const ControlDomain &domain, State &state) {
    state.slots.erase(std::remove_if(state.slots.begin(), state.slots.end(), [&](const Slot &slot) {
      for (const auto &candidate : domain.candidates) {
        const auto *source = candidate.value.getObject("source");
        const auto *allocation = candidate.value.getObject("allocation");
        if (candidate.value.getString("kind") == "object" && source && allocation &&
            source->getString("id") == slot.pointer.source &&
            allocation->getString("invocation_id") == slot.pointer.invocation) return true;
      }
      return false;
    }), state.slots.end());
  }
  ControlDomain substituteReturn(const json::Object &summary, CallBase &call, State &state) {
    std::map<std::string, std::pair<ControlDomain, unsigned>> actuals;
    const auto *root = summary.getObject("root");
    const auto *formals = root ? root->getArray("arguments") : nullptr;
    if (!formals || formals->size() != call.arg_size()) return top("callee_return_binding_mismatch");
    for (unsigned index = 0; index < formals->size(); ++index) {
      const auto *formal = (*formals)[index].getAsObject();
      if (formal && formal->getString("kind") == "parameter" && formal->getObject("source"))
        actuals[formal->getObject("source")->getString("id")->str()] =
          {resolve(call.getArgOperand(index), state), call.getArgOperand(index)->getType()->getPointerAddressSpace()};
    }
    auto substitute = [&](auto &&self, json::Object value) -> ControlDomain {
      auto kind = value.getString("kind");
      auto *valueSource = value.getObject("source");
      auto found = valueSource ? actuals.find(valueSource->getString("id")->str()) : actuals.end();
      if (kind == "parameter" && found != actuals.end()) return found->second.first;
      if (kind == "object" && found != actuals.end()) {
        auto childOffset = value.getString("offset");
        if (!childOffset) return top("callee_return_offset_unknown");
        ControlDomain result;
        for (auto candidate : found->second.first.candidates) {
          if (candidate.value.getString("kind") == "parameter") {
            if (*childOffset == "0") { result.candidates.push_back(std::move(candidate)); continue; }
            candidate.value = json::Object{{"kind", "object"}, {"source", json::Object(*candidate.value.getObject("source"))},
              {"offset", childOffset->str()}, {"address_space", found->second.second}, {"allocation", nullptr}};
            result.candidates.push_back(std::move(candidate)); continue;
          }
          if (candidate.value.getString("kind") != "object" || !candidate.value.getString("offset"))
            return top("callee_return_object_unknown");
          int64_t left = 0, right = 0, sum = 0;
          if (candidate.value.getString("offset")->getAsInteger(10, left) || childOffset->getAsInteger(10, right) ||
              __builtin_add_overflow(left, right, &sum)) return top("callee_return_offset_overflow");
          candidate.value["offset"] = std::to_string(sum); result.candidates.push_back(std::move(candidate));
        }
        return found->second.first.unknown.empty() ? result : top(found->second.first.unknown);
      }
      if (kind == "expression") {
        auto *operands = value.getArray("operands");
        if (!operands) return top("callee_return_expression_invalid");
        for (auto &operand : *operands) {
          auto *object = operand.getAsObject();
          if (!object) return top("callee_return_expression_invalid");
          auto domain = self(self, json::Object(*object));
          if (!domain.unknown.empty() || domain.candidates.size() != 1) return top("callee_return_expression_unknown");
          operand = json::Object(domain.candidates[0].value);
        }
        value["source"] = ref(&call);
        value["invocation_id"] = invocation;
        auto *boundOperands = value.getArray("operands");
        if (boundOperands->size() == 2) {
          auto *base = (*boundOperands)[0].getAsObject();
          auto *delta = (*boundOperands)[1].getAsObject();
          if (base && delta && base->getString("kind") == "object" && delta->getString("kind") == "integer" &&
              base->getString("offset") && delta->getInteger("bits") && delta->getString("hex")) {
            APInt parsed;
            unsigned bits = unsigned(*delta->getInteger("bits"));
            int64_t oldOffset = 0;
            if (!delta->getString("hex")->getAsInteger(16, parsed) && parsed.getActiveBits() <= bits && bits <= 64 &&
                !base->getString("offset")->getAsInteger(10, oldOffset)) {
              int64_t sum = 0;
              if (!__builtin_add_overflow(oldOffset, parsed.zextOrTrunc(bits).sextOrTrunc(64).getSExtValue(), &sum)) {
                (*base)["offset"] = std::to_string(sum);
                return one(json::Object(*base));
              }
            }
          }
        }
      }
      return one(std::move(value));
    };
    ControlDomain result;
    bool normal = false;
    for (const auto &item : *summary.getArray("returns")) {
      const auto *returned = item.getAsObject();
      if (!returned || returned->getString("exit") != "normal" || !returned->getObject("value")) continue;
      normal = true;
      auto candidate = substitute(substitute, json::Object(*returned->getObject("value")));
      result = result.bottom() ? std::move(candidate) : joinControl(result, candidate, budget);
    }
    return normal ? result : top("callee_has_no_normal_return");
  }
  bool useBoundCall(CallBase &call, State &state) {
    auto found = boundCalls.find(ids.lookup(&call));
    if (found == boundCalls.end()) return false;
    const auto &summary = *found->second;
    bool invalidates = !summary.getArray("escape")->empty();
    for (const auto &item : *summary.getArray("effects")) {
      auto kind = item.getAsObject()->getString("kind");
      invalidates |= kind == "write" || kind == "rmw" || kind == "cas" || kind == "unknown";
    }
    if (invalidates) invalidateTouched(call, state);
    if (!call.getType()->isVoidTy()) {
      auto result = substituteReturn(summary, call, state);
      state.values[&call] = result; emitValue(&call, result);
      if (!result.unknown.empty()) pending(&call, result.unknown);
    }
    if (summary.getString("status") != "complete") pending(&call, "callee_summary_partial");
    return true;
  }
  void emitEffect(Instruction &instruction, StringRef kind, const Value *addressValue,
                  const ControlDomain *valueDomain, bool atomic, bool isVolatile,
                  StringRef successOrder, std::optional<StringRef> failureOrder, StringRef scope,
                  State &state) {
    if (effects.size() >= effectLimit) { stop(&instruction, "effect_items_budget"); return; }
    json::Value address = nullptr;
    std::string visibility = "unknown";
    if (addressValue) {
      auto domain = resolve(addressValue, state);
      if (domain.candidates.size() == 1) address = json::Object(domain.candidates[0].value);
      auto target = pointer(addressValue);
      visibility = target.kind == ObjectKind::Local ? "local" : target.kind == ObjectKind::Global ? "observable" : "unknown";
      if (!domain.unknown.empty()) pending(&instruction, domain.unknown);
    }
    json::Value value = nullptr;
    if (valueDomain) {
      if (valueDomain->candidates.size() == 1) value = json::Object(valueDomain->candidates[0].value);
      else if (!valueDomain->unknown.empty()) {
        value = json::Object{{"kind", "unknown"}, {"reason", valueDomain->unknown}};
        pending(&instruction, valueDomain->unknown);
      } else pending(&instruction, "non_single_effect_value");
    }
    Type *accessType = nullptr;
    if (auto *load = dyn_cast<LoadInst>(&instruction)) accessType = load->getType();
    if (auto *store = dyn_cast<StoreInst>(&instruction)) accessType = store->getValueOperand()->getType();
    if (auto *rmw = dyn_cast<AtomicRMWInst>(&instruction)) accessType = rmw->getValOperand()->getType();
    if (auto *cas = dyn_cast<AtomicCmpXchgInst>(&instruction)) accessType = cas->getCompareOperand()->getType();
    auto size = accessType && !module.getDataLayoutStr().empty() ? byteSize(accessType, module.getDataLayout()) : std::nullopt;
    const std::string id = ids.lookup(&instruction) + ":effect:" + std::to_string(effects.size());
    const bool repeated = repeatedCondition(*instruction.getParent());
    const char *multiplicity = invocationCardinality != Cardinality::Single ? "unknown" : repeated ? "repeated" : "single";
    bool hasNormalReturn = false, mustNormal = invocationCardinality == Cardinality::Single && !repeated;
    for (auto &block : function) if (auto *ret = dyn_cast<ReturnInst>(block.getTerminator())) {
      hasNormalReturn = true; mustNormal &= dominators.dominates(&instruction, ret);
    }
    mustNormal &= hasNormalReturn;
    json::Object effect{{"id", id}, {"source", ref(&instruction)}, {"context_id", context},
      {"invocation_id", invocation}, {"kind", kind.str()}, {"address", std::move(address)},
      {"size_bytes", size ? json::Value(std::to_string(size->getZExtValue())) : json::Value(nullptr)},
      {"value", std::move(value)}, {"atomic", atomic}, {"volatile", isVolatile},
      {"ordering", successOrder.empty() ? json::Value(nullptr) : json::Value(successOrder.str())},
      {"failure_ordering", failureOrder ? json::Value(failureOrder->str()) : json::Value(nullptr)},
      {"syncscope", scope.empty() ? json::Value(nullptr) : json::Value(scope.str())},
      {"visibility", visibility}, {"guards", json::Array(state.guards)},
      {"occurrence", mustNormal ? "must-normal-return" : "may"},
      {"multiplicity", multiplicity}, {"proof", json::Array{ref(&instruction)}}, {"call_path", json::Array{}}};
    if (!previousEffect.empty()) order.push_back(json::Object{{"before", previousEffect}, {"after", id},
      {"guards", json::Array(state.guards)}});
    previousEffect = id;
    effects.push_back(std::move(effect));
  }
  void unknownCall(CallBase &call, State &state) {
    std::vector<ControlDomain> domains;
    for (const auto &argument : call.args()) domains.push_back(resolve(argument, state));
    auto sourceRef = ref(&call);
    auto existing = llvm::find_if(calls, [&](const json::Value &value) {
      return equal(*value.getAsObject()->get("source"), json::Value(json::Object(sourceRef)));
    });
    if (existing == calls.end()) {
      json::Array arguments;
      for (const auto &domain : domains) arguments.push_back(toJson(domain));
      calls.push_back(json::Object{{"source", json::Object(sourceRef)}, {"arguments", std::move(arguments)},
        {"guards", json::Array(state.guards)}});
    } else {
      auto *record = existing->getAsObject();
      auto *arguments = record->getArray("arguments");
      for (size_t index = 0; index < domains.size(); ++index) {
        auto merged = joinControl(fromJson((*arguments)[index]), domains[index], budget);
        (*arguments)[index] = toJson(merged);
      }
      appendUnique(*record->getArray("guards"), state.guards);
    }
    pending(&call, "unknown_call_effect");
    invalidateTouched(call, state);
    emitEffect(call, "unknown", nullptr, nullptr, false, false, "", {}, "", state);
    if (!call.getType()->isVoidTy()) state.values[&call] = top("unknown_call_return");
  }
  void execute(Work &work) {
    auto &state = work.state;
    if (work.predecessor) {
      DenseMap<const Value *, ControlDomain> incoming;
      for (auto &instruction : *work.block) {
        auto *phi = dyn_cast<PHINode>(&instruction); if (!phi) break;
        auto domain = phiControl(*phi, *work.predecessor, work.edge, state.values, budget);
        if (domain.bottom()) domain = resolve(phi->getIncomingValueForBlock(work.predecessor), state);
        incoming[phi] = withPath(domain, state.guards);
      }
      for (auto &entry : incoming) state.values[entry.first] = entry.second;
    }
    for (auto &instruction : *work.block) {
      if (isa<PHINode>(instruction)) { emitValue(&instruction, resolve(&instruction, state)); continue; }
      if (isa<AllocaInst>(instruction)) { auto domain = resolve(&instruction, state); emitValue(&instruction, domain); continue; }
      if (auto *store = dyn_cast<StoreInst>(&instruction)) {
        auto value = resolve(store->getValueOperand(), state);
        auto target = pointer(store->getPointerOperand());
        auto size = module.getDataLayoutStr().empty() ? std::nullopt : byteSize(store->getValueOperand()->getType(), module.getDataLayout());
        if (!store->isAtomic() && !store->isVolatile()) {
          storePrivate(target, size, value, ref(store), state);
          if (!privatePointer(target) && store->getValueOperand()->getType()->isPointerTy()) {
            recordEscape(value, "externally_visible_store_escape");
            invalidateEscaped(value, state);
          }
        }
        emitEffect(*store, "write", store->getPointerOperand(), &value, store->isAtomic(), store->isVolatile(),
                   ordering(store->getOrdering()), {}, syncScope(module.getContext(), store->getSyncScopeID()), state);
        continue;
      }
      if (auto *load = dyn_cast<LoadInst>(&instruction)) {
        auto target = pointer(load->getPointerOperand());
        auto size = module.getDataLayoutStr().empty() ? std::nullopt : byteSize(load->getType(), module.getDataLayout());
        auto value = (!load->isAtomic() && !load->isVolatile()) ? loadPrivate(target, size, state, *load) : top("shared_or_atomic_load");
        state.values[load] = value; emitValue(load, value);
        emitEffect(*load, "read", load->getPointerOperand(), &value, load->isAtomic(), load->isVolatile(),
                   ordering(load->getOrdering()), {}, syncScope(module.getContext(), load->getSyncScopeID()), state);
        if (!value.unknown.empty()) pending(load, value.unknown);
        continue;
      }
      if (auto *rmw = dyn_cast<AtomicRMWInst>(&instruction)) {
        auto value = resolve(rmw->getValOperand(), state); state.values[rmw] = top("atomic_rmw_result");
        emitEffect(*rmw, "rmw", rmw->getPointerOperand(), &value, true, rmw->isVolatile(),
                   ordering(rmw->getOrdering()), {}, syncScope(module.getContext(), rmw->getSyncScopeID()), state);
        continue;
      }
      if (auto *cas = dyn_cast<AtomicCmpXchgInst>(&instruction)) {
        auto value = resolve(cas->getNewValOperand(), state); state.values[cas] = top("cmpxchg_result");
        emitEffect(*cas, "cas", cas->getPointerOperand(), &value, true, cas->isVolatile(),
                   ordering(cas->getSuccessOrdering()), ordering(cas->getFailureOrdering()),
                   syncScope(module.getContext(), cas->getSyncScopeID()), state);
        continue;
      }
      if (auto *fence = dyn_cast<FenceInst>(&instruction)) {
        emitEffect(*fence, "fence", nullptr, nullptr, true, false, ordering(fence->getOrdering()), {},
                   syncScope(module.getContext(), fence->getSyncScopeID()), state); continue;
      }
      if (auto *call = dyn_cast<CallBase>(&instruction)) {
        const bool bound = useBoundCall(*call, state);
        if (auto *intrinsic = dyn_cast<IntrinsicInst>(call)) {
          if (intrinsic->getIntrinsicID() == Intrinsic::lifetime_end ||
              intrinsic->getIntrinsicID() == Intrinsic::lifetime_start) {
            auto target = pointer(intrinsic->getArgOperand(1));
            if (intrinsic->getIntrinsicID() == Intrinsic::lifetime_end)
              state.slots.erase(std::remove_if(state.slots.begin(), state.slots.end(), [&](const Slot &slot) {
                return compareRanges(target, {}, slot.pointer, slot.size) != RangeRelation::Disjoint;
              }), state.slots.end());
            continue;
          }
          if (!bound) unknownCall(*call, state);
        } else if (!bound) unknownCall(*call, state);
        if (auto *invoke = dyn_cast<InvokeInst>(call)) {
          queue.push_back({invoke->getNormalDest(), work.block, 0, state});
          auto *target = invoke->getCalledFunction();
          if (!target || !target->hasFnAttribute(Attribute::NoUnwind)) {
            pending(invoke, "unwind_effect_unknown");
            queue.push_back({invoke->getUnwindDest(), work.block, 1, state});
          }
          return;
        }
        if (auto *target = call->getCalledFunction(); target && target->hasFnAttribute(Attribute::NoReturn)) {
          returns.push_back(json::Object{{"source", ref(call)}, {"invocation_id", invocation},
            {"value", nullptr}, {"guards", json::Array(state.guards)}, {"exit", "noreturn"}});
          return;
        }
        continue;
      }
      if (auto *select = dyn_cast<SelectInst>(&instruction)) {
        auto result = selectControl(*select, resolve(select->getCondition(), state),
          resolve(select->getTrueValue(), state), resolve(select->getFalseValue(), state), budget);
        state.values[select] = result; emitValue(select, result);
        if (!result.unknown.empty()) pending(select, result.unknown);
        continue;
      }
      if (auto *ret = dyn_cast<ReturnInst>(&instruction)) {
        auto value = ret->getReturnValue() ? resolve(ret->getReturnValue(), state) : ControlDomain{};
        if (ret->getReturnValue() && value.candidates.size() == 1 &&
            value.candidates[0].value.getString("kind") == "object" &&
            value.candidates[0].value.getObject("allocation")) {
          recordEscape(value, "expired_local_return");
          value = top("expired_local_return");
        }
        if (ret->getReturnValue() && !value.unknown.empty()) pending(ret, value.unknown);
        else if (ret->getReturnValue() && value.candidates.size() != 1) pending(ret, "unknown_return");
        json::Value serialized = nullptr;
        if (ret->getReturnValue() && value.candidates.size() == 1) serialized = json::Object(value.candidates[0].value);
        returns.push_back(json::Object{{"source", ref(ret)}, {"invocation_id", invocation},
          {"value", std::move(serialized)}, {"guards", json::Array(state.guards)}, {"exit", "normal"}});
        return;
      }
      if (isa<ResumeInst>(instruction) || isa<CleanupReturnInst>(instruction)) {
        returns.push_back(json::Object{{"source", ref(&instruction)}, {"invocation_id", invocation},
          {"value", nullptr}, {"guards", json::Array(state.guards)}, {"exit", "unwind"}});
        pending(&instruction, "unwind_effect_unknown"); return;
      }
      if (isa<UnreachableInst>(instruction)) {
        returns.push_back(json::Object{{"source", ref(&instruction)}, {"invocation_id", invocation},
          {"value", nullptr}, {"guards", json::Array(state.guards)}, {"exit", "noreturn"}});
        return;
      }
      if (instruction.isTerminator()) {
        ControlDomain condition;
        if (auto *branch = dyn_cast<BranchInst>(&instruction); branch && branch->isConditional())
          condition = resolve(branch->getCondition(), state);
        else if (auto *sw = dyn_cast<SwitchInst>(&instruction)) condition = resolve(sw->getCondition(), state);
        auto choices = chooseControl(instruction, condition, ref(&instruction), invocation, invocationCardinality, budget);
        if (!choices.pending.empty()) pending(&instruction, choices.pending);
        for (auto &choice : choices.edges) {
          State next = state;
          appendUnique(next.guards, json::Array{json::Object(choice.guard)});
          queue.push_back({instruction.getSuccessor(choice.ordinal), work.block, choice.ordinal, std::move(next)});
        }
        return;
      }
      if (!instruction.getType()->isVoidTy()) {
        auto result = instruction.getType()->isPointerTy() ? resolve(&instruction, state) : scalar(instruction, state);
        state.values[&instruction] = result; emitValue(&instruction, result);
        if (!result.unknown.empty()) pending(&instruction, result.unknown);
      }
    }
  }
  void publishBlocks() {
    json::Array proof{ref(&function.getEntryBlock())};
    for (auto &block : function) {
      const bool reached = reachable.contains(&block), pendingState = pendingBlocks.contains(&block);
      if (pendingState) pending(&block, "block_pending");
      blocks.push_back(json::Object{{"source", ref(&block)},
        {"state", pendingState ? "pending" : reached ? "reachable" : "unreachable"},
        {"proof", reached || pendingState ? json::Array{} : json::Array(proof)}});
    }
  }
};
} // namespace

json::Object interpretLocal(Module &module, Function &function, const json::Object &request,
                            const DenseMap<const Value *, std::string> &ids,
                            const json::Array *summaries) {
  return Interpreter(module, function, request, ids, summaries).run();
}
} // namespace moa
