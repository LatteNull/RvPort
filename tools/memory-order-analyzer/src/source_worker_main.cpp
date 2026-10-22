#include "source_facts.h"
#include <string>

int main(int argc, const char *argv[]) {
  if (argc == 2 && std::string(argv[1]) == "--source-analysis-protocol") {
    llvm::outs() << llvm::json::Value(moa::sourceProtocol()) << "\n";
    return 0;
  }
  if (argc == 2 && std::string(argv[1]) == "--object-provenance-protocol") {
    llvm::outs() << llvm::json::Value(moa::provenanceProtocol()) << "\n";
    return 0;
  }
  if (argc == 3 && std::string(argv[1]) == "--source-request")
    return moa::sourceWorker(argv[2], llvm::outs(), llvm::errs());
  if (argc == 3 && std::string(argv[1]) == "--object-path-request")
    return moa::objectPathWorker(argv[2], llvm::outs(), llvm::errs());
  if (argc == 3 && std::string(argv[1]) == "--ir-binding-request")
    return moa::irBindingWorker(argv[2], llvm::outs(), llvm::errs());
  llvm::errs() << "usage: memory-order-source-worker --source-analysis-protocol | --object-provenance-protocol | --source-request REQUEST.json | --object-path-request REQUEST.json | --ir-binding-request REQUEST.json\n";
  return 1;
}
