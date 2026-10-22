#include "source_facts.h"
#include "source_protocol.h"
#include "provenance_protocol.h"

#include <clang/AST/ASTConsumer.h>
#include <clang/AST/ASTContext.h>
#include <clang/AST/Decl.h>
#include <clang/AST/DeclCXX.h>
#include <clang/AST/Expr.h>
#include <clang/AST/ExprCXX.h>
#include <clang/AST/Mangle.h>
#include <clang/AST/RecursiveASTVisitor.h>
#include <clang/AST/RecordLayout.h>
#include <clang/AST/Stmt.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/FrontendActions.h>
#include <clang/Index/USRGeneration.h>
#include <clang/Lex/Lexer.h>
#include <clang/Tooling/CompilationDatabase.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/ADT/SmallString.h>
#include <llvm/ADT/StringExtras.h>
#include <llvm/ADT/StringSwitch.h>
#include <llvm/IR/Function.h>
#include <llvm/IR/GlobalVariable.h>
#include <llvm/IR/Module.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/SHA256.h>
#include <llvm/Support/SourceMgr.h>

#include <algorithm>
#include <filesystem>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace clang;
using namespace clang::tooling;
using namespace llvm;

namespace moa {
namespace {

std::string requiredString(const json::Object &object, StringRef name) {
  auto value = object.getString(name);
  if (!value || value->empty())
    throw std::runtime_error(("source_request_invalid: missing " + name).str());
  return value->str();
}

int64_t requiredBudget(const json::Object &budgets, StringRef name) {
  auto value = budgets.getInteger(name);
  if (!value || *value < 1)
    throw std::runtime_error(("source_request_invalid: invalid budget " + name).str());
  return *value;
}

json::Object diag(StringRef code, StringRef detail, StringRef detailEn,
                  json::Value source = nullptr) {
  return json::Object{{"code", code.str()}, {"detail", detail.str()}, {"detail_en", detailEn.str()},
                      {"suggestion", nullptr}, {"suggestion_en", nullptr},
                      {"source", std::move(source)}};
}

json::Object provenanceDiag(StringRef code, StringRef detail, StringRef detailEn,
                            json::Value source = nullptr) {
  return json::Object{{"code", code.str()}, {"detail", detail.str()}, {"detail_en", detailEn.str()},
                      {"limitation", "有限对象来源结果不代表全程序别名、安全或 happens-before 证明"},
                      {"limitation_en", "Bounded object provenance is not a whole-program alias, safety, or happens-before proof"},
                      {"suggestion", nullptr}, {"suggestion_en", nullptr}, {"source", std::move(source)}};
}

std::string linkageName(const NamedDecl &decl) {
  static constexpr const char *names[] = {
      "unknown", "none", "internal", "unique_external", "none", "module", "external"};
  return names[static_cast<unsigned>(decl.getFormalLinkage())];
}

std::string storageName(const NamedDecl &decl) {
  StorageClass value = SC_None;
  if (auto *variable = dyn_cast<VarDecl>(&decl))
    value = variable->getStorageClass();
  else if (auto *function = dyn_cast<FunctionDecl>(&decl))
    value = function->getStorageClass();
  static constexpr const char *names[] = {
      "none", "extern", "static", "private_extern", "auto", "register"};
  return names[static_cast<unsigned>(value)];
}

std::string visibilityName(const NamedDecl &decl) {
  static constexpr const char *names[] = {"hidden", "protected", "default"};
  return names[static_cast<unsigned>(decl.getVisibility())];
}

struct Collector {
  std::string physical;
  size_t nodeLimit = 1;
  size_t relationLimit = 1;
  size_t pathLimit = 1;
  size_t pathSegmentsUsed = 0;
  size_t pathDepthLimit = 1;
  bool nodeExhausted = false;
  bool relationExhausted = false;
  bool pathExhausted = false;
  std::set<std::string> ids;
  std::map<std::string, size_t> ordinals;
  std::vector<json::Object> nodes;
  std::vector<json::Object> relations;
  std::vector<json::Object> paths;

  Collector(std::string physicalId, size_t nodesLimit, size_t relationsLimit,
            size_t pathsLimit = 1, size_t depthLimit = 1)
      : physical(std::move(physicalId)), nodeLimit(nodesLimit), relationLimit(relationsLimit),
        pathLimit(pathsLimit), pathDepthLimit(depthLimit) {}

  std::string locationId(const SourceManager &sm, SourceLocation location,
                         StringRef kind) const {
    SourceLocation expansion = sm.getExpansionLoc(location);
    PresumedLoc presumed = sm.getPresumedLoc(expansion);
    std::string anchor = presumed.isValid()
      ? std::string(presumed.getFilename()) + ":" + std::to_string(presumed.getLine()) + ":" + std::to_string(presumed.getColumn())
      : "invalid";
    return physical + ":" + kind.str() + ":" + anchor;
  }

  json::Object position(const SourceManager &sm, SourceLocation location) const {
    PresumedLoc presumed = sm.getPresumedLoc(location);
    if (!presumed.isValid())
      return json::Object{{"file", "<invalid>"}, {"line", 0}, {"column", 0}};
    return json::Object{{"file", std::string(presumed.getFilename())},
                        {"line", static_cast<int64_t>(presumed.getLine())},
                        {"column", static_cast<int64_t>(presumed.getColumn())}};
  }

  json::Array macroStack(const SourceManager &sm, SourceLocation location) const {
    json::Array result;
    SourceLocation current = location;
    while (current.isMacroID()) {
      SourceLocation spelling = sm.getSpellingLoc(current);
      SourceLocation caller = sm.getImmediateMacroCallerLoc(current);
      result.push_back(json::Object{{"spelling", position(sm, spelling)},
                                   {"expansion", position(sm, sm.getExpansionLoc(current))}});
      if (!caller.isValid() || caller == current) break;
      current = caller;
    }
    return result;
  }

  json::Object source(const SourceManager &sm, SourceRange range, size_t ordinal) const {
    SourceLocation spellingBegin = sm.getSpellingLoc(range.getBegin());
    SourceLocation spellingEnd = sm.getSpellingLoc(range.getEnd());
    SourceLocation expansionBegin = sm.getExpansionLoc(range.getBegin());
    SourceLocation expansionEnd = sm.getExpansionLoc(range.getEnd());
    return json::Object{{"spelling", position(sm, spellingBegin)},
                        {"spelling_end", position(sm, spellingEnd)},
                        {"expansion", position(sm, expansionBegin)},
                        {"expansion_end", position(sm, expansionEnd)},
                        {"ordinal", static_cast<int64_t>(ordinal)},
                        {"inlined_at", nullptr}};
  }

  json::Object abi(QualType type, ASTContext &context) const {
    if (type.isNull() || type->isIncompleteType() || type->isDependentType())
      return json::Object{{"complete", false}, {"size_bits", nullptr}, {"align_bits", nullptr}};
    TypeInfo info = context.getTypeInfo(type);
    return json::Object{{"complete", true},
                        {"size_bits", static_cast<int64_t>(info.Width)},
                        {"align_bits", static_cast<int64_t>(info.Align)}};
  }

  std::string addExpression(const Stmt &stmt, ASTContext &context, StringRef kind,
                            json::Array attributes = {}) {
    auto id = locationId(context.getSourceManager(), stmt.getBeginLoc(), kind);
    if (ids.count(id)) return id;
    if (nodes.size() >= nodeLimit) { nodeExhausted = true; return id; }
    ids.insert(id);
    auto ordinal = ordinals[id]++;
    std::string canonicalType = "statement";
    if (const auto *expression = dyn_cast<Expr>(&stmt))
      canonicalType = expression->getType().getCanonicalType().getAsString();
    nodes.push_back(json::Object{{"id", id}, {"kind", kind.str()}, {"name", ""}, {"qualified_name", ""},
                     {"usr", nullptr}, {"mangled_name", nullptr}, {"canonical_decl", id},
                     {"definition", false}, {"definition_kind", "declaration"},
                     {"linkage", "none"}, {"language_linkage", "none"}, {"storage", "none"},
                     {"visibility", "unknown"}, {"tls", false}, {"canonical_type", canonicalType},
                     {"abi", json::Object{}}, {"source", source(context.getSourceManager(), stmt.getSourceRange(), ordinal)},
                     {"macro_stack", macroStack(context.getSourceManager(), stmt.getBeginLoc())}, {"attributes", std::move(attributes)}});
    return id;
  }

  void addNodeAttributes(StringRef id, json::Array attributes) {
    for (auto &value : nodes) {
      auto *node = &value;
      if (node->getString("id") != id) continue;
      auto *existing = node->getArray("attributes");
      for (auto &attribute : attributes) existing->push_back(std::move(attribute));
      return;
    }
  }

