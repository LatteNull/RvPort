## 1. 审查与共享边界

- [x] 1.1 审查 `type`、常量与函数重复候选，排除业务语义不一致的实现。
- [x] 1.2 为共享展示与解析模块补充类型化 API 及单元测试。

## 2. 合并重复实现

- [x] 2.1 迁移构建相关 Drawer 的同构状态展示常量。
- [x] 2.2 迁移环境变量解析和构建时间区间格式化函数，删除局部副本。
- [x] 2.3 清理迁移后无引用的类型、常量、函数、样式与测试 fixture。

## 3. 验证

- [x] 3.1 运行受影响单元测试、`pnpm lint` 和 `pnpm typecheck`。
- [x] 3.2 运行 `openspec validate consolidate-frontend-abstractions --strict`。
