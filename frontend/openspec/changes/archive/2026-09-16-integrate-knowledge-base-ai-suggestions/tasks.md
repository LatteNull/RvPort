## 1. API 与领域状态

- [x] 1.1 增加 AI 扩展 readiness、运行记录、创建响应和状态类型，并通过 TypeScript 类型检查验证与后端 DTO 一致
- [x] 1.2 在知识库 API 模块增加 readiness、运行列表和创建请求，在 query key 工厂增加对应 key，并用 API 单元测试验证路径、参数和请求体

## 2. AI 扩展状态闭环

- [x] 2.1 在知识库 Drawer Hook 中并行读取当前扫描 readiness 与最新运行记录，创建成功后更新缓存，并用 Hook/页面测试覆盖可用、禁用和创建状态
- [x] 2.2 扩展项目任务 SSE 的 `kb_ai_extension_run` 精确失效规则，并用事件 Hook 测试验证终态刷新运行记录、Finding 列表和详情

## 3. 知识库扫描界面

- [x] 3.1 在扫描结果概览加入紧凑 AI 状态条和生成/重新生成操作，并用组件测试覆盖未生成、运行中、成功、部分成功、失败及请求错误状态
- [x] 3.2 在 Finding 列表增加轻量 AI 补充标识，在详情补全置信度展示，并用组件测试验证有无 `aiExtension` 的呈现差异
- [x] 3.3 保证历史扫描记录保持只读且不出现生成入口，并用知识库 Drawer 测试验证当前与历史上下文的操作边界

## 4. 交付验证

- [x] 4.1 运行相关 Vitest 用例、`pnpm lint`、`pnpm typecheck`、`git diff --check` 与 `openspec validate integrate-knowledge-base-ai-suggestions --strict` 并修复本 change 引入的问题
- [x] 4.2 运行 `pnpm format:check`；仅命中已有的无关基线文件 `src/pages/project-detail/StageDrawer/AssessmentReport/index.tsx`，本 change 文件格式检查通过
