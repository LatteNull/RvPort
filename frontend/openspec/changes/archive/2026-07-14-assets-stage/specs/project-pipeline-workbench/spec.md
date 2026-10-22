## MODIFIED Requirements

### Requirement: 项目流水线工作台数据加载

项目流水线工作台页面 SHALL 通过项目 API 边界并使用 TanStack Query 加载项目概览数据。

#### Scenario: 项目流水线工作台发起请求

- **WHEN** `/projects/:projectId` 带有项目 ID 并开始渲染
- **THEN** 页面 SHALL 通过 TanStack Query 调用该项目 ID 对应的项目概览 API 边界

#### Scenario: 项目流水线工作台加载中

- **WHEN** 概览查询处于加载中
- **THEN** 页面 SHALL 在工作台内容区域展示局部加载状态

#### Scenario: 项目流水线工作台请求失败

- **WHEN** 概览查询失败
- **THEN** 页面 SHALL 展示错误状态和重试操作

#### Scenario: 开发 mock 提供项目流水线工作台数据

- **WHEN** Vite dev server 以 serve 模式运行，且 mock 项目请求 `/api/projects/:projectId/overview`
- **THEN** mock API SHALL 使用当前前端响应包络返回不包含 workflow 拓扑的项目概览数据

#### Scenario: 开发 mock 提供 Workflow 状态快照

- **WHEN** Vite dev server 以 serve 模式运行，且 mock 项目请求 `/api/projects/:projectId/workflow/status`
- **THEN** mock API SHALL 使用当前前端响应包络返回当前阶段摘要、阶段状态、运行中边和可选的 workflow 焦点信息

### Requirement: 项目流水线工作台内容

项目流水线工作台页面 SHALL 汇总当前迁移项目状态并渲染迁移流程，但 MUST NOT 在页面渲染时自动执行流水线任务。

#### Scenario: 项目流水线工作台渲染摘要

- **WHEN** 项目概览数据加载成功
- **THEN** 页面 SHALL 展示项目标识、架构迁移方向、总体风险、问题数量、当前阶段和构建状态摘要卡片

#### Scenario: 项目流水线工作台渲染流程画布

- **WHEN** 项目概览数据加载成功
- **THEN** 页面 SHALL 渲染 React Flow 流水线画布，包含前端固定维护的迁移阶段节点、分组框和连接边

#### Scenario: Workflow 状态映射到固定拓扑

- **WHEN** Workflow 状态快照加载成功
- **THEN** 页面 SHALL 将后端返回的阶段状态、当前阶段摘要、运行中边和可选焦点映射到前端固定维护的节点、分组和边上
- **AND** 页面 SHALL NOT 要求后端返回 React Flow 节点、分组、边或布局坐标

#### Scenario: 展示并行源码分析支路

- **WHEN** `assets` 阶段已启动源码分析且状态快照包含六个运行中的分析节点
- **THEN** 页面 SHALL 同时展示 `sbom`、`kb`、`ai-scan`、`memory`、`fp` 和 `alignment` 的运行状态及对应活动边
- **AND** 当前阶段摘要 SHALL 展示“源码分析 · 6 项进行中”或服务端返回的等价聚合文案

#### Scenario: 聚焦源码扫描分组

- **WHEN** workflow 状态快照指定 `focusGroupId=scan`
- **THEN** 画布 SHALL 在初始化或状态切换时将源码扫描分组置于视觉中心
- **AND** 页面 SHALL NOT 为并行支路任意选择单一节点作为唯一当前阶段

#### Scenario: 用户操作流水线画布

- **WHEN** 用户平移或缩放流水线画布
- **THEN** 画布 SHALL 支持 React Flow 的平移和缩放行为，且不改变服务端拥有的项目状态

#### Scenario: 流水线节点不可拖拽编排

- **WHEN** 用户查看项目流水线工作台
- **THEN** 页面 SHALL 禁止拖拽节点改变 workflow 布局或流程结构

#### Scenario: 初始化聚焦当前阶段

- **WHEN** Workflow 状态快照包含当前阶段且不包含分组焦点
- **THEN** 画布 SHALL 在初始化或状态切换时将当前阶段置于视觉中心
- **AND** 画布 SHALL NOT 以展示完整 workflow 为初始化目标

#### Scenario: 用户悬浮流水线节点

- **WHEN** 用户将鼠标悬浮在流水线节点上
- **THEN** 页面 SHALL 通过样式联动展示该节点直接相连的 source/target edges
- **AND** 页面 SHALL NOT 通过每次悬浮修改 React Flow edges 数组来实现该效果

#### Scenario: 项目流水线工作台不建立实时连接

- **WHEN** 本 change 中的项目流水线工作台页面渲染
- **THEN** 页面 SHALL NOT 建立项目级 SSE 连接

#### Scenario: 页面渲染不自动执行任务

- **WHEN** 用户查看项目流水线工作台页面且未确认阶段操作
- **THEN** 页面 SHALL NOT 自动启动扫描、SBOM、报告、构建、测试、归档或其他长任务

#### Scenario: 已确认的阶段操作启动任务

- **WHEN** 用户在阶段 Drawer 中确认启动源码分析
- **THEN** 页面 SHALL 通过阶段 API 请求服务端启动任务
- **AND** 页面 SHALL 仅根据服务端返回的 workflow 状态更新画布
