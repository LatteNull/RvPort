## ADDED Requirements

### Requirement: KB 扫描运行表必须支持异步任务和摘要查询
数据库 SHALL 使用 `kb_scan_runs` 保存 KB 扫描运行事实，并 SHALL 支持按项目、源码版本和状态查询。

#### Scenario: 创建 KB 扫描运行
- **WHEN** 后端创建 KB 扫描任务
- **THEN** 数据库 SHALL 保存 `kb_scan_runs` 记录
- **AND** `project_id` SHALL 关联项目
- **AND** `task_id` SHALL 唯一关联 `tasks.id`
- **AND** `source_revision_id` SHALL 关联被扫描源码版本
- **AND** `status` SHALL 使用 `PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **AND** `scope` SHALL 保存扫描范围、排除路径、语言、目标架构和规则集摘要

#### Scenario: 更新运行摘要
- **WHEN** KB 扫描完成或失败
- **THEN** `kb_scan_runs.summary` SHALL 保存 schema version、tool version、rule pack、文件数、finding 数量、severity counts、diagnostics 摘要和 artifact 摘要
- **AND** summary MUST NOT 保存源码工作副本路径、scanner 输出目录、明文凭据或完整 stdout/stderr

#### Scenario: 查询 KB 扫描运行
- **WHEN** 创建或维护 `kb_scan_runs`
- **THEN** 数据库 SHALL 为 `project_id, started_at desc` 建立索引
- **AND** 数据库 SHALL 为 `source_revision_id` 建立索引
- **AND** 如实现支持按状态过滤，数据库 MAY 为 `project_id, status, started_at desc` 建立索引

### Requirement: Findings 表必须支持 KB 扫描结果分页审计
数据库 SHALL 将 KB Scanner 输出的每条 finding 保存为独立 `findings` 记录。

#### Scenario: 保存 finding
- **WHEN** 后端导入 `scan-result.json`
- **THEN** 每条 finding SHALL 保存 `project_id`、`scan_run_id`、`source_revision_id`、`rule_id`、`category`、`severity`、`title`、`file_path`、`line_start`、`line_end`、`symbol`、`evidence`、`suggestion`、`fingerprint`、`status` 和 `created_at`
- **AND** `status` SHALL 使用 `DETECTED` 或 `SUPPRESSED`
- **AND** `evidence` SHALL 保存受控 scanner evidence、confidence、snippet、trace、condition macros 和 build context
- **AND** `evidence` MUST NOT 保存服务器真实路径、完整 scanner output、明文凭据或完整任务输入快照

#### Scenario: Finding 行号约束
- **WHEN** 创建或更新 finding
- **THEN** `line_start` 和 `line_end` SHALL 在非空时大于 0
- **AND** `line_end` 在非空时 SHALL 大于或等于 `line_start`

#### Scenario: Finding 查询索引
- **WHEN** 创建或维护 `findings` 表
- **THEN** 数据库 SHALL 为 `scan_run_id` 建立索引
- **AND** 数据库 SHALL 为 `project_id, severity` 建立索引
- **AND** 数据库 SHALL 为 `source_revision_id` 建立索引
- **AND** 数据库 SHALL 为 `fingerprint` 建立索引
- **AND** 数据库 SHALL 为 `file_path` 建立索引

### Requirement: KB 扫描 artifact 元数据必须受控保存
数据库 SHALL 支持保存 KB 扫描输出文件的轻量 metadata 或等效报告记录，避免 API 暴露本地文件系统路径。

#### Scenario: 保存 KB artifact
- **WHEN** 后端保存 `scan-result.json`、`scan-report.html` 或 `scan.log` 的 artifact metadata
- **THEN** 每条 artifact SHALL 关联 `project_id`、`task_id` 和 `scan_run_id`
- **AND** artifact SHALL 保存 artifact type、schema version、sha256、size bytes、summary、created at 和受控文件引用
- **AND** artifact type SHALL 至少能表达 `SCAN_RESULT_JSON`、`SCAN_REPORT_HTML` 和 `SCAN_LOG`

#### Scenario: Artifact 内容限制
- **WHEN** 后端保存 KB artifact metadata、summary 或 content
- **THEN** 数据库 MUST NOT 保存明文凭据、私钥、token、passphrase、完整任务输入快照或未经脱敏的完整日志
- **AND** API 可见字段 MUST NOT 暴露后端服务器真实绝对路径

#### Scenario: Artifact 查询索引
- **WHEN** 创建或维护 KB artifact metadata
- **THEN** 数据库 SHALL 支持按 `scan_run_id` 查询 artifact
- **AND** 数据库 SHALL 支持按 `task_id` 追溯 artifact
- **AND** 数据库 SHALL 防止同一扫描运行下同一 artifact type 出现不可解释的重复成功记录
