# KB Scanner Core Pipeline Specification

## Purpose

定义 KB Scanner 分层静态分析管线的核心领域合同、阶段生命周期、兼容迁移方式及执行边界，使后续前端、知识、关系分析和分类组件可以独立替换，同时保持现有扫描结果兼容。

## Requirements

### Requirement: 核心领域合同必须独立于具体实现技术
KB Scanner SHALL 使用 scanner 自有领域对象表达 Entity、Evidence、Relation、Observation、Assessment 和 Diagnostic；核心合同 MUST NOT 暴露 Tree-sitter、Clang、NetworkX、Pydantic 或 legacy parser 的私有类型。

#### Scenario: 前端产生解析证据
- **WHEN** 任一 frontend 从源码或构建输入产生解析结果
- **THEN** 下游阶段 SHALL 接收 scanner 自有 Evidence 或 StageResult
- **AND** 下游 MUST NOT 依赖该 frontend 的原生语法节点或 cursor 类型

#### Scenario: 更换具体实现技术
- **WHEN** 后续 change 替换 parser、GraphStore 或边界验证库
- **THEN** 未直接负责该 adapter 的其他阶段 SHALL 无需改变其领域接口
- **AND** 现有报告合同 MUST NOT 因具体库类型变化而改变

### Requirement: 核心对象必须具有确定且可追溯的身份
Entity、Evidence、Relation 和 Observation SHALL 使用由规范化领域身份材料生成的稳定 ID，并 SHALL 在适用时保留项目相对源码位置、producer、parse mode、confidence 和 knowledge provenance。

#### Scenario: 同一输入重复扫描
- **WHEN** 使用相同 scanner/knowledge 版本、输入和扫描选项重复扫描项目
- **THEN** 对应核心对象 SHALL 产生相同稳定 ID
- **AND** ID 构造 MUST NOT 包含机器绝对路径、内存地址、随机 UUID 或非确定时间

#### Scenario: 多个前端发现同一源码事实
- **WHEN** 两个 producer 在同一 source span 发现相同 kind 的事实
- **THEN** scanner SHALL 能保留两个 producer 的 Evidence 身份
- **AND** 后续合并 MUST NOT 丢失任一来源

### Requirement: 每次扫描必须使用统一只读 ScanContext
Pipeline SHALL 在开始执行前构造统一 `ScanContext`，显式携带输入范围、目标架构、当前扫描选项、compile context、rule/knowledge identity 和 scanner 版本；阶段 MUST NOT 重新解析 CLI 参数或通过全局可变状态获取这些值。

#### Scenario: CLI 发起扫描
- **WHEN** 用户通过现有 `kb-scanner scan` 命令提交参数
- **THEN** CLI adapter SHALL 将参数规范化为一个 ScanContext 后再调用 pipeline
- **AND** 各阶段 SHALL 从同一 context 读取目标架构和扫描选项

#### Scenario: 单元测试替换扫描组件
- **WHEN** 测试向 pipeline 注入 recording 或 stub stage
- **THEN** 替代组件 SHALL 接收与正式组件相同的 ScanContext
- **AND** 测试 MUST NOT 依赖修改模块级全局变量来控制阶段行为

### Requirement: Staged Pipeline 必须按确定顺序执行可替换阶段
KB Scanner 的 `StagedPipelineRunner` SHALL 按工作区采集、知识加载、输入前端、事实归一化、关系分析、局部检测、分类、项目评估和兼容报告投影的顺序执行阶段，并 SHALL 通过显式 profile 或构造参数注入各阶段实现；正式 default profile SHALL 为每个阶段提供完整新实现并由 `kb-scanner scan` 使用，qualification profile MAY 使用 recording/no-op Projector 但 MUST NOT 成为默认扫描路径。

#### Scenario: 执行完整 pipeline
- **WHEN** 所有阶段均成功返回
- **THEN** orchestrator SHALL 按定义顺序把前序 scanner 自有结果传给后续阶段
- **AND** Report Projector SHALL 是写入正式 artifact 的唯一阶段

