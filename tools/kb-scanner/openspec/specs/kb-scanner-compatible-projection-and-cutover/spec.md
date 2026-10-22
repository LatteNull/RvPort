# KB Scanner Compatible Projection and Cutover Specification

## Purpose

定义完整 staged pipeline 如何确定性投影为现有 schema 1.0、JSON/HTML/log 三个固定 artifact，以及默认 CLI 切换、差异门禁、Legacy 隔离和独立容器验收所必须遵守的兼容边界。

## Requirements

### Requirement: 正式 Projector 必须生成现有 schema 1.0 结果和三个 artifact
版本选择器 SHALL 把同一次 staged scan 的 ScanContext、WorkspaceSnapshot、KnowledgeSnapshot、FrontendSnapshot、NormalizedSnapshot、AnalysisSnapshot、DetectionSnapshot、ClassificationSnapshot、AssessmentSnapshot 和 Diagnostic 直接交给所选版本的独立 Projector。ScanRequest/ScanContext SHALL 接受结果版本 `1.0` 或 `2.0`，未指定时 MUST 使用 `2.0`；v1 Projector SHALL 保持 `schemaVersion: "1.0"` 及既有顶层语义，v2 Projector SHALL 从内部 snapshots 直接生成 `kb-scanner-report-schema-v2`，MUST NOT 读取、解析或转换 v1 JSON。两种版本均 SHALL 使用现有 `scan-result.json`、`scan-report.html`、`scan.log` artifact 名称，同一次 scan MUST NOT 创建第二个主结果；v1 SHALL 作为显式兼容和回滚版本保留。

#### Scenario: 默认扫描成功投影
- **WHEN** 用户未显式选择结果版本，且完整 staged pipeline 对受支持项目完成静态扫描
- **THEN** 版本选择器 SHALL 委托 v2 Projector 直接从 staged snapshots 生成通过 schema 与引用完整性验证的 schema 2.0 artifact，并返回具有正确摘要的 ArtifactRef
- **AND** 默认 json/html 格式 SHALL 产生 `scan-result.json`、`scan-report.html` 和 `scan.log`

#### Scenario: 显式请求 schema v1
- **WHEN** 调用方显式请求结果版本 `1.0`
- **THEN** 版本选择器 SHALL 委托现有 v1 Projector 并生成原 schema 1.0 合同
- **AND** 结果字段、Finding/summary 计数、字符串 Diagnostic、artifact 名称和既有 v1 消费者行为 MUST 保持不变

#### Scenario: 旧消费者忽略可选新字段
- **WHEN** v1 结果包含可选 `summary.readiness` 或更丰富的 Finding `trace`
- **THEN** 既有 schema 1.0 消费者 SHALL 仍可读取既有字段和 Finding
- **AND** 可选字段 MUST NOT 改变既有字段的名称、类型、计数语义或 artifact 名称

#### Scenario: 调用方显式请求 schema v2
- **WHEN** 调用方通过 CLI 或 ScanRequest 明确请求 `2.0`，或未指定版本而使用默认值
- **THEN** 版本选择器 SHALL 把原始 staged snapshots 交给 v2 Projector，后者 SHALL 生成通过 v2 schema 与引用完整性验证的 `scan-result.json`，并使 HTML/log 与同一 v2 result model 一致
- **AND** 它 MUST NOT 同时生成 v1 主结果、把 v2 伪装为 v1 可选字段或改变上游分析阶段

#### Scenario: v2 生成不依赖 v1 中间结果
- **WHEN** 同一组 staged snapshots 可供 v1 和 v2 Projector 使用
- **THEN** 两个 Projector SHALL 分别从内部模型投影自己的结果合同
- **AND** v2 MUST NOT 把 v1 Finding、`trace` 或字符串 Diagnostic 作为输入事实

#### Scenario: v2 投影或写入失败
- **WHEN** v2 从 staged snapshots 直接投影、上下文读取、引用验证、序列化、渲染或任一 artifact replace 失败
- **THEN** Projector SHALL 返回 failed Diagnostic 和非零结果且不报告未完成的 ArtifactRef，并 SHALL 恢复本次发布前已有的完整 artifact 集合
- **AND** 它 MUST NOT 静默回退 v1 或留下会被误认为本次成功扫描的半套 artifact

#### Scenario: 回滚到 schema v1
- **WHEN** v2 消费者尚未就绪或部署需要回滚
- **THEN** 调用方 SHALL 能显式选择 v1 并取得既有合同和 artifact
- **AND** 回滚 MUST NOT 要求修改扫描知识、Evidence Graph、事实数据、检测策略或上游 snapshots

