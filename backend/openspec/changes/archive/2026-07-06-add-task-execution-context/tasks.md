## 1. 执行上下文模型

- [x] 1.1 新增 `TaskExecutionContext` 接口，提供 `task()`、输入解析、进度更新、事件追加和日志写入方法。
- [x] 1.2 新增默认执行上下文实现，组合 `TaskRepository`、`TaskEventService`、任务日志写入能力、`ObjectMapper` 和运行时日志目录配置。
- [x] 1.3 为输入快照解析定义安全失败策略，解析失败时抛出可由 worker 映射为任务失败的异常，错误摘要不得包含原始输入快照。
- [x] 1.4 为进度更新增加 0 到 100 的边界校验，并确保合法进度同时更新 `tasks.progress/message` 与追加 `task.progress` 事件。
- [x] 1.5 增加日志摘要截断和基础敏感信息遮蔽工具，覆盖 password、token、privateKey、passphrase、secret 等关键词边界。

## 2. 任务日志写入能力

- [x] 2.1 为 worker 侧新增任务日志写入入口，支持 `STDOUT`、`STDERR`、`COMBINED` 和 `TOOL` 类型。
- [x] 2.2 将日志文件写入 `RVPORT_LOG_DIR` 管理目录下的任务专属子目录，并避免向 API 或事件暴露真实绝对路径。
- [x] 2.3 在 `task_logs` 表登记日志类型、文件路径、大小、摘要和创建时间所需信息。
- [x] 2.4 处理空日志内容，确保不会产生无法下载的悬空日志记录。
- [x] 2.5 处理日志文件创建或写入失败，并将失败映射为安全的任务失败摘要。

## 3. Worker 与 Handler 改造

- [x] 3.1 调整 `TaskHandler` 接口，使 handler 接收 `TaskExecutionContext`。
- [x] 3.2 调整 `TaskWorkerService`，在任务认领成功后创建执行上下文并传递给 handler。
- [x] 3.3 保持缺少 handler、handler 抛异常、重复消息跳过和成功完成的既有状态流转语义。
- [x] 3.4 确保 handler 成功完成后 worker 仍统一设置 `SUCCEEDED`、`finished_at`、进度 100 和 `task.succeeded` 事件。
- [x] 3.5 确保 RabbitMQ 消息格式和任务 API 响应不因执行上下文引入输入快照、日志内容或明文凭据。

## 4. 单元测试与边界覆盖

- [x] 4.1 为执行上下文补充正常流程测试：解析输入、更新进度、写入日志、追加日志摘要事件。
- [x] 4.2 为执行上下文补充异常流程测试：输入解析失败、非法进度、日志写入失败。
- [x] 4.3 为执行上下文补充 edge case 测试：空日志、超长日志摘要截断、多次进度更新、敏感信息遮蔽。
- [x] 4.4 更新 `TaskWorkerServiceTests`，覆盖新 handler 接口下的成功、缺少 handler、handler 抛异常、不可认领任务和任务不存在路径。
- [x] 4.5 更新或新增日志下载相关测试，确认新写入的日志记录可通过既有受控下载能力访问，且非法路径仍被拒绝。

## 5. 验证与收尾

- [x] 5.1 运行受影响测试类，确认任务执行上下文、worker 和任务日志测试通过。
- [x] 5.2 运行完整 `mvn test`，确认普通单元测试通过，且不依赖 Docker Compose、RabbitMQ、Redis 或真实 PostgreSQL 连通性。
- [x] 5.3 复核新增实现没有引入 SSH/Git 真实执行逻辑，确保本 change 范围只限任务执行器基础能力。
- [x] 5.4 复核 API 响应、任务事件、队列消息和测试断言中不包含明文凭据、完整日志或服务器真实绝对路径。
