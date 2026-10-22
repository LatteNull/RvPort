## ADDED Requirements

### Requirement: Test-support API 必须构建期隔离
测试辅助 API SHALL 放在独立源码目录，并 MUST NOT 被默认生产构建编译或打包进 jar。

#### Scenario: 默认生产构建
- **WHEN** 开发者执行默认 Maven 构建命令
- **THEN** 构建产物 MUST NOT 包含 `/api/test-support/**` controller、配置类、DTO 或相关资源
- **AND** 构建产物 MUST NOT 包含旧 `/api/dev/session` controller

#### Scenario: 显式测试构建
- **WHEN** 开发者显式启用 test-support Maven profile 构建或运行后端
- **THEN** 构建 SHALL 将 test-support 源码目录加入编译
- **AND** 后端 SHALL 暴露 `/api/test-support/**` 测试辅助 API

### Requirement: Test-support API 必须要求测试 token
测试辅助 API SHALL 要求请求提交 test-support token，并 SHALL 在 token 缺失或错误时拒绝请求。

#### Scenario: 携带有效 token
- **WHEN** E2E runner 调用 `/api/test-support/**` 并提交有效 `X-RvPort-Test-Support-Token`
- **THEN** 后端 SHALL 继续处理该测试辅助请求

#### Scenario: token 缺失或错误
- **WHEN** 请求未提交 test-support token 或 token 不匹配
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 执行 fixture、触发器、清理或 session 创建动作

#### Scenario: 未配置 token
- **WHEN** test-support 构建已启用但后端未配置 test-support token
- **THEN** test-support API SHALL 默认不可用或拒绝所有请求

### Requirement: Test-support API 不得提供通用后门
测试辅助 API MUST NOT 提供任意 SQL、任意 shell、任意文件读取写入、任意 Spring Bean 调用或通用调试控制台。

#### Scenario: 请求执行任意 SQL
- **WHEN** 客户端尝试通过 test-support API 提交任意 SQL
- **THEN** 后端 MUST NOT 提供此类接口

#### Scenario: 请求执行任意命令
- **WHEN** 客户端尝试通过 test-support API 提交任意 shell 命令或系统命令
- **THEN** 后端 MUST NOT 提供此类接口

### Requirement: Test-support API 必须提供测试 session 创建能力
测试辅助 API SHALL 替代旧 dev session 能力，允许 E2E 通过用户名创建测试 session。

#### Scenario: 创建测试 session
- **WHEN** E2E 调用 `POST /api/test-support/session` 并提交有效 token 和存在的用户名
- **THEN** 后端 SHALL 为该用户创建服务端 session
- **AND** 响应 SHALL 设置正常的 session cookie
- **AND** 响应 MUST NOT 包含密码、密码哈希、角色或权限字段

#### Scenario: 用户不存在
- **WHEN** E2E 使用不存在的用户名创建测试 session
- **THEN** 后端 SHALL 返回明确错误
- **AND** 后端 MUST NOT 创建 session

### Requirement: Test-support API 必须支持 SSE 测试触发
测试辅助 API SHALL 支持创建任务事件、触发 SSE 推送和触发 SSE heartbeat，用于验证项目级 SSE 行为。

#### Scenario: 插入任务事件并推送 SSE
- **WHEN** E2E 调用 `POST /api/test-support/projects/{projectId}/task-events` 并提交合法任务事件 fixture
- **THEN** 后端 SHALL 创建对应任务事件
- **AND** 后端 SHALL 触发项目级 SSE 推送

#### Scenario: 触发 SSE heartbeat
- **WHEN** E2E 调用 `POST /api/test-support/sse/heartbeat`
- **THEN** 后端 SHALL 对当前已注册的 SSE emitter 发送 heartbeat

#### Scenario: 项目或任务不匹配
- **WHEN** 任务事件 fixture 的任务不属于请求中的项目
- **THEN** 后端 SHALL 拒绝创建事件

### Requirement: Test-support API 必须支持用户 action token fixture 和清理触发
测试辅助 API SHALL 支持创建用户 action token 测试数据，并 SHALL 支持显式触发历史 token 清理逻辑。

#### Scenario: 创建 token fixture
- **WHEN** E2E 调用 `POST /api/test-support/user-action-tokens/fixtures`
- **THEN** 后端 SHALL 创建指定类型、过期时间和消费状态的 action token 测试数据
- **AND** 响应 MUST NOT 返回 token hash

