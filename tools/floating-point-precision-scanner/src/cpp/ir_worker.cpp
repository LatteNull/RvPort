#include "ir_facts.hpp"

#include <cstdlib>
#include <limits>
#include <string>
#include <string_view>
#include <unordered_map>

#include "llvm/Support/Error.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/raw_ostream.h"

namespace {

void printJson(llvm::json::Object value) {
  llvm::outs() << llvm::formatv("{0}", llvm::json::Value(std::move(value))) << '\n';
}

int fail(llvm::StringRef message) {
  llvm::errs() << message << '\n';
  return 2;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc == 2 && std::string_view(argv[1]) == "--version-json") {
    printJson(fp_scanner::versionJson());
    return 0;
  }
  if (argc < 3 || argc % 2 == 0) return fail("invalid_arguments");
  std::unordered_map<std::string, std::string> arguments;
  for (int index = 1; index + 1 < argc; index += 2) {
    arguments.emplace(argv[index], argv[index + 1]);
  }
  constexpr const char *required[] = {
      "--input",          "--artifact-set-id", "--artifact-key",
      "--physical-tu-id", "--context-id",      "--profile",
      "--sha256",         "--max-facts",       "--max-use-edges",
      "--max-summary-depth", "--max-summary-call-edges",
      "--protocol-version",
  };
  for (const char *key : required) {
    if (!arguments.contains(key)) return fail("missing_argument");
  }
  if (arguments["--protocol-version"] != fp_scanner::kWorkerProtocolVersion) {
    return fail("unsupported_protocol_version");
  }
  std::size_t max_facts = 0;
  std::size_t max_use_edges = 0;
  std::size_t max_summary_depth = 0;
  std::size_t max_summary_call_edges = 0;
  try {
    const unsigned long long parsed = std::stoull(arguments["--max-facts"]);
    max_facts = static_cast<std::size_t>(parsed);
    const unsigned long long parsed_uses = std::stoull(arguments["--max-use-edges"]);
    max_use_edges = static_cast<std::size_t>(parsed_uses);
    const unsigned long long parsed_depth =
        std::stoull(arguments["--max-summary-depth"]);
    max_summary_depth = static_cast<std::size_t>(parsed_depth);
    const unsigned long long parsed_calls =
        std::stoull(arguments["--max-summary-call-edges"]);
    max_summary_call_edges = static_cast<std::size_t>(parsed_calls);
  } catch (...) {
    return fail("invalid_budget");
  }
  fp_scanner::ArtifactIdentity identity{
      arguments["--artifact-set-id"], arguments["--artifact-key"],
      arguments["--physical-tu-id"], arguments["--context-id"],
      arguments["--profile"], arguments["--sha256"],
  };
  auto result = fp_scanner::extractFacts(arguments["--input"], identity, max_facts,
                                         max_use_edges, max_summary_depth,
                                         max_summary_call_edges);
  if (!result) {
    llvm::errs() << llvm::toString(result.takeError()) << '\n';
    return 3;
  }
  printJson(std::move(*result));
  return 0;
}
