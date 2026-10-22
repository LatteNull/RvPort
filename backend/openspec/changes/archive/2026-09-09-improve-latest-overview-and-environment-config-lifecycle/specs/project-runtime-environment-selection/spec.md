## ADDED Requirements

### Requirement: 单环境配置版本必须参与项目运行 Context 生命周期
项目运行环境管理 SHALL 将当前 source 和 target 环境的有效配置版本纳入项目 Context 生命周期。

#### Scenario: 当前 source 环境有效配置变化
- **WHEN** 当前项目选中的 source 环境 `configVersion` 递增
- **THEN** 后端 SHALL 递增该项目的 `runtimeEnvironmentVersion`
- **AND** 依赖运行环境的当前构建、依赖分析、测试、报告、优化和归档结果 SHALL 变为旧 Context 历史事实

#### Scenario: 当前 target 环境有效配置变化
- **WHEN** 当前项目选中的 target 环境 `configVersion` 递增
- **THEN** 后端 SHALL 递增该项目的 `runtimeEnvironmentVersion`
- **AND** 后端 SHALL 要求当前双环境重新完成所需连接测试后才恢复就绪

#### Scenario: 非当前环境变化
- **WHEN** 某环境没有被项目选为当前 source 或 target
- **AND** 该环境有效配置发生变化
- **THEN** 后端 SHALL 递增该环境自身 `configVersion`
- **AND** 后端 MUST NOT 因此递增无引用项目的 `runtimeEnvironmentVersion`

#### Scenario: 当前环境变化发送 Context 事件
- **WHEN** 当前环境有效配置变化导致项目 `runtimeEnvironmentVersion` 递增
- **THEN** 后端 SHALL 为受影响项目追加 `project.context.changed` 事件
- **AND** 事件 SHALL 包含新的运行环境版本和受影响资源标识

#### Scenario: 同一请求同时更新双环境
- **WHEN** 一个操作同时改变当前 source 和 target 环境的有效配置
- **THEN** 每个环境 SHALL 分别递增自身 `configVersion`
- **AND** 同一项目的 `runtimeEnvironmentVersion` SHALL 在该业务操作中只递增一次
