#include "effect_domain.h"
#include "ir_identity.h"
#include <llvm/ADT/SCCIterator.h>
#include <llvm/IR/GetElementPtrTypeIterator.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/CFG.h>
#include <algorithm>

using namespace llvm;
namespace moa {
std::optional<APInt> constantByteOffset(const GEPOperator &gep, const DataLayout &layout) {
  const unsigned bits = layout.getIndexSizeInBits(gep.getPointerAddressSpace());
  // Extra room detects multiplication/addition overflow instead of silently
  // treating a wrapped offset as a valid mathematical object byte interval.
  const unsigned wide = bits + 65;
  APInt total(wide, 0);
  for (auto it = gep_type_begin(gep), end = gep_type_end(gep); it != end; ++it) {
    auto *index = dyn_cast<ConstantInt>(it.getOperand());
    if (!index) return std::nullopt;
    if (auto *structure = it.getStructTypeOrNull()) {
      if (!structure->isSized()) return std::nullopt;
      total += APInt(wide, layout.getStructLayout(structure)->getElementOffset(index->getZExtValue()));
    } else {
      Type *type = it.getIndexedType();
      if (!type->isSized()) return std::nullopt;
      auto size = layout.getTypeAllocSize(type);
      if (size.isScalable()) return std::nullopt;
      // LLVM first sign-extends/truncates a sequential index to index width.
      total += index->getValue().sextOrTrunc(bits).sext(wide) * APInt(wide, size.getFixedValue());
    }
    if (!total.isSignedIntN(bits)) return std::nullopt;
  }
  return total.trunc(bits);
}

PointerValue pointerValue(const Value *value, Module &module, StringRef artifact, StringRef scope,
                          StringRef invocation, Cardinality cardinality, const GlobalBindings &bindings, unsigned steps) {
  PointerValue result;
  result.artifact = artifact.str(); result.scope = scope.str();
  auto fail = [&](StringRef reason) { result.kind = ObjectKind::Unknown; result.reason = reason.str(); result.offset.reset(); return result; };
  if (!value->getType()->isPointerTy()) return fail("not_pointer");
  result.addressSpace = value->getType()->getPointerAddressSpace();
  if (module.getDataLayoutStr().empty()) return fail("missing_data_layout");
  const unsigned bits = module.getDataLayout().getIndexSizeInBits(result.addressSpace);
  result.offset = APInt(bits, 0);
  auto ids = originalIdentities(module, artifact.str());
  result.expressionSource = ids.lookup(value);
  while (steps--) {
    if (auto *gep = dyn_cast<GEPOperator>(value)) {
      auto offset = constantByteOffset(*gep, module.getDataLayout());
      if (result.offset && offset) {
        bool overflow = false;
        auto sum = result.offset->sadd_ov(*offset, overflow);
        result.offset = overflow ? std::nullopt : std::optional<APInt>(sum);
      } else result.offset.reset();
      value = gep->getPointerOperand();
      continue;
    }
    if (auto *cast = dyn_cast<BitCastOperator>(value)) { value = cast->getOperand(0); continue; }
    result.source = ids.lookup(value);
    if (result.source.empty()) return fail("unsupported_pointer_origin");
    if (auto *arg = dyn_cast<Argument>(value)) {
      if (invocation.empty()) return fail("unbound_invocation");
      result.kind = ObjectKind::Parameter; result.function = ids.lookup(arg->getParent());
      result.invocation = invocation.str(); result.cardinality = cardinality;
      return result;
    }
    if (auto *allocation = dyn_cast<AllocaInst>(value)) {
      if (invocation.empty()) return fail("unbound_invocation");
      result.kind = ObjectKind::Local; result.function = ids.lookup(allocation->getFunction());
      result.invocation = invocation.str(); result.cardinality = cardinality;
      if (cardinality != Cardinality::Single) result.reason = "non_single_invocation";
      // SCCs include irreducible cycles that LoopInfo alone may not describe.
      for (auto it = scc_begin(allocation->getFunction()); !it.isAtEnd(); ++it)
        if (it.hasCycle() && llvm::is_contained(*it, allocation->getParent())) {
          if (cardinality == Cardinality::Single) result.cardinality = Cardinality::Merged;
          result.reason = "repeated_allocation";
        }
      return result;
    }
    if (auto *global = dyn_cast<GlobalVariable>(value)) {
      if (global->isThreadLocal() || global->hasAtLeastLocalUnnamedAddr()) return fail("unsupported_global_identity");
      if (!global->isDeclaration() &&
          (global->hasLocalLinkage() || (global->isDSOLocal() && !global->isInterposable()))) {
        result.kind = ObjectKind::Global; result.cardinality = Cardinality::Single;
        return result;
      }
      auto found = bindings.find(global);
      if (found == bindings.end()) return fail("unresolved_global_definition");
      const auto &bound = found->second;
      if (bound.kind != ObjectKind::Global || bound.scope != scope || bound.addressSpace != result.addressSpace ||
          bound.source.empty() || bound.artifact.empty() || bound.cardinality != Cardinality::Single)
        return fail("invalid_global_binding");
      result.kind = ObjectKind::Global; result.artifact = bound.artifact; result.source = bound.source;
      result.cardinality = Cardinality::Single;
      return result;
    }
    return fail("unsupported_pointer_conversion_or_origin");
  }
  return fail("pointer_step_budget");
}

RangeRelation compareRanges(const PointerValue &left, const std::optional<APInt> &leftSize,
                            const PointerValue &right, const std::optional<APInt> &rightSize) {
  // Zero bytes is an empty access even when the pointer cannot be resolved.
  if ((leftSize && leftSize->isZero()) || (rightSize && rightSize->isZero())) return RangeRelation::Disjoint;
  if (!left.known() || !right.known() || left.scope.empty() || left.scope != right.scope ||
      left.addressSpace != right.addressSpace) return RangeRelation::Unknown;
  if (left.cardinality != Cardinality::Single || right.cardinality != Cardinality::Single)
    return RangeRelation::Unknown;
  if (left.kind == ObjectKind::Parameter || right.kind == ObjectKind::Parameter) return RangeRelation::Unknown;
  const bool same = left.kind == right.kind && left.artifact == right.artifact && left.source == right.source &&
                    left.invocation == right.invocation;
  if (!same) return RangeRelation::Disjoint;
  if (!leftSize || !rightSize) return RangeRelation::Unknown;
  if (!left.offset || !right.offset) return RangeRelation::Unknown;
  unsigned width = std::max({left.offset->getBitWidth(), right.offset->getBitWidth(), leftSize->getBitWidth(), rightSize->getBitWidth()}) + 2;
  auto a = left.offset->sext(width), b = right.offset->sext(width);
  auto ae = a + leftSize->zext(width), be = b + rightSize->zext(width);
  return a.slt(be) && b.slt(ae) ? RangeRelation::Overlap : RangeRelation::Disjoint;
}
} // namespace moa
