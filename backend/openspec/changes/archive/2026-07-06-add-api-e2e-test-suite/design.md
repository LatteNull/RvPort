## Context

后端当前已经具备 Spring Boot API、Liquibase schema、jOOQ、PostgreSQL、Redis、RabbitMQ、Session Cookie、CSRF、任务运行时、SSE、项目/源码/环境和用户管理能力。已有测试主要包含服务层单元测试、少量 MockMvc controller/security 测试，以及默认跳过的 Liquibase 迁移测试。

这些测试能覆盖很多业务规则，但不能稳定证明真实运行环境下的端到端链路。例如：

```text
浏览器式登录
  -> CSRF
  -> Session Cookie
  -> API 创建资源
  -> PostgreSQL 副作用
  -> RabbitMQ 任务消息
  -> SSE 历史恢复
  -> 清理测试数据
```

这类链路如果放进 `mvn test`，会让普通单元测试依赖 Docker、真实端口和运行中的后端服务，容易造成慢、脆和环境污染。因此本 change 设计一个独立 E2E 测试套件，作为开发者或 CI 明确触发的测试产品。

## Goals / Non-Goals

**Goals:**

- 创建独立 API E2E 测试目录和运行入口，不混入 Spring Boot 单元测试。
- E2E 测试依赖真实运行的后端 API、PostgreSQL、Redis 和 RabbitMQ。
- 提供 Windows 和 Linux/macOS 可用的运行方式。
- 支持真实 Session Cookie、CSRF、JSON 请求、multipart 上传、SSE 读取、数据库校验和队列校验。
- 每次测试生成唯一 `runId`，所有测试数据可追踪并可清理。
- 提供常规清理和强制清理脚本，防止脏数据影响后续测试。
- 第一批 E2E case 覆盖当前已实现 API 的主链路，并按正常流程、异常流程和 edge case 组织。
- 明确后续新增 API 必须同步补充 E2E case 或说明不适用原因。

**Non-Goals:**

- 不把 E2E 测试加入普通 `mvn test`。
- 不替代单元测试、服务层测试、MockMvc 安全测试或 Liquibase 迁移测试。
- 不做 UI 浏览器测试。
- 不做性能、压测或稳定性长跑测试。
- 不在本 change 中接入 CI；只预留命令和目录结构。
- 不要求 E2E runner 解析业务自动化测试报告内容。

## Decisions

### 1. E2E 套件独立于 Maven 单元测试

E2E 测试放在 `backend/e2e` 或等价目录，不放入 `src/test/java`，也不通过 Surefire/Failsafe 自动执行。普通开发者运行 `mvn test` 时只跑单元测试和轻量 Spring 测试。

理由：E2E 测试依赖真实基础设施和运行中的 API 服务，和单元测试的速度、隔离性、失败语义不同。独立运行可以避免“单元测试因为 Docker 或端口问题失败”的噪音。

备选方案：使用 JUnit + Testcontainers。该方案利于 Java 断言和 CI，但会把 E2E 和 Maven 生命周期绑定得更紧，也不符合当前“单纯创建文件夹和脚本”的方向。

### 2. 使用单套跨平台 runner，并提供平台入口脚本

优先采用 Node.js 或等价跨平台脚本运行时实现核心 runner，平台脚本只做薄封装：

```text
e2e/
  README.md
  package.json 或 runner 配置
  config/
    e2e.env.example
  scripts/
    run.ps1
    run.sh
    cleanup.ps1
    cleanup.sh
    check-infra.ps1
    check-infra.sh
  cases/
    001-auth-users.*
    002-project-source-environment.*
    003-task-sse.*
  lib/
    api-client.*
    assertions.*
    cleanup-registry.*
    db.*
    rabbitmq.*
    redis.*
```

理由：HTTP、Cookie jar、CSRF、multipart、SSE、JSON 断言、子进程调用 Docker 在跨平台运行时中更容易保持一致。Windows 和 Linux/macOS 的入口脚本可以只负责加载环境变量和调用同一个 runner。

备选方案：PowerShell + Bash 双实现。它更贴近 shell，但测试逻辑会重复，长期维护成本更高。

### 3. E2E 不负责自动启动所有基础设施，但必须检查健康状态

`run` 脚本必须先检查：