  std::string addDeclaration(const NamedDecl &decl, ASTContext &context) {
    StringRef kind = isa<FunctionDecl>(decl) ? "function" : isa<FieldDecl>(decl) ? "field" :
                     isa<ParmVarDecl>(decl) ? "parameter" : "variable";
    const NamedDecl *canonical = cast<NamedDecl>(decl.getCanonicalDecl());
    auto canonicalId = locationId(context.getSourceManager(), canonical->getLocation(), kind);
    auto id = locationId(context.getSourceManager(), decl.getLocation(), kind);
    if (ids.count(id)) return id;
    if (canonical != &decl && !ids.count(canonicalId))
      addDeclaration(*canonical, context);
    if (ids.count(id)) return id;
    if (nodes.size() >= nodeLimit) { nodeExhausted = true; return id; }
    ids.insert(id);
    auto ordinal = ordinals[id]++;
    SmallString<256> usr;
    bool hasUsr = !index::generateUSRForDecl(&decl, usr);
    std::string mangled;
    if (isa<FunctionDecl>(decl) ||
        (isa<VarDecl>(decl) && cast<VarDecl>(decl).hasGlobalStorage())) {
      auto mangle = context.createMangleContext();
      if (mangle->shouldMangleDeclName(&decl)) {
        raw_string_ostream stream(mangled);
        if (auto *constructor = dyn_cast<CXXConstructorDecl>(&decl))
          mangle->mangleName(GlobalDecl(constructor, CXXCtorType::Ctor_Complete), stream);
        else if (auto *destructor = dyn_cast<CXXDestructorDecl>(&decl))
          mangle->mangleName(GlobalDecl(destructor, CXXDtorType::Dtor_Complete), stream);
        else
          mangle->mangleName(&decl, stream);
      } else {
        mangled = decl.getNameAsString();
      }
    }
    bool definition = false, tls = false;
    std::string definitionKind = "declaration";
    QualType type;
    if (auto *function = dyn_cast<FunctionDecl>(&decl)) {
      definition = function->isThisDeclarationADefinition();
      type = function->getType();
      if (function->isInlined()) definitionKind = "inline";
      else if (function->getTemplatedKind() != FunctionDecl::TK_NonTemplate) definitionKind = "template";
      else if (function->hasAttr<WeakAttr>()) definitionKind = "weak";
      else if (definition) definitionKind = "strong";
    } else if (auto *variable = dyn_cast<VarDecl>(&decl)) {
      definition = variable->isThisDeclarationADefinition() != VarDecl::DeclarationOnly;
      type = variable->getType(); tls = variable->getTLSKind() != VarDecl::TLS_None;
      if (variable->isThisDeclarationADefinition() == VarDecl::TentativeDefinition)
        definitionKind = "tentative";
      else if (variable->hasAttr<WeakAttr>()) definitionKind = "weak";
      else if (definition) definitionKind = "strong";
    } else if (auto *field = dyn_cast<FieldDecl>(&decl)) {
      definition = true; definitionKind = "strong"; type = field->getType();
    }
    json::Array attributes;
    if (decl.isInAnonymousNamespace()) attributes.push_back("anonymous-namespace");
    for (const Attr *attribute : decl.attrs())
      attributes.push_back(attribute->getSpelling());
    if (definition) {
      bool invalid = false;
      StringRef text = Lexer::getSourceText(CharSourceRange::getTokenRange(decl.getSourceRange()),
                                            context.getSourceManager(), context.getLangOpts(), &invalid);
      if (!invalid && !text.empty())
        attributes.push_back("definition-sha256:" + toHex(SHA256::hash(arrayRefFromStringRef(text)), true));
    }
    std::string languageLinkage = "none";
    if (decl.getDeclContext()->isFunctionOrMethod() || decl.hasExternalFormalLinkage())
      languageLinkage = context.getLangOpts().CPlusPlus ? "c++" : "c";
    nodes.push_back(json::Object{{"id", id}, {"kind", kind.str()}, {"name", decl.getNameAsString()},
                     {"qualified_name", decl.getQualifiedNameAsString()},
                     {"usr", hasUsr ? json::Value(usr.str().str()) : json::Value(nullptr)},
                     {"mangled_name", mangled.empty() ? json::Value(nullptr) : json::Value(mangled)},
                     {"canonical_decl", canonicalId},
                     {"definition", definition}, {"definition_kind", definitionKind},
                     {"linkage", linkageName(decl)}, {"language_linkage", languageLinkage},
                     {"storage", storageName(decl)}, {"visibility", visibilityName(decl)},
                     {"tls", tls}, {"canonical_type", type.isNull() ? "unknown" : type.getCanonicalType().getAsString()},
                     {"abi", abi(type, context)}, {"source", source(context.getSourceManager(), decl.getSourceRange(), ordinal)},
                     {"macro_stack", macroStack(context.getSourceManager(), decl.getLocation())}, {"attributes", std::move(attributes)}});
    return id;
  }

  void addRelation(StringRef kind, StringRef from, std::optional<std::string> to,
                   const Stmt &stmt, ASTContext &context, StringRef status = "exact",
                   std::optional<StringRef> reason = std::nullopt) {
    if (!ids.count(from.str()) || (to && !ids.count(*to))) return;
    if (relations.size() >= relationLimit) { relationExhausted = true; return; }
    std::string id = physical + ":relation:" + std::to_string(relations.size()) + ":" + kind.str();
    relations.push_back(json::Object{{"id", id}, {"kind", kind.str()}, {"from", from.str()},
                         {"to", to ? json::Value(*to) : json::Value(nullptr)},
                         {"source", source(context.getSourceManager(), stmt.getSourceRange(), relations.size())},
                         {"status", status.str()},
                         {"reason", reason ? json::Value(reason->str()) : json::Value(nullptr)}});
  }

  void addDeclRelation(StringRef kind, StringRef from, std::optional<std::string> to,
                       const NamedDecl &decl, ASTContext &context, StringRef status = "exact",
                       std::optional<StringRef> reason = std::nullopt) {
    if (!ids.count(from.str()) || (to && !ids.count(*to))) return;
    if (relations.size() >= relationLimit) { relationExhausted = true; return; }
    std::string id = physical + ":relation:" + std::to_string(relations.size()) + ":" + kind.str();
    relations.push_back(json::Object{{"id", id}, {"kind", kind.str()}, {"from", from.str()},
                         {"to", to ? json::Value(*to) : json::Value(nullptr)},
                         {"source", source(context.getSourceManager(), decl.getSourceRange(), relations.size())},
                         {"status", status.str()},
                         {"reason", reason ? json::Value(reason->str()) : json::Value(nullptr)}});
  }
};

class SourceVisitor : public RecursiveASTVisitor<SourceVisitor> {
  ASTContext &context;
  Collector &collector;

  static bool isStdThread(const CXXRecordDecl *record) {
    if (!record) return false;
    auto name = record->getCanonicalDecl()->getQualifiedNameAsString();
    return StringSwitch<bool>(name)
        .Cases("std::thread", "std::__1::thread", true).Default(false);
  }

  static bool isStdJthread(const CXXRecordDecl *record) {
    if (!record) return false;
    auto name = record->getCanonicalDecl()->getQualifiedNameAsString();
    return StringSwitch<bool>(name)
        .Cases("std::jthread", "std::__1::jthread", true).Default(false);
  }

  static bool isStdAsync(const FunctionDecl *function) {
    if (!function) return false;
    auto name = function->getCanonicalDecl()->getQualifiedNameAsString();
    return StringSwitch<bool>(name)
        .Cases("std::async", "std::__1::async", true).Default(false);
  }

  static bool isBoostThread(const CXXRecordDecl *record) {
    return record->getCanonicalDecl()->getQualifiedNameAsString() == "boost::thread";
  }

  static std::string cAtomicRelation(StringRef operation) {
    if (operation.contains("signal_fence")) return "atomic-c-signal-fence";
    if (operation.contains("thread_fence")) return "atomic-c-thread-fence";
    if (operation.contains("compare_exchange")) return "atomic-c-cas";
    if (operation.contains("fetch_") || operation.contains("exchange")) return "atomic-c-rmw";
    if (operation.contains("store") || operation.contains("init")) return "atomic-c-store";
    if (operation.contains("load")) return "atomic-c-load";
    return "atomic";
  }

  std::optional<std::string> atomicOrderName(const Expr &orderExpression) const {
    const Expr *expression = orderExpression.IgnoreParenImpCasts();
    if (auto *reference = dyn_cast<DeclRefExpr>(expression)) {
      if (auto *constant = dyn_cast<EnumConstantDecl>(reference->getDecl())) {
        auto name = constant->getNameAsString();
        if (StringRef(name).starts_with("memory_order_"))
          return StringRef(name).drop_front(StringRef("memory_order_").size()).str();
      }
    }
    Expr::EvalResult evaluated;
    if (expression->EvaluateAsInt(evaluated, context)) {
      uint64_t value = evaluated.Val.getInt().getZExtValue();
      switch (value) {
        case 0: return "relaxed";
        case 1: return "consume";
        case 2: return "acquire";
        case 3: return "release";
        case 4: return "acq_rel";
        case 5: return "seq_cst";
        default: break;
      }
    }
    return std::nullopt;
  }

  std::optional<std::string> cppAtomicRelation(const FunctionDecl &callee) const {
    auto *canonical = callee.getCanonicalDecl();
    auto qualified = canonical->getQualifiedNameAsString();
    SourceLocation location = context.getSourceManager().getSpellingLoc(canonical->getLocation());
    if (!context.getSourceManager().isInSystemHeader(location)) return std::nullopt;
    bool standard = StringRef(qualified).starts_with("std::") ||
                    StringRef(qualified).starts_with("std::__1::");
    if (!standard) return std::nullopt;
    // getName() asserts for constructors, conversion functions and operators;
    // source traversal visits all of them before deciding whether a call is an
    // atomic operation, so keep the discriminator total over NamedDecl kinds.
    std::string nameStorage = canonical->getNameAsString();
    StringRef name(nameStorage);
    if (name == "atomic_signal_fence") return "atomic-cpp-signal-fence";
    if (name == "atomic_thread_fence") return "atomic-cpp-thread-fence";
    bool atomicOwner = qualified.find("atomic") != std::string::npos;
    if (!atomicOwner) return std::nullopt;
    if (name.starts_with("compare_exchange")) return "atomic-cpp-cas";
    if (name == "exchange" || name.starts_with("fetch_") || name.starts_with("atomic_fetch_"))
      return "atomic-cpp-rmw";
    if (name == "store" || name.starts_with("atomic_store")) return "atomic-cpp-store";
    if (name == "load" || name.starts_with("atomic_load")) return "atomic-cpp-load";
    return std::nullopt;
  }

  static bool isStdMutex(const CXXRecordDecl *record) {
    if (!record) return false;
    auto name = record->getCanonicalDecl()->getQualifiedNameAsString();
    return StringSwitch<bool>(name)
        .Cases("std::mutex", "std::__1::mutex", true).Default(false);
  }

  static StringRef raiiOwnerKind(const CXXRecordDecl *record) {
    if (!record) return {};
    auto name = record->getCanonicalDecl()->getQualifiedNameAsString();
    if (StringRef(name).contains("lock_guard")) return "lock-guard";
    if (StringRef(name).contains("unique_lock")) return "unique-lock";
    if (StringRef(name).contains("scoped_lock")) return "scoped-lock";
    return {};
  }

  static StringRef lockTag(Expr *expr) {
    expr = expr ? expr->IgnoreParenImpCasts() : nullptr;
    const CXXRecordDecl *record = expr && !expr->getType().isNull()
                                    ? expr->getType()->getAsCXXRecordDecl() : nullptr;
    if (!record) return {};
    auto name = record->getCanonicalDecl()->getQualifiedNameAsString();
    if (StringRef(name).contains("defer_lock_t")) return "defer_lock";
    if (StringRef(name).contains("adopt_lock_t")) return "adopt_lock";
    if (StringRef(name).contains("try_to_lock_t")) return "try_to_lock";
    return {};
  }

  static Expr *unwrap(Expr *expr) {
    return expr ? expr->IgnoreParenImpCasts() : nullptr;
  }

  const NamedDecl *referencedObject(Expr *expr) const {
    expr = unwrap(expr);
    if (auto *reference = dyn_cast_or_null<DeclRefExpr>(expr))
      return dyn_cast<NamedDecl>(reference->getDecl());
    if (auto *member = dyn_cast_or_null<MemberExpr>(expr))
      return dyn_cast<NamedDecl>(member->getMemberDecl());
    if (auto *unary = dyn_cast_or_null<UnaryOperator>(expr);
        unary && (unary->getOpcode() == UO_AddrOf || unary->getOpcode() == UO_Deref))
      return referencedObject(unary->getSubExpr());
    if (auto *call = dyn_cast_or_null<CallExpr>(expr); call && call->getNumArgs() == 1) {
      const FunctionDecl *callee = call->getDirectCallee();
      if (callee && (callee->getQualifiedNameAsString() == "std::move" ||
                     callee->getQualifiedNameAsString() == "std::__1::move"))
        return referencedObject(call->getArg(0));
    }
    return nullptr;
  }

