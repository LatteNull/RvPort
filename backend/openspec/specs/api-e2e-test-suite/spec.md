> 迁移状态：本能力已退出当前交付范围。下文保留历史规范，相关 CI、E2E 和测试专用 API 实现不在本项目中，不应按下文恢复。历史归档中的原任务状态保持不变。

## Purpose

定义 RvPort 后端独立 API E2E 测试套件的运行边界、覆盖范围、真实基础设施校验、副作用校验、敏感信息边界和清理要求。
## Requirements
### Requirement: API E2E 测试套件必须独立运行
后端 SHALL 提供独立于 Spring Boot 单元测试的 API 端到端测试套件，并 SHALL 通过显式脚本运行，而不是随普通 `mvn test` 自动执行。

#### Scenario: 运行普通单元测试
- **WHEN** 开发者执行 `mvn test`
- **THEN** API E2E 测试套件 MUST NOT 自动运行
- **AND** `mvn test` MUST NOT 因本机 Docker Compose 基础设施未启动而失败

#### Scenario: 显式运行 E2E 测试
- **WHEN** 开发者执行 E2E 运行脚本
- **THEN** 脚本 SHALL 运行独立 API 端到端测试流程
- **AND** 脚本 SHALL 使用真实 HTTP 请求访问运行中的后端 API

#### Scenario: 提供跨平台入口
- **WHEN** 开发者在 Windows 或 Linux/macOS 环境运行 E2E 测试
- **THEN** 后端 SHALL 提供对应平台可用的运行命令或入口脚本

### Requirement: E2E 测试必须检查真实基础设施和后端服务
API E2E 测试套件 SHALL 在运行用例前检查 PostgreSQL、Redis、RabbitMQ 和后端 API 的可用性。

#### Scenario: 基础设施正常
- **WHEN** PostgreSQL、Redis、RabbitMQ 和后端 API 均可访问
- **THEN** E2E 运行脚本 SHALL 继续执行测试用例

#### Scenario: 基础设施未启动
- **WHEN** 任一必要基础设施不可访问或未处于 healthy 状态
- **THEN** E2E 运行脚本 SHALL 失败并输出明确错误
- **AND** 错误信息 SHALL 指出缺失或异常的依赖

#### Scenario: 后端 API 不可访问
- **WHEN** `GET /api/health` 无法成功返回
- **THEN** E2E 运行脚本 SHALL 停止执行测试用例
- **AND** 错误信息 SHALL 提示先启动后端服务

### Requirement: E2E 测试必须覆盖真实浏览器式认证行为
API E2E 测试套件 SHALL 使用真实 Session Cookie 和 CSRF token 调用需要登录态或状态变更的 API。

#### Scenario: 获取 CSRF 并登录
- **WHEN** E2E 用例需要调用受保护 API
- **THEN** runner SHALL 先调用 CSRF 接口获取 token
- **AND** runner SHALL 使用登录接口建立服务端 Session
- **AND** 后续请求 SHALL 携带 Session Cookie 和状态变更所需的 CSRF header

#### Scenario: 未登录访问受保护 API
- **WHEN** E2E 用例不携带有效登录态访问受保护 API
- **THEN** API SHALL 返回未认证错误

#### Scenario: 强制改密用户访问业务 API
- **WHEN** E2E 用例使用 `mustChangePassword=true` 的用户访问受保护业务 API
- **THEN** API SHALL 返回强制改密错误

### Requirement: E2E 用例必须覆盖当前已实现 API 主链路
API E2E 测试套件 SHALL 覆盖当前已实现的认证、用户管理、项目、源码、环境、任务和 SSE 主链路。

#### Scenario: 覆盖认证和用户管理 API
- **WHEN** 运行 E2E 测试
- **THEN** 测试 SHALL 覆盖 CSRF、登录、当前用户、修改密码、退出登录和超级管理员用户管理 API

#### Scenario: 覆盖项目源码环境 API
- **WHEN** 运行 E2E 测试
- **THEN** 测试 SHALL 覆盖项目创建、列表、详情、更新、概览、源码上传、源码激活、Git 同步任务、环境创建、跳板机配置和环境任务投递 API

#### Scenario: 覆盖任务和 SSE API
- **WHEN** 运行 E2E 测试
- **THEN** 测试 SHALL 覆盖项目任务列表、任务详情、任务日志列表、任务取消边界和项目级 SSE 历史事件恢复

### Requirement: E2E 用例必须覆盖正常异常和边界路径
API E2E 测试套件 SHALL 为被覆盖 API 提供正常流程、异常流程和 edge case 测试。

#### Scenario: 覆盖正常流程
- **WHEN** E2E 用例验证 API 成功路径
- **THEN** 测试 SHALL 覆盖合法输入下的成功创建、查询、更新、任务投递、队列消息和 SSE 事件恢复

#### Scenario: 覆盖异常流程
- **WHEN** E2E 用例验证 API 错误路径
- **THEN** 测试 SHALL 覆盖未登录、权限不足、强制改密、资源不存在、参数非法、状态不允许、Git URL 携带凭据和禁用环境创建任务等错误路径

#### Scenario: 覆盖 edge case
- **WHEN** E2E 用例验证边界路径
- **THEN** 测试 SHALL 覆盖空列表、分页边界、重复源码上传、active 源码切换、跳板机自引用、多级跳板、跨项目跳板、脱敏输出、路径隐藏和 SSE 游标边界

### Requirement: E2E 测试必须校验真实副作用和敏感信息边界
API E2E 测试套件 SHALL 校验 HTTP 响应以外的 PostgreSQL、Redis、RabbitMQ 和本地文件副作用，并 SHALL 确认敏感信息不会泄露。

#### Scenario: 校验数据库副作用
- **WHEN** E2E 用例创建或修改业务资源
- **THEN** 测试 SHALL 校验 PostgreSQL 中对应用户、项目、源码、导入、环境、凭据、任务、任务事件和审计记录符合预期

#### Scenario: 校验队列副作用
- **WHEN** E2E 用例创建异步任务
- **THEN** 测试 SHALL 校验 RabbitMQ 队列收到任务消息
- **AND** 队列消息 MUST 只包含任务 ID 等路由信息

#### Scenario: 校验 Redis 和 Session
- **WHEN** E2E 用例完成登录
- **THEN** 测试 SHALL 能确认 Session 基于 Redis 可用
- **AND** Redis key 或 value 检查 MUST NOT 发现明文密码、token 或业务凭据

#### Scenario: 校验敏感信息不泄露
- **WHEN** E2E 用例提交密码、私钥、token 或 passphrase
- **THEN** API 响应、任务输入快照、审计详情、队列消息和日志摘要 MUST NOT 包含明文秘密

### Requirement: E2E 测试必须清理测试数据
API E2E 测试套件 SHALL 在运行完成后清理自身创建的测试数据、上传文件和队列消息，并 SHALL 提供可单独执行的清理脚本。

#### Scenario: 生成 run id
- **WHEN** E2E 测试开始运行
- **THEN** runner SHALL 生成唯一 run id
- **AND** 测试创建的可命名资源 SHALL 带有该 run id 或可追踪前缀

#### Scenario: 正常清理本次运行
- **WHEN** E2E 测试完成或失败进入清理阶段
- **THEN** 清理流程 SHALL 删除本次 run id 关联的数据库记录、上传文件和测试队列消息

#### Scenario: 强制清理历史残留
- **WHEN** 开发者执行强制清理脚本
- **THEN** 清理脚本 SHALL 删除历史 `e2e_` 前缀残留数据
- **AND** 清理脚本 SHALL 清理测试上传目录和测试队列残留消息

#### Scenario: 清理失败
- **WHEN** 清理流程无法删除某类资源
- **THEN** 脚本 SHALL 返回失败状态
- **AND** 脚本 SHALL 输出无法清理的资源类型和标识

### Requirement: E2E 文档必须说明运行和排查方式
API E2E 测试套件 SHALL 提供中文文档，说明运行前置条件、运行命令、清理命令、覆盖范围和失败排查方式。

#### Scenario: 阅读 E2E 文档
- **WHEN** 开发者查看 E2E 文档
- **THEN** 文档 SHALL 说明所需基础设施、后端启动方式、环境变量、运行命令、清理命令和常见失败原因

#### Scenario: 查看覆盖矩阵
- **WHEN** 开发者查看 E2E 文档
- **THEN** 文档 SHALL 列出当前 E2E 覆盖的 API 领域和正常流程、异常流程、edge case 覆盖矩阵

#### Scenario: 新增 API 后更新文档
- **WHEN** 后续 change 新增或修改 API
- **THEN** 对应 change SHALL 同步更新 E2E 覆盖矩阵或说明该 API 不适用 E2E 的原因

### Requirement: API E2E 必须覆盖项目访问守卫
API E2E 测试套件 SHALL 覆盖项目访问守卫的正常流程、异常流程和 edge case，确保普通用户不能读取或操作其他用户项目资源。

#### Scenario: 覆盖普通用户访问自己资源
- **WHEN** E2E 使用普通用户创建项目、源码、环境和任务
- **THEN** 测试 SHALL 验证该用户可以读取项目详情、概览、源码列表、环境列表、任务详情、任务日志和项目级 SSE

#### Scenario: 覆盖超级管理员访问项目资源
- **WHEN** E2E 使用超级管理员访问普通用户创建的项目资源
- **THEN** 测试 SHALL 验证超级管理员可以读取项目详情、任务详情和必要的管理视图

#### Scenario: 覆盖跨用户越权读取
- **WHEN** E2E 使用用户 A 创建项目资源后切换到用户 B
- **THEN** 测试 SHALL 验证用户 B 访问用户 A 的项目详情、概览、源码列表、环境列表、任务列表、任务详情和任务日志时被拒绝
- **AND** 响应 MUST NOT 包含用户 A 项目的名称、任务状态、日志摘要、环境主机或源码版本信息

#### Scenario: 覆盖跨用户越权操作
- **WHEN** E2E 使用用户 B 操作用户 A 的项目资源
- **THEN** 测试 SHALL 验证源码激活、Git 同步、环境运行、任务取消和日志下载被拒绝
- **AND** 后端 MUST NOT 创建任务、投递队列消息或改变用户 A 的资源状态

#### Scenario: 覆盖 SSE 越权订阅
- **WHEN** E2E 使用用户 B 订阅用户 A 项目的 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 拒绝请求
- **AND** 测试 SHALL 验证不会收到用户 A 的历史任务事件

#### Scenario: 覆盖访问守卫 edge case
- **WHEN** E2E 验证访问守卫边界
- **THEN** 测试 SHALL 覆盖不存在项目、软删除项目、任务不存在、日志不属于任务、源码版本不属于项目、环境不属于项目和非法 `Last-Event-ID`

### Requirement: API E2E 必须覆盖 SBOM 分析验证和清理
API E2E 测试套件 SHALL 覆盖 SBOM 分析相关的端到端验证入口、真实副作用检查、artifact 入库检查和测试数据清理。

#### Scenario: 覆盖 SBOM 分析主链路
- **WHEN** 运行 SBOM API E2E 用例且基础设施与后端服务可用
- **THEN** 测试 SHALL 创建或复用测试项目、源环境、目标环境和必要快照
- **AND** 测试 SHALL 创建 `SBOM_ANALYSIS` 任务并等待任务终态
- **AND** 测试 SHALL 校验 `sbom_runs`、`sbom_components`、`replacement_candidates`、`sbom_analysis_artifacts`、`tasks`、`task_events` 和 `tool_runs` 的真实副作用

#### Scenario: 覆盖 SBOM artifact 查询
- **WHEN** SBOM API E2E 用例完成一次成功分析
- **THEN** 测试 SHALL 调用 `GET /api/sbom-analyses/{analysisId}/artifacts`
- **AND** 测试 SHALL 校验列表包含预期 artifact 类型
- **AND** 测试 SHALL 调用 `GET /api/sbom-analyses/{analysisId}/artifacts/{artifactType}`
- **AND** 测试 SHALL 校验 artifact 关联正确的 `project_id`、`task_id` 和 `sbom_run_id`

