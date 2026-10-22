#include "facts.h"
#include <gtest/gtest.h>
#include <llvm/AsmParser/Parser.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Bitcode/BitcodeWriter.h>
#include <llvm/IR/IRBuilder.h>
#include <llvm/Support/FileSystem.h>
#include <llvm/Support/Path.h>
#include <fstream>

#define main worker_main_under_test
#include "../../src/worker.cpp"
#undef main

namespace {
std::unique_ptr<llvm::Module> parse(llvm::LLVMContext &context, const char *ir) {
  llvm::SMDiagnostic error;
  auto module = llvm::parseAssemblyString(ir, error, context);
  if (!module) error.print("unit", llvm::errs());
  return module;
}
struct Temporary {
  llvm::SmallString<128> path;
  Temporary() { EXPECT_FALSE(llvm::sys::fs::createTemporaryFile("moa-unit", "bc", path)); }
  ~Temporary() { llvm::sys::fs::remove(path); }
  void bitcode(llvm::Module &module) {
    std::error_code error;
    llvm::raw_fd_ostream stream(path, error);
    ASSERT_FALSE(error);
    llvm::WriteBitcodeToFile(module, stream);
  }
};
} // namespace

TEST(Facts, DeclarationAndDeterminism) {
  llvm::LLVMContext context;
  llvm::SMDiagnostic error;
  auto module = llvm::parseAssemblyString("declare void @external()\n", error, context);
  ASSERT_NE(module, nullptr);
  auto first = moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'));
  EXPECT_EQ(first.getArray("functions")->size(), 1u);
  EXPECT_EQ(first.getArray("events")->size(), 0u);
  EXPECT_EQ(first.getString("source_mapping"), "unavailable");
  auto second = moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'));
  EXPECT_EQ(llvm::json::Value(std::move(first)), llvm::json::Value(std::move(second)));
}