  const FunctionDecl *callableTarget(Expr *expr, StringRef &reason) const {
    expr = unwrap(expr);
    if (auto *unary = dyn_cast_or_null<UnaryOperator>(expr);
        unary && unary->getOpcode() == UO_AddrOf)
      expr = unwrap(unary->getSubExpr());
    if (auto *reference = dyn_cast_or_null<DeclRefExpr>(expr)) {
      if (auto *function = dyn_cast<FunctionDecl>(reference->getDecl())) return function;
    }
    if (auto *lambda = dyn_cast_or_null<LambdaExpr>(expr)) return lambda->getCallOperator();
    const CXXRecordDecl *record = expr && !expr->getType().isNull()
                                    ? expr->getType()->getAsCXXRecordDecl() : nullptr;
    const CXXMethodDecl *target = nullptr;
    if (record) {
      for (const CXXMethodDecl *method : record->methods()) {
        if (method->getOverloadedOperator() != OO_Call || method->isVirtual()) continue;
        if (target) { reason = "ambiguous-functor-call-operator"; return nullptr; }
        target = method;
      }
      if (target) return target;
    }
    reason = "unsupported-cpp-thread-callable";
    return nullptr;
  }

  bool acceptsStopToken(const FunctionDecl *function) const {
    if (!function || function->getNumParams() == 0) return false;
    std::string type = function->getParamDecl(0)->getType().getCanonicalType().getAsString();
    return StringRef(type).contains("stop_token");
  }

  json::Array threadEntryAttributes(const CXXConstructExpr &expr, StringRef family,
                                    const FunctionDecl *callable = nullptr) const {
    const CXXConstructorDecl *constructor = expr.getConstructor();
    const CXXRecordDecl *record = constructor->getParent()->getCanonicalDecl();
    QualType type = expr.getType();
    std::string spelled = type.getAsString();
    std::string canonical = type.getCanonicalType().getAsString();
    std::string kind = constructor->isDefaultConstructor() ? "default" :
                       constructor->isMoveConstructor() ? "move-construction" :
                       constructor->isCopyConstructor() ? "copy-or-deleted" :
                       expr.getNumArgs() ? "callable-construction" : "other";
    std::string recordName = record->getQualifiedNameAsString();
    std::string constructorName = constructor->getQualifiedNameAsString();
    std::string origin = "unknown";
    const SourceManager &manager = context.getSourceManager();
    SourceLocation location = manager.getSpellingLoc(record->getLocation());
    origin = manager.getFilename(location).str();
    bool system = manager.isInSystemHeader(location);
    std::string aliases = spelled == canonical ? canonical : spelled + "|" + canonical;
    json::Array result;
    for (const std::string &value : {
           "thread-entry:family=" + family.str(),
           "thread-entry:spelled-type=" + spelled,
           "thread-entry:canonical-type=" + canonical,
           "thread-entry:canonical-record=" + recordName,
           "thread-entry:constructor-decl=" + constructorName,
           "thread-entry:constructor-kind=" + kind,
           "thread-entry:alias-chain=" + aliases,
           "thread-entry:declaration-origin=" + origin,
           std::string("thread-entry:system-boundary=") + (system ? "true" : "false"),
           std::string("thread-entry:stop-token-injected=") + (acceptsStopToken(callable) ? "true" : "false")})
      result.push_back(value);
    return result;
  }

  std::string asyncPolicy(Expr *expression, size_t depth = 0) const {
    if (depth > 8) return "unknown";
    expression = expression->IgnoreParenImpCasts();
    if (auto *reference = dyn_cast<DeclRefExpr>(expression)) {
      if (auto *constant = dyn_cast<EnumConstantDecl>(reference->getDecl())) {
        if (constant->getName() == "async") return "async";
        if (constant->getName() == "deferred") return "deferred";
      }
    }
    if (auto *call = dyn_cast<CallExpr>(expression); call && call->getNumArgs() == 2) {
      const FunctionDecl *callee = call->getDirectCallee();
      if (callee && callee->getOverloadedOperator() == OO_Pipe) {
        auto left = asyncPolicy(call->getArg(0), depth + 1);
        auto right = asyncPolicy(call->getArg(1), depth + 1);
        if ((left == "async" && right == "deferred") ||
            (left == "deferred" && right == "async") || left == "both" || right == "both")
          return "both";
      }
    }
    return "unknown";
  }

  json::Array asyncEntryAttributes(const CallExpr &expr, const FunctionDecl &function,
                                   StringRef policy) const {
    QualType type = expr.getType();
    std::string spelled = type.getAsString();
    std::string canonical = type.getCanonicalType().getAsString();
    const FunctionDecl *declaration = function.getCanonicalDecl();
    const SourceManager &manager = context.getSourceManager();
    SourceLocation location = manager.getSpellingLoc(declaration->getLocation());
    std::string origin = manager.getFilename(location).str();
    bool system = manager.isInSystemHeader(location);
    std::string aliases = spelled == canonical ? canonical : spelled + "|" + canonical;
    json::Array result;
    for (const std::string &value : {
           std::string("thread-entry:family=std-async"),
           "thread-entry:spelled-type=" + spelled,
           "thread-entry:canonical-type=" + canonical,
           "thread-entry:canonical-record=" + declaration->getQualifiedNameAsString(),
           "thread-entry:constructor-decl=" + declaration->getQualifiedNameAsString(),
           std::string("thread-entry:constructor-kind=async-call"),
           "thread-entry:alias-chain=" + aliases,
           "thread-entry:declaration-origin=" + origin,
           std::string("thread-entry:system-boundary=") + (system ? "true" : "false"),
           "thread-entry:launch-policy=" + policy.str()})
      result.push_back(value);
    return result;
  }

  json::Array factoryEntryAttributes(const CallExpr &expr, const FunctionDecl &function,
                                     StringRef family, const CXXRecordDecl &record) const {
    QualType type = expr.getType();
    std::string spelled = type.getAsString();
    std::string canonical = type.getCanonicalType().getAsString();
    const SourceManager &manager = context.getSourceManager();
    SourceLocation location = manager.getSpellingLoc(function.getCanonicalDecl()->getLocation());
    std::string origin = manager.getFilename(location).str();
    json::Array result;
    for (const std::string &value : {
           "thread-entry:family=" + family.str(),
           "thread-entry:spelled-type=" + spelled,
           "thread-entry:canonical-type=" + canonical,
           "thread-entry:canonical-record=" + record.getCanonicalDecl()->getQualifiedNameAsString(),
           "thread-entry:constructor-decl=" + function.getCanonicalDecl()->getQualifiedNameAsString(),
           std::string("thread-entry:constructor-kind=factory-return"),
           "thread-entry:alias-chain=" + (spelled == canonical ? canonical : spelled + "|" + canonical),
           "thread-entry:declaration-origin=" + origin,
           std::string("thread-entry:system-boundary=") +
               (manager.isInSystemHeader(location) ? "true" : "false")})
      result.push_back(value);
    return result;
  }

  struct SourcePath {
    json::Object base;
    std::vector<json::Object> segments;
    std::string status = "exact";
    std::string reason;
    std::set<std::string> evidence;
  };

  bool pathFor(Expr *expression, SourcePath &result, size_t depth = 0) {
    if (!expression || depth >= collector.pathDepthLimit) {
      result.status = "unknown"; result.reason = "path-depth-budget-exhausted";
      collector.pathExhausted = true; return false;
    }
    expression = expression->IgnoreParens();
    if (auto *implicit = dyn_cast<ImplicitCastExpr>(expression))
      return pathFor(implicit->getSubExpr(), result, depth + 1);
    if (auto *member = dyn_cast<MemberExpr>(expression)) {
      if (!pathFor(member->getBase(), result, depth + 1) && result.status == "unknown") return false;
      auto *field = dyn_cast<FieldDecl>(member->getMemberDecl());
      json::Value index = nullptr, offset = nullptr, size = nullptr, alignment = nullptr, overlap = nullptr;
      std::string fieldId = collector.addDeclaration(*member->getMemberDecl(), context);
      std::string recordType;
      if (field) {
        const RecordDecl *record = field->getParent();
        recordType = context.getRecordType(record).getCanonicalType().getAsString();
        if (record->isUnion())
          overlap = collector.locationId(context.getSourceManager(), record->getLocation(), "union-overlap");
        bool flexible = field->getType()->isIncompleteArrayType();
        if (record->isCompleteDefinition() && !field->isBitField() && !flexible) {
          unsigned fieldIndex = field->getFieldIndex();
          const ASTRecordLayout &layout = context.getASTRecordLayout(record);
          index = static_cast<int64_t>(fieldIndex);
          offset = static_cast<int64_t>(layout.getFieldOffset(fieldIndex));
          size = static_cast<int64_t>(context.getTypeSize(field->getType()));
          alignment = static_cast<int64_t>(context.getTypeAlign(field->getType()));
          result.evidence.insert("ast-record-layout");
        } else {
          result.status = "candidate";
          result.reason = field->isBitField() ? "bit-field-layout" : flexible ? "flexible-array-layout" : "incomplete-record-layout";
        }
        if (record->isAnonymousStructOrUnion()) {
          result.status = "candidate"; result.reason = "anonymous-record-path";
        }
      } else {
        result.status = "unknown"; result.reason = "non-field-member";
      }
      result.segments.push_back(json::Object{
          {"kind", "field"}, {"field_id", fieldId}, {"record_type", recordType.empty() ? json::Value(nullptr) : json::Value(recordType)},
          {"access", member->isArrow() ? "arrow" : "dot"}, {"field_index", std::move(index)},
          {"offset_bits", std::move(offset)}, {"size_bits", std::move(size)},
          {"align_bits", std::move(alignment)}, {"union_group", std::move(overlap)}});
      result.evidence.insert("member-expr-base");
      return result.status != "unknown";
    }
    if (auto *reference = dyn_cast<DeclRefExpr>(expression)) {
      auto *named = dyn_cast<NamedDecl>(reference->getDecl());
      if (!named) { result.status = "unknown"; result.reason = "unnamed-declaration"; return false; }
      auto id = collector.addDeclaration(*named, context);
      StringRef kind = isa<ParmVarDecl>(named) ? "parameter" : "declaration";
      result.base = json::Object{{"kind", kind.str()}, {"declaration_id", id},
                                 {"name", named->getNameAsString()},
                                 {"canonical_type", expression->getType().getCanonicalType().getAsString()}};
      result.evidence.insert("canonical-declaration"); return true;
    }
    if (isa<CXXThisExpr>(expression)) {
      result.base = json::Object{{"kind", "receiver"}, {"declaration_id", collector.physical + ":this:" + expression->getType().getCanonicalType().getAsString()},
                                 {"name", "this"},
                                 {"canonical_type", expression->getType().getCanonicalType().getAsString()}};
      result.evidence.insert("cxx-this-expression"); return true;
    }
    if (auto *unary = dyn_cast<UnaryOperator>(expression);
        unary && (unary->getOpcode() == UO_AddrOf || unary->getOpcode() == UO_Deref)) {
      bool ok = pathFor(unary->getSubExpr(), result, depth + 1);
      if (unary->getOpcode() == UO_Deref)
        result.segments.push_back(json::Object{{"kind", "deref"}, {"field_id", nullptr}, {"record_type", nullptr},
          {"access", "deref"}, {"field_index", nullptr}, {"offset_bits", nullptr}, {"size_bits", nullptr},
          {"align_bits", nullptr}, {"union_group", nullptr}});
      result.evidence.insert(unary->getOpcode() == UO_Deref ? "explicit-dereference" : "address-of");
      return ok;
    }
    if (auto *cast = dyn_cast<CastExpr>(expression)) {
      bool ok = pathFor(cast->getSubExpr(), result, depth + 1);
      auto kind = cast->getCastKind();
      bool lossy = kind == CK_PointerToIntegral || kind == CK_IntegralToPointer || kind == CK_AddressSpaceConversion;
      result.segments.push_back(json::Object{{"kind", "cast"}, {"field_id", nullptr},
        {"record_type", cast->getType().getCanonicalType().getAsString()}, {"access", "cast"},
        {"field_index", nullptr}, {"offset_bits", nullptr}, {"size_bits", nullptr},
        {"align_bits", nullptr}, {"union_group", nullptr}});
      result.evidence.insert("explicit-cast");
      if (lossy) { result.status = "unknown"; result.reason = "lossy-or-address-space-cast"; }
      return ok && !lossy;
    }
    if (auto *subscript = dyn_cast<ArraySubscriptExpr>(expression)) {
      bool ok = pathFor(subscript->getBase(), result, depth + 1);
      Expr::EvalResult evaluated;
      json::Value index = nullptr;
      if (subscript->getIdx()->EvaluateAsInt(evaluated, context))
        index = evaluated.Val.getInt().getSExtValue();
      else { result.status = "candidate"; result.reason = "dynamic-array-index"; }
      result.segments.push_back(json::Object{{"kind", "array-index"}, {"field_id", nullptr},
        {"record_type", nullptr}, {"access", "index"}, {"field_index", std::move(index)},
        {"offset_bits", nullptr}, {"size_bits", nullptr}, {"align_bits", nullptr}, {"union_group", nullptr}});
      result.evidence.insert("array-subscript"); return ok;
    }
    if (isa<ConditionalOperator>(expression) || isa<BinaryConditionalOperator>(expression)) {
      result.base = json::Object{{"kind", "conditional"}, {"declaration_id", nullptr},
                                 {"name", nullptr},
                                 {"canonical_type", expression->getType().getCanonicalType().getAsString()}};
      result.status = "candidate"; result.reason = "conditional-candidates";
      result.evidence.insert("conditional-expression"); return true;
    }
    result.base = json::Object{{"kind", "unknown"}, {"declaration_id", nullptr},
                               {"name", nullptr},
                               {"canonical_type", expression->getType().getCanonicalType().getAsString()}};
    result.status = "unknown"; result.reason = "unsupported-source-expression"; return false;
  }