#### Scenario: 覆盖 SBOM 分析异常流程
- **WHEN** 运行 SBOM API E2E 异常用例
- **THEN** 测试 SHALL 覆盖源快照不存在、目标快照不存在、环境不属于项目、无项目权限和分析器失败
- **AND** 测试 SHALL 验证失败不会写入成功态 SBOM 结果
- **AND** 测试 SHALL 验证失败不会写入成功态 SBOM artifact

#### Scenario: 覆盖 SBOM 分析 edge case
- **WHEN** 运行 SBOM API E2E 边界用例
- **THEN** 测试 SHALL 覆盖空组件清单、仓库候选为空但有 warning、同名不同架构组件、重复仓库候选和输出脱敏
- **AND** 测试 SHALL 验证 API 响应和 artifact 内容不暴露服务器真实敏感路径或凭据

#### Scenario: 清理 SBOM 验证数据
- **WHEN** SBOM API E2E 或真实验证流程结束
- **THEN** 清理流程 SHALL 删除本次 run id 创建的项目、环境、快照、组件、SBOM 运行、替代候选、SBOM artifact、任务、事件、日志、执行记录和临时 runtime 文件
- **AND** 清理流程 SHALL 保留明确标记为非敏感的验证记录
- **AND** 清理失败时 SHALL 返回非零退出码并说明未清理资源

### Requirement: E2E runner 必须支持模块化选择运行
API E2E 测试套件 SHALL 支持按模块、按 case、按 tag 选择运行，并 SHALL 保留全量运行能力。

#### Scenario: 列出可运行 E2E 模块和用例
- **WHEN** 开发者执行 E2E list 命令
- **THEN** runner SHALL 输出所有可运行 case 的 `id`、`module`、`tags` 和简要说明
- **AND** 输出 SHALL 能帮助开发者选择 `--module`、`--case` 或 `--tag`

#### Scenario: 按模块运行
- **WHEN** 开发者执行 `node e2e/runner.js run --module=auth`
- **THEN** runner SHALL 只运行 module 为 `auth` 的 E2E case
- **AND** runner SHALL NOT 运行 project、task、sbom 等无关模块 case

#### Scenario: 按单个 case 运行
- **WHEN** 开发者执行 `node e2e/runner.js run --case=001-auth-users`
- **THEN** runner SHALL 只运行指定 case
- **AND** runner SHALL 在 case 不存在时返回失败状态并输出可用 case 提示

#### Scenario: 按 tag 运行
- **WHEN** 开发者执行 `node e2e/runner.js run --tag=smoke`
- **THEN** runner SHALL 运行所有包含 `smoke` tag 的 case
- **AND** runner SHALL 在 tag 不存在时返回失败状态并输出可用 tag 提示

#### Scenario: 默认全量运行
- **WHEN** 开发者执行 `node e2e/runner.js run`
- **THEN** runner SHALL 继续运行全部 E2E case
- **AND** 该行为 SHALL 与 change 前的默认全量运行兼容

#### Scenario: 显式全量运行
- **WHEN** 开发者执行 `node e2e/runner.js run --all`
- **THEN** runner SHALL 运行全部 E2E case

### Requirement: 模块化 E2E 运行必须具备独立 setup 和清理
API E2E runner SHALL 为任意被选择的模块或 case 执行公共 setup、状态恢复和清理，避免单模块运行依赖其他模块先执行。

#### Scenario: 单独运行非认证模块
- **WHEN** 开发者单独运行 project、task 或 sbom 模块
- **THEN** runner SHALL 在执行 case 前完成基础设施检查、后端健康检查、管理员登录和 CSRF 初始化
- **AND** case SHALL NOT 依赖 `001-auth-users` 先运行才能访问受保护 API

#### Scenario: 临时处理管理员强制改密状态
- **WHEN** runner 发现管理员 `must_change_password=true`
- **THEN** runner SHALL 在执行选中 case 前临时清除该状态
- **AND** runner SHALL 在成功、失败或清理完成后恢复原始状态

#### Scenario: 清理模块化运行数据
- **WHEN** 模块化 E2E 运行成功或失败
- **THEN** runner SHALL 使用本次 run id 和 cleanup registry 清理该次运行创建的数据、上传文件和队列消息
- **AND** 清理范围 SHALL NOT 依赖是否执行了其他模块

### Requirement: E2E post-run assertion 必须按选中模块启用
API E2E runner SHALL 根据选中 case 的需要执行 post-run assertion，避免轻量模块被无关外部副作用校验阻断。

#### Scenario: 轻量认证模块运行
- **WHEN** runner 只运行 auth 模块
- **THEN** runner SHALL 执行 Redis session 和敏感信息边界检查
- **AND** runner SHALL NOT 因 RabbitMQ 中存在无关历史消息而失败

#### Scenario: 任务相关模块运行
- **WHEN** runner 运行会创建异步任务的 source、task 或 sbom case
- **THEN** runner SHALL 执行 RabbitMQ 队列可查询和任务消息脱敏检查

#### Scenario: 全量运行
- **WHEN** runner 执行全量 E2E
- **THEN** runner SHALL 执行所有适用的 post-run assertion

### Requirement: E2E 文档必须说明模块化运行方式
API E2E 文档 SHALL 说明模块化运行命令、case/tag 列表查询方式、适用场景和新增 API 时的推荐验证路径。

#### Scenario: 查看模块化运行文档
- **WHEN** 开发者查看 E2E README 或覆盖矩阵文档
- **THEN** 文档 SHALL 展示 `list`、`--module`、`--case`、`--tag` 和 `--all` 的示例命令
- **AND** 文档 SHALL 说明新增 API 时应优先运行相关模块，必要时再运行全量 E2E

#### Scenario: 新增 E2E case
- **WHEN** 后续 change 新增 E2E case
- **THEN** 文档或任务说明 SHALL 要求该 case 提供稳定 metadata
- **AND** metadata SHALL 至少包含 `id`、`module` 和 `tags`

### Requirement: API E2E 必须覆盖用户邀请和邮件配置
API E2E 测试套件 SHALL 覆盖用户邀请注册、忘记密码、邮箱配置和任务完成邮件推送的端到端行为。

#### Scenario: 覆盖管理员邀请创建用户
- **WHEN** E2E 使用超级管理员创建用户
- **THEN** 测试 SHALL 验证创建请求不提交 `initialPassword`
- **AND** 测试 SHALL 验证数据库创建用户和邀请 token hash
- **AND** 测试 SHALL 验证邮件发送请求被触发或测试邮件收件箱收到邀请邮件

#### Scenario: 覆盖接受邀请
- **WHEN** E2E 使用邀请 token 调用邀请接受 API
- **THEN** 测试 SHALL 验证用户可以设置密码并登录
- **AND** 测试 SHALL 验证 token 被消费后不能再次使用

#### Scenario: 覆盖管理员直接重置密码
- **WHEN** E2E 使用超级管理员调用重置密码 API
- **THEN** 测试 SHALL 验证管理员可直接设置新密码
- **AND** 测试 SHALL 验证 `mustChangePassword` 可按请求设置
- **AND** 测试 SHALL 验证该流程不发送重置密码邮件

#### Scenario: 覆盖忘记密码流程
- **WHEN** E2E 调用忘记密码 request 和 confirm API
- **THEN** 测试 SHALL 验证 request 响应不暴露账号是否存在
- **AND** 测试 SHALL 验证有效 token 可设置新密码
- **AND** 测试 SHALL 验证过期、已消费和错误类型 token 不能修改密码

#### Scenario: 覆盖邮箱配置
- **WHEN** E2E 使用超级管理员保存邮箱服务器配置
- **THEN** 测试 SHALL 验证配置写入 `system_configs`
- **AND** 测试 SHALL 验证 secret 配置不会明文返回
- **AND** 测试 SHALL 验证测试发送 API 返回可审计结果

#### Scenario: 覆盖任务完成邮件推送
- **WHEN** E2E 创建任务并使任务进入终态
- **THEN** 测试 SHALL 验证邮件通知开启时触发任务完成邮件
- **AND** 测试 SHALL 验证邮件内容不包含明文凭据、完整日志或服务器真实敏感路径

#### Scenario: 覆盖异常和 edge case
- **WHEN** E2E 验证用户邀请和邮件配置边界
- **THEN** 测试 SHALL 覆盖重复 username、重复 email、缺失 email、无效邮箱格式、无权限访问管理员邮件配置、SMTP 配置不完整、邮件发送失败、token 过期、token 重放和 token 类型不匹配

### Requirement: API E2E 必须覆盖用户 action token 清理边界
API E2E 测试套件 SHALL 覆盖用户 action token 清理任务的关键边界，确保清理不会影响有效邀请和忘记密码流程。

#### Scenario: 覆盖清理不影响有效邀请
- **WHEN** E2E 创建未过期且未消费的邀请 token 后触发或等待清理任务
- **THEN** 测试 SHALL 验证该邀请 token 仍可用于接受邀请

#### Scenario: 覆盖过期或已消费历史 token 清理
- **WHEN** E2E 或维护脚本准备 30 天前已过期或已消费 token 并执行清理
- **THEN** 测试 SHALL 验证这些 token 被删除
- **AND** 测试 SHALL 验证 30 天内的已过期或已消费 token 被保留

#### Scenario: 覆盖清理任务失败不影响接口校验
- **WHEN** 清理任务未执行或失败
- **THEN** E2E SHALL 验证过期 token 和已消费 token 仍被 API 拒绝

### Requirement: API E2E 必须覆盖运行中任务取消
API E2E 测试套件 SHALL 覆盖运行中任务取消的正常流程、异常流程和 edge case，并 SHALL 验证任务事件、SSE 和清理状态。

#### Scenario: 正常取消运行中任务
- **WHEN** E2E 创建可控运行中任务并调用 `POST /api/tasks/{taskId}/cancel`
- **THEN** API SHALL 返回 `CANCELLED` 任务状态
- **AND** E2E SHALL 验证任务详情、项目任务列表和 SSE 均能观察到 `task.cancelled`
- **AND** E2E SHALL 验证对应 runtime handle 进入取消清理终态或可解释的清理异常状态

#### Scenario: 无权限取消运行中任务
- **WHEN** E2E 使用无项目权限用户取消另一个项目的运行中任务
- **THEN** API SHALL 返回安全错误
- **AND** E2E SHALL 验证任务状态未被改变
- **AND** E2E SHALL 验证未产生取消事件或取消清理消息

#### Scenario: 重复取消任务
- **WHEN** E2E 对同一运行中任务连续调用取消接口
- **THEN** API SHALL 幂等返回 `CANCELLED` 或当前终态
- **AND** E2E SHALL 验证不会重复产生不可解释的取消清理副作用

#### Scenario: 取消清理失败可观测
- **WHEN** E2E 通过 test-support 制造取消清理失败
- **THEN** 任务业务状态 SHALL 保持 `CANCELLED`
- **AND** runtime handle SHALL 记录失败状态和安全错误摘要
- **AND** 取消消息 SHALL 按配置进入重试或 DLQ

#### Scenario: 目标 worker 取消队列不存在
- **WHEN** E2E 通过 test-support 制造 active runtime handle 指向不存在的 `workerInstanceId`
- **THEN** 取消 API SHALL 仍将任务业务状态更新为 `CANCELLED`
- **AND** RabbitMQ unroutable publisher return SHALL 被捕获
- **AND** runtime handle SHALL 记录路由不可达、worker 不存在或等效清理异常状态

### Requirement: API E2E 可以使用 test-support API 稳定触发内部机制
API E2E runner SHALL 在显式配置 test-support API 时，使用该 API 准备 fixture、触发内部机制、查询副作用和清理测试数据。

