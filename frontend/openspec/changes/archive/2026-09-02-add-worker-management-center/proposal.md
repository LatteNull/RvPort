## Why

后端已提供 Worker 自动注册、心跳、运行任务观测和单实例并发控制接口，但前端管理中心没有对应入口。超级管理员无法从界面判断 Worker 是否在线、当前任务负载或调整消费并发，只能直接调用 API。

## What Changes

- 在管理中心增加独立的“Worker 管理”导航和懒加载路由。
- 增加 Worker 列表，支持按实例、主机、状态和是否有运行任务筛选，并展示在线状态、期望/实际并发、任务数量及最近心跳。
- 增加 Worker 详情 Drawer，完整展示实例信息和当前运行任务。
- 增加单 Worker 并发设置；`concurrencyLimit=0` 明确表示暂停接收新任务，不取消正在运行的任务。
- 页面只提供显式刷新，不新增后台轮询。

## Capabilities

### Modified Capabilities

- `admin-center`: 增加 Worker 可观测和并发控制界面。

## Impact

- Frontend：管理中心导航、路由、管理员 API 模块、Worker 页面及测试。
- Backend：不修改，直接使用现有 `/api/admin/workers` 接口。
