## Why

优化相关的构建、测试和源码复检结果已由后端按源码版本汇总为优化轮次，但工作流还没有入口展示这些数据，用户无法判断当前版本是否具备进入下一轮优化或交付归档的条件。

## What Changes

- 开放“优化闭环”工作流节点，并提供项目当前优化轮次摘要与历史轮次列表。
- 展示现有后端汇总的迁移输入、评估报告、源码复检、部署、构建、测试和测试对比状态。
- 从优化轮次提供到现有构建验证、自动化测试和归档节点的导航入口；不新增优化任务或重跑任务的后端接口。

## Capabilities

### New Capabilities

- `optimization-cycle-stage`: Display and navigate project optimization cycles using the existing optimization overview and cycle APIs.

### Modified Capabilities

- None.

## Impact

- Affected frontend workflow topology, stage routing, project API client, project types, and a new optimization-cycle Drawer.
- Uses existing `/projects/{projectId}/optimization/overview` and `/projects/{projectId}/optimization/cycles` APIs without backend changes.
