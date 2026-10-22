#pragma once
#include "facts.h"
#include "analysis_protocol.h"

namespace moa {
inline llvm::json::Object analysisProtocol() {
  return *llvm::cantFail(llvm::json::parse(MOA_ANALYSIS_PROTOCOL_JSON)).getAsObject();
}
llvm::json::Object localMetadata(llvm::Module &, const llvm::json::Object &origin,
                                 const llvm::json::Object &budgets);
llvm::json::Object localBatch(const llvm::json::Object &request);
std::string analysisDigest(const llvm::json::Value &value);
llvm::json::Object evaluationPlan(llvm::Module &, const llvm::json::Object &request,
                                  const llvm::json::Array *summaries = nullptr);
llvm::json::Object evaluationBatch(const llvm::json::Object &request);
void localQueries(llvm::Module &, llvm::StringRef artifact, const llvm::json::Object &budgets,
                  llvm::json::Object &output);
int analysisWorker(const std::string &path, llvm::raw_ostream &, llvm::raw_ostream &, bool evaluate = false);
} // namespace moa
