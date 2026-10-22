#pragma once
#include "facts.h"
#include "thread_protocol.h"

namespace moa {
inline llvm::json::Object threadProtocol() {
  return *llvm::cantFail(llvm::json::parse(MOA_THREAD_PROTOCOL_JSON)).getAsObject();
}
llvm::json::Object threadFacts(llvm::Module &, const llvm::json::Object &origin,
                               const llvm::json::Object &budgets);
llvm::json::Object threadBatch(const llvm::json::Object &request);
int threadWorker(const std::string &path, llvm::raw_ostream &, llvm::raw_ostream &);
} // namespace moa