#### Scenario: test-support 可用
- **WHEN** E2E runner 配置了 test-support base URL 和 token
- **THEN** runner SHALL 能调用 `/api/test-support/**` 完成 fixture 准备、定时任务触发、SSE 触发和 outbox 查询

#### Scenario: test-support 不可用
- **WHEN** E2E runner 未配置 test-support token 或后端未以 test-support 构建启动
- **THEN** runner SHALL 对依赖 test-support 的用例给出明确错误或跳过原因
- **AND** runner MUST NOT 静默假装该用例通过

### Requirement: API E2E 必须保留关键真实链路验证
API E2E 使用 test-support API 时，仍 SHALL 保留关键真实 API 和真实副作用验证。

#### Scenario: 真实认证链路
- **WHEN** E2E 覆盖认证模块
- **THEN** 测试 SHALL 继续覆盖 CSRF、登录、当前用户、修改密码和退出登录的真实 API 调用

#### Scenario: 真实任务链路
- **WHEN** E2E 覆盖任务创建模块
- **THEN** 测试 SHALL 继续验证真实任务创建、任务事件、数据库状态和队列副作用
- **AND** test-support 只 MAY 用于缩短等待、触发 repair 或制造边界事件

### Requirement: API E2E 必须验证 test-support 安全边界
API E2E SHALL 覆盖 test-support API 的 token 校验和生产构建隔离边界。

#### Scenario: token 错误
- **WHEN** E2E 使用缺失或错误的 test-support token 调用测试辅助 API
- **THEN** 后端 SHALL 拒绝请求

#### Scenario: 默认生产构建
- **WHEN** E2E 或构建验证使用默认生产 jar 启动后端
- **THEN** `/api/test-support/**` SHALL 不可访问

### Requirement: API E2E 必须覆盖构建验证模块
API E2E SHALL 提供可单独运行的构建验证模块，并覆盖正常流程、异常流程和 edge case。

#### Scenario: 构建验证正常流程
- **WHEN** E2E 运行构建验证模块
- **THEN** 测试 SHALL 创建项目、源码版本、环境和成功源码部署记录
- **AND** 测试 SHALL 通过 API 创建构建验证任务
- **AND** 测试 SHALL 等待任务完成并校验 `build_runs.status`、退出码、任务详情和日志可查询

#### Scenario: 构建验证异常流程
- **WHEN** E2E 使用失败源码部署、跨项目源码部署或无权限会话创建构建验证
- **THEN** 后端 SHALL 返回明确错误
- **AND** 测试 SHALL 校验没有创建构建任务、构建运行或队列消息

#### Scenario: 构建验证 edge case
- **WHEN** E2E 提交空脚本、重复源码部署 ID、非法分页排序参数或非零退出码脚本
- **THEN** 后端 SHALL 返回参数错误或稳定失败状态
- **AND** 测试 SHALL 校验错误响应和数据库状态符合预期

#### Scenario: 构建验证清理
- **WHEN** E2E 构建验证模块结束
- **THEN** 清理脚本 SHALL 删除测试创建的项目、任务、构建运行、脚本 payload、日志、源码部署记录和相关运行目录

### Requirement: API E2E 清理可以委托 test-support runtime 清理
API E2E runner MAY 使用 test-support runtime 清理接口清理本次 run id 关联的数据，但 SHALL 保留失败报告。

#### Scenario: 使用 run id 清理
- **WHEN** E2E 运行结束并配置了 test-support API
- **THEN** runner MAY 调用 `POST /api/test-support/runtime:cleanup` 清理本次 run id 的测试数据

#### Scenario: 清理失败
- **WHEN** test-support runtime 清理返回失败
- **THEN** runner SHALL 返回失败状态或明确输出未清理资源

### Requirement: E2E 必须覆盖 CUSTOM_BASH 脚本执行
API E2E 测试 SHALL 覆盖 `CUSTOM_BASH` 从创建、执行、日志输出、执行记录恢复到清理的端到端流程。

#### Scenario: CUSTOM_BASH 正常执行
- **WHEN** E2E 创建项目、SSH 环境并提交一个成功退出的 `CUSTOM_BASH` 脚本
- **THEN** 后端 SHALL 创建 `ENV_RUN_SCRIPT` 任务
- **AND** worker SHALL 执行脚本并将任务推进到 `SUCCEEDED`
- **AND** E2E SHALL 校验 `tasks`、`tool_runs`、`task_logs` 和 `task_log_events` 均产生对应记录
- **AND** E2E SHALL 校验 API 响应、任务输入、任务事件、审计日志和日志摘要不包含脚本正文中的敏感测试值

#### Scenario: CUSTOM_BASH 失败执行
- **WHEN** E2E 提交一个返回非 0 退出码的 `CUSTOM_BASH` 脚本
- **THEN** worker SHALL 将任务推进到 `FAILED`
- **AND** `tool_runs.exit_code` SHALL 保存非 0 退出码
- **AND** E2E SHALL 能从日志 API 和任务级日志 SSE 读取失败前产生的 stdout/stderr

#### Scenario: CUSTOM_BASH 参数校验
- **WHEN** E2E 提交空脚本、超大脚本或非法脚本类型
- **THEN** API SHALL 返回统一校验错误
- **AND** E2E SHALL 校验未创建任务、未保存脚本正文且未投递队列消息

### Requirement: E2E 必须覆盖任务级日志 SSE
API E2E 测试 SHALL 覆盖任务级日志 SSE 的历史补发、实时推送、断线恢复和权限边界。

#### Scenario: 首次连接补发历史日志
- **WHEN** 脚本任务已经产生若干日志事件
- **THEN** E2E 调用 `GET /api/tasks/{taskId}/log-events` 且不提交 `Last-Event-ID`
- **AND** SSE SHALL 先返回已有日志事件
- **AND** 返回事件 SHALL 按 `task_log_events.id` 升序排列

#### Scenario: 断线后继续恢复日志
- **WHEN** E2E 记录最后收到的任务级日志 SSE ID 后重新连接
- **THEN** 后端 SHALL 只补发同一任务中 ID 更大的日志事件
- **AND** E2E SHALL 校验不会收到其他任务或其他项目的日志事件

#### Scenario: 运行中继续推送日志
- **WHEN** 脚本任务仍在运行且持续输出日志
- **THEN** 任务级日志 SSE SHALL 在历史补发后继续推送新增日志事件
- **AND** 页面关闭或 SSE 断开 MUST NOT 取消后端任务

#### Scenario: 无权限订阅任务级日志 SSE
- **WHEN** 普通用户尝试订阅其他用户项目任务的日志 SSE
- **THEN** API SHALL 返回安全错误
- **AND** 后端 MUST NOT 补发任何日志事件

### Requirement: E2E 必须覆盖脚本执行记录恢复
API E2E 测试 SHALL 覆盖脚本执行记录列表、详情、状态映射和恢复查看。

#### Scenario: 查询脚本执行记录列表
- **WHEN** E2E 创建并执行脚本任务
- **THEN** `GET /api/projects/{projectId}/script-executions` SHALL 返回该执行记录
- **AND** 执行记录 SHALL 包含任务 ID、环境摘要、脚本 SHA256、脚本长度、状态、退出码和时间字段
- **AND** 响应 MUST NOT 包含脚本正文或服务器真实路径

#### Scenario: 查询运行中执行记录
- **WHEN** 脚本任务仍在 `PENDING`、`QUEUED` 或 `RUNNING`
- **THEN** 脚本执行记录状态 SHALL 展示为 `RUNNING`
- **AND** E2E SHALL 能通过任务级日志 SSE 恢复历史日志并继续接收新增日志

#### Scenario: 查询终态执行记录
- **WHEN** 脚本任务已经进入 `SUCCEEDED` 或 `FAILED`
- **THEN** 脚本执行记录 SHALL 展示为 `SUCCEEDED` 或 `ERROR`
- **AND** E2E SHALL 能通过执行记录详情和日志 API 查看完整结果摘要

### Requirement: API E2E 必须覆盖 KB 扫描验证和清理
API E2E 测试套件 SHALL 覆盖 KB 扫描相关的端到端验证入口、真实副作用检查、finding 入库检查和测试数据清理。

#### Scenario: 覆盖 KB 扫描主链路
- **WHEN** 运行 KB API E2E 用例且基础设施、后端服务、worker 和 KB Scanner 可用
- **THEN** 测试 SHALL 创建或复用测试项目和源码版本
- **AND** 测试 SHALL 创建 `KB_SCAN` 任务并等待任务终态
- **AND** 测试 SHALL 校验 `kb_scan_runs`、`findings`、KB artifact metadata、`tasks`、`task_events`、`task_log_events` 和 `tool_runs` 的真实副作用

#### Scenario: 覆盖 KB API 查询
- **WHEN** KB API E2E 用例完成一次成功扫描
- **THEN** 测试 SHALL 调用 `GET /api/projects/{projectId}/kb-scans`
- **AND** 测试 SHALL 调用 `GET /api/kb-scans/{scanId}`
- **AND** 测试 SHALL 调用 `GET /api/kb-scans/{scanId}/findings`
- **AND** 测试 SHALL 调用 `GET /api/findings/{findingId}`
- **AND** 测试 SHALL 校验 API 响应不包含服务器真实路径或完整 scanner output 原文

#### Scenario: 覆盖 KB 扫描异常流程
- **WHEN** 运行 KB API E2E 异常用例
- **THEN** 测试 SHALL 覆盖源码版本不存在、源码版本不属于项目、无 active source、无项目权限和 scanner 失败
- **AND** 测试 SHALL 验证失败不会写入成功态 findings 或成功态 artifact

#### Scenario: 覆盖 KB 查询分页过滤排序
- **WHEN** KB API E2E 创建包含多条 finding 的扫描结果
- **THEN** 测试 SHALL 验证 finding 列表支持分页
- **AND** 测试 SHALL 验证 severity、ruleId、filePath 或 keyword 过滤
- **AND** 测试 SHALL 验证合法排序和非法排序字段拒绝

#### Scenario: 清理 KB E2E 数据
- **WHEN** KB API E2E 运行成功或失败
- **THEN** runner SHALL 清理本次 run id 创建的项目、源码版本、扫描运行、findings、artifact metadata、任务、任务事件、日志和本地测试输出
- **AND** 清理 MUST NOT 删除用户手工创建的真实项目或真实扫描结果

### Requirement: E2E runner 必须支持 KB 模块
API E2E runner SHALL 将 KB 扫描用例作为独立 `kb` 模块运行。

#### Scenario: 按 KB 模块运行
- **WHEN** 开发者执行 `node e2e/runner.js run --module=kb`
- **THEN** runner SHALL 只运行 KB 扫描相关 E2E case
- **AND** runner SHALL 完成公共 setup、管理员登录、CSRF 初始化、基础设施检查和清理
- **AND** runner SHALL NOT 运行 auth、project、task、sbom 等无关模块 case

#### Scenario: KB 模块 post-run assertion
- **WHEN** runner 运行 `kb` 模块
- **THEN** runner SHALL 执行 RabbitMQ 队列可查询、任务消息脱敏、任务事件项目隔离和 KB 结果入库检查
- **AND** runner SHALL NOT 因无关模块的历史数据失败

### Requirement: E2E 测试必须覆盖对象存储制品能力
API E2E 测试套件 SHALL 覆盖对象存储连通性、后端输出制品写入、业务下载和清理行为。

#### Scenario: 验证对象存储连通性
- **WHEN** E2E check 运行且对象存储配置启用
- **THEN** 测试 SHALL 验证后端或测试辅助能力可以访问 MinIO
- **AND** 测试 SHALL 验证目标 bucket 可用

#### Scenario: 验证 KB artifact 对象存储
- **WHEN** E2E 运行 KB 扫描并产生 artifact
- **THEN** 测试 SHALL 校验输出制品元数据已写入
- **AND** 测试 SHALL 通过 KB 业务下载接口读取对象内容
- **AND** 响应 MUST NOT 暴露 bucket、object key 或服务器真实路径