  void emitPath(Expr *expression, StringRef role) {
    if (!expression || !eligible(expression->getBeginLoc())) return;
    std::string id = collector.locationId(context.getSourceManager(), expression->getBeginLoc(),
                                          ("object-path-" + role).str());
    if (std::any_of(collector.paths.begin(), collector.paths.end(), [&](const auto &item) {
          return item.getString("id") == id;
        })) return;
    SourcePath path;
    pathFor(expression, path);
    if (path.segments.size() > collector.pathLimit -
          std::min(collector.pathLimit, collector.pathSegmentsUsed)) {
      size_t remaining = collector.pathLimit -
                         std::min(collector.pathLimit, collector.pathSegmentsUsed);
      path.segments.resize(remaining);
      collector.pathSegmentsUsed += remaining;
      path.status = "unknown";
      path.reason = "path-segment-budget-exhausted";
      collector.pathExhausted = true;
    } else {
      collector.pathSegmentsUsed += path.segments.size();
    }
    json::Array segments, evidence;
    for (auto &segment : path.segments) segments.push_back(std::move(segment));
    for (const auto &item : path.evidence) evidence.push_back(item);
    auto source = collector.source(context.getSourceManager(), expression->getSourceRange(), collector.paths.size());
    collector.paths.push_back(json::Object{
      {"id", id}, {"expression_id", collector.addExpression(*expression, context, "object-path-expression")},
      {"role", role.str()}, {"base", std::move(path.base)}, {"segments", std::move(segments)},
      {"status", path.status}, {"reason", path.reason.empty() ? json::Value(nullptr) : json::Value(path.reason)},
      {"source", std::move(source)}, {"evidence", std::move(evidence)}});
  }

public:
  SourceVisitor(ASTContext &context, Collector &collector) : context(context), collector(collector) {}
  bool eligible(SourceLocation location) const {
    const auto &manager = context.getSourceManager();
    return location.isValid() && !manager.isInSystemHeader(manager.getExpansionLoc(location));
  }
  bool VisitNamedDecl(NamedDecl *decl) {
    if (!eligible(decl->getLocation()) || decl->isImplicit()) return true;
    if (isa<FunctionDecl, VarDecl, FieldDecl, ParmVarDecl>(decl)) collector.addDeclaration(*decl, context);
    return true;
  }
  bool VisitFieldDecl(FieldDecl *decl) {
    if (!eligible(decl->getLocation()) || !context.getLangOpts().CPlusPlus) return true;
    auto target = collector.addDeclaration(*decl, context);
    if (isStdMutex(decl->getType()->getAsCXXRecordDecl()))
      collector.addDeclRelation("cpp-raii-mutex-object", target, target, *decl, context,
                                "candidate", "plain-mutex-field-requires-base-provenance");
    return true;
  }
  bool VisitVarDecl(VarDecl *decl) {
    if (!eligible(decl->getLocation()) || decl->isImplicit()) return true;
    auto target = collector.addDeclaration(*decl, context);
    if (context.getLangOpts().CPlusPlus && isStdMutex(decl->getType()->getAsCXXRecordDecl()))
      collector.addDeclRelation("cpp-raii-mutex-object", target, target, *decl, context,
                                "candidate", "plain-mutex-requires-profile-and-ir-binding");
    StringRef ownerKind = context.getLangOpts().CPlusPlus
                            ? raiiOwnerKind(decl->getType()->getAsCXXRecordDecl()) : StringRef();
    if (!decl->hasInit()) {
      if (!ownerKind.empty()) {
        std::string reason = ("uninitialized-" + ownerKind).str();
        collector.addDeclRelation("cpp-raii-owner-object", target, target, *decl, context,
                                  "unknown", reason);
      }
      return true;
    }
    auto source = collector.addExpression(*decl->getInit(), context, "initializer-expression");
    collector.addRelation("initialize", source, target, *decl->getInit(), context);
    if (!ownerKind.empty()) {
      std::string reason = (ownerKind + "-requires-profile-cfg-and-ir-binding").str();
      if (auto *construct = dyn_cast<CXXConstructExpr>(unwrap(decl->getInit()))) {
        for (Expr *argument : construct->arguments()) {
          StringRef tag = lockTag(argument);
          if (tag == "defer_lock") reason += "-defer_lock";
          if (tag == "adopt_lock" || tag == "try_to_lock")
            collector.addRelation("cpp-raii-owner-unsupported", source, target,
                                  *decl->getInit(), context, "unknown", tag);
        }
      }
      collector.addRelation("cpp-raii-owner-object", source, target, *decl->getInit(), context,
                            "candidate", reason);
      collector.addRelation("cpp-raii-owner-construct", source, target, *decl->getInit(), context,
                            "candidate", reason);
      if (auto *construct = dyn_cast<CXXConstructExpr>(unwrap(decl->getInit()))) {
        if (construct->getConstructor()->isMoveConstructor() && construct->getNumArgs()) {
          std::optional<std::string> moved;
          if (auto *owner = referencedObject(construct->getArg(0)))
            moved = collector.addDeclaration(*owner, context);
          collector.addRelation("cpp-raii-owner-move", source, moved, *decl->getInit(), context,
                                moved ? "candidate" : "unknown",
                                moved ? "move-source-requires-owner-token-binding"
                                      : "unresolved-move-source");
        } else {
          for (Expr *argument : construct->arguments()) {
            if (auto *mutex = referencedObject(argument)) {
              auto mutexId = collector.addDeclaration(*mutex, context);
              collector.addRelation("cpp-raii-mutex-argument", source, mutexId,
                                    *decl->getInit(), context, "candidate",
                                    "requires-object-provenance-and-ir-binding");
            }
          }
        }
      }
      std::string cleanupReason = ("implicit-cleanup-" + ownerKind).str();
      collector.addRelation("cpp-raii-owner-destruct", target, target, *decl->getInit(), context,
                            "candidate", cleanupReason);
    }
    const CXXRecordDecl *threadRecord = context.getLangOpts().CPlusPlus
                                          ? decl->getType()->getAsCXXRecordDecl() : nullptr;
    if (isStdThread(threadRecord) || isStdJthread(threadRecord)) {
      bool jthread = isStdJthread(threadRecord);
      std::string spelled = decl->getType().getAsString();
      std::string canonical = decl->getType().getCanonicalType().getAsString();
      json::Array attributes;
      attributes.push_back("thread-entry:declared-spelled-type=" + spelled);
      attributes.push_back("thread-entry:declared-canonical-type=" + canonical);
      attributes.push_back("thread-entry:declared-alias-chain=" +
                           (spelled == canonical ? canonical : spelled + "|" + canonical));
      collector.addNodeAttributes(target, std::move(attributes));
      collector.addRelation(jthread ? "cpp-jthread-object" : "cpp-thread-object",
                            source, target, *decl->getInit(), context,
                            "candidate", "requires-profile-and-ir-binding");
      collector.addRelation(jthread ? "cpp-jthread-destruct" : "cpp-thread-destruct",
                            target, std::nullopt, *decl->getInit(), context,
                            "candidate", "implicit-scope-exit");
    }
    return true;
  }

