## ADDED Requirements

### Requirement: 环境任务必须绑定环境配置版本并阻止旧任务回写
会读取或更新环境当前事实的任务 SHALL 在创建时绑定环境配置版本，并 SHALL 防止旧配置版本任务晚到完成后覆盖当前状态。

#### Scenario: 创建环境连接测试任务
- **WHEN** 后端为已保存环境创建连接测试任务
- **THEN** 任务输入 SHALL 保存任务创建时的 `environmentConfigVersion`
- **AND** Worker SHALL 使用该版本执行完成回写校验

#### Scenario: 创建环境采集任务
- **WHEN** 后端为已保存环境创建基础信息或依赖信息采集任务
- **THEN** 任务输入 SHALL 保存任务创建时的 `environmentConfigVersion`
- **AND** 新建环境快照 SHALL 保存相同配置版本

#### Scenario: 当前版本任务完成
- **WHEN** 环境任务完成时其 `environmentConfigVersion` 等于环境当前 `configVersion`
- **THEN** 后端 MAY 更新环境当前状态、连接时间、采集时间和当前快照引用
- **AND** 后端 SHALL 按任务结果追加正常生命周期事件

#### Scenario: 旧版本任务晚到成功
- **WHEN** 环境任务完成时其 `environmentConfigVersion` 小于环境当前 `configVersion`
- **THEN** 后端 SHALL 保留任务、日志和历史快照
- **AND** 后端 MUST NOT 更新环境当前状态、连接时间、采集时间或当前基础信息
- **AND** 后端 MUST NOT 使项目当前 `env` 节点变为 `DONE`

#### Scenario: 旧版本任务晚到失败
- **WHEN** 旧配置版本环境任务在配置更新后失败
- **THEN** 后端 SHALL 保存该任务失败事实用于历史审计
- **AND** 后端 MUST NOT 将当前环境状态改为不可用或将当前 Workflow 节点标记为该旧失败导致的 `BLOCKED`