#### Scenario: 验证 SBOM artifact 对象存储
- **WHEN** E2E 运行 SBOM 分析并产生 artifact
- **THEN** 测试 SHALL 校验输出制品元数据已写入
- **AND** 测试 SHALL 通过 SBOM 业务接口读取 artifact 内容
- **AND** 响应 MUST NOT 暴露 bucket、object key 或服务器真实路径

#### Scenario: 清理对象存储测试数据
- **WHEN** E2E 清理本次 run id 创建的数据
- **THEN** 清理流程 SHALL 删除对应输出制品元数据
- **AND** 清理流程 SHALL 尽力删除对象存储中的测试对象

### Requirement: E2E 测试必须覆盖迁移报告 API
API E2E 测试套件 SHALL 覆盖迁移报告 API 的正常流程、异常流程和 edge case。测试 SHALL 使用节点内确认后的迁移输入 reference，并 SHALL 验证零 confirmed 输入也能生成全零报告。

#### Scenario: 正常生成迁移评估报告
- **WHEN** E2E 创建项目、创建源码版本、准备 KB 或依赖分析来源结果，并通过节点内确认规则产生至少一条 `CONFIRMED` reference
- **THEN** E2E SHALL 调用报告创建 API
- **AND** E2E SHALL 等待报告任务成功
- **AND** E2E SHALL 校验报告详情、报告输入快照、HTML 下载和 JSON 下载均可用
- **AND** E2E SHALL 校验报告输出制品已写入对象存储元数据
- **AND** API 响应 MUST NOT 暴露 bucket、object key 或服务器真实路径

#### Scenario: 未确认输入生成全零报告
- **WHEN** E2E 在有效源码版本下不存在迁移输入，或只存在 `CANDIDATE`、`EXCLUDED` 迁移输入
- **THEN** 报告 readiness SHALL 允许生成报告
- **AND** 报告生成任务 SHALL 成功
- **AND** 报告输入数量、高风险数量和预计工作量 SHALL 为 0
- **AND** HTML 与 JSON 报告制品 SHALL 可下载

#### Scenario: 报告快照不可变
- **WHEN** E2E 成功生成报告后修改原迁移输入状态或备注
- **THEN** 后续查询报告输入快照和下载 JSON 报告 SHALL 保持生成时内容不变

#### Scenario: 越权访问报告失败
- **WHEN** E2E 使用普通用户访问其他用户项目的报告详情、输入快照或下载接口
- **THEN** 后端 SHALL 拒绝访问

#### Scenario: 非法下载格式失败
- **WHEN** E2E 调用报告下载接口并提交不支持的 `format`
- **THEN** 后端 SHALL 返回统一业务错误

### Requirement: E2E 测试必须覆盖节点内迁移输入确认
API E2E 测试套件 SHALL 覆盖 KB 和依赖分析节点内确认、撤回和默认风险规则。

#### Scenario: 默认确认高中风险和说明类结果
- **WHEN** E2E 准备 `CRITICAL`、`HIGH`、`MEDIUM`、`INFO` 或 `COMMENT` 来源结果
- **THEN** 对应 migration input reference SHALL 默认为 `CONFIRMED`

#### Scenario: 默认低风险候选
- **WHEN** E2E 准备 `LOW` 来源结果
- **THEN** 对应 migration input reference SHALL 默认为 `CANDIDATE`
- **AND** 报告生成 MUST NOT 默认使用该结果

#### Scenario: 人工加入低风险
- **WHEN** E2E 将 `LOW` reference 更新为 `CONFIRMED`
- **THEN** 报告生成 SHALL 可以使用该结果

#### Scenario: 人工撤回默认确认结果
- **WHEN** E2E 将默认 `CONFIRMED` reference 更新为 `EXCLUDED`
- **THEN** 报告生成 MUST NOT 使用该结果

#### Scenario: 新流程不导入 SBOM
- **WHEN** E2E 尝试在新流程中导入 `SBOM_RESULT`
- **THEN** API SHALL 返回 deprecated 或拒绝响应
- **AND** 后端 MUST NOT 创建新的 `SBOM_RESULT` migration input reference

### Requirement: E2E 必须覆盖项目归档节点
API E2E 测试套件 SHALL 提供独立归档模块，覆盖归档当前状态、源码版本隔离、归档详情和归档包下载。

#### Scenario: 归档已有候选内容
- **WHEN** E2E 创建项目、激活源码版本并准备可归档候选
- **THEN** 测试 SHALL 调用归档当前状态 API
- **AND** 测试 SHALL 等待归档任务成功
- **AND** 测试 SHALL 验证归档 overview、列表和详情包含本次候选内容

#### Scenario: 下载归档包
- **WHEN** 归档任务成功
- **THEN** E2E SHALL 调用归档包下载 API
- **AND** 测试 SHALL 验证压缩包包含 `manifest.json`、`summary.json` 和候选引用的报告文件
- **AND** 测试 SHALL 验证响应和归档 manifest 不暴露服务器真实路径或对象存储内部 key

#### Scenario: 新源码版本隔离
- **WHEN** E2E 激活第二个源码版本但不为该版本登记候选
- **THEN** 再次归档当前状态 MUST NOT 包含第一个源码版本的候选内容
- **AND** 测试 SHALL 验证旧归档详情仍能查看第一个源码版本的归档项

#### Scenario: 越权访问归档
- **WHEN** 普通用户访问其他项目的归档 overview、列表、详情、单项内容或下载接口
- **THEN** E2E SHALL 验证后端返回访问拒绝错误
- **AND** 响应 MUST NOT 泄漏归档或项目是否存在

### Requirement: E2E 必须覆盖 Agent Runtime 选择
API E2E 测试套件 SHALL 覆盖 agent runtime 展示、阶段绑定、模型测试和测试比较运行时解析。

#### Scenario: 查询 agent runtime 列表
- **WHEN** E2E 使用超级管理员调用 agent runtime 列表 API
- **THEN** 响应 SHALL 至少包含 `CODEX`、`DEEPSEEK_HARNESS` 和 `OPENCODE`
- **AND** 响应 MUST NOT 包含 API key、授权头、完整 prompt 或服务器真实敏感路径

#### Scenario: 保存 TEST_LOG_COMPARE 模型和 agent 绑定
- **WHEN** E2E 创建或使用一个模型 profile 并选择一个已启用 agent runtime
- **THEN** E2E SHALL 调用阶段绑定 API 保存 `TEST_LOG_COMPARE` 绑定
- **AND** 再次查询 SHALL 返回同一个模型 profile 和 agent runtime

#### Scenario: 模型测试指定 agent runtime
- **WHEN** E2E 调用模型 profile 测试 API 并指定 agent runtime
- **THEN** 响应 SHALL 返回 agent 类型、agent runtime ID、分项 probe 和聚合兼容性状态
- **AND** 响应 MUST NOT 泄漏 API key 或完整命令

#### Scenario: 测试比较使用阶段绑定 agent
- **WHEN** E2E 通过 test-support 或完整自动化测试链路触发测试结果比较
- **THEN** 后端 SHALL 使用 `TEST_LOG_COMPARE` 阶段绑定的模型 profile 和 agent runtime
- **AND** 比较详情 SHALL 返回使用的 agent 类型或 runtime 摘要

#### Scenario: Agent runtime 缺失或禁用
- **WHEN** E2E 将 `TEST_LOG_COMPARE` 绑定到不可用 agent runtime 或未完成绑定
- **THEN** 测试比较 SHALL 返回不可用或受控失败状态
- **AND** 自动化测试结果本身 SHALL 仍可查询

### Requirement: API E2E 必须覆盖任务日志内容读取
API E2E 测试套件 SHALL 覆盖完成态任务日志内容读取 API 的正常流程、异常流程和 edge case，并 SHALL 使用按时间正序追加的真实日志文件顺序。

#### Scenario: 默认读取三类日志
- **WHEN** E2E 创建包含 merged/stdout/stderr 日志的任务 fixture 并调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** 响应 SHALL 包含三类日志
- **AND** 每类默认最多返回文件尾部的最新展示页 100 行
- **AND** 每类返回页内部 SHALL 按日志产生时间正序排列

#### Scenario: 单类日志读取
- **WHEN** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 响应 SHALL 只包含 stdout 日志内容
- **AND** 响应 SHALL 不包含 merged 或 stderr 内容

#### Scenario: 多类不同 offset
- **WHEN** E2E 使用不同 offset 请求 merged、stdout 和 stderr
- **THEN** 每类日志 SHALL 从各自文件尾部跳过对应数量的最新行后返回文本片段
- **AND** 每个文本片段 SHALL 保持页内时间正序
- **AND** `hasMore` SHALL 正确表达是否还有更早日志

#### Scenario: 正序追加日志首屏返回最新内容
- **WHEN** E2E 创建文件头为最早日志、文件尾为最新日志的任务日志 fixture
- **AND** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=0&lines=2`
- **THEN** 响应 SHALL 返回文件尾部的最新两行
- **AND** 两行 SHALL 按产生时间正序排列
- **AND** 响应 MUST NOT 返回文件头部的最早两行

#### Scenario: offset 返回更旧内容
- **WHEN** E2E 创建文件头为最早日志、文件尾为最新日志的任务日志 fixture
- **AND** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=2&lines=2`
- **THEN** 响应 SHALL 跳过最新两行并返回其前方更旧的日志
- **AND** 返回页内部 SHALL 保持时间正序
- **AND** `hasMore` SHALL 正确表达是否仍有更旧日志

#### Scenario: 非法参数
- **WHEN** E2E 使用未知日志类型、负数 offset 或超过上限的 lines
- **THEN** API SHALL 返回统一参数校验错误

#### Scenario: 越权读取日志内容
- **WHEN** 普通用户读取其他用户项目任务的日志内容
- **THEN** API SHALL 返回安全错误
- **AND** 响应 MUST NOT 泄漏日志是否存在

#### Scenario: 构建和测试详情暴露日志引用
- **WHEN** E2E 查询构建详情和自动化测试详情
- **THEN** 响应 SHALL 暴露 merged/stdout/stderr 日志引用或明确缺失状态
- **AND** 前端可使用同一个任务日志内容接口读取这些日志内容

### Requirement: API E2E 必须覆盖依赖分析主链路
API E2E 测试套件 SHALL 覆盖构建事实驱动依赖分析的正常流程、异常流程、edge case 和清理。

#### Scenario: 覆盖前置 source-only 构建
- **WHEN** E2E 运行依赖分析模块
- **THEN** 测试 SHALL 创建或复用项目、源码版本、运行双环境和 source-only 构建运行
- **AND** 测试 SHALL 验证构建记录包含 `buildScope=SOURCE_ONLY`

#### Scenario: 覆盖依赖分析任务
- **WHEN** source-only 构建成功
- **THEN** E2E SHALL 调用依赖分析创建 API
- **AND** E2E SHALL 等待 `DEPENDENCY_ANALYSIS` 任务进入终态
- **AND** E2E SHALL 校验依赖分析运行、结果明细、任务事件、日志和 artifact 副作用

#### Scenario: 覆盖依赖分析查询
- **WHEN** 依赖分析成功产生结果
- **THEN** E2E SHALL 查询依赖分析列表、详情、结果列表、结果详情和 artifact 下载
- **AND** E2E SHALL 验证分页、过滤、排序和敏感信息边界

#### Scenario: 覆盖依赖分析异常流程
- **WHEN** 没有成功 source/x86 构建、缺少运行双环境、环境不属于项目或用户无权限
- **THEN** E2E SHALL 验证 API 返回明确错误
- **AND** E2E SHALL 验证不会创建成功态依赖分析结果

#### Scenario: 覆盖迁移输入导入
- **WHEN** 依赖分析结果存在
- **THEN** E2E SHALL 将 `DEPENDENCY_RESULT` 导入迁移输入
- **AND** E2E SHALL 验证重复导入幂等跳过和详情回查 evidence

