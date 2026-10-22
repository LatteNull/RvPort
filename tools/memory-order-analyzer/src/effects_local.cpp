#include "effects.h"
#include "ir_identity.h"
#include <llvm/Analysis/AssumptionCache.h>
#include <llvm/Analysis/BasicAliasAnalysis.h>
#include <llvm/Analysis/MemorySSA.h>
#include <llvm/Analysis/TargetLibraryInfo.h>
#include <llvm/IR/Dominators.h>
#include <llvm/IR/Instructions.h>
#include <llvm/Transforms/Utils/PromoteMemToReg.h>
#include <stdexcept>

using namespace llvm;
namespace moa {
void localQueries(Module &module, StringRef artifact, const json::Object &budgets, json::Object &output) {
  auto ids = originalIdentities(module, artifact.str());
  json::Array nodes, evidence, objects;
  int64_t remaining = *budgets.getInteger("local_steps");
  auto step = [&] {
    if (--remaining < 0) throw std::runtime_error("local_budget_exceeded: local registry work limit");
  };
  auto source = [&](const Value *value, json::Value owner) {
    return json::Object{{"artifact_key", artifact.str()}, {"function_id", std::move(owner)}, {"id", ids.lookup(value)}};
  };
  auto typeText = [](Type *type) {
    std::string text;
    raw_string_ostream out(text);
    type->print(out);
    return text;
  };
  for (auto &function : module) {
    if (function.isDeclaration()) continue;
    auto fid = ids.lookup(&function);
    DominatorTree dt(function);
    TargetLibraryInfoImpl impl(module.getTargetTriple());
    TargetLibraryInfo tli(impl, &function);
    AssumptionCache ac(function);
    BasicAAResult basic(module.getDataLayout(), function, tli, ac, &dt);
    AAResults aa(tli);
    if (!module.getDataLayoutStr().empty()) aa.addAAResult(basic);
    MemorySSA mssa(function, &aa, &dt);
    DenseMap<const MemoryAccess *, std::string> memoryIds;
    unsigned serial = 0;
    auto analysisRef = [&](StringRef id) {
      return json::Object{{"artifact_key", artifact.str()}, {"function_id", fid}, {"analysis_id", id.str()}};
    };
    auto makeId = [&](StringRef kind) { return fid + ":p2:" + kind.str() + ":" + std::to_string(serial++); };
    // Register before emitting edges: MemoryPhi may refer forward or back.
    auto registerMemory = [&](const MemoryAccess *access, StringRef kind) {
      step();
      memoryIds[access] = makeId(kind);
    };
    registerMemory(mssa.getLiveOnEntryDef(), "memory_live_on_entry");
    for (auto &block : function) {
      if (auto *phi = mssa.getMemoryAccess(&block)) registerMemory(phi, "memory_phi");
      for (auto &instruction : block) {
        step();
        nodes.push_back(json::Object{{"source", source(&instruction, fid)}, {"block", source(&block, fid)},
          {"opcode", instruction.getOpcodeName()}, {"type", typeText(instruction.getType())}});
        if (auto *access = mssa.getMemoryAccess(&instruction))
          registerMemory(access, isa<MemoryDef>(access) ? "memory_def" : "memory_use");
        if (auto *alloca = dyn_cast<AllocaInst>(&instruction)) {
          step();
          json::Value size = nullptr;
          std::string reason;
          if (module.getDataLayoutStr().empty()) reason = "missing_data_layout";
          else if (auto bytes = alloca->getAllocationSize(module.getDataLayout()); bytes && !bytes->isScalable())
            size = std::to_string(bytes->getFixedValue());
          else reason = "dynamic_or_scalable_allocation";
          bool privateCandidate = isAllocaPromotable(alloca);
          if (!privateCandidate) reason += (reason.empty() ? "" : ";") + std::string("not_promotable");
          objects.push_back(json::Object{{"source", source(alloca, fid)}, {"allocated_type", typeText(alloca->getAllocatedType())},
            {"size_bytes", std::move(size)}, {"address_space", alloca->getAddressSpace()}, {"private", privateCandidate},
            {"reason", reason.empty() ? json::Value(nullptr) : json::Value(reason)}});
        }
      }
    }
    auto memoryRef = [&](const MemoryAccess *access) { return analysisRef(memoryIds.lookup(access)); };
    auto emit = [&](json::Object ref, StringRef kind, json::Object src, json::Array inputs, StringRef result) {
      evidence.push_back(json::Object{{"ref", std::move(ref)}, {"kind", kind.str()}, {"source", std::move(src)},
        {"inputs", std::move(inputs)}, {"result", result.str()}});
    };
    emit(memoryRef(mssa.getLiveOnEntryDef()), "memory_live_on_entry", source(&function, nullptr), {}, "candidate");
    for (auto &block : function) {
      step();
      json::Array dominators;
      auto *node = dt.getNode(&block);
      if (node && node->getIDom()) dominators.push_back(source(node->getIDom()->getBlock(), fid));
      emit(analysisRef(makeId("dominance")), "dominance", source(&block, fid), std::move(dominators),
           dt.isReachableFromEntry(&block) ? "reachable" : "unreachable");
      if (auto *phi = mssa.getMemoryAccess(&block)) {
        json::Array incoming;
        for (unsigned i = 0; i < phi->getNumIncomingValues(); ++i) {
          step();
          incoming.push_back(source(phi->getIncomingBlock(i), fid));
          incoming.push_back(memoryRef(phi->getIncomingValue(i)));
        }
        emit(memoryRef(phi), "memory_phi", source(&block, fid), std::move(incoming), "candidate");
      }
      for (auto &instruction : block) if (auto *access = mssa.getMemoryAccess(&instruction)) {
        emit(memoryRef(access), isa<MemoryDef>(access) ? "memory_def" : "memory_use", source(&instruction, fid),
             json::Array{memoryRef(access->getDefiningAccess())}, "candidate");
        step();
        auto *clobber = mssa.getWalker()->getClobberingMemoryAccess(access);
        emit(analysisRef(makeId("aa_clobber")), "aa_clobber", source(&instruction, fid),
             json::Array{memoryRef(access), memoryRef(clobber)}, "candidate");
      }
    }
  }
  output["ir_nodes"] = std::move(nodes);
  output["analysis_evidence"] = std::move(evidence);
  output["objects"] = std::move(objects);
}
} // namespace moa
