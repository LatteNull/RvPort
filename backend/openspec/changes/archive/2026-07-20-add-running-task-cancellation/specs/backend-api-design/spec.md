## MODIFIED Requirements

### Requirement: 长任务 API 以 PostgreSQL 任务模型为事实来源
所有长任务创建 API SHALL 先创建持久化任务记录，再返回 `taskId` 和初始任务状态。

#### Scenario: 创建长任务
- **WHEN** 前端发起 Git 同步、环境连接测试、环境采集、远程脚本、KB 扫描、SBOM 分析、报告生成、复检、构建、测试或归档
- **THEN** API SHALL 返回 `taskId`、任务类型和初始状态
- **AND** API SHALL 先创建 `tasks` 记录并追加初始 `task_events`
- **AND** 队列载荷 SHALL 只使用 `task_id` 等路由信息
- **AND** API 响应 MUST NOT 返回完整任务输入快照、明文凭据或服务器本地路径

#### Scenario: 查询任务详情
- **WHEN** 前端调用 `GET /api/tasks/{taskId}`
- **THEN** API SHALL 从持久化任务状态返回任务类型、状态、进度、消息、时间、错误摘要和关联业务资源引用
- **AND** API 响应 MUST NOT 返回完整任务输入快照、明文凭据或服务器本地路径

#### Scenario: 查询项目任务列表
- **WHEN** 前端调用 `GET /api/projects/{projectId}/tasks`
- **THEN** API SHALL 返回该项目的分页任务列表
- **AND** 列表项 SHALL 包含任务 ID、任务类型、状态、进度、消息和关键时间字段

#### Scenario: 取消任务
- **WHEN** 前端调用 `POST /api/tasks/{taskId}/cancel`
- **THEN** API SHALL 可靠取消 `PENDING`、`QUEUED` 或 `RUNNING` 任务
- **AND** 对 `RUNNING` 任务 SHALL 将任务业务状态更新为 `CANCELLED` 并投递取消清理消息
- **AND** API MUST NOT 返回明文凭据、服务器真实路径或底层完整命令输入

#### Scenario: 枚举任务状态
- **WHEN** API 文档列出任务状态
- **THEN** 文档 SHALL 包含 `PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 和 `TIMEOUT`
