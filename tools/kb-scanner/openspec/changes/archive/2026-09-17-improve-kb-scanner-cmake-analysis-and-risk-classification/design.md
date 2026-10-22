## Context

demo-test1 首次扫描 `0553c2c6-e13a-49e1-9960-4d0932f673dd` 使用源码版本 `824b32c0-2d38-414f-8ee8-e0a583d21871`，结果为 19 个 Finding：18 medium、1 low。局部 AVX/向量类型/cpuid 证据被统一投影为 medium；`immintrin.h` 的 `input-or-relation-unknown` 却投影为 low/complete。原始 JSON 已如此，并非 UI 降级。该次 compdb 标记 USED，但部分上下文关联缺失；不能把所有断链都归因于单条 Diagnostic。

CMake 源码先用 `NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$"` 触发 `FATAL_ERROR`，之后才声明 vectorcalc 及 `-mavx2/-msse4.2`。当前正式路由主要支持 CMake 机器 JSON，不能据此恢复源码控制流。第二次扫描使用不同源码版本，不作本次前后对照。

本设计以当前默认 V2/显式 V1 为准；旧 config.yaml 中 schema 1.0 的描述不作为退回旧结果的理由。

## Goals / Non-Goals

**Goals:**

- 一次打通 CMake 源码事实 → 有界选择/拒绝证明 → 风险分类 → 已有结果展示。
- 准确表达“依赖已确认但目标影响待补证”，而非高风险等同阻断、未知等同低风险。
- 用固定源码、人工 oracle、隔离单元和合同测试验收这两个问题。

**Non-Goals:**

- 完整 CMake 解释器、执行 configure/build/test、模拟交叉编译误选、后端输入协议改造。
- 任意 function/macro、生成器表达式、外部 package 查找、动态下载、完整 `#error` 终止求值。
- 以发现 CMake 文件或出现 RISC-V/scalar 关键词直接证明支持；以 scalar 尾循环证明独立通用实现。
- 重算历史数据库、部署生产服务、修改 GCC/Clang 事实数据。

## Decisions

### 1. 独立 CMake 源码适配边界

新增源码 adapter，独立于已有 File API JSON adapter；发现 `CMakeLists.txt` 和 workspace 内普通 `.cmake`，保留文件/命令/参数 span。孤立的 `.cmake` 可以提取事实，但只有由已知入口引用才参与该配置的确定求值。第三方节点不得穿过 frontend；立即转换成 scanner-owned records。

实施开始先在独立测试容器评估可复用的 CMake 语法解析器，验证许可证、维护状态、锁定版本、命令/引号/括号参数/注释/多行位置、错误恢复及原生 ABI。现有 tree-sitter 技术栈是候选，不预先宣称某 grammar 可直接兼容。若候选不可用，记录证据后采用有界词法/命令解析，不能退化成逐行关键字正则或扩大成完整解释器。选择记录与依赖锁在进入实现门禁前定稿。

### 2. 静态子集和未知污染

首批支持字面 `set`、简单变量/列表展开、`list(APPEND)`，`if/elseif/else/endif` 的括号、NOT/AND/OR、已知布尔量、STREQUAL 与可安全解释的 MATCHES；恢复 `add_library/add_executable/target_sources`、`target_compile_options/target_compile_definitions`、目录级 compile options/definitions，以及有界本地 `include/add_subdirectory`。必要的 include directories 和本地 target_link_libraries 关系用于作用域/usage requirement 追溯，不模拟链接。

从 ScanContext 取得目标 CPU；不从宿主机或 x86 compdb 借用 RISC-V 的系统、编译器、cache 值。普通变量、目录/子目录、target PRIVATE/PUBLIC/INTERFACE、编译配置与参数顺序分离建模。`option`/CACHE 等外部可覆盖输入，未有适用配置证明时不得仅按默认值确定分支。未知函数、动态 include、生成器表达式、策略依赖语义和未知命令的潜在写入必须污染相应求值结果；无法界定影响范围时将当前后续作用域降为 unknown，不能跳过后继续使用旧变量宣称确定。

