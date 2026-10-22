#include "effect_control.h"
#include <llvm/ADT/SCCIterator.h>
#include <llvm/IR/Constants.h>

using namespace llvm;
namespace moa {
namespace {
ControlDomain top(StringRef reason) { return {{}, reason.str()}; }
bool equal(const json::Value &a, const json::Value &b) { return a == b; }
void appendUnique(json::Array &to, const json::Array &from) {
  for (auto &item : from)
    if (!llvm::any_of(to, [&](const auto &old) { return equal(old, item); })) to.push_back(item);
}
// Inputs have already passed the binding validator. Only singleton observations
// of the same terminator in the same activation can contradict one another.
bool combine(GuardedScalar &to, const GuardedScalar &from) {
  for (auto &left : to.guards) for (auto &right : from.guards) {
    const auto &a = *left.getAsObject(), &b = *right.getAsObject();
    if (a.getString("multiplicity") == "single" && b.getString("multiplicity") == "single" &&
        a.getString("invocation_id") == b.getString("invocation_id") && equal(*a.get("source"), *b.get("source")) &&
        a.getInteger("edge") != b.getInteger("edge")) return false;
  }
  appendUnique(to.guards, from.guards); appendUnique(to.proof, from.proof);
  return true;
}
void add(ControlDomain &to, GuardedScalar value, ControlBudget &budget) {
  if (!to.unknown.empty()) return;
  for (const auto &old : to.candidates)
    if (equal(json::Object(old.value), json::Object(value.value)) &&
        equal(json::Array(old.guards), json::Array(value.guards)) && equal(json::Array(old.proof), json::Array(value.proof))) return;
  to.candidates.push_back(std::move(value));
  if (to.candidates.size() > budget.candidates) to = top("value_candidate_budget");
}
std::optional<APInt> integer(const json::Object &value, Type *type) {
  auto bits = value.getInteger("bits"); auto hex = value.getString("hex");
  if (!type->isIntegerTy() || value.getString("kind") != "integer" || !bits || *bits != type->getIntegerBitWidth() ||
      !hex || hex->empty() || hex->find_first_not_of("0123456789ABCDEF") != StringRef::npos) return {};
  APInt parsed;
  if (hex->getAsInteger(16, parsed) || parsed.getActiveBits() > unsigned(*bits)) return {};
  return parsed.zextOrTrunc(unsigned(*bits));
}
} // namespace

bool ControlBudget::spend() { if (steps == limit) return false; ++steps; return true; }

bool repeatedCondition(const BasicBlock &block) {
  // Reachability is irrelevant here: even an unreachable cyclic block cannot
  // manufacture single-observation evidence if later considered as a root.
  const auto *function = block.getParent();
  for (auto component = scc_begin(function); !component.isAtEnd(); ++component)
    if (llvm::is_contained(*component, &block)) return component.hasCycle();
  return true; // Not reached from function entry: no singleton proof.
}

ControlDomain joinControl(const ControlDomain &a, const ControlDomain &b, ControlBudget &budget) {
  if (!a.unknown.empty()) return top(a.unknown);
  if (!b.unknown.empty()) return top(b.unknown);
  ControlDomain result;
  for (const auto *input : {&a, &b}) for (const auto &candidate : input->candidates) {
    if (!budget.spend()) return top("local_steps_budget");
    add(result, candidate, budget);
  }
  return result;
}

ControlDomain selectControl(const SelectInst &instruction, const ControlDomain &condition,
                            const ControlDomain &onTrue, const ControlDomain &onFalse, ControlBudget &budget) {
  if (!condition.unknown.empty()) return top("unknown_select_condition");
  ControlDomain result;
  for (const auto &choice : condition.candidates) {
    if (!budget.spend()) return top("local_steps_budget");
    const auto selected = integer(choice.value, instruction.getCondition()->getType());
    if (!selected) {
      if (choice.value.getString("kind") != "poison") return top("unknown_select_condition");
      add(result, choice, budget); // LLVM select propagates a poison condition.
      continue;
    }
    const auto &arm = selected->isZero() ? onFalse : onTrue;
    if (!arm.unknown.empty()) return top(arm.unknown);
    for (const auto &value : arm.candidates) {
      if (!budget.spend()) return top("local_steps_budget");
      auto candidate = value;
      if (combine(candidate, choice)) add(result, std::move(candidate), budget);
    }
  }
  return result;
}

ControlChoices chooseControl(const Instruction &instruction, const ControlDomain &condition,
                             const json::Object &source, StringRef invocation, Cardinality cardinality, ControlBudget &budget) {
  auto *branch = dyn_cast<BranchInst>(&instruction);
  auto *sw = dyn_cast<SwitchInst>(&instruction);
  if (!branch && !sw) return {{}, "unsupported_control"};
  bool unconditional = branch && branch->isUnconditional();
  if (!unconditional && condition.bottom()) return {{}, "condition_pending"};
  const Value *value = unconditional ? nullptr : branch ? branch->getCondition() : sw->getCondition();
  ControlChoices result;
  auto multiplicity = cardinality != Cardinality::Single ? "unknown" : repeatedCondition(*instruction.getParent()) ? "repeated" : "single";
  for (unsigned edge = 0; edge < instruction.getNumSuccessors(); ++edge) {
    if (!budget.spend()) return {std::move(result.edges), "local_steps_budget"};
    ControlDomain filtered;
    if (unconditional) filtered = condition;
    else if (!condition.unknown.empty()) filtered = top(condition.unknown);
    else for (const auto &candidate : condition.candidates) {
      if (!budget.spend()) return {std::move(result.edges), "local_steps_budget"};
      auto scalar = integer(candidate.value, value->getType());
      if (!scalar) { filtered = top("indeterminate_control"); break; }
      unsigned selected;
      if (branch) selected = scalar->isZero() ? 1 : 0;
      else {
        auto *constant = ConstantInt::get(cast<IntegerType>(value->getType()), *scalar);
        selected = sw->findCaseValue(cast<ConstantInt>(constant))->getSuccessorIndex();
      }
      if (selected == edge) add(filtered, candidate, budget);
    }
    if (unconditional || !filtered.unknown.empty() || !filtered.candidates.empty()) {
      json::Object guard{{"source", json::Object(source)}, {"edge", edge}, {"invocation_id", invocation.str()}, {"multiplicity", multiplicity}};
      result.edges.push_back({edge, std::move(guard), std::move(filtered)});
    }
  }
  return result;
}

ControlDomain phiControl(const PHINode &phi, const BasicBlock &predecessor, unsigned ordinal,
                          const DenseMap<const Value *, ControlDomain> &values, ControlBudget &budget) {
  if (!budget.spend()) return top("local_steps_budget");
  auto *term = predecessor.getTerminator();
  if (predecessor.getParent() != phi.getFunction() || ordinal >= term->getNumSuccessors() ||
      term->getSuccessor(ordinal) != phi.getParent()) return top("invalid_phi_edge");
  auto index = phi.getBasicBlockIndex(&predecessor);
  if (index < 0) return top("invalid_phi_predecessor");
  auto found = values.find(phi.getIncomingValue(index));
  return found == values.end() ? ControlDomain{} : found->second;
}
} // namespace moa
