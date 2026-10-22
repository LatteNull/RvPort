## ADDED Requirements

### Requirement: 构建验证必须基于成功源码部署创建
后端 SHALL 提供构建验证创建 API，并 SHALL 使用成功的源码部署记录作为远端源码输入。

#### Scenario: 创建单环境构建验证
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/builds` 并提交一个 `sourceDeploymentId`、构建脚本和超时时间
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 校验源码部署记录属于 URL 中的 `projectId`
- **AND** 后端 SHALL 校验源码部署记录状态为 `SUCCEEDED`
- **AND** 后端 SHALL 创建任务类型为 `BUILD_VALIDATION` 的 `tasks` 记录
- **AND** 后端 SHALL 创建一条绑定该任务的 `build_runs` 记录
- **AND** 后端 SHALL 投递任务到 RabbitMQ
- **AND** 响应 SHALL 返回构建运行 ID、任务 ID、环境 ID、源码版本 ID 和初始状态

#### Scenario: 创建双环境构建验证
- **WHEN** 已登录用户提交 x86 和 RISC-V 两条成功源码部署记录
- **THEN** 后端 SHALL 为每条源码部署记录创建独立的构建运行和任务
- **AND** 两条构建运行 SHALL 绑定同一个源码版本
- **AND** 任一环境构建失败 MUST NOT 阻止另一环境任务执行或写回结果

#### Scenario: 拒绝失败或未完成部署
- **WHEN** 用户提交的源码部署记录状态不是 `SUCCEEDED`
- **THEN** 后端 SHALL 返回 `SOURCE_DEPLOYMENT_NOT_READY`
- **AND** 后端 MUST NOT 创建构建任务、构建运行或队列消息

#### Scenario: 拒绝跨项目部署
- **WHEN** 用户提交的源码部署记录不属于 URL 中的项目
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露其他项目的源码部署、源码版本、环境或远端路径信息

### Requirement: 构建脚本必须安全存储和执行
后端 SHALL 对构建脚本做输入校验、加密存储和远端临时脚本执行。

#### Scenario: 保存构建脚本
- **WHEN** 用户创建构建验证任务
- **THEN** 后端 SHALL 将完整构建脚本加密保存到 `task_script_payloads`
- **AND** `tasks.input_snapshot` MUST NOT 保存完整构建脚本明文
- **AND** `build_runs.command` SHALL 只保存脱敏命令摘要或脚本哈希

#### Scenario: 拒绝空脚本
- **WHEN** 用户提交空构建脚本或纯空白构建脚本
- **THEN** 后端 SHALL 返回参数校验错误
- **AND** 后端 MUST NOT 创建任务或脚本 payload

#### Scenario: 远端脚本执行
- **WHEN** `BUILD_VALIDATION` worker 执行任务
- **THEN** worker SHALL 在远端创建临时脚本文件
- **AND** worker SHALL 在 `source_deploy_runs.remote_path` 目录中执行该脚本
- **AND** worker SHALL 在执行完成、失败、超时或取消后尝试删除远端临时脚本

### Requirement: 构建验证必须持久化运行结果
构建验证 worker SHALL 将构建运行状态和任务状态可靠写回 PostgreSQL。

#### Scenario: 构建成功
- **WHEN** 远端构建脚本退出码为 `0`
- **THEN** worker SHALL 将任务和 `build_runs.status` 标记为 `SUCCEEDED`
- **AND** worker SHALL 写入 `exit_code=0`、日志引用、开始时间和结束时间
- **AND** worker SHALL 追加任务终态事件供项目级 SSE 推送

#### Scenario: 构建失败
- **WHEN** 远端构建脚本退出码非 `0`
- **THEN** worker SHALL 将任务和 `build_runs.status` 标记为 `FAILED`
- **AND** worker SHALL 写入退出码、失败分类、日志引用和安全错误摘要
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
构建验证 SHALL 复用任务日志和项目级 SSE，使前端能观察运行中状态和历史结果。

#### Scenario: 推送运行中状态
- **WHEN** 构建任务进入 `RUNNING`
- **THEN** 后端 SHALL 追加任务事件
- **AND** 项目级 SSE SHALL 向有项目权限的订阅方推送该事件
- **AND** SSE 事件 MUST 只发送给同一 `projectId` 的连接

#### Scenario: 记录构建输出
- **WHEN** worker 捕获远端 stdout 或 stderr
- **THEN** 后端 SHALL 写入任务日志事件或任务日志文件元数据
- **AND** 前端 SHALL 能通过已有任务日志 API 查询历史日志
- **AND** 响应 MUST NOT 暴露服务器真实日志文件路径

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
- **AND** 响应 SHALL 包含构建运行 ID、项目 ID、任务 ID、源码版本摘要、环境摘要、源码部署 ID、状态、退出码、失败分类、日志引用和时间字段
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