#### Scenario: SBOM E2E 兼容
- **WHEN** 保留 SBOM E2E 用例
- **THEN** 测试 SHALL 明确标记该覆盖为 deprecated 兼容验证
- **AND** 新依赖分析 E2E MUST NOT 依赖旧 SBOM E2E 先运行

### Requirement: API E2E 必须覆盖依赖分析 provider 版本展示
API E2E 测试套件 SHALL 覆盖构建驱动依赖分析中 provider package/version、detected version、provider version status 和 HTML/JSON 展示字段。

#### Scenario: 正常流程校验 provider 版本字段
- **WHEN** E2E 运行依赖分析模块并产生构建工具、ELF 或 SO 依赖结果
- **THEN** 测试 SHALL 查询依赖分析结果列表和详情
- **AND** 测试 SHALL 校验响应包含源 provider package/version、目标 provider package/version、detected version、provider version status、目标匹配状态和风险等级字段
- **AND** 测试 SHALL 校验 JSON artifact 中包含同一组字段
- **AND** 测试 SHALL 校验 HTML artifact 或真实验证 HTML 展示同一组可审计字段

#### Scenario: 异常流程校验 provider 版本缺失
- **WHEN** E2E 构造或运行源 owner 查询失败、目标 provider 查询失败或版本解析失败的依赖分析场景
- **THEN** 测试 SHALL 验证 API 和 artifact 返回 `UNKNOWN`、warning 或明确空值
- **AND** 测试 SHALL 验证任务不会因为单条 provider 版本缺失而整体失败
- **AND** 测试 SHALL 验证响应中不包含明文凭据、远端真实敏感路径或完整构建日志

#### Scenario: edge case 校验 ELF 和工具版本来源
- **WHEN** E2E 覆盖 ELF/SO、命令行工具、目标软件源可用但未安装、源无 owner package 但有 detected version 的场景
- **THEN** 测试 SHALL 验证 ELF/SO 不依赖默认 `--version` 输出
- **AND** 测试 SHALL 验证工具命令版本只作为 detected version 或 evidence 保存
- **AND** 测试 SHALL 验证风险等级与 `providerVersionStatus` 的映射一致

### Requirement: API E2E 必须覆盖依赖分析前环境刷新
API E2E 测试套件 SHALL 覆盖依赖分析默认刷新环境快照的正常流程、异常流程和 stale snapshot edge case。

#### Scenario: 正常流程验证刷新快照
- **WHEN** E2E 运行依赖分析模块
- **THEN** 测试 SHALL 创建或复用 source/x86 和 target/RISC-V 环境
- **AND** 测试 SHALL 调用依赖分析创建 API
- **AND** 测试 SHALL 验证依赖分析任务执行期间产生新的 source 和 target 环境快照
- **AND** 测试 SHALL 验证依赖分析 artifact 使用的是本次新快照 ID

#### Scenario: stale snapshot 不再被使用
- **WHEN** E2E 准备一个旧 target snapshot，其中某工具被记录为已安装
- **AND** E2E 改变实时 target 环境使该工具不再安装但软件源仍可提供
- **THEN** 重新运行依赖分析后，测试 SHALL 验证该工具不再返回 `TARGET_INSTALLED`
- **AND** 测试 SHALL 验证结果来自本次刷新后的 target snapshot

#### Scenario: 采集失败导致分析失败
- **WHEN** E2E 使 source 或 target 环境采集失败
- **THEN** 依赖分析任务 SHALL 进入 `FAILED`
- **AND** E2E SHALL 验证错误摘要说明是 source 或 target 环境刷新失败
- **AND** E2E SHALL 验证后端没有使用旧 snapshot 生成成功态依赖分析结果

#### Scenario: 敏感信息边界
- **WHEN** E2E 验证环境刷新日志、依赖分析结果和 artifact
- **THEN** 响应和制品 MUST NOT 暴露 SSH 密码、私钥、token、服务器真实敏感路径或完整远端日志

### Requirement: API E2E 必须覆盖 CMake compiler flag probe 解析
API E2E 测试套件 SHALL 覆盖 CMake compiler flag probe 动态映射的正常流程、异常流程和 edge case。

#### Scenario: 覆盖真实 CMake flag probe 映射
- **WHEN** E2E 使用包含 `check_c_compiler_flag` 或 `check_cxx_compiler_flag` 的真实 CMake 项目运行 source-only 构建和依赖分析
- **THEN** 依赖分析结果 SHALL 将命中映射的 define 标记为 `compiler_flag_probe`
- **AND** 结果 evidence SHALL 包含真实 compiler flag 和 CMake 来源文件

#### Scenario: 覆盖多层级 CMake 文件
- **WHEN** E2E 或 fixture 项目的 compiler flag 检测调用位于子目录 `CMakeLists.txt` 或 `cmake/*.cmake`
- **THEN** 后端 SHALL 能采集到对应映射
- **AND** 依赖分析 SHALL 正确解释后续 compile command 中的 define

#### Scenario: 覆盖前缀误判防护
- **WHEN** 测试项目定义了以 `FLAG_SUPPORTED_` 开头但没有 CMake 检测映射的普通宏
- **THEN** 依赖分析 MUST NOT 将其判定为 `compiler_flag_probe`
- **AND** 该结果 SHALL 按项目/构建自定义宏处理

#### Scenario: 覆盖冲突映射
- **WHEN** 测试 fixture 中同一 CMake 变量映射到多个不同 compiler flag
- **THEN** 依赖分析 SHALL 将对应结果标记为需要人工确认
- **AND** evidence SHALL 保存冲突来源

### Requirement: API E2E 必须覆盖 ELF/SO provider package 版本匹配
API E2E 依赖分析模块 SHALL 覆盖 ELF/SO 到源环境 provider package、目标环境 provider package 和版本关系的端到端验证。

#### Scenario: 覆盖 provider package 正常匹配
- **WHEN** E2E 使用包含 ELF/SO 链接依赖的真实 C/C++ 项目完成 source-only 构建并创建依赖分析
- **THEN** 测试 SHALL 等待依赖分析任务成功
- **AND** 测试 SHALL 查询依赖分析结果列表和详情
- **AND** 至少一条 ELF/SO 相关结果 SHALL 包含 source owner package、source owner version、target provider package、target provider version、version relation 和 risk mapping evidence

#### Scenario: 覆盖目标版本关系风险映射
- **WHEN** E2E 或 test-support fixture 准备五类 ELF/SO provider 匹配场景
- **THEN** 测试 SHALL 验证 `SAME_MAJOR` 映射为 `INFO`
- **AND** 测试 SHALL 验证 `TARGET_NEWER` 映射为 `LOW`
- **AND** 测试 SHALL 验证 `TARGET_OLDER` 映射为 `HIGH`
- **AND** 测试 SHALL 验证 `TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED` 映射为 `MEDIUM`
- **AND** 测试 SHALL 验证 `NO_TARGET_VERSION_FOUND` 映射为 `CRITICAL`

#### Scenario: 覆盖 flag 和宏不进入依赖结果
- **WHEN** E2E 使用 CMake 项目产生 `compile_commands.json`、CMake compiler flag probe 宏和项目自定义宏
- **THEN** 依赖分析结果列表 MUST NOT 包含 `compile_database_define`、`strace_execve_define`、`compiler_flag_probe`、`compile-db` 或 `build-ninja` 类型结果
- **AND** 下载的 JSON 和 HTML 制品 MUST NOT 把这些内容展示为依赖结果项

#### Scenario: 覆盖 provider 结果去重聚合
- **WHEN** 同一个 source owner package 通过多个 ELF/SO 文件命中同一个 target provider package 和版本关系
- **THEN** 依赖分析结果列表 SHALL 只展示聚合后的 provider package 结果
- **AND** 单条结果详情 SHALL 保留所有参与聚合的源路径或 SONAME evidence

#### Scenario: 覆盖迁移输入导入展示
- **WHEN** E2E 将 ELF/SO provider package 依赖结果导入迁移输入
- **THEN** 迁移输入 SHALL 使用 `sourceType=DEPENDENCY_RESULT`
- **AND** `detectedLevel` SHALL 使用 `riskLevel + "/" + versionRelation`
- **AND** `locationLabel` SHALL 优先使用 `package:<name@version>`，源无 owner 时使用 `lib:<soname-or-path>`

### Requirement: E2E 必须覆盖评估报告 readiness 和输入预览
API E2E 测试套件 SHALL 覆盖迁移输入合并节点移除后的评估报告页 readiness、输入预览、生成报告和历史快照行为，并 SHALL 将 confirmed 输入数量作为统计事实而非生成门禁。

#### Scenario: readiness 展示可生成状态
- **WHEN** E2E 创建项目、激活源码版本并准备至少一条 `CONFIRMED` migration input reference
- **THEN** E2E SHALL 调用评估报告 readiness API
- **AND** 响应 SHALL 返回 `canGenerate=true`
- **AND** 响应 SHALL 返回 confirmed 输入数量、来源统计和当前源码版本摘要

#### Scenario: readiness 展示零 confirmed 输入
- **WHEN** E2E 创建源码版本但不存在 reference，或只准备 `CANDIDATE`、`EXCLUDED` reference
- **THEN** E2E SHALL 调用评估报告 readiness API
- **AND** 响应 SHALL 返回 `canGenerate=true`
- **AND** confirmed 输入数量 SHALL 为 0
- **AND** blockers MUST NOT 包含没有 confirmed 输入的错误码

#### Scenario: readiness 提示低风险候选
- **WHEN** E2E 准备 `LOW` 风险 dependency 或 KB 结果并保持其 reference 为 `CANDIDATE`
- **THEN** readiness SHALL 返回 LOW candidate 数量
- **AND** warnings SHALL 提示低风险候选未进入报告

#### Scenario: 输入预览分页过滤排序
- **WHEN** E2E 调用评估报告输入预览 API
- **THEN** 响应 SHALL 使用分页格式
- **AND** E2E SHALL 校验按 `sourceType`、`status`、`riskLevel` 和关键字过滤有效
- **AND** E2E SHALL 校验非法排序字段返回统一业务错误

#### Scenario: 人工加入和撤回影响 readiness
- **WHEN** E2E 将 LOW candidate 更新为 `CONFIRMED`
- **THEN** readiness 的 confirmed 数量 SHALL 增加
- **AND** 报告生成 SHALL 使用该输入
- **WHEN** E2E 将默认 confirmed 输入更新为 `EXCLUDED`
- **THEN** readiness 的 confirmed 数量 SHALL 减少
- **AND** 后续报告生成 MUST NOT 使用该输入

#### Scenario: 报告详情区分快照和当前输入状态
- **WHEN** E2E 成功生成报告后修改同源码版本下 migration input reference 的状态或备注
- **THEN** 报告输入快照和 JSON 下载 SHALL 保持生成时内容
- **AND** 报告详情的当前输入摘要 SHALL 反映修改后的状态

### Requirement: E2E 必须覆盖 KB 自动复用 compile database
API E2E 测试套件 SHALL 覆盖 source/x86 构建生成 compile database 后，KB 扫描自动复用该构建上下文的端到端行为。

#### Scenario: 成功复用 compile database
- **WHEN** E2E 创建项目、上传或同步源码、部署 source 环境并运行 source-only 构建
- **AND** 构建在远端工作目录生成合法 `compile_commands.json`
- **THEN** E2E SHALL 等待构建成功
- **AND** E2E SHALL 创建 KB 扫描且不提交 compile database 参数
- **AND** E2E SHALL 校验 KB 扫描成功
- **AND** E2E SHALL 校验 KB scan summary 中 `compileCommands.mode=USED`

