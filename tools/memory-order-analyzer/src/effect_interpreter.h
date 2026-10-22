#pragma once
#include "effects.h"

namespace moa {
// Execute one bounded, read-only local evaluation.  The returned object contains
// the dynamic LocalEvaluationResult fields; the transport layer adds the request
// identity and protocol envelope.
llvm::json::Object interpretLocal(llvm::Module &, llvm::Function &,
                                  const llvm::json::Object &request,
                                  const llvm::DenseMap<const llvm::Value *, std::string> &ids,
                                  const llvm::json::Array *summaries = nullptr);
} // namespace moa
