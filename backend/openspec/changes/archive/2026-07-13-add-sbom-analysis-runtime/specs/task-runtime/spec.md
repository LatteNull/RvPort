## ADDED Requirements

### Requirement: 任务运行时必须支持 SBOM_ANALYSIS 任务类型
任务运行时 SHALL 支持 `SBOM_ANALYSIS` 长任务类型，并通过既有 worker handler 机制执行 SBOM 分析。

#### Scenario: 创建 SBOM 分析任务
- **WHEN** SBOM API 请求创建分析
- **THEN** 任务运行时 SHALL 创建任务类型为 `SBOM_ANALYSIS` 的 `tasks` 记录
- **AND** 任务输入快照 SHALL 包含项目 ID、源环境 ID、目标环境 ID、源快照 ID、目标快照 ID、仓库策略和分析选项
- **AND** 任务输入快照 MUST NOT 包含明文凭据、服务器真实路径或完整分析器输入 JSON

#### Scenario: Worker 执行 SBOM handler
- **WHEN** worker 认领 `SBOM_ANALYSIS` 任务
- **THEN** worker SHALL 分发到 SBOM handler
- **AND** handler SHALL 通过任务执行上下文读取输入、更新进度、写入日志和完成任务

#### Scenario: 缺少 SBOM handler
- **WHEN** worker 认领 `SBOM_ANALYSIS` 任务但未注册 handler
- **THEN** 任务 SHALL 按既有缺少 handler 规则失败
- **AND** 错误码 SHALL 表示任务 handler 不存在

### Requirement: SBOM_ANALYSIS 必须写入工具执行记录和任务日志
SBOM_ANALYSIS handler SHALL 将分析器调用记录为 tool run，并保存 stdout/stderr 日志元数据。

#### Scenario: 分析器调用成功
- **WHEN** SBOM 分析器返回成功
- **THEN** 后端 SHALL 写入 `tool_runs`
- **AND** `tool_runs.tool_name` SHALL 使用稳定 SBOM 分析器工具名
- **AND** `tool_runs.exit_code` SHALL 保存分析器退出码
- **AND** `tool_runs.summary` SHALL 保存分析器版本、输入摘要、输出摘要、耗时和解析警告
- **AND** 后端 SHALL 通过 `task_logs` 保存 stdout/stderr 日志文件元数据和安全 excerpt

#### Scenario: 分析器调用失败
- **WHEN** SBOM 分析器进程启动失败、超时或返回非零退出码
- **THEN** 后端 SHALL 写入失败态 `tool_runs`
- **AND** 后端 SHALL 保存 stdout/stderr 日志文件元数据
- **AND** 任务失败摘要 MUST NOT 暴露服务器真实路径或完整工具输入

### Requirement: SBOM_ANALYSIS 必须通过 SSE 推送任务状态
SBOM_ANALYSIS 任务 SHALL 复用项目级 SSE 推送进度、日志摘要和终态事件。

#### Scenario: 推送进度
- **WHEN** SBOM handler 完成输入导出、工具执行、结果解析和结果落库阶段
- **THEN** handler SHALL 通过任务执行上下文写入进度事件
- **AND** 项目级 SSE SHALL 能向有权限用户推送这些事件

#### Scenario: 推送终态
- **WHEN** SBOM_ANALYSIS 任务成功或失败
- **THEN** worker SHALL 写入对应终态事件
- **AND** 前端 SHALL 能通过项目级 SSE 或任务详情查询获得最终状态