#### Scenario: 没有 compile database 时降级
- **WHEN** E2E 运行构建但未生成 `compile_commands.json`
- **THEN** 后续 KB 扫描 SHALL 成功或按 scanner 结果进入终态
- **AND** E2E SHALL 校验 KB scan summary 中 `compileCommands.mode=NOT_AVAILABLE` 或等效降级状态
- **AND** E2E SHALL 校验任务没有因为缺少 compile database 失败

#### Scenario: compile database artifact 异常
- **WHEN** E2E 或测试支持能力制造 compile database artifact 缺失、不可下载或内容非法
- **THEN** KB 扫描 SHALL 降级为源码上下文扫描
- **AND** summary SHALL 记录 `FALLBACK` 和安全原因码
- **AND** API 响应 MUST NOT 暴露对象存储 key、服务器真实路径或远端路径

#### Scenario: 清理测试数据
- **WHEN** compile database 复用 E2E 成功或失败
- **THEN** runner SHALL 清理本次 run id 创建的项目、源码版本、部署运行、构建运行、KB scan、findings、tasks、stored artifacts 和对象存储测试对象

### Requirement: E2E 必须覆盖 compile database 派生 KB finding
API E2E 测试套件 SHALL 覆盖 KB 扫描从 `compile_commands.json` 派生 finding 的正常流程、异常流程和 edge case。

#### Scenario: 正常流程生成 compile command finding
- **WHEN** E2E 创建项目、准备源码版本并完成 source/x86 构建
- **AND** 构建产物中保存的 compile database 包含明确 x86/SIMD 编译参数
- **AND** E2E 创建 KB 扫描且不手动提交 compile database 参数
- **THEN** KB 扫描 SHALL 成功或按 scanner 结果进入终态
- **AND** E2E SHALL 校验 scan summary 中 `compileCommands.mode=USED`
- **AND** E2E SHALL 校验 findings 列表或详情中存在来源为 compile command 的 finding

#### Scenario: 源码无文本风险但编译命令有风险
- **WHEN** E2E fixture 的源码正文不包含 x86/SIMD 风险文本
- **AND** compile database 中包含 `-mavx2`、`-msse`、`-march=x86-64` 或等效参数
- **THEN** KB 扫描 SHALL 生成 compile command 派生 finding
- **AND** finding evidence SHALL 包含命中 token、token 类型、源码相对路径和 compile command 索引

#### Scenario: compile database 不减少既有源码 finding
- **WHEN** E2E 对同一源码版本分别运行不带 compile database 和带 compile database 的 KB 扫描
- **THEN** 带 compile database 的扫描 MUST NOT 隐藏不带 compile database 时已经产生的源码 finding
- **AND** E2E SHALL 校验源码 finding 数量或 fingerprint 集合不被减少

#### Scenario: 非法 compile database 降级
- **WHEN** E2E 或测试支持能力制造缺失、不可下载或非法 JSON 的 compile database artifact
- **THEN** KB 扫描 SHALL 降级为源码上下文扫描或按受控错误进入终态
- **AND** E2E SHALL 校验 API 响应、任务日志和 summary 不暴露对象存储 key、服务器真实路径或远端路径

#### Scenario: 过滤内部构建探测 entry
- **WHEN** E2E fixture 的 compile database 包含 CMake、Meson、Ninja 或编译器内部探测文件 entry
- **AND** 这些 entry 不关联项目源码扫描范围
- **THEN** KB 扫描 MUST NOT 为这些 entry 生成 compile command finding

#### Scenario: 清理 compile command finding 测试数据
- **WHEN** compile command 派生 finding E2E 成功或失败
- **THEN** runner SHALL 清理本次 run id 创建的项目、源码版本、构建运行、KB scan、findings、任务、stored artifacts、对象存储测试对象和 runtime 临时文件

### Requirement: API E2E 必须覆盖依赖自动修复
API E2E 测试套件 SHALL 覆盖依赖自动修复候选项、任务创建、远端安装、修复结果查询、自动重跑依赖分析、异常流程和 edge case。

#### Scenario: 覆盖自动修复正常流程
- **WHEN** E2E 准备一个包含中风险可安装依赖的依赖分析结果
- **THEN** E2E SHALL 调用候选项查询 API
- **AND** E2E SHALL 验证中风险候选项 `defaultSelected=true`
- **AND** E2E SHALL 调用创建自动修复 API
- **AND** E2E SHALL 等待 `DEPENDENCY_AUTO_FIX` 任务进入终态
- **AND** E2E SHALL 验证修复运行、修复条目、任务事件和任务日志副作用

#### Scenario: 覆盖高风险默认不选中
- **WHEN** E2E 准备一个高风险且存在 `sourceProviderPackage` 的依赖分析结果
- **THEN** 候选项查询 SHALL 返回该条目
- **AND** 该条目 SHALL 设置 `defaultSelected=false`
- **AND** E2E SHALL 验证只有显式提交该条目时才会创建安装计划

#### Scenario: 覆盖自动重跑依赖分析
- **WHEN** 自动修复任务至少有一个条目安装成功或已满足
- **THEN** E2E SHALL 验证后端创建新的 `DEPENDENCY_ANALYSIS` 任务
- **AND** E2E SHALL 等待新依赖分析进入终态或验证其任务已被正确入队
- **AND** E2E SHALL 验证自动修复运行记录中保存重跑分析 ID 和任务 ID

#### Scenario: 覆盖越权访问
- **WHEN** 普通用户尝试查询或创建其他项目的依赖自动修复
- **THEN** E2E SHALL 验证 API 返回拒绝访问或资源不存在
- **AND** 后端 MUST NOT 创建修复运行、修复条目或任务

#### Scenario: 覆盖非法候选项
- **WHEN** E2E 使用不可自动修复的 result item 创建修复任务
- **THEN** API SHALL 返回明确业务错误
- **AND** 后端 MUST NOT 执行远端安装命令

#### Scenario: 覆盖安装失败和清理
- **WHEN** E2E 模拟目标包管理器失败、包不存在或不支持的 package manager
- **THEN** 自动修复运行 SHALL 进入失败或部分失败终态
- **AND** 修复条目 SHALL 保存失败状态和脱敏错误摘要
- **AND** E2E 清理脚本 SHALL 清理测试项目、任务、修复运行、修复条目和远端测试包副作用

### Requirement: API E2E 必须覆盖模型连通性和多 Agent Probe 流程
API E2E 测试套件 SHALL 覆盖模型 profile 连通性测试、多 agent runtime 通用兼容性 probe、活跃 run 恢复、异常输入、阶段无关性和无权限访问。

#### Scenario: 连通性测试正常流程
- **WHEN** E2E 使用超级管理员创建带有效连接配置的模型 profile 并调用连通性测试 API
- **THEN** 响应 SHALL 返回连通性状态、脱敏消息、测试时间和耗时
- **AND** 再次查询 profile 列表 SHALL 返回最近连通性摘要
- **AND** 响应 MUST NOT 包含 API key、授权头或完整 prompt

#### Scenario: 多 Agent Probe 正常流程
- **WHEN** E2E 使用超级管理员提交多个已启用 `agentRuntimeIds`
- **THEN** 创建接口 SHALL 返回 `runId` 和初始状态
- **AND** E2E SHALL 通过 run 查询接口获取每个 agent runtime 的通用分项 probe 结果
- **AND** 单个 runtime 的结果 SHALL 包含 agent 类型、runtime ID、Agent 响应、workspace 读取、workspace 写入、聚合兼容性状态和脱敏消息
- **AND** 结果 MUST NOT 包含测试比较、KB AI 扩展或其他业务阶段兼容性字段

#### Scenario: Probe 与阶段绑定无关
- **WHEN** E2E 对同一模型 Profile 与 Agent Runtime 组合执行兼容性 probe
- **AND** 该组合未绑定阶段或绑定到任意一个或多个允许阶段
- **THEN** probe 的检查集合和结果结构 SHALL 保持一致
- **AND** 后端 MUST NOT 因阶段绑定生成阶段专属检查

#### Scenario: 列表返回活跃 Probe Run
- **WHEN** E2E 创建 agent probe run 后立即查询模型 profile 列表或详情
- **THEN** 对应 profile SHALL 返回 `activeAgentProbeRun`
- **AND** `activeAgentProbeRun.runId` SHALL 与创建接口返回的 run ID 一致
- **AND** E2E SHALL 能使用该 run ID 继续查询测试结果

#### Scenario: Agent Probe 异常输入
- **WHEN** E2E 提交空 `agentRuntimeIds`、重复 ID、不存在 ID 或禁用 runtime ID
- **THEN** API SHALL 返回统一参数或业务错误
- **AND** 后端 MUST NOT 创建部分非法 run
- **AND** 响应 MUST NOT 泄漏内部执行细节

#### Scenario: 单 Agent 失败不影响其他结果
- **WHEN** E2E 使用一个可用 runtime 和一个受控失败 runtime 创建 probe run
- **THEN** run SHALL 最终进入 `PARTIAL_SUCCESS` 或等效受控终态
- **AND** 成功 runtime 的结果 SHALL 被保存
- **AND** 失败 runtime 的结果 SHALL 返回脱敏失败原因

#### Scenario: 通用 Workspace 输出异常
- **WHEN** Agent 未创建结果文件、写出无效 JSON、marker 不匹配或 probe 超时
- **THEN** 对应 runtime 的通用兼容性结果 SHALL 为失败
- **AND** 临时 workspace SHALL 被清理
- **AND** 失败消息 MUST NOT 泄漏 API key、完整 prompt 或服务器真实路径

#### Scenario: 普通用户不能测试模型 Profile
- **WHEN** 普通用户调用连通性测试、agent probe run 创建、run 查询或 profile-agent 结果查询 API
- **THEN** 后端 SHALL 返回无权限错误
- **AND** 响应 MUST NOT 泄漏 profile、runtime 或 run 是否存在

#### Scenario: 旧测试接口兼容
- **WHEN** E2E 调用旧 `POST /api/admin/model-profiles/{profileId}:test`
- **THEN** 后端 SHALL 返回兼容旧入口的通用单 Agent 结果或明确迁移提示
- **AND** 响应 MUST NOT 返回阶段兼容性字段
- **AND** 响应 MUST NOT 泄漏 API key、授权头、完整 agent 命令或服务器真实敏感路径

### Requirement: API E2E 必须覆盖测试比较输出文件和无效输出拒绝
API E2E 测试套件 SHALL 覆盖自动化测试比较的成功文件输出、无效 agent 输出拒绝，以及比较失败不影响测试记录的行为。

#### Scenario: 比较 agent 通过结果文件返回统计
- **WHEN** E2E 使用测试辅助能力创建同批次 source 和 target 自动化测试记录
- **AND** 测试比较 agent 写出合法 `comparison-result.json`
- **THEN** 比较运行 SHALL 标记为 `SUCCEEDED`
- **AND** 比较详情 SHALL 返回 source 与 target 的结构化测试统计
- **AND** finding 列表 SHALL 不包含 schema 占位符

#### Scenario: 无效 agent 输出被拒绝
- **WHEN** 测试比较 agent 返回组合枚举、`...` 或 prompt schema 占位符
- **THEN** 比较运行 SHALL 标记为 `FAILED`
- **AND** 错误码 SHALL 表明 agent 输出无效
- **AND** E2E SHALL 验证无效内容没有写入成功比较结果

#### Scenario: x86 成功 target 失败仍可比较
- **WHEN** source 自动化测试记录为 `SUCCEEDED`
- **AND** target 自动化测试记录为 `FAILED`
- **AND** 两侧记录属于同一个 `testBatchId`
- **THEN** 后端 SHALL 自动创建测试比较运行
- **AND** 比较运行 SHALL 基于两侧日志生成结果或明确失败
- **AND** source 和 target 测试记录本身 SHALL 保持原始状态

