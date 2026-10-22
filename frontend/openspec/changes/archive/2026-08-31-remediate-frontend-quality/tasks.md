## 1. 恢复规格与质量门禁

- [x] 1.1 补齐并格式化所有主规格 Purpose，验证 `openspec validate --specs --strict` 通过。
- [x] 1.2 修复格式、lint 与 TypeScript 错误及测试 fixture，验证 `pnpm format:check`、`pnpm lint`、`pnpm typecheck` 通过。

## 2. 收敛代码结构与样式边界

- [x] 2.1 将超过约 400 行且混合独立职责的 Stage Drawer 拆为同目录模块，验证受影响单元测试通过。
- [x] 2.2 修复 CSS Module 无效选择器，并将新增 Drawer 样式限制在组件根类名；验证 Drawer 视觉与交互不变。

## 3. 现代化 UI 与性能细节

- [x] 3.1 补齐账号、邮箱、URL 等表单原生语义，并验证相关表单测试通过。
- [x] 3.2 为 LogViewer 添加长日志分段渲染和完整内容操作，验证长日志组件测试通过。
- [x] 3.3 集中使用 `Intl.DateTimeFormat` 和 `Intl.NumberFormat` 格式化展示数据，验证展示工具测试通过。
- [x] 3.4 为新增/编辑表单使用关闭后卸载与字段清理策略，避免复用上次输入，并验证公共组件测试通过。
- [x] 3.5 记录 Ant Design 布局原语、原生语义元素与 CSS Module 的使用边界。
- [x] 3.6 审查并迁移现有 Ant Design 内部选择器；优先采用公开的 `classNames` / `styles` 语义化接口，并为必要例外补充原因。

## 4. 验证

- [x] 4.1 运行 `pnpm test` 与 `pnpm build`，确认质量门禁和生产产物通过。
- [x] 4.2 运行 `openspec validate remediate-frontend-quality --strict`，确认 change 完整。
