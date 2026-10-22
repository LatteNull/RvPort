## ADDED Requirements

### Requirement: BaseTable 提供统一的三段列表布局

前端 SHALL 提供项目级 `BaseTable`，内部使用 Ant Design `Table`，并按“工具栏、表格区域、Footer”的顺序渲染远程列表。工具栏 SHALL 在左侧渲染筛选区域、右侧渲染业务操作区域；Footer SHALL 在左侧渲染可选的选择操作区域、右侧渲染分页器。

#### Scenario: 同时配置筛选、操作、选择与分页

- **WHEN** 调用方为 `BaseTable` 提供筛选字段、工具栏操作、行选择操作和分页数据
- **THEN** 组件 SHALL 按左筛选/右操作、表格、左选择操作/右分页器的顺序展示这些区域

#### Scenario: 未配置可选区域

- **WHEN** 调用方未提供筛选字段、工具栏操作或选择操作中的任一项
- **THEN** 组件 SHALL 不渲染对应区域且不得保留无意义空白

### Requirement: BaseTable 自动分配表格可用高度

`BaseTable` SHALL 在具有确定高度的父容器中，将工具栏和 Footer 之外的剩余空间分配给表格区域，并使表格内容在该区域内滚动。组件 MUST 在无法取得有效可用高度时安全降级为内容高度，且不得遮挡 Footer。

#### Scenario: 父容器高度变化

- **WHEN** Drawer 尺寸、工具栏高度或 Footer 高度发生变化
- **THEN** 组件 SHALL 更新表格区域的可用高度并保持 Footer 可见

#### Scenario: 父容器未提供有效高度

- **WHEN** `BaseTable` 无法计算剩余可用高度
- **THEN** 组件 SHALL 以内容高度渲染表格且不得产生负高度或重叠布局

### Requirement: BaseTable 统一远程列表查询状态

`BaseTable` SHALL 接收调用方提供的基础 `queryKey` 与 `request` 函数，并使用 TanStack Query 管理远程 `PageResponse<T>` 的加载、缓存、失败和重试。组件 MUST 将当前页码、页大小、筛选字段以及可选的 `sortBy`、`sortOrder` 传入 `request`，但不得直接调用任何领域 API。

#### Scenario: 初始加载远程列表

- **WHEN** 组件以有效 `queryKey` 和 `request` 挂载
- **THEN** 组件 SHALL 使用初始查询状态调用 `request` 并渲染返回的分页数据

#### Scenario: 领域页面绑定资源标识

- **WHEN** 调用方通过 `request` 闭包绑定项目 ID 或其他领域资源标识
- **THEN** 组件 SHALL 仅调用该函数并使用调用方提供的 `queryKey`，不得感知或构造领域 API 路径

### Requirement: BaseTable 渲染受控动态筛选 Form

`BaseTable` SHALL 基于配置字段在工具栏左侧渲染动态筛选 Form，至少支持 `search`、`input`、`select`、`date`、`dateRange` 和自定义渲染字段。筛选控件 SHALL 随可用宽度换行，且不得对业务字段强制固定宽度。

#### Scenario: 使用标准筛选字段

- **WHEN** 调用方配置搜索输入和选择字段
- **THEN** 组件 SHALL 渲染相应 Ant Design 控件，并将用户输入更新为当前查询筛选字段

#### Scenario: 使用复杂自定义筛选字段

- **WHEN** 调用方为字段提供自定义渲染函数
- **THEN** 组件 SHALL 在筛选区域渲染该控件且保留统一的工具栏布局

### Requirement: 筛选、排序和分页触发一致的远程刷新

`BaseTable` MUST 在筛选字段变化时将页码重置为第一页并重新请求；在用户改变表头排序或分页器时，组件 SHALL 使用更新后的查询参数重新请求数据。组件不得为未由服务端确认的参数执行本地筛选或本地排序来伪造结果。

#### Scenario: 修改筛选条件

- **WHEN** 用户修改任一筛选字段
- **THEN** 组件 SHALL 将页码重置为 1，并以更新后的筛选字段调用 `request`

#### Scenario: 修改排序

- **WHEN** 用户对可排序列切换排序方向
- **THEN** 组件 SHALL 将对应字段和 `ascend` 或 `descend` 排序方向传入 `request`

#### Scenario: 切换分页

- **WHEN** 用户切换页码或页大小
- **THEN** 组件 SHALL 以新页码或页大小调用 `request` 并在 Footer 右侧更新分页器

### Requirement: BaseTable 支持选择操作与显式刷新

`BaseTable` SHALL 复用 Ant Design 受控 `rowSelection` 模型。启用选择操作时，组件 MUST 在 Footer 左侧展示选中数量、清空选择入口和调用方提供的 `selection` 内容。组件 SHALL 暴露显式刷新能力，供领域 mutation 成功后重新加载当前查询。

#### Scenario: 选择多行并执行批量操作

- **WHEN** 调用方启用行选择且用户选择一条或多条记录
- **THEN** Footer 左侧 SHALL 展示当前选中数量与调用方提供的批量操作内容

#### Scenario: 清空选择

- **WHEN** 用户触发清空选择
- **THEN** 组件 SHALL 调用受控选择状态更新回调并清空当前选择

#### Scenario: 领域 mutation 后刷新

- **WHEN** 调用方在领域 mutation 成功后调用 `BaseTable` 的刷新能力
- **THEN** 组件 SHALL 使用当前筛选、排序和分页状态重新调用 `request`

### Requirement: BaseTable 提供完整的数据状态反馈

`BaseTable` SHALL 区分加载、请求失败、初始空数据和筛选无结果状态。请求失败时 MUST 提供重试入口；加载、空态和失败反馈均 SHALL 保持在表格区域内，不得破坏工具栏和 Footer 布局。

#### Scenario: 请求失败

- **WHEN** `request` 返回失败
- **THEN** 组件 SHALL 在表格区域展示可理解的失败反馈和重试操作

#### Scenario: 没有任何记录

- **WHEN** 初始查询返回空分页结果且未设置筛选条件
- **THEN** 组件 SHALL 展示初始空数据状态

#### Scenario: 筛选后无匹配记录

- **WHEN** 存在筛选条件且查询返回空分页结果
- **THEN** 组件 SHALL 展示区别于初始空数据的筛选无结果状态
