## Why

RvPort 已经具备源码导入、分析、迁移输入确认、报告、人工修复、复检、构建验证、自动化测试和测试比较等节点，但缺少一个把多轮优化结果聚合展示的事实层。用户需要查看每一轮源码版本对应的优化成果，而不是只看分散在各节点中的最新记录。

## What Changes

- 新增优化轮次运行时能力，用于按源码版本落库记录多轮优化 cycle。
- 每个 cycle 绑定一个项目和一个源码版本，并保存轮次号、展示状态和关键时间字段。
- 新增优化概览和轮次列表/详情 API，聚合展示当前轮和历史多轮的迁移输入、报告、复检、源码部署、构建、测试和测试比较摘要。
- 源码版本被激活时创建或复用对应优化 cycle；同一 `projectId + sourceRevisionId` 不重复创建。
- 本 change 只做数据聚合和展示，不做自动决策、不触发下游任务、不修改已有节点执行逻辑。

## Capabilities

### New Capabilities

- `optimization-cycle-runtime`: 管理和查询项目优化轮次，按源码版本聚合展示多轮优化结果。

### Modified Capabilities

- `backend-api-design`: 新增优化闭环概览、轮次列表和轮次详情 API 契约。
- `backend-database-design`: 新增 `optimization_cycles` 表及索引约束。

## Impact

- 新增 Liquibase changelog、jOOQ 生成代码和优化轮次领域服务。
- 新增项目级优化 API controller/service/repository/DTO。
- 源码版本激活流程需要调用优化轮次创建或复用逻辑。
- 项目概览可选读取当前 optimization cycle 摘要，但不改变现有节点状态来源。
- 增加单元测试和 E2E 模块，覆盖正常流程、异常流程和 edge case。