  bool VisitCXXConstructExpr(CXXConstructExpr *expr) {
    if (!eligible(expr->getBeginLoc())) return true;
    const CXXRecordDecl *record = expr->getConstructor()->getParent();
    bool standardThread = isStdThread(record), standardJthread = isStdJthread(record);
    if (!standardThread && !standardJthread) {
      if (isBoostThread(record)) {
        auto from = collector.addExpression(*expr, context, "unsupported-thread-construction",
                                            threadEntryAttributes(*expr, "framework"));
        collector.addRelation("unsupported-thread-api", from, std::nullopt, *expr, context,
                              "unknown", "unregistered-boost-thread");
      }
      return true;
    }
    StringRef family = standardJthread ? "std-jthread" : "std-thread";
    StringRef callableReason;
    const FunctionDecl *callable = nullptr;
    if (!expr->getConstructor()->isMoveConstructor() && expr->getNumArgs())
      callable = callableTarget(expr->getArg(0), callableReason);
    auto from = collector.addExpression(*expr, context,
                                        standardJthread ? "cpp-jthread-construction" : "cpp-thread-construction",
                                        threadEntryAttributes(*expr, family, callable));
    if (expr->getConstructor()->isMoveConstructor()) {
      std::optional<std::string> target;
      if (expr->getNumArgs())
        if (auto *object = referencedObject(expr->getArg(0)))
          target = collector.addDeclaration(*object, context);
      collector.addRelation(standardJthread ? "cpp-jthread-move-construct" : "cpp-thread-move-construct",
                            from, target, *expr, context,
                            target ? "candidate" : "unknown",
                            target ? std::optional<StringRef>("requires-ir-handle-transfer")
                                   : std::optional<StringRef>("unresolved-move-source"));
      return true;
    }
    collector.addRelation(standardJthread ? "cpp-jthread-construct" : "cpp-thread-construct",
                          from, std::nullopt, *expr, context,
                          "candidate", "requires-profile-and-ir-binding");
    if (!expr->getNumArgs()) return true;
    if (callable) {
      auto target = collector.addDeclaration(*callable, context);
      collector.addRelation(standardJthread ? "cpp-jthread-callback" : "cpp-thread-callback",
                            from, target, *expr, context,
                            "candidate", "requires-cross-tu-definition-and-ir-binding");
    } else {
      collector.addRelation(standardJthread ? "cpp-jthread-callback" : "cpp-thread-callback",
                            from, std::nullopt, *expr, context,
                            "unknown", callableReason);
    }
    for (unsigned index = 1; index < expr->getNumArgs(); ++index) {
      std::optional<std::string> target;
      if (auto *argument = referencedObject(expr->getArg(index)))
        target = collector.addDeclaration(*argument, context);
      collector.addRelation(standardJthread ? "cpp-jthread-argument" : "cpp-thread-argument",
                            from, target, *expr, context,
                            target ? "candidate" : "unknown",
                            target ? std::optional<StringRef>("requires-ir-argument-binding")
                                   : std::optional<StringRef>("unsupported-thread-argument"));
    }
    return true;
  }

  bool VisitCXXMemberCallExpr(CXXMemberCallExpr *expr) {
    if (!eligible(expr->getBeginLoc())) return true;
    auto *method = expr->getMethodDecl();
    if (!method) return true;
    StringRef ownerKind = raiiOwnerKind(method->getParent());
    if (!ownerKind.empty()) {
      StringRef kind;
      if (method->getName() == "lock") kind = "cpp-raii-owner-lock";
      else if (method->getName() == "unlock") kind = "cpp-raii-owner-unlock";
      else if (method->getName() == "owns_lock") kind = "cpp-raii-owner-owns-lock";
      else if (method->getName() == "release") kind = "cpp-raii-owner-unsupported";
      else if (method->getName() == "swap") kind = "cpp-raii-owner-unsupported";
      if (!kind.empty()) {
        auto from = collector.addExpression(*expr, context, "cpp-raii-member-call");
        std::optional<std::string> object;
        if (auto *target = referencedObject(expr->getImplicitObjectArgument()))
          object = collector.addDeclaration(*target, context);
        std::string reason = (method->getName() + "-" + ownerKind).str();
        collector.addRelation(kind, from, object, *expr, context,
                              object ? "candidate" : "unknown", reason);
      }
    }
    if (method->getName() == "submit" || method->getName() == "enqueue" ||
        method->getName() == "post") {
      auto from = collector.addExpression(*expr, context, "unsupported-thread-api-call");
      auto target = collector.addDeclaration(*method, context);
      collector.addRelation("unsupported-thread-api", from, target, *expr, context,
                            "unknown", "framework-descriptor-required");
    }
    if (!isStdThread(method->getParent()) && !isStdJthread(method->getParent())) return true;
    bool jthread = isStdJthread(method->getParent());
    StringRef kind;
    if (method->getName() == "join") kind = jthread ? "cpp-jthread-join" : "cpp-thread-join";
    else if (method->getName() == "detach") kind = jthread ? "cpp-jthread-detach" : "cpp-thread-detach";
    else if (method->getName() == "joinable") kind = jthread ? "cpp-jthread-joinable" : "cpp-thread-joinable";
    else return true;
    auto from = collector.addExpression(*expr, context,
                                        jthread ? "cpp-jthread-member-call" : "cpp-thread-member-call");
    std::optional<std::string> object;
    if (auto *target = referencedObject(expr->getImplicitObjectArgument()))
      object = collector.addDeclaration(*target, context);
    collector.addRelation(kind, from, object, *expr, context,
                          object ? "candidate" : "unknown",
                          object ? std::optional<StringRef>("requires-profile-and-ir-binding")
                                 : std::optional<StringRef>("unresolved-thread-object"));
    return true;
  }

