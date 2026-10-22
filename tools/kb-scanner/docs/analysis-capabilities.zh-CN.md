# 源码分析与能力边界

[English](analysis-capabilities.md) | 简体中文

只描述现有静态能力。这里分析被扫描工程的测试源码，不执行测试，也不是迁移中已排除的 E2E 设施。零命中不表示可编译或可运行。

<a id="doc-architecture-enum-analysis-baseline"></a>

## 架构枚举

## 冻结事实数据

| 文件 | SHA-256 |
|---|---|
| `rulesets/riscv-porting/generated/clang-x86-entries.json` | `adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7` |
| `rulesets/riscv-porting/generated/gcc-x86-entries.json` | `22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191` |

上表为开源迁移后的冻结摘要。GCC 数据仅将来源路径脱敏为 `vendor/gcc/gcc/config/i386`，事实内容不变；旧报告中的摘要仍代表原版本，不用当前摘要回写历史证据。当前 bytes、category、source identity 和加载路径由回归合同保护；枚举分析只复用已加载的 `targetFeatures`、`architectureAliases` 和适用 `platformMacros`。

## 行为边界

- 有界输入：只提取 enum 声明、成员声明，以及能绑定到声明成员的条件/case 引用；普通变量、注释、字符串和任意 identifier 不进入枚举 Evidence。
- 名称命中只是 candidate。孤立名称为 unknown；只有声明—引用—选择—真实 x86 依赖关系闭合后才升级。
- template-dependent、动态、歧义、恢复解析或缺失绑定保持 unknown；RISC-V/generic/portable/scalar 只作为 sibling，ARM 只作上下文。
- Schema V2 默认使用既有 `architecture_probe`、`source_evidence` 和既有 edge kinds；细节写入 `org.rvport.kb-scanner.architecture-enum` extension。
- 显式 V1 中，`if constexpr` 继续使用 `CPP.X86.CONSTEXPR_ARCH_BRANCH`，其他枚举候选使用 `C_CPP.X86.ARCH_ENUM_CANDIDATE`。

<a id="doc-architecture-candidate-noise-baseline"></a>

## 候选准入与去重

## 实现边界

1. 锁定的 tree-sitter-c 0.24.2 / tree-sitter-cpp 0.23.4 都使用 `gnu_asm_expression`。只有完整容器生成 inline_asm Evidence，qualifier、constraint、operand、clobber 不再各自生成事实。MS asm 没有受支持的独立节点；未知 asm 结构给 Diagnostic，不猜测节点名称。保留 SourceByteIndex，禁止读取原生 Point。
2. asm/attribute 保留完整文本与 byte span；相同源位置的不同 producer 合并 provenance，不同位置和显式 compilation context 保持独立。没有更换全局事实身份方案。
3. foreign 不是汇编指令黑名单。仅用显式 ARM/AArch64 编译器 selector 与可追溯的同文件宏定义证明必要条件。`ARMCRC32` 这个名字本身不算证据。定义歧义、前向定义、相关 undef、宏循环、否定和不支持的表达式都不用于排除。
4. AND 至少一个必要 ARM 条件可成立；OR 每一边都需能证明。`x86 || aarch64` 保留 x86 线索；`x86 || UNKNOWN` 不可直接断定 RISC-V 上不生效。else 不借用前一个分支的 ARM 标签。最内层未知 guard 仍保守保留候选，不在本 change 进行全局布尔求解。
5. 文件其他位置的 ERROR 不应污染完整的条件/宏定义/asm 构造。Frontend 的 `structureComplete` 检查相关表达式/构造的 byte 范围；只有 foreign guarded_by 的全部相关证据局部完整时，才允许该关系为 complete。文件诊断照常保留；条件或 asm 自身不完整时不排除。
6. Detector 优先使用已加载的 x86 KnowledgeEntry。确定命中不会被 foreign 排除；无确定命中且 foreign proof 完整时不生成 x86 Observation；其余 asm 为 `candidateBasis=unclassified_inline_asm`。结构属性候选需有 target、target_clones、vector width 等属性名称，字符串和注释中的名字不算属性语义。普通 no_sanitize/aligned/visibility 类属性不准入。
7. Classifier 对非法候选给结构化 INFO 合同诊断，并从 ClassificationSnapshot 中移除，因此不进入 Assessment。V1/V2 Projector 再次校验；绕过分类合同的输入会使投影失败、不发布新 artifact，保留原 artifact，不能静默伪装为成功过滤。

