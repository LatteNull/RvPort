## ADDED Requirements

### Requirement: API E2E 必须覆盖任务日志通知和增量读取
API E2E 测试 SHALL 独立覆盖新任务日志通知 SSE 与增量读取接口的正常流程、异常流程和 edge case，并 SHALL 在测试结束后清理 fixture 数据。

#### Scenario: 正常流程下通知并读取增量
- **WHEN** E2E 创建运行中任务，建立日志通知 SSE，并分批写入 stdout 和 stderr fixture
- **THEN** SSE SHALL 收到不含正文的 `task.log.updated`
- **AND** 增量 API SHALL 按游标返回对应 stdout、stderr 和顺序合并的 merged 内容
- **AND** 使用返回游标再次请求 SHALL 只取得后续新增内容

#### Scenario: 正常终态收尾
- **WHEN** E2E 在最后一批日志写入后将任务置为终态
- **THEN** SSE SHALL 先允许前端获知最后日志游标
- **AND** SSE SHALL 收到 `task.log.completed` 并结束
- **AND** 最终增量请求 SHALL 能取得终态前写入的全部剩余日志

#### Scenario: 异常参数和越权访问
- **WHEN** E2E 使用非法游标、非法 limit 或无任务权限用户调用新接口
- **THEN** 后端 SHALL 返回约定的 400 或不可枚举权限响应
- **AND** 响应与 SSE MUST NOT 泄露其他任务日志、状态或游标

#### Scenario: Edge case 多连接和跨任务隔离
- **WHEN** E2E 同时订阅同一任务两次并向另一个任务写入交错事件
- **THEN** 同一任务的两个连接 SHALL 收到对应变化通知
- **AND** 任一增量响应 MUST NOT 包含另一个任务的日志

#### Scenario: Edge case 已终态任务与空日志
- **WHEN** E2E 订阅一个没有任何日志且已经终态的任务
- **THEN** SSE SHALL 立即发送 `task.log.completed` 并结束
- **AND** 增量 API SHALL 返回空的三类内容和 `hasMore=false`

#### Scenario: 现有日志接口回归
- **WHEN** E2E 调用旧 `/log-events` 和现有 `/log-content`
- **THEN** 两个接口 SHALL 在迁移期保持既有行为
- **AND** 新增接口 MUST NOT 改变 `log-content` 的完成态历史分页结果
