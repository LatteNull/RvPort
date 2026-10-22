## MODIFIED Requirements

### Requirement: SBOM 运行时必须复用现有数据库表
SBOM 分析运行时 SHALL 优先复用现有环境快照、环境组件、任务、工具执行和 SBOM 结果表，不得为 MVP 引入通用 artifact 表。SBOM 分析 MAY 引入仅服务 SBOM 领域的专用分析结果明细表和轻量 artifact 摘要表，用于保存可查询的结果行和非敏感审计摘要。

#### Scenario: 保存环境组件来源
- **WHEN** 环境采集写入 `environment_components`
- **THEN** `source` SHALL 使用稳定来源值表达组件来源
- **AND** 来源值 SHALL 至少包含 `INSTALLED_PACKAGE`、`INSTALLED_LIBRARY`、`TOOL_VERSION`、`NATIVE_FILE`、`REPOSITORY_PACKAGE` 和 `REPOSITORY_PROVIDE`

#### Scenario: 保存 SBOM 运行结果
- **WHEN** SBOM_ANALYSIS 成功完成
- **THEN** 后端 SHALL 使用 `sbom_runs` 保存运行记录
- **AND** SHALL 使用 `sbom_components` 保存组件事实
- **AND** SHALL 使用 `replacement_candidates` 保存替代候选
- **AND** SHALL 使用 `tool_runs` 和 `task_logs` 保存分析器执行记录和日志元数据
- **AND** SHALL 使用 `sbom_analysis_result_items` 按行保存分析结果明细
- **AND** SHALL 使用 `sbom_analysis_artifacts` 保存轻量分析摘要 artifact

#### Scenario: 不新增通用 artifact 表
- **WHEN** 保存分析器输入、输出或日志
- **THEN** 后端 MUST NOT 引入通用 artifact 表
- **AND** 完整日志 SHALL 继续通过 `task_logs` 元数据和本地日志文件管理
- **AND** 可查询结果明细 SHALL 保存到 SBOM 专用 `sbom_analysis_result_items` 表
- **AND** 可追溯摘要 SHALL 保存到 `summary`、`metadata` JSON 字段或 SBOM 专用 `sbom_analysis_artifacts` 表

#### Scenario: 保存 SBOM 分析结果明细
- **WHEN** 后端写入 `sbom_analysis_result_items`
- **THEN** 每条记录 SHALL 表示一条 package、library、tool 或 native file 分析结果
- **AND** 每条记录 SHALL 同时关联 `project_id`、`task_id` 和 `sbom_run_id`
- **AND** 记录 SHALL 保存组件类型、源名称、源版本、源架构、源包名、目标匹配状态、目标名称、目标版本、目标包名、风险等级、匹配策略、建议动作和创建时间等可查询字段
- **AND** 记录 MAY 保存有限 `evidence` JSONB
- **AND** `evidence` MUST 只保存解释匹配所需的有限证据，不得保存完整 analyzer output 原文

#### Scenario: 索引 SBOM 分析结果明细查询路径
- **WHEN** 创建 `sbom_analysis_result_items` 表
- **THEN** 数据库 SHALL 为 `sbom_run_id, created_at DESC` 建立索引
- **AND** SHALL 为 `project_id, task_id` 建立索引
- **AND** SHALL 为 `sbom_run_id, component_type` 建立索引
- **AND** SHALL 为 `sbom_run_id, source_name` 建立索引
- **AND** SHALL 为 `sbom_run_id, risk_level` 建立索引
- **AND** SHALL 为 `sbom_run_id, target_match_status` 建立索引

#### Scenario: 保存 SBOM 专用 artifact 关联
- **WHEN** 后端写入 `sbom_analysis_artifacts`
- **THEN** 每条记录 SHALL 同时关联 `project_id`、`task_id` 和 `sbom_run_id`
- **AND** `project_id` SHALL 引用该 SBOM 运行所属项目
- **AND** `task_id` SHALL 引用该 SBOM 运行对应的 `SBOM_ANALYSIS` 任务
- **AND** `sbom_run_id` SHALL 引用该 SBOM 运行记录

#### Scenario: 限制 SBOM artifact 类型和唯一性
- **WHEN** 后端写入 `sbom_analysis_artifacts`
- **THEN** `artifact_type` SHALL 使用稳定枚举值
- **AND** 同一 `sbom_run_id` 下同一 `artifact_type` MUST NOT 重复
- **AND** 同一 `task_id` 下同一 `artifact_type` MUST NOT 重复
- **AND** `size_bytes` MUST 大于 0

#### Scenario: 索引 SBOM artifact 查询路径
- **WHEN** 创建 `sbom_analysis_artifacts` 表
- **THEN** 数据库 SHALL 为 `project_id, created_at DESC` 建立索引
- **AND** SHALL 为 `task_id` 建立索引
- **AND** SHALL 为 `sbom_run_id` 建立索引
- **AND** SHALL 为 `project_id, task_id` 建立索引

### Requirement: SBOM 数据不得保存敏感信息
SBOM 相关表中的摘要、元数据和 artifact 内容 SHALL 避免保存明文凭据、私钥、token、passphrase、完整任务日志和服务器真实绝对路径。

#### Scenario: 写入分析器摘要
- **WHEN** 后端保存 `sbom_runs.summary`、`sbom_components.metadata` 或 `replacement_candidates.metadata`
- **THEN** 写入内容 MUST NOT 包含明文凭据
- **AND** 写入内容 MUST NOT 包含服务器真实绝对路径
- **AND** 必要路径信息 SHALL 使用文件名、远端相对摘要、哈希或遮蔽值表达

#### Scenario: 写入 SBOM artifact 和结果明细
- **WHEN** 后端保存 `sbom_analysis_artifacts.content` 或 `sbom_analysis_artifacts.summary`
- **THEN** 写入内容 MUST NOT 包含明文凭据、私钥、token 或 passphrase
- **AND** 写入内容 MUST NOT 包含完整任务日志
- **AND** 写入内容 MUST NOT 复制完整 `environment_snapshots.raw_snapshot`
- **AND** 写入内容 MUST NOT 包含服务器真实绝对路径
- **AND** artifact SHALL 保存 `sha256` 和 `size_bytes` 以支持审计
- **AND** `sbom_analysis_result_items.evidence` MUST NOT 包含完整 analyzer output 原文

#### Scenario: 写入失败摘要
- **WHEN** SBOM_ANALYSIS 失败并保存任务错误信息或 tool run summary
- **THEN** 错误信息 MUST NOT 包含明文凭据、服务器真实绝对路径或完整分析器输入 JSON