### Requirement: v1/v2 版本选择和发布边界必须具有独立回归门禁
版本值验证、默认选择、显式委托、固定 artifact 名称、单版本输出、渲染一致性、失败不回退和原子发布/回滚 SHALL 分别由隔离 unit tests 覆盖，并 SHALL 由 v1 consumer contract 与 v2 JSON Schema/component tests 共同验证。共享 artifact publisher MAY 被两个 Projector 复用，但 MUST NOT 合并或转换两个版本的 mapper、report model 或 renderer。

#### Scenario: 版本选择器只负责委托
- **WHEN** 单元测试分别请求默认、`1.0`、`2.0` 和不支持的版本
- **THEN** 默认与 `2.0` SHALL 只调用 v2 Projector，`1.0` SHALL 只调用 v1 Projector，不支持版本 SHALL 在分析或写入前失败
- **AND** selector MUST NOT 修改 snapshots、投影字段或生成 artifact 内容

#### Scenario: 同一输入分别验证两个合同
- **WHEN** 独立容器对同一确定性 staged fixture 分别运行显式 v1 和显式 v2
- **THEN** v1 artifact SHALL 继续通过现有 schema 1.0 consumer contract，v2 artifact SHALL 通过 schema 2.0 与 Finding 内引用完整性合同
- **AND** 两次扫描都 SHALL 使用固定 artifact 名称且各自只发布一个版本

### Requirement: Classification 必须确定性投影为兼容 Finding
Projection Policy SHALL 以版本化、code-owned 的 detector/observation/classification 映射产生现有 Finding 字段；每个发布 Finding SHALL 引用一个语义根因，确定性选择主 Evidence，并在 `trace` 中保留其他 Evidence、KnowledgeEntry、Relation 和 ProofPath 的稳定引用、状态、完整性与 producer。Projector MUST NOT 读取 Legacy YAML、Legacy DTO、源码或构建文件来补猜映射。

#### Scenario: 完整 selected proof 形成阻断 Finding
- **WHEN** Classification 为 `blocking_issue` 且引用完整 selected x86 dependency proof
- **THEN** Finding SHALL 使用显式映射的 rule ID、severity、reason、suggestion、类型和位置，并设置兼容 blocking/actionable 语义
- **AND** `trace` SHALL 可追溯到 Classification、Observation、Evidence、Knowledge、Relation 和 ProofPath

#### Scenario: x86 路径已被静态隔离
- **WHEN** Classification 为 `guarded_inactive` 且互斥 proof 完整
- **THEN** Finding SHALL 保留原 x86 Evidence 并投影为 guarded/inactive、non-blocking、non-actionable
- **AND** 它 MUST NOT 因局部 x86 命中退化为 blocker 或项目 ready

#### Scenario: 注释提示或未知分类
- **WHEN** Classification 为 `hint` 或 `unknown`
- **THEN** hint SHALL 最多形成非阻断提示，unknown SHALL 保持 unknown Diagnostic 或受限 Finding
- **AND** 缺失映射、断裂引用或不完整 proof MUST NOT 被投影成确定高危结论

#### Scenario: 输入顺序改变
- **WHEN** 等价 snapshots 的 Evidence、Relation、Observation 或 Classification 输入顺序不同
- **THEN** 主 Evidence、Finding ID、字段内容、排序和 artifact bytes SHALL 保持相同

### Requirement: 项目 Assessment 必须投影为可选且有静态范围的 readiness
Projector SHALL 将唯一有效的 `project_migration_state` Assessment 投影到可选 `summary.readiness`，并 SHALL 保留 state、confidence、dimensions、blocking dimensions、completeness、引用摘要、`staticScopeOnly=true`、`compiled=false` 和 `testsExecuted=false`；它 MUST NOT 从 Finding 计数重新推断 readiness。

#### Scenario: 完整静态证据支持 RISC-V ready
- **WHEN** Assessor 已产生引用完整且无 blocking/unknown 维度的 `riscv_ready`
- **THEN** `summary.readiness.state` SHALL 为 `riscv_ready` 并明确标记仅限静态范围
- **AND** HTML/log MUST NOT 使用“真实编译成功”或“测试通过”的文案

