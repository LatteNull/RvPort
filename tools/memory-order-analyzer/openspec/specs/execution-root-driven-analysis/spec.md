# execution-root-driven-analysis

## Purpose

规范独立版本化的 ExecutionRoot 发现、AST/BC 线程创建证据对齐、root 驱动可达规划、完整性、缓存、CLI 和非安全结论边界。

## Requirements

### Requirement: Publish an independent versioned execution-root analysis protocol

系统 SHALL 定义 `ExecutionRootDiscoveryRequest v1`、`ThreadCreationSiteIndex v1`、`ExecutionRootIndex v1`、`RootDrivenAnalysisPlan v1` 和 `RootDrivenAnalysisReport v1`，通过 kind、identity 和 canonical digest 显式引用 scope/profile、P1/P2/P3、A1 及适用的 A2/A3 依赖。R1 产物 MUST 使用独立 schema、artifact 和缓存命名空间，不得修改或重解释 P1–P4、A1–A5 的既有版本、finding、discharged、退出码或安全语义。

#### Scenario: Existing analysis runs without an R1 request
- **WHEN** 调用方只运行既有 P1–P4 或 A1–A5 命令且没有 R1 request/artifact
- **THEN** 既有输出、缓存、root 选择、风险结果和 unknown 语义保持不变

#### Scenario: A referenced dependency was replaced
- **WHEN** request 引用的 scope、profile、AST/IR、P2/P3 或 A3 产物 digest 与实际文件不一致
- **THEN** R1 拒绝组合并输出稳定的中英文引用错误，不扫描目录寻找替代产物

### Requirement: Build a lightweight global view without claiming lazy P1 extraction

系统 SHALL 在显式 `ScopeManifest` 内复用 P1 函数/符号/直接调用、A1 program entity 与 AST–IR binding、P2 adopted call 和 P3/A3 线程候选，建立用于 root discovery 的轻量全局视图。R1 MUST 记录全部 scope members、物理 TU、profile 和输入失败，但不得声称 P1 已改为按函数懒提取，也不得从 `compile_commands.json` 或目录布局猜测目标成员。

#### Scenario: Two targets share source files
- **WHEN** 编译数据库包含共享源码但显式 scope 只选择其中一个目标配置的 artifacts
- **THEN** 轻量视图只包含该 scope 的成员并保留其他记录为 scope 外，不将共同路径解释为同一目标

#### Scenario: P1 still contains facts for unreachable functions
- **WHEN** ModuleFacts v2 包含未进入 R1 reachable plan 的普通函数和内存事件
- **THEN** R1 可将其标为未需求但不得删除、重写或声称底层未提取这些事实

### Requirement: Discover AST and BC thread-creation candidates independently

系统 SHALL 分别从可信 AST/source facts 与已 parse/verify 的 BC/LLVM facts发现线程创建候选，并以集合并集形成 `ThreadCreationSiteIndex` 的初始分母。每个候选 MUST 保存物理 TU、profile、source/IR call identity、runtime/API model、callback source entity、callback SSA candidates、参数/receiver、handle/object线索、成功条件、支持和反对证据；一侧缺失不得删除另一侧候选。

#### Scenario: Direct pthread creation is visible in both layers
- **WHEN** C11/C17 或 C++ 源码和对应 BC 都包含 ABI 相容的直接 `pthread_create`，且 callback 唯一绑定
- **THEN** 索引合并为一个创建点并同时保留 AST 与 IR 证据，不发布两个动态线程实例

#### Scenario: Optimization removes the recognizable source shape from BC
- **WHEN** AST 保存线程创建候选但 build-faithful BC 无法唯一恢复对应 runtime call
- **THEN** 索引保留 source candidate 与缺失 IR frontier，不把它解释为没有线程

#### Scenario: No-debug BC contains an exact direct pthread call
- **WHEN** AST 不可用但 verified BC 中直接 pthread ABI、scope definition 和 callback SSA 目标均唯一
- **THEN** 索引保留 IR 候选并允许按受限规则评估为 `ir-exact`，同时标明源码完整性不可用

### Requirement: Align creation evidence with conservative classifications

