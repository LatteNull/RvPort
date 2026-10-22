## Why

知识库扫描仅能识别迁移风险，用户仍需逐条理解原因、选择修改策略并确定验证方式。需要增加知识库 AI 扩展阶段，将知识库 findings 转化为可审阅、可选择并可并入迁移输入的建议结果。

## What Changes

- 新增知识库 AI 扩展阶段 Drawer，展示阶段状态、待解释/已生成/需人工确认摘要和服务端分页的建议结果表。
- 支持在同一 Drawer 内配置输入范围并启动 AI 建议生成；固定生成原因解释、修改方式和验证建议，不提供无意义的输出内容选择。
- 支持在结果表逐行或全选建议，并在二次确认后将已选建议加入迁移输入；已加入建议不可重复选择。
- 增加 `kb-ai` 阶段详情、建议分页查询、生成和加入迁移输入的领域类型、API 边界、Vite mock 及测试。
- 为工作台 `kb-ai` 节点注册专属 Drawer，并在生成或加入成功后刷新 workflow 状态。

## Capabilities

### New Capabilities

- `knowledge-base-ai-extension`: 知识库 findings 的 AI 扩展建议生成、结果审阅、选择和迁移输入加入能力。

### Modified Capabilities

- `project-pipeline-workbench`: 工作台支持从 `kb-ai` 节点进入知识库 AI 扩展 Drawer，并映射该阶段的服务端状态。

## Impact

- 受影响页面：`src/pages/project-detail/StageDrawer/`、`StageDrawer/index.tsx` 和项目工作台 Workflow 节点交互。
- 受影响领域边界：`src/types/project.ts`、`src/api/project.ts`、`mock/project.ts` 与领域 API/Drawer 测试。
- 复用现有 BaseDrawer、BaseTable、TanStack Query、Ant Design Form/Select/Popconfirm；不新增运行时依赖，不引入 SSE 或轮询。