#### Scenario: 输入不完整或冲突
- **WHEN** Assessment 为 provisional/unknown 或引用缺失
- **THEN** readiness SHALL 保留 provisional/unknown、缺失维度和 Diagnostic
- **AND** Projector MUST NOT 因没有 Finding 或没有 x86 命中而升级为 ready

### Requirement: 切换必须由版本化差异 oracle 阻断未解释退化
Differential Gate SHALL 在删除 Legacy 前对同一只读 fixture 双跑 Legacy 与新 staged pipeline，规范化机器路径后比较退出码、artifact、schema、rule ID、Finding 类型、severity、blocking/actionable、位置、reason/suggestion、trace、summary 和 diagnostics；差异 SHALL 标记为 `parity-required`、`approved-correction` 或 `deferred-blocking`，未登记差异和 deferred-blocking MUST 阻止切换。

#### Scenario: 高价值行为语义相同
- **WHEN** Clang/GCC facts、accepted curated facts、AVX/x86-only、guarded/inactive、portable alternative、build/test selection 和零命中 fixture 双跑
- **THEN** parity-required 字段 SHALL 与版本化 oracle 相同
- **AND** 计数差异 SHALL 能定位到具体 fixture、Finding 字段、Evidence 或 proof

#### Scenario: 新实现修正 Legacy 误判
- **WHEN** 新结果与 Legacy 不同且完整 Evidence/proof 证明新结论更准确
- **THEN** 人工维护 ledger SHALL 记录 fixture、字段、旧值、新值、稳定引用和理由后才可批准
- **AND** scanner 或测试 MUST NOT 自动生成、覆盖或放宽该批准

#### Scenario: Legacy 实现已经删除
- **WHEN** 切换门禁已通过且 normalized Legacy 输出已冻结
- **THEN** 后续回归 SHALL 将新结果与版本化 golden oracle 比较
- **AND** 测试 MUST NOT 为运行 oracle 而重新导入已删除的 Legacy 生产路径

### Requirement: 默认 CLI 必须切换到完整 staged pipeline
`kb-scanner scan` SHALL 通过单一 default application factory 运行正式 Workspace、Knowledge、Frontend、Normalizer、Analyzer、Detector、Classifier、Assessor 和 Compatible Report Projector；默认路径 MUST NOT 调用或在失败时回退 Legacy runner、Legacy parser/evaluator/report 或 YAML rule loader。Qualification profile MAY 继续使用 recording/no-op Projector，但不得成为正式扫描入口。

#### Scenario: 用户执行默认 scan
- **WHEN** 用户使用现有 scan 参数扫描知识包
- **THEN** CLI SHALL 规范化为同一 ScanContext 并运行完整 staged profile
- **AND** CLI 参数形状、目标架构含义、既有退出码语义和 artifact 行为 SHALL 保持兼容

#### Scenario: 正式阶段失败或不可用
- **WHEN** 默认 staged profile 的必需阶段 failed/unavailable
- **THEN** scanner SHALL 保留结构化 Diagnostic 并返回兼容非零退出码
- **AND** 它 MUST NOT 静默调用 Legacy 获得另一套结论

#### Scenario: 校验或列出当前规则包
- **WHEN** 用户调用既有 `validate-rules` 或 `list-rules`
- **THEN** 命令 SHALL 验证或列出正式 knowledge bundle、detector 和 projection policy，并保持可兼容的命令/退出码表面
- **AND** 任意 Legacy YAML 扩展 MUST NOT 被默认 scan、校验或列表命令执行

### Requirement: Legacy 和技术 spike 只能在等价证据闭合后清理
Cleanup Inventory SHALL 为每个 Legacy parser/evaluator/model/report bridge、重复正则和 `technology/` spike 记录生产引用、测试引用、正式替代、差异 fixture、处置和退出条件；只有默认路径无引用、替代模块存在、相应 unit/component/differential gate 通过且 golden 已冻结时才可删除。尚无等价替代的能力 SHALL 隔离保留或标记 deferred，不得通过删除测试隐藏缺口。

#### Scenario: 旧模块具有完整替代
- **WHEN** import graph、能力矩阵、单元测试和 differential oracle 证明旧模块不再承担唯一行为
- **THEN** 旧活动实现 SHALL 被删除且默认/qualification 路径 SHALL 保持无 Legacy import
- **AND** Git 历史、冻结 golden 和已有源码 archive SHALL 提供审计与恢复依据

#### Scenario: 旧能力尚无正式替代
- **WHEN** inventory 无法关联正式实现或存在 deferred-blocking 差异
- **THEN** 该能力 SHALL 明确保留在隔离边界或阻止 change 完成
- **AND** cleanup MUST NOT 删除对应 fixture、oracle 或兼容要求

