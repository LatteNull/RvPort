#pragma once

#include "facts.h"
#include "demand_protocol.h"
#include "advanced_atomic_protocol.h"

namespace moa {
inline llvm::json::Object demandProtocol() {
  return *llvm::cantFail(llvm::json::parse(MOA_DEMAND_PROTOCOL_JSON)).getAsObject();
}
inline llvm::json::Object advancedAtomicProtocol() {
  return *llvm::cantFail(llvm::json::parse(MOA_ADVANCED_ATOMIC_PROTOCOL_JSON)).getAsObject();
}
llvm::json::Object demandBatch(const llvm::json::Object &request);
llvm::json::Object advancedAtomicDemandBatch(const llvm::json::Object &request);
int demandWorker(const std::string &path, llvm::raw_ostream &, llvm::raw_ostream &);
int advancedAtomicDemandWorker(const std::string &path, llvm::raw_ostream &, llvm::raw_ostream &);
} // namespace moa
