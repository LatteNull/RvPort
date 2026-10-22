#pragma once
#include "effect_domain.h"
#include <llvm/IR/Instructions.h>

namespace moa {
// Internal lattice only. Empty candidates are bottom, never a published domain.
struct GuardedScalar {
  llvm::json::Object value;
  llvm::json::Array guards, proof;
};
struct ControlDomain {
  std::vector<GuardedScalar> candidates;
  std::string unknown;
  bool bottom() const { return unknown.empty() && candidates.empty(); }
};
struct ControlBudget {
  unsigned steps = 0, limit = 100000, candidates = 8;
  bool spend();
};
struct ControlEdge {
  unsigned ordinal;
  llvm::json::Object guard;
  ControlDomain condition;
};
struct ControlChoices {
  std::vector<ControlEdge> edges;
  // Nonempty means a pending frontier, not a proof that omitted edges cannot run.
  std::string pending;
};
bool repeatedCondition(const llvm::BasicBlock &);
ControlDomain joinControl(const ControlDomain &, const ControlDomain &, ControlBudget &);
ControlDomain selectControl(const llvm::SelectInst &, const ControlDomain &condition,
                            const ControlDomain &onTrue, const ControlDomain &onFalse, ControlBudget &);
ControlChoices chooseControl(const llvm::Instruction &, const ControlDomain &condition,
                             const llvm::json::Object &source, llvm::StringRef invocation,
                             Cardinality, ControlBudget &);
// Lookup is supplied by the worklist for this predecessor state, before PHIs
// are assigned simultaneously. No union of unrelated predecessor operands.
ControlDomain phiControl(const llvm::PHINode &, const llvm::BasicBlock &predecessor, unsigned ordinal,
                          const llvm::DenseMap<const llvm::Value *, ControlDomain> &, ControlBudget &);
} // namespace moa