#### Scenario: 触发 token 清理
- **WHEN** E2E 调用 `POST /api/test-support/user-action-tokens:cleanup`
- **THEN** 后端 SHALL 执行与定时任务一致的用户 action token 清理逻辑

#### Scenario: 清理不删除有效 token
- **WHEN** 清理逻辑执行时存在未过期且未消费 token
- **THEN** 后端 MUST NOT 删除这些仍可使用的 token

### Requirement: Test-support API 必须支持任务运行时测试触发
测试辅助 API SHALL 支持显式触发 pending task dispatch repair，并 MAY 支持直接处理指定任务。

#### Scenario: 触发 dispatch repair
- **WHEN** E2E 调用 `POST /api/test-support/tasks:repair-dispatch`
- **THEN** 后端 SHALL 执行与后台 repair 调度一致的 pending task dispatch repair 逻辑

#### Scenario: 直接处理指定任务
- **WHEN** E2E 调用 `POST /api/test-support/tasks/{taskId}:process`
- **THEN** 后端 MAY 直接调用 worker 处理指定任务
- **AND** 后端 SHALL 只处理已存在任务
- **AND** 后端 MUST NOT 接受客户端提交任意任务输入快照

#### Scenario: 任务不存在
- **WHEN** E2E 请求处理不存在的任务
- **THEN** 后端 SHALL 返回明确错误

### Requirement: Test-support API 必须支持邮件 outbox 查询和清理
测试辅助 API SHALL 支持查询和清理测试邮件 outbox，便于验证邀请、忘记密码和任务完成邮件。

#### Scenario: 查询测试邮件 outbox
- **WHEN** E2E 调用 `GET /api/test-support/mail/outbox`
- **THEN** 后端 SHALL 返回可分页的测试邮件摘要
- **AND** 响应 MUST NOT 返回 SMTP 密码、token hash 或其他秘密

#### Scenario: 清理测试邮件 outbox
- **WHEN** E2E 调用 `DELETE /api/test-support/mail/outbox` 并提交 run id 或测试前缀
- **THEN** 后端 SHALL 清理匹配范围内的测试邮件记录

#### Scenario: 清理范围为空
- **WHEN** 清理请求没有提交 run id、测试前缀或明确资源 ID
- **THEN** 后端 SHALL 拒绝清理请求

### Requirement: Test-support API 必须支持 SBOM 轻量 fixture
测试辅助 API SHALL 支持创建 SBOM 轻量 fixture，用于验证分页、排序、过滤、artifact 查询和清理行为。

#### Scenario: 创建 SBOM fixture
- **WHEN** E2E 调用 `POST /api/test-support/sbom/fixtures`
- **THEN** 后端 SHALL 创建指定项目和任务关联的 SBOM 测试数据
- **AND** 后端 SHALL 保证数据带有 run id 或测试前缀

#### Scenario: fixture 项目不匹配
- **WHEN** SBOM fixture 中的任务、运行或 artifact 不属于同一项目
- **THEN** 后端 SHALL 拒绝创建 fixture

### Requirement: Test-support API 必须支持队列状态查询
测试辅助 API SHALL 支持查询测试所需的 RabbitMQ 队列状态摘要。

#### Scenario: 查询任务队列状态
- **WHEN** E2E 调用 `GET /api/test-support/queues/task`
- **THEN** 后端 SHALL 返回任务队列、retry 队列和 dead-letter 队列的摘要信息
- **AND** 响应 MUST NOT 返回明文凭据或完整业务载荷

### Requirement: Test-support API 必须支持测试 runtime 清理
测试辅助 API SHALL 支持按 run id 或测试前缀清理测试数据和 runtime 文件。

#### Scenario: 清理指定 run id
- **WHEN** E2E 调用 `POST /api/test-support/runtime:cleanup` 并提交 run id
- **THEN** 后端 SHALL 清理该 run id 关联的测试数据库记录、测试邮件、测试任务事件和测试 runtime 文件

#### Scenario: 拒绝过宽清理
- **WHEN** 清理请求没有 run id、测试前缀或明确资源 ID
- **THEN** 后端 SHALL 拒绝执行清理
- **AND** 后端 MUST NOT 删除真实业务数据
