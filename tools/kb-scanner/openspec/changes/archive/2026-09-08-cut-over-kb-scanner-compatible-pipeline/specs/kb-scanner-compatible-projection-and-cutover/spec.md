## ADDED Requirements

### Requirement: 正式 Projector 必须生成现有 schema 1.0 结果和三个 artifact
Compatible Report Projector SHALL 从同一次 staged scan 的 ScanContext、WorkspaceSnapshot、KnowledgeSnapshot、FrontendSnapshot、NormalizedSnapshot、AnalysisSnapshot、DetectionSnapshot、ClassificationSnapshot、AssessmentSnapshot 和 Diagnostic 生成现有 `scan-result.json`、`scan-report.html`、`scan.log`；JSON SHALL 保持 `schemaVersion: "1.0"` 及 `tool`、`rulePack`、`project`、`summary`、`findings`、`diagnostics` 顶层字段的名称、类型和既有语义，并 MUST NOT 创建第二个主结果。

#### Scenario: 默认扫描成功投影
- **WHEN** 完整 staged pipeline 对受支持项目完成静态扫描
- **THEN** Projector SHALL 生成请求格式对应的现有 artifact 并返回具有正确摘要的 ArtifactRef
- **AND** 默认 json/html 格式 SHALL 产生 `scan-result.json`、`scan-report.html` 和 `scan.log`

#### Scenario: 旧消费者忽略可选新字段
- **WHEN** 结果包含可选 `summary.readiness` 或更丰富的 Finding `trace`
- **THEN** 既有 schema 1.0 消费者 SHALL 仍可读取既有字段和 Finding
- **AND** 可选字段 MUST NOT 改变既有字段的名称、类型、计数语义或 artifact 名称

#### Scenario: 投影或写入失败
- **WHEN** 映射、序列化、验证或任一 artifact 写入失败
- **THEN** Projector SHALL 返回 failed Diagnostic 和非零结果且不报告未完成的 ArtifactRef
- **AND** scanner MUST NOT 留下会被误认为本次成功扫描的半套新 artifact

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
