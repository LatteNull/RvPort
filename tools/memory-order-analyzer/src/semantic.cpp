#include "semantic.h"
#include "ir_identity.h"
#include "protocol.h"
#include <llvm/ADT/StringExtras.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/IntrinsicInst.h>
#include <llvm/IR/Operator.h>
#include <llvm/Support/SHA256.h>
#include <set>
#include <map>
#include <stdexcept>

using namespace llvm;
namespace moa {
json::Object protocol() {
  auto parsed = cantFail(json::parse(MOA_PROTOCOL_JSON));
  return *parsed.getAsObject();
}
ExtractionBudget defaultBudget() {
  auto doc = protocol();
  auto &p = *doc.getObject("policy");
  return {size_t(*p.getInteger("max_nodes")), size_t(*p.getInteger("max_references")),
          unsigned(*p.getInteger("max_constant_depth")), size_t(*p.getInteger("max_output_bytes"))};
}
namespace {
std::string typeText(Type *type) {
  std::string text;
  raw_string_ostream out(text);
  type->print(out);
  return text;
}
std::string number(const APInt &value, unsigned radix = 16, bool sign = false) {
  SmallString<64> text;
  value.toString(text, radix, sign);
  return text.str().str();
}
json::Object unknownSize(StringRef reason) {
  return json::Object{{"status", "unknown"}, {"reason", reason.str()}};
}
class Graph {
  Module &module;
  ExtractionBudget budget;
  std::string artifact;
  DenseMap<const Value *, std::string> ids;
  std::set<std::string> scheduled, roots;
  struct Pending { Value *value; unsigned depth; std::string id; };
  std::vector<Pending> pending;
  json::Array values, diagnostics;
  std::set<std::pair<std::string, std::string>> diagnosed;
  size_t references = 0;
public:
  Graph(Module &m, const std::string &a, ExtractionBudget b) : module(m), budget(b), artifact(a) {
    ids = originalIdentities(module, artifact);
  }
  std::string id(const Value *value) const { return ids.lookup(value); }
  void diagnose(const std::string &key, const std::string &reason) {
    if (diagnosed.emplace(key, reason).second) diagnostics.push_back(json::Object{{"id", key}, {"reason", reason}});
  }
  std::string ref(Value *value, unsigned depth = 0) {
    auto key = id(value);
    if (key.empty()) {
      std::string text;
      raw_string_ostream stream(text);
      value->printAsOperand(stream, true, &module);
      key = artifact + ":constant:" + toHex(SHA256::hash(arrayRefFromStringRef(text)), true);
      ids[value] = key;
    }
    if (depth > budget.depth && isa<Constant>(value) && !isa<GlobalValue>(value)) key += ":depth-limit";
    if (scheduled.insert(key).second) {
      if (scheduled.size() > budget.nodes) throw std::runtime_error("extraction_budget_exceeded: value nodes");
      pending.push_back({value, depth, key});
    }
    return key;
  }
  std::string root(Value *value) { auto key = ref(value); roots.insert(key); return key; }
  json::Value result(Instruction &inst) { return inst.getType()->isVoidTy() ? json::Value(nullptr) : json::Value(root(&inst)); }
  json::Object size(Type *type, const std::string &key) {
    if (module.getDataLayoutStr().empty() || !type->isSized()) {
      diagnose(key, "layout_unavailable"); return unknownSize("layout_unavailable");
    }
    auto bytes = module.getDataLayout().getTypeStoreSize(type);
    if (bytes.isScalable()) { diagnose(key, "scalable_size"); return unknownSize("scalable_size"); }
    return json::Object{{"status", "known"}, {"bytes", std::to_string(bytes.getFixedValue())}};
  }
  json::Object access(Value *pointer, Type *type, MaybeAlign alignment, StringRef role,
                      const std::string &key, Value *length = nullptr) {
    json::Object bytes;
    if (auto *constant = dyn_cast_or_null<ConstantInt>(length))
      bytes = json::Object{{"status", "known"}, {"bytes", number(constant->getValue(), 10)}};
    else if (length) { bytes = unknownSize("dynamic_length"); diagnose(key, "dynamic_length"); }
    else bytes = size(type, key);
    return json::Object{{"role", role.str()}, {"address_ref", root(pointer)},
            {"address_space", pointer->getType()->getPointerAddressSpace()},
            {"alignment", alignment ? json::Value(alignment->value()) : json::Value(nullptr)}, {"size", std::move(bytes)}};
  }
  void operation(Value *value, json::Object &node, json::Object &details, unsigned depth) {
    auto *user = dyn_cast<User>(value);
    json::Array operands;
    if (user) for (auto &use : user->operands()) {
      if (isa<BasicBlock>(use.get()) || isa<MetadataAsValue>(use.get())) continue;
      if (++references > budget.references) throw std::runtime_error("extraction_budget_exceeded: operand references");
      operands.push_back(ref(use.get(), isa<Constant>(value) ? depth + 1 : 0));
    }
    node["operands"] = std::move(operands);
    auto *op = dyn_cast<Operator>(value);
    if (!op) return;
    details["opcode"] = Instruction::getOpcodeName(op->getOpcode());
    if (auto *overflow = dyn_cast<OverflowingBinaryOperator>(value)) {
      details["nsw"] = overflow->hasNoSignedWrap(); details["nuw"] = overflow->hasNoUnsignedWrap();
    }
    if (auto *exact = dyn_cast<PossiblyExactOperator>(value)) details["exact"] = exact->isExact();
    if (auto *phi = dyn_cast<PHINode>(value)) {
      json::Array incoming;
      for (unsigned i = 0; i < phi->getNumIncomingValues(); ++i)
        incoming.push_back(json::Object{{"value_ref", ref(phi->getIncomingValue(i))}, {"predecessor", id(phi->getIncomingBlock(i))}});
      details["incoming"] = std::move(incoming);
    }
    if (auto *cmp = dyn_cast<ICmpInst>(value)) details["predicate"] = cmp->getPredicateName(cmp->getPredicate()).str();
    if (auto *extract = dyn_cast<ExtractValueInst>(value)) {
      json::Array indices; for (auto i : extract->getIndices()) indices.push_back(i); details["indices"] = std::move(indices);
    }
    if (auto *insert = dyn_cast<InsertValueInst>(value)) {
      json::Array indices; for (auto i : insert->getIndices()) indices.push_back(i); details["indices"] = std::move(indices);
    }
    if (auto *gep = dyn_cast<GEPOperator>(value)) {
      details["source_type"] = typeText(gep->getSourceElementType());
      details["inbounds"] = gep->isInBounds();
      details["nuw"] = gep->hasNoUnsignedWrap();
      details["nusw"] = gep->hasNoUnsignedSignedWrap();
      auto key = *node.getString("id");
      if (module.getDataLayoutStr().empty()) {
        details["offset"] = unknownSize("layout_unavailable"); diagnose(key.str(), "layout_unavailable");
      } else {
        auto width = module.getDataLayout().getIndexSizeInBits(gep->getPointerAddressSpace());
        APInt offset(width, 0);
        if (gep->accumulateConstantOffset(module.getDataLayout(), offset))
          details["offset"] = json::Object{{"status", "known"}, {"bits", width}, {"hex", number(offset)}, {"signed_decimal", number(offset, 10, true)}};
        else { details["offset"] = unknownSize("dynamic_offset"); diagnose(key.str(), "dynamic_offset"); }
      }
    }
    const auto opcode = op->getOpcode();
    bool supported = opcode == Instruction::PHI || opcode == Instruction::Select || opcode == Instruction::Freeze ||
      opcode == Instruction::GetElementPtr || opcode == Instruction::ICmp || opcode == Instruction::ExtractValue ||
      opcode == Instruction::InsertValue || opcode == Instruction::Alloca || opcode == Instruction::Load ||
      opcode == Instruction::AtomicRMW || opcode == Instruction::AtomicCmpXchg || opcode == Instruction::Call ||
      opcode == Instruction::Invoke || (Instruction::isCast(opcode) && opcode != Instruction::AddrSpaceCast && opcode != Instruction::IntToPtr) ||
      (Instruction::isBinaryOp(opcode) && value->getType()->isIntOrIntVectorTy());
    if (!supported) { node["status"] = "unknown"; node["reason"] = "unsupported_operation"; diagnose(node.getString("id")->str(), "unsupported_operation"); }
  }
  void finish(json::Object &facts) {
    for (size_t i = 0; i < pending.size(); ++i) {
      auto [value, depth, key] = pending[i];
      auto *type = value->getType();
      json::Object node{{"id", key}, {"kind", "unknown"}, {"type", typeText(type)},
        {"type_kind", type->isIntegerTy() ? "integer" : type->isPointerTy() ? "pointer" : "other"},
        {"function", nullptr}, {"block", nullptr}, {"operands", json::Array{}}, {"status", "known"}};
      if (type->isIntegerTy()) node["bits"] = type->getIntegerBitWidth();
      if (type->isPointerTy()) node["address_space"] = type->getPointerAddressSpace();
      json::Object details;
      if (key.ends_with(":depth-limit")) { node["status"] = "unknown"; node["reason"] = "constant_depth"; diagnose(key, "constant_depth"); }
      else if (auto *arg = dyn_cast<Argument>(value)) { node["kind"] = "argument"; node["function"] = id(arg->getParent()); details["position"] = arg->getArgNo(); }
      else if (isa<GlobalValue>(value)) node["kind"] = "symbol";
      else if (auto *integer = dyn_cast<ConstantInt>(value)) { node["kind"] = "integer"; details["hex"] = number(integer->getValue()); }
      else if (isa<ConstantPointerNull>(value)) node["kind"] = "null";
      else if (isa<PoisonValue>(value)) node["kind"] = "poison";
      else if (isa<UndefValue>(value)) node["kind"] = "undef";
      else if (isa<ConstantAggregateZero>(value)) node["kind"] = "zero";
      else if (auto *data = dyn_cast<ConstantDataSequential>(value)) {
        node["kind"] = "aggregate"; json::Array items;
        for (unsigned n = 0; n < data->getNumElements(); ++n) {
          if (++references > budget.references) throw std::runtime_error("extraction_budget_exceeded: operand references");
          items.push_back(ref(data->getElementAsConstant(n), depth + 1));
        }
        node["operands"] = std::move(items);
      } else if (isa<ConstantAggregate>(value)) { node["kind"] = "aggregate"; operation(value, node, details, depth); }
      else if (isa<Instruction>(value) || isa<ConstantExpr>(value)) {
        node["kind"] = isa<Instruction>(value) ? "instruction" : "expression";
        if (auto *inst = dyn_cast<Instruction>(value)) { node["function"] = id(inst->getFunction()); node["block"] = id(inst->getParent()); }
        operation(value, node, details, depth);
      } else { node["status"] = "unknown"; node["reason"] = "unsupported_value"; diagnose(key, "unsupported_value"); }
      node["details"] = std::move(details); values.push_back(std::move(node));
    }
    facts["extraction"] = json::Object{{"status", diagnostics.empty() ? "complete" : "partial"}, {"roots", roots.size()},
       {"nodes", values.size()}, {"references", references}, {"unknown", diagnostics.size()}, {"diagnostics", std::move(diagnostics)}};
    facts["values"] = std::move(values); facts["protocol"] = protocol(); facts["schema_version"] = 2;
  }
};
} // namespace

void enrich(Module &module, json::Object &facts, ExtractionBudget budget) {
  Graph graph(module, facts.getString("artifact_key")->str(), budget);
  std::map<std::string, json::Object *> functions, events, calls, globals;
  for (auto &v : *facts.getArray("functions")) functions[v.getAsObject()->getString("id")->str()] = v.getAsObject();
  for (auto &v : *facts.getArray("globals")) globals[v.getAsObject()->getString("id")->str()] = v.getAsObject();
  for (auto &v : *facts.getArray("events")) events[v.getAsObject()->getString("id")->str()] = v.getAsObject();
  for (auto &v : *facts.getArray("calls")) calls[v.getAsObject()->getString("id")->str()] = v.getAsObject();
  for (auto &g : module.globals()) (*globals.at(graph.id(&g)))["initializer"] = json::Object{
    {"state", g.hasInitializer() ? "value" : "declaration"}, {"value_ref", g.hasInitializer() ? json::Value(graph.root(g.getInitializer())) : json::Value(nullptr)}};
  for (auto &f : module) {
    auto &fn = *functions.at(graph.id(&f)); json::Array parameters;
    for (auto &arg : f.args()) parameters.push_back(graph.root(&arg));
    fn["parameters"] = std::move(parameters); fn["return_type"] = typeText(f.getReturnType()); fn["vararg"] = f.isVarArg();
    unsigned bi = 0;
    for (auto &block : f) {
      auto &bj = *(*fn.getArray("blocks"))[bi++].getAsObject(); auto *term = block.getTerminator();
      json::Object tj{{"id", graph.id(term)}, {"opcode", term->getOpcodeName()}, {"condition_ref", nullptr}, {"return_ref", nullptr}, {"status", "known"}};
      Value *condition = nullptr;
      if (auto *br = dyn_cast<BranchInst>(term)) { if (br->isConditional()) condition = br->getCondition(); }
      if (auto *sw = dyn_cast<SwitchInst>(term)) condition = sw->getCondition();
      if (condition) tj["condition_ref"] = graph.root(condition);
      if (auto *ret = dyn_cast<ReturnInst>(term)) if (ret->getReturnValue()) tj["return_ref"] = graph.root(ret->getReturnValue());
      bool known = isa<BranchInst, SwitchInst, ReturnInst, UnreachableInst, InvokeInst>(term);
      if (!known) { tj["status"] = "unknown"; graph.diagnose(graph.id(term), "unsupported_terminator"); }
      json::Array edges;
      for (unsigned i = 0; i < term->getNumSuccessors(); ++i) {
        std::string kind = "unconditional"; json::Value caseRef(nullptr);
        if (isa<BranchInst>(term) && condition) kind = i == 0 ? "true" : "false";
        if (auto *sw = dyn_cast<SwitchInst>(term)) { kind = i ? "case" : "default"; if (i) caseRef = graph.root((sw->case_begin() + (i - 1))->getCaseValue()); }
        if (isa<InvokeInst>(term)) kind = i == 0 ? "normal" : "unwind";
        if (!known) kind = "unknown";
        edges.push_back(json::Object{{"ordinal", i}, {"target", graph.id(term->getSuccessor(i))}, {"kind", kind},
          {"condition_ref", condition ? json::Value(graph.root(condition)) : json::Value(nullptr)}, {"case_ref", std::move(caseRef)}});
      }
      tj["edges"] = std::move(edges); bj["terminator"] = std::move(tj);
      for (auto &inst : block) {
        const auto key = graph.id(&inst);
        if (auto *call = dyn_cast<CallBase>(&inst)) {
          auto &cj = *calls.at(key); json::Array arguments, bundles;
          for (auto &arg : call->args()) arguments.push_back(graph.root(arg.get()));
          cj["called_ref"] = graph.root(call->getCalledOperand()); cj["arguments"] = std::move(arguments); cj["result_ref"] = graph.result(inst);
          cj["function_type"] = typeText(call->getFunctionType()); cj["calling_convention"] = call->getCallingConv();
          cj["normal"] = nullptr; cj["unwind"] = nullptr; cj["tail"] = "none"; cj["status"] = "known";
          if (auto *invoke = dyn_cast<InvokeInst>(call)) { cj["normal"] = graph.id(invoke->getNormalDest()); cj["unwind"] = graph.id(invoke->getUnwindDest()); }
          if (auto *ci = dyn_cast<CallInst>(call)) cj["tail"] = std::to_string(ci->getTailCallKind());
          std::string attrs; raw_string_ostream stream(attrs);
          if (!call->getAttributes().isEmpty()) call->getAttributes().print(stream);
          cj["attributes"] = attrs;
          cj["attribute_status"] = attrs.empty() ? "not_applicable" : "unknown";
          if (!attrs.empty()) { cj["status"] = "unknown"; graph.diagnose(key, "uninterpreted_abi_attributes"); }
          for (unsigned b = 0; b < call->getNumOperandBundles(); ++b) {
            auto bundle = call->getOperandBundleAt(b); json::Array inputs;
            for (auto &input : bundle.Inputs) inputs.push_back(graph.root(input.get()));
            bundles.push_back(json::Object{{"tag", bundle.getTagName().str()}, {"inputs", std::move(inputs)}});
          }
          cj["bundles"] = std::move(bundles);
          if (call->hasOperandBundles() || call->isInlineAsm()) { cj["status"] = "unknown"; graph.diagnose(key, "opaque_call_features"); }
        }
        if (!events.contains(key)) continue;
        auto &event = *events.at(key); json::Object inputs; json::Array ranges;
        event["result_ref"] = graph.result(inst);
        if (auto *l = dyn_cast<LoadInst>(&inst)) ranges.push_back(graph.access(l->getPointerOperand(), l->getType(), l->getAlign(), "read", key));
        if (auto *s = dyn_cast<StoreInst>(&inst)) { inputs["value"] = graph.root(s->getValueOperand()); ranges.push_back(graph.access(s->getPointerOperand(), s->getValueOperand()->getType(), s->getAlign(), "write", key)); }
        if (auto *r = dyn_cast<AtomicRMWInst>(&inst)) { inputs["value"] = graph.root(r->getValOperand()); ranges.push_back(graph.access(r->getPointerOperand(), r->getValOperand()->getType(), r->getAlign(), "read_write", key)); }
        if (auto *c = dyn_cast<AtomicCmpXchgInst>(&inst)) {
          inputs["compare"] = graph.root(c->getCompareOperand()); inputs["new"] = graph.root(c->getNewValOperand());
          ranges.push_back(graph.access(c->getPointerOperand(), c->getCompareOperand()->getType(), c->getAlign(), "read_write", key));
        }
        if (auto *m = dyn_cast<MemIntrinsic>(&inst)) {
          inputs["length"] = graph.root(m->getLength()); ranges.push_back(graph.access(m->getDest(), nullptr, m->getDestAlign(), "write", key, m->getLength()));
          if (auto *t = dyn_cast<MemTransferInst>(m)) ranges.push_back(graph.access(t->getSource(), nullptr, t->getSourceAlign(), "read", key, m->getLength()));
          if (auto *s = dyn_cast<MemSetInst>(m)) inputs["fill"] = graph.root(s->getValue());
        }
        if (event.getString("kind") == "opaque_effect") graph.diagnose(key, "opaque_effect");
        event["range_status"] = isa<FenceInst>(inst) ? "not_applicable" : ranges.empty() ? "unknown" : "available";
        event["inputs"] = std::move(inputs); event["ranges"] = std::move(ranges);
      }
    }
  }
  graph.finish(facts);
  auto &cap = *facts.getObject("capabilities"); cap["values"] = true; cap["conditional_cfg"] = true; cap["call_operands"] = true; cap["memory_ranges"] = true;
  std::string serialized; raw_string_ostream stream(serialized); stream << json::Value(json::Object(facts));
  if (serialized.size() + 1 > budget.output) throw std::runtime_error("extraction_budget_exceeded: JSON output");
}
} // namespace moa
