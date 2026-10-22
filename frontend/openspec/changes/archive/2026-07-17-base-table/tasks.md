## 1. 组件基础与查询模型

- [x] 1.1 新建 `src/components/BaseTable/` 模块、公开导出和共享类型，定义远程 `request`、基础 `queryKey`、分页、排序、工具栏、筛选字段和选择操作的泛型 API。
- [x] 1.2 实现内部查询状态 hook，使用 TanStack Query 组合稳定 query key，并处理筛选、排序、页码、页大小和 `reload()`。
- [x] 1.3 为查询状态与请求参数转换编写单元测试，覆盖初始请求、筛选重置页码、排序、分页和刷新。

## 2. 三段布局与动态筛选

- [x] 2.1 实现 `BaseTable` 组合入口及工具栏区域，固定左侧动态筛选 Form、右侧操作区的布局与响应式换行。
- [x] 2.2 实现标准筛选字段渲染，覆盖 `search`、`input`、`select`、`date`、`dateRange` 与自定义渲染字段。
- [x] 2.3 实现自动高度 Table viewport 和独立 Footer，使用尺寸观测计算可用高度，并在无法计算时安全降级。
- [x] 2.4 在 Footer 实现受控选择数量、清空入口、批量操作区和固定右侧分页器。

## 3. 表格反馈与质量保障

- [x] 3.1 将 Ant Design `Table` 属性、行选择、固定列、横向滚动和表头排序接入 `BaseTable`，内部禁止 Table 自带分页器。
- [x] 3.2 实现加载、错误重试、初始空数据和筛选无结果状态，并保持工具栏和 Footer 布局稳定。
- [x] 3.3 编写组件交互测试，覆盖三段布局、动态筛选、自定义筛选、选择操作、分页、错误重试与空态区分。
- [x] 3.4 编写 `BaseTable` 使用说明，声明父级高度约束、远程请求协议、刷新方式和领域职责边界。

## 4. 首个领域接入与验证

- [x] 4.1 将环境管理列表迁移为 `BaseTable` 调用方，保留现有领域 API、操作按钮、确认流程及远程筛选/排序语义。
- [x] 4.2 为环境管理接入更新测试，验证查询参数、分页、排序、工具栏操作与行级操作不回归。
- [x] 4.3 运行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck`、相关 `pnpm test` 和 `openspec validate base-table`，记录验证结果。

## 验证结果

- `pnpm exec prettier --check src/components/BaseTable src/pages/project-detail/StageDrawer/Environment/List.tsx src/pages/project-detail/StageDrawer/Environment/List.test.tsx src/pages/project-detail/StageDrawer/Environment/index.module.scss openspec/changes/base-table`：通过。
- `pnpm exec eslint src/components/BaseTable src/pages/project-detail/StageDrawer/Environment/List.tsx src/pages/project-detail/StageDrawer/Environment/List.test.tsx`：通过。
- `pnpm typecheck`：通过。
- `pnpm test`：通过。
- `openspec validate base-table`：通过。
- 全局 `pnpm format:check` 仍报告工作区已有的 `mock/project.ts` 格式问题；全局 `pnpm lint` 仍报告该文件未使用符号及 `src/App.tsx` 的 import 排序问题，均不属于本次变更范围。
