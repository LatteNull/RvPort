## 1. 领域契约与数据边界

- [x] 1.1 在项目领域类型中定义迁移输入合并阶段详情、可用来源、合并项、冲突详情、确认状态和报告生成资格。
- [x] 1.2 在项目 API 模块中实现阶段详情、服务端分页列表、重新合并、冲突处理、确认已选问题和生成报告的请求边界。
- [x] 1.3 扩展 Vite mock，以正式响应包络提供可用来源、分页筛选、冲突处理、确认和报告生成后的 workflow 状态变化。
- [x] 1.4 为迁移输入合并 API 与 mock 的请求、响应、失败和状态流转添加测试。

## 2. 迁移输入合并 Drawer

- [x] 2.1 新建 `StageDrawer/MigrationInputMerge` 模块，使用 TanStack Query 加载阶段详情并以 `1100px` BaseDrawer 承载内部视图。
- [x] 2.2 实现结果视图的三项摘要、输入来源入口、服务端筛选栏和 BaseTable 分页列表。
- [x] 2.3 实现输入来源配置视图，展示可用上游来源、候选数量和冲突策略，并在重新合并成功后刷新结果。
- [x] 2.4 实现冲突处理视图，支持采用来源结论或提交手工合并结论，并在成功后返回结果列表。
- [x] 2.5 实现选择工具栏的确认已选问题操作、报告生成资格提示和 Drawer Footer 的生成评估报告操作。
- [x] 2.6 使用嵌套 SCSS Module 完成抽屉摘要、筛选、表格和内部视图的布局、加载、空数据、错误、禁用及提交中状态。

## 3. Workflow 集成与验证

- [x] 3.1 在 `StageDrawer/index.tsx` 注册 `merge` 专属 Drawer，并在所有 mutation 成功后失效阶段详情、列表与 workflow 状态 query。
- [x] 3.2 为结果筛选、来源重新合并、冲突阻断确认、冲突处理、确认已选问题和报告生成资格添加 Drawer 交互测试。
- [x] 3.3 更新根目录 `problem.md`，记录实现结果与原型之间仍待确认的偏差。
- [x] 3.4 运行 `openspec validate migration-input-merge-stage --strict`、相关单元测试、`pnpm format:check`、`pnpm lint` 与 `pnpm typecheck`，并记录无法通过的既有问题。
  - 验证记录：OpenSpec 严格校验、格式检查、类型检查和迁移输入合并定向测试均通过。全仓 `pnpm lint` 仍受既有 `mock/project.ts` 三处未使用声明及 `src/App.tsx` import 排序问题阻断；本 change 涉及文件的 ESLint 已通过。