  bool VisitCXXOperatorCallExpr(CXXOperatorCallExpr *expr) {
    if (!eligible(expr->getBeginLoc()) || expr->getOperator() != OO_Equal || expr->getNumArgs() != 2)
      return true;
    auto *method = dyn_cast_or_null<CXXMethodDecl>(expr->getDirectCallee());
    if (!method) return true;
    StringRef ownerKind = raiiOwnerKind(method->getParent());
    if (!ownerKind.empty()) {
      auto from = collector.addExpression(*expr, context, "cpp-raii-move-assignment");
      for (unsigned index = 0; index < 2; ++index) {
        std::optional<std::string> object;
        if (auto *target = referencedObject(expr->getArg(index)))
          object = collector.addDeclaration(*target, context);
        std::string reason = (index ? "move-source-" + ownerKind
                                    : "move-target-" + ownerKind).str();
        collector.addRelation("cpp-raii-owner-move", from, object, *expr, context,
                              object ? "candidate" : "unknown", reason);
      }
      return true;
    }
    if (!isStdThread(method->getParent()) && !isStdJthread(method->getParent())) return true;
    bool jthread = isStdJthread(method->getParent());
    auto from = collector.addExpression(*expr, context,
                                        jthread ? "cpp-jthread-move-assignment"
                                                : "cpp-thread-move-assignment");
    for (unsigned index = 0; index < 2; ++index) {
      std::optional<std::string> object;
      if (auto *target = referencedObject(expr->getArg(index)))
        object = collector.addDeclaration(*target, context);
      collector.addRelation(index ? (jthread ? "cpp-jthread-move-source" : "cpp-thread-move-source")
                                  : (jthread ? "cpp-jthread-move-assign" : "cpp-thread-move-assign"),
                            from, object, *expr, context,
                            object ? "candidate" : "unknown",
                            object ? std::optional<StringRef>("requires-ir-handle-transfer")
                                   : std::optional<StringRef>("unresolved-move-object"));
    }
    return true;
  }
  bool VisitDeclRefExpr(DeclRefExpr *expr) {
    if (!eligible(expr->getBeginLoc())) return true;
    auto from = collector.addExpression(*expr, context, "reference-expression");
    auto to = collector.addDeclaration(*expr->getDecl(), context);
    collector.addRelation("read", from, to, *expr, context);
    return true;
  }
  bool VisitMemberExpr(MemberExpr *expr) {
    if (!eligible(expr->getBeginLoc())) return true;
    auto from = collector.addExpression(*expr, context, "member-expression");
    auto to = collector.addDeclaration(*expr->getMemberDecl(), context);
    collector.addRelation("read", from, to, *expr, context);
    emitPath(expr, "read");
    return true;
  }
  bool VisitCallExpr(CallExpr *expr) {
    if (!eligible(expr->getBeginLoc())) return true;
    const FunctionDecl *directCallee = expr->getDirectCallee();
    bool standardAsync = context.getLangOpts().CPlusPlus && isStdAsync(directCallee);
    unsigned asyncCallableIndex = 0;
    std::string launchPolicy = "not-applicable";
    if (standardAsync) {
      launchPolicy = "default";
      if (expr->getNumArgs() > 1) {
        QualType first = expr->getArg(0)->getType().getCanonicalType();
        if (StringRef(first.getAsString()).contains("launch")) {
          asyncCallableIndex = 1;
          launchPolicy = asyncPolicy(expr->getArg(0));
        }
      }
    }
    const CXXRecordDecl *resultRecord = context.getLangOpts().CPlusPlus && !expr->getType().isNull()
                                          ? expr->getType()->getAsCXXRecordDecl() : nullptr;
    bool threadFactory = directCallee && !expr->getType()->isReferenceType() &&
                         (isStdThread(resultRecord) || isStdJthread(resultRecord)) &&
                         !context.getSourceManager().isInSystemHeader(
                             context.getSourceManager().getSpellingLoc(directCallee->getLocation()));
    auto from = standardAsync
                  ? collector.addExpression(*expr, context, "cpp-async-call-expression",
                                            asyncEntryAttributes(*expr, *directCallee, launchPolicy))
                  : threadFactory
                      ? collector.addExpression(
                          *expr, context, "cpp-thread-factory-expression",
                          factoryEntryAttributes(*expr, *directCallee,
                                                 isStdJthread(resultRecord) ? "std-jthread" : "std-thread",
                                                 *resultRecord))
                      : collector.addExpression(*expr, context, "call-expression");
    if (auto *callee = directCallee) {
      auto to = collector.addDeclaration(*callee, context);
      collector.addRelation("call", from, to, *expr, context);
      auto name = callee->getNameAsString();
      auto qualified = callee->getQualifiedNameAsString();
      if (auto atomicKind = cppAtomicRelation(*callee)) {
        std::string profile = StringRef(qualified).starts_with("std::__1::") ? "libc++" : "libstdc++";
        json::Array atomicAttributes{
          "atomic-operation:" + *atomicKind,
          "selected-declaration:" + callee->getCanonicalDecl()->getQualifiedNameAsString(),
          "atomic-profile:" + profile,
          "canonical-result-type:" + expr->getType().getCanonicalType().getAsString()
        };
        std::vector<std::string> orders;
        for (const Expr *argument : expr->arguments()) {
          std::string type = argument->getType().getCanonicalType().getAsString();
          if (!StringRef(type).contains("memory_order")) continue;
          if (auto order = atomicOrderName(*argument)) orders.push_back(*order);
        }
        if (!orders.empty()) atomicAttributes.push_back("atomic-order:" + orders.front());
        if (orders.size() > 1) atomicAttributes.push_back("atomic-failure-order:" + orders.back());
        collector.addNodeAttributes(from, std::move(atomicAttributes));
        collector.addRelation(*atomicKind, from, to, *expr, context, "exact",
                              "canonical-std-atomic-declaration");
        for (unsigned index = 0; index < expr->getNumArgs(); ++index) {
          auto argument = collector.addExpression(*expr->getArg(index), context,
                                                  "atomic-argument-expression",
                                                  json::Array{"argument-index:" + std::to_string(index)});
          collector.addRelation("atomic-argument", from, argument, *expr->getArg(index), context,
                                "exact", "selected-atomic-overload-argument");
        }
      } else if (!context.getLangOpts().CPlusPlus &&
                 (StringRef(name).contains("atomic_thread_fence") ||
                  StringRef(name).contains("atomic_signal_fence"))) {
        auto atomicKind = cAtomicRelation(name);
        json::Array atomicAttributes{"atomic-operation:" + name,
                                     "atomic-profile:c"};
        if (expr->getNumArgs() > 0)
          if (auto order = atomicOrderName(*expr->getArg(0)))
            atomicAttributes.push_back("atomic-order:" + *order);
        collector.addNodeAttributes(from, std::move(atomicAttributes));
        collector.addRelation(atomicKind, from, to, *expr, context, "exact",
                              "canonical-clang-atomic-builtin");
      } else if (name.find("atomic") != std::string::npos ||
                 qualified.find("atomic") != std::string::npos) {
        // Preserve the A1 candidate surface. A6 never adopts this relation as
        // canonical evidence because it is name-only.
        collector.addRelation("atomic", from, to, *expr, context, "candidate",
                              "name-only-atomic-candidate");
      }
      StringRef pthreadKind;
      for (StringRef candidate : {"pthread_create", "pthread_join",
                                  "pthread_mutex_lock", "pthread_mutex_unlock"})
        if (name == candidate || qualified == candidate)
          pthreadKind = candidate;
      if (!pthreadKind.empty()) {
        collector.addRelation(pthreadKind, from, to, *expr, context);
        unsigned targetIndex = pthreadKind == "pthread_create" ? 2 : 0;
        if (expr->getNumArgs() > targetIndex) {
          Expr *argument = expr->getArg(targetIndex)->IgnoreParenImpCasts();
          if (auto *unary = dyn_cast<UnaryOperator>(argument);
              unary && unary->getOpcode() == UO_AddrOf)
            argument = unary->getSubExpr()->IgnoreParenImpCasts();
          if (auto *reference = dyn_cast<DeclRefExpr>(argument)) {
            auto target = collector.addDeclaration(*cast<NamedDecl>(reference->getDecl()), context);
            collector.addRelation(pthreadKind == "pthread_create" ? "callback" : "thread-handle",
                                  from, target, *expr, context);
          } else {
            collector.addRelation(pthreadKind == "pthread_create" ? "callback" : "thread-handle",
                                  from, std::nullopt, *expr, context, "unknown",
                                  "unsupported-pthread-argument");
          }
        }
      }
      if (name == "thrd_create" && qualified == "thrd_create") {
        collector.addRelation("thrd_create", from, to, *expr, context);
        if (expr->getNumArgs() > 1) {
          StringRef reason;
          if (const FunctionDecl *callback = callableTarget(expr->getArg(1), reason)) {
            auto target = collector.addDeclaration(*callback, context);
            collector.addRelation("thrd-callback", from, target, *expr, context);
          } else {
            collector.addRelation("thrd-callback", from, std::nullopt, *expr, context,
                                  "unknown", reason.empty() ? "unsupported-thrd-callback" : reason);
          }
        }
      }
      if (standardAsync) {
        collector.addRelation("cpp-async-call", from, to, *expr, context,
                              "candidate", launchPolicy);
        if (expr->getNumArgs() > asyncCallableIndex) {
          StringRef reason;
          if (const FunctionDecl *callback = callableTarget(expr->getArg(asyncCallableIndex), reason)) {
            auto target = collector.addDeclaration(*callback, context);
            collector.addRelation("cpp-async-callback", from, target, *expr, context,
                                  "candidate", "requires-profile-and-ir-binding");
          } else {
            collector.addRelation("cpp-async-callback", from, std::nullopt, *expr, context,
                                  "unknown", reason);
          }
        }
      }
      if (name == "clone" && qualified == "clone")
        collector.addRelation("unsupported-thread-api", from, to, *expr, context,
                              "unknown", "platform-thread-api-unsupported");
      if (threadFactory)
        collector.addRelation(isStdJthread(resultRecord) ? "cpp-jthread-factory-return"
                                                         : "cpp-thread-factory-return",
                              from, to, *expr, context, "candidate",
                              "factory-call-does-not-create-at-callsite");
    } else {
      collector.addRelation("call", from, std::nullopt, *expr, context, "unknown", "indirect-call");
    }
    for (Expr *argument : expr->arguments()) emitPath(argument, "argument");
    if (auto *memberCall = dyn_cast<CXXMemberCallExpr>(expr))
      emitPath(memberCall->getImplicitObjectArgument(), "receiver");
    return true;
  }
  bool VisitBinaryOperator(BinaryOperator *expr) {
    if (!eligible(expr->getBeginLoc())) return true;
    if (expr->isComparisonOp()) {
      auto from = collector.addExpression(*expr, context, "compare-expression");
      for (Expr *operand : {expr->getLHS(), expr->getRHS()}) {
        operand = operand->IgnoreParenImpCasts();
        if (auto *reference = dyn_cast<DeclRefExpr>(operand)) {
          auto to = collector.addDeclaration(*cast<NamedDecl>(reference->getDecl()), context);
          collector.addRelation("compare", from, to, *expr, context, "candidate");
        }
      }
    }
    if (!expr->isAssignmentOp()) return true;
    auto from = collector.addExpression(*expr, context, "assignment-expression");
    Expr *left = expr->getLHS()->IgnoreParenImpCasts();
    if (auto *reference = dyn_cast<DeclRefExpr>(left)) {
      auto to = collector.addDeclaration(*cast<NamedDecl>(reference->getDecl()), context);
      collector.addRelation("write", from, to, *expr, context);
    } else if (auto *member = dyn_cast<MemberExpr>(left)) {
      auto to = collector.addDeclaration(*cast<NamedDecl>(member->getMemberDecl()), context);
      collector.addRelation("write", from, to, *expr, context);
      emitPath(member, "write");
    }
    return true;
  }
  bool VisitUnaryOperator(UnaryOperator *expr) {
    if (!eligible(expr->getBeginLoc()) || !expr->isIncrementDecrementOp()) return true;
    auto from = collector.addExpression(*expr, context, "update-expression");
    Expr *operand = expr->getSubExpr()->IgnoreParenImpCasts();
    if (auto *reference = dyn_cast<DeclRefExpr>(operand)) {
      auto to = collector.addDeclaration(*cast<NamedDecl>(reference->getDecl()), context);
      collector.addRelation("write", from, to, *expr, context);
    } else if (auto *member = dyn_cast<MemberExpr>(operand)) {
      auto to = collector.addDeclaration(*cast<NamedDecl>(member->getMemberDecl()), context);
      collector.addRelation("write", from, to, *expr, context);
    }
    return true;
  }
  bool VisitCastExpr(CastExpr *expr) {
    if (!eligible(expr->getBeginLoc())) return true;
    if (isa<ImplicitCastExpr>(expr)) return true;
    auto from = collector.addExpression(*expr, context, "cast-expression");
    Expr *operand = expr->getSubExpr()->IgnoreParenImpCasts();
    if (auto *reference = dyn_cast<DeclRefExpr>(operand)) {
      auto to = collector.addDeclaration(*cast<NamedDecl>(reference->getDecl()), context);
      collector.addRelation("cast", from, to, *expr, context, "candidate");
    }
    return true;
  }
  bool VisitAtomicExpr(AtomicExpr *expr) {
    if (!eligible(expr->getBeginLoc())) return true;
    std::string operation = expr->getOpAsString().str();
    std::string relation = cAtomicRelation(operation);
    json::Array atomicAttributes{"atomic-operation:" + operation,
                                 "canonical-value-type:" + expr->getValueType().getCanonicalType().getAsString(),
                                 "atomic-profile:c"};
    if (auto order = atomicOrderName(*expr->getOrder()))
      atomicAttributes.push_back("atomic-order:" + *order);
    if (expr->isCmpXChg())
      if (auto failure = atomicOrderName(*expr->getOrderFail()))
        atomicAttributes.push_back("atomic-failure-order:" + *failure);
    auto from = collector.addExpression(*expr, context, "atomic-expression",
                                        std::move(atomicAttributes));
    Expr *pointer = expr->getPtr()->IgnoreParenImpCasts();
    std::optional<std::string> object;
    if (auto *unary = dyn_cast<UnaryOperator>(pointer);
        unary && unary->getOpcode() == UO_AddrOf)
      pointer = unary->getSubExpr()->IgnoreParenImpCasts();
    if (auto *reference = dyn_cast<DeclRefExpr>(pointer))
      object = collector.addDeclaration(*cast<NamedDecl>(reference->getDecl()), context);
    else if (auto *member = dyn_cast<MemberExpr>(pointer))
      object = collector.addDeclaration(*cast<NamedDecl>(member->getMemberDecl()), context);
    collector.addRelation(relation, from, object, *expr, context,
                          relation == "atomic" ? "unknown" : "exact",
                          relation == "atomic" ? "unsupported-c-atomic-operation"
                                               : "canonical-clang-atomic-expression");
    if (relation != "atomic")
      collector.addRelation("atomic", from, object, *expr, context, "candidate",
                            "compatibility-atomic-source-candidate");
    if (!StringRef(operation).contains("init")) {
      auto order = collector.addExpression(*expr->getOrder(), context, "atomic-order-expression");
      collector.addRelation("atomic-order", from, order, *expr->getOrder(), context,
                            "candidate", "order-expression-requires-ir-binding");
    }
    if (expr->isCmpXChg()) {
      auto failure = collector.addExpression(*expr->getOrderFail(), context,
                                             "atomic-failure-order-expression");
      collector.addRelation("atomic-failure-order", from, failure, *expr->getOrderFail(), context,
                            "candidate", "failure-order-expression-requires-ir-binding");
    }
    return true;
  }
  bool VisitCompoundStmt(CompoundStmt *stmt) {
    if (!eligible(stmt->getBeginLoc())) return true;
    const Stmt *previous = nullptr;
    for (const Stmt *current : stmt->body()) {
      // Clang's CompoundStmt body stores non-null child statements.
      // Only adjacent expression statements are source-level full expressions;
      // control/declaration statements reset the chain instead of being crossed.
      if (!eligible(current->getBeginLoc()) || !isa<Expr>(current)) {
        previous = nullptr;
        continue;
      }
      if (previous) {
        auto from = collector.addExpression(*previous, context, "statement");
        auto to = collector.addExpression(*current, context, "statement");
        collector.addRelation("sequenced-before", from, to, *previous, context);
      }
      previous = current;
    }
    return true;
  }
  bool VisitIfStmt(IfStmt *stmt) {
    if (!eligible(stmt->getBeginLoc())) return true;
    auto from = collector.addExpression(*stmt->getCond(), context, "control-expression");
    collector.addRelation("control", from, std::nullopt, *stmt, context, "candidate");
    return true;
  }
  bool VisitWhileStmt(WhileStmt *stmt) {
    if (!eligible(stmt->getBeginLoc())) return true;
    auto from = collector.addExpression(*stmt->getCond(), context, "control-expression");
    collector.addRelation("control", from, std::nullopt, *stmt, context, "candidate");
    return true;
  }
  bool VisitReturnStmt(ReturnStmt *stmt) {
    if (!eligible(stmt->getBeginLoc())) return true;
    auto from = collector.addExpression(*stmt, context, "return-expression");
    std::optional<std::string> target;
    if (Expr *value = stmt->getRetValue()) {
      value = value->IgnoreParenImpCasts();
      if (auto *reference = dyn_cast<DeclRefExpr>(value))
        target = collector.addDeclaration(*cast<NamedDecl>(reference->getDecl()), context);
      emitPath(value, "return");
    }
    collector.addRelation("return", from, target, *stmt, context, "candidate");
    return true;
  }
};

class SourceConsumer : public ASTConsumer {
  Collector &collector;
public:
  explicit SourceConsumer(Collector &collector) : collector(collector) {}
  void HandleTranslationUnit(ASTContext &context) override {
    SourceVisitor visitor(context, collector);
    visitor.TraverseDecl(context.getTranslationUnitDecl());
  }
};

class SourceAction : public ASTFrontendAction {
  Collector &collector;
public:
  explicit SourceAction(Collector &collector) : collector(collector) {}
  std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance &, StringRef) override {
    return std::make_unique<SourceConsumer>(collector);
  }
};

class SourceFactory : public FrontendActionFactory {
  Collector &collector;
public:
  explicit SourceFactory(Collector &collector) : collector(collector) {}
  std::unique_ptr<FrontendAction> create() override { return std::make_unique<SourceAction>(collector); }
};

json::Object count(size_t planned, size_t visited, size_t emitted, size_t skipped, size_t failed) {
  return json::Object{{"planned", static_cast<int64_t>(planned)}, {"visited", static_cast<int64_t>(visited)},
                      {"emitted", static_cast<int64_t>(emitted)}, {"skipped", static_cast<int64_t>(skipped)},
                      {"failed", static_cast<int64_t>(failed)},
                      {"ratio", planned ? json::Value(static_cast<double>(emitted) / planned) : json::Value(nullptr)}};
}

std::string llvmType(llvm::Type *type) {
  std::string result;
  raw_string_ostream stream(result);
  type->print(stream);
  return result;
}

std::string llvmLinkage(const GlobalValue &value) {
  if (value.hasLocalLinkage()) return "internal";
  if (value.hasExternalLinkage()) return "external";
  if (value.hasExternalWeakLinkage()) return "extern_weak";
  if (value.hasCommonLinkage()) return "common";
  if (value.hasAvailableExternallyLinkage()) return "available_externally";
  if (value.hasLinkOnceLinkage()) return "linkonce";
  return "weak";
}

std::string llvmVisibility(const GlobalValue &value) {
  static constexpr const char *names[] = {"default", "hidden", "protected"};
  return names[static_cast<unsigned>(value.getVisibility())];
}

json::Object llvmAbi(llvm::Type *type, const DataLayout &layout) {
  if (!type->isSized())
    return json::Object{{"complete", false}, {"size_bits", nullptr}, {"align_bits", nullptr}};
  TypeSize size = layout.getTypeStoreSizeInBits(type);
  if (size.isScalable())
    return json::Object{{"complete", false}, {"size_bits", nullptr}, {"align_bits", nullptr}};
  return json::Object{{"complete", true}, {"size_bits", static_cast<int64_t>(size.getFixedValue())},
                      {"align_bits", static_cast<int64_t>(layout.getABITypeAlign(type).value() * 8)}};
}

json::Object llvmSymbol(const GlobalValue &value, StringRef artifact, const DataLayout &layout) {
  bool function = isa<Function>(value);
  llvm::Type *type = function ? cast<Function>(value).getFunctionType() : cast<GlobalVariable>(value).getValueType();
  json::Object abi = function ? json::Object{{"complete", true},
      {"parameters", static_cast<int64_t>(cast<llvm::FunctionType>(type)->getNumParams())},
      {"vararg", cast<llvm::FunctionType>(type)->isVarArg()},
      {"return_type", llvmType(cast<llvm::FunctionType>(type)->getReturnType())}}
      : llvmAbi(type, layout);
  const auto *object = dyn_cast<GlobalObject>(&value);
  return json::Object{{"id", artifact.str() + ":symbol:" + value.getName().str()},
                      {"kind", function ? "function" : "global"}, {"name", value.getName().str()},
                      {"linkage", llvmLinkage(value)}, {"visibility", llvmVisibility(value)},
                      {"tls", !function && cast<GlobalVariable>(value).isThreadLocal()},
                      {"comdat", object && object->hasComdat()}, {"definition", !value.isDeclaration()},
                      {"canonical_type", llvmType(type)}, {"abi", std::move(abi)}};
}

} // namespace

