## Why

后端已经提供知识库 AI 扩展的 readiness、任务创建、运行记录和 Finding 结果聚合能力，但当前知识库扫描 Drawer 只能被动展示已有 `aiExtension`，用户无法从扫描结果中启动、跟踪或重新生成 AI 建议。需要将这条能力闭环直接集成到知识库扫描结果中，同时保持当前精简工作流拓扑。

## What Changes

- 在当前知识库扫描成功后读取 AI 扩展 readiness，并根据扫描结果、Finding 数量和模型配置展示可执行或不可执行原因。
- 在扫描结果概览中增加“生成 AI 建议”主操作，创建任务后展示排队、运行、成功、部分成功和失败状态，并阻止同一扫描重复并发启动。
- 查询当前扫描对应的最新 AI 扩展运行记录；任务终态后刷新运行记录、Finding 列表与已打开的 Finding 详情，使后端返回的最新 `aiExtension` 成为展示事实。
- 在扫描结果列表中以轻量状态提示哪些 Finding 已有 AI 补充，并继续在 Finding 详情中区分扫描器建议与 AI 补充建议。
- 保持 AI 扩展为知识库扫描 Drawer 内的附加动作，不恢复独立 `kb-ai` 工作流节点。
- 补充领域类型、API、query key、状态展示和交互测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-pipeline-workbench`: 知识库扫描结果支持在当前 Drawer 内启动和跟踪 AI 扩展任务，并在完成后刷新每条 Finding 的 AI 补充建议。
- `knowledge-base-finding-detail`: Finding 详情明确区分扫描器建议与后端返回的最新 AI 补充建议，并随 AI 扩展任务完成刷新。

## Impact

- 前端领域边界：`src/types/project/knowledge-base.ts`、`src/api/project/knowledge-base.ts`、`src/pages/project-detail/queryKeys.ts`。
- 页面状态：`StageDrawer/KnowledgeBase/useKnowledgeBaseDrawer.ts` 负责 readiness、最新运行记录、创建 mutation 和终态刷新。
- 页面展示：知识库扫描结果概览、Finding 列表和 Finding 详情。
- 项目级 SSE：复用现有 `KB_AI_EXTENSION` 任务的 `stageId=kb-scan`、`resource.type=kb_ai_extension_run` 生命周期事件，不新增 SSE 连接。
- 后端与依赖：不修改后端接口，不新增前端运行时依赖，不恢复独立知识库 AI 工作流节点。
