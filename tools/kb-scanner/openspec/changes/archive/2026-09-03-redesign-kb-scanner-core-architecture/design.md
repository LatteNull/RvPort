## Context

KB Scanner 当前是一个可运行的 Python CLI MVP，已经形成以下主链路：

```text
CLI
  → C/C++、文本与 RPM 扫描
  → FileFacts / CompileCommandContext
  → YAML 规则与生成词典匹配
  → 局部上下文分类和替代实现降噪
  → JSON / HTML Finding 报告
```

它在 x86 痕迹识别深度上已经具备优势，包括大规模 intrinsic、builtin、header、compiler flag、SIMD 类型、汇编、CPU API、构建文件和 RPM 规则。但交叉验证暴露出的主要缺口均要求关联多个事实：Makefile 中目标架构如何驱动源码选择、测试是否会在 RISC-V 执行、宏如何跨文件传播、RISC-V 实现是否真正可达、项目整体迁移到什么程度。继续把这些逻辑放进单一规则求值模块，会让解析、知识、推理、分类和输出进一步耦合。

该模块由规则维护者、扫描器开发者、后端集成人员和迁移工程师共同使用。设计需要同时满足离线 CLI、后端任务运行、可解释报告和持续扩展规则包的需求。

约束如下：

- 聚焦 C/C++ 软件的 x86→RISC-V 迁移，不承担操作系统、内核、系统调用或硬件适配。
- KB Scanner 只负责静态分析。`compile_commands.json` 可以作为已知编译配置的增强上下文，但真实 RISC-V 编译和测试执行属于 RvPort 后续阶段，不进入本模块的核心判定。
- `uname` 等架构探测属于需要追踪的静态选择来源，但本设计假设探测结果与运行机器架构一致，不分析交叉编译导致选错架构分支的情况。
- 现有 x86 深度词典和检测能力属于必须保留的资产。
- 同一证据可能被多个分析器复用，且最终结论必须能追溯到原始文件、位置、解析方式和知识来源。
- memory-model IR checker 是弱内存序分析的权威工具，KB Scanner 不重复建设。

## Goals / Non-Goals

**Goals:**

- 保留现有 Clang/GCC 编译器派生 x86 事实数据和规则引用方式。
- 定义稳定的分层分析管线和模块责任。
- 定义统一、可追溯的事实、关系、发现和项目评估模型。
- 使源码、构建、RPM、测试和编译数据库通过明确边界接入。
- 支持局部模式匹配与跨文件/跨构建变量关系分析共存。
- 将目标架构可达性、替代实现和项目级就绪度变成一等分析结果。
- 允许知识集、规则包和分析策略独立版本化，同时保持现有外部结果结构兼容。
- 为后续多个小型实现 change 提供依赖顺序和验收边界。

**Non-Goals:**

- 本 change 不选择具体 AST、Makefile、Autoconf 或 RPM 解析库。
- 本 change 不决定继续使用 Python 还是更换实现语言。
- 本 change 不实现新扫描器、不迁移现有规则、不修改 CLI 和报告。
- 本 change 不枚举全部 x86 指令、intrinsic 或宏；这些属于知识包内容。
- 本 change 不分析操作系统、内核、系统调用、驱动或硬件平台迁移。
- 本 change 不在 KB Scanner 内实现 RVWMO 并发语义分析。

## Decisions

### 1. 采用“证据图驱动的分层管线”，而不是规则直接遍历文件

目标架构如下：

```text
┌─────────────────────────────────────────────────────────────┐
│ Scan Request：root / target / excludes / policy / context   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Workspace Intake                                         │
│ 文件发现、角色识别、构建入口、compile_commands、排除边界      │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Frontends & Knowledge Providers                          │
│ C/C++ | asm | Make/Autoconf | RPM | test | generated sets  │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Evidence Graph                                           │
│ Entity + Fact + Relation + Provenance                       │
└──────────────────────┬───────────────────────┬──────────────┘
                       ▼                       ▼
┌──────────────────────────────┐  ┌───────────────────────────┐
│ 4a. Local Detectors          │  │ 4b. Relational Analyzers │
│ intrinsic/asm/header/...     │  │ macro/build/test/alt path│
└──────────────────────┬───────┘  └─────────────┬─────────────┘
                       └──────────────┬──────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Classification & Policy                                 │
│ reachability / actionable / blocking / confidence / suppress│
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Project Assessment                                      │
│ dimensions / readiness state / gaps / unknowns / evidence  │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Compatible Report Projection                            │
│ existing scan-result.json + additive optional details      │
└─────────────────────────────────────────────────────────────┘
```