json::Object sourceProtocol() {
  auto parsed = json::parse(MOA_SOURCE_PROTOCOL_JSON);
  if (!parsed) throw std::runtime_error("source_protocol_invalid");
  return std::move(*parsed->getAsObject());
}

json::Object provenanceProtocol() {
  auto parsed = json::parse(MOA_PROVENANCE_PROTOCOL_JSON);
  if (!parsed) throw std::runtime_error("provenance_protocol_invalid");
  return std::move(*parsed->getAsObject());
}

json::Object analyzeSource(const json::Object &request) {
  auto requestVersion = request.getInteger("schema_version");
  if (requiredString(request, "kind") != "SourceSemanticRequest" ||
      !requestVersion || (*requestVersion != 1 && *requestVersion != 2))
    throw std::runtime_error("source_request_invalid: schema/kind");
  auto *profile = request.getObject("profile"); auto *budgets = request.getObject("budgets");
  if (!profile || !budgets) throw std::runtime_error("source_request_invalid: profile/budgets");
  static constexpr const char *languageContext[] = {
      "dialect", "standard_source", "standard_option"};
  if (*requestVersion == 2) {
    if (profile->getInteger("schema_version") != 2)
      throw std::runtime_error("source_request_invalid: request/profile schema mismatch");
    requiredString(*profile, "language");
    requiredString(*profile, "standard");
    for (const auto *field : languageContext) requiredString(*profile, field);
  } else {
    for (const auto *field : languageContext)
      if (profile->get(field))
        throw std::runtime_error("source_request_invalid: v1 profile carries v2 language context");
  }
  auto physical = requiredString(request, "physical_tu_id");
  auto sourcePath = requiredString(request, "source_path");
  auto *profileSource = profile->getObject("source");
  if (!profileSource || sourcePath != requiredString(*profileSource, "path"))
    throw std::runtime_error("source_request_invalid: source/profile path mismatch");
  if (auto *replay = profile->getObject("replay"); replay && replay->getString("status") == "failed")
    throw std::runtime_error("source_request_invalid: compilation profile is not replayable");
  Collector collector{physical, static_cast<size_t>(requiredBudget(*budgets, "ast_nodes")),
                      static_cast<size_t>(requiredBudget(*budgets, "references"))};
  std::vector<std::string> arguments;
  auto *argv = profile->getArray("argv");
  if (!argv || argv->empty()) throw std::runtime_error("source_request_invalid: argv");
  auto directory = requiredString(*profile, "working_directory");
  const auto normalizedSource = std::filesystem::weakly_canonical(sourcePath);
  bool skip = true;
  for (const auto &item : *argv) {
    auto value = item.getAsString(); if (!value) throw std::runtime_error("source_request_invalid: argv item");
    if (skip) { skip = false; continue; }
    auto argumentPath = std::filesystem::path(value->str());
    if (argumentPath.is_relative()) argumentPath = std::filesystem::path(directory) / argumentPath;
    if (*value == "-c" || *value == "-emit-llvm" || *value == sourcePath ||
        std::filesystem::weakly_canonical(argumentPath) == normalizedSource) continue;
    if (*value == "-o") { skip = true; continue; }
    arguments.push_back(value->str());
  }
  FixedCompilationDatabase database(directory, arguments);
  ClangTool tool(database, {sourcePath});
  SourceFactory factory(collector);
  int result = tool.run(&factory);
  std::sort(collector.nodes.begin(), collector.nodes.end(), [](const auto &left, const auto &right) {
    return *left.getString("id") < *right.getString("id");
  });
  std::sort(collector.relations.begin(), collector.relations.end(), [](const auto &left, const auto &right) {
    return *left.getString("id") < *right.getString("id");
  });
  json::Array nodes, relations, diagnostics, frontier;
  for (auto &node : collector.nodes) nodes.push_back(std::move(node));
  for (auto &relation : collector.relations) relations.push_back(std::move(relation));
  if (result != 0) {
    auto item = diag("clang-replay-failed", "Clang 语义重放失败", "Clang semantic replay failed");
    diagnostics.push_back(json::Value(diag("clang-replay-failed", "Clang 语义重放失败", "Clang semantic replay failed")));
    frontier.push_back(json::Value(std::move(item)));
  }
  if (collector.nodeExhausted || collector.relationExhausted) {
    auto item = diag("source-budget-exhausted", "源语义提取预算已耗尽", "Source semantic extraction budget exhausted");
    diagnostics.push_back(json::Value(diag("source-budget-exhausted", "源语义提取预算已耗尽", "Source semantic extraction budget exhausted")));
    frontier.push_back(json::Value(std::move(item)));
  }
  std::string status = result != 0 && collector.nodes.empty() ? "failed" :
                       result != 0 || collector.nodeExhausted || collector.relationExhausted ? "partial" : "complete";
  json::Object countMap;
  countMap["translation_units"] = count(1, 1, result == 0 ? 1 : 0, 0, result == 0 ? 0 : 1);
  countMap["nodes"] = count(collector.nodes.size() + (collector.nodeExhausted ? 1 : 0),
                            collector.nodes.size() + (collector.nodeExhausted ? 1 : 0),
                            collector.nodes.size(), 0, collector.nodeExhausted ? 1 : 0);
  countMap["relations"] = count(collector.relations.size() + (collector.relationExhausted ? 1 : 0),
                                collector.relations.size() + (collector.relationExhausted ? 1 : 0),
                                collector.relations.size(), 0, collector.relationExhausted ? 1 : 0);
  return json::Object{{"schema_version", 1}, {"kind", "SourceSemanticFacts"}, {"analysis_version", "0.1.0"},
                      {"policy_id", "ast-cross-tu-evidence-v1"}, {"profile_id", requiredString(*profile, "profile_id")},
          {"physical_tu_id", physical}, {"source_digest", requiredString(*profileSource, "sha256")},
                      {"status", status}, {"nodes", std::move(nodes)}, {"relations", std::move(relations)},
                      {"counts", std::move(countMap)}, {"diagnostics", std::move(diagnostics)}, {"frontier", std::move(frontier)}};
}

