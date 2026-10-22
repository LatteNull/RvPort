## Why

当前分析器已经能够在 GCC/Clang 的 C11/C17/C++17/C++20 输入上组合 pthread 生命周期、AST/IR 跨 TU 证据和按 TU 降级结果，但真实 C++ 工程大量通过 `std::thread`、lambda、成员函数和 functor 启动线程；这些调用目前只能进入 unknown，无法形成可审计的 callback、线程对象、实例和 join 证明。A2 已建立可靠的证据可用性与保守降级边界，现在适合在不改变 P1–P4、A1、A2 既有协议语义的前提下，增加受限、版本化的 C++ 线程生命周期分析。

这是运行时分析能力、协议、测试与文档的实现变更，不是纯文档 change。

## What Changes

- 新增独立版本化的 `CppThreadLifecycleRequest v1`、C++ 线程局部事实、标准库 profile、生命周期 overlay 和双语报告；保持 `ModuleFacts v2`、`EffectSummary v1`、`ThreadContextGraph v1`、`PublicationRiskReport`、A1 source-evidence 与 A2 degraded-source 协议原义不变。
- 在经过验证且身份完全匹配的 libstdc++/libc++ profile 下，受限识别 C++17/C++20 `std::thread` 构造、线程对象 move、`join`、`detach`、`joinable`、析构以及构造/调用失败路径；C11/C17 直接 pthread 路径继续独立回归，不依赖 C++ AST 或标准库模型。
- 使用 AST canonical entity、跨 TU definition、SourceIRBinding 和 ABI/LLVM wrapper 证据共同解析自由函数、非捕获/受限捕获 lambda、成员函数和简单 functor callback；不得按名称、类型拼写或单一 mangled symbol 猜测线程入口。
- 建立线程对象与 native handle 的有界 provenance、`ThreadContext`/`ThreadInstance` 分离、条件化 start/exit/join/detach 关系及 move 后所有权转移。只有唯一目标、成功路径与执行顺序证据完整的 `join` 才能补充生命周期顺序；`detach`、析构、`joinable` 或源码书写顺序不得制造 join、synchronizes-with 或 happens-before。
- 建立绑定编译 profile、标准库种类与版本、ABI、target、工具链和模型版本的摘要注册表及系统边界；摘要不匹配、wrapper 漂移、候选歧义、异常/预算前沿或依赖不完整时必须进入 partial/unknown，并参与 A2 候选相关完整性传播。
- 增加版本化缓存、资源预算、确定性、CLI/退出码和中英文字段；不把生命周期图解释为完整 C++ 内存模型、通用 happens-before 求解或全程序安全证明。
- 增加 C++17/C++20 单 TU、物理跨 TU、自由函数、lambda、成员函数、functor、move、join、detach、无 debug、开放 scope、构造失败、ABI/profile 不匹配和预算夹具；分别回归并报告 C11、C17、C++17、C++20 的计划/完成/unknown 分母。
- 明确排除 `std::jthread`、`std::async`、线程池、任意 executor、自定义调度框架、完整 RAII mutex、通用指针分析、fence 和 RMW/CAS；这些构造必须保守进入 unknown/frontier。
- 所有新增、修改或复用的自有可执行代码同步增加正常、边界、异常和 unknown 单元测试；项目整体、实现语言及每个受影响模块的行覆盖率和分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `cpp-thread-lifecycle-modeling`: 定义独立 C++ 线程生命周期请求、局部事实、线程对象/实例 overlay、生命周期关系、报告、预算、缓存和证明边界。
- `cpp-thread-library-profiles`: 定义 libstdc++/libc++ 版本、ABI、target 和 wrapper 摘要注册、采用、失效及系统边界。

### Modified Capabilities

- `gcc-clang-compilation-context`: 将 C++ 标准库种类、版本、ABI 与相关 driver 默认纳入 A3 profile 和缓存身份，同时保持 C profile 独立。
- `clang-source-semantic-facts`: 增加 `std::thread` 构造、对象 move/状态操作和受限 callable/capture 源事实，但不从 AST 产生执行或 HB 证明。
- `cross-tu-program-entity-index`: 增加跨 TU 自由函数、成员函数、lambda/functor 调用实体的精确 declaration/definition 关联和外部边界。
- `source-ir-evidence-binding`: 增加 callable、线程对象操作与标准库 wrapper 的基数化 AST/IR 绑定，禁止单凭名称或 debug location 采用模型。
- `llvm-thread-analysis-facts`: 增加 C++ ABI wrapper、对象/handle token、move、join/detach 和异常出口的独立局部候选事实，不修改既有 pthread 事实语义。
- `thread-context-modeling`: 允许从已验证 A3 overlay 创建 C++ `ThreadContext`/`ThreadInstance` 和条件生命周期，同时维持实例隔离与递归/预算保守语义。
- `thread-order-and-synchronization`: 规定 `std::thread::join` 的受限完成边及 detach/析构禁止生成 join/HB 的规则，继续禁止把候选关系提升为安全证明。
- `thread-analysis-reporting`: 增加 C++ 生命周期 overlay、标准库 profile、证据缺口和中英文字段的独立报告与既有 P3 报告引用。
- `degraded-source-analysis`: 将未知标准库 profile、wrapper、callable、线程对象 provenance 和预算前沿纳入候选相关降级切片。
- `analysis-validation-corpus`: 增加四语言独立分母及 C++17/C++20 `std::thread` 生命周期真值/回归语料，不削弱 C11/C17 pthread 基线。
- `analysis-validation-reporting`: 分别报告 C11、C17、C++17、C++20 的完成度、unknown、缓存、性能和语义结果，禁止用 C++ 新能力覆盖 C 分母。
- `analyzer-unit-test-quality`: 将 A3 所有新增或修改自有模块纳入整体、语言和逐受影响模块行/分支至少 90% 的单元覆盖率与离线验收门禁。

## Impact

- 影响 C++ source worker、LLVM thread-local worker、跨 TU 实体/绑定、线程图组合、A2 降级编排、schema/协议、缓存、CLI、报告、质量入口和离线夹具。
- 可能新增对锁定开发镜像内 libstdc++/libc++ 头文件、ABI 符号和版本元数据的读取，但不得引入网络、SSH、ARM DevKit 或执行被分析程序的核心依赖。
- 现有 C11/C17 pthread 结果、P1–P4/A1/A2 产物和缓存不得因未请求 A3 而改变；A3 产物缺失不得解释为不存在 C++ 线程。
- Windows、MSVC、clang-cl 和 sibling archive 不属于实现或运行依赖。