#### Scenario: 测试阶段编排
- **WHEN** 测试使用 recording stages 执行 pipeline
- **THEN** 测试 SHALL 能观察确定的调用顺序和输入传递
- **AND** orchestrator MUST NOT 通过隐藏的服务定位器或全局 plugin registry 选择组件

#### Scenario: 注入 qualification Frontend
- **WHEN** qualification profile 使用正式 Workspace、Knowledge、Frontend、Normalizer、Analyzer、Detector、Classifier、Assessor 和 recording/no-op Projector
- **THEN** StagedPipelineRunner SHALL 把全部真实 snapshot 按合同传递给 recording downstream
- **AND** qualification 运行 MUST NOT 写入正式 artifact 或替代默认 CLI 报告

#### Scenario: 默认正式阶段尚未完成
- **WHEN** default profile 的任一必需阶段仍为空实现、recording/no-op 或缺少兼容门禁
- **THEN** release gate SHALL 阻止默认切换并返回明确失败
- **AND** scanner MUST NOT 把不完整 staged 运行呈现为完整成功扫描或静默回退 Legacy

### Requirement: 阶段结果必须显式传播 Diagnostic 和完整性状态
每个阶段 SHALL 返回包含阶段值、结构化 Diagnostic 和 completion status 的 `StageResult`；缺失输入、部分解析或增强失败 MUST NOT 被转换为空成功结果或被解释为没有迁移问题。

#### Scenario: 可选增强阶段失败
- **WHEN** 一个允许降级的增强组件不可用或无法处理单个输入
- **THEN** orchestrator SHALL 保留已产生的基础结果并汇总带 stage/producer 的 Diagnostic
- **AND** 依赖缺失证据的结论 SHALL 保持 partial/unknown

#### Scenario: 必需阶段发生内部失败
- **WHEN** 阶段违反核心不变量或无法产生继续执行所需的值
- **THEN** orchestrator SHALL 停止依赖该值的后续阶段并返回非零结果
- **AND** scanner MUST NOT 生成看似完整的成功 Assessment

#### Scenario: 正式知识包加载失败
- **WHEN** Knowledge Provider 发现 manifest、source、hash、schema 或引用错误且该错误影响正式扫描
- **THEN** default staged profile SHALL 保持该错误对退出码的兼容影响并产生结构化 Diagnostic
- **AND** 普通可降级 input completeness Diagnostic MUST NOT 被错误升级为同等失败

### Requirement: Legacy compatibility profile 必须支持渐进迁移
Legacy compatibility profile SHALL 仅在切换前作为冻结 differential oracle 使用，不得成为默认生产路径或向新 core 泄漏 Legacy DTO；差异门禁通过后 SHALL 以版本化 golden 保留行为基线，并 SHALL 删除已有正式替代的活动 Legacy runtime。Legacy 缺陷的修复 MUST 进入新实现并由 approved-correction 记录，不得修改旧实现制造表面一致。

#### Scenario: 切换前运行 Legacy oracle
- **WHEN** differential gate 尚在比较同一 fixture 的 Legacy 和新 staged 结果
- **THEN** Legacy runner SHALL 保持只读并与新 runner 隔离执行
- **AND** 它 MUST NOT 被 default application factory 或新业务模块导入

#### Scenario: 差异已经完成分类
- **WHEN** 所有结果差异均为 parity-required 一致或具有完整 Evidence/proof 的 approved-correction
- **THEN** normalized Legacy 结果 SHALL 固化为版本化 golden
- **AND** deferred-blocking 或未登记差异 MUST 阻止默认切换

#### Scenario: 删除已替代 Legacy runtime
- **WHEN** golden 已冻结、默认路径无引用且正式替代模块通过单元和差异门禁
- **THEN** 对应 Legacy parser/evaluator/model/report bridge SHALL 从活动代码删除
- **AND** 后续回归 SHALL 使用 golden 而不是恢复可执行 Legacy

#### Scenario: 旧行为存在缺陷或限制
- **WHEN** 新实现发现 Legacy frontend、detector 或 report 的 bug、误报或信息缺失
- **THEN** 该差异 SHALL 通过 baseline fixture、稳定引用和迁移说明显式记录
- **AND** 修复 SHALL 进入新实现，不得通过修改旧代码制造兼容