#### Scenario: 检查 Legacy 知识资产
- **WHEN** 默认切换完成
- **THEN** 现有 YAML 和全部 `generatedSet` 引用 SHALL 作为冻结审计资产保持不变
- **AND** 默认及 qualification 新管线 MUST NOT 读取它们或把它们转换成新知识

### Requirement: 兼容切换必须通过逐模块单元测试和独立容器门禁
本 capability 的每个新增或实质修改业务模块 SHALL 映射到机器可读 test inventory 中的隔离 unit suite，并 SHALL 在唯一 `kb-scanner-test` 容器中分别通过至少 90% line / 80% branch 覆盖；component、differential、真实 knowledge、后端契约、artifact E2E 和 full regression SHALL 作为额外门禁，MUST NOT 替代逐模块 unit coverage。

#### Scenario: 审计新增和修改模块
- **WHEN** 新增、删除或重命名 projection contract/policy/mapper/renderer/projector、default factory、differential comparator/ledger validator 或 cleanup validator
- **THEN** inventory SHALL 同步记录 unit suite、fake/mock 边界和适用高层测试
- **AND** 缺失映射、模块无 executed lines 或覆盖不足 SHALL 使容器门禁失败

#### Scenario: 验证文件和外部边界
- **WHEN** unit suite 测试 artifact 写入失败、恶意命令文本、workspace escape 或外部依赖不可用
- **THEN** 测试 SHALL 使用内存 snapshot、fake/temporary writer 和受控故障，不启动 compiler、build tool、test runner、项目命令或网络
- **AND** 宿主机、生产镜像、根 Compose 和 backend Dockerfile SHALL 保持不变

#### Scenario: 执行正式 cut-over gate
- **WHEN** 独立容器执行本 change 验收
- **THEN** 它 SHALL 通过逐模块覆盖、schema 1.0、三 artifact、后端消费、compiler facts 哈希、AVX/关键 fixture、无副作用、Legacy import boundary 和 full regression
- **AND** 任一失败 SHALL 阻止默认切换或 Legacy 删除

### Requirement: 兼容 Finding 必须投影完整语义与引用闭包
Compatible Report Projector SHALL 在不改变 schema 1.0 必需字段和既有 Finding identity 的前提下，从结构化 Evidence、KnowledgeEntry、Relation 和 ProofPath 恢复语义 `symbol`，并 SHALL 在可选 `trace` 字段中保留主 Evidence 的完整 start/end span 及该 Finding 引用的完整证据闭包。Projector MUST NOT 重新扫描 snippet、源码或构建文件来猜测缺失信息。

#### Scenario: intrinsic 和向量类型具有结构化 symbol
- **WHEN** 主 Evidence 或被引用的 KnowledgeEntry/终端 Relation 提供唯一语义 symbol
- **THEN** Finding `symbol` SHALL 使用该结构化值
- **AND** 相同输入乱序 MUST NOT 改变 symbol、主位置或 Finding identity

#### Scenario: 宏调用引用定义和终端 intrinsic
- **WHEN** Classification 引用从宏调用到宏定义和终端 x86 intrinsic 的完整 proof
- **THEN** `trace.evidence` SHALL 包含调用、定义与终端 Evidence 对象，并保留全部 Relation/ProofPath 引用
- **AND** 用户 MUST NOT 需要读取内部 snapshot 才能定位宏定义

#### Scenario: 内部 Evidence 具有结束位置
- **WHEN** 主 Evidence 提供完整 start/end 坐标
- **THEN** 顶层 `location.file/line/column` SHALL 保持兼容，且 `trace` SHALL 以可选字段保留完整 span
- **AND** 旧 schema 1.0 消费者忽略该字段时仍能读取报告

#### Scenario: 引用闭包断裂
- **WHEN** 任一被引用对象不存在、类型冲突或 traversal 超限
- **THEN** Projector SHALL 保留可验证的局部 Finding 并产生 partial/failed Diagnostic
- **AND** 它 MUST NOT 伪造 symbol、span、Evidence 或 complete trace

### Requirement: 聚合 Finding 必须保留全部底层 occurrence
当多个位置按既有策略合并为一个 Finding 时，Projector SHALL 保持现有 Finding 数量、主位置和 summary 计数语义，并 SHALL 在可选 `trace` 中提供稳定的 occurrence count 和逐 occurrence path、span、configuration、selection status 与 Evidence 引用。

