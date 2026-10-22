#include "effect_domain.h"
#include <llvm/Analysis/ConstantFolding.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/Instructions.h>
#include <llvm/ADT/StringExtras.h>

using namespace llvm;
namespace moa {
namespace {
json::Object unknown(StringRef reason) { return json::Object{{"kind", "unknown"}, {"reason", reason.str()}}; }
bool flagsViolated(const Instruction &instruction, ArrayRef<Constant *> operands) {
  auto *first = dyn_cast<ConstantInt>(operands[0]);
  if (!first) return false;
  const auto &a = first->getValue();
  if (auto *trunc = dyn_cast<TruncInst>(&instruction)) {
    unsigned bits = instruction.getType()->getIntegerBitWidth();
    return (trunc->hasNoUnsignedWrap() && !a.isIntN(bits)) || (trunc->hasNoSignedWrap() && !a.isSignedIntN(bits));
  }
  if (isa<ZExtInst>(instruction)) return instruction.hasNonNeg() && a.isNegative();
  if (operands.size() != 2) return false;
  auto *second = dyn_cast<ConstantInt>(operands[1]);
  if (!second) return false;
  const auto &b = second->getValue();
  if (auto *cmp = dyn_cast<ICmpInst>(&instruction)) return cmp->hasSameSign() && a.isNegative() != b.isNegative();
  if (auto *disjoint = dyn_cast<PossiblyDisjointInst>(&instruction)) return disjoint->isDisjoint() && !(a & b).isZero();
  if (auto *overflowing = dyn_cast<OverflowingBinaryOperator>(&instruction)) {
    bool signedOverflow = false, unsignedOverflow = false;
    switch (instruction.getOpcode()) {
    case Instruction::Add: (void)a.sadd_ov(b, signedOverflow); (void)a.uadd_ov(b, unsignedOverflow); break;
    case Instruction::Sub: (void)a.ssub_ov(b, signedOverflow); (void)a.usub_ov(b, unsignedOverflow); break;
    case Instruction::Mul: (void)a.smul_ov(b, signedOverflow); (void)a.umul_ov(b, unsignedOverflow); break;
    case Instruction::Shl:
      if (b.uge(a.getBitWidth())) return true;
      (void)a.sshl_ov(b, signedOverflow); (void)a.ushl_ov(b, unsignedOverflow); break;
    }
    return (overflowing->hasNoSignedWrap() && signedOverflow) || (overflowing->hasNoUnsignedWrap() && unsignedOverflow);
  }
  if (auto *exact = dyn_cast<PossiblyExactOperator>(&instruction); exact && exact->isExact()) {
    switch (instruction.getOpcode()) {
    case Instruction::SDiv:
      return b.isZero() || (a.isMinSignedValue() && b.isAllOnes()) || !a.srem(b).isZero();
    case Instruction::UDiv: return b.isZero() || !a.urem(b).isZero();
    default: return b.uge(a.getBitWidth()) || a.countTrailingZeros() < b.getLimitedValue();
    }
  }
  return false;
}
json::Object encode(Constant *value) {
  if (auto *integer = dyn_cast_or_null<ConstantInt>(value)) {
    SmallString<32> hex;
    integer->getValue().toStringUnsigned(hex, 16);
    return json::Object{{"kind", "integer"}, {"bits", integer->getBitWidth()}, {"hex", hex.str().str()}};
  }
  if (isa_and_nonnull<PoisonValue>(value)) return json::Object{{"kind", "poison"}, {"reason", "llvm_poison"}};
  return unknown("not_deterministically_foldable");
}
} // namespace

json::Object foldScalar(const Instruction &instruction, ArrayRef<json::Object> values) {
  unsigned opcode = instruction.getOpcode();
  bool supported = isa<BinaryOperator>(instruction) || isa<ICmpInst>(instruction) ||
    opcode == Instruction::Trunc || opcode == Instruction::ZExt || opcode == Instruction::SExt ||
    opcode == Instruction::Select || opcode == Instruction::Freeze;
  if (!supported || !instruction.getType()->isIntegerTy()) return unknown("unsupported_scalar_operation");
  if (values.size() != instruction.getNumOperands()) return unknown("operand_count_mismatch");
  SmallVector<Constant *, 4> operands;
  for (unsigned i = 0; i < values.size(); ++i) {
    auto *type = dyn_cast<IntegerType>(instruction.getOperand(i)->getType());
    auto bits = values[i].getInteger("bits");
    auto hex = values[i].getString("hex");
    auto kind = values[i].getString("kind");
    if (kind == "poison") { operands.push_back(PoisonValue::get(instruction.getOperand(i)->getType())); continue; }
    // An arbitrary undef/freeze choice must never become a branch proof. Known
    // select can still ignore an undef/unknown unchosen arm below.
    if (kind != "integer") { operands.push_back(nullptr); continue; }
    if (!type || !bits || *bits != type->getBitWidth() || !hex || hex->empty() ||
        hex->find_first_not_of("0123456789ABCDEF") != StringRef::npos)
      return unknown("operand_type_mismatch");
    APInt parsed;
    if (hex->getAsInteger(16, parsed) || parsed.getActiveBits() > unsigned(*bits)) return unknown("integer_out_of_range");
    operands.push_back(ConstantInt::get(type, parsed.zextOrTrunc(unsigned(*bits))));
  }
  if (opcode == Instruction::Select) {
    if (isa_and_nonnull<PoisonValue>(operands[0])) return encode(operands[0]);
    if (auto *condition = dyn_cast_or_null<ConstantInt>(operands[0])) {
      unsigned chosen = condition->isZero() ? 2 : 1;
      return operands[chosen] ? encode(operands[chosen]) : json::Object(values[chosen]);
    }
    return unknown("unknown_select_condition");
  }
  if (opcode == Instruction::Freeze) {
    if (isa_and_nonnull<ConstantInt>(operands[0])) return encode(operands[0]);
    return json::Object{{"kind", "freeze"}, {"reason", "nondeterministic_freeze"}};
  }
  if (llvm::is_contained(operands, nullptr)) return unknown("unknown_scalar_operand");
  if (flagsViolated(instruction, operands)) return json::Object{{"kind", "poison"}, {"reason", "llvm_flags_violated"}};
  auto &layout = instruction.getModule()->getDataLayout();
  return encode(ConstantFoldInstOperands(&instruction, operands, layout, nullptr, false));
}

json::Object symbolicScalar(const Instruction &instruction, ArrayRef<json::Object> values,
                            const json::Object &source, StringRef invocation) {
  auto result = foldScalar(instruction, values);
  auto reason = result.getString("reason");
  if (reason != "unknown_scalar_operand" && reason != "unknown_select_condition") return result;
  // Source and activation are validated at the product boundary. A symbolic
  // relation retains the original opcode/flags through its IR SourceRef; it is
  // not a known constant, non-poison guarantee, or a feasible-path proof.
  if (invocation.empty()) return unknown("unbound_scalar_expression");
  json::Array operands;
  for (const auto &value : values) {
    auto kind = value.getString("kind");
    if (kind != "integer" && kind != "parameter" && kind != "expression") return result;
    operands.push_back(json::Object(value));
  }
  return json::Object{{"kind", "expression"}, {"source", json::Object(source)},
    {"invocation_id", invocation.str()}, {"operands", std::move(operands)}};
}

ScalarSet mergeScalars(ArrayRef<json::Object> values, unsigned limit) {
  ScalarSet result;
  for (const auto &value : values) {
    if (value.getString("kind") == "unknown") return {json::Object(value)};
    bool duplicate = llvm::any_of(result, [&](const auto &old) { return json::Value(json::Object(old)) == json::Value(json::Object(value)); });
    if (!duplicate) result.push_back(json::Object(value));
    if (result.size() > limit) return {unknown("value_candidate_budget")};
  }
  // Bottom (no predecessor yet) is internal only; callers must not publish an
  // empty unprocessed candidate set as a complete result.
  return result;
}
} // namespace moa
