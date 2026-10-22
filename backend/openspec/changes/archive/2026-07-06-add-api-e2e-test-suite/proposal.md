## Why

当前后端已经有认证、用户管理、项目、源码、环境、任务和 SSE 等 API，但自动化测试主要集中在单元测试和少量 MockMvc 测试，真实 HTTP、Session Cookie、CSRF、PostgreSQL、Redis、RabbitMQ 和清理流程还没有形成可重复运行的端到端测试套件。

随着后续 API 增多，如果继续依赖手工联通验证，容易遗漏历史接口、留下脏数据，也难以及时发现真实基础设施下的契约回归。

## What Changes

- 新增独立 API E2E 测试套件，不混入 Spring Boot 单元测试或普通 `mvn test`。
- 新增独立目录、脚本和文档，用于检查基础设施、运行端到端 API 流程、校验副作用并清理测试数据。
- E2E 测试使用真实运行的后端服务、PostgreSQL、Redis 和 RabbitMQ，覆盖真实 Session Cookie、CSRF、multipart 上传、任务投递和 SSE 恢复。
- E2E 测试数据必须带统一 run id 或可追踪前缀，测试完成后必须清理数据库、队列消息和上传文件。
- 当前已实现 API 需要补齐第一批 E2E 覆盖矩阵，至少覆盖认证与用户、项目、源码、环境、任务和 SSE 主链路。
- 后续新增或修改 API 时，必须同步补充 E2E 测试用例，覆盖正常流程、异常流程和 edge case；若不适用，必须在 change 文档中说明原因。

## Capabilities

### New Capabilities

- `api-e2e-test-suite`: 定义独立 API 端到端测试套件的运行方式、基础设施依赖、测试覆盖、清理策略和后续 API 测试扩展规则。

### Modified Capabilities

- `backend-app-skeleton`: 扩展全局测试约定，要求后续后端 API change 同步考虑独立 E2E 测试覆盖，而不是只依赖单元测试或 MockMvc 测试。

## Impact

- 新增 `backend/e2e` 或等价目录，用于保存 E2E runner、case、工具函数、配置样例和清理脚本。
- 新增跨平台运行入口，至少包含 Windows 和 Linux/macOS 的运行方式。
- 新增 API E2E 文档，说明基础设施要求、运行命令、清理命令、失败排查和测试数据约定。
- 可能引入 Node.js、Python 或脚本运行时依赖；该依赖只用于 E2E 测试，不影响后端应用运行和 `mvn test`。
- E2E 测试会访问真实 Docker Compose 基础设施和后端服务，必须避免默认自动运行。