#### Scenario: 同一构建参数在多个位置出现
- **WHEN** 24 个构建参数 occurrence 被按 4 个 Makefile 根因聚合
- **THEN** 兼容结果 SHALL 继续产生 4 个 Finding，并在对应 trace 中覆盖全部 24 个 occurrence
- **AND** occurrence 顺序 MUST NOT 依赖文件系统或输入遍历顺序

#### Scenario: occurrence 信息不完整
- **WHEN** 某个 occurrence 缺少 configuration、结束位置或选择状态
- **THEN** trace SHALL 保留该 occurrence 及明确的 completeness/unknown reason
- **AND** Projector MUST NOT 删除它或复制其他 occurrence 的字段

### Requirement: 重复关系诊断必须可追溯地聚合
Compatible Report Projector SHALL 对同一扫描中具有相同 code、reason、relation kind、stage 和 severity 的重复关系 Diagnostic 做确定性聚合，并 SHALL 保留原始数量、代表位置和稳定引用；聚合 MUST NOT 丢失 failed/partial 状态或改变扫描退出码语义。

#### Scenario: 大量 include 关系以相同原因未解析
- **WHEN** 多个 `unresolved-include` Diagnostic 具有相同聚合键
- **THEN** 对外 diagnostics SHALL 使用一条聚合记录表达，并包含总数与可追溯引用
- **AND** HTML/log SHALL 展示摘要而不是重复相同文案

#### Scenario: 原因或严重性不同
- **WHEN** Diagnostic 的 reason、relation kind、stage 或 severity 任一不同
- **THEN** 它们 SHALL 保持为不同聚合组
- **AND** 聚合 MUST NOT 把 failed 与 warning/partial 合并

### Requirement: 投影修正必须保持 schema 1.0 并通过隔离单元门禁
本 change 修改的 reference index、Finding mapper、summary mapper、Diagnostic aggregator 和 renderer SHALL 分别映射到隔离单元测试，并 SHALL 在唯一 `kb-scanner-test` 容器中达到每模块至少 90% line / 80% branch。`scan-result.json` 的 `schemaVersion: "1.0"`、既有顶层字段、必需 Finding 字段、三个 artifact 和旧消费者行为 SHALL 保持兼容。

#### Scenario: 运行投影模块单元门禁
- **WHEN** 独立容器执行本 capability 的 unit inventory
- **THEN** 每个新增或实质修改业务模块 SHALL 被执行并分别满足 line/branch 门槛
- **AND** component、AVX 或全量回归 MUST NOT 替代隔离单元覆盖

#### Scenario: 旧消费者读取增强结果
- **WHEN** 结果包含新增 trace span、occurrences 或聚合 diagnostic details
- **THEN** 旧消费者 SHALL 继续读取既有字段、summary 和 artifacts
- **AND** scanner MUST NOT 输出 schema 2.0 或第二个主结果文件

### Requirement: 架构枚举分析必须保持显式 Schema V1 兼容投影
显式 V1 Projector SHALL 从新的 enum Observation、Classification 和 proof snapshots 投影原 Schema 1.0 顶层结构与固定 artifact。if constexpr 中的架构 enum branch SHALL 使用既有 `CPP.X86.CONSTEXPR_ARCH_BRANCH` rule identity；其他结构化 enum candidate MAY 使用稳定 `C_CPP.X86.ARCH_ENUM_CANDIDATE` identity。兼容投影 MUST NOT 恢复 Legacy/YAML evaluator、改变默认 Schema V2、生成第二个主结果或把 candidate 伪装为 confirmed blocker。

#### Scenario: 显式 V1 扫描既有 constexpr fixture
- **WHEN** 用户以 `--schema-version 1.0` 扫描 `Backend::avx2` if constexpr fixture
- **THEN** V1 结果 SHALL 恢复 `CPP.X86.CONSTEXPR_ARCH_BRANCH` Finding，并保留现有必需字段、位置和 summary 计数语义
- **AND** `scan-result.json`、`scan-report.html`、`scan.log` 名称和 Schema 1.0 顶层字段 MUST 保持不变

#### Scenario: V1 投影孤立 enum candidate
- **WHEN** enum member 只有 candidate/unknown Classification
- **THEN** V1 Finding SHALL 保持非阻断、非操作和 unknown reachability，并可在兼容 trace 中携带结构化声明/引用摘要
- **AND** 它 MUST NOT 因 V1 字段较少而升级 severity 或丢失不完整 Diagnostic