### Requirement: 新管线入口必须保持现有扫描结果兼容
默认 staged orchestrator 执行扫描时，KB Scanner SHALL 保持现有 CLI 参数、退出码语义、`schemaVersion: "1.0"`、七个顶层字段、Finding 关键语义和三个 artifact，并 MUST NOT 产生替代现有 JSON 的第二个主结果文件；新增内部信息只能投影到既有字段或可选兼容扩展。

#### Scenario: 成功扫描现有项目
- **WHEN** default staged profile 完成扫描
- **THEN** scanner SHALL 继续生成请求的 `scan-result.json`、`scan-report.html` 和 `scan.log`
- **AND** JSON SHALL 保留 `tool`、`rulePack`、`project`、`summary`、`findings` 和 `diagnostics` 顶层结构

#### Scenario: 核心对象包含新内部信息
- **WHEN** core pipeline 中存在现有结果未直接表达的内部对象
- **THEN** Projector SHALL 将安全摘要放入 Finding `trace`、可选 `summary.readiness` 或 diagnostics，或者保留为内部状态
- **AND** 新内部类型 MUST NOT 被直接序列化为新的主报告结构

#### Scenario: 兼容 Projector 失败
- **WHEN** 正式投影无法满足 schema、引用或 artifact 完整性
- **THEN** pipeline SHALL 返回兼容非零退出码和 failed Diagnostic
- **AND** 它 MUST NOT 回退 Legacy、发布伪完整 artifact 或丢弃前序 unknown 状态

### Requirement: 新管线入口必须保留现有知识和检测资产
Default staged profile SHALL 通过正式 JSON Knowledge Provider 原样加载 `clang-x86-entries.json`、`gcc-x86-entries.json`、新增 generated sources 和 accepted curated sources，并 SHALL 通过 code-owned Detector/Classifier/Projection Policy 保持当前高价值 x86 fixture 的兼容检测语义；Legacy YAML/`generatedSet` SHALL 仅作为冻结 oracle 资产而不得成为默认运行时依赖。

#### Scenario: 加载 compiler-derived facts
- **WHEN** default staged orchestrator 扫描 RISC-V porting knowledge bundle
- **THEN** Knowledge Provider SHALL 直接读取两份现有 JSON 的六类条目、来源和既有稳定 identity
- **AND** 本 change MUST NOT 重生成、转换、删除或改变这些数据的 SHA-256

#### Scenario: 加载 accepted curated facts
- **WHEN** knowledge manifest 声明 schema、hash、reference 和 review 均有效的 curated source
- **THEN** default staged profile SHALL 合并该来源并保留完整 provenance
- **AND** rejected/deferred decision ledger MUST NOT 进入运行时 KnowledgeSnapshot

#### Scenario: 运行现有检测 fixture
- **WHEN** 独立测试容器执行 generated-entry、curated、AVX 和关键兼容 fixture
- **THEN** 既有关键 rule ID、Finding 分类、阻断状态和位置 SHALL 不发生未登记退化
- **AND** guarded、inactive 或 portable alternative 语义 MUST NOT 无证据变成 blocker

### Requirement: 核心管线建立不得扩大分析或执行边界
本 change SHALL 继续只执行 C/C++ 软件迁移静态分析，并 MUST NOT 因引入 orchestrator 或 adapter 而执行项目构建、配置、编译器插件、RPM 宏或测试代码。

#### Scenario: 输入包含其他迁移领域内容
- **WHEN** 项目包含操作系统、内核、系统调用、驱动或板级迁移内容
- **THEN** 新 core pipeline MUST NOT 将其纳入本模块的权威迁移结论

#### Scenario: Pipeline 处理当前构建输入
- **WHEN** compatibility profile 遇到 Make、Autoconf、RPM、CMake 或 compilation database 内容
- **THEN** scanner SHALL 保持当前静态读取边界
- **AND** orchestrator MUST NOT 新增执行真实构建、RISC-V 编译或项目测试的路径

