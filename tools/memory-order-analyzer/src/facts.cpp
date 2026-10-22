#include "facts.h"
#include "semantic.h"
#include <llvm/ADT/StringExtras.h>
#include <llvm/IR/CFG.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/DebugInfoMetadata.h>
#include <llvm/IR/InlineAsm.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/IntrinsicInst.h>
#include <llvm/IR/Operator.h>
#include <llvm/IR/Verifier.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/SHA256.h>
#include <llvm/Support/SourceMgr.h>
#include <stdexcept>

using namespace llvm;
namespace moa {
std::string symbolId(const GlobalValue &value, const std::string &artifact) {
  if (value.hasName()) return artifact + ":symbol:" + value.getName().str();
  std::string operand;
  raw_string_ostream stream(operand);
  value.printAsOperand(stream, false, value.getParent());
  return artifact + ":unnamed-symbol:" + operand;
}
namespace {
std::string ordering(AtomicOrdering order) {
  return toIRString(order);
}
std::string scope(LLVMContext &context, SyncScope::ID id) {
  SmallVector<StringRef> names;
  context.getSyncScopeNames(names);
  return names[id].empty() ? "system" : names[id].str();
}
std::string linkage(GlobalValue &value) {
  if (value.hasLocalLinkage()) return "internal";
  if (value.hasExternalLinkage()) return "external";
  if (value.hasExternalWeakLinkage()) return "extern_weak";
  if (value.hasCommonLinkage()) return "common";
  if (value.hasAvailableExternallyLinkage()) return "available_externally";
  if (value.hasLinkOnceLinkage()) return "linkonce";
  return "weak";
}
json::Object symbol(GlobalValue &value, const std::string &artifact) {
  auto *object = dyn_cast<GlobalObject>(&value);
  return json::Object{{"id", symbolId(value, artifact)},
          {"name", value.getName().str()}, {"declaration", value.isDeclaration()},
          {"linkage", linkage(value)}, {"comdat", object && object->hasComdat()},
          {"visibility", static_cast<int64_t>(value.getVisibility())}};
}
json::Object address(Value *value, const std::string &function,
                     const DenseMap<const Instruction *, std::string> &ids,
                     unsigned depth = 0) {
  if (!value || depth > 8) return json::Object{{"kind", "unknown"}};
  // A cast is not an object-identity proof, including equal-width address spaces.
  if (auto *global = dyn_cast<GlobalVariable>(value)) {
    if (global->hasName()) return json::Object{{"kind", "global"}, {"symbol", global->getName().str()}};
    return json::Object{{"kind", "unknown"}};
  }
  if (auto *arg = dyn_cast<Argument>(value))
    return json::Object{{"kind", "argument"}, {"object", function + ":arg:" + std::to_string(arg->getArgNo())}};
  if (auto *alloca = dyn_cast<AllocaInst>(value))
    return json::Object{{"kind", "alloca"}, {"object", ids.lookup(alloca)}};
  if (auto *gep = dyn_cast<GEPOperator>(value)) {
    json::Array indices;
    for (auto &index : gep->indices()) {
      auto *constant = dyn_cast<ConstantInt>(index);
      if (!constant || constant->getBitWidth() > 64) return json::Object{{"kind", "unknown"}};
      indices.push_back(constant->getSExtValue());
    }
    return json::Object{{"kind", "constant_gep"}, {"base", address(gep->getPointerOperand(), function, ids, depth + 1)},
            {"indices", std::move(indices)}};
  }
  return json::Object{{"kind", "unknown"}};
}
json::Object location(const Instruction &instruction) {
  json::Array chain;
  for (auto *loc = instruction.getDebugLoc().get(); loc; loc = loc->getInlinedAt()) {
    chain.push_back(json::Object{{"file", loc->getFilename().str()}, {"directory", loc->getDirectory().str()},
                                {"line", static_cast<int64_t>(loc->getLine())},
                                {"column", static_cast<int64_t>(loc->getColumn())}});
  }
  return json::Object{{"inline_chain", std::move(chain)}, {"consistency", "unverified"}};
}
} // namespace

json::Object extract(Module &module, const std::string &artifact, const std::string &hash) {
  json::Array functions, globals, events, calls, producer;
  size_t located = 0, eventCount = 0;
  if (auto *ident = module.getNamedMetadata("llvm.ident"))
    for (auto *node : ident->operands())
      for (auto &operand : node->operands())
        if (auto *text = dyn_cast<MDString>(operand)) producer.push_back(text->getString().str());
  for (auto &global : module.globals()) globals.push_back(symbol(global, artifact));
  for (auto &alias : module.aliases()) {
    auto value = symbol(alias, artifact);
    value["linkage"] = "alias";
    globals.push_back(std::move(value));
  }
  for (auto &ifunc : module.ifuncs()) {
    auto value = symbol(ifunc, artifact);
    value["linkage"] = "ifunc";
    functions.push_back(std::move(value));
  }
  for (auto &function : module) {
    auto fn = symbol(function, artifact);
    const auto functionId = symbolId(function, artifact);
    json::Array blocks;
    DenseMap<const BasicBlock *, std::string> blockIds;
    DenseMap<const Instruction *, std::string> ids;
    size_t blockNumber = 0;
    for (auto &block : function) {
      auto blockId = functionId + ":b" + std::to_string(blockNumber++);
      blockIds[&block] = blockId;
      size_t instructionNumber = 0;
      for (auto &instruction : block)
        ids[&instruction] = blockId + ":i" + std::to_string(instructionNumber++);
    }
    for (auto &block : function) {
      json::Array successors;
      for (auto *successor : llvm::successors(&block)) successors.push_back(blockIds.lookup(successor));
      blocks.push_back(json::Object{{"id", blockIds.lookup(&block)}, {"successors", std::move(successors)}});
      for (auto &instruction : block) {
        json::Object event;
        if (auto *load = dyn_cast<LoadInst>(&instruction)) {
          event = json::Object{{"kind", "load"}, {"volatile", load->isVolatile()}, {"atomic", load->isAtomic()},
                   {"ordering", ordering(load->getOrdering())}, {"syncscope", scope(module.getContext(), load->getSyncScopeID())},
                   {"address", address(load->getPointerOperand(), functionId, ids)}};
        } else if (auto *store = dyn_cast<StoreInst>(&instruction)) {
          event = json::Object{{"kind", "store"}, {"volatile", store->isVolatile()}, {"atomic", store->isAtomic()},
                   {"ordering", ordering(store->getOrdering())}, {"syncscope", scope(module.getContext(), store->getSyncScopeID())},
                   {"address", address(store->getPointerOperand(), functionId, ids)}};
        } else if (auto *rmw = dyn_cast<AtomicRMWInst>(&instruction)) {
          event = json::Object{{"kind", "atomicrmw"}, {"operation", AtomicRMWInst::getOperationName(rmw->getOperation())},
                   {"ordering", ordering(rmw->getOrdering())}, {"volatile", rmw->isVolatile()},
                   {"syncscope", scope(module.getContext(), rmw->getSyncScopeID())},
                   {"address", address(rmw->getPointerOperand(), functionId, ids)}};
        } else if (auto *cas = dyn_cast<AtomicCmpXchgInst>(&instruction)) {
          event = json::Object{{"kind", "cmpxchg"}, {"success_ordering", ordering(cas->getSuccessOrdering())},
                   {"failure_ordering", ordering(cas->getFailureOrdering())}, {"weak", cas->isWeak()},
                   {"volatile", cas->isVolatile()}, {"syncscope", scope(module.getContext(), cas->getSyncScopeID())},
                   {"address", address(cas->getPointerOperand(), functionId, ids)}};
        } else if (auto *fence = dyn_cast<FenceInst>(&instruction)) {
          event = json::Object{{"kind", "fence"}, {"ordering", ordering(fence->getOrdering())},
                   {"syncscope", scope(module.getContext(), fence->getSyncScopeID())}};
        }
        if (auto *call = dyn_cast<CallBase>(&instruction)) {
          auto *callee = dyn_cast<Function>(call->getCalledOperand()->stripPointerCasts());
          if (callee && !callee->hasName()) callee = nullptr;
          calls.push_back(json::Object{{"id", ids.lookup(call)}, {"function", functionId},
                                      {"target", callee ? json::Value(callee->getName().str()) : json::Value(nullptr)},
                                      {"kind", callee ? "direct" : "indirect"},
                                      {"source", location(instruction)}});
          if (auto *memory = dyn_cast<MemIntrinsic>(call)) {
            event = json::Object{{"kind", callee->getName().str()}, {"volatile", memory->isVolatile()},
                     {"address", address(memory->getDest(), functionId, ids)}};
            if (auto *transfer = dyn_cast<MemTransferInst>(memory))
              event["source_address"] = address(transfer->getSource(), functionId, ids);
          } else if (call->isInlineAsm() || (callee && callee->isIntrinsic())) {
            event = json::Object{{"kind", "opaque_effect"}, {"reason", call->isInlineAsm() ? "inline_asm" : "intrinsic"}};
          }
        }
        if (!event.empty()) {
          ++eventCount;
          if (instruction.getDebugLoc()) ++located;
          event["id"] = ids.lookup(&instruction);
          event["function"] = functionId;
          event["block"] = blockIds.lookup(&block);
          event["source"] = location(instruction);
          events.push_back(std::move(event));
        }
      }
    }
    fn["blocks"] = std::move(blocks);
    functions.push_back(std::move(fn));
  }
  json::Object facts{{"schema_version", 2}, {"kind", "ModuleFacts"}, {"artifact_key", artifact},
          {"module_hash", hash}, {"target", module.getTargetTriple().str()}, {"layout", module.getDataLayoutStr()},
          {"producer", std::move(producer)}, {"functions", std::move(functions)}, {"globals", std::move(globals)},
          {"events", std::move(events)}, {"calls", std::move(calls)},
          {"source_mapping", located == 0 ? "unavailable" : located == eventCount ? "complete" : "partial"},
          {"capabilities", json::Object{{"direct_symbols", true}, {"constant_gep", true},
                                        {"points_to", false}, {"callsite_specialization", false},
                                        {"effect_propagation", false}, {"threads", false}, {"memory_model", false}}}};
  enrich(module, facts, defaultBudget());
  return facts;
}

json::Object read(const std::string &path, const std::string &artifact) {
  auto buffer = MemoryBuffer::getFile(path);
  if (!buffer) throw std::runtime_error("input_unreadable: " + buffer.getError().message());
  if ((*buffer)->getBufferSize() < 4 || !(*buffer)->getBuffer().starts_with(StringRef("BC\xc0\xde", 4)))
    throw std::runtime_error("format_invalid: expected LLVM bitcode (not textual IR)");
  LLVMContext context;
  SMDiagnostic diagnostic;
  auto module = parseIR((*buffer)->getMemBufferRef(), diagnostic, context);
  if (!module) throw std::runtime_error("reader_failed: " + diagnostic.getMessage().str());
  std::string verification;
  raw_string_ostream stream(verification);
  if (verifyModule(*module, &stream)) throw std::runtime_error("verify_failed: " + verification);
  auto digest = SHA256::hash(arrayRefFromStringRef((*buffer)->getBuffer()));
  return extract(*module, artifact, toHex(digest, true));
}
} // namespace moa
