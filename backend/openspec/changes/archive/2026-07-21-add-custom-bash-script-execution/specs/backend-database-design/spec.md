## ADDED Requirements

### Requirement: 数据库必须安全保存脚本正文引用
数据库 SHALL 提供受控脚本正文存储，使 `CUSTOM_BASH` 任务可以在 worker 执行时读取脚本正文，同时避免脚本正文进入任务输入快照和事件流。

#### Scenario: 创建脚本正文存储
- **WHEN** 执行数据库迁移
- **THEN** Schema SHALL 创建脚本正文存储表或等效持久化结构
- **AND** 每条记录 SHALL 关联 `project_id`、`task_id`、创建人和创建时间
- **AND** 每条记录 SHALL 保存脚本 SHA256、脚本长度和加密后的脚本正文
- **AND** 数据库 MUST NOT 在普通明文字段保存脚本正文

#### Scenario: 脚本正文与任务唯一关联
- **WHEN** 后端保存 `CUSTOM_BASH` 脚本正文
- **THEN** 该脚本正文 SHALL 关联唯一任务
- **AND** 数据库 SHALL 防止同一任务关联多个活跃脚本正文
- **AND** 任务输入快照 SHALL 只引用脚本正文记录 ID、脚本 SHA256 和脚本长度

#### Scenario: 脚本正文查询路径
- **WHEN** worker 根据任务读取脚本正文
- **THEN** 数据库 SHALL 支持按 `task_id` 查询脚本正文记录
- **AND** 数据库 SHALL 支持按 `project_id, created_at desc` 查询脚本正文摘要
- **AND** API 查询 MUST NOT 返回加密脚本正文或明文脚本正文

#### Scenario: 脚本正文安全边界
- **WHEN** 写入或读取脚本正文
- **THEN** 后端 SHALL 使用应用层加密保护脚本正文
- **AND** 审计日志、任务事件、任务日志摘要和 API 响应 MUST NOT 包含脚本正文

### Requirement: 数据库必须持久化任务日志事件
数据库 SHALL 提供 `task_log_events` 或等效持久化结构，用于任务级日志 SSE 的历史补发、断线恢复和实时展示。

#### Scenario: 创建任务日志事件表
- **WHEN** 执行数据库迁移
- **THEN** Schema SHALL 创建 `task_log_events` 表
- **AND** 表 SHALL 包含 `id`、`project_id`、`task_id`、`log_type`、`sequence`、`content` 和 `created_at`
- **AND** `id` SHALL 是单调递增游标
- **AND** `project_id` SHALL 引用 `projects.id`
- **AND** `task_id` SHALL 引用 `tasks.id`

#### Scenario: 限制日志事件类型
- **WHEN** 创建或维护 `task_log_events`
- **THEN** `log_type` SHALL 限定为 `STDOUT` 或 `STDERR`
- **AND** `content` SHALL 为非空受控长度文本
- **AND** 同一任务内 `sequence` SHALL 可用于稳定排序

#### Scenario: 索引任务日志事件恢复路径
- **WHEN** 创建 `task_log_events` 表
- **THEN** 数据库 SHALL 为 `task_id, id` 建立索引
- **AND** SHALL 为 `project_id, task_id, id` 建立索引
- **AND** SHALL 为 `task_id, sequence` 建立唯一索引或等效约束

#### Scenario: 日志事件不替代完整日志文件
- **WHEN** worker 写入 stdout 或 stderr
- **THEN** 数据库 SHALL 保存任务日志事件用于实时展示
- **AND** `task_logs` SHALL 继续保存完整日志文件元数据
- **AND** `task_log_events.content` MUST NOT 保存明文凭据、私钥、token、passphrase 或服务器真实绝对路径

### Requirement: 数据库必须支持脚本执行记录查询
数据库设计 SHALL 允许后端从任务、工具运行、脚本正文摘要和日志事件中聚合脚本执行记录。

#### Scenario: 查询脚本执行记录列表
- **WHEN** 后端查询项目脚本执行记录
- **THEN** 数据库 SHALL 支持按 `project_id`、任务类型 `ENV_RUN_SCRIPT`、脚本类型和创建时间分页查询
- **AND** 数据库 SHALL 支持关联最近 `tool_runs` 执行结果
- **AND** 数据库 SHALL 支持关联最近日志事件摘要

#### Scenario: 查询脚本执行详情
- **WHEN** 后端查询单个脚本执行记录
- **THEN** 数据库 SHALL 支持通过任务 ID 找到任务、环境引用、脚本摘要、工具执行记录和日志统计
- **AND** 查询结果 MUST NOT 需要读取明文脚本正文