限制字节/命令数、展开深度/值数、include 深度、路径访问、图新增量和匹配复杂度。只解释支持的正则子集；不支持/过长/复杂模式返回 unknown，避免不受控正则运行。根外、缺失、循环、错误恢复和预算耗尽都有可定位 Diagnostic。与 CMake 官方 [if](https://cmake.org/cmake/help/latest/command/if.html)、[message](https://cmake.org/cmake/help/latest/command/message.html) 和 [CMAKE_SYSTEM_PROCESSOR](https://cmake.org/cmake/help/latest/variable/CMAKE_SYSTEM_PROCESSOR.html) 语义逐项对照，无法等价支持的形状保持 unknown。

### 3. 拒绝路径与目标选择分开

对已确定入口、目标条件和执行顺序的 `message(FATAL_ERROR)` 建立配置拒绝 proof，复用 `missing_riscv_selection_path` Observation，并携带内部 source kind、配置范围、必需性、控制流与拒绝依据。只有入口对当前扫描范围确实必需、条件完整且到达 fatal 的路径完整，才能作为该范围的 blocker。可选子目录、未引用片段、条件未知均不能作为整个项目拒绝证明。

明确记录终止点，之后的命令仍保留源码 Fact，但不再产生该次配置的 selected target/source。也不能把“配置先失败”伪装成“x86 代码被互斥条件安全隔离”，后续局部依赖保持自身风险与目标适用性未知。另设移除前置拒绝的最小 fixture 验证 target/source/flag 闭包，不能用原项目不存在的实际选择路径凑完整链。

### 4. 目标作用关系与配置身份

用 CMake 自身 target identity/source path 闭合关系，不复用 Make 的文件名/recipe 匹配假设。参数只作用于已证明归属、传播方向和配置的源码；`-D`/`-U` 连接已有宏绑定器，保留顺序和源码覆盖。没有预定义宏映射证据时，`-mavx2` 不直接变成任意用户宏，也不自动证明 `__AVX2__` 的目标值。

x86 compdb/File API 表示已观察的源环境，与 RISC-V 静态推导并存；冲突保留双方 provenance 并 unknown，不静默覆盖。CMake 根入口或 target 范围不明时不放大到全项目。新增图预算仍按本阶段新增量计算，不能因继承源码图变大跳过构建分析。

### 5. 用共享策略分离风险和证明强度

风险判断在 scanner-owned classification/presentation policy 中统一产生，V2 和显式 V1 适配已有字段，不从 V1 JSON 生成 V2。扩展内部决策 metadata 即可，不增加外部必填字段或枚举。至少按以下优先关系处理：完整互斥排除优先；确定阻断需闭合 proof；未排除的确认依赖保留高风险；纯候选不冒充确认依赖。

| 情形 | severity | status | actionable / blocking |
|---|---|---|---|
| 目标必需配置的显式拒绝，或目标确实选中 x86 执行依赖，证明完整 | high | complete | true / true |
| 已确认 intrinsic、向量类型、x86 指令/参数或精确知识确认的专用头文件，但目标适用性未闭合 | high | partial；必要关系完全未知时 unknown | true（需核查处理） / false |
| 仅架构名称、宏或枚举候选，执行依赖尚未确认 | medium（待核查优先级） | unknown/ambiguous | false / false |
| 完整证明 x86 路径被目标互斥排除 | low | inactive | false / false |
| 纯注释线索 | info | 已有适用状态 | false / false |
| 已证明的普通迁移/测试缺口或软依赖 | 保留其适用策略，通常 medium | 按实际完整性 | 不因本次修复一律阻断 |

severity 表示迁移处理优先级，不表示置信度；actionable 表示已有具体依赖可供处理，不要求所有上游完整；blocking 始终需要当前范围完整证明。保留原 confidence 的事实置信含义，不用 1.0 推断目标影响已确定。status 表达当前结论完整性，evidenceChain status 表达链完整性，代码上下文缺失等展示问题不反向抹掉已证明结论。

`immintrin.h` 若已精确命中架构知识，系统 include 内容未展开不能单独抹掉其架构归属；影响/可达性仍可未知。未知 relation 只影响它能影响的结论，不让无关 unresolved include 否决所有 proof。宏名 `__AVX2__` 不因名字或相邻 intrinsic 自动升为 blocker；必须逐项审校其用途。未知项不再走 severity 默认 low 和 status 默认 complete。

### 6. 现有结果直接展示

保持 schemaVersion 2.0、核心字段/枚举及默认 V2/显式 V1、三个 artifact。复用源码型 step 和现有关系，必要的 CMake 细节放合法命名空间 extensions；classification/assessment 不放回 evidenceChain。每个代码节点保留真实 span、命中高亮及上下各 20 行，未知上游有明确 break。新增 reason 对应成对中文 suggestion/英文 suggestion_en；部分结论说明“依赖已确认、目标适用性待核查”，不把高风险说成已验证编译失败。

V1 字段形状保持兼容，但已被修复的风险值允许随同一内部判断变化。JSON/HTML/log 各自支持的风险展示必须一致；不修改后端/UI，历史报告不自动重写。schemaVersion 不变不意味着结果值完全相同，差异要逐项记账。

### 7. 测试与审校

固定第一份源码版本、输入清单/哈希及报告摘要，脱敏并排除运行凭据；oracle 人工维护，不能自动把新输出覆写成正确答案。原 19 项逐一记录保留、聚合、严重性/状态/依据变化，新增 CMake 拒绝及参数事实独立记录，不以 Finding 总数作结论。原项目至少要正确给出适用范围的配置拒绝；不要求原 19 项全部 high/blocking。原 scalar 循环仅为尾部处理，不作为完整 fallback。

| 模块边界 | 隔离单元断言与替身 |
|---|---|
| workspace / CMake adapter | 文件路由、span、错误/超限；mock parser，临时目录验证路径 |
| evaluator / scope resolver | 表驱动变量/条件/终止/传播/未知污染；scanner-owned records，无真实 CMake |
| normalizer / analyzer / detector | target-source 与宏桥接、配置隔离、proof 引用、预算；合成 snapshots |
| classifier / assessment / 风险策略 | 上述风险矩阵、局部与项目范围、未知 relation 相关性、互斥优先级 |
| V2/V1 mapper / suggestions / renderer 接线 | 同一内部结论映射、双语、状态、引用、上下文；fake 下游/IO |

新增/修改模块逐项登记 test inventory。统计包含未被单测加载的 `kb_scanner/scripts/tools` 自有可执行源码；整体及各受影响模块都必须达到 90% 行和 90% 分支。原生 parser 组件测试、完整管线/合同/真实项目回归单列，不混入隔离单元达标数字。无法满足或需大规模历史改造则报告并请求扩大范围，不能缩小分母。

## Risks / Trade-offs

- CMake 是可编程语言 → 明确支持子集、作用域污染和预算，接受一部分 unknown，不执行补证。
- 将未知目标适用性的确定依赖调高可能增加 high 数量 → 展示高风险但非 blocker、具体缺失依据与核查建议，保留完整排除降级。
- 配置提前终止后路径容易伪造 → 分开拒绝 proof、声明事实、实际选择，分别设反例。
- 公共风险策略影响既有 Make/RPM/Autoconf/enum → 固定回归，保持软依赖等专属规则，不全局把 missing-path 升为 blocker。
- parser 原生崩溃或语法版本差异 → 容器锁定、继承现有隔离/故障边界、畸形输入组件测试；不得绕过已有安全机制。

## Migration Plan

先固定基线与 parser 选择，再接入源码事实/证明，随后统一风险与投影，最后完成隔离覆盖及端到端审校。所有测试仅用独立 `kb-scanner-test`；不改现有生产 Compose、不重建生产镜像。保留知识数据前后 SHA-256、显式 V1 合同及其他功能回归。

本 change 不迁移数据库。未来由用户决定部署/重扫；回退代码版本即可回退 producer 行为，无外部 schema 迁移。覆盖或审校失败不得勾选完成，也不能提示归档就绪。

## Open Questions

- CMake parser 的具体包/版本在实施第一步容器验证后确定，不能在验证前新增宿主机依赖。
- 首次扫描的 compdb 原文件若不可取回，用真实源码的固定最小样例验证同类关系并标注限制；不得把重建 compdb 说成原始输入或声称精确复现全量旧报告。
