## MODIFIED Requirements

### Requirement: 项目 overview 必须返回最新任务事件 ID
项目 overview API SHALL 返回稳定项目元数据、当前 Context、完整 Workflow 节点状态、最近任务和当前项目最新任务事件 ID，供前端首屏展示并以该事件 ID 作为项目级 SSE baseline。

#### Scenario: 读取项目概览包含当前 Context 和最近任务
- **WHEN** 有项目访问权限的用户调用 `GET /api/projects/{projectId}/overview`
- **THEN** 响应 SHALL 包含 `project`、`currentContext`、`workflow`、`recentTasks` 和 `latestTaskEventId`
- **AND** `currentContext` SHALL 包含当前源码版本、source 环境、target 环境、项目运行环境版本和双环境就绪状态
- **AND** `recentTasks` SHALL 返回当前项目按 `createdAt` 和任务 ID 倒序排列的最近 5 条任务
- **AND** 当前项目没有任务时 `recentTasks` SHALL 返回空数组
- **AND** 后端 MUST NOT 在该响应中恢复旧版领域空摘要或推荐动作集合

#### Scenario: overview 返回全部 Workflow 节点
- **WHEN** 后端生成项目 overview
- **THEN** `workflow.stages` SHALL 恰好包含 `project`、`env`、`assets`、`kb`、`x86-build`、`rv-dependency-analysis`、`report`、`manual`、`build`、`test`、`optimize` 和 `archive`
- **AND** 每个节点 SHALL 包含稳定 `id`、`status` 和可空 `reasonCode`
- **AND** `status` SHALL 仅使用 `PENDING`、`RUNNING`、`DONE` 或 `BLOCKED`

#### Scenario: overview 优先展示当前运行状态
- **WHEN** 某节点在当前 Context 存在 `PENDING`、`QUEUED` 或 `RUNNING` 任务
- **THEN** 该 Workflow 节点状态 SHALL 为 `RUNNING`
- **AND** 后端 MUST NOT 使用该节点更早的成功或失败结果覆盖运行状态

#### Scenario: overview 返回 latestTaskEventId
- **WHEN** 前端读取项目 overview
- **THEN** `latestTaskEventId` SHALL 为当前项目在该快照读取边界内可见的最新 `task_events.id`
- **AND** 当前项目没有任务事件时 SHALL 返回 `0`
- **AND** 后端 MUST NOT 返回会使前端跳过业务状态变化的“旧业务快照与新事件游标”组合

#### Scenario: 无权限读取 overview
- **WHEN** 用户无权访问目标项目
- **THEN** 后端 SHALL 拒绝返回 overview
- **AND** 后端 MUST NOT 暴露该项目的 Context、Workflow 状态、最近任务或 `latestTaskEventId`
