#include "facts.h"
#include "semantic.h"
#include "effects.h"
#include "threads.h"
#include "publication.h"
#include "provenance.h"
#include "demand_analysis.h"
#include <llvm/Config/llvm-config.h>
#include <exception>

namespace moa {
int worker(int argc, const char *const *argv, llvm::raw_ostream &out, llvm::raw_ostream &err) {
  if (argc == 2 && std::string(argv[1]) == "--analysis-protocol") {
    out << llvm::json::Value(analysisProtocol()) << "\n";
    return 0;
  }
  if (argc == 3 && std::string(argv[1]) == "--local-batch")
    return analysisWorker(argv[2], out, err);
  if (argc == 3 && std::string(argv[1]) == "--evaluate-batch")
    return analysisWorker(argv[2], out, err, true);
  if (argc == 2 && std::string(argv[1]) == "--thread-analysis-protocol") {
    out << llvm::json::Value(threadProtocol()) << "\n";
    return 0;
  }
  if (argc == 3 && std::string(argv[1]) == "--thread-batch")
    return threadWorker(argv[2], out, err);
  if (argc == 2 && std::string(argv[1]) == "--publication-analysis-protocol") {
    out << llvm::json::Value(publicationProtocol()) << "\n";
    return 0;
  }
  if (argc == 3 && std::string(argv[1]) == "--publication-batch")
    return publicationWorker(argv[2], out, err);
  if (argc == 2 && std::string(argv[1]) == "--object-provenance-protocol") {
    out << llvm::json::Value(objectProvenanceProtocol()) << "\n";
    return 0;
  }
  if (argc == 3 && std::string(argv[1]) == "--object-provenance-request")
    return objectProvenanceWorker(argv[2], out, err);
  if (argc == 2 && std::string(argv[1]) == "--demand-analysis-protocol") {
    out << llvm::json::Value(demandProtocol()) << "\n";
    return 0;
  }
  if (argc == 3 && std::string(argv[1]) == "--demand-batch")
    return demandWorker(argv[2], out, err);
  if (argc == 2 && std::string(argv[1]) == "--advanced-atomic-protocol") {
    out << llvm::json::Value(advancedAtomicProtocol()) << "\n";
    return 0;
  }
  if (argc == 3 && std::string(argv[1]) == "--advanced-atomic-batch")
    return advancedAtomicDemandWorker(argv[2], out, err);
  if (argc == 2 && std::string(argv[1]) == "--protocol") {
    out << llvm::json::Value(protocol()) << "\n";
    return 0;
  }
  if (argc == 2 && std::string(argv[1]) == "--version") {
    out << "moa-worker LLVM " << LLVM_VERSION_STRING << "\n";
    return 0;
  }
  if (argc != 3 || std::string(argv[2]).size() != 64 ||
      std::string(argv[2]).find_first_not_of("0123456789abcdef") != std::string::npos) {
    err << "usage: moa-worker INPUT.bc ARTIFACT_SHA256\n";
    return 1;
  }
  try {
    out << llvm::json::Value(read(argv[1], argv[2])) << "\n";
    return 0;
  } catch (const std::exception &error) {
    err << error.what() << "\n";
    return 1;
  }
}
} // namespace moa
