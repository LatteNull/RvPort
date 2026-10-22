## ADDED Requirements

### Requirement: 数据库必须支持远程自动化测试输出和日志引用
数据库 SHALL 支持保存自动化测试在远程环境中的执行摘要、输出摘要、日志引用和报告产物引用，并 SHALL 允许通过项目、源码版本、环境和状态查询。

#### Scenario: 保存测试输出摘要
- **WHEN** 自动化测试任务创建或完成
- **THEN** 数据库 SHALL 保存测试运行记录并关联 `project_id`、`task_id`、`source_revision_id`、`environment_id` 和可选 `build_run_id`
- **AND** 数据库 SHALL 保存退出码、状态、输出摘要、stdout 日志引用、stderr 日志引用、报告 artifact 摘要、开始时间和结束时间
- **AND** 数据库 MUST NOT 保存明文凭据、SSH 私钥、token、passphrase 或服务器真实敏感路径

#### Scenario: 测试运行查询索引
- **WHEN** 创建或维护自动化测试运行表
- **THEN** 数据库 SHALL 支持按 `project_id, started_at desc` 查询
- **AND** 数据库 SHALL 支持按 `source_revision_id`、`environment_id` 和 `build_run_id` 查询
- **AND** 数据库 SHALL 支持按 `project_id, status, started_at desc` 查询

#### Scenario: 不保存完整日志正文
- **WHEN** 测试产生 stdout 或 stderr
- **THEN** 数据库 SHALL 只保存日志文件引用、大小、哈希和受控摘要
- **AND** 完整日志正文 SHALL 继续由任务日志文件或受控制品保存

#### Scenario: 保存测试报告 artifact 引用
- **WHEN** 自动化测试回收远端文字报告文件
- **THEN** 数据库 SHALL 通过 `test_runs` 摘要字段、`stored_artifacts` 或等效受控结构保存报告 artifact 引用
- **AND** 报告 artifact SHALL 关联 `project_id`、`task_id` 和测试运行 ID
- **AND** 数据库 MUST NOT 保存服务器真实路径或远端敏感绝对路径