系统 SHALL 结合 physical TU/profile、SourceIRBinding、linkage/visibility、ABI/target/DataLayout、调用点、callback identity、标准库 profile 与 opposed evidence，将创建点分类为且仅分类为 `dual-exact`、`ir-exact`、`source-candidate`、`ambiguous`、`unsupported` 或 `failed`。只有 `dual-exact` 和满足受限 runtime 模型的 `ir-exact` MAY 创建正式线程 root；其他分类 MUST 进入非空 frontier。

#### Scenario: AST and IR callbacks disagree
- **WHEN** source call 唯一指向函数 A，而绑定到同一创建点的 IR callback 唯一指向不兼容函数 B
- **THEN** 创建点为 `ambiguous` 并保存双方证据，不按任一侧任选 root

#### Scenario: A standard-thread profile does not match
- **WHEN** AST 明确存在 `std::thread` 构造但 vendor、版本、ABI、target、wrapper digest 或 A3 profile 不匹配
- **THEN** 创建点为 `unsupported` 或 `ambiguous`，不得仅凭构造类型或 mangled name 创建线程实例

#### Scenario: A source-only callback exists
- **WHEN** AST callback 实体唯一但 BC 生成、IR binding 或 runtime wrapper 证据失败
- **THEN** 创建点为 `source-candidate`，可进入计划 frontier但不得建立 ThreadInstance、MHP 或风险结论

### Requirement: Model explicit execution roots without name guessing

`ExecutionRootIndex` SHALL 支持用户显式程序 root、请求允许且 closed scope 内唯一相容的 `main`、用户显式库导出 root、已验证 pthread callback、A3 已验证 `std::thread` callable 和用户显式框架线程入口。root identity MUST 绑定 scope、profile、program entity、artifact/function、来源、父创建点或 external-parent 语义和抽象参数；同一 callable 的不同创建点或显式外部入口不得合并为一个动态实例。

#### Scenario: Unique main discovery is enabled
- **WHEN** 请求允许自动发现 main，closed scope 中只有一个 ABI/profile 相容的 external `main` definition
- **THEN** 索引发布一个 program-entry root并引用完整实体集合证据

#### Scenario: A library has no main
- **WHEN** scope 表示库且用户显式列出两个 exported roots
- **THEN** 两个 roots 以 external-parent 语义分别进入计划，不从任意 exported 符号名称自动增加入口

#### Scenario: One callback is created at two callsites
- **WHEN** 两个 exact 创建点使用同一 callback definition
- **THEN** roots 可复用分析 context，但保留两个不同创建来源和实例身份

### Requirement: Expand a bounded reachable analysis plan from roots

系统 SHALL 从正式 ExecutionRoot 沿 scope 内 A1/P1 唯一直接绑定、P2 adopted direct-call edge 与明确支持的 wrapper 摘要执行确定固定点扩展，生成 reachable function、context、physical TU、thread-creation demand 和 P2/P3 roots 请求。间接/虚调用、歧义定义、开放外部边界、递归 SCC、重复创建和 context/path 预算 MUST 保留已知可达项并产生 frontier，不得切换到 `all-defined` 或把未遍历项当作不可达。

#### Scenario: A direct wrapper creates a pthread across TUs
- **WHEN** root 经唯一 adopted direct call 到另一 TU 的 wrapper，wrapper 中创建点和 callback 均 exact
- **THEN** 计划包含 wrapper context、callback root、所需 TU 和每条采用证据，无需 llvm-link 或运行目标程序

#### Scenario: An indirect call may create a thread
- **WHEN** reachable context 包含无法唯一解析的间接调用且候选可能到达线程创建 wrapper
- **THEN** 计划登记 `indirect-call-frontier` 和相关候选，不声称其后所有线程 roots 已覆盖

#### Scenario: Recursion reaches the context budget
- **WHEN** 递归或重复 wrapper 展开命中 context/SCC 预算
- **THEN** 已知 contexts 保留，重复部分合并且 root/reachable completeness 为 partial，不发布完整空后继

### Requirement: Keep C and C++ discovery profiles independent