### Requirement: 核心管线必须通过独立测试容器验证
核心领域对象、orchestrator、默认 profile、兼容 Projector、差异 oracle、cleanup guard 和输出合同的正式测试 SHALL 在 `kb-scanner-test` 容器中运行，并 MUST NOT 要求开发者在宿主机安装扫描器依赖或修改生产镜像；每个新增或实质修改业务模块 SHALL 具有隔离单元测试映射和逐模块至少 90% line / 80% branch 门禁。

#### Scenario: 验证本 change
- **WHEN** 开发者构建并运行本 change 的正式测试
- **THEN** 测试 SHALL 使用 `tools/kb-scanner/Dockerfile.test` 和专属 Compose 服务执行逐模块 unit、component、differential、contract 和 full regression
- **AND** `backend/Dockerfile`、根 Compose 和生产 API/worker 镜像 SHALL 保持不变

#### Scenario: 历史快照存在
- **WHEN** 默认测试或模块发现运行
- **THEN** `archive/2026-09-04-pre-rewrite` SHALL 只作为显式参考输入
- **AND** archive 中的包和测试 MUST NOT 被自动导入或重复执行

#### Scenario: 审计业务模块覆盖
- **WHEN** default factory、projection、differential 或 cleanup 模块新增、修改、删除或重命名
- **THEN** 机器可读 inventory SHALL 同步更新 unit suite、fake/mock 边界和高层测试
- **AND** integration/full regression 的覆盖 MUST NOT 代替隔离 unit coverage

### Requirement: 核心管线必须承载知识、归一事实和知识引用
核心领域层 SHALL 提供与 JSON schema model、YAML、parser、图库和 legacy DTO 无关的 KnowledgeSource、KnowledgeEntry 与 NormalizedFact，并 SHALL 允许 KnowledgeSnapshot、NormalizedSnapshot 和 Observation 通过默认兼容字段承载这些对象及其引用。Detector definition SHALL 由 detector 模块的代码维护，而 MUST NOT 伪装成知识事实进入 KnowledgeSnapshot。

#### Scenario: Knowledge Provider 向下游传值
- **WHEN** 正式 Provider 成功加载知识包
- **THEN** 下游 SHALL 从 KnowledgeSnapshot 接收 scanner 自有知识类型
- **AND** Detector MUST NOT 接收 Pydantic、JSON/YAML node、catalog recipe 或 legacy Rule 对象

#### Scenario: 现有测试构造空 Snapshot
- **WHEN** 现有 pipeline/component 测试不提供新增知识或归一事实字段
- **THEN** Snapshot 和 Observation SHALL 使用默认空 tuple 保持构造兼容
- **AND** 新内部字段 MUST NOT 自动成为新的主报告结构

### Requirement: Analyzer 必须显式接收同一扫描的知识快照
核心 `Analyzer` protocol SHALL 从 orchestrator 显式接收 ScanContext、NormalizedSnapshot 和同一次扫描加载的 KnowledgeSnapshot，并 SHALL 返回只包含 scanner-owned Entity、Relation、ProofPath 与 Diagnostic 的 AnalysisSnapshot/StageResult；Analyzer MUST NOT 通过全局状态、文件重读或 Legacy rule loader 获取知识。

#### Scenario: Pipeline 执行关系分析
- **WHEN** Knowledge Provider、Frontend 和 Normalizer 成功完成
- **THEN** orchestrator SHALL 把同一个 KnowledgeSnapshot 与 NormalizedSnapshot 传入 Analyzer
- **AND** Local Detector SHALL 在 Analyzer 之后接收该 AnalysisSnapshot

#### Scenario: 测试替换 Analyzer
- **WHEN** pipeline 单元测试注入 recording Analyzer
- **THEN** 测试 SHALL 能验证 knowledge/facts 的身份和确定调用顺序
- **AND** recording stage MUST NOT 读取 manifest、YAML 或源码

### Requirement: AnalysisSnapshot 扩展必须保持内部与输出兼容
AnalysisSnapshot SHALL 以默认空 tuple 承载 Analyzer 合成 Entity、Relation 和 ProofPath，现有空构造 SHALL 继续有效；这些内部对象 MUST NOT 自动序列化为第二个主结果，未来需要持久化的 proof SHALL 投影到现有 Finding `trace` 或其他既有兼容字段。

