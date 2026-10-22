## ADDED Requirements

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
