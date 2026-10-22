## ADDED Requirements

### Requirement: 构建运行表必须关联源码部署
数据库 schema SHALL 使 `build_runs` 能追溯构建使用的远端源码部署记录。

#### Scenario: 保存源码部署关联
- **WHEN** 后端创建构建运行
- **THEN** `build_runs` SHALL 保存 `source_deploy_run_id`
- **AND** `source_deploy_run_id` SHALL 外键引用 `source_deploy_runs.id`
- **AND** 后端 SHALL 保证 `project_id`、`source_revision_id`、`environment_id` 与被引用的源码部署记录一致

#### Scenario: 保存构建脚本摘要
- **WHEN** 后端保存构建运行
- **THEN** `build_runs.command` SHALL 保存脱敏后的构建命令摘要
- **AND** 完整构建脚本 SHALL 使用 `task_script_payloads` 加密保存
- **AND** `build_runs.command` MUST NOT 保存明文密码、token 或私钥

#### Scenario: 构建查询索引
- **WHEN** 后端按项目分页查询构建运行
- **THEN** 数据库 SHALL 支持按 `project_id, started_at desc` 查询
- **AND** 数据库 SHALL 支持按 `source_revision_id`、`environment_id`、`source_deploy_run_id` 和 `status` 过滤