V2 仍默认，V1 必须显式选择；固定输出 `scan-result.json`、`scan-report.html`、`scan.log`。V1 log 原本只有诊断与 readiness，不新增 finding 列表。上下文允许包含邻近 ARM/普通属性代码；测试检查 finding 的命中根，而不是禁止报告出现这些词。

<a id="doc-architecture-family-analysis"></a>

## 架构实现家族

## 可以回答什么

在同一次授权文件清单中，发现 `foo_x86.cpp` / `foo_generic.cpp` / `foo.cpp`，或 `arch/x86/math/foo.cpp` / `arch/riscv/math/foo.cpp` 等局部家族；即使没有构建数据库、文件为空，也可以记录路径线索。复用既有 source file 身份，不再次遍历磁盘。

文件名前后缀和目录角色槽位是两种模板，第一版只支持单槽位。完整父目录、角色目录外路径和扩展名保留在 key 中，不跨 vendor/子项目按 basename 聚类。多槽位冲突及大小写碰撞保留歧义；无角色文件为 unlabelled，不自动当成 generic。只有存在 x86 角色候选的家族才进入本次目录，ARM 成员仅作上下文。

词表中的 amd64/x64、AVX/SSE、generic 等是版本化路径启发式，不是新采集的编译器事实；角色提示保留原词与规则名。两份 GCC/Clang 事实 JSON 未修改。

## 不会据此断言什么

- 名称为 generic 不证明没有 AVX，名称为 x86 也不证明使用了 x86 指令。
- 发现通用候选不能消除已有 blocker；未发现通用或 RISC-V 文件不能新增 portability gap。
- 同 target 共同编译两个文件不等于它们互为替代；不新增 `alternative_to` 或函数等价证明。
- `discoveryStatus=complete` 仅表示授权清单中的受支持模板已处理完，不是项目所有替代实现都已找到。
- 本次不补齐函数多版本 fallback、跨函数值流、复杂宏或动态构建语义。

## 已有证据如何接入

新增 `candidate_member_of` 是非执行结构关系，没有伪造的源码 Evidence；不进入源码主链。已有 proof 按成员及 configuration 校验后可绑定，保留 selected/inactive/not_selected/unknown 和实际来源文件/行号。原来的 Evidence、Fact、Classification、Assessment 和 proof 不改写。

来源描述只是绑定的溯源信息，不是重新生成的调用链；对外不输出无法在 Finding 内解析的内部 proof/relation ID。原有源码链、命中高亮、上下各 20 行和 suggestion/suggestion_en 保持。

Make/CMake 中存在可定位的 source selection proof 时可以展示；只有变量赋值、没有与文件闭合的 Autoconf 事件时绑定仍为空/unknown。本次不让家族分析器补做 Shell 或构建解释。

## 报告位置

默认 V2 使用已有 namespace `org.rvport.kb-scanner.architecture-family`：

- 顶层 `extensions`：有界候选目录；没有代码 Finding 的纯路径家族也可见。
- 相关 Finding 的 `fact.extensions`：内嵌自身需要的成员和绑定信息，不依赖顶层目录。
- HTML：有界中文家族摘要，路径安全转义；纯路径没有虚假第 1 行、源码高亮或跳转链接。
- 显式 V1：保持原有字段和 Findings；不塞入只有路径的伪代码 Finding。

