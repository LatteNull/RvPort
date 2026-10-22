#pragma once
#include "facts.h"
#include "publication_protocol.h"

namespace moa {
inline llvm::json::Object publicationProtocol() {
  return *llvm::cantFail(llvm::json::parse(MOA_PUBLICATION_PROTOCOL_JSON)).getAsObject();
}
llvm::json::Object publicationFacts(llvm::Module &, const llvm::json::Object &origin,
                                    const llvm::json::Object &budgets);
llvm::json::Object publicationBatch(const llvm::json::Object &request);
int publicationWorker(const std::string &path, llvm::raw_ostream &, llvm::raw_ostream &);
} // namespace moa
