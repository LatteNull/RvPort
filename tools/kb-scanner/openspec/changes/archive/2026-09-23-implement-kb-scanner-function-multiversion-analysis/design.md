## Context

本设计接续 proposal 的函数多版本静态分析范围。现有 `frontends/cpp/tree_sitter_adapter.py` 提取完整 `declaration_attribute`，`normalization/cpp.py` 保留其值，Local Detector 已识别 target feature；但没有普通函数声明/定义 Evidence 和可靠的 attribute-to-function 绑定。`ClangCppAdapter` 当前主要增强宏、include、调用、类型和 enum，不能假设已有函数多版本语义索引。

架构家族分析仅按路径发现候选，不提供函数身份或行为等价证明。此 change 不把文件家族 ID 当作函数版本组 ID。现有默认 V2、显式 V1、源码主链、±20 行上下文及中文/英文建议继续生效；历史 config 中的 Legacy/schema 1.0 描述不代表恢复旧管线。

### 官方依据与使用边界

于 2026-09-22 通过 AnySearch 开发文档检索定位并直接核对官方文档，以下是语义规则依据而非目标环境探测结果：

- [GCC Function Multiversioning](https://gcc.gnu.org/onlinedocs/gcc/Function-Multiversioning.html)：x86 的 `target` 多定义与 `target_clones` 单定义是不同模式；其他架构的 `target_version` 不能套用本轮 x86 规则。
- [Clang target](https://clang.llvm.org/docs/AttributeReference.html#target)、[target_clones](https://clang.llvm.org/docs/AttributeReference.html#target-clones)：普通 target codegen 属性和多版本组需区分；clone 参数存在多字符串及逗号混合形式，default 规则具有目标约束。
- [Clang cpu_dispatch/cpu_specific](https://clang.llvm.org/docs/AttributeReference.html#cpu-dispatch-cpu-specific)：属于另一种分发机制，本轮仅保留候选及不支持原因，不按 target 规则判断。

在线文档与本项目 libclang/parser 的版本不必相同。实施必须固定所支持的编译器家族、语言、目标与版本适用范围，记录来源日期/章节和人工样例；不从当前在线文档反推未知工具链版本的保证。仅使用这几条语义事实，不复制官方长文。

## Goals / Non-Goals

**Goals:**

- 没有编译数据库时，仍可从字面属性和局部声明恢复可核查版本候选。
- 区分普通 target 特化、多定义版本组和共用一个函数体的 clone 列表。
- 展示 default 的声明/实现状态、局部依赖及配置选择，未知原因各自独立。
- 保持风险保守、输出兼容、按事实关联及有界计算，并具备隔离单元门禁。

**Non-Goals:**

- 不模拟运行时 resolver、不求值 CPUID 或任意函数指针/跨函数值流，不证明函数行为等价。
- 不实现 `cpu_dispatch/cpu_specific`、`target_version`、手写 IFUNC、pragma 属性栈和任意属性宏的完整求值。
- 不做通用跨 TU 链接、模板实例化、编译器合法性诊断器或新全程序调用图。
- 不宣称 x86 默认 CPU 基线等于 RISC-V，不因 default 存在推导 ready。
- 不扩大 ARM/OS/内存模型分析，不运行项目或真实编译，不更改后端/生产容器。

## Decisions

### 1. 复用解析器，增加窄范围 scanner-owned 函数索引

在现有 Tree-sitter 解析生命周期内提取轻量函数描述，首版支持可完整定位的非模板自由函数，包括命名空间和 `extern "C"`；属性位于返回类型前、声明符后或标准属性位置时都必须按语法父子关系绑定。先按单文件一次遍历建立轻量声明索引，再仅物化有相关属性的函数及可能匹配的声明/定义，不为所有普通函数生成迁移事实。

新增内部 function declaration/definition Evidence 或同等有版本字段的结构记录：精确名称 token、声明/属性/函数体 byte span、限定作用域、参数类型形状、语言/linkage、定义标记、configuration、producer 和绑定完整性。完整属性 Evidence 原值/原 ID 保留，不拆成重复同 kind 命中；新关联在独立 metadata/record 中表达。普通重载、不同 namespace、匿名 namespace、不同文件的 static 函数不按裸名合并；参数名称可忽略，类型别名不能凭文本猜相等，返回类型/调用约定差异按冲突处理。

首版基线仅在同一文件可完整枚举的受支持语法范围内声明组完整。可选 Clang 在既有安全参数下补充 canonical declaration/语义签名和定义绑定，需按上下文限定；USR 只作为内部关联线索，不能未经路径规范化写入稳定 ID。Clang 折叠/拒绝多版本声明或与基线冲突时保留全部原始位置并降级，不能静默选它覆盖 Tree-sitter。跨文件只能展示有唯一语义依据的关联，首版不据此证明全项目 default 缺失。

沿用 `SourceByteIndex`；禁止读取 Tree-sitter Point 或让 Node/Tree/Cursor 逃逸生命周期。重叠错误节点、损坏声明、非字面量/宏包装、方法/模板/复杂函数指针声明产生 partial/unsupported；能定位的原始属性、调用仍保留。嵌套 lambda/函数体的 Evidence 不自动归到外层函数版本。

备选：全文正则/裸函数名拼组无法处理作用域和重载；强制编译数据库会丢掉基线能力，均不采用。

### 2. 版本化属性语义，不把 target 特化一律当作多版本

实现纯函数 attribute decoder 与 code-owned semantic profile，profile 包含 compiler family/version 范围、language、source target、mechanism、规则 ID/来源和适用状态。profile 缺少任何必须前提时保留 unknown；不执行 `gcc --version`、编译或 shell 来补信息，也不新增后端必填参数。源侧 compile command 可以帮助界定来源配置，不代表目标 RISC-V 工具链身份或接受能力。

| 源码构造 | 结构观察 | 不能推出 |
|---|---|---|
| 一个 `target("avx2")` 定义 | 单个特化函数，继续原 feature 检测 | 自动认定缺少 default |
| 同一语义函数的不同 target 定义 | 有界多版本候选组 | 任意同名函数都互为版本 |
| `target("default")` 只有声明 | default 声明存在，定义未验证 | 可执行 fallback 已存在 |
| `target_clones("avx2,default")` 的单一定义 | 一个源函数体，两个版本描述 | 两个不同源码函数体或机器码 |
| `target_clones("avx2","default")` | 与受支持混合字面量规则一致 | 不同参数写法产生重复问题 |
| unknown 宏参数或其他机制 | 可定位候选及未知原因 | 没看到 default 就是缺失 |

defaultPresence 取 present / absent_in_scope / unknown / not_applicable；defaultDefinition 取 present / declaration_only / unknown / not_applicable。条件不同的 default 声明不能无条件满足另一配置：成员 presence、body presence 和 configuration selection 分开。`absent_in_scope` 只描述明确范围，缺口判定还要检查语义适用、组完整性和目标相关性。无属性同名函数只有被适用规则及可靠声明绑定确认时才可作为 default；否则是未分类成员。

### 3. 独立分析阶段，按现有事实关联依赖

建议拆分 `frontends/cpp/function_inventory.py`、`analyzers/function_multiversion/{attributes,grouping,analysis}.py` 等可替换模块（实现可按现有结构调整）。Normalizer 校验属性 owner/body 引用，身份按稳定相对位置与语义材料分组，不能跨配置吞并。新 FunctionMultiversionAnalyzer 在已有 source/build/test proof 可用之后运行，家族分析与它保持独立；Detector 在已有 Local Detector 结果上关联精确 Knowledge-backed 事实，不重复匹配一套知识词表。

函数体依赖索引按 source file、最近有效函数体和 occurrence/configuration 精确绑定已有 fact/evidence。同一行不同函数按 byte span 区分；嵌套体、函数声明默认参数和无法定位的展开分别处理，不能宽泛吸附。clone 版本共用源体，关联源 fact 一次，不按 clone 数重复计数。只关联局部依赖及现有完整宏/source proof，不做新的跨函数递归；未解析调用/include/宏保留 body completeness unknown。

图增加 function/version group 结构记录及非执行 membership、attribute-owner、body provenance。它们不能直接进入执行可达性或 `alternative_to` 查询；有证据的声明包含/属性归属可由投影显式映射为既有 `defines/contains`。选择/排除只能绑定精确 configuration 的既有 build/source proof。禁止文件 selected 推导某个运行时版本 selected，也不能用 generic 路径候选代替 default 函数。

### 4. 缺口、风险与目标适用性分别判定

专用 Detector 产生有稳定 rule/reason 的多版本观察，Classifier 按以下顺序解释，Assessor 复用同一结论与不完整性；所有原始 fact 均保留：

1. 完整互斥 source/build proof 已排除该 occurrence：沿用 inactive/low，但不删除版本描述。
2. 存在原有确认 x86 dependency：继续已有 high 局部风险/闭合 selected blocker 策略。版本标签或 default 存在不能降低它；runtime 未选中不等于编译期不需要处理属性/函数体。
3. 有适用 compiler/target/language 规则、完整局部组和属性列表，且证明该机制要求 default 而未提供：允许 `function_multiversion_fallback_gap` 观察，默认 actionable_non_blocking/medium；它只说明该范围的多版本 default 缺口，不自动增加全项目 portabilityGap 或 blocking。只有既有独立目标阻断 proof 才能沿原规则给 blocker。
4. 未闭合的绑定、声明-only、条件成员、未知工具链或不支持机制：报告 unknown/medium 与具体补证据原因；不把缺口当确认问题，也不因零 blocker 提升 readiness。
5. 完整组含 default 实现且无额外缺口：展示结构补充，不仅因一个 default 字样额外生成问题；default 内若含 AVX 则原 fact/高风险继续可见。没发现已知 x86 依赖只表示当前扫描范围未命中，不能证明可移植。

避免相同属性的旧 generic candidate 和新未决组观察重复报告同一根因：按明确 Evidence/group/configuration 建立合并表，保留 provenance；不合并独立 x86 feature 命中或其他 occurrence。新观察种类/metadata 是内部扩展，须显式接入 risk、suggestion 和 V1/V2 mapping，不能依赖未知类型兜底。稳定 reason 示例：`multiversion-single-target-specialization`、`multiversion-default-declaration-only`、`multiversion-default-absent-in-scope`、`multiversion-compiler-profile-unknown`、`multiversion-binding-ambiguous`、`multiversion-budget-exceeded`。

### 5. 既有输出结构内展示，不生成虚假 clone 代码

V2 使用 `org.rvport.kb-scanner.function-multiversion` namespace：顶层有界 catalog 记录无 Finding 的版本组；相关 Finding 的 fact.extensions 自包含组/版本/属性来源、default 状态、局部依赖状态、configuration 及有效选择来源，不依赖 catalog 回查。与架构家族/enum/RPM/Autoconf namespace 合并而非覆盖。

新检查映射为已有 `architecture_probe` fact；真实 intrinsic 保持原 fact.kind。新增 findingType 是既有开放字符串中的规则值，不增加核心 schema kind/枚举/必填字段。代码链只展示真实属性、声明、定义及已闭合来源，保留各自位置/高亮/±20 行；compiler 自动生成的版本/resolver 没有真实源行，不能伪造 definition/调用边。clone 成员在 extension 引用真实共用属性/函数体，不能复制生成多个 occurrence。classification/assessment 留在 conclusion/summary，不回到 evidenceChain。

扩展中的引用要在单 Finding 内闭合；无法闭合则提供真实路径/span 描述和未知原因，不泄露悬空内部 ID。新增标题、解释和建议均采用中文/英文成对模板；现有 conclusion.title 没有 title_en 时，不新增核心字段，英文标题放入 namespace 的配对展示数据；suggestion/suggestion_en 沿既有合同。HTML 安全转义，以中文有界展示组摘要；显式 V1 复用既有字段和风险策略，不强加 catalog/core 字段，不要求新后端接入。

### 6. 有界计算与原生安全

轻量函数索引每文件一次构建；按作用域/签名/configuration 分桶，不做全部函数两两比较，不按 Finding 重扫源码/全图、不重启 source proof 全量搜索。默认预算在实施中固化为可注入对象：每文件最多 50000 轻量声明、每扫描 20000 个相关声明、10000 个组、每组 64 版本、每属性 65536 字符/128 选项、100000 次依赖关联。输出 catalog 1000 组/10000 成员；单 Finding 4 组/64 成员/256 来源引用，并服从现有上下文硬预算。

预算适用于所有相关表/索引及被拒绝候选的诊断聚合；超限要有原始数量、保留数量和稳定理由。发现、绑定与投影截断分别表达，任何截断禁止 absent/gap 推理。稳定 ID 不含绝对根、对象地址或遍历时序；原生节点只在其 Tree 存活时提取标量，异常路径沿现有 native-crash 修复合同。

### 7. 单元映射与验收标准

| 模块职责 | 隔离单元重点 | 隔离边界 |
|---|---|---|
| function inventory、Tree-sitter/Clang adapter、vocabulary | 属性归属、签名/作用域、精确字节位置、声明/定义、错误恢复及对象生命周期 | Node/Cursor facade、parser/cindex fake；真实 parser 另列组件 |
| CppEvidenceNormalizer | 合并 provenance、owner 校验、跨配置隔离、不更改旧事实身份 | 合成 Evidence/Snapshot |
| attribute/profile、grouping、analysis | literal 列表、普通 target 反例、完整性、歧义、预算、默认版本状态 | 纯数据/合成索引和已有 proof |
| 专用 Detector、组合管线 | 局部 fact 绑定、去重、排序、失败短路和 partial 传播 | 上下游 fake，不重复运行知识/解析器 |
| classifier/policy/risk、assessor 实际受影响模块 | 缺口门槛、unknown、原 high/blocker 保留、无 ready 升级 | 合成 Observation/Proof |
| V2 extension/mapper/chain/context/validator/renderers、suggestions、V1 实际受影响模块 | 自包含引用、双语、真位置、共享体不重复、namespace 合并、安全转义和发布失败 | reader/publisher fake、临时目录 |

新增/复用/实质修改模块必须登记机器可读 inventory；未改模块不能为了覆盖率而虚构改动。独立 scanner 测试容器运行 `python tests/run_source_chain_unit_tests.py --output /tmp/function-multiversion-coverage`，纳入全部自有 `kb_scanner/`、`scripts/`、`tools/`，包括未加载模块，整体与每个受影响模块行/分支均至少 90%。第三方、自动生成事实、测试资产及未部署 archive 的排除理由需明确列出，不排除业务逻辑。若发现历史缺口超出本 change，报告并请求扩围，不能降低门槛。

人工 oracle 至少包含：单 target、多 target+default、default 声明-only、clones 两种/混合参数、同名重载/namespace/static、不同配置/预处理分支、默认体内 AVX、未知调用、共享体不重复、非 FMV 属性、foreign/target_version/cpu_dispatch、宏包装、跨 TU/模板、parse error、UTF-8/CRLF、恶意文件/HTML、排除和根外路径、每项预算及乱序/迁根稳定性。先固定期望再跑真实 parser/CLI 组件，不自动重写 oracle。

运行完整回归 `python tests/run_container_tests.py --regression-only`，对固定 AVX、CMake、libarchive/zlib/cJSON 缩减样例逐字段审校。没有受支持多版本属性的输入剔除允许新增的空/缺省 extension 后须与旧报告一致；有属性的差异要逐项记录根因、风险及 occurrence 变化。两份 compiler JSON 哈希保持。合成 10000/20000 普通函数与稀疏属性组，记录索引/关联计数、时间、峰值内存、预算截断；新增阶段超过基线总时长 10% 且超过 1 秒须调查并说明。组件、性能或真实扫描不能代替隔离单元。

## Risks / Trade-offs

- [default 在 x86 与 RISC-V 语义不同] → source/profile/target applicability 分离，不将源侧成功当目标证明。
- [新函数索引扩大前端负担或引入原生崩溃] → 单次有界标量采集，复用字节位置和现有崩溃回归。
- [文本签名无法完全代表 C++ 语义] → 首版限自由函数和可解释语法，复杂绑定 unknown，Clang 不静默覆盖冲突。
- [多版本规则导致重复或降级原事实] → 明确根因合并表、原 fact 保留、人工差异账本与 blocker 反例。
- [严格 profile 限制确定结论数量] → 无 profile 仍交付有用的结构观察与 unknown，后续机制可补充，不能虚构确定性。

## Migration Plan

先固定官方语义矩阵与人工 oracle，保存现有报告/覆盖率/事实哈希；依次实现前端绑定、版本组、精确事实关联、分类投影和回归。默认管线接入，保留 V2/V1 和输出文件名，无数据库迁移。测试只更新/使用独立 scanner 测试容器，不重建生产镜像、不安装宿主依赖。

完成实际门禁后提交中文验证记录，用户确认后另行同步归档、commit/push 或部署。回滚为恢复上一个 scanner 版本；不得修改原始 compiler facts、历史结果或其他任务内容。

## Open Questions

没有需要用户现在选择的阻塞项。具体 compiler/version profile 与标准属性 grammar 支持在实施第一阶段用固定官方资料和现有 parser 组件确认；未验证的组合列为 unknown，不借此扩大到新分发机制或升级宿主依赖。