- Docker Compose 中 PostgreSQL、Redis、RabbitMQ 是否存在且 healthy。
- 后端 API 是否可访问 `GET /api/health`。
- 必要环境变量是否存在，例如 API base URL、数据库连接、Redis/RabbitMQ 连接和凭据密钥。

如果基础设施未启动，脚本应给出明确提示，例如先运行根目录 `docker compose up -d`，但不隐式修改环境。

理由：E2E 测试应该验证真实运行环境，而不是悄悄创建一个和开发环境不同的临时环境。显式失败比隐式启动更容易排查。

### 4. 每次运行生成唯一 runId，并以 runId 驱动清理

runner 启动时生成类似：

```text
e2e_20260706_103000_abcd1234
```

所有可命名资源都包含该前缀：

- 用户名
- 项目名
- 凭据名
- 环境名
- 源码版本 label
- 上传目录或临时文件名

同时 runner 维护 cleanup registry，记录本次创建的 projectId、userId、taskId、environmentId、sourceRevisionId、credentialId、上传文件路径和队列名称。

清理策略：

```text
normal cleanup:
  删除本次 runId 关联数据、上传文件和队列测试消息

force cleanup:
  删除所有 e2e_ 前缀历史残留数据
  清空测试队列残留消息
  删除 e2e 上传目录残留
```

理由：数据库存在外键和任务/审计链路，单靠名字前缀不一定足够；cleanup registry 可以让清理顺序稳定，runId 前缀则提供兜底。

### 5. E2E case 按领域和三类路径组织

第一批 case 覆盖当前已实现 API：

```text
001-auth-users
  正常流程：csrf、login、me、change-password、logout、super admin 用户管理
  异常流程：错误密码、未登录访问、普通用户访问 admin API
  edge case：mustChangePassword 限制、isSuperAdmin 不可通过 API 写入

002-project-source-environment
  正常流程：项目创建/查询/更新/overview、源码上传/激活、Git sync 投递、环境/跳板机创建
  异常流程：Git URL 内嵌凭据、资源不存在、禁用环境创建任务
  edge case：空列表、分页边界、自引用跳板、多级跳板、跨项目跳板、路径隐藏和脱敏输出

003-task-sse
  正常流程：任务列表、任务详情、任务日志列表、SSE 历史事件恢复
  异常流程：非法 Last-Event-ID、非法 taskId、不可取消状态
  edge case：空日志、队列消息只包含任务 ID、SSE 客户端断开不污染测试结果
```

理由：按领域组织可以和后续业务 change 自然扩展；三类路径和全局测试策略一致。

### 6. E2E 对真实副作用做断言

E2E 不只断言 HTTP status，还必须断言关键副作用：

- PostgreSQL 中用户、项目、源码、导入、环境、凭据、任务、任务事件、审计记录符合预期。
- RabbitMQ 任务队列出现预期消息，且消息只包含任务 ID 等路由信息。
- Redis 中 session 可建立，且 key 不应出现 Java 序列化乱码前缀或明文秘密。
- API 响应、审计详情和任务 input snapshot 不包含明文密码、私钥、token 或服务器真实路径。

理由：端到端测试的价值在于覆盖真实系统边界，而不是重复 controller 单元测试。

### 7. 后续新增 API 必须同步补 E2E 覆盖

每个新增或修改 HTTP API 的 OpenSpec change 应在 tasks 中包含 E2E 测试项。若某 API 不适合 E2E，例如纯内部 health 或无业务副作用的极小接口，需要在 design 或 tasks 中说明原因。

理由：规则必须落在 change 流程里，否则历史 API 覆盖会继续漂移。

## Risks / Trade-offs

- E2E 运行依赖真实基础设施，失败原因可能来自环境而非代码。→ 运行前做健康检查，并在失败信息中输出具体依赖状态。
- 清理失败可能留下脏数据。→ 使用 runId、cleanup registry、normal cleanup 和 force cleanup 双层策略。
- E2E 太多会变慢。→ 第一批只覆盖关键链路和高风险边界，后续按 API 变更增量维护。
- 脚本运行时引入额外依赖。→ 依赖只放在 `e2e` 目录，不影响应用运行、打包和 `mvn test`。
- 真实凭据测试容易泄漏秘密。→ 测试凭据使用固定假秘密，断言响应、审计、任务输入和队列消息不包含秘密原文。
- SSE 测试可能因为短连接断开产生噪声。→ runner 将 SSE 读取限制为短窗口，并只断言历史 replay 和事件格式。
