#pragma once
#include "facts.h"
#include <llvm/ADT/DenseMap.h>

namespace moa {
inline void registerFunctionIdentities(
    llvm::Function &function, const std::string &artifact,
    llvm::DenseMap<const llvm::Value *, std::string> &ids) {
  if (!ids.count(&function)) ids[&function] = symbolId(function, artifact);
  for (auto &arg : function.args())
    ids[&arg] = ids[&function] + ":arg:" + std::to_string(arg.getArgNo());
  unsigned bn = 0;
  for (auto &block : function) {
    ids[&block] = ids[&function] + ":b" + std::to_string(bn++);
    unsigned in = 0;
    for (auto &inst : block)
      ids[&inst] = ids[&block] + ":i" + std::to_string(in++);
  }
}

inline llvm::DenseMap<const llvm::Value *, std::string>
functionIdentities(llvm::Function &function, const std::string &artifact) {
  llvm::DenseMap<const llvm::Value *, std::string> ids;
  if (auto *module = function.getParent())
    for (auto &global : module->global_values())
      ids[&global] = symbolId(global, artifact);
  registerFunctionIdentities(function, artifact, ids);
  return ids;
}

// Register identities on the original, untransformed module. P1 still exports
// only its root closure; registering an ID does not add a raw fact node.
inline llvm::DenseMap<const llvm::Value *, std::string>
originalIdentities(llvm::Module &module, const std::string &artifact) {
  llvm::DenseMap<const llvm::Value *, std::string> ids;
  for (auto &global : module.global_values()) ids[&global] = symbolId(global, artifact);
  for (auto &function : module) registerFunctionIdentities(function, artifact, ids);
  return ids;
}
} // namespace moa
