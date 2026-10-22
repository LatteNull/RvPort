## 1. 实现

- [x] 1.1 修复 `WorkerConcurrencyController` 升高并发时的 setter 顺序
- [x] 1.2 修复降低并发时的 setter 顺序
- [x] 1.3 保持并发为 0 时停止 listener、正数时恢复 listener、prefetch 固定为 1

## 2. 测试

- [x] 2.1 增加并发 `1 -> 4` 的单元测试
- [x] 2.2 增加并发 `4 -> 1` 的单元测试
- [x] 2.3 增加并发为 0 暂停和正数恢复的单元测试
- [x] 2.4 运行 worker 相关单元测试

## 3. 运行验证

- [x] 3.1 校验 OpenSpec change
- [x] 3.2 重建并重启后端 worker 容器
- [x] 3.3 通过 API 设置 worker 并发为 4
- [x] 3.4 确认数据库 `active_concurrency` 和 RabbitMQ consumer 数变为 4
