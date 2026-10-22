## Why

现有分析器已经能够以直接 `pthread_create` 和经过验证的 `std::thread` 为执行根，但线程入口发现仍分散在 P3、A3 和 R1 中，且源事实没有完整保留构造表达式的语义类型证据。归档的 `memory-model-ir-checker/samples` 还暴露出仅凭名称、源码拼写或接收者启发式会重复识别 `std::async`、误认 `boost::thread`/自定义 `thread`，并遗漏真正 C11/C17 `thrd_create` 等问题，因此需要先建立统一、证据驱动且可审计的线程入口发现层，再扩展后续并发分析。

这是运行时分析能力变更，不是纯文档变更。

## What Changes

- 新增独立版本化的 `ThreadEntryDiscoveryRequest`、`ThreadEntryLocalFacts`、`ThreadEntrySiteIndex`、`ThreadEntryRootOverlay` 和中英文字段齐全的 `ThreadEntryDiscoveryReport`，不重解释既有 P1–P4、A1–A5、A3 或 R1 v1 产物。
- 由 Clang AST 与 LLVM BC 分别发现线程入口候选，取候选并集保留召回率，再以物理 TU、编译 profile、`SourceIRBinding`、ABI、linkage、调用点、callback SSA、源码实体和标准库 profile 对齐验证；仅证据交集完整的候选可成为精确线程创建点。
- 将 Clang 已解析的 spelled type、canonical semantic type、canonical record、constructor declaration/kind、类型别名链、声明来源和标准库 profile 保存为一等事实；区分默认构造、callable construction、move、对象返回和真实线程创建。
- 回归直接 `pthread_create` 及现有 `std::thread` 自由函数、非限定名、类型别名、copy-init、`auto`、`new`、临时对象、lambda、非虚成员函数和简单 functor；新增真正的 C11/C17 `thrd_create` 支持。
- 在经过验证的 libstdc++/libc++ profile 下新增 `std::jthread` 和 `std::async` 入口发现；`std::async` 明确区分 `launch::async`、`launch::deferred` 与实现选择的默认策略，后者只能形成条件化入口和非空 frontier。
- 对同一物理调用点去重，同时分离 callable、线程对象、创建点与动态 `ThreadInstance`；新 overlay 只为 R1 编排提供经过分类的根，不扩展生命周期、同步、happens-before 或风险规则。
- `boost::thread`、Linux `clone`、线程池及 `submit`/`enqueue`/`post` 等自定义框架不得按名称猜测；没有显式版本化模型时保持 `unsupported`/`unknown`。Windows、MSVC 与 clang-cl 明确排除。
- 从归档样例中最小化复制有价值的正反例并记录来源摘要，测试运行时不得依赖兄弟目录；C11、C17、C++17、C++20 分别维护 fixture、truth 分母和诊断断言。
- 为全部新增或修改的项目自有代码补充单元测试，项目整体、实现语言及每个受影响模块的行覆盖率和分支覆盖率均至少为 90%。

## Capabilities

### New Capabilities

- `thread-entry-discovery`: 定义 AST/BC 双源线程入口事实、语义类型归一化、证据对齐、去重、入口分类、root overlay、缓存、CLI、完整性传播和双语报告契约。

### Modified Capabilities

无。既有 capability 的协议和报告语义保持不变，新能力仅通过显式依赖和 overlay 与它们组合。

## Impact

- 影响 Clang source worker、LLVM 局部事实提取、标准库 profile、Source/IR binding、线程入口编排、缓存、CLI、报告及对应 Python/C++ 单元测试。
- 新增独立 artifact/schema 命名空间和离线 truth 语料；需要更新 README、架构说明和 `doc/IMPLEMENTATION_ROADMAP.md`。
- 不引入对 `memory-model-ir-checker`、SSH、ARM DevKit、网络或目标程序运行的依赖；归档项目只作为用例来源。
- 不改变现有风险退出码或安全语义；线程入口证据不完整时必须保持 `partial`/`unknown`，不得据此建立同步或安全结论。
