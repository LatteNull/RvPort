## 1. 领域数据与开发期契约

- [x] 1.1 在 `src/types/project.ts` 定义 AI 扩展阶段、建议结果、摘要、生成范围、判断、置信度和迁移输入状态类型。
- [x] 1.2 在 `src/api/project.ts` 增加阶段详情、建议分页列表、生成建议和加入迁移输入的领域 API。
- [x] 1.3 在 `mock/project.ts` 实现符合正式包络的阶段详情、分页建议、生成状态与已加入状态更新 mock。
- [x] 1.4 在 `src/api/project.test.ts` 覆盖 AI 扩展 API 的 URL、请求体、分页参数和加入参数契约。

## 2. 知识库 AI 扩展 Drawer

- [x] 2.1 新增 `StageDrawer/KnowledgeBaseAi` 目录、入口组件、SCSS Module 和 `results`/`config` 内部视图状态。
- [x] 2.2 实现阶段摘要、加载、未生成、生成中、失败和可恢复错误状态。
- [x] 2.3 使用 BaseTable 实现服务端分页建议表，包含六列、当前页全选/反选、已加入禁选和内容优先高度。
- [x] 2.4 实现 BaseTable selection 工具栏的批量加入迁移输入操作、二次确认、禁用规则和成功后的刷新。
- [x] 2.5 实现 Drawer 内生成配置视图，仅支持全部/高风险知识库 findings，取消时返回结果视图，提交时刷新阶段状态与建议结果。
- [x] 2.6 将 AI 扩展 Drawer 在所有内部视图固定为 `1100px`，并在配置视图禁用意外关闭。

## 3. 工作台集成

- [x] 3.1 在 `StageDrawer/index.tsx` 注册 `kb-ai` 到知识库 AI 扩展 Drawer 的映射。
- [x] 3.2 在生成和加入迁移输入成功后失效项目 workflow 状态查询，使固定 `kb-ai` 节点读取服务端最新状态。

## 4. 测试与交付记录

- [x] 4.1 为 AI 扩展 Drawer 覆盖结果展示、生成配置、分页选择与加入、运行/失败/空态及关闭语义测试。
- [x] 4.2 实现完成后将与原型存在的待确认差异记录到根目录 `problem.md`。
- [x] 4.3 运行 `openspec validate knowledge-base-ai-stage`、`pnpm format:check`、`pnpm lint`、`pnpm typecheck` 和相关 `pnpm test`。
