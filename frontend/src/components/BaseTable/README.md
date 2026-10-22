# BaseTable

English | [简体中文](README.zh-CN.md)

`BaseTable` is RvPort's shared remote-data table component. It wraps Ant Design `Table` and provides a consistent layout: dynamic filters on the left and business actions on the right, an automatically sized table, then selection actions on the left and pagination on the right.

## Responsibility boundaries

- Callers provide a stable `queryKey` and domain-specific `request` function. `BaseTable` must not depend directly on domain APIs.
- `request` receives flat `page`, `pageSize`, filter, `sortBy`, and `sortOrder` fields and returns `PageResponse<T>`.
- Callers own columns, row actions, domain mutations, detail views, exports, and confirmation interactions.
- `BaseTable` owns filters, remote-request state, sorting, pagination, loading, empty states, retries, and `reload()`.
- With no data, the default standalone empty state retains the toolbar and hides headers, pagination, and the scrolling area. No filter matches allow filters to be cleared; failed requests can reload. Use `emptyPresentation="table"` only when headers are needed to explain the structure.
- `size` controls density for both table and pagination and defaults to `small`. Ant Design pagination has compact and default density only, so `middle` and `large` use its default density.

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
    actions: <Button type="primary">New environment</Button>
  }}
/>

await saveEnvironment(values)
await tableRef.current?.reload()
```

## Height constraints

The root uses `height: 100%` and `min-height: 0`. Its parent must provide a measurable height and permit shrinking. For example, a Drawer list container should use `display: flex`, `flex-direction: column`, `height: 100%`, and `min-height: 0`. The component observes toolbar, Footer, layout gaps, and non-scrolling table dimensions, then passes remaining height to the Table body's vertical scrolling area. It safely falls back to content height when calculation is unavailable.

## Filter fields

`toolbar.filters.fields` supports `search`, `input`, `select`, and `custom`. Standard fields are rendered internally; complex controls use `custom` with `render`. Filter changes reset to page one and refetch. The component does not perform local filtering or sorting.

## Selection and pagination

Row selection uses Ant Design's controlled `rowSelection`. Supplying `selection` adds selection status, a clear action, and business bulk actions on the Footer's left. BaseTable owns pagination on the right, with a default total-count label. Override its text through `pagination.showTotal`, or hide pagination with `pagination={false}`.

## Navigating between lists and details

`TableViewStateProvider` defines a local persistence scope. A table remounted within that scope restores filters, page, page size, and sorting by stable `queryKey`. Search drafts are stored separately from applied filters: blur does not submit; entering details cancels debounce; returning restores input and resumes ordinary debounce. Enter and clear submit immediately. Keys for different datasets must include a project or record identifier. Switching datasets does not reuse previous queries or drafts. Row data is refetched; selected rows and hidden component trees are not cached.

Project stages share this scope through `StageSurface`, for both Workflow Drawer and Step. Closing the stage clears it; retention is not guaranteed across stages, projects, or view switches. Without a Provider, tables keep independent local state with no global persistence.

Clearing filters resets applied queries and pending search drafts and cancels debounce. The search-reset version is retained with list-control state but is not sent as a request parameter. New drafts entered after clearing still support list/detail restoration.

## Empty states

When the whole table is empty, the default is a standalone state panel. `emptyDescription` supplies its title; `emptyAction` can add business actions such as creation. Active filters show a clear-filter action; failed requests show reload. Explicitly use `emptyPresentation="table"` when empty headers must remain visible.
