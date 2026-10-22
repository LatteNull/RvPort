# Project Stage

## Why

项目流水线工作台的阶段抽屉将按节点逐步联调。当前先实现 `project` 节点，也就是“项目创建”阶段。该阶段内容应由后端根据 `projectId + stageId` 返回，前端只负责渲染对应内容。

## What Changes

- 将 StageDrawer 收敛为按 Stage 文件夹分发，当前只保留 `Project` 与兜底 `Default`。
- `project` 阶段使用独立抽屉组件 `Project/index.tsx`。
- `project` 阶段详情通过接口数据渲染项目基本信息、项目状态信息和操作入口。
- 项目基本信息中只有“项目描述”可修改，其它字段只读展示。

## Impact

- 影响项目详情页的 StageDrawer 内容组织。
- 后续其它 Stage 需要分别创建独立 change，再添加对应内容组件。
