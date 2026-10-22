#pragma once
#include "facts.h"
#include <llvm/ADT/APInt.h>
#include <llvm/ADT/DenseMap.h>
#include <llvm/IR/Operator.h>
#include <optional>
#include <vector>

namespace moa {
// In-memory domain: no new serialized kind and no mutation of P1 facts.
enum class ObjectKind { Unknown, Global, Parameter, Local };
enum class Cardinality { Single, Merged, Unknown };
struct PointerValue {
  ObjectKind kind = ObjectKind::Unknown;
  std::string artifact, source, expressionSource, function, scope, invocation, reason;
  Cardinality cardinality = Cardinality::Unknown;
  unsigned addressSpace = 0;
  std::optional<llvm::APInt> offset;
  bool known() const { return kind != ObjectKind::Unknown; }
};
// Supplied only after scope/definition eligibility validation. A missing entry
// never creates storage for an extern declaration. Key is the local IR symbol.
using GlobalBindings = llvm::DenseMap<const llvm::GlobalVariable *, PointerValue>;
PointerValue pointerValue(const llvm::Value *, llvm::Module &, llvm::StringRef artifact,
                          llvm::StringRef scope, llvm::StringRef invocation, Cardinality,
                          const GlobalBindings &, unsigned steps = 100000);
std::optional<llvm::APInt> constantByteOffset(const llvm::GEPOperator &, const llvm::DataLayout &);
enum class RangeRelation { Unknown, Overlap, Disjoint };
RangeRelation compareRanges(const PointerValue &, const std::optional<llvm::APInt> &leftSize,
                             const PointerValue &, const std::optional<llvm::APInt> &rightSize);
// Exact scalar LLVM evaluation. Arguments are already validated scalar Values;
// symbolic/non-integer values are not guessed. Select does not evaluate its
// untaken operand. No load/store/call can be folded by this API.
llvm::json::Object foldScalar(const llvm::Instruction &, llvm::ArrayRef<llvm::json::Object>);
llvm::json::Object symbolicScalar(const llvm::Instruction &, llvm::ArrayRef<llvm::json::Object>,
                                  const llvm::json::Object &source, llvm::StringRef invocation);
using ScalarSet = std::vector<llvm::json::Object>;
ScalarSet mergeScalars(llvm::ArrayRef<llvm::json::Object>, unsigned limit);
} // namespace moa
