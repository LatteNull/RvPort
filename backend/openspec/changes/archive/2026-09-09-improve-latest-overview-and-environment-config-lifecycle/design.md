## Context

当前后端已经具备领域 latest、项目 overview、项目运行双环境版本和项目级 SSE，但三者的“当前事实”口径并不一致：部分领域按照完成时间查 latest，导致运行中任务被旧终态遮蔽；overview 仍是早期统计摘要，不能一次返回全部 Workflow 节点状态；环境编辑只修改可用状态并递增项目环境版本，没有单环境配置版本，旧连接时间、旧采集快照以及晚到任务可能再次成为当前数据。

本 change 只修改后端契约和生命周期，不修改前端。所有状态均以当前源码版本和当前项目运行环境版本组成的 Context 为边界。

## Goals / Non-Goals

**Goals:**

- 统一各领域 latest 的活动执行优先语义，避免旧成功或旧失败遮蔽当前运行。
- 将 overview 收敛为稳定项目信息、当前 Context、完整 Workflow 节点状态和 SSE baseline。
- 为单个环境建立配置版本，使连接测试、采集快照和晚到任务结果均可判断是否属于当前配置。
- 在当前 source/target 环境的有效配置变化时递增项目运行环境版本，使依赖环境的节点结果自然失效。
- 保证 overview 快照与 `latestTaskEventId` 之间不存在会跳过状态变化的读取窗口。

**Non-Goals:**

- 不修改前端页面、节点坐标、按钮或展示文案。
- 不改变领域结果 DTO 的业务字段，也不把所有 latest 合并为一个通用接口。
- 不删除旧任务、旧快照或旧领域结果；它们仍可用于历史审计。
- 不把环境名称等纯展示字段修改视为运行环境变化。
- 不在本 change 中引入新的 Workflow 节点或改变业务节点顺序。

## Decisions

### 1. latest 使用“活动执行优先、否则最新终态”的统一选择器

每个领域仍保留自己的 latest endpoint 和 result DTO，但仓储查询或服务层选择必须遵循同一规则：

1. 只在当前 Context 中查找该领域记录。
2. 若存在 `PENDING`、`QUEUED` 或 `RUNNING` 执行，返回其中最近创建的活动执行。
3. 若不存在活动执行，返回最近创建的终态执行，包括失败、取消和超时；不得跳过失败回退到旧成功。
4. 当前 Context 无记录时返回 `EMPTY`；只有显式查询历史 Context 时才表达历史事实。

latest 的 `execution.status` 保留任务精确状态，不将 `PENDING` 或 `QUEUED` 改写成 `RUNNING`。Workflow 节点聚合时再将三种活动状态统一映射为节点 `RUNNING`。

这样既保留 API 的诊断精度，也保证“用户刚启动的任务就是当前任务”。

### 2. overview 返回固定 Context 与完整 Workflow 快照

`GET /api/projects/{projectId}/overview` 调整为以下概念结构：

```text
project
currentContext
  activeSourceRevision
  runtimeEnvironments
    sourceEnvironment
    targetEnvironment
    version
    ready
workflow
  recommendedStageId
  stages[]
latestTaskEventId
```

`stages[]` 必须固定包含且仅包含：`project`、`env`、`assets`、`kb`、`x86-build`、`rv-dependency-analysis`、`report`、`manual`、`build`、`test`、`optimize`、`archive`。每项返回 `id`、`status` 和可空的稳定 `reasonCode`。

节点状态统一为：

- `RUNNING`：当前 Context 存在活动执行，优先级最高。
- `BLOCKED`：资源不可用、前置条件无法满足，或当前 Context 最近终态执行失败、取消或超时。
- `DONE`：当前 Context 存在有效成功结果。
- `PENDING`：尚未执行或前置条件尚未满足，但没有失败事实。

后端新增集中式 Workflow 状态聚合器。执行型节点复用领域 latest；`project`、`env`、`assets` 和 `manual` 使用各自事实提供器。`recommendedStageId` 只是导航提示，优先指向活动节点，其次是阻塞节点，再其次是第一个可执行的待办节点，不成为业务状态来源。

旧版 `environments` 计数、领域空摘要、`recentTasks` 和 `recommendedActions` 从 overview 响应中移除。这是有意的后端契约升级。

