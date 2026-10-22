## 1. 契约与导航

- [x] 1.1 增加 Worker 列表、详情、任务和并发更新类型及 API 方法，并补充契约测试。
- [x] 1.2 增加 `/admin/workers` 懒加载路由和“Worker 管理”导航。

## 2. Worker 管理界面

- [x] 2.1 实现 Worker 列表、筛选、排序、完整字段展示和显式刷新。
- [x] 2.2 实现 Worker 详情 Drawer 和当前运行任务列表。
- [x] 2.3 实现并发设置 Modal，覆盖正整数、`0` 暂停及提交成功刷新。

## 3. 验证

- [x] 3.1 补充页面交互、详情加载和并发设置测试。
- [x] 3.2 运行受影响文件格式检查与 lint、`pnpm typecheck`、受影响测试、生产构建和 `openspec validate add-worker-management-center --strict`。
