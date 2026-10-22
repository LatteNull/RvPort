#pragma once

#include <llvm/Support/JSON.h>
#include <llvm/Support/raw_ostream.h>

namespace moa {
llvm::json::Object sourceProtocol();
llvm::json::Object provenanceProtocol();
llvm::json::Object analyzeSource(const llvm::json::Object &request);
llvm::json::Object analyzeObjectPaths(const llvm::json::Object &request);
llvm::json::Object analyzeLLVMSourceBinding(const llvm::json::Object &request);
int sourceWorker(const char *path, llvm::raw_ostream &out, llvm::raw_ostream &err);
int objectPathWorker(const char *path, llvm::raw_ostream &out, llvm::raw_ostream &err);
int irBindingWorker(const char *path, llvm::raw_ostream &out, llvm::raw_ostream &err);
}
