#include "effects.h"
#include "ir_identity.h"
#include <llvm/IR/Instructions.h>
#include <llvm/Support/SHA256.h>
#include <llvm/ADT/StringExtras.h>
#include <set>

using namespace llvm;
namespace moa {
namespace {
std::string typeText(Type *type) {
  std::string result;
  raw_string_ostream out(result);
  type->print(out);
  return result;
}
json::Object reference(const std::string &artifact, json::Value function, std::string id) {
  return json::Object{{"artifact_key", artifact}, {"function_id", std::move(function)}, {"id", std::move(id)}};
}
bool scalar(Type *type) { return type->isIntegerTy() || type->isPointerTy(); }
std::string bodyFingerprint(Function &function, StringRef artifact) {
  if (function.isDeclaration()) return {};
  DenseMap<const Value *, unsigned> numbers;
  unsigned serial = 0;
  for (auto &argument : function.args()) numbers[&argument] = serial++;
  for (auto &block : function) {
    numbers[&block] = serial++;
    for (auto &instruction : block) numbers[&instruction] = serial++;
  }
  std::string normalized;
  raw_string_ostream out(normalized);
  out << typeText(function.getFunctionType()) << ';';
  for (auto &block : function) for (auto &instruction : block) {
    out << instruction.getOpcodeName() << ':' << typeText(instruction.getType()) << '(';
    for (const auto &use : instruction.operands()) {
      const Value *operand = use.get();
      if (auto found = numbers.find(operand); found != numbers.end()) out << '#' << found->second;
      else if (auto *global = dyn_cast<GlobalValue>(operand)) {
        // Two TUs may legally reuse a private/internal spelling for different
        // objects.  Keep that artifact-qualified identity in the ODR digest;
        // externally visible references remain name-normalized across copies.
        out << '@' << (global->hasLocalLinkage() ? symbolId(*global, artifact.str()) : global->getName().str());
      }
      else operand->printAsOperand(out, false);
      out << ',';
    }
    out << ");";
  }
  out.flush();
  return toHex(SHA256::hash(arrayRefFromStringRef(normalized)), true);
}
json::Object interface(FunctionType *type, unsigned convention, AttributeList attributes,
                       bool unsupportedCall = false) {
  bool supported = !type->isVarArg() && convention == CallingConv::C && !unsupportedCall;
  supported &= type->getReturnType()->isVoidTy() || scalar(type->getReturnType());
  json::Array parameters, attrs;
  for (auto *parameter : type->params()) {
    parameters.push_back(typeText(parameter));
    supported &= scalar(parameter);
  }
  // No precision is derived from these attributes. Unknown/ABI-changing ones
  // remain unsupported; textual spelling is retained as evidence.
  const std::set<std::string> ignored = {"noalias", "nocapture", "readonly", "readnone",
    "nofree", "willreturn", "nosync", "speculatable", "nonnull", "align", "dereferenceable",
    "dereferenceable_or_null", "noinline", "alwaysinline", "optnone", "optsize", "minsize",
    "mustprogress", "uwtable", "ssp", "sspreq", "sspstrong", "memory", "captures"};
  const std::set<std::string> ignoredStrings = {"target-cpu", "target-features", "tune-cpu", "frame-pointer", "min-legal-vector-width",
    "no-trapping-math", "stack-protector-buffer-size"};
  for (unsigned slot : attributes.indexes()) for (Attribute attr : attributes.getAttributes(slot)) {
    std::string name = attr.isStringAttribute() ? attr.getKindAsString().str() :
                       Attribute::getNameFromAttrKind(attr.getKindAsEnum()).str();
    bool modeled = !attr.isStringAttribute() && (name == "noundef" || name == "nounwind" || name == "noreturn");
    bool ignore = attr.isStringAttribute() ? ignoredStrings.contains(name) : ignored.contains(name);
    supported &= modeled || ignore;
    attrs.push_back(json::Object{{"slot", slot == AttributeList::FunctionIndex ? -1 : int64_t(slot)},
      {"text", attr.getAsString()}, {"status", modeled ? "modeled" : ignore ? "conservatively-ignored" : "unsupported"},
      {"reason", modeled ? "llvm-contract-precondition" : ignore ? "not-used-for-precision" : "outside-abi-policy"}});
  }
  return json::Object{{"function_type", typeText(type)}, {"return_type", typeText(type->getReturnType())},
    {"parameter_types", std::move(parameters)}, {"calling_convention", convention},
    {"vararg", type->isVarArg()}, {"attributes", std::move(attrs)}, {"status", supported ? "supported" : "unsupported"},
    {"nounwind", attributes.hasFnAttr(Attribute::NoUnwind)}, {"noreturn", attributes.hasFnAttr(Attribute::NoReturn)}};
}
} // namespace

json::Object localMetadata(Module &module, const json::Object &origin, const json::Object &budgets) {
  const auto artifact = origin.getString("artifact_key")->str();
  auto ids = originalIdentities(module, artifact);
  const char *linkages[] = {"external", "available_externally", "linkonce", "linkonce_odr", "weak",
    "weak_odr", "appending", "internal", "private", "extern_weak", "common"};
  const char *visibilities[] = {"default", "hidden", "protected"};
  const char *selections[] = {"any", "exactmatch", "largest", "nodeduplicate", "samesize"};
  json::Array functions, calls;
  for (auto &function : module) {
    const auto fid = ids.lookup(&function);
    auto *comdat = function.getComdat();
    functions.push_back(json::Object{{"source", reference(artifact, nullptr, fid)},
      {"linkage", linkages[function.getLinkage()]}, {"visibility", visibilities[function.getVisibility()]},
      {"dso_local", function.isDSOLocal()}, {"declaration", function.isDeclaration()},
      {"interposable", function.isInterposable()}, {"exact_definition", function.hasExactDefinition()},
      {"comdat", comdat ? json::Value(comdat->getName().str()) : json::Value(nullptr)},
      {"selection", comdat ? json::Value(selections[comdat->getSelectionKind()]) : json::Value(nullptr)},
      {"interface", interface(function.getFunctionType(), function.getCallingConv(), function.getAttributes())},
      {"body_fingerprint", function.isDeclaration() ? json::Value(nullptr) : json::Value(bodyFingerprint(function, artifact))}});
    for (auto &block : function) {
      for (auto &instruction : block) {
        const auto iid = ids.lookup(&instruction);
        auto *call = dyn_cast<CallBase>(&instruction);
        if (!call) continue;
        auto *ordinary = dyn_cast<CallInst>(call);
        auto *target = call->getCalledFunction();
        json::Array bundles;
        for (unsigned i = 0; i < call->getNumOperandBundles(); ++i)
          bundles.push_back(call->getOperandBundleAt(i).getTagName().str());
        bool musttail = ordinary && ordinary->isMustTailCall();
        calls.push_back(json::Object{{"source", reference(artifact, fid, iid)},
          {"interface", interface(call->getFunctionType(), call->getCallingConv(), call->getAttributes(), musttail || !bundles.empty())},
          {"target", target ? json::Value(reference(artifact, nullptr, symbolId(*target, artifact))) : json::Value(nullptr)},
          {"tail", musttail ? "musttail" : ordinary && ordinary->isTailCall() ? "tail" : "none"},
          {"bundles", std::move(bundles)}});
      }
    }
  }
  // Metadata extraction is useful independently, but is not an effect solver.
  json::Object result{{"schema_version", 1}, {"kind", "LocalAnalysisFacts"}, {"analysis_version", "0.1.0"},
    {"policy_id", "scoped-effects-v1"}, {"origin", json::Object(origin)}, {"budgets", json::Object(budgets)},
    {"functions", std::move(functions)}, {"calls", std::move(calls)}, {"objects", json::Array{}},
    {"resolutions", json::Array{}}, {"diagnostics", json::Array{json::Object{{"code", "local_evaluation_pending"},
      {"detail", "Local LLVM evidence available; context values and effects have not been evaluated"},
      {"source", nullptr}, {"context_id", nullptr}}}}, {"status", "partial"}};
  localQueries(module, artifact, budgets, result);
  return result;
}
} // namespace moa
