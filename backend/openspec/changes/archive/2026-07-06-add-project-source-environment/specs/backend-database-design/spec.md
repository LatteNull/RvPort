## ADDED Requirements

### Requirement: 环境表必须支持单跳跳板机引用
数据库设计 SHALL 允许一个执行环境可选引用同项目内另一个环境作为 SSH 跳板机，并 SHALL 保持该引用可查询、可约束和可索引。

#### Scenario: 保存跳板机引用
- **WHEN** 用户为源环境或目标环境选择跳板机
- **THEN** 数据库 SHALL 在 `environments` 表保存可空的 `jump_host_environment_id`
- **AND** `jump_host_environment_id` SHALL 外键引用 `environments.id`
- **AND** 数据库 SHALL 为 `jump_host_environment_id` 建立索引

#### Scenario: 未配置跳板机
- **WHEN** 环境不需要通过跳板机访问
- **THEN** `environments.jump_host_environment_id` SHALL 允许为空

#### Scenario: 避免自引用
- **WHEN** 保存环境跳板机引用
- **THEN** 数据库或服务层 MUST NOT 允许 `jump_host_environment_id` 等于该环境自身 `id`

#### Scenario: 同项目跳板机约束
- **WHEN** 保存环境跳板机引用
- **THEN** 服务层 MUST 验证目标环境和跳板机环境属于同一项目
- **AND** 服务层 MUST 验证跳板机环境已启用

#### Scenario: MVP 不支持多级跳板
- **WHEN** 保存环境跳板机引用
- **THEN** 服务层 MUST NOT 允许被引用的跳板机环境自身再配置跳板机
