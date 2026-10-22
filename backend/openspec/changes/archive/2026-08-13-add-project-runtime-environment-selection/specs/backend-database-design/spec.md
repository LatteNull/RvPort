## ADDED Requirements

### Requirement: 数据库必须保存项目运行环境配置和版本
数据库 SHALL 使用专用表保存每个项目当前运行环境配置，并 SHALL 使用版本号支持历史运行结果有效性判断。

#### Scenario: 保存项目运行环境配置
- **WHEN** 创建项目运行环境配置表
- **THEN** Schema SHALL 创建 `project_runtime_environments`
- **AND** 表 SHALL 包含 `project_id`、`source_environment_id`、`target_environment_id`、`version`、`updated_by`、`created_at` 和 `updated_at`
- **AND** `project_id` SHALL 唯一并外键引用 `projects.id`
- **AND** `source_environment_id` 和 `target_environment_id` SHALL 外键引用 `environments.id`
- **AND** `source_environment_id` 和 `target_environment_id` SHALL 允许为空以支持局部设置

#### Scenario: 运行记录保存环境配置版本
- **WHEN** 创建或维护 SBOM、源码部署、构建验证和自动化测试运行表
- **THEN** `sbom_runs`、`source_deploy_runs`、`build_runs` 和 `test_runs` SHALL 保存 `environment_config_version`
- **AND** 新创建的运行记录 SHALL 写入创建时的项目运行环境配置版本
- **AND** 查询响应 SHALL 能比较运行记录版本和当前配置版本

#### Scenario: 历史记录兼容
- **WHEN** 数据库中存在没有环境配置版本的历史运行记录
- **THEN** migration SHALL 使用受控默认值填充版本字段或允许后端将其识别为未知版本
- **AND** 后端 MUST NOT 删除历史运行记录

#### Scenario: 版本查询索引
- **WHEN** 创建环境配置版本字段
- **THEN** 数据库 SHALL 为按项目、源码版本、环境配置版本和创建时间查询的路径提供必要索引
- **AND** 查询当前运行环境结果时 SHALL 能有效过滤或标识非当前版本记录
