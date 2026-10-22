## ADDED Requirements

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
KB Scanner 的 `StagedPipelineRunner` SHALL 按工作区采集、输入前端、事实归一化、关系分析、局部检测、分类、项目评估和兼容报告投影的顺序执行阶段，并 SHALL 通过显式 profile 或构造参数注入各阶段实现；本阶段的默认 CLI MAY 继续选择独立的 legacy-compatible runner。

#### Scenario: 执行完整 pipeline
- **WHEN** 所有阶段均成功返回
- **THEN** orchestrator SHALL 按定义顺序把前序 scanner 自有结果传给后续阶段
- **AND** Report Projector SHALL 是写入正式 artifact 的唯一阶段

#### Scenario: 测试阶段编排
- **WHEN** 测试使用 recording stages 执行 pipeline
- **THEN** 测试 SHALL 能观察确定的调用顺序和输入传递
- **AND** orchestrator MUST NOT 通过隐藏的服务定位器或全局 plugin registry 选择组件

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

#### Scenario: 当前规则加载失败
- **WHEN** legacy rule loader 产生当前会影响 CLI 成功状态的错误
- **THEN** compatibility profile SHALL 保持该错误对退出码的现有影响
- **AND** 普通 compile context 降级 Diagnostic MUST NOT 被错误升级为同等失败

### Requirement: Legacy compatibility profile 必须支持渐进迁移
本 change 的默认运行 profile SHALL 通过 adapter 调用当前 compile command loader、项目解析、规则评估和报告逻辑，并 SHALL 把 legacy 私有状态限制在 adapter 内，使 CLI 可以先进入新 orchestrator 而不改变当前扫描行为。

#### Scenario: 使用默认 profile 扫描现有 fixture
- **WHEN** CLI 使用默认 compatibility profile 扫描任一现有规则 fixture
- **THEN** scanner SHALL 产生与当前实现语义等价的 Finding 和 Diagnostic
- **AND** legacy `ProjectFacts` 或其他私有 DTO MUST NOT 成为新 core protocol 的参数或返回类型

#### Scenario: 后续替换一个阶段
- **WHEN** 后续 change 为某一阶段提供正式新实现
- **THEN** pipeline SHALL 能通过 profile 替换该实现而不要求同步重写所有其他阶段
- **AND** 未替换的 legacy 行为 SHALL 保持可回归直至最终 cut-over

### Requirement: 新管线入口必须保持现有扫描结果兼容
通过新 orchestrator 执行扫描时，KB Scanner SHALL 保持现有 CLI 参数、退出码语义、`schemaVersion: "1.0"`、顶层字段、Finding 关键语义和三个 artifact，并 MUST NOT 产生替代现有 JSON 的第二个主结果文件。

#### Scenario: 成功扫描现有项目
- **WHEN** compatibility profile 完成扫描
- **THEN** scanner SHALL 继续生成 `scan-result.json`、`scan-report.html` 和 `scan.log`
- **AND** JSON SHALL 保留 `tool`、`rulePack`、`project`、`summary`、`findings` 和 `diagnostics` 顶层结构

#### Scenario: 核心对象包含新内部信息
- **WHEN** core pipeline 中存在现有结果未直接表达的内部对象
- **THEN** 本 change SHALL 保持该信息为内部状态或投影到既有兼容位置
- **AND** 新内部类型 MUST NOT 被直接序列化为新的主报告结构

### Requirement: 新管线入口必须保留现有知识和检测资产
Compatibility profile SHALL 继续原样加载现有 YAML 规则、`generatedSet`、`clang-x86-entries.json` 和 `gcc-x86-entries.json`，并 SHALL 保持当前高价值 x86 fixture 的检测语义。

#### Scenario: 加载 compiler-derived facts
- **WHEN** 新 orchestrator 扫描 RISC-V porting 规则包
- **THEN** Knowledge adapter SHALL 继续读取两份现有 JSON 的六类条目和来源信息
- **AND** 本 change MUST NOT 重生成、转换或删除这些数据

#### Scenario: 运行现有检测 fixture
- **WHEN** 独立测试容器执行当前规则与 generated-entry fixtures
- **THEN** 既有关键 rule ID、Finding 分类、阻断状态和位置 SHALL 不发生非预期退化
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
核心领域对象、orchestrator、legacy adapter 和兼容合同的正式测试 SHALL 在 `kb-scanner-test` 容器中运行，并 MUST NOT 要求开发者在宿主机安装扫描器依赖或修改生产镜像。

#### Scenario: 验证本 change
- **WHEN** 开发者构建并运行本 change 的正式测试
- **THEN** 测试 SHALL 使用 `tools/kb-scanner/Dockerfile.test` 和专属 Compose 服务
- **AND** `backend/Dockerfile`、根 Compose 和生产 API/worker 镜像 SHALL 保持不变

#### Scenario: 历史快照存在
- **WHEN** 默认测试或模块发现运行
- **THEN** `archive/2026-09-04-pre-rewrite` SHALL 只作为显式参考输入
- **AND** archive 中的包和测试 MUST NOT 被自动导入或重复执行