R1 SHALL 分别支持 GCC/Clang 的 C11、C17、C++17、C++20。C 路径 MUST 使用 C linkage、直接 pthread ABI、C AST/IR callback 与用户显式 root，不得依赖 C++ AST 类型、libstdc++/libc++ 或 A3 profile；C++ `std::thread` 采用 MUST 绑定已验证 A3 library profile。Windows、MSVC 与 clang-cl MUST 明确拒绝或报告 unsupported。

#### Scenario: C fixtures pass without C++ profiles
- **WHEN** C11/C17 scope 只有直接 pthread roots且没有任何 C++ 标准库 profile
- **THEN** R1 可完整生成 C root plan，不要求或伪造 C++ profile

#### Scenario: One language denominator is missing
- **WHEN** 验收只提供 C++17/C++20 truth而没有 C11 或 C17 的 planned/completed/root/frontier 结果
- **THEN** 四语言语义验收失败，不能合并分母或用 C++ 覆盖 C 路径

### Requirement: Report root and reachable completeness without safety claims

`RootDrivenAnalysisReport` SHALL 分别报告计划/发现/对齐/正式/候选/ambiguous/unsupported/failed 创建点与 roots，以及 reachable function/context/TU、P2/P3 demand、frontier 和候选相关依赖切片。任何相关 root、创建点、调用边、TU、profile 或预算不完整 MUST 使请求为 partial；无 root、零创建点、零 finding 或下游 exit zero MUST NOT 表述为没有线程、没有风险或程序安全。R1 固定 `safety=not_evaluated`、`findings=null`。

#### Scenario: An unrelated TU fails
- **WHEN** 失败 TU 已证明不在任何正式 root 的可达/创建依赖切片中
- **THEN** 对应 root plan 可保持 complete，同时顶层报告保存该 scope failure及其无关证据

#### Scenario: A relevant root is AST-only
- **WHEN** 用户计划入口的线程创建链只形成 source candidate
- **THEN** root coverage 与相关 plan 为 partial，退出码不得表示完整成功

#### Scenario: No thread creation is found
- **WHEN** 索引没有正式或候选线程创建点
- **THEN** 报告区分完整扫描后的零创建点与输入/预算失败造成的零创建点，二者均不产生安全结论

### Requirement: Bound resources and cache deterministic root plans

请求 SHALL 限制 scope members、TU、source/IR candidates、binding candidates、roots、functions、contexts、call edges、wrapper depth、SCC iterations、frontier、诊断、worker/request 时间和输出字节。缓存键 MUST 包含协议/schema/实现、LLVM/Clang、scope/profile、全部依赖、root seeds、wrapper/model 和预算 identity；损坏、陈旧、failed、timeout 或 wall-clock partial 条目不得作为成功命中，cold/warm semantic digest MUST 一致。

#### Scenario: Root budget is exhausted
- **WHEN** exact 创建点数量超过 root limit
- **THEN** 已知 roots、hit/limit 和未处理创建点保留，报告 partial并产生非空 budget frontier

#### Scenario: A dependency digest changes
- **WHEN** cache 结构有效但 source/IR binding、P2 adoption、P3 或 A3 profile digest 变化
- **THEN** 系统拒绝旧计划并重新分析或明确失败，不复用旧 reachable 集合

### Requirement: Expose a deterministic bilingual R1 CLI

系统 SHALL 提供独立 CLI，接受显式 request、artifact store、source/IR worker 和全新 output，确定排序输出请求快照、创建点索引、root 索引、分析计划和报告。退出码 `0` 表示请求范围内 root discovery/planning complete，`2` 表示 partial/unknown/unsupported/frontier，`1` 表示无效或全部不可用；R1 MUST NOT 返回风险码 `3`。用户诊断 SHALL 同时提供中文和英文 detail、limitation 与 suggestion，机器 code/identity 不依赖翻译。

#### Scenario: The output directory already exists
- **WHEN** 调用方指定已存在的 R1 output 目录
- **THEN** 命令拒绝覆盖并返回结构化失败报告

#### Scenario: Planning completes with no risk evaluation
- **WHEN** root discovery、对齐和 reachable plan 全部 complete
- **THEN** CLI 返回 `0`，同时报告明确 `safety=not_evaluated`、`findings=null` 和“尚未运行 R2/P4 风险消费者”的双语限制