选择该方案，是因为跨文件宏传播、构建选择、测试覆盖和替代实现都可以表达为实体之间的关系，并共享可达性与证据追踪能力。备选方案是继续扩展 `evaluate_rules`，优点是短期改动小，但会重复解析上下文并让每条高级规则自行实现关系追踪，因此不采用。

### 2. 将 Fact、Evidence、Relation、Finding 和 Assessment 分离

核心领域对象定义如下：

| 对象 | 含义 | 示例 |
|---|---|---|
| Entity | 可被引用的程序或工程对象 | 文件、宏、函数、测试、构建变量、源码集合、目标架构 |
| Fact | 前端直接观察到的规范化事实 | 宏定义、函数调用、条件分支、变量赋值、include |
| Evidence | Fact 的出处和质量信息 | 文件/行列、解析器、命令上下文、知识集版本、置信度 |
| Relation | 实体间可推理的连接 | expands-to、selects、guards、includes、tests、alternative-to |
| Observation | 检测器对证据模式的命中 | 发现 x86 intrinsic、发现架构变量控制源码集合 |
| Finding | 经过目标架构和策略分类后的局部结论 | blocker、portability_gap、guarded、hint |
| Assessment | 跨 Finding/Relation 聚合的项目级结论 | multiarch_without_riscv、partial_riscv |

原始证据不可被规则覆盖或丢弃；抑制只影响 Finding 的状态，不删除 Evidence。这样报告既能简洁呈现结论，也能在需要时解释推理链。

备选方案是只给现有 Finding 增加更多字段。该方案无法表达一份证据支撑多个结论、一个结论依赖多条关系的情况，因此不采用。

### 3. 使用轻量、可序列化的内存证据图，不引入图数据库

单次扫描建立有界的内存图，并允许序列化为调试/缓存产物。核心通过稳定实体 ID、关系类型和索引查询图，不依赖外部图数据库。

原因：扫描任务以单项目、离线、可重复执行为主，外部数据库会显著增加部署和故障面。未来若超大项目需要持久化或增量图，可以在不改变领域契约的前提下替换存储实现。

### 4. 前端负责“理解输入”，分析器负责“解释关系”

前端类型至少包括：

- C/C++ 与预处理器前端。
- 汇编源文件前端。
- Make/Autoconf 等构建前端。
- RPM spec 前端。
- compile_commands 提供者，用于补充静态已知的编译单元、命令行宏、include 顺序和编译参数。
- 文件角色识别器，包括 production、test、benchmark、example、generated、vendor、unknown。
- 生成知识集提供者。

前端只产出规范化 Fact 和 Evidence，不直接决定告警严重级别。关系分析器消费多个前端的事实，例如把 Makefile 变量赋值、条件判断和路径引用组合成 `selects(source-set)` 关系。

备选方案是让每个前端直接产生 Finding。该方案实现简单，但会复制目标架构判定、严重级别和降噪逻辑，因此不采用。

### 5. 同时保留快速局部检测与深层关系分析

扫描器提供两个互补分析层，而不是要求所有规则都升级为 AST 或图规则：

- Local Detector：处理 intrinsic、builtin、header、寄存器、明确宏和编译参数等高确定性模式。
- Relational Analyzer：处理宏传播、构建选择、测试角色、目标可达性、替代实现和项目聚合。

两者输出 Observation，由统一分类器产生 Finding。这样可以保留当前词典驱动的高覆盖能力，也避免用昂贵关系分析处理所有文本。

