#pragma once

#include <llvm/IR/Module.h>
#include <llvm/Support/JSON.h>
#include <llvm/Support/raw_ostream.h>

namespace moa {
llvm::json::Object objectProvenanceProtocol();
llvm::json::Object localObjectProvenance(llvm::Module &module,
                                         const llvm::json::Object &request);
int objectProvenanceWorker(const char *path, llvm::raw_ostream &out,
                           llvm::raw_ostream &err);
}