### Requirement: E2E 必须覆盖日志内容总行数
API E2E 测试套件 SHALL 覆盖 `GET /api/tasks/{taskId}/log-content` 的 `totalLines` 返回行为，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常流程返回准确总行数
- **WHEN** E2E 创建包含 merged、stdout 和 stderr 日志内容的任务 fixture
- **AND** E2E 调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** 响应中每个日志类型 SHALL 包含对应的 `totalLines`
- **AND** `totalLines` SHALL 等于 fixture 中对应日志类型的总逻辑行数

#### Scenario: 单类请求不返回其他类型总行数
- **WHEN** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 响应 SHALL 只包含 stdout 日志对象
- **AND** stdout 日志对象 SHALL 包含 `totalLines`
- **AND** 响应 MUST NOT 包含 merged 或 stderr 的日志对象

#### Scenario: offset 翻页不改变总行数
- **WHEN** E2E 对同一日志类型分别请求 `offset=0` 和更大的 offset
- **THEN** 两次响应的 `totalLines` SHALL 保持一致
- **AND** `returnedLines` MAY 随分页位置变化

#### Scenario: 缺失日志总行数为零
- **WHEN** E2E 创建缺少某类日志文件或日志记录的任务 fixture
- **AND** E2E 请求该日志类型
- **THEN** 响应 SHALL 返回 `totalLines=0`
- **AND** 响应 SHALL 返回空内容、`returnedLines=0` 和 `hasMore=false`

#### Scenario: 非法参数仍返回统一错误
- **WHEN** E2E 调用 `GET /api/tasks/{taskId}/log-content` 并传入非法 `types`、负数 offset 或超过上限的 lines
- **THEN** API SHALL 返回统一参数校验错误
- **AND** 响应 MUST NOT 返回 `totalLines`

### Requirement: API E2E 必须覆盖 worker 观测和并发控制
API E2E 测试套件 SHALL 覆盖 worker 实例注册、心跳、列表查询、详情查询、并发设置和暂停接新任务行为。

#### Scenario: 覆盖 worker 注册和列表
- **WHEN** E2E 以 worker enabled 的后端实例运行
- **THEN** 测试 SHALL 查询 `GET /api/admin/workers`
- **AND** 响应 SHALL 包含当前 worker 实例
- **AND** worker SHALL 包含在线状态、并发限制、实际并发、运行任务数量和最近心跳时间
- **AND** 响应 MUST NOT 包含 `prefetchCount`

#### Scenario: 覆盖 worker 详情和运行任务
- **WHEN** E2E 创建可控长任务并等待其进入 `RUNNING`
- **THEN** 测试 SHALL 查询对应 worker 详情
- **AND** 响应 SHALL 在运行任务列表中包含该任务
- **AND** 任务摘要 SHALL 包含任务 ID、任务类型、项目 ID、状态、进度和 runtime handle ID

#### Scenario: 覆盖并发大于一
- **WHEN** E2E 将 worker `concurrencyLimit` 设置为 `2`
- **AND** E2E 投递两个可控长任务
- **THEN** 两个任务 SHALL 能同时进入 `RUNNING`
- **AND** 任一任务完成或取消 MUST NOT 影响另一个任务继续执行

#### Scenario: 覆盖暂停接新任务
- **WHEN** E2E 将 worker `concurrencyLimit` 设置为 `0`
- **AND** E2E 投递新的异步任务
- **THEN** 该 worker SHALL 不再认领新的任务
- **AND** 已经运行中的任务 SHALL 不因该设置被取消

#### Scenario: 覆盖非法并发和权限
- **WHEN** E2E 使用非法 `concurrencyLimit` 或普通用户访问 worker 管理 API
- **THEN** API SHALL 返回统一错误
- **AND** 后端 MUST NOT 修改 worker 并发限制
- **AND** 响应 MUST NOT 泄露 worker 主机或任务明细

#### Scenario: 覆盖离线 worker 展示
- **WHEN** E2E 使用测试支持能力制造超过心跳阈值的 worker 记录
- **THEN** worker 列表 SHALL 将该实例展示为 `OFFLINE`
- **AND** 该实例 MUST NOT 被展示为可接收新任务

### Requirement: API E2E 必须覆盖极简 RPM 环境的 provider 匹配
API E2E 依赖分析模块 SHALL 覆盖源环境和目标环境为 RPM/DNF 系统时，辅助工具缺失、自动安装尝试、库文件降级采集和 provider package 回退匹配。

#### Scenario: 极简目标环境基础库不误判缺失
- **WHEN** E2E 使用目标环境中安装了 `glibc`、`libgcc` 但缺少 `findutils` 或 `binutils` 的 RPM/DNF 环境运行依赖分析
- **THEN** 后端 SHALL 在分析前尝试补齐目标环境采集工具
- **AND** 依赖分析结果 MUST NOT 将 `libc.so` 或 `libgcc_s.so` 误判为缺失
- **AND** 结果 SHALL 包含目标 provider package/version 或说明可用的回退证据

#### Scenario: 源环境构建观测工具补齐
- **WHEN** E2E 使用源环境运行 source-only 构建和依赖分析
- **THEN** 后端 SHALL 尝试补齐源环境中的 `strace` 和 `bear`
- **AND** 测试 SHALL 验证任务日志或 artifact 中存在 execve 观测、compile database 证据或明确的工具缺失 warning

#### Scenario: 自动安装失败不导致静默误判
- **WHEN** E2E 或测试 fixture 模拟辅助工具安装失败
- **THEN** 环境刷新或依赖分析 SHALL 记录安装失败 warning
- **AND** 后端 SHALL 使用已有包清单和 provider package 回退继续生成可审计结果
- **AND** 结果 MUST NOT 因空的库扫描结果直接断定目标环境完全没有基础库

#### Scenario: 源 owner package 回退匹配
- **WHEN** E2E 构造或运行包含 `-lc` 和 `-lgcc_s` 的真实构建
- **AND** 目标环境缺少对应 `INSTALLED_LIBRARY` 快照组件但存在 `glibc`、`gcc` 或 `libgcc` package 证据
- **THEN** 依赖分析 SHALL 通过源 owner package 或基础库别名命中目标 provider
- **AND** 测试 SHALL 校验风险等级与 provider version status 一致

### Requirement: E2E 必须覆盖构建自动源码部署链路
API E2E SHALL 覆盖前端不调用正式源码部署创建接口时，构建验证能够自动部署源码并继续执行构建。

#### Scenario: 未预部署源码时创建构建
- **WHEN** E2E 创建项目、源码版本和当前双运行环境
- **AND** E2E 不调用正式 `POST /api/projects/{projectId}/source-deployments`
- **AND** E2E 调用 `POST /api/projects/{projectId}/builds`
- **THEN** 后端 SHALL 创建对应 `BUILD_VALIDATION` 任务和构建运行
- **AND** 构建任务 SHALL 在执行构建脚本前自动完成或复用源码部署
- **AND** E2E SHALL 验证构建记录包含 `sourceDeploymentId` 且状态可通过任务/SSE 观察

#### Scenario: 构建复用已有成功部署
- **WHEN** 同源码版本和同环境配置版本已经存在成功源码部署记录
- **AND** E2E 再次调用构建创建 API
- **THEN** 后端 SHALL 复用已有源码部署记录
- **AND** 构建任务 MUST NOT 重复执行源码传输

#### Scenario: 正式源码部署创建接口不再作为业务入口
- **WHEN** E2E 需要直接创建源码部署夹具
- **THEN** E2E SHALL 使用 `test-support` API 或数据库夹具准备数据
- **AND** 正式业务 E2E MUST NOT 依赖 `POST /api/projects/{projectId}/source-deployments` 作为构建前置步骤

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

### Requirement: E2E 必须覆盖阶段 readiness
API E2E 测试套件 SHALL 覆盖项目级阶段 readiness 接口的正常流程、异常流程和边界情况。

#### Scenario: readiness 正常返回前置事实
- **WHEN** E2E 创建项目、源码、运行环境和相关执行记录
- **THEN** E2E SHALL 调用 `GET /api/projects/{projectId}/readiness?stageId=...`
- **AND** 响应 SHALL 包含预期 prerequisite key、status、referenceId 和 reasonCode

#### Scenario: readiness 返回缺失和过期状态
- **WHEN** E2E 构造缺失 active source、缺失环境或旧 Context 记录
- **THEN** readiness SHALL 返回 `MISSING` 或 `STALE`
- **AND** 后端 MUST NOT 将旧 Context 结果判定为满足当前阶段

#### Scenario: readiness 权限隔离
- **WHEN** 普通用户访问其他用户项目的 readiness
- **THEN** E2E SHALL 验证请求失败
- **AND** 响应 MUST NOT 暴露被访问项目的执行记录信息

### Requirement: E2E 必须覆盖领域 latest 外壳
API E2E 测试套件 SHALL 覆盖各领域 latest 接口的统一外壳、无记录、失败记录和旧 Context 行为。

#### Scenario: latest 返回统一外壳
- **WHEN** E2E 调用任一领域 latest 接口
- **THEN** 响应业务数据 SHALL 包含 `context`、`freshness`、`execution` 和 `result`
- **AND** `result` SHALL 保持对应领域结构

#### Scenario: latest 不回退到旧成功记录
- **WHEN** E2E 构造当前 Context 最新失败记录和更早成功记录
- **THEN** latest SHALL 返回失败 execution
- **AND** 后端 MUST NOT 返回更早成功记录作为当前 latest

#### Scenario: latest 无记录成功返回
- **WHEN** E2E 对没有执行记录的领域调用 latest
- **THEN** 响应 SHALL 成功
- **AND** `execution` 和 `result` SHALL 为 `null`

### Requirement: E2E 必须覆盖写接口二次校验
API E2E 测试套件 SHALL 验证执行类写接口不会信任前端先前获得的 readiness 结果。

#### Scenario: Context 改变后写接口拒绝创建任务
- **WHEN** E2E 先查询 readiness 得到满足状态
- **AND** 随后修改源码版本或运行环境版本
- **THEN** 创建依赖分析、自动化测试、报告或归档任务 SHALL 返回 `PREREQUISITE_NOT_SATISFIED`
- **AND** 错误详情 SHALL 包含不满足的 prerequisite 状态

### Requirement: API E2E 必须覆盖 KB Scanner schema v2 链路
API E2E 测试套件 SHALL 覆盖后端调用真实 KB Scanner v2、导入 finding、查询详情和下载 artifact 的完整链路。

#### Scenario: 真实 scanner v2 扫描成功
- **GIVEN** 后端、worker、数据库、Redis、RabbitMQ 和对象存储均已启动
- **WHEN** E2E 通过 API 创建源码、触发 KB 扫描并等待任务完成
- **THEN** 任务 SHALL 成功
- **AND** 保存的 `scan-result.json` SHALL 包含 `schemaVersion: "2.0"`
- **AND** finding 列表 API SHALL 返回扫描出的 v2 finding 摘要
- **AND** finding 详情 API SHALL 返回完整 v2 payload
- **AND** artifact 下载 API SHALL 能下载 JSON 和 HTML 两种格式

#### Scenario: 非 schema v2 结果失败
- **WHEN** E2E 或测试辅助能力注入 schema v1 或无版本扫描结果
- **THEN** 后端 SHALL 拒绝导入
- **AND** 扫描任务 SHALL 进入失败状态
- **AND** 失败原因 SHALL 能通过任务状态或日志 API 查询

#### Scenario: 缺少主位置的 finding
- **WHEN** E2E 或 fixture 导入缺少 `fact.primaryLocation` 的 v2 finding
- **THEN** 后端 SHALL 保留该 finding
- **AND** finding 详情 SHALL 返回完整 evidence
- **AND** 代码上下文查询 SHALL 返回明确的不可定位结果，而不是服务端异常

### Requirement: API E2E 仍必须遵循三类测试策略
新增和修改的 E2E SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: KB schema v2 E2E 分类
- **WHEN** 编写 KB schema v2 相关 E2E
- **THEN** 正常流程 SHALL 覆盖真实扫描与查询
- **AND** 异常流程 SHALL 覆盖版本不兼容或 scanner 依赖缺失
- **AND** edge case SHALL 覆盖缺少位置、空 findings、结构化 diagnostics 等边界数据

