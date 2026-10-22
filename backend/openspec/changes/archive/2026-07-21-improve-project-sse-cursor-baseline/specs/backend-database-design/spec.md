## ADDED Requirements

### Requirement: 数据库必须支持项目最新任务事件游标查询
数据库 SHALL 支持后端按项目查询最新任务事件 ID，用于项目 overview 返回 SSE baseline。

#### Scenario: 查询项目最新事件 ID
- **WHEN** 后端需要生成 `latestTaskEventId`
- **THEN** 数据库 SHALL 支持按 `project_id` 查询该项目最大的 `task_events.id`
- **AND** 没有事件时后端 SHALL 能返回 `0`

#### Scenario: 复用项目事件索引
- **WHEN** 后端补发项目级 SSE 事件或查询项目最新事件 ID
- **THEN** 查询 SHALL 使用 `task_events(project_id, id)` 或等效索引路径
- **AND** 后端 MUST NOT 只按全局 `id` 查询事件

#### Scenario: 历史事件保留
- **WHEN** 项目级 SSE 首次连接默认从最新事件之后开始
- **THEN** 数据库 SHALL 继续保留历史 `task_events`
- **AND** 历史事件 SHALL 继续可通过任务详情、任务列表或明确游标补发路径审计
