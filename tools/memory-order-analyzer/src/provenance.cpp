#include "provenance.h"
#include "provenance_protocol.h"

#include <llvm/ADT/SmallVector.h>
#include <llvm/ADT/StringExtras.h>
#include <llvm/Analysis/AliasAnalysis.h>
#include <llvm/Analysis/AssumptionCache.h>
#include <llvm/Analysis/BasicAliasAnalysis.h>
#include <llvm/Analysis/CaptureTracking.h>
#include <llvm/Analysis/LoopInfo.h>
#include <llvm/Analysis/MemoryLocation.h>
#include <llvm/Analysis/MemorySSA.h>
#include <llvm/Analysis/TargetLibraryInfo.h>
#include <llvm/Analysis/ValueTracking.h>
#include <llvm/IR/Dominators.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/Verifier.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/SHA256.h>
#include <llvm/Support/SourceMgr.h>

#include <algorithm>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using namespace llvm;

namespace moa {
namespace {

void require(bool condition, StringRef message) {
  if (!condition) throw std::runtime_error(message.str());
}

std::string requiredString(const json::Object &object, StringRef key) {
  auto value = object.getString(key);
  require(value && !value->empty(), "object_provenance_request_invalid: missing string");
  return value->str();
}

int64_t requiredBudget(const json::Object &budgets, StringRef key) {
  auto value = budgets.getInteger(key);
  require(value && *value > 0, "object_provenance_request_invalid: invalid budget");
  return *value;
}

std::string digest(StringRef text) {
  return toHex(SHA256::hash(arrayRefFromStringRef(text)), true);
}

std::string valueText(const Value &value) {
  std::string text;
  raw_string_ostream output(text);
  value.printAsOperand(output, false);
  return text;
}

std::string valueId(const Value &value, StringRef function, size_t serial) {
  return function.str() + ":value:" + std::to_string(serial) + ":" + valueText(value);
}

json::Object diagnostic(StringRef code, StringRef detail, StringRef detailEn) {
  return json::Object{{"code", code.str()}, {"detail", detail.str()}, {"detail_en", detailEn.str()},
    {"limitation", "有限对象来源结果不代表全程序别名、安全或 happens-before 证明"},
    {"limitation_en", "Bounded object provenance is not a whole-program alias, safety, or happens-before proof"},
    {"suggestion", nullptr}, {"suggestion_en", nullptr}, {"source", nullptr}};
}

std::string storageKind(const Value *value) {
  if (isa<GlobalValue>(value)) return "global";
  if (isa<AllocaInst>(value)) return "stack";
  if (isa<Argument>(value)) return cast<Argument>(value)->getArgNo() == 0 &&
      cast<Argument>(value)->getParent()->hasParamAttribute(0, Attribute::StructRet) ? "receiver" : "parameter";
  return "unknown";
}

json::Object storage(const Value *root, StringRef artifact, StringRef function,
                     StringRef sourceId, unsigned addressSpace) {
  std::string kind = storageKind(root);
  std::string raw = artifact.str() + "|" + function.str() + "|" + sourceId.str() + "|" +
                    kind + "|" + std::to_string(addressSpace);
  return json::Object{{"id", digest(raw)}, {"kind", kind}, {"artifact_key", artifact.str()},
    {"source_id", sourceId.str()}, {"function_id", function.empty() ? json::Value(nullptr) : json::Value(function.str())},
    {"invocation_id", nullptr}, {"allocation", kind == "unknown" ? "unknown" : "single"},
    {"lifetime", "live"}, {"address_space", static_cast<int64_t>(addressSpace)}};
}

json::Object object(json::Object storageValue, int64_t offset) {
  std::string storageId = storageValue.getString("id")->str();
  std::string raw = storageId + "|" + std::to_string(offset) + "|unknown";
  return json::Object{{"id", digest(raw)}, {"storage", std::move(storageValue)},
                      {"path", json::Array{}},
                      {"byte_range", json::Object{{"offset", offset}, {"size", nullptr}}}};
}

json::Object candidate(json::Object objectValue, json::Array proof = {},
                       json::Array opposed = {}, json::Array guards = {}) {
  return json::Object{{"object", std::move(objectValue)}, {"guards", std::move(guards)},
                      {"proof", std::move(proof)}, {"opposed", std::move(opposed)},
                      {"dependencies", json::Array{}}};
}

json::Object unknownDomain(StringRef reason, json::Array candidates = {}) {
  return json::Object{{"state", "unknown"}, {"candidates", std::move(candidates)},
                      {"reason", reason.str()}};
}

StringRef aliasName(AliasResult value) {
  if (value == AliasResult::NoAlias) return "no-alias";
  if (value == AliasResult::MustAlias) return "must-alias";
  if (value == AliasResult::PartialAlias) return "partial-alias";
  return "may-alias";
}

json::Object domainFor(const Value *value, StringRef artifact, StringRef function,
                       const DataLayout &layout, const LoopInfo *loops,
                       unsigned candidateLimit, unsigned captureLimit,
                       json::Array &queries, size_t &querySerial) {
  if (isa<ConstantPointerNull>(value) || isa<UndefValue>(value) || isa<PoisonValue>(value))
    return unknownDomain("null-undef-or-poison-origin");
  if (isa<IntToPtrInst>(value) || isa<PtrToIntInst>(value))
    return unknownDomain("ptr-int-origin");
  if (isa<AddrSpaceCastInst>(value))
    return unknownDomain("address-space-cast");
  SmallVector<const Value *, 8> roots;
  getUnderlyingObjects(value, roots, loops, candidateLimit);
  std::sort(roots.begin(), roots.end(), [](const Value *left, const Value *right) {
    return valueText(*left) < valueText(*right);
  });
  roots.erase(std::unique(roots.begin(), roots.end()), roots.end());
  if (roots.empty()) return unknownDomain("unknown-underlying-object");
  if (roots.size() > candidateLimit) return unknownDomain("candidate-budget-exhausted");
  std::map<const Value *, std::set<std::string>> guardedRoots;
  auto collectGuards = [&](const Value *input, StringRef guard) {
    SmallVector<const Value *, 8> guarded;
    getUnderlyingObjects(input, guarded, loops, candidateLimit);
    for (const Value *root : guarded) guardedRoots[root].insert(guard.str());
  };
  if (auto *phi = dyn_cast<PHINode>(value))
    for (unsigned index = 0; index < phi->getNumIncomingValues(); ++index)
      collectGuards(phi->getIncomingValue(index),
                    ("phi-predecessor:" + phi->getIncomingBlock(index)->getName()).str());
  if (auto *select = dyn_cast<SelectInst>(value)) {
    collectGuards(select->getTrueValue(), "select:true:" + valueText(*select->getCondition()));
    collectGuards(select->getFalseValue(), "select:false:" + valueText(*select->getCondition()));
  }
  bool dynamicIndex = false;
  if (auto *gep = dyn_cast<GetElementPtrInst>(value))
    for (const Use &index : gep->indices())
      dynamicIndex |= !isa<ConstantInt>(index.get());
  json::Array candidates;
  for (const Value *root : roots) {
    int64_t offset = 0;
    const Value *base = GetPointerBaseWithConstantOffset(value, offset, layout);
    bool captured = false;
    if (isa<Instruction, Argument>(root))
      captured = PointerMayBeCaptured(root, true, captureLimit);
    unsigned addressSpace = cast<PointerType>(value->getType())->getAddressSpace();
    std::string sourceId = valueText(*root);
    json::Array proof;
    proof.push_back("llvm-get-underlying-objects");
    if (base == root) proof.push_back("llvm-constant-base-offset");
    if (!captured) proof.push_back("llvm-not-captured");
    json::Array opposed;
    if (captured && !isa<Argument>(root)) opposed.push_back("llvm-pointer-may-be-captured");
    if (storageKind(root) == "unknown") opposed.push_back("llvm-unknown-storage-kind");
    if (dynamicIndex) opposed.push_back("llvm-dynamic-index-unbounded");
    json::Array guards;
    for (const auto &guard : guardedRoots[root]) guards.push_back(guard);
    candidates.push_back(candidate(object(storage(root, artifact, function, sourceId, addressSpace), offset),
                                   std::move(proof), std::move(opposed), std::move(guards)));
    queries.push_back(json::Object{{"id", function.str() + ":query:" + std::to_string(querySerial++)},
      {"kind", "underlying-object"}, {"input", valueText(*value)}, {"result", sourceId},
      {"analysis_node", "llvm-value-tracking"}, {"budget", "candidate_targets"}});
    queries.push_back(json::Object{{"id", function.str() + ":query:" + std::to_string(querySerial++)},
      {"kind", "constant-base-offset"}, {"input", valueText(*value)},
      {"result", base == root ? std::to_string(offset) : "unknown"},
      {"analysis_node", "llvm-data-layout"}, {"budget", "ir_nodes"}});
    queries.push_back(json::Object{{"id", function.str() + ":query:" + std::to_string(querySerial++)},
      {"kind", "capture-tracking"}, {"input", sourceId},
      {"result", captured ? "captured" : "not-captured"},
      {"analysis_node", "llvm-capture-tracking"}, {"budget", "capture_uses"}});
  }
  if (dynamicIndex) return unknownDomain("dynamic-index-unbounded", std::move(candidates));
  bool exact = candidates.size() == 1 && candidates[0].getAsObject()->getArray("opposed")->empty();
  return json::Object{{"state", exact ? "must" : "may"}, {"candidates", std::move(candidates)},
                      {"reason", nullptr}};
}

void strongLoadPropagation(const LoadInst &load, MemorySSA &memory, AAResults &aa,
                           DominatorTree &dominators, StringRef artifact, StringRef function,
                           const DataLayout &layout, const LoopInfo *loops,
                           unsigned candidateLimit, unsigned captureLimit,
                           json::Object &domain, json::Array &queries, size_t &querySerial) {
  if (!load.getType()->isPointerTy() || load.isAtomic() || load.isVolatile()) return;
  auto *access = memory.getMemoryAccess(&load);
  if (!access) return;
  auto *clobber = memory.getWalker()->getClobberingMemoryAccess(access);
  queries.push_back(json::Object{{"id", function.str() + ":query:" + std::to_string(querySerial++)},
    {"kind", "memoryssa-clobber"}, {"input", valueText(*load.getPointerOperand())},
    {"result", clobber ? "memory-access" : "unknown"},
    {"analysis_node", "llvm-memoryssa"}, {"budget", "memoryssa_steps"}});
  auto *definition = dyn_cast<MemoryDef>(clobber);
  auto *store = definition ? dyn_cast_or_null<StoreInst>(definition->getMemoryInst()) : nullptr;
  if (!store || !store->getValueOperand()->getType()->isPointerTy()) return;
  AliasResult alias = aa.alias(MemoryLocation::get(&load), MemoryLocation::get(store));
  bool dominates = dominators.dominates(store, &load);
  queries.push_back(json::Object{{"id", function.str() + ":query:" + std::to_string(querySerial++)},
    {"kind", "aa-memory-location"}, {"input", valueText(*load.getPointerOperand())},
    {"result", aliasName(alias)}, {"analysis_node", "llvm-basicaa"}, {"budget", "aa_queries"}});
  queries.push_back(json::Object{{"id", function.str() + ":query:" + std::to_string(querySerial++)},
    {"kind", "dominance"}, {"input", valueText(*store) + "|" + valueText(load)},
    {"result", dominates ? "dominates" : "does-not-dominate"},
    {"analysis_node", "llvm-dominator-tree"}, {"budget", "ir_nodes"}});
  if (alias != AliasResult::MustAlias || !dominates ||
      PointerMayBeCaptured(store->getPointerOperand(), true, captureLimit)) return;
  domain = domainFor(store->getValueOperand(), artifact, function, layout, loops,
                     candidateLimit, captureLimit, queries, querySerial);
  if (auto *items = domain.getArray("candidates"))
    for (auto &item : *items)
      item.getAsObject()->getArray("proof")->push_back("memoryssa-unique-dominating-store");
}

} // namespace

json::Object objectProvenanceProtocol() {
  auto parsed = json::parse(MOA_PROVENANCE_PROTOCOL_JSON);
  if (!parsed) throw std::runtime_error("object_provenance_protocol_invalid");
  return std::move(*parsed->getAsObject());
}

json::Object localObjectProvenance(Module &module, const json::Object &request) {
  require(request.getInteger("schema_version") == 1 &&
          request.getString("kind") == "LLVMObjectProvenanceRequest",
          "object_provenance_request_invalid: schema/kind");
  auto *budgets = request.getObject("budgets");
  require(budgets, "object_provenance_request_invalid: budgets");
  auto *bitcode = request.getObject("bitcode");
  require(bitcode, "object_provenance_request_invalid: bitcode");
  std::string artifact = requiredString(request, "artifact_key");
  unsigned valueLimit = static_cast<unsigned>(requiredBudget(*budgets, "values"));
  unsigned candidateLimit = static_cast<unsigned>(requiredBudget(*budgets, "candidate_targets"));
  unsigned captureLimit = static_cast<unsigned>(requiredBudget(*budgets, "capture_uses"));
  unsigned aaLimit = static_cast<unsigned>(requiredBudget(*budgets, "aa_queries"));
  unsigned memoryLimit = static_cast<unsigned>(requiredBudget(*budgets, "memoryssa_steps"));
  json::Array values, queries, callEdges, returns, diagnostics, frontier;
  size_t valueSerial = 0, querySerial = 0, memorySteps = 0;
  bool exhausted = false;
  auto emitValue = [&](const Value &value, StringRef function, json::Object domain) {
    if (values.size() >= valueLimit) { exhausted = true; return; }
    auto *pointer = dyn_cast<PointerType>(value.getType());
    values.push_back(json::Object{{"id", valueId(value, function, valueSerial++)},
      {"function_id", function.empty() ? json::Value(nullptr) : json::Value(function.str())},
      {"opcode", isa<Instruction>(value) ? cast<Instruction>(value).getOpcodeName() :
                  isa<Argument>(value) ? "argument" : "global"},
      {"ir_name", valueText(value)},
      {"argument_index", isa<Argument>(value) ? json::Value(static_cast<int64_t>(cast<Argument>(value).getArgNo())) : json::Value(nullptr)},
      {"domain", std::move(domain)}, {"offset", nullptr},
      {"address_space", static_cast<int64_t>(pointer->getAddressSpace())},
      {"evidence", json::Array{"llvm-value-tracking", "llvm-data-layout"}}});
  };
  for (GlobalVariable &global : module.globals()) {
    if (values.size() >= valueLimit) { exhausted = true; break; }
    emitValue(global, {}, domainFor(&global, artifact, {}, module.getDataLayout(), nullptr,
                                   candidateLimit, captureLimit, queries, querySerial));
  }
  for (Function &function : module) {
    if (function.isDeclaration()) continue;
    std::string functionId = function.getName().str();
    DominatorTree dominators(function);
    LoopInfo loops(dominators);
    TargetLibraryInfoImpl implementation(module.getTargetTriple());
    TargetLibraryInfo libraries(implementation, &function);
    AssumptionCache assumptions(function);
    BasicAAResult basic(module.getDataLayout(), function, libraries, assumptions, &dominators);
    AAResults aliases(libraries);
    if (!module.getDataLayoutStr().empty()) aliases.addAAResult(basic);
    MemorySSA memory(function, &aliases, &dominators);
    for (Argument &argument : function.args()) if (argument.getType()->isPointerTy())
      emitValue(argument, functionId, domainFor(&argument, artifact, functionId, module.getDataLayout(), &loops,
                                                candidateLimit, captureLimit, queries, querySerial));
    std::vector<const Value *> pointers;
    for (BasicBlock &block : function) for (Instruction &instruction : block) {
      if (instruction.getType()->isPointerTy()) pointers.push_back(&instruction);
      if (auto *call = dyn_cast<CallBase>(&instruction)) {
        json::Array arguments;
        for (const Use &argument : call->args()) arguments.push_back(valueText(*argument.get()));
        const Function *callee = call->getCalledFunction();
        callEdges.push_back(json::Object{{"id", functionId + ":call:" + std::to_string(callEdges.size())},
          {"caller", functionId}, {"callee", callee ? json::Value(callee->getName().str()) : json::Value(nullptr)},
          {"arguments", std::move(arguments)},
          {"result", instruction.getType()->isPointerTy() ? json::Value(valueText(instruction)) : json::Value(nullptr)},
          {"status", callee ? "direct" : "indirect"}});
        if (!callee) {
          diagnostics.push_back(diagnostic("indirect-call-frontier", "间接调用目标不在有界对象来源范围内",
                                           "Indirect call target is outside bounded object provenance"));
          frontier.push_back(diagnostic("indirect-call-frontier", "间接调用目标不在有界对象来源范围内",
                                        "Indirect call target is outside bounded object provenance"));
        }
      }
      if (auto *ret = dyn_cast<ReturnInst>(&instruction); ret && ret->getReturnValue() &&
          ret->getReturnValue()->getType()->isPointerTy())
        returns.push_back(json::Object{{"id", functionId + ":return:" + std::to_string(returns.size())},
          {"function_id", functionId}, {"value", valueText(*ret->getReturnValue())},
          {"lifetime", isa<AllocaInst>(getUnderlyingObject(ret->getReturnValue())) ? "expired" : "unknown"}});
    }
    for (const Value *pointer : pointers) {
      if (values.size() >= valueLimit) { exhausted = true; break; }
      json::Object domain = domainFor(pointer, artifact, functionId, module.getDataLayout(), &loops,
                                      candidateLimit, captureLimit, queries, querySerial);
      if (auto *load = dyn_cast<LoadInst>(pointer); load && memorySteps++ < memoryLimit)
        strongLoadPropagation(*load, memory, aliases, dominators, artifact, functionId,
                              module.getDataLayout(), &loops, candidateLimit, captureLimit,
                              domain, queries, querySerial);
      emitValue(*pointer, functionId, std::move(domain));
    }
    for (size_t left = 0; left < pointers.size() && querySerial < aaLimit; ++left)
      for (size_t right = left + 1; right < pointers.size() && querySerial < aaLimit; ++right) {
        AliasResult result = aliases.alias(MemoryLocation(pointers[left], LocationSize::beforeOrAfterPointer()),
                                           MemoryLocation(pointers[right], LocationSize::beforeOrAfterPointer()));
        queries.push_back(json::Object{{"id", functionId + ":query:" + std::to_string(querySerial++)},
          {"kind", "aa-memory-location"}, {"input", valueText(*pointers[left]) + "|" + valueText(*pointers[right])},
          {"result", aliasName(result)}, {"analysis_node", "llvm-basicaa"}, {"budget", "aa_queries"}});
      }
  }
  if (exhausted || memorySteps >= memoryLimit || querySerial >= aaLimit) {
    diagnostics.push_back(diagnostic("llvm-provenance-budget-exhausted", "LLVM 对象来源预算已耗尽",
                                     "LLVM object-provenance budget exhausted"));
    frontier.push_back(diagnostic("llvm-provenance-budget-exhausted", "LLVM 对象来源预算已耗尽",
                                  "LLVM object-provenance budget exhausted"));
  }
  std::sort(values.begin(), values.end(), [](const json::Value &left, const json::Value &right) {
    return *left.getAsObject()->getString("id") < *right.getAsObject()->getString("id");
  });
  std::sort(callEdges.begin(), callEdges.end(), [](const json::Value &left, const json::Value &right) {
    return *left.getAsObject()->getString("id") < *right.getAsObject()->getString("id");
  });
  std::sort(returns.begin(), returns.end(), [](const json::Value &left, const json::Value &right) {
    return *left.getAsObject()->getString("id") < *right.getAsObject()->getString("id");
  });
  bool partial = !frontier.empty();
  std::string target = module.getTargetTriple().empty() ? "unknown" : module.getTargetTriple().str();
  return json::Object{{"schema_version", 1}, {"kind", "LLVMObjectProvenanceFacts"},
    {"analysis_version", "0.1.0"}, {"policy_id", "bounded-object-provenance-v1"},
    {"artifact_key", artifact}, {"profile_id", requiredString(request, "profile_id")},
    {"physical_tu_id", requiredString(request, "physical_tu_id")},
    {"bitcode_digest", requiredString(*bitcode, "sha256")},
    {"target", target}, {"data_layout", module.getDataLayoutStr()}, {"mode", "ir-only"},
    {"status", partial ? "partial" : "complete"}, {"values", std::move(values)},
    {"queries", std::move(queries)}, {"call_edges", std::move(callEdges)}, {"returns", std::move(returns)},
    {"counts", json::Object{{"values", static_cast<int64_t>(valueSerial)},
                             {"queries", static_cast<int64_t>(querySerial)}}},
    {"dependencies", json::Array{}}, {"diagnostics", std::move(diagnostics)},
    {"frontier", std::move(frontier)}};
}

int objectProvenanceWorker(const char *path, raw_ostream &out, raw_ostream &err) {
  try {
    auto requestBuffer = MemoryBuffer::getFile(path);
    require(bool(requestBuffer), "object_provenance_request_invalid: cannot read request");
    auto parsed = json::parse((*requestBuffer)->getBuffer());
    require(parsed && parsed->getAsObject(), "object_provenance_request_invalid: invalid JSON");
    auto &request = *parsed->getAsObject();
    auto *bitcode = request.getObject("bitcode");
    require(bitcode, "object_provenance_request_invalid: bitcode");
    LLVMContext context;
    SMDiagnostic error;
    auto module = parseIRFile(requiredString(*bitcode, "path"), error, context);
    require(bool(module), "object_provenance_parse_failed: cannot parse bitcode");
    std::string verification;
    raw_string_ostream verificationStream(verification);
    require(!verifyModule(*module, &verificationStream), "object_provenance_verify_failed: invalid module");
    auto facts = localObjectProvenance(*module, request);
    std::string payload;
    raw_string_ostream stream(payload); stream << json::Value(std::move(facts)) << "\n"; stream.flush();
    auto *budgets = request.getObject("budgets");
    require(budgets && static_cast<uint64_t>(requiredBudget(*budgets, "worker_output_bytes")) >= payload.size(),
            "object_provenance_output_limit: output exceeds worker_output_bytes");
    out << payload; return 0;
  } catch (const std::exception &error) {
    err << error.what() << "\n"; return 1;
  }
}

} // namespace moa