#### Scenario: 现有测试构造空分析结果
- **WHEN** recording/no-op Analyzer 或旧 component test 使用 `AnalysisSnapshot()`
- **THEN** 构造 SHALL 保持有效且表示没有已物化关系

#### Scenario: Qualification 产生图关系
- **WHEN** staged qualification 返回非空 Entity、Relation 和 ProofPath
- **THEN** recording/no-op Projector SHALL 不写 artifact
- **AND** 默认 CLI 的 `schemaVersion: "1.0"`、顶层字段和三个 artifact SHALL 保持不变

### Requirement: Staged qualification 必须能真实运行到 Local Detection
StagedPipelineRunner SHALL 允许 qualification profile 注入真实 Project Workspace Collector、组合 C/C++/Build Frontend、Knowledge Provider、组合 Normalizer、源码/Build/Test Selection Graph Analyzer、组合 Local/Build/Test Detector、Migration Classifier 和 Migration Assessor，同时使用 recording/no-op Report Projector；default profile SHALL 注入同一组正式分析阶段和 Compatible Report Projector，并由当前 `kb-scanner scan` 使用。

#### Scenario: 执行知识、源码关系、构建/测试选择、分类与评估 qualification
- **WHEN** fixture 包含有效 C/C++、受支持构建/打包/测试输入、compilation context 和 RISC-V porting 知识包
- **THEN** 同一个只读 ScanContext SHALL 沿固定阶段顺序产生 WorkspaceSnapshot、FrontendSnapshot、KnowledgeSnapshot、NormalizedSnapshot、AnalysisSnapshot、DetectionSnapshot、ClassificationSnapshot 和 AssessmentSnapshot
- **AND** recording Projector SHALL 能观察真实 selector、Relation、ProofPath、Observation、Classification、Assessment 及其引用

#### Scenario: qualification 存在外部验证缺口
- **WHEN** 输入完整性显示真实编译/测试、外部 RVWMO 或其他外部能力仍未执行
- **THEN** qualification SHALL 保留 partial/provisional/unknown Diagnostic 和 scope metadata
- **AND** pipeline MUST NOT 把该运行呈现为经过真实构建验证的 RISC-V readiness 扫描

#### Scenario: 默认应用运行现有 CLI
- **WHEN** 用户执行当前 `kb-scanner scan`
- **THEN** ScanApplication SHALL 选择完整 default staged profile 和正式 Compatible Report Projector
- **AND** qualification 的 recording/no-op Projector MUST NOT 进入默认路径或改变 Finding、summary、退出码和 artifact 行为

### Requirement: 正式输入阶段必须可组合 C/C++ 与构建 Frontend
Project Workspace Collector、Composite Frontend 和 Composite Normalizer SHALL 通过现有 WorkspaceSnapshot、FrontendSnapshot 和 NormalizedSnapshot 合并 C/C++ 与构建输入结果，并 SHALL 确定性验证 Entity/Evidence/Fact 引用、排序、Diagnostic 和 completion status；组合器 MUST NOT 把第三方 parser 类型、Legacy DTO 或新的外部报告结构引入核心合同。

#### Scenario: 两类 Frontend 均成功
- **WHEN** workspace 同时包含 C/C++ 与受支持构建输入
- **THEN** 同一个 FrontendSnapshot SHALL 保留两个正式 producer 的全部 scanner-owned Entity/Evidence
- **AND** Composite Normalizer SHALL 产生可由统一 Analyzer 消费的源码与构建 NormalizedFact

#### Scenario: 一个可选 Build adapter 部分失败
- **WHEN** C/C++ Frontend 成功但某构建输入不支持或机器产物缺失
- **THEN** 组合阶段 SHALL 保留 C/C++ 与其他构建结果并传播 partial/unavailable Diagnostic
- **AND** 缺失维度 MUST NOT 被转换为空成功或 RISC-V ready

#### Scenario: 现有独立 C/C++ profile
- **WHEN** 单元测试或旧 qualification 只注入既有 C/C++ Collector/Frontend/Normalizer
- **THEN** 现有 protocol、snapshot 构造和稳定身份 SHALL 继续有效
- **AND** 它 MUST NOT 被迫提供虚假的构建 Evidence
