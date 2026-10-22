## Why

当前领域 latest、项目 overview 和环境配置失效语义没有形成一致闭环：部分 latest 查询会被旧终态记录遮蔽运行中任务，overview 仍返回旧版聚合结构且缺少全部 Workflow 节点状态，环境连接配置修改后旧测试时间和采集快照仍可能被当作当前事实。需要统一当前 Context 下的执行优先级、项目全局快照以及环境配置版本生命周期，避免前端展示过期或相互矛盾的状态。

## What Changes

- 统一所有异步领域 latest 的选择规则：当前 Context 存在 `PENDING`、`QUEUED` 或 `RUNNING` 执行时优先返回活动执行；不存在活动执行时才返回最新终态，且不得回退到更早成功记录。
- **BREAKING**：将项目 overview 调整为 Feature-v0.0.2 目标结构，仅返回稳定项目元数据、当前源码与运行环境 Context、完整 Workflow 节点状态以及 `latestTaskEventId`，移除旧版统计占位、最近任务和推荐动作字段。
- overview 返回 `project`、`env`、`assets`、`kb`、`x86-build`、`rv-dependency-analysis`、`report`、`manual`、`build`、`test`、`optimize`、`archive` 全部节点的 `PENDING/RUNNING/DONE/BLOCKED` 状态和稳定 `reasonCode`。
- 为单个环境增加连接配置版本；连接、身份、跳板机、工作目录、角色或架构等有效配置变化时递增版本，并使当前连接测试和采集结果失效。
- 当前 source/target 环境的有效配置发生变化时，同时递增项目运行环境配置版本，使依赖该 Context 的部署、构建、分析、测试、报告、优化与归档结果变为历史事实。
- 环境任务保存创建时的环境配置版本；旧版本任务晚到完成时保留历史结果，但不得覆盖新版本环境的当前状态或基础信息。
- 环境名称等不影响执行的展示字段变化不触发配置版本递增或测试失效；凭据和跳板机的有效配置变化需要传播到引用它们的环境。
- 补充项目 SSE 上下文变化通知，并保证 overview 业务快照和 `latestTaskEventId` 不会形成跳过事件的不一致边界。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `backend-api-design`：修改领域 latest 的活动执行优先语义和项目 overview 的响应结构、完整节点状态及一致性约束。
- `project-source-environment`：修改环境编辑后的当前测试状态、连接时间和基础采集信息失效行为。
- `project-runtime-environment-selection`：增加单环境配置版本，并规定当前环境有效配置变化对项目运行环境版本及下游事实的影响。
- `task-runtime`：环境任务绑定配置版本，旧版本任务完成不得写回当前状态，并补充相关项目上下文事件要求。
- `backend-database-design`：增加环境配置版本及环境测试、采集快照与配置版本的持久化约束。

## Impact

- 影响项目 overview DTO、聚合服务、Workflow 节点状态推导以及相关 controller 测试和 E2E 契约。
- 影响 KB 扫描、构建、依赖分析、评估报告、自动化测试、优化和归档等领域 latest 查询及排序规则。
- 影响环境、环境快照、环境任务输入和项目运行环境配置表，需要新增 Liquibase 迁移并重新生成 jOOQ 代码。
- 影响环境编辑、凭据更新、跳板机更新、连接测试和环境采集完成回写链路。
- 前端后续需要按新的 overview 结构读取 `currentContext` 和 `workflow.stages[]`；本 change 只处理后端。