### Requirement: Worker E2E 必须覆盖失效实例收敛和清理
API E2E 测试套件 SHALL 在独立 Worker 模块中覆盖失效 Worker 清理的正常流程、异常流程和 edge case，并 SHALL 在完成后清理测试数据。

#### Scenario: 正常收敛并删除失效 Worker
- **WHEN** E2E 创建超过失联确认时间的 Worker、`RUNNING` 任务和活动 runtime handle 并触发清理
- **THEN** runtime handle SHALL 变为 `WORKER_LOST`
- **AND** 任务 SHALL 以 `WORKER_LOST` 错误码进入 `FAILED`
- **AND** 对应失败事件 SHALL 可查询
- **AND** 超过保留期且没有非终态句柄的 Worker SHALL 被删除

#### Scenario: 异常和权限边界
- **WHEN** 未授权调用者尝试访问 Worker 清理测试辅助接口，或生产构建检查接口映射
- **THEN** 后端 SHALL 拒绝未授权访问
- **AND** 生产构建 SHALL 不存在该接口
- **AND** 响应和日志 MUST NOT 泄露任务输入、凭据或服务器真实路径

#### Scenario: 心跳恢复和重复触发边界
- **WHEN** E2E 创建处于短时离线窗口、清理期间恢复心跳、任务已终态或被重复清理的 Worker 数据
- **THEN** 短时离线或已恢复 Worker MUST NOT 被收敛或删除
- **AND** 已终态任务 MUST NOT 被覆盖
- **AND** 重复清理 MUST NOT 产生重复失败事件
- **AND** 测试结束后 SHALL 删除本次创建的 Worker、任务、事件和 runtime handle fixture

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

### Requirement: API E2E 必须验证带诊断包装的 Agent Probe 输出
API E2E 测试套件 SHALL 使用不依赖外部模型服务的可控 Agent fixture，通过真实进程 stdout、stderr 与 workspace 文件验证模型 Profile Agent Probe 不会因 CLI 诊断包装而误判。

#### Scenario: DeepSeek Harness 风格输出
- **WHEN** fixture 在 stdout 返回预期单行 JSON，且 merged output 由运行器附加 `[STDOUT]` 标签
- **THEN** Agent Probe Run API 的对应 runtime 结果 SHALL 为成功
- **AND** 三个通用 probe SHALL 全部通过

#### Scenario: OpenCode 风格输出
- **WHEN** fixture 在 stderr 输出 ANSI 状态日志，在 stdout 返回预期 JSON，并按要求读写 workspace 文件
- **THEN** Agent Probe Run API SHALL 返回 Agent 响应、workspace 读取和 workspace 写入全部成功
- **AND** ANSI 日志与通道标签 MUST NOT 出现在结构化判定中

#### Scenario: 无效输出和脱敏
- **WHEN** fixture 返回零退出码但没有匹配 JSON，或返回包含测试密钥的失败诊断
- **THEN** API SHALL 返回对应 probe 失败及稳定错误码
- **AND** API 响应和持久化消息 MUST NOT 包含完整 API key

### Requirement: E2E 必须覆盖迁移报告模块文件组织能力
独立 API E2E 套件 SHALL 覆盖迁移报告模块、文件、问题类型、finding 和文件联合上下文 API 的正常流程、异常流程与 edge case，并 SHALL 在测试结束后清理创建的数据和对象存储制品。

#### Scenario: 正常流程验证四级组织和联合上下文
- **WHEN** E2E 使用包含多个模块、多个文件和同文件多个 finding 的真实源码 fixture 生成迁移报告
- **THEN** E2E SHALL 依次查询模块、文件、问题类型和 finding API
- **AND** E2E SHALL 校验逐级统计守恒、风险与类型分布、默认行号顺序和分页结果
- **AND** E2E SHALL 校验联合上下文包含首末 finding 的前后最多 20 行及全部高亮
- **AND** E2E SHALL 校验 HTML 与 JSON 报告统计一致

#### Scenario: 正常流程验证依赖独立展示
- **WHEN** 报告同时包含代码 finding 和多个同 provider 软件包的依赖证据
- **THEN** E2E SHALL 校验依赖不出现在代码模块层级
- **AND** E2E SHALL 校验同 provider 的 SO 或 ELF 被聚合为一个依赖主条目

#### Scenario: 异常流程验证权限和路径安全
- **WHEN** 普通用户访问其他项目的报告层级或文件上下文
- **THEN** E2E SHALL 校验请求被拒绝且未泄露报告内容
- **AND** 对路径逃逸或不可读取文件，E2E SHALL 校验返回稳定不可用状态而非服务器绝对路径或底层异常

#### Scenario: Edge case 验证结构化省略和历史版本
- **WHEN** E2E fixture 在同一大文件的远距离行上创建多个 finding，并在报告完成后激活新源码版本
- **THEN** E2E SHALL 校验响应包含可加载的结构化 `OMITTED` block
- **AND** E2E SHALL 校验展开行范围返回真实代码而非省略提示文本
- **AND** E2E SHALL 校验旧报告上下文内容与内容哈希保持不变

#### Scenario: Edge case 验证未定位输入和旧报告兼容
- **WHEN** 报告包含无有效行号的 confirmed finding，且系统中存在没有组织投影的历史报告 fixture
- **THEN** E2E SHALL 校验未定位 finding 仍可查询且不会导致报告失败
- **AND** E2E SHALL 校验历史报告返回组织不可用状态并继续支持平铺输入和制品下载

### Requirement: 迁移报告组织能力必须具有独立单元测试和覆盖率验收
本变更涉及的模块解析、分组聚合、上下文窗口、结构化省略、路径安全和查询逻辑 SHALL 具有不依赖外部服务的单元测试，并 SHALL 满足项目整体与受影响模块的行覆盖率和分支覆盖率至少 90%。

#### Scenario: 单元测试隔离外部连接
- **WHEN** 运行迁移报告组织能力单元测试
- **THEN** 测试 SHALL mock 数据库、对象存储、源码存储及其他 service connection 的返回值
- **AND** 测试 MUST NOT 连接真实数据库、Redis、RabbitMQ、MinIO、SSH 或外部 HTTP 服务

#### Scenario: 覆盖正常异常和边界路径
- **WHEN** 执行本变更的单元测试套件
- **THEN** 测试 SHALL 覆盖正常模块识别与聚合
- **AND** 测试 SHALL 覆盖对象存储失败、路径非法、源码缺失和权限拒绝等异常路径
- **AND** 测试 SHALL 覆盖共享文件、多目标、空报告、空行号、文件边界和远距离 finding 等 edge case

#### Scenario: 覆盖率门槛验收
- **WHEN** 执行项目覆盖率检查
- **THEN** 项目自有可执行代码整体行覆盖率 SHALL 至少为 90%
- **AND** 受影响模块行覆盖率 SHALL 至少为 90%
- **AND** 工具可统计分支覆盖率时，项目整体与受影响模块分支覆盖率 SHALL 至少为 90%
- **AND** 未被测试加载的项目源码 MUST 纳入统计

### Requirement: API E2E 必须验证 C++ 编译器 provider 匹配
独立 API E2E 套件 SHALL 使用真实构建和环境快照验证 C++ 编译工具不会被目标环境中的裸 `gcc` 错误满足，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常流程验证目标仓库 gcc-c++ 候选
- **WHEN** E2E 项目使用 CMake 构建 C++ 源码，源环境实际执行 `c++` 且 provider 为 `gcc-c++`，目标环境仅安装 `gcc` 但仓库提供 `gcc-c++`
- **THEN** 依赖分析 API SHALL 返回 `BUILD_TOOL c++`
- **AND** 结果 SHALL 为 `REPO_AVAILABLE/MEDIUM`
- **AND** 目标 provider package 和版本 SHALL 来自目标仓库中的 `gcc-c++`

#### Scenario: 异常流程验证裸 gcc 不满足 C++ 构建
- **WHEN** 目标环境只有 `gcc`，且不存在目标 C++ 工具或可用 C++ provider package
- **THEN** API 结果 MUST NOT 返回 `TARGET_INSTALLED`
- **AND** 结果 SHALL 清楚表示依赖未满足且不泄露远端路径或凭据

#### Scenario: Edge case 验证多证据去重
- **WHEN** compile database、execve 和日志中同时出现同一 `c++` 工具
- **THEN** API SHALL 只返回一个语义唯一的 C++ 构建工具结果
- **AND** 结果 SHALL 保留实际工具名、源 provider、目标 provider 和最高质量证据

#### Scenario: E2E 清理测试数据
- **WHEN** C++ provider 匹配 E2E 完成或中途失败
- **THEN** 套件 SHALL 清理创建的项目、环境、任务、分析结果和相关制品
- **AND** 测试 MUST NOT 在共享环境中遗留凭据或测试数据

### Requirement: E2E 必须覆盖真实浮点分析流程
独立 API E2E 模块 SHALL 使用真实 C/C++ fixture、真实 x86 构建、真实 `compile_commands.json`、真实 Shared LLVM BC v2 和容器内浮点扫描器完成端到端验证。

#### Scenario: 正常浮点分析
- **WHEN** E2E 通过 API 准备源码与构建并创建浮点分析
- **THEN** Worker SHALL 运行真实工具并生成 schema v2 结果
- **AND** E2E SHALL 校验运行、Finding、详情、latest、readiness、日志、JSON/HTML、迁移输入和归档候选

#### Scenario: 浮点异常和边界流程
- **WHEN** 输入缺少 BC、profile 无法解析、manifest 损坏、工具返回 partial、结果为空或任务取消
- **THEN** E2E SHALL 校验受控状态、无半导入数据和旧输入保留语义

### Requirement: E2E 必须覆盖真实内存序统一分析流程
独立 API E2E 模块 SHALL 调用真实 `analyze-project`，不得用 fixture 结果替代工具执行，并 SHALL 验证退出码 0、2、3 和失败路径。

#### Scenario: 发现内存序风险
- **WHEN** 真实 fixture 产生 memory-order exit 3 和 risk Finding
- **THEN** 任务 SHALL 成功而不是重试
- **AND** E2E SHALL 校验 Finding evidenceChain、迁移输入、报告和归档

#### Scenario: 部分分析
- **WHEN** 开放 Scope、AST-only 或受控预算产生 exit 2
- **THEN** 运行 SHALL 以 PARTIAL 可查询
- **AND** E2E SHALL 校验 frontier、diagnostics 和已完成 Finding 被保留

#### Scenario: 统一报告失败
- **WHEN** 请求无效、所有 Scope 失败或 status/verdict/exit_code 冲突
- **THEN** 任务 SHALL 失败
- **AND** MUST NOT 写入成功态 Finding 或刷新旧迁移输入

### Requirement: E2E 必须覆盖权限和查询合同
专项分析 E2E SHALL 覆盖项目权限、分页、过滤、排序、Finding 详情、制品下载和非法参数。

#### Scenario: 多条 Finding 查询
- **WHEN** 真实或受控工具输入产生多风险、多路径和多规则 Finding
- **THEN** E2E SHALL 验证运行与 Finding 分页总数、过滤和稳定排序

#### Scenario: 跨项目访问
- **WHEN** 普通用户访问其他项目的运行、Finding 或制品
- **THEN** API SHALL 拒绝访问且不泄漏资源存在性

### Requirement: E2E 必须清理专项分析数据
专项分析 E2E 在成功或失败后 SHALL 清理本次创建的数据库记录、对象存储对象、工具 cache namespace 和 runtime 临时目录。

#### Scenario: 测试结束清理
- **WHEN** E2E 模块结束或中途失败
- **THEN** runner SHALL 按本次 run ID 清理任务、事件、日志、运行、Finding、迁移输入、归档候选和 stored artifacts
- **AND** MUST NOT 清理非本次测试创建的数据
