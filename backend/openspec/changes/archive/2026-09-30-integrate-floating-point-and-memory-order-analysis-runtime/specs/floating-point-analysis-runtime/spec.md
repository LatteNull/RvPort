## ADDED Requirements

### Requirement: 浮点分析必须消费当前构建上下文和共享 BC
系统 SHALL 仅基于当前源码版本、同源码版本成功的 source/x86 构建、真实 `compile_commands.json`、可用的 `SharedLlvmBitcodeArtifactSet@2.0` 以及可解析的源/目标 profile 创建浮点分析任务。

#### Scenario: 创建完整浮点分析
- **WHEN** 当前源码版本存在成功 x86 构建、compile database、至少一个校验成功的 produced BC record 和受支持的源/目标 profile
- **THEN** 后端 SHALL 创建 `FLOATING_POINT_ANALYSIS` 异步任务
- **AND** 运行记录 SHALL 固定源码版本、构建、artifact set、环境配置版本和工具协议版本

#### Scenario: 缺少可用 BC
- **WHEN** BC 为历史 v1、FAILED、哈希无效或没有 produced record
- **THEN** 后端 MUST 拒绝创建任务并返回明确的前置条件错误

#### Scenario: 部分 BC 可审计运行
- **WHEN** v2 artifact set 为 PARTIAL 但仍包含至少一个合法 produced record 和完整失败分母
- **THEN** 后端 SHALL 允许运行
- **AND** readiness 与最终结果 MUST 保留部分输入警告

### Requirement: Worker 必须通过统一 CLI 运行浮点扫描
Worker SHALL 生成符合工具最新请求 schema 的 request，先执行请求校验，再调用 `fp-precision-scanner scan`，且默认启用当前 schema 的全部稳定规则。

#### Scenario: 工具完整成功
- **WHEN** 工具返回退出码 0 且结果 schema v2 校验成功
- **THEN** 任务 SHALL 成功
- **AND** 运行状态 SHALL 为 COMPLETE，无论 Finding 数量是否为零

#### Scenario: 工具返回部分结果
- **WHEN** 工具返回退出码 4 且结果 schema v2 校验成功
- **THEN** 任务 SHALL 成功完成
- **AND** 分析运行状态 SHALL 为 PARTIAL 并保留 diagnostics 与分母

#### Scenario: 工具或协议失败
- **WHEN** 工具返回退出码 2、3 或 5，或结果缺失、损坏、版本不支持
- **THEN** 任务 SHALL 失败
- **AND** 后端 MUST NOT 导入成功态 Finding 或刷新当前迁移输入

### Requirement: 浮点 Finding 必须逐条保存并保持 v2 语义
后端 SHALL 独立保存每条浮点 Finding 的稳定 ID、规则、风险、置信度、状态、双语内容、位置、occurrences、validation plan、证据和 semantic digest。

#### Scenario: 导入带位置的 Finding
- **WHEN** v2 Finding 包含主位置和多个 occurrence
- **THEN** 列表 SHALL 保存主位置供排序过滤
- **AND** 详情 SHALL 返回完整 occurrence、evidenceChain 与 validationPlan

#### Scenario: Finding 缺少可定位主位置
- **WHEN** 合法 v2 Finding 的位置不可用或状态为 unknown
- **THEN** 后端 SHALL 保留该 Finding
- **AND** MUST NOT 伪造文件路径或行号

#### Scenario: 空 Finding 完整结果
- **WHEN** 合法完整结果的 Finding 数量为零
- **THEN** 运行 SHALL 成功并返回零计数
- **AND** 后端 MUST NOT 将其描述为所有浮点行为均安全

### Requirement: 浮点分析必须提供可审计制品
后端 SHALL 保存原始请求、结果 JSON 和后端生成的轻量 HTML，并保留工具版本、profile、build context、层级分母和 diagnostics。

#### Scenario: 下载分析制品
- **WHEN** 有项目权限的用户下载浮点分析 JSON 或 HTML
- **THEN** 后端 SHALL 返回该运行对应的不可变制品
- **AND** 内容 MUST NOT 暴露服务器路径、对象存储 key、凭据或环境变量值