### 6. 保留现有 Clang/GCC 编译器派生 x86 事实数据

以下两个文件作为重写后的保留资产，而不是待替换的临时数据：

- `rulesets/riscv-porting/generated/clang-x86-entries.json`
- `rulesets/riscv-porting/generated/gcc-x86-entries.json`

它们当前共同提供 headers、intrinsics、builtins、vectorTypes、platformMacros 和 compilerFlags 六类事实数据。新架构通过 Knowledge Provider 直接读取现有结构，并继续支持 YAML 规则中的 `generatedSet` 引用。

运行时可以合并并去重两个编译器来源的条目，但必须保留数据来源，不能把两份数据手工复制进 YAML，也不能为了内部模型方便而强制转换成不兼容的新文件格式。重写本身不得删减现有条目；未来若要重新采集或调整生成格式，必须由单独 change 说明来源、生成脚本、差异和回归结果。

### 7. 架构知识使用规范化 ontology，项目标识符作为候选而非事实

架构知识至少区分：

- architecture family：x86、riscv、arm、generic、unknown。
- architecture alias：x86_64、amd64、i386、riscv64 等。
- feature：SSE、AVX、AVX2、AVX512、AESNI、RVV 等。
- implementation role：architecture-specific、portable、fallback、unknown。

像 `ENABLE_X86_FAST_PATH` 或枚举成员 `X86_AESNI` 的模糊命中只产生候选 Observation；只有结合作用位置、分支、被选源码或调用关系后，才能升级为 Finding。注释中的架构词继续作为非阻断 hint，不能与代码标识符规则合并。

### 8. 构建分析以静态“选择关系”作为共同抽象

不同构建系统最终都需要静态回答相同问题：当目标架构是 RISC-V 时，配置逻辑会选择哪些源码、参数、依赖和子目录。统一关系包括：

```text
declares(variable)
assigns(variable, value)
derives-from(variable, source)
guards(block, predicate)
expands-to(expression, value)
selects(target/configuration, artifact)
includes(build-file)
```

Makefile、Autoconf、RPM 和 compile_commands 可以有不同前端，但进入核心后均转换为选择关系。对于可识别的架构探测，分析器按目标 RISC-V 值推导对应分支；无法静态求值的其他动态表达式保持 unknown/partial。

`uname -m` 本身不是风险。分析器把它记录为架构选择来源，并假设在 RISC-V 机器上返回 RISC-V，因此 x86 分支保持 inactive：

- 存在 RISC-V 分支时，继续分析该分支选择的源码和参数。
- 不存在 RISC-V 分支但存在 generic/portable/fallback 时，分析兼容路径是否足以承载 RISC-V。
- RISC-V 分支和通用 fallback 都不存在时，产生“缺少 RISC-V 选择路径”的迁移缺口。
- 不得把最后一种情况解释为 RISC-V 会错误进入 x86 分支。

### 9. 测试是源码单元的角色和静态覆盖关系，不是独立文本规则集

扫描器先识别测试文件/目标，再建立 `tests(test, implementation-or-feature)` 和 `selected-for(test, target)` 关系。由此派生：

- `x86_test_guarded`：x86 专用测试已正确隔离。
- `riscv_test_blocker`：测试会在 RISC-V 构建或执行并造成失败风险。
- `riscv_test_coverage_gap`：x86 路径存在测试，而对应 RISC-V 实现没有覆盖证据。

文件路径只是测试角色的证据之一；构建目标、测试框架注册和命名约定也可以提供静态证据。扫描器只判断测试是否会按静态选择关系进入 RISC-V 测试配置、是否被正确守卫以及是否存在对应覆盖，不判断实际测试执行成败。扫描器不得把所有 tests 目录内容自动视为 blocker。

### 10. 项目就绪度采用“状态 + 维度 + 未知项”，不使用单一分数

顶层状态集合为：

```text
architecture_independent
x86_only
multiarch_without_riscv
partial_riscv
riscv_ready
unknown
```

