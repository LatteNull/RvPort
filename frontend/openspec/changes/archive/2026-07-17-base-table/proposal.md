## Why

当前各领域列表重复实现筛选栏、表格可用高度、分页、远程查询和批量操作区域，导致布局和交互逐步分叉。项目已统一采用 Ant Design 与 TanStack Query，适合建立一套不耦合领域 API 的 `BaseTable`，作为所有远程列表的稳定基础。

## What Changes

- 新增项目级 `BaseTable`，内部渲染 Ant Design `Table`，统一“左侧动态筛选、右侧操作、自动高度表格、左侧批量操作与右侧分页”的三段布局。
- 统一列表查询协议：组件管理筛选、排序、页码和页大小，并通过调用方传入的 `request` 与 `queryKey` 使用 TanStack Query 获取远程分页数据。
- 提供配置化动态筛选 Form，覆盖标准输入、搜索、选择和日期类字段，并保留自定义字段渲染入口。
- 保持领域页面负责 API 选择、列定义、领域 mutation、详情和确认流程；`BaseTable` 不直接调用领域 API，也不承载领域业务操作。
- 不引入新的表格、虚拟化或拖拽运行时依赖，继续使用现有 Ant Design `Table` 与 TanStack Query。

## Capabilities

### New Capabilities

- `base-table`: 项目级远程数据表的布局、筛选、查询、分页、选择操作与状态反馈能力。

### Modified Capabilities

- 无。

## Impact

- 新增 `src/components/BaseTable/` 及其类型、样式、测试和使用说明。
- 后续环境管理、SBOM 分析、知识库扫描等列表可迁移到 `BaseTable`；本 change 不要求同时迁移所有领域页面。
- 复用现有 `antd`、`@tanstack/react-query` 和项目分页响应类型；不改变后端 API 或新增依赖。
