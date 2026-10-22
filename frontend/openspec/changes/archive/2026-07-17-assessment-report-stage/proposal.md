## Why

迁移输入完成确认后，用户需要一个集中呈现整体风险、优先问题、依赖替代性与工作量判断的评估报告，才能决定是否进入修复阶段。当前 Workflow 的 `report` 节点没有专属报告详情和导出能力。

## What Changes

- 新增评估报告阶段 Drawer，展示总体风险、高风险问题数、预计工作量和结构化报告摘要。
- 支持重新生成当前报告；重新生成会覆盖当前报告结果，并在二次确认中明确提示。
- 支持在同一个 Drawer 内配置导出文件名和格式，并导出 HTML、JSON 或 Markdown 报告。
- 支持从报告阶段进入修复阶段，并在操作成功后刷新 Workflow 状态。
- 增加评估报告的领域类型、API 边界、Vite mock、测试以及 `report` Workflow 节点的 Drawer 映射。

## Capabilities

### New Capabilities

- `assessment-report`: 已生成评估报告的展示、重新生成、导出和修复阶段推进能力。

### Modified Capabilities

- `project-pipeline-workbench`: 工作台支持从 `report` 节点进入评估报告 Drawer，并在报告生成或进入修复阶段后映射服务端 Workflow 状态。

## Impact

- 受影响页面：`src/pages/project-detail/StageDrawer/`、`StageDrawer/index.tsx` 与 Workflow 节点交互。
- 受影响领域边界：`src/types/project.ts`、`src/api/project.ts`、`mock/project.ts` 与领域 API/Drawer 测试。
- 复用现有 BaseDrawer、TanStack Query、Ant Design Descriptions/Form/Select/Popconfirm；不新增运行时依赖，不引入 SSE 或轮询。
- 依赖 `migration-input-merge-stage` 首次生成的报告结果；不重复实现输入选择、冲突处理或首次报告生成。