状态由多个静态维度共同支撑：源码可达性、构建选择、架构依赖、替代实现、测试覆盖和输入完整性。每个维度输出 status、evidence、gaps 和 unknowns。`riscv_ready` 只表示“静态迁移就绪”，不表示真实 RISC-V 编译或测试已经成功；后续构建验证必须单独给出运行结果。

单一百分比分数容易掩盖阻断项，并会把“未能分析”误当成“没有问题”，因此不作为权威结果。后续可以基于维度计算展示性分数，但必须同时呈现阻断项和未知项。

### 11. 规则包、知识包和策略独立版本化，外部报告契约保持稳定

- Rule pack：定义可声明的检测模式和消息。
- Knowledge pack：保存编译器派生词典、架构 alias/feature 和来源元数据。
- Policy：定义目标架构、严重级别、阻断规则、vendor/generated 处理和抑制策略。
- Existing report contract：继续作为下游消费契约，不随内部领域模型重写而替换。

扫描结果必须在现有允许承载版本信息的位置记录扫描器、规则包和适用的知识/策略版本。生成知识集还需记录上游编译器/规范来源，以支持可重复扫描和差异解释。任何新增版本元数据都必须是可选、向后兼容的扩展。

### 12. 内部新模型必须投影为现有 scan-result.json，而不是发布新结果结构

对外继续输出当前 `schemaVersion: "1.0"`，并保留以下顶层结构及其现有字段语义：

```text
schemaVersion
tool
rulePack
project
summary
findings
diagnostics
```

当前后端使用 `KbScannerResult` 导入结果，并具有以下实际兼容边界：

- `schemaVersion` 必须严格等于 `1.0`，否则整次导入失败。
- 顶层 `project` 和 `summary` 以 Map 读取，适合承载可选增量信息。
- JSON 中未知字段会被忽略，因此新增可选字段不会要求当前 parser 切换 DTO。
- Finding 的 `trace` 和 `condition_macros` 会进入后端 evidence；额外 Finding 字段不一定会被后端持久化。
- 当前 artifact 文件名和类型由后端固定识别。

内部 Relation、Observation 和 Assessment 不是新的并列主输出。投影规则如下：

- 局部问题继续写入现有 `findings[]`，保留当前 Finding 字段名、类型和语义。
- 需要被后端保留的关系证据优先写入 Finding 已有的 `trace`；`build_context`、`alternative_impl`、`condition_macros` 等当前字段继续保持原名称和语义。
- 项目评估投影到现有 `summary` 下的可选 `readiness` 子字段；原有计数项保持不变，旧消费者忽略该字段时仍能正常解析。
- 输入覆盖和扫描上下文可以在现有 `project` Map 下增加可选字段，但权威摘要仍通过 `summary` 暴露。
- `scan-report.html` 和 `scan.log` 文件名、用途及 artifact 类型保持不变。
- 不允许删除、重命名、改变类型或重新解释既有字段；不允许新增必填字段。
- 不允许为了暴露新分析能力而要求后端切换到新的主 JSON、专属关系文件或 report v2。

未来每个实现 change 都必须用现有 fixture 和后端 `KbScannerResult`/`KbScanRuntimeService` 契约测试验证兼容性。若某项内部信息无法安全投影，应先保留在内部或 diagnostic 中，并单独评审可选字段，而不是创建新结果结构。

### 13. 将弱内存序作为外部分析结果关联

KB Scanner 可以在统一报告中引用 memory-model IR checker 的工具版本、产物位置和摘要，但不解析线程同步语义，也不把外部工具不可用解释为“没有内存模型问题”。这保持职责单一，并允许项目级评估把该维度标记为 passed、failed 或 unknown。

## Design Drivers from the Cross-validation

