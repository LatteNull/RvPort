# BaseTable

[English](README.md) | 简体中文

`BaseTable` 是 RvPort 的项目级远程数据表组件。它内部使用 Ant Design `Table`，并统一渲染三段布局：左侧动态筛选、右侧业务操作、自动高度表格，以及左侧选择操作和右侧分页器。

## 使用边界

- 调用方提供稳定 `queryKey` 和领域 `request` 函数；`BaseTable` 不得直接依赖领域 API。
- `request` 接收扁平的 `page`、`pageSize`、筛选字段、`sortBy` 与 `sortOrder`，并返回 `PageResponse<T>`。
- 列定义、行级操作、领域 mutation、详情、导出和确认交互由调用方负责。
- `BaseTable` 负责筛选、远程请求状态、排序、分页、加载、空态、失败重试与 `reload()`。
- 无数据时默认使用独立空状态，保留工具栏并隐藏表头、分页和滚动区域；筛选无结果可清空筛选，请求失败可重新加载。只有需要用表头解释数据结构时才传入 `emptyPresentation="table"`。
- `size` 是表格与分页器共用的密度入口，默认 `small`。分页器只支持 Ant Design 的紧凑与默认两档，因此 `middle` 和 `large` 会使用其默认密度。

```tsx
const tableRef = useRef<BaseTableHandle>(null)

<BaseTable<ProjectEnvironment, EnvironmentFilters, 'name' | 'host'>
  ref={tableRef}
  columns={columns}
  queryKey={['project-environments', projectId]}
  request={(query) => getProjectEnvironments(projectId, query)}
  rowKey="id"
  toolbar={{
    filters: { fields: environmentFilterFields },
    actions: <Button type="primary">新建环境</Button>
  }}
/>

await saveEnvironment(values)
await tableRef.current?.reload()
```

## 高度约束

组件根节点使用 `height: 100%`、`min-height: 0`。父级必须提供可计算高度，并允许子节点收缩；例如 Drawer 内容区中的列表容器应使用 `display: flex`、`flex-direction: column`、`height: 100%` 与 `min-height: 0`。组件会观测工具栏、Footer、布局间距和表格非滚动区尺寸，将剩余高度传给 Table body 的垂直滚动区域；无法计算时会安全降级为内容高度。

## 筛选字段

`toolbar.filters.fields` 支持 `search`、`input`、`select` 和 `custom`。标准字段由组件渲染；复杂控件使用 `custom` 与 `render`。筛选变化会自动回到第一页并重新请求，组件不会执行本地筛选或本地排序。

## 选择与分页

行选择沿用 Ant Design 受控 `rowSelection`。传入 `selection` 后，Footer 左侧显示选择状态、清空入口和业务批量操作；分页器由 `BaseTable` 始终渲染在 Footer 右侧，并默认显示“共 N 条”。调用方可通过 `pagination.showTotal` 覆盖文案，传入 `pagination={false}` 可隐藏分页栏。

## 列表与详情往返

`TableViewStateProvider` 提供局部状态保留范围：同一范围内表格卸载后再次挂载，会按稳定 `queryKey` 恢复筛选、页码、每页条数和排序。搜索输入草稿与已应用筛选独立保存：失焦不提交，进入详情取消防抖计时，返回后恢复输入并继续正常防抖；Enter 和清空仍立即提交。不同数据集的 `queryKey` 必须包含项目或记录标识；切换数据集时不会沿用上一列表的查询条件或草稿。表格行数据仍重新请求，不缓存选中行或隐藏的组件树。

项目阶段的 `StageSurface` 已统一提供此范围，Workflow Drawer 与 Step 均生效。关闭阶段时清空；跨阶段、跨项目和视图切换不保证保留。没有 Provider 的表格沿用独立局部状态，不进行全局持久化。

“清空筛选”会同时清理已应用查询和待生效搜索草稿、取消防抖。搜索重置版本随该列表控件状态保留，不作为请求参数发送；清空之后新输入的草稿仍支持详情往返恢复。

## 空状态

整表无数据时，组件默认使用独立状态面板。`emptyDescription` 设置标题，`emptyAction` 可以补充新建等业务操作；存在筛选条件时组件显示“清空筛选”，请求失败时显示“重新加载”。需要保留空表头的特殊场景可以显式传入 `emptyPresentation="table"`。