### 3. 单环境配置版本与项目运行环境版本分工

`environments.config_version` 记录单个环境的有效连接配置版本，初始为 `1`。以下字段的有效值发生变化时递增：角色、架构、主机、SSH 端口、用户名、凭据、跳板机、工作目录和启用状态。名称等展示字段变化不递增。

当前被项目选为 source 或 target 的环境发生有效变化时，还必须递增 `project_runtime_environments.version`。两种版本的职责为：

```text
environment.config_version
  -> 连接测试、基础采集、环境快照是否仍属于当前环境

project_runtime_environments.version
  -> 构建、依赖分析、KB、报告、测试、优化、归档是否仍属于当前项目 Context
```

凭据内容变化或跳板机有效配置变化会影响引用它们的环境，因此必须找到受影响环境并执行相同的版本递增与失效传播。

### 4. 环境结果按配置版本写入，旧任务不得覆盖当前事实

环境连接测试、环境采集及其他会更新环境当前状态的任务，在创建时保存 `environmentConfigVersion`。环境快照同样持久化该版本。

任务完成时先比较任务版本和环境当前版本：

- 版本一致：允许更新当前 `status`、`lastConnectedAt`、`lastCollectedAt` 和当前基础信息。
- 版本不一致：保留任务、日志和历史快照，但不得更新环境当前状态，也不得让 overview 或环境详情把它作为当前基础信息。

有效配置修改后立即将环境状态重置为 `UNKNOWN`，清空当前连接与采集时间。环境详情只投影与当前 `configVersion` 匹配的最新成功快照。

数据库更新使用带版本条件的更新，避免“先编辑、后完成”的旧任务覆盖新配置。

### 5. 环境变化通过 Context 失效和 SSE 通知传播

当选中环境的配置版本变化并引起项目运行环境版本递增时，后端追加 `project.context.changed` 事件。领域数据不做物理删除，latest、readiness 和 overview 依据新 Context 自动返回 `EMPTY`、`PENDING` 或相应阻塞状态。

环境本身的连接测试或采集状态变化继续发送对应任务事件，使 overview 重读后可得到最新 `env` 节点状态。

### 6. overview 快照与 SSE baseline 使用无跳失读取边界

overview 必须避免返回“旧业务快照 + 新事件 ID”，否则前端用该 ID 建立 SSE 后会永久跳过中间变化。实现采用同一只读事务中的一致性快照，或先读取 `latestTaskEventId`、再聚合业务状态的等价策略。

允许得到“新业务快照 + 较旧 event ID”，因为最多导致 SSE 重放和前端再次刷新；不允许得到会跳过事件的反向组合。

## Risks / Trade-offs

- [完整 Workflow 聚合会增加 overview 查询量] -> 由集中聚合器批量查询当前 Context，避免逐节点重复读取任务和领域表，并为仓储查询增加必要索引。
- [凭据或跳板机变化可能影响大量环境] -> 在事务内计算受影响环境并批量递增版本；事件在提交后发布，避免观察到未提交状态。
- [旧客户端依赖旧 overview 字段] -> 本 change 明确为契约升级，前端将在独立改动中迁移；领域独立接口保持不变。
- [活动任务异常遗留会长期遮蔽终态] -> 继续依赖现有任务超时、Worker 恢复和 stale Worker 清理机制将异常活动任务推进终态。
- [单环境版本引入后历史快照查询更复杂] -> 当前查询强制匹配版本，历史审计查询保留显式版本或任务引用，不隐式混用。

## Migration Plan

1. 通过 Liquibase 为环境和环境快照增加配置版本字段，并为现有数据回填 `1`。
2. 为需要保存环境版本的任务输入或执行记录增加字段，重新运行 jOOQ codegen。
3. 先上线兼容新字段的写入和晚到回写保护，再切换环境当前状态读取逻辑。
4. 切换领域 latest 选择规则和集中 Workflow 聚合器。
5. 最后替换 overview DTO；运行单元测试和后端 E2E，覆盖正常、异常和边界流程。
6. 回滚应用时保留新增列；旧应用可忽略新增字段，避免破坏历史数据。

## Open Questions

无。
