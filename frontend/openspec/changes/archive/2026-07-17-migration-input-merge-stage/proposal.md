## Why

多个上游扫描与分析阶段会产生重叠或冲突的迁移问题，当前缺少一个可审阅、可处理冲突并形成统一评估依据的阶段。需要在生成评估报告前，将这些输入合并为明确且已确认的问题清单。

## What Changes

- 新增迁移输入合并阶段 Drawer，展示合并后的问题摘要和服务端分页的迁移输入列表。
- 支持选择可用上游输入来源并重新合并结果；来源选择影响合并结果，而不是仅过滤表格展示。
- 支持对来源间冲突的问题进入 Drawer 内部视图处理，并禁止带有待处理冲突的问题被确认或用于生成评估报告。
- 支持在表格选择工具栏确认无冲突的已选问题，并以已确认问题清单作为评估报告阶段的唯一输入基线。
- 调整该阶段 Footer，仅保留生成评估报告这一全局推进操作；该操作仅在存在已确认问题且没有待处理冲突时可用。
- 增加迁移输入合并的领域类型、API 边界、Vite mock、测试以及 `merge` Workflow 节点的 Drawer 映射。

## Capabilities

### New Capabilities

- `migration-input-merge`: 上游迁移问题输入的来源选择、合并、冲突处理、问题确认和评估输入基线管理。

### Modified Capabilities

- `project-pipeline-workbench`: 工作台支持从 `merge` 节点打开迁移输入合并 Drawer，并根据合并、确认和报告生成操作刷新阶段状态。

## Impact

- 受影响页面：`src/pages/project-detail/StageDrawer/`、`StageDrawer/index.tsx` 与 Workflow 节点交互。
- 受影响领域边界：`src/types/project.ts`、`src/api/project.ts`、`mock/project.ts` 及相关 API/Drawer 测试。
- 复用 BaseDrawer、BaseTable、TanStack Query、Ant Design Form/Select/Popconfirm；不新增运行时依赖，不引入 SSE 或轮询。
- `assessment-report-stage` 将消费本 change 产出的已确认迁移输入基线，但不在本 change 内实现报告详情页。
