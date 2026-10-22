#pragma once
#include <llvm/IR/Module.h>
#include <llvm/Support/JSON.h>
#include <llvm/Support/raw_ostream.h>
#include <string>

namespace moa {
std::string symbolId(const llvm::GlobalValue &value, const std::string &artifact);
llvm::json::Object extract(llvm::Module &module, const std::string &artifact,
                           const std::string &hash);
llvm::json::Object read(const std::string &path, const std::string &artifact);
int worker(int argc, const char *const *argv, llvm::raw_ostream &out,
           llvm::raw_ostream &err);
} // namespace moa
