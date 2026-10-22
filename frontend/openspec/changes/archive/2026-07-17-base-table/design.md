## Context

环境管理、SBOM 分析和知识库扫描等 Drawer 都包含远程列表，但目前各自组合筛选控件、Ant Design `Table`、分页器和批量操作，且表格剩余高度的处理不一致。项目已有 Ant Design、TanStack Query 和统一 `PageResponse<T>`；环境列表已采用扁平的 `page`、`pageSize`、筛选字段、`sortBy`、`sortOrder` 查询参数。

本设计新增共享 `src/components/BaseTable/`。它不绑定任何领域 API，只接收调用方提供的 `queryKey` 与 `request`，并将列表查询状态作为组件内部服务端状态边界。

## Goals / Non-Goals

**Goals:**

- 用统一三段布局渲染所有远程列表：左筛选/右操作、自动高度表格、左选择操作/右分页。
- 在组件内统一筛选、排序、分页、加载、错误、空态和刷新行为。
- 使用配置化 Ant Design Form 渲染常见筛选项，并允许复杂筛选控件自定义渲染。
- 保留 Ant Design `Table` 的列、行选择、固定列、横向滚动和 `onChange` 能力。
- 使业务 mutation 完成后能够显式刷新当前列表。

**Non-Goals:**

- 不替换 Ant Design `Table`，不引入 TanStack Table、虚拟化或拖拽库。
- 不封装领域 API 路径、字段转换、新建/编辑/详情/导出/确认弹窗或批量业务语义。
- 不在本 change 强制迁移全部既有列表；具体领域 change 按需接入。
- 不支持前端本地排序、前端本地筛选或同时传入本地 `dataSource` 与远程 `request` 两种数据模式。

## Decisions

### 1. `BaseTable` 内部渲染 Ant Design `Table`

`BaseTable` 以 Ant Design `TableProps<TRecord>` 为基础接收列、行键、行选择、行事件、滚动和列固定配置，内部固定 `pagination={false}`，并在独立 Footer 渲染 Ant Design `Pagination`。

选择此方案是为了复用项目唯一 UI 库已有的表格语义、固定列阴影、可访问性和视觉 token，同时消除各业务页面重复的布局代码。直接将 `Table` 作为 children 虽然灵活，但会使组件无法可靠控制自动高度、加载/空态与分页位置。

### 2. 固定三段布局，工具栏使用 `toolbar` 配置

对外 API 使用单个 `toolbar` 字段，内部明确为：

- `toolbar.filters`：左侧动态筛选 Form；可换行并占据剩余宽度。
- `toolbar.actions`：右侧业务操作；按内容宽度展示且不拉伸。
- Table viewport：`flex: 1`、`min-height: 0`，占据工具栏和 Footer 之外的可用高度。
- `selection`：Footer 左侧的已选行批量操作；仅在配置时渲染。
- `pagination`：Footer 右侧；由组件根据查询结果统一渲染。

调用方必须将 `BaseTable` 放在具有确定高度、且自身允许收缩的父级中。组件通过 `ResizeObserver` 观测工具栏和 Footer 高度，计算并传入 Table 的垂直滚动高度；容器空间不足时表格区域滚动，不挤压分页栏。

将 `filters` 和 `actions` 直接作为顶层 props 会泄漏内部布局结构；允许任意 `toolbar: ReactNode` 则无法保证项目要求的左右布局。因此使用 `toolbar` 配置对象。

### 3. `request` 与 `queryKey` 进入组件，领域 API 留在调用方

`BaseTable` 接收基础 `queryKey` 和 `request`：

```ts
type BaseTableQuery<TFilters> = TFilters & {
  page: number
  pageSize: number
  sortBy?: string
  sortOrder?: 'ascend' | 'descend'
}

type BaseTableRequest<TRecord, TFilters> = (
  query: BaseTableQuery<TFilters>
) => Promise<PageResponse<TRecord>>
```

组件将当前 `filters`、分页和排序追加到基础 `queryKey` 后使用 TanStack Query 调用 `request`。筛选改变时组件将页码重置为 1；表头排序和分页改变时使用新 query 重新请求。筛选字段保持扁平，匹配当前领域 API 的 query 参数形态，避免对后端约定施加嵌套对象要求。

调用方通过闭包绑定领域资源标识，例如 `request={(query) => getProjectEnvironments(projectId, query)}`，从而满足共享组件不得直接调用领域 API 的边界。

备选方案是由每个页面自行维护 `useQuery` 并把结果传入组件。该方案无法消除列表请求状态的重复，且会让动态筛选 Form 只能成为视觉封装，故不采用。

### 4. 筛选栏采用受控动态 Form

`toolbar.filters` 提供 `fields`、初始值与可选值变化回调。标准字段类型包括 `search`、`input`、`select`、`date` 和 `dateRange`；字段可提供 Ant Design 控件 props、选项及自定义 `render`。复杂筛选通过 `custom`/`render` 接入，不为单个领域扩展公共字段类型。

筛选状态由 `BaseTable` 管理，并通过 `request` 进入服务端查询；对外回调只用于同步 URL、上层展示或领域侧观察，不替代内部请求状态。筛选控件不预设业务宽度，使用内容和容器宽度自然换行。

### 5. 选择、刷新与错误状态遵循通用边界

行选择沿用 Ant Design `rowSelection` 的受控模型；`selection` 仅承载批量操作内容，不替代选择状态。组件在 Footer 左侧提供选中数量与清空入口，调用方提供具体批量动作。

`BaseTable` 通过 ref 暴露 `reload()`，供领域 mutation 成功后重新请求；同时保留 TanStack Query 的 queryKey，使调用方可按既有项目方式失效缓存。加载时保留表格框架，错误和空数据分别展示可理解状态；错误态提供重试。

## Risks / Trade-offs

- [父容器没有确定高度时无法计算 Table 垂直滚动高度] → 在组件文档和接入检查中明确 `height`/`min-height: 0` 约束；无法计算时安全降级为内容高度。
- [动态筛选字段覆盖不了领域复杂控件] → 保留 `custom`/`render`，不将领域逻辑加入公共组件。
- [内部请求状态可能与页面缓存策略冲突] → 要求调用方提供稳定的基础 `queryKey`，组件只追加自身 query 状态；暴露 `reload()` 并支持标准 query 失效。
- [远程接口暂未实现全部筛选或排序参数] → `BaseTable` 仍按统一协议传参；领域 mock 与正式后端按各自 API change 补齐行为，不在组件中做本地伪过滤。
- [Table 的纵向滚动计算与 Drawer 尺寸动画竞争] → 使用 `ResizeObserver` 及下一帧测量，关闭 Drawer 后释放观察器。

## Migration Plan

1. 新增并测试 `BaseTable`，不替换现有领域列表。
2. 选取环境管理列表作为首个接入方，验证远程筛选、排序、分页、选择和 Drawer 自动高度。
3. 后续在各自领域 change 中迁移 SBOM、知识库扫描等列表，并保留对比验证。
4. 如出现组件行为或视觉问题，可将单个领域列表恢复为直接使用 Ant Design `Table`；该变更不修改后端 API 或持久化数据，无需数据回滚。

## Open Questions

- 无。当前筛选字段与分页协议、布局与请求边界均已确认。