TEST(Facts, MemoryKindsAddressesAndControlFlow) {
  llvm::LLVMContext context;
  auto module = parse(context, R"(
target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-p:64:64"
@global = global i32 0
@array = global [4 x i32] zeroinitializer
@ext = external global i32
@local = internal global i32 0
@common = common global i32 0
@weak = weak global i32 0
@externweak = extern_weak global i32
@alias = alias i32, ptr @global
declare void @external()
declare void @llvm.memcpy.p0.p0.i64(ptr, ptr, i64, i1)
declare void @llvm.memset.p0.i64(ptr, i8, i64, i1)
declare void @llvm.assume(i1)
define void @f(ptr %arg, ptr %fp, i64 %index, i1 %condition) {
entry:
  %stack = alloca i32
  store i32 1, ptr %stack
  %a = load volatile i32, ptr @global
  store volatile i32 2, ptr @global
  %b = load atomic i32, ptr @global acquire, align 4
  store atomic i32 3, ptr @global release, align 4
  %c = atomicrmw add ptr @global, i32 1 monotonic
  %d = cmpxchg weak ptr @global, i32 1, i32 2 acq_rel acquire
  fence syncscope("singlethread") release
  fence seq_cst
  %e = load i32, ptr %arg
  %gep = getelementptr i32, ptr %arg, i64 2
  %g = load i32, ptr %gep
  %dyn = getelementptr i32, ptr %arg, i64 %index
  %h = load i32, ptr %dyn
  %unknown = inttoptr i64 %index to ptr
  %i = load i32, ptr %unknown
  %j = load i32, ptr getelementptr ([4 x i32], ptr @array, i64 0, i64 1)
  call void @external()
  call void %fp()
  call void asm sideeffect "", "~{memory}"()
  call void @llvm.memcpy.p0.p0.i64(ptr %arg, ptr @global, i64 4, i1 false)
  call void @llvm.memset.p0.i64(ptr %arg, i8 0, i64 4, i1 true)
  call void @llvm.assume(i1 %condition)
  br i1 %condition, label %yes, label %no
yes:
  ret void
no:
  ret void
}
define internal void @localfn() { ret void }
define available_externally void @available() { ret void }
define linkonce void @once() { ret void }
!llvm.ident = !{!0}
!0 = !{!"unit producer"}
)");
  ASSERT_NE(module, nullptr);
  auto facts = moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'));
  auto *events = facts.getArray("events");
  ASSERT_EQ(events->size(), 18u);
  EXPECT_EQ((*events)[0].getAsObject()->getObject("address")->getString("kind"), "alloca");
  EXPECT_EQ((*events)[1].getAsObject()->getBoolean("volatile"), true);
  EXPECT_EQ((*events)[3].getAsObject()->getString("ordering"), "acquire");
  EXPECT_EQ((*events)[4].getAsObject()->getString("ordering"), "release");
  EXPECT_EQ((*events)[5].getAsObject()->getString("operation"), "add");
  EXPECT_EQ((*events)[6].getAsObject()->getString("success_ordering"), "acq_rel");
  EXPECT_EQ((*events)[6].getAsObject()->getString("failure_ordering"), "acquire");
  EXPECT_EQ((*events)[6].getAsObject()->getBoolean("weak"), true);
  EXPECT_EQ((*events)[7].getAsObject()->getString("syncscope"), "singlethread");
  EXPECT_EQ((*events)[8].getAsObject()->getString("syncscope"), "system");
  EXPECT_EQ((*events)[9].getAsObject()->getObject("address")->getString("kind"), "argument");
  EXPECT_EQ((*events)[10].getAsObject()->getObject("address")->getString("kind"), "constant_gep");
  EXPECT_EQ((*events)[11].getAsObject()->getObject("address")->getString("kind"), "unknown");
  EXPECT_EQ((*events)[12].getAsObject()->getObject("address")->getString("kind"), "unknown");
  EXPECT_EQ((*events)[14].getAsObject()->getString("reason"), "inline_asm");
  EXPECT_EQ((*events)[15].getAsObject()->getObject("source_address")->getString("kind"), "global");
  EXPECT_EQ((*events)[16].getAsObject()->getBoolean("volatile"), true);
  EXPECT_EQ((*events)[17].getAsObject()->getString("reason"), "intrinsic");
  ASSERT_EQ(facts.getArray("calls")->size(), 6u);
  EXPECT_EQ((*facts.getArray("calls"))[1].getAsObject()->getString("kind"), "indirect");
  EXPECT_EQ(facts.getArray("globals")->size(), 8u);
  EXPECT_EQ(facts.getArray("producer")->size(), 1u);
  EXPECT_EQ(facts.getObject("capabilities")->getBoolean("callsite_specialization"), false);
  for (auto &value : *facts.getArray("functions")) {
    auto *fn = value.getAsObject();
    if (fn->getString("name") == "f") {
      EXPECT_EQ(fn->getArray("blocks")->size(), 3u);
      EXPECT_EQ((*fn->getArray("blocks"))[0].getAsObject()->getArray("successors")->size(), 2u);
    }
  }
  std::string serialized;
  llvm::json::Value retained(std::move(facts));
  llvm::raw_string_ostream stream(serialized);
  stream << retained;
  module.reset();
  std::vector<std::string> overwrite(10000, std::string(128, 'x'));
  std::string afterRelease;
  llvm::raw_string_ostream after(afterRelease);
  after << retained;
  EXPECT_EQ(afterRelease, serialized);
}

TEST(Facts, DebugInlineAndStableInstructionIdentities) {
  llvm::LLVMContext context;
  auto module = parse(context, R"(
@x = global i32 0
define void @f() !dbg !4 {
  store i32 1, ptr @x, !dbg !7
  store i32 2, ptr @x, !dbg !7
  ret void
}
!llvm.dbg.cu = !{!0}
!llvm.module.flags = !{!8}
!0 = distinct !DICompileUnit(language: DW_LANG_C11, file: !1, producer: "unit", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug)
!1 = !DIFile(filename: "input.c", directory: "/source")
!2 = !DISubroutineType(types: !3)
!3 = !{}
!4 = distinct !DISubprogram(name: "f", scope: !1, file: !1, line: 1, type: !2, scopeLine: 1, spFlags: DISPFlagDefinition, unit: !0)
!5 = distinct !DISubprogram(name: "inline", scope: !1, file: !1, line: 2, type: !2, scopeLine: 2, spFlags: DISPFlagDefinition, unit: !0)
!6 = !DILocation(line: 3, column: 2, scope: !4)
!7 = !DILocation(line: 2, column: 1, scope: !5, inlinedAt: !6)
!8 = !{i32 2, !"Debug Info Version", i32 3}
)");
  ASSERT_NE(module, nullptr);
  auto facts = moa::extract(*module, std::string(64, 'a'), std::string(64, 'b'));
  EXPECT_EQ(facts.getString("source_mapping"), "complete");
  auto *events = facts.getArray("events");
  ASSERT_EQ(events->size(), 2u);
  auto *first = (*events)[0].getAsObject();
  auto *second = (*events)[1].getAsObject();
  EXPECT_NE(first->getString("id"), second->getString("id"));
  EXPECT_EQ(first->getObject("source")->getArray("inline_chain")->size(), 2u);
  module->getFunction("f")->front().front().setDebugLoc({});
  EXPECT_EQ(moa::extract(*module, "a", "b").getString("source_mapping"), "partial");
}

