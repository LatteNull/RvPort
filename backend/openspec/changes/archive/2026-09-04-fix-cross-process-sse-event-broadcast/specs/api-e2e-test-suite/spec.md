## ADDED Requirements

### Requirement: API E2E 必须覆盖跨进程 SSE 事件广播
API E2E 测试套件 SHALL 覆盖 API 进程持有浏览器 SSE 连接、worker 进程产生任务事件和日志事件的分进程部署场景。

#### Scenario: 项目级 SSE 接收 worker 任务生命周期事件
- **WHEN** E2E 在 `backend` 与 `backend-worker` 分离部署下创建异步任务
- **AND** 测试在 API 进程上建立 `GET /api/projects/{projectId}/task-events` SSE 连接
- **THEN** E2E SHALL 验证该连接能收到 worker 产生的 `task.queued`、`task.started` 和任务终态事件
- **AND** 如果任务产生进度事件，E2E SHALL 验证该连接能收到 `task.progress`
- **AND** 事件 SHALL 按同一项目隔离，不得收到其他项目事件

#### Scenario: 项目级 SSE 接收 worker 上下文变更事件
- **WHEN** worker 进程完成 Git 同步并激活新的 source revision
- **THEN** E2E SHALL 验证 API 进程上的项目级 SSE 连接能收到 `project.context.changed`
- **AND** 该事件 SHALL 包含 `stageId`、`resource` 和 `changedFields`
- **AND** 事件 payload MUST NOT 包含服务器真实路径、完整 Git 输出、明文凭据、token 或私钥

#### Scenario: 任务级日志 SSE 接收 worker 日志事件
- **WHEN** E2E 在 `backend` 与 `backend-worker` 分离部署下创建会持续输出日志的异步任务
- **AND** 测试在 API 进程上建立 `GET /api/tasks/{taskId}/log-events` SSE 连接
- **THEN** E2E SHALL 验证该连接能收到 worker 产生的 stdout 或 stderr 日志事件
- **AND** 日志事件 SHALL 只属于当前任务
- **AND** 页面断开后重新连接 SHALL 能通过数据库历史事件补发缺失日志

#### Scenario: Redis 广播降级后仍可从数据库恢复
- **WHEN** E2E 无法稳定模拟 Redis Pub/Sub 中断
- **THEN** 测试 SHALL 至少验证事件和日志事件已经落库
- **AND** 使用 `afterEventId`、`Last-Event-ID` 或任务级日志重连能够从数据库恢复事件
- **AND** 测试 SHALL 明确区分实时广播验证和数据库恢复验证

#### Scenario: combined mode 不能替代跨进程验证
- **WHEN** E2E 覆盖跨进程 SSE 广播
- **THEN** 测试环境 MUST 使用独立 API 进程和独立 worker 进程
- **AND** 只在 combined mode 下通过的测试 MUST NOT 被视为跨进程广播验证通过
