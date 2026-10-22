## MODIFIED Requirements

### Requirement: 项目流水线工作台内容

项目流水线工作台页面 SHALL 汇总当前迁移项目状态并渲染迁移流程，但 MUST NOT 在页面渲染时自动执行流水线任务。

#### Scenario: 项目流水线工作台渲染摘要

- **WHEN** 项目概览数据加载成功
- **THEN** 页面 SHALL 展示项目标识、架构迁移方向、总体风险、问题数量、当前阶段和构建状态摘要卡片

#### Scenario: 项目流水线工作台渲染流程画布

- **WHEN** 项目概览数据加载成功
- **THEN** 页面 SHALL 渲染 React Flow 流水线画布，包含前端固定维护的迁移阶段节点、分组框和连接边
- **AND** SHALL 将 `env` 和 `assets` 放入“源数据管理”分组，将 `kb` 放入“源码分析”分组
- **AND** SHALL 将 `assets` 展示为“源码管理”
- **AND** SHALL 展示 `x86-build` 和 `rv-dependency-analysis` 构建可用性节点
- **AND** SHALL 将 `build` 展示为可点击的“构建验证”节点
- **AND** SHALL NOT 在画布中展示“环境扫描”分组、“环境与依赖对比”节点或“迁移输入合并”节点

#### Scenario: 展示源数据与扫描依赖边

- **WHEN** 页面渲染当前主流程
- **THEN** 画布 SHALL 使用具体节点 edge 表示 `project -> env`、`project -> assets`、`assets -> kb`、`kb -> report`、`report -> manual` 和 `manual -> assets`
- **AND** SHALL 使用具体节点 edge 表示 `env -> x86-build`、`assets -> x86-build`、`x86-build -> rv-dependency-analysis`、`rv-dependency-analysis -> report`、`report -> build` 与 `build -> test`
- **AND** SHALL 保留 `test -> optimize`、`optimize -> assets` 和 `optimize -> archive` 的现有后段关系
- **AND** SHALL NOT 将业务 edge 连接到分组边界

#### Scenario: Workflow 状态映射到固定拓扑

- **WHEN** Workflow 状态快照加载成功
- **THEN** 页面 SHALL 将后端返回的阶段状态、当前阶段摘要、运行中边和可选焦点映射到前端固定维护的节点、分组和边上
- **AND** 页面 SHALL NOT 要求后端返回 React Flow 节点、分组、边或布局坐标

#### Scenario: 环境与依赖对比阶段状态

- **WHEN** workflow 状态快照包含 `sbom` 任务状态
- **THEN** 页面 SHALL NOT 将其映射到当前固定画布中的节点
- **AND** 既有 SBOM Drawer、接口和历史数据 SHALL 保持可用，以便后续恢复入口

#### Scenario: 构建验证阶段状态

- **WHEN** workflow 状态快照包含 `build` 任务状态
- **THEN** 页面 SHALL 将其映射到前端固定的“构建验证”节点
- **AND** 用户 SHALL 始终能够打开该节点以查看前置条件、构建记录或恢复入口

#### Scenario: 用户操作流水线画布

- **WHEN** 用户平移或缩放流水线画布
- **THEN** 画布 SHALL 支持 React Flow 的平移和缩放行为，且不改变服务端拥有的项目状态

#### Scenario: 扫描任务不自动启动

- **WHEN** 用户完成环境配置或更新当前源码
- **THEN** 页面 SHALL NOT 自动启动知识库扫描、评估报告、x86 构建、依赖分析或构建验证
- **AND** 当前 change 中新增的构建可用性节点 SHALL 仅展示静态演示数据

#### Scenario: 聚焦扫描分组

- **WHEN** workflow 状态快照指定 `focusGroupId=source-scan`
- **THEN** 画布 SHALL 在初始化或状态切换时将对应分组置于视觉中心
- **AND** 页面 SHALL NOT 为并行支路任意选择单一节点作为唯一当前阶段

#### Scenario: 流水线节点不可拖拽编排

- **WHEN** 用户查看项目流水线工作台
- **THEN** 页面 SHALL 禁止拖拽节点改变 workflow 布局或流程结构

#### Scenario: 用户悬浮流水线节点

- **WHEN** 用户将鼠标悬浮在流水线节点上
- **THEN** 页面 SHALL 通过样式联动展示该节点直接相连的 source/target edges
- **AND** 页面 SHALL NOT 通过每次悬浮修改 React Flow edges 数组来实现该效果

#### Scenario: 初始化聚焦当前阶段

- **WHEN** Workflow 状态快照包含当前阶段且不包含分组焦点
- **THEN** 画布 SHALL 在初始化或状态切换时将当前阶段置于视觉中心
- **AND** 画布 SHALL NOT 以展示完整 workflow 为初始化目标

#### Scenario: 项目流水线工作台不建立实时连接

- **WHEN** 本 change 中的项目流水线工作台页面渲染
- **THEN** 页面 SHALL NOT 建立项目级 SSE 连接

#### Scenario: 项目流水线工作台不自动执行任务

- **WHEN** 用户查看项目流水线工作台页面且未确认阶段操作
- **THEN** 页面 SHALL NOT 启动扫描、报告、构建、测试、归档或其他长任务

#### Scenario: 已确认的阶段操作启动任务

- **WHEN** 用户在既有阶段 Drawer 中确认启动知识库扫描或构建验证
- **THEN** 页面 SHALL 通过该阶段既有 API 请求服务端启动任务
- **AND** 页面 SHALL 仅根据服务端返回的 workflow 状态更新画布
