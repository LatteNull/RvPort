## MODIFIED Requirements

### Requirement: MVP 不包含通用 artifact 持久化
MVP 数据库设计 SHALL NOT 为源码包、源码工作副本或 Git checkout 等源码输入制品引入通用 artifact 表。后端运行产生的报告、扫描输出、日志归档和项目归档等输出制品 MAY 使用统一对象存储元数据表保存可查询元数据。

#### Scenario: 生成报告
- **WHEN** 生成 HTML 或 JSON 报告
- **THEN** 报告记录 SHALL 保存报告业务元数据
- **AND** 报告文件内容 SHALL 保存到对象存储或受控输出存储
- **AND** 数据库 MAY 通过后端输出制品元数据记录引用报告文件

#### Scenario: 生成归档
- **WHEN** 生成归档包
- **THEN** 归档记录 SHALL 保存归档业务元数据
- **AND** 归档包内容 MAY 保存到对象存储
- **AND** 数据库 MAY 通过后端输出制品元数据记录引用归档包

#### Scenario: 源码输入制品不进入通用输出制品表
- **WHEN** 用户上传源码包、后端创建源码工作副本或 Git 同步源码
- **THEN** 数据库 MUST NOT 将源码包、源码工作副本或 Git checkout 作为后端输出制品写入统一 artifact 元数据表
- **AND** 源码版本事实 SHALL 继续由 `source_revisions` 和 `source_imports` 表表达

## ADDED Requirements

### Requirement: 后端输出制品元数据必须支持对象存储
数据库 SHALL 支持保存后端运行产生的输出制品对象存储元数据。

#### Scenario: 创建输出制品元数据表
- **WHEN** 数据库创建或维护后端输出制品元数据表
- **THEN** 表 SHALL 包含主键、`project_id`、`task_id`、`owner_type`、`owner_id`、`artifact_type`、`bucket`、`object_key`、`content_type`、`size_bytes`、`sha256`、`summary` 和 `created_at`
- **AND** `project_id` SHALL 引用 `projects(id)`
- **AND** `task_id` MAY 引用 `tasks(id)`

#### Scenario: 输出制品查询索引
- **WHEN** 后端按业务归属查询输出制品
- **THEN** 数据库 SHALL 提供 `owner_type + owner_id + artifact_type` 查询能力
- **AND** 数据库 SHALL 支持按 `project_id` 和 `created_at` 查询
- **AND** 数据库 SHALL 支持按 `task_id` 追溯制品

#### Scenario: 输出制品内容安全
- **WHEN** 后端保存输出制品元数据
- **THEN** `summary` MUST NOT 包含明文凭据、私钥、token、passphrase、完整任务日志或服务器真实绝对路径
- **AND** `object_key` MUST NOT 包含服务器真实绝对路径
