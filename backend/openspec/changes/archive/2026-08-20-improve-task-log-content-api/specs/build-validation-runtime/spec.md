## MODIFIED Requirements

### Requirement: 构建验证必须持久化运行结果
构建验证 worker SHALL 将构建运行状态和任务状态可靠写回 PostgreSQL，并 SHALL 保存 merged/stdout/stderr 三类日志引用。

#### Scenario: 构建成功
- **WHEN** 远端构建脚本退出码为 `0`
- **THEN** worker SHALL 将任务和 `build_runs.status` 标记为 `SUCCEEDED`
- **AND** worker SHALL 写入 `exit_code=0`、merged/stdout/stderr 日志引用、开始时间和结束时间
- **AND** worker SHALL 追加任务终态事件供项目级 SSE 推送

#### Scenario: 构建失败
- **WHEN** 远端构建脚本退出码非 `0`
- **THEN** worker SHALL 将任务和 `build_runs.status` 标记为 `FAILED`
- **AND** worker SHALL 写入退出码、失败分类、merged/stdout/stderr 日志引用和安全错误摘要
- **AND** worker SHALL 在失败状态可靠写回后确认 RabbitMQ 消息

#### Scenario: SSH 或远端命令失败
- **WHEN** SSH 连接失败、认证失败、远端工作目录不存在或远端命令无法启动
- **THEN** worker SHALL 将任务和 `build_runs.status` 标记为 `FAILED`
- **AND** 失败摘要 MUST NOT 暴露明文凭据或服务器本机路径

#### Scenario: 构建超时
- **WHEN** 构建执行超过 `timeoutSeconds`
- **THEN** worker SHALL 尝试终止远端命令
- **AND** worker SHALL 将任务和 `build_runs.status` 标记为 `TIMEOUT`
- **AND** worker SHALL 写入失败分类 `BUILD_TIMEOUT`

### Requirement: 构建验证必须支持日志和 SSE 观察
构建验证 SHALL 复用任务日志、任务日志内容读取 API 和项目级 SSE，使前端能观察运行中状态和完成后历史结果。

#### Scenario: 推送运行中状态
- **WHEN** 构建任务进入 `RUNNING`
- **THEN** 后端 SHALL 追加任务事件
- **AND** 项目级 SSE SHALL 向有项目权限的订阅方推送该事件
- **AND** SSE 事件 MUST 只发送给同一 `projectId` 的连接

#### Scenario: 记录构建输出
- **WHEN** worker 捕获远端 stdout 或 stderr
- **THEN** 后端 SHALL 写入 stdout、stderr 和 merged 任务日志文件
- **AND** 后端 SHALL 写入任务日志事件用于运行中 SSE
- **AND** 响应 MUST NOT 暴露服务器真实日志文件路径

#### Scenario: 完成后读取构建日志内容
- **WHEN** 构建任务进入终态且前端需要展示历史日志
- **THEN** 前端 SHALL 通过 `GET /api/tasks/{taskId}/log-content` 读取 merged/stdout/stderr 日志内容
- **AND** 构建详情响应 SHALL 返回 merged/stdout/stderr 日志 ID 或明确缺失状态

### Requirement: 构建验证查询必须支持分页排序过滤
后端 SHALL 提供构建验证列表、详情和取消 API，并 SHALL 对所有访问执行项目权限校验。

#### Scenario: 查询构建列表
- **WHEN** 用户调用 `GET /api/projects/{projectId}/builds`
- **THEN** 后端 SHALL 返回分页构建运行列表
- **AND** 列表 SHALL 支持按 `sourceRevisionId`、`environmentId`、`status` 和创建时间范围过滤
- **AND** 列表 SHALL 支持按 `createdAt`、`startedAt`、`finishedAt`、`status` 和 `environmentId` 排序

#### Scenario: 查询构建详情
- **WHEN** 用户调用 `GET /api/builds/{buildId}`
- **THEN** 后端 SHALL 根据构建所属项目执行项目访问守卫
- **AND** 响应 SHALL 包含构建运行 ID、项目 ID、任务 ID、源码版本摘要、环境摘要、源码部署 ID、状态、退出码、失败分类、merged/stdout/stderr 日志引用和时间字段
- **AND** 响应 MUST NOT 返回完整构建脚本明文、明文凭据或服务器本机路径

#### Scenario: 取消构建
- **WHEN** 用户调用 `POST /api/builds/{buildId}/cancel`
- **THEN** 后端 SHALL 根据构建所属项目执行项目访问守卫
- **AND** 后端 SHALL 复用任务取消服务取消对应任务
- **AND** `build_runs.status` SHALL 最终与任务终态一致

#### Scenario: 无权限访问构建
- **WHEN** 无项目权限用户查询或取消构建运行
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露构建运行是否存在
