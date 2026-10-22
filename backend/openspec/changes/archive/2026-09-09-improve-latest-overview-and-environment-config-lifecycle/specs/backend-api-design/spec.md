## MODIFIED Requirements

### Requirement: 项目 overview 必须返回最新任务事件 ID
项目 overview API SHALL 返回稳定项目元数据、当前 Context、完整 Workflow 节点状态和当前项目最新任务事件 ID，供前端首屏展示并以该事件 ID 作为项目级 SSE baseline。

#### Scenario: 读取项目概览包含当前 Context
- **WHEN** 有项目访问权限的用户调用 `GET /api/projects/{projectId}/overview`
- **THEN** 响应 SHALL 包含 `project`、`currentContext`、`workflow` 和 `latestTaskEventId`
- **AND** `currentContext` SHALL 包含当前源码版本、source 环境、target 环境、项目运行环境版本和双环境就绪状态
- **AND** 后端 MUST NOT 在该响应中继续返回旧版领域空摘要、最近任务或推荐动作集合

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
- **AND** 后端 MUST NOT 暴露该项目的 Context、Workflow 状态或 `latestTaskEventId`

### Requirement: 领域 latest 接口必须使用统一响应外壳
需要 latest 的领域接口 SHALL 保留各自领域路径和结果结构，并 SHALL 使用统一 latest 外壳与活动执行优先的记录选择规则。

#### Scenario: 返回当前领域 latest
- **WHEN** 已登录用户调用某个领域 latest 接口
- **THEN** 后端 SHALL 校验用户对项目的访问权限
- **AND** 响应业务数据 SHALL 包含 `context`、`freshness`、`execution` 和 `result`
- **AND** `context` SHALL 包含当前 `sourceRevisionId` 和当前 `runtimeEnvironmentVersion`
- **AND** `result` SHALL 保持领域自己的结构

#### Scenario: 活动执行优先于终态结果
- **WHEN** 当前 Context 下存在状态为 `PENDING`、`QUEUED` 或 `RUNNING` 的对应领域执行
- **THEN** latest 接口 SHALL 返回最近创建的活动执行
- **AND** `execution.status` SHALL 保留任务的精确状态
- **AND** 后端 MUST NOT 返回更早的成功、失败、取消或超时执行作为 latest

#### Scenario: 无活动执行时返回最新终态
- **WHEN** 当前 Context 下不存在活动执行但存在终态执行
- **THEN** latest 接口 SHALL 返回最近创建的终态执行
- **AND** 后端 MUST NOT 跳过失败、取消或超时记录并回退到更早成功记录

#### Scenario: 无执行记录返回空 latest
- **WHEN** 当前 Context 下没有对应领域执行记录
- **THEN** latest 接口 SHALL 成功返回
- **AND** `freshness` SHALL 为 `EMPTY`
- **AND** `execution` SHALL 为 `null`
- **AND** `result` SHALL 为 `null`
- **AND** 后端 MUST NOT 使用 404 表达无 latest

#### Scenario: latest 标识旧 Context
- **WHEN** 领域存在历史记录但没有当前 Context 记录
- **THEN** latest 接口 SHALL 返回 `freshness=STALE` 或 `freshness=EMPTY`
- **AND** 后端 MUST NOT 将旧源码版本或旧运行环境版本的结果标记为 `CURRENT`