TEST(Facts, IfuncComdatMoveAndExchangeRemainExplicit) {
  llvm::LLVMContext context;
  auto module = parse(context, R"(
$group = comdat any
@dispatch = ifunc void (), ptr @resolve
@word = global i32 0
declare void @llvm.memmove.p0.p0.i64(ptr, ptr, i64, i1)
define ptr @resolve() { ret ptr @target }
define linkonce_odr void @target() comdat($group) { ret void }
define void @f(ptr %destination, ptr %source) {
  %x = atomicrmw xchg ptr @word, i32 2 seq_cst
  call void @llvm.memmove.p0.p0.i64(ptr %destination, ptr %source, i64 8, i1 false)
  call void @dispatch()
  ret void
}
)");
  ASSERT_NE(module, nullptr);
  auto facts = moa::extract(*module, "artifact", "hash");
  EXPECT_EQ((*facts.getArray("functions"))[0].getAsObject()->getString("linkage"), "ifunc");
  EXPECT_EQ((*facts.getArray("events"))[0].getAsObject()->getString("operation"), "xchg");
  EXPECT_EQ((*facts.getArray("events"))[1].getAsObject()->getString("kind"), "llvm.memmove.p0.p0.i64");
  EXPECT_EQ((*facts.getArray("calls"))[1].getAsObject()->getString("kind"), "indirect");
  bool hasComdat = false;
  for (auto &fn : *facts.getArray("functions")) hasComdat |= fn.getAsObject()->getBoolean("comdat").value();
  EXPECT_TRUE(hasComdat);
}

TEST(Reader, ValidInvalidVerifyAndWorkerEntry) {
  llvm::LLVMContext context;
  auto module = parse(context, "define void @f() { ret void }\n");
  ASSERT_NE(module, nullptr);
  Temporary temporary;
  temporary.bitcode(*module);
  auto facts = moa::read(temporary.path.str().str(), std::string(64, 'a'));
  EXPECT_EQ(facts.getArray("functions")->size(), 1u);
  const std::string key(64, 'a');
  const char *args[] = {"worker", temporary.path.c_str(), key.c_str()};
  std::string output, error;
  llvm::raw_string_ostream out(output), err(error);
  EXPECT_EQ(moa::worker(3, args, out, err), 0);
  EXPECT_NE(output.find("ModuleFacts"), std::string::npos);
  const char *version[] = {"worker", "--version"};
  EXPECT_EQ(moa::worker(2, version, out, err), 0);
  EXPECT_EQ(worker_main_under_test(2, version), 0);
  EXPECT_EQ(moa::worker(1, args, out, err), 1);
  const char *shortKey[] = {"worker", "missing", "a"};
  EXPECT_EQ(moa::worker(3, shortKey, out, err), 1);
  const std::string invalidKey(64, 'z');
  const char *badKey[] = {"worker", "missing", invalidKey.c_str()};
  EXPECT_EQ(moa::worker(3, badKey, out, err), 1);
  const char *missing[] = {"worker", "/nonexistent-bitcode", key.c_str()};
  EXPECT_EQ(moa::worker(3, missing, out, err), 1);
  EXPECT_THROW(moa::read("/nonexistent-bitcode", key), std::runtime_error);
  { std::ofstream file(temporary.path.c_str()); file << "not bitcode"; }
  EXPECT_THROW(moa::read(temporary.path.str().str(), key), std::runtime_error);
  { std::ofstream file(temporary.path.c_str()); file << "BC\xc0\xde"; }
  EXPECT_THROW(moa::read(temporary.path.str().str(), key), std::runtime_error);
  auto *terminator = module->getFunction("f")->front().getTerminator();
  terminator->eraseFromParent();
  llvm::IRBuilder<> builder(&module->getFunction("f")->front());
  builder.CreateRet(builder.getInt32(1));
  temporary.bitcode(*module);
  try {
    moa::read(temporary.path.str().str(), key);
    FAIL() << "Verifier accepted invalid return type";
  } catch (const std::runtime_error &failure) {
    EXPECT_NE(std::string(failure.what()).find("verify_failed"), std::string::npos);
  }
}
