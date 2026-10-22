#pragma once
#include "facts.h"

namespace moa {
struct ExtractionBudget {
  size_t nodes;
  size_t references;
  unsigned depth;
  size_t output;
};
llvm::json::Object protocol();
ExtractionBudget defaultBudget();
void enrich(llvm::Module &, llvm::json::Object &, ExtractionBudget);
} // namespace moa
