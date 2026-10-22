## 1. 领域契约与数据边界

- [x] 1.1 在项目领域类型中定义评估报告阶段详情、风险指标、结构化摘要、导出请求与导出结果。
- [x] 1.2 在项目 API 模块中实现报告详情、重新生成、导出和进入修复阶段的请求边界。
- [x] 1.3 扩展 Vite mock，以正式响应包络提供当前报告、重新生成覆盖、导出和阶段推进后的 workflow 状态变化。
- [x] 1.4 为评估报告 API 与 mock 的请求、响应、失败和状态流转添加测试。

## 2. 评估报告 Drawer

- [x] 2.1 新建 `StageDrawer/AssessmentReport` 模块，使用 TanStack Query 加载报告阶段详情并以 `800px` BaseDrawer 承载内部视图。
- [x] 2.2 实现报告结果视图的风险概览卡、结构化摘要、加载、空数据和失败状态。
- [x] 2.3 实现重新生成报告的确认操作，以及进入修复阶段的确认操作和 query 刷新。
- [x] 2.4 实现 Drawer 内导出视图，支持文件名、HTML/JSON/Markdown 格式、扩展名同步、校验、下载和失败恢复。
- [x] 2.5 使用嵌套 SCSS Module 完成 `800px` 报告布局、摘要换行、Footer 操作和导出内部视图样式。

## 3. Workflow 集成与验证

- [x] 3.1 在 `StageDrawer/index.tsx` 注册 `report` 专属 Drawer，并在 mutation 成功后失效报告详情和 workflow 状态 query。
- [x] 3.2 为报告展示、空数据、重新生成确认、导出格式与文件名校验、进入修复阶段添加 Drawer 交互测试。
- [x] 3.3 更新根目录 `problem.md`，记录实现结果与原型之间仍待确认的偏差。
- [x] 3.4 运行 `openspec validate assessment-report-stage --strict`、相关单元测试、`pnpm format:check`、`pnpm lint` 与 `pnpm typecheck`，并记录无法通过的既有问题。

验证记录：`openspec validate assessment-report-stage --strict`、`pnpm format:check`、`pnpm typecheck` 与评估报告相关 Vitest 均通过。全量 `pnpm lint` 仍受既有 `mock/project.ts` 的 3 项未使用声明和 `src/App.tsx` 的 import 排序影响；本次涉及的前端实现文件已通过 scoped lint。