#### Scenario: 默认扫描仍使用 V2
- **WHEN** 用户未传结果版本或显式传 `2.0`
- **THEN** Versioned Projector SHALL 只调用 V2 enum projection
- **AND** enum 投影失败 MUST NOT 静默回退 V1 或留下半套 artifact

#### Scenario: enum 功能不改变既有非枚举结果
- **WHEN** 输入不含 enum Evidence，或 enum 与架构知识无关
- **THEN** 显式 V1 的既有 x86 Finding、summary、Diagnostic、artifact bytes normalization 和退出码语义 SHALL 保持兼容
- **AND** AVX、compiler fact、comment hint、macro/build/test 既有回归中的未解释差异 SHALL 阻止 change 完成

### Requirement: Projector 必须阻止非 x86 噪声重新进入 Finding
V2 默认和显式 V1 Projector SHALL 只投影具有有效 Classification 的 Observation。标记为 foreign、not-architecture-related、duplicate-child 或缺少候选资格的对象 MUST NOT 生成 Finding；真正 unknown candidate SHALL 继续使用现有低严重度、非阻断、非操作语义。两种版本 MUST NOT 为此新增顶层结果结构、第二个主文件或不一致的 HTML/log 过滤。

#### Scenario: zlib ARMCRC32 与通用属性
- **WHEN** staged snapshots 包含九条已证明属于 ARMCRC32 分支的 asm Evidence 和 `no_sanitize("memory")` attribute Evidence
- **THEN** V2 与 V1 均不得为这些 Evidence 生成 x86 Finding
- **AND** JSON、HTML、log 和 summary 的 Finding 数量 SHALL 一致

#### Scenario: 真正未知的汇编候选
- **WHEN** Classification 为有效 `unknown / candidate-evidence-not-sufficient` 且引用一个完整最外层 asm occurrence
- **THEN** Projector SHALL 生成至多一个低严重度、非阻断、非操作候选 Finding
- **AND** evidence chain/trace SHALL 指向完整 asm span 而不是 qualifier 或 operand 子节点

#### Scenario: 防御性收到 foreign Classification
- **WHEN** Projector 收到违反分类合同的 foreign 或无架构语义 Classification
- **THEN** Projector SHALL 产生结构化 Diagnostic 并拒绝发布对应 Finding
- **AND** 它 MUST NOT 静默把该对象改写为 candidate 或 confirmed x86 finding

### Requirement: 候选过滤必须保持版本化输出兼容
候选噪声修复 SHALL 保持默认 Schema V2、显式 V1、现有必需字段、artifact 名称和旧消费者读取能力。被移除的重复/foreign/通用属性 Finding 数量变化 SHALL 作为 approved correctness correction 固化在 golden；合法 x86 Finding 的字段类型、证据引用和稳定排序 MUST 保持兼容。

#### Scenario: 默认和显式版本回归
- **WHEN** 同一 zlib/AVX fixture 分别使用默认、显式 V2 和显式 V1 扫描
- **THEN** 默认与显式 V2 SHALL 生成 Schema 2.0，显式 V1 SHALL 生成 Schema 1.0，且每次只发布固定三类 artifact
- **AND** 三种结果均不得恢复 ARM asm 重复候选或通用 attribute 候选

#### Scenario: 既有 x86 finding
- **WHEN** fixture 包含知识支持的 x86 intrinsic、asm、target feature 或架构条件
- **THEN** V2/V1 SHALL 继续投影现有兼容字段、状态、严重度和 evidence trace
- **AND** 候选去重不得合并不同 source span 或不同 configuration 的合法 occurrence

### Requirement: 候选投影修复必须通过独立容器回归门禁
修改的 V2/V1 projection policy、mapper、renderer 或 summary 模块 SHALL 具有逐模块隔离单元测试并在 `kb-scanner-test` 达到 90% line / 80% branch；此外 SHALL 运行 zlib ARMCRC32、真正未知 asm、AVX、架构枚举、原生崩溃和全量兼容回归。

#### Scenario: 固定 zlib 数量上限
- **WHEN** 容器扫描固定 zlib ARMCRC32 回归输入
- **THEN** 九条 ARM asm 和一个 `no_sanitize` MUST 产生零个对应 x86 findings，真实 x86 mixed condition SHALL 保留既有 inactive 结果
- **AND** Evidence、Observation、Classification 与 Finding 数量上限 SHALL 被明确断言，防止父子节点爆炸恢复
