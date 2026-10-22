## ADDED Requirements

### Requirement: 数据库必须持久化环境配置版本及结果归属
数据库 SHALL 持久化单环境配置版本，并 SHALL 使环境任务和环境快照能够证明其所属配置版本。

#### Scenario: 环境表保存配置版本
- **WHEN** Liquibase 应用本 change 的迁移
- **THEN** `environments` SHALL 增加非空 `config_version`
- **AND** 现有环境 SHALL 幂等回填为版本 `1`
- **AND** 新环境 SHALL 默认从版本 `1` 开始

#### Scenario: 环境快照保存配置版本
- **WHEN** 后端保存环境采集快照
- **THEN** `environment_snapshots` SHALL 保存对应 `environment_config_version`
- **AND** 当前快照查询 SHALL 能按环境 ID 和当前配置版本筛选

#### Scenario: 环境任务保存配置版本
- **WHEN** 后端创建会影响环境当前事实的任务或执行记录
- **THEN** 持久化数据 SHALL 保存创建时的 `environment_config_version`
- **AND** 完成回写 SHALL 能通过数据库条件更新验证版本仍一致

#### Scenario: 支持当前版本查询性能
- **WHEN** 后端按环境及配置版本查询最新成功快照或活动任务
- **THEN** 数据库 SHALL 提供匹配查询模式的索引
- **AND** 查询 MUST NOT 依赖扫描全部历史快照或全部项目任务

#### Scenario: Schema 变更由 Liquibase 管理
- **WHEN** 开发者构建或部署后端
- **THEN** 所有新增表字段、默认值、约束和索引 SHALL 由 Liquibase changelog 创建
- **AND** 开发者 MUST NOT 通过手工建表替代迁移
- **AND** jOOQ 生成代码 SHALL 在迁移后的 Schema 上重新生成并保存到约定源码目录
