## ADDED Requirements

### Requirement: 项目流水线工作台路由

前端 SHALL 提供受认证保护的项目流水线工作台路由，并将其作为项目工作台默认入口。

#### Scenario: 已登录用户打开项目流水线工作台

- **WHEN** 已登录用户打开 `/projects/:projectId`
- **THEN** 应用 SHALL 在受保护的主布局中渲染项目流水线工作台页面

#### Scenario: 未登录用户打开项目流水线工作台

- **WHEN** 不存在有效登录会话且用户打开 `/projects/:projectId`
- **THEN** 现有受保护路由守卫 SHALL 将用户导向 `/login`

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
- **THEN** mock API SHALL 使用当前前端响应包络返回当前阶段、阶段状态和运行中边 ID

### Requirement: 项目流水线工作台内容

项目流水线工作台页面 SHALL 汇总当前迁移项目状态并渲染迁移流程，但 MUST NOT 执行流水线任务。

#### Scenario: 项目流水线工作台渲染摘要

- **WHEN** 项目概览数据加载成功
- **THEN** 页面 SHALL 展示项目标识、架构迁移方向、总体风险、问题数量、当前阶段和构建状态摘要卡片

#### Scenario: 项目流水线工作台渲染流程画布

- **WHEN** 项目概览数据加载成功
- **THEN** 页面 SHALL 渲染 React Flow 流水线画布，包含前端固定维护的迁移阶段节点、分组框和连接边

#### Scenario: Workflow 状态映射到固定拓扑

- **WHEN** Workflow 状态快照加载成功
- **THEN** 页面 SHALL 将后端返回的阶段状态、当前阶段和运行中边 ID 映射到前端固定维护的节点和边上
- **AND** 页面 SHALL NOT 要求后端返回 React Flow 节点、分组、边或布局坐标

#### Scenario: 用户操作流水线画布

- **WHEN** 用户平移或缩放流水线画布
- **THEN** 画布 SHALL 支持 React Flow 的平移和缩放行为，且不改变服务端拥有的项目状态

#### Scenario: 流水线节点不可拖拽编排

- **WHEN** 用户查看项目流水线工作台
- **THEN** 页面 SHALL 禁止拖拽节点改变 workflow 布局或流程结构

#### Scenario: 初始化聚焦当前阶段

- **WHEN** Workflow 状态快照包含当前阶段
- **THEN** 画布 SHALL 在初始化或状态切换时将当前阶段置于视觉中心
- **AND** 画布 SHALL NOT 以展示完整 workflow 为初始化目标

#### Scenario: 用户悬浮流水线节点

- **WHEN** 用户将鼠标悬浮在流水线节点上
- **THEN** 页面 SHALL 通过样式联动展示该节点直接相连的 source/target edges
- **AND** 页面 SHALL NOT 通过每次悬浮修改 React Flow edges 数组来实现该效果

#### Scenario: 项目流水线工作台不建立实时连接

- **WHEN** 本 change 中的项目流水线工作台页面渲染
- **THEN** 页面 SHALL NOT 建立项目级 SSE 连接

#### Scenario: 项目流水线工作台不执行任务

- **WHEN** 用户查看项目流水线工作台页面
- **THEN** 页面 SHALL NOT 启动扫描、SBOM、报告、构建、测试、归档或其他长任务
