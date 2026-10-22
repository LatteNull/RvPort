## 1. Redis 广播基础设施

- [x] 1.1 新增 SSE 跨进程广播配置，定义项目事件 channel、任务日志事件 channel、启用开关和 Redis namespace 规则
- [x] 1.2 新增项目事件广播 payload DTO，只包含 `eventId`、`projectId` 和必要版本字段
- [x] 1.3 新增任务日志事件广播 payload DTO，只包含 `eventId`、`taskId` 和必要版本字段
- [x] 1.4 新增 Redis publisher，负责序列化最小 payload 并发布到对应 channel
- [x] 1.5 新增 Redis subscriber 配置，确保只在 API 或 combined 运行模式启用订阅

## 2. 项目级 SSE 跨进程推送

- [x] 2.1 为 `TaskEventRepository` 增加按 `projectId` 和事件数字 ID 读取单条事件的方法
- [x] 2.2 新增项目事件 Redis subscriber handler，收到通知后从数据库重读事件并调用 `TaskSseBroker.publish`
- [x] 2.3 调整 `TaskEventService` 的 after-commit 发布路径，改为发布跨进程通知
- [x] 2.4 保持项目级 SSE 的 `afterEventId`、`Last-Event-ID`、无游标 baseline 和项目访问守卫行为不变
- [x] 2.5 确认 API 进程没有本地 emitter 时不会触发无意义历史补偿或异常

## 3. 任务级日志 SSE 跨进程推送

- [x] 3.1 为 `TaskLogEventRepository` 增加按 `taskId` 和日志事件数字 ID 读取单条事件的方法
- [x] 3.2 新增任务日志事件 Redis subscriber handler，收到通知后从数据库重读日志事件并调用 `TaskLogSseBroker.publish`
- [x] 3.3 调整 `TaskLogEventService` 的 after-commit 发布路径，改为发布跨进程通知
- [x] 3.4 保持任务级日志 SSE 的首次历史补发、`Last-Event-ID` 恢复、终态事件和权限边界不变
- [x] 3.5 确认 Redis 广播失败不会导致日志事件写入失败或任务状态失败

## 4. 错误处理和运行模式

- [x] 4.1 广播发布失败时记录脱敏 warning，且不向业务调用方抛出导致任务失败的异常
- [x] 4.2 订阅端读取不到事件、project/task 不匹配或 payload 非法时记录脱敏 warning 并丢弃通知
- [x] 4.3 worker-only 模式不启用 Redis subscriber，但仍允许发布广播通知
- [x] 4.4 API 和 combined 模式启用 Redis subscriber，并复用现有 broker 推送逻辑

## 5. 测试

- [x] 5.1 补充单元测试：项目事件 payload 不包含业务数据、日志内容或敏感字段
- [x] 5.2 补充单元测试：任务日志 payload 不包含日志片段、路径或敏感字段
- [x] 5.3 补充单元测试：`TaskEventService` 和 `TaskLogEventService` 在事务提交后才发布 Redis 通知
- [x] 5.4 补充单元测试：Redis 发布失败不影响事件服务返回和任务状态
- [x] 5.5 补充单元测试：订阅端按运行模式启停，并能从数据库重读后推送 broker
- [x] 5.6 补充 E2E：在 `backend` + `backend-worker` 分离容器下，项目级 SSE 能收到 worker 产生的任务生命周期事件
- [x] 5.7 补充 E2E：在分离容器下，项目级 SSE 能收到 Git 同步完成后的 `project.context.changed`
- [x] 5.8 补充 E2E：在分离容器下，任务级日志 SSE 能收到 worker 产生的 stdout/stderr 日志事件

## 6. 验证

- [x] 6.1 运行 `openspec validate fix-cross-process-sse-event-broadcast --strict`
- [x] 6.2 运行相关 Maven 单元测试
- [x] 6.3 重新构建并启动 `backend` 与 `backend-worker` 容器
- [x] 6.4 运行相关 E2E 模块，确认跨进程 SSE 实时推送通过
- [x] 6.5 使用真实或 test-support 异步任务观察浏览器 SSE，确认 heartbeat 正常且 worker 后续事件实时到达