新增解释有 `explanation` / `explanation_en`。不修改核心 V2 schema、枚举或三个 artifact，不要求后端接入新参数。旧 reader 可忽略 extension；展示增强需要消费者自愿使用它。

## 预算和限制

内部默认最多处理 100000 路径、10000 家族、每家族 128 成员、4096 proof 绑定/10000 proof steps、10000 新结构关系。V2 catalog 上限为 1000 家族/10000 成员；每个 Finding 上限为 8 家族/128 成员；每成员最多展示 32 个绑定、每绑定 64 条来源。

截断具有稳定原因和计数，发现与展示状态分开。按模板分桶，不进行全量两两比较、不重新搜索 proof。source parseStatus 在组合前端不完整时保守显示 unknown，不能把它理解为每个文件都已证实解析失败。

示例 fixture：`tests/fixtures/architecture-family-demo/`；分组人工 oracle：`tests/fixtures/architecture-family-oracle.json`。该 fixture 用来证明候选和选择关系，不主张两份示例函数的 API 或行为等价。

<a id="doc-function-multiversion-analysis"></a>

## 函数多版本

## 固定语义矩阵

参考日期 2026-09-22。官方依据：[GCC 多版本](https://gcc.gnu.org/onlinedocs/gcc/Function-Multiversioning.html)、[Clang 18.1 属性](https://releases.llvm.org/18.1.8/tools/clang/docs/AttributeReference.html#target-clones)。本轮首先固定 Clang 18.1、x86/x86-64、C/C++ 的 target_clones 和 C++ target 语义；其他组合不能由该规则自动外推。scanner 使用的 libclang 版本不是被扫描项目编译器的版本。

| 构造 | 结构结论 | 默认实现规则 |
|---|---|---|
| 单个 target 特化 | 不是缺失 default 的充分条件 | 不生成缺口 |
| 同函数不同 target | 局部多版本候选 | 仅在适用规则和局部范围完整时判断缺口 |
| target_clones 字面量列表 | 一个源体与多个版本描述 | default token 与 body 分别检查 |
| default 只有声明 | 声明存在 | 不能认定实现已具备 |
| default 的 body 含 AVX | 原 x86 事实保留 | 不证明 RISC-V 可用 |
| cpu_dispatch/cpu_specific、target_version、宏/pragma、模板 | 未决/不支持范围 | 不套用本轮 default 规则 |

现有输入没有可靠 compiler version/source-target 时，profile 保持 unknown。可执行文件名、编译成功、compiler facts 的生成工具版本和 scanner parser 版本都不能代替项目编译器身份；不运行命令补证据、不增加后端必填输入。任何无法确认的支持组合只输出结构信息及未知原因。

## 已接入能力与边界

- Tree-sitter 只物化有相关属性的自由函数及匹配声明；保留原属性 ID/值，并提供限定签名、owner 和函数体范围。可选 Clang 仅补充 scanner-owned 标量，冲突不覆盖基线。
- 识别单 target 特化、多 target 定义、target_clones 共享体；default 存在、声明/实现、组完整性、body 依赖与目标适用性分开表达。
- 复用已有 intrinsic/feature 与 source/build proof；同一行按列范围、嵌套体按排除范围关联，版本成员不参与执行可达，不按 clone 数复制 occurrence。
- 完整排除必须覆盖整个相关属性组；跨配置、局部排除或未知选择保持 unknown。外国架构保护下的属性不新增 x86 迁移问题。已有 confirmed x86/high/blocker 不因 default 被撤销。
- V2 顶层与单 Finding 均使用 `org.rvport.kb-scanner.function-multiversion`，与架构家族等 namespace 合并。真实 attribute → function → body fact 进入源码链，仍为 ±20 行。选择绑定展示真实来源，不外泄悬空 proof ID。V1 保留现有字段，新增规则映射及双语建议，不改变核心 schema。
- 源码/关联/展示均有独立预算。语义绑定和选择来源共享展示预算；截断保留计数，不把未显示 default 当作缺失。

未知范围：复杂签名、类型别名、方法/模板、宏包装、pragma、跨 TU 完整性、cpu_dispatch/IFUNC、运行时选择、跨函数行为等价，以及真实目标编译验证。本轮没有增加后端必填输入，也没有执行项目或编译器探测。

<a id="doc-macro-and-build-effect-proofs"></a>

## 宏与构建参数作用

## 能看到什么

例如 `OUTER(_mm256_add_epi32, value)`：实参是原始 fact；若 `OUTER → INNER → fn(value)` 的绑定成立，证明会连回实参的真实行列。Finding 的链路可追溯参数来源、实际编译 recipe/target 使用、预处理条件、宏定义、形参/replacement 和最终 intrinsic，知识匹配独立作为旁支。上下文仍默认上下各 20 行、包含命中高亮，不插入 classification/assessment 阶段节点。

声明变量不等于参数已使用。`store(fn)` 或没有使用 fn 不证明调用了 fn；原始实参和 compiler knowledge 命中仍保留，后续分析为 candidate/unknown。此证明不证明通用/RISC-V 实现等价、用途排除或真实构建成功；缺少新证明也不撤销已确认的 x86 事实。

## 首版边界

| 支持 | 保留 unknown/限制 |
| --- | --- |
| 静态 Make include、条件、四种赋值时机、单源码 recipe `$@/$<`、多来源 `-D/-U` | shell/eval/动态 include、pattern/target-specific、其他自动变量、response file、未知 compiler wrapper |
| CMake 既有 target/source/link usage，等价定义合流、显式同命令选项顺序 | 不同传播来源的冲突或无依据的覆盖顺序；不执行配置 |
| 每 TU/configuration 独立 define/undef、使用时对象别名、受限整数与布尔条件、可行路径合流 | 算术/类型/平台内建值未建模、未知 include 副作用、pragma push/pop 宏栈、复杂表达式 |
| 固定参数、嵌套传递、原始实参位置、调用身份隔离 | 字符串化、token 拼接、变参、递归、模板逗号和其他无法恢复的 token 结构 |
| 从正式知识反向查找宏需求，保留全部原始 records/facts | 索引命中不是作用证明；调用时环境仍需逐项验证 |

Tree-sitter 记录仅含 Python 标量与 source span；Clang token 在活跃 TU 内复制，不把 Cursor/Node/Tree 带入后续阶段。编译数据库是源配置的观察，不作为目标 RISC-V 已选择的证明。共享头文件在多个 TU 中的作用可分别 selected/inactive；同一 Finding 展示独立 occurrence，整体链路遇到配置冲突为 ambiguous，primaryPath 不跨配置拼接。

## 预算与输出

- 每 TU 100000 事件，include 深度 16/次数 128；Make include 深度 8/次数 128。
- 单调用展开深度 32、4096 token；每扫描最多新增 100000 作用关系，继承大图不占此额度，拒绝新增关系时不遗留孤立实体。
- 源码查询仍为深度 16、访问 256、路径 32；每段上下文最多 256 行/65536 字符。截断保留原始事实及 unknown，不用不完整证明降低风险。
- V2 仍使用既有 `steps/edges/occurrences`；`fact.extensions.org.rvport.kb-scanner.macro-effects` 提供有界作用说明、配置、TU、证明状态、reasonCodes、中文 `description` 与英文 `description_en`，最多展示 32 个作用配置并通过 totalUses/truncated 报告裁剪。
- 默认 V2、显式 `--schema-version 1.0`，工件仍为 JSON/HTML/log。V1 不新增核心字段，可在既有 trace 中增加真实来源。

<a id="doc-test-content-analysis"></a>

## 测试源码的静态关系

## 可以看见什么

一个 intrinsic Finding 可以附带这样的真实来源：

```text
CMake add_test → 本地 executable 的源码成员
                       ↓
                  main / 一跳调用点 → 辅助函数 → assert 形态 → intrinsic
```

这不是固定拼接的展示顺序。只有有证据的实际关联才连边；未调用函数可以显示词法归属，但不会被连成 main 已验证的内容。正常源码节点沿用命中行和上下各 20 行，预算裁剪会明示。classification/assessment 不作为源码步骤。

同一个 Finding 分别解释三件事：

| 轴 | 说明 |
|---|---|
| `buildStatus` | 该源是否属于对应配置的编译目标 |
| `registrationStatus` | 该测试是否注册、启用或被架构条件排除 |
| `content.entryStatus` / `content.relation` | 源码中的入口、一跳调用、断言参数或局部值关联是否可证明 |

例如 `DISABLED TRUE` 的测试仍可能需要编译 x86 intrinsic，因此不能因注册禁用而降低独立编译风险。入口存在也不表示执行过、测试通过或覆盖完整。

## 首版支持与 unknown

- CMake：`enable_testing()`、`add_test(NAME … COMMAND 本地普通 executable …)`、同目录有序字面 `DISABLED`；前向引用和目录作用域分开解析。
- 旧式签名、wrapper、动态发现、函数/宏内部注册、无法解释的属性/过滤参数保留候选或 unknown。不执行 CMake/CTest/Make。
- 复用 Make/RPM/CTest 已有构建资产与成员关系；历史 `confirmed` 构建资产不是 C++ 入口证明，新内容语境仍保留入口注册断点。
- 普通唯一 `main`、同文件唯一普通直接一跳、直接 assert 参数，以及同一直线 block 的 scalar 单次初始化→assert 使用。
- 重载/另行声明、包含文件中的未知声明、模板、成员/间接调用、递归、跨 TU、第二跳、嵌套 lambda、控制条件、重写/逃逸、损坏语法不补造 complete。
- 标准 `assert` 身份不能靠名称猜测。已有 Clang 编译上下文下，精确匹配受支持的 glibc 系统头宏定义并追踪实际宏实例，可展示该**观测 TU** 的 enabled/disabled（包括 `NDEBUG`）。其他 libc/profile、未知宏覆盖、缺少 compilation database 保持 unknown。观测 x86 配置不自动成为 RISC-V 配置的证明。
- `value == 42`、`sizeof(long) == 8` 不独立生成架构 Finding；codec 数据枚举沿用既有用途准入，断言形态不把它升级为执行依赖。
- 第三方测试框架的完整注册/断言语义、深层调用图 deferred。有符号移位仍是最后的低优先级目标。

## 兼容输出

V2 核心 schema、required 字段、后端输入和三工件不改。可选数据位于：

```text
findings[].fact.extensions["org.rvport.kb-scanner.test-content"]
  uses[]: testName, configuration, role,
          buildStatus, registrationStatus, proofStatus,
          content, assertion, reasonCodes, sourceIds,
          description, description_en
  sources[]: id, symbol, source(file/span/context/highlights)
  totalUses, truncated, limit, sourceLimit
```

每个 Finding 内的 `sourceIds` 自包含闭合；`assertion.observedConfigurations` 仅是当前编译 TU 的静态观测，不依赖外部 Evidence ID。可选扩展与家族、多版本、候选用途和宏作用扩展合并，不覆盖它们。HTML 默认中文并转义；原有 `suggestion/suggestion_en` 不变。显式 V1 沿用旧字段，不要求消费这个 namespace。

<a id="doc-candidate-usage-proofs"></a>

## 候选用途证明

## 能力与限制

默认管线先把本次已加载知识提供给前端，在 native tree 有效期内将原 Evidence 按正式规则预归一化并匹配候选，只采集命中作用域的完整使用记录。预选择时同 kind/value 的引用可共享代表，匹配后展开全部原始 occurrence；声明及引用校验仍使用正式 Normalizer。最终统一归一化仍保留所有原始事实。随后在已有源码、构建、测试、架构家族和函数多版本分析之后，从最终候选 fact 选择精确用途查询根。复用原 matcher 和 GCC/Clang 事实数据，不按 codec、算法名或人工审校标签排除。

非候选函数不再生成 usage_scope 或消耗扫描级用途记录预算；被选中的函数仍必须完整采集，不能只看候选命中行。采集需求不是排除证明：配置、绑定、作用域闭包与执行冲突仍由最终事实和消费门禁验证。整个过程不跨阶段保存 Node/Tree，也不逐 Finding 重读源码。

普通函数内，唯一绑定的局部枚举、明确整型标量的复制/比较，以及无逃逸的固定本地数组写入，可以构成纯数据闭包。默认 CLI 的局部枚举正例已经跑通：自动采集 → 归一化 → 用途图 → 消费校验 → 省略候选 Classification → V2 排除审计。没有人工注入 role。

调用、return、字段/指针写入、取址、volatile、不支持的运算或控制、错误语法、开放定义、跨配置和超预算均不能据此排除。宏定义、复杂展开、模板与跨函数分析尚无完整实现；scoped enum 名称不退化绑定为同名局部变量。存在 generic/RISC-V 文件也不证明执行实现等价。

自动角色为 `non_execution_data`，不自动声称它是 algorithm、data_format 或 output_platform。用途角色不证明编译成功，也不能替代目标选择、替代实现或项目 readiness 的证据。调用名即使含 portable 也不当作安全证明。

闭包命中的已确认 x86 依赖复用正式 matcher 和 compiler facts，提供 `usage-known-execution-conflict`、冲突数与来源；只检查同 subject/configuration 的实际闭包范围，不因同文件别处存在 intrinsic 就污染数据闭包。Detector 用 Evidence 反向索引隔离非执行用途图，避免每个候选遍历全图。

存在编译数据库时，未配置的 Tree-sitter inventory 不能自动代表其中某个编译配置；只有精确配置对应才具备证明资格。默认 Tree-sitter 路径及显式注入可选 Clang 的多配置组件测试均验证此边界。

## 内部合同

候选根严格使用 `factId + subjectId + configuration + matchedEvidenceIds`。使用记录在原生 Tree 生命周期内提取，只含标量与项目相对源码范围；后续阶段不保存 Node/Point。新记录追加，不重写旧 fact。

`usage_scope` 保存函数范围、全部已采集记录、声明绑定和不完整原因。规范化检查父子端点、范围、顺序、绑定与配置；不同 producer 冲突不提升为完整。

每个候选查询复用作用域索引，闭包纳入相关读写、声明和值流、受控语句与逃逸。`usage_record`、`usage_scope_coverage`、`usage_dependency`、`usage_scope_member` 是非执行关系，标记 `semanticRole=non_executing_usage`。它们不能充当构建选择或 alternative_to。

自动 proof 可用一条 has_semantic_role 汇总边，但必须带 usageProof，供消费者复核：

- 精确根、配置、原始匹配 Evidence 集合；
- 非空源码记录、作用域摘要、完整支持关系和来源；
- 全部预期使用与实际使用计数一致；
- 记录及 scope 成员关系闭合，从查询根能访问全部支持记录；
- 无未决、冲突、逃逸或截断，ProofPath 非空、连续且包含本 role 边。

消费者不会只相信 scopeComplete/complete。原始 Observation 和 fact 保留，只省略通过准入的候选 Classification；confirmed 执行依赖优先。

## 预算

| 层次 | 硬上限 |
| --- | --- |
| 文件语法访问 | 100000 节点 |
| 单函数用途记录 | 10000 条 |
| 全扫描新用途记录 | 100000 条 |
| 单根闭包 | 深度 32、节点 4096、支持关系 8192 |
| 全扫描查询访问 | 1000000 次 |
| 单 Finding 展示 | 64 个候选根，共享 64 个源码来源 |
| 顶层排除审计 | 100 条，每条至多 64 个源码来源 |

作用域成员边同样计入 proof 的支持关系额度，不只统计值流边。测试可降低预算，不允许突破上述硬上限。超限保留原事实并关闭排除资格，summary 的 truncated/reasonCodes 与 budget 记录相应状态。

若采集预算已经明确耗尽，保留原始 fact 与采集记录、精确命中和预算原因，直接返回 unknown，不再构造无法证明完整性的用途闭包。此时查询 visits 为 0，审计来源是已定位的命中，而非未执行查询的使用记录。非预算 partial 仍继续原有断点查询。`cacheHits` 统计用途查询缓存，不包含投影、物化及消费者的内部共享缓存。

源码上下文复用 SourceContextProjector：默认上下各 20 行，每段仍受最多 256 行、65536 字符限制，包含命中高亮。展示裁剪不改变分类结论。

## V2 扩展

命名空间：`org.rvport.kb-scanner.candidate-usage`，不增加核心 schemaVersion、required 字段或枚举。

- Finding 的 `fact.extensions`：`version/rootCount/omittedRoots/roots`。每根提供 symbol、configuration、用途状态、producerStatus、reason/reasonCodes、统计、分析预算及自包含 sources。
- 顶层 `extensions`：`excludedCount/omittedExcludedCandidates/excludedCandidates`，仅列实际通过准入且没有 Classification 的候选；不凭 producerStatus=complete 就声称排除。
- 来源为现有 Source 形状，含 file/span/context；不输出悬空的内部 proof/relation typed refs。多个根不合并配置或丢弃来源而不报告计数。
- 每根 `projectionStatus` 和来源省略/缺失计数表示展示完整性；`analysisTruncated` 表示分析完整性，二者不能互换。
- `explanation/explanation_en` 分别提供中文和英文。HTML 默认中文，符号、路径和代码均转义；命中行高亮。语义 role、classification、assessment 不作为源码 step。

有界结构示意（计数为说明用，不是项目扫描结果）：

```json
{
  "org.rvport.kb-scanner.candidate-usage": {
    "version": 1,
    "excludedCount": 0,
    "omittedExcludedCandidates": 0,
    "excludedCandidates": [],
    "statistics": {
      "rootCount": 0,
      "scopeIndexes": 0,
      "recordCount": 0,
      "visits": 0,
      "cacheHits": 0
    },
    "explanation": "排除仅针对已证明的局部非执行用途，不证明替代实现或项目已可迁移。",
    "explanation_en": "Exclusions concern proven local non-execution usage only, not alternative implementations or project readiness."
  }
}
```

无候选时不生成本扩展；上述空结构仅解释字段，不代表无候选输入的实际输出。默认 V2、显式 V1 和 JSON/HTML/log 三工件保持，V1 不增加该扩展。现有分类器通过聚合 INFO 诊断记录排除。

2026-09-23 固定样例审校：`tests/fixtures/candidate-usage-report-differential.json` 追加本轮账本，旧 CMake/函数多版本账本不覆盖。source-evidence-chain 与 architecture-enum 仅新增 V2 顶层和候选 fact 的用途 namespace，均没有自动排除；原结论、ID、源码主链和汇总未变。四个固定样例的 V1 三工件与日志均未改变，另外两个样例的 V2 三工件也未变。

`tests/audit_candidate_usage_reports.py <容器内新输出目录>` 可生成四个固定样例在关闭/开启新增采集和 Analyzer 时的 V1/V2 工件，以及逐字段 `audit.json`。必须在独立测试容器执行，输出目录可单独挂载持久保存。此工具只收集差异，不自动批准或更新 golden；审校后仍须运行正式回归和覆盖率门禁。