json::Object analyzeObjectPaths(const json::Object &request) {
  if (requiredString(request, "kind") != "SourceObjectPathRequest" || request.getInteger("schema_version") != 1)
    throw std::runtime_error("object_path_request_invalid: schema/kind");
  auto *profile = request.getObject("profile"); auto *budgets = request.getObject("budgets");
  if (!profile || !budgets) throw std::runtime_error("object_path_request_invalid: profile/budgets");
  auto physical = requiredString(request, "physical_tu_id");
  auto sourcePath = requiredString(request, "source_path");
  auto *profileSource = profile->getObject("source");
  if (!profileSource || sourcePath != requiredString(*profileSource, "path"))
    throw std::runtime_error("object_path_request_invalid: source/profile path mismatch");
  if (auto *replay = profile->getObject("replay"); replay && replay->getString("status") == "failed")
    throw std::runtime_error("object_path_request_invalid: compilation profile is not replayable");
  size_t sourceLimit = static_cast<size_t>(requiredBudget(*budgets, "source_nodes"));
  Collector collector{physical, sourceLimit, sourceLimit,
                      static_cast<size_t>(requiredBudget(*budgets, "path_segments")),
                      static_cast<size_t>(requiredBudget(*budgets, "path_depth"))};
  std::vector<std::string> arguments;
  auto *argv = profile->getArray("argv");
  if (!argv || argv->empty()) throw std::runtime_error("object_path_request_invalid: argv");
  auto directory = requiredString(*profile, "working_directory");
  const auto normalizedSource = std::filesystem::weakly_canonical(sourcePath);
  bool skip = true;
  std::string standard;
  for (const auto &item : *argv) {
    auto value = item.getAsString(); if (!value) throw std::runtime_error("object_path_request_invalid: argv item");
    if (value->starts_with("-std=")) standard = value->drop_front(5).str();
    if (skip) { skip = false; continue; }
    auto argumentPath = std::filesystem::path(value->str());
    if (argumentPath.is_relative()) argumentPath = std::filesystem::path(directory) / argumentPath;
    if (*value == "-c" || *value == "-emit-llvm" || *value == sourcePath ||
        std::filesystem::weakly_canonical(argumentPath) == normalizedSource) continue;
    if (*value == "-o") { skip = true; continue; }
    arguments.push_back(value->str());
  }
  bool cpp = StringRef(standard).starts_with("c++") || StringRef(standard).starts_with("gnu++");
  if (standard == "gnu11") standard = "c11";
  if (standard == "gnu17") standard = "c17";
  if (standard == "gnu++17") standard = "c++17";
  if (standard == "gnu++20") standard = "c++20";
  if (standard != "c11" && standard != "c17" && standard != "c++17" && standard != "c++20")
    throw std::runtime_error("object_path_request_invalid: unsupported C/C++ standard");
  FixedCompilationDatabase database(directory, arguments);
  ClangTool tool(database, {sourcePath});
  SourceFactory factory(collector);
  int result = tool.run(&factory);
  std::sort(collector.paths.begin(), collector.paths.end(), [](const auto &left, const auto &right) {
    return *left.getString("id") < *right.getString("id");
  });
  json::Array paths, diagnostics, frontier;
  for (auto &path : collector.paths) paths.push_back(std::move(path));
  if (result != 0) {
    diagnostics.push_back(provenanceDiag("clang-replay-failed", "Clang 对象路径重放失败", "Clang object-path replay failed"));
    frontier.push_back(provenanceDiag("clang-replay-failed", "Clang 对象路径重放失败", "Clang object-path replay failed"));
  }
  if (collector.pathExhausted || collector.nodeExhausted) {
    diagnostics.push_back(provenanceDiag("source-path-budget-exhausted", "源对象路径预算已耗尽", "Source object-path budget exhausted"));
    frontier.push_back(provenanceDiag("source-path-budget-exhausted", "源对象路径预算已耗尽", "Source object-path budget exhausted"));
  }
  std::string status = result != 0 && collector.paths.empty() ? "failed" :
                       result != 0 || collector.pathExhausted || collector.nodeExhausted ? "partial" : "complete";
  json::Object counts{{"planned", 1}, {"completed", status == "complete" ? 1 : 0},
                      {"paths", static_cast<int64_t>(paths.size())},
                      {"source_nodes", static_cast<int64_t>(collector.nodes.size())}};
  return json::Object{{"schema_version", 1}, {"kind", "SourceObjectPathFacts"},
                      {"analysis_version", "0.1.0"}, {"policy_id", "bounded-object-provenance-v1"},
                      {"profile_id", requiredString(*profile, "profile_id")}, {"physical_tu_id", physical},
                      {"source_digest", requiredString(*profileSource, "sha256")},
                      {"language", cpp ? "c++" : "c"}, {"standard", standard}, {"mode", "ast-only"},
                      {"status", status}, {"paths", std::move(paths)}, {"counts", std::move(counts)},
                      {"dependencies", json::Array{}}, {"diagnostics", std::move(diagnostics)},
                      {"frontier", std::move(frontier)}};
}

json::Object analyzeLLVMSourceBinding(const json::Object &request) {
  if (requiredString(request, "kind") != "LLVMSourceBindingRequest" || request.getInteger("schema_version") != 1)
    throw std::runtime_error("ir_binding_request_invalid: schema/kind");
  auto *bitcode = request.getObject("bitcode");
  auto *budgets = request.getObject("budgets");
  if (!bitcode || !budgets) throw std::runtime_error("ir_binding_request_invalid: bitcode/budgets");
  auto artifact = requiredString(request, "artifact_key");
  auto path = requiredString(*bitcode, "path");
  LLVMContext context;
  SMDiagnostic error;
  auto module = parseIRFile(path, error, context);
  if (!module) throw std::runtime_error("ir_binding_parse_failed: cannot parse bitcode");
  size_t limit = static_cast<size_t>(requiredBudget(*budgets, "binding_candidates"));
  size_t planned = module->size() + module->global_size();
  json::Array symbols, frontier;
  std::vector<json::Object> values;
  for (const Function &function : *module) values.push_back(llvmSymbol(function, artifact, module->getDataLayout()));
  for (const GlobalVariable &global : module->globals()) values.push_back(llvmSymbol(global, artifact, module->getDataLayout()));
  std::sort(values.begin(), values.end(), [](const auto &left, const auto &right) {
    return *left.getString("id") < *right.getString("id");
  });
  bool exhausted = values.size() > limit;
  if (exhausted) values.resize(limit);
  for (auto &value : values) symbols.push_back(std::move(value));
  if (exhausted) frontier.push_back(diag("ir-binding-budget-exhausted", "LLVM 符号预算已耗尽",
                                        "LLVM symbol budget exhausted"));
  json::Array diagnostics;
  json::Object countMap;
  countMap["symbols"] = count(planned, planned, symbols.size(), 0, planned - symbols.size());
  std::string target = module->getTargetTriple().empty() ? "unknown" : module->getTargetTriple().str();
  return json::Object{{"schema_version", 1}, {"kind", "LLVMSourceBindingFacts"},
                      {"analysis_version", "0.1.0"}, {"policy_id", "ast-cross-tu-evidence-v1"},
                      {"artifact_key", artifact}, {"profile_id", requiredString(request, "profile_id")},
                      {"physical_tu_id", requiredString(request, "physical_tu_id")},
                      {"bitcode_digest", requiredString(*bitcode, "sha256")}, {"target", target},
                      {"data_layout", module->getDataLayoutStr()}, {"status", exhausted ? "partial" : "complete"},
                      {"symbols", std::move(symbols)}, {"counts", std::move(countMap)},
                      {"diagnostics", std::move(diagnostics)}, {"frontier", std::move(frontier)}};
}

int sourceWorker(const char *path, raw_ostream &out, raw_ostream &err) {
  try {
    auto buffer = MemoryBuffer::getFile(path);
    if (!buffer) throw std::runtime_error("source_request_invalid: cannot read request");
    auto parsed = json::parse((*buffer)->getBuffer());
    if (!parsed || !parsed->getAsObject()) throw std::runtime_error("source_request_invalid: invalid JSON");
    auto facts = analyzeSource(*parsed->getAsObject());
    std::string payload;
    raw_string_ostream stream(payload);
    stream << json::Value(std::move(facts)) << "\n";
    stream.flush();
    auto *budgets = parsed->getAsObject()->getObject("budgets");
    if (!budgets || static_cast<uint64_t>(requiredBudget(*budgets, "worker_output_bytes")) < payload.size())
      throw std::runtime_error("source_worker_output_limit: output exceeds worker_output_bytes");
    out << payload;
    return 0;
  } catch (const std::exception &error) {
    err << error.what() << "\n";
    return 1;
  }
}

int objectPathWorker(const char *path, raw_ostream &out, raw_ostream &err) {
  try {
    auto buffer = MemoryBuffer::getFile(path);
    if (!buffer) throw std::runtime_error("object_path_request_invalid: cannot read request");
    auto parsed = json::parse((*buffer)->getBuffer());
    if (!parsed || !parsed->getAsObject())
      throw std::runtime_error("object_path_request_invalid: invalid JSON");
    auto facts = analyzeObjectPaths(*parsed->getAsObject());
    std::string payload;
    raw_string_ostream stream(payload);
    stream << json::Value(std::move(facts)) << "\n";
    stream.flush();
    auto *budgets = parsed->getAsObject()->getObject("budgets");
    if (!budgets || static_cast<uint64_t>(requiredBudget(*budgets, "worker_output_bytes")) < payload.size())
      throw std::runtime_error("object_path_worker_output_limit: output exceeds worker_output_bytes");
    out << payload;
    return 0;
  } catch (const std::exception &error) {
    err << error.what() << "\n";
    return 1;
  }
}

int irBindingWorker(const char *path, raw_ostream &out, raw_ostream &err) {
  try {
    auto buffer = MemoryBuffer::getFile(path);
    if (!buffer) throw std::runtime_error("ir_binding_request_invalid: cannot read request");
    auto parsed = json::parse((*buffer)->getBuffer());
    if (!parsed || !parsed->getAsObject())
      throw std::runtime_error("ir_binding_request_invalid: invalid JSON");
    auto facts = analyzeLLVMSourceBinding(*parsed->getAsObject());
    std::string payload;
    raw_string_ostream stream(payload);
    stream << json::Value(std::move(facts)) << "\n";
    stream.flush();
    auto *budgets = parsed->getAsObject()->getObject("budgets");
    if (!budgets || static_cast<uint64_t>(requiredBudget(*budgets, "worker_output_bytes")) < payload.size())
      throw std::runtime_error("source_worker_output_limit: output exceeds worker_output_bytes");
    out << payload;
    return 0;
  } catch (const std::exception &error) {
    err << error.what() << "\n";
    return 1;
  }
}
} // namespace moa
