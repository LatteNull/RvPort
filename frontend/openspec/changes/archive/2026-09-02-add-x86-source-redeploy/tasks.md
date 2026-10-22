## 1. 实现

- [x] 1.1 扩展源码部署 API 封装，支持显式的 `force` 选项并保留默认首次部署语义。
- [x] 1.2 在 x86 构建前置条件的成功部署状态中增加带确认的“重新部署”操作。
- [x] 1.3 创建任务后失效当前源码部署与 overview 缓存，并提供区分首次部署与重新部署的反馈。

## 2. 验证

- [x] 2.1 覆盖重新部署操作发送 `force: true` 的单元测试。
- [x] 2.2 运行相关 Vitest、format、lint、typecheck 与 `openspec validate add-x86-source-redeploy --strict`。