| 交叉验证结论 | 对总体设计的驱动 |
|---|---|
| RvPort 对明确 x86 痕迹识别更深 | 保留 Local Detector 和生成知识包，不以重写为由退化 |
| 11 项缺口多为关系问题 | 引入 Evidence Graph 和 Relational Analyzer |
| Makefile 缺口是变量流与选择链 | 用 selection relations 静态推导目标为 RISC-V 时会选择什么 |
| 测试缺口是目标选择与覆盖语义 | 将 test 建模为角色及静态覆盖关系，不分析实际执行结果 |
| 注释提示与模糊宏/enum 不同 | 分离 hint、candidate observation 和 actionable finding |
| 项目就绪度缺失 | 引入多维 Assessment 和 unknown 状态 |
| RVWMO 已有独立工具 | 使用外部结果关联，不重复实现 |

## Risks / Trade-offs

- [风险] 证据图抽象过度，延迟第一批可用能力。→ 只定义满足已知关系分析的最小实体/关系集，未知语义允许保存在 typed attributes 中，新增关系需有实际场景。
- [风险] 多层对象增加学习成本。→ 固定术语和生命周期，并提供从单一 intrinsic 到 Finding、从 Makefile 变量流到 Assessment 的端到端示例。
- [风险] 关系层引用的事实缺少统一身份。→ 为规范化 Fact 定义稳定引用和索引规则，不以文本相同作为唯一身份判断。
- [风险] Clang/GCC 两份事实数据存在大量重叠。→ 加载时按类别去重，同时在知识提供者中保留来源集合，禁止通过删除某一数据源解决重复。
- [风险] 动态构建表达式无法静态求值。→ 识别 `uname` 等明确架构 selector，并按目标 RISC-V 值推导；其他无法确定的表达式输出 unknown/diagnostic，不猜测分支。
- [风险] 项目级状态被误解为迁移完成认证。→ 报告同时展示维度、阻断项、未知项和输入覆盖，不允许只输出一个状态标签。
- [风险] 新增可选字段仍可能触发严格 JSON 消费者失败。→ 新字段进入输出前必须通过当前后端 parser 与 fixture 契约测试；默认优先复用现有 Finding 证据字段。
- [风险] 保持现有结果契约限制新模型表达力。→ 兼容投影只位于报告边界，内部领域模型不复刻现有扁平结构；无法安全投影的信息先不对外发布。
- [风险] 解析器技术选型过早固化。→ 本 change 定义前端契约和语义，不指定第三方库；通过后续 spike 决策。

## Migration Plan

本 change 本身只建立设计基线，不部署运行时代码。后续建议按以下独立 change 推进：

1. 定义 Fact/Evidence、稳定引用、关系类型与现有 `scan-result.json` 的兼容投影规则。
2. 为现有 C/C++、RPM、compile_commands 和 Clang/GCC 事实数据建立接入边界，确保 `generatedSet` 和现有词典覆盖不退化。
3. 引入统一分类与策略层，迁移 guarded、inactive、portability_gap 和 alternative suppression。
4. 实现 Makefile 目标架构与源码选择的最小关系分析。
5. 实现测试角色、目标可达性和三类架构测试结论。
6. 实现宏传播、Autoconf/RPM 深层关系和项目级 Assessment。
7. 接入外部 memory-model 结果摘要，并完成后端产物消费迁移。

每一步都必须能回退到旧扫描器实现，并始终产生现有主输出文件与顶层 JSON 结构，直到同一 fixture 集上的关键能力与精度达到约定门槛。

## Open Questions

- 重写继续使用 Python，还是将核心模型与前端迁移到其他实现语言？该问题应在领域契约稳定后决定。
- C/C++ 深层前端采用 libclang、Clang tooling、tree-sitter，还是分层组合？需要以预处理器保真、部署成本和性能做 spike。
- Makefile/Autoconf 的第一阶段支持“静态部分求值”到什么边界，哪些动态 shell 行为必须标记 unknown？
- 除 `uname -m` 外，第一阶段还应将哪些常见 shell/configure 架构探测表达式识别为可按目标架构求值的 selector？
- `summary.readiness` 的最小字段集合应只包含状态、维度、阻断项数量和未知项数量，还是同时包含证据引用？详细证据可继续放入相关 Finding 的 `trace`。
- vendor、generated、benchmark 和 example 的默认策略应由规则包还是调用方 policy 决定？
