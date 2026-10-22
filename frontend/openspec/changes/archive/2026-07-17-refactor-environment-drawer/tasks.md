## 1. 模块拆分

- [x] 1.1 提取环境表单到 API 输入模型的纯转换函数，并添加单元测试。
- [x] 1.2 提取检查结果、日志等纯展示视图，以及 Drawer 标题/Footer 组合模块。
- [x] 1.3 提取环境 Drawer 的视图切换、查询、mutation 与缓存失效编排 hook。
- [x] 1.4 收敛 `Environment/index.tsx` 为模块组合入口，保持公开 props 和可观察行为不变。

## 2. 验证

- [x] 2.1 更新或补充环境 Drawer 相关单元测试，覆盖输入转换及关键操作路径。
- [ ] 2.2 在 Node `>=24.18.0` 运行 `openspec validate refactor-environment-drawer`、`pnpm format:check`、`pnpm lint`、`pnpm typecheck` 和 `pnpm test`。
