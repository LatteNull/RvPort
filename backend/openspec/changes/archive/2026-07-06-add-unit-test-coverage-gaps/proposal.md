## Why

现有 Java 单元测试已经能覆盖部分主流程，但与项目约定的“正常流程、异常流程、edge case”三类覆盖标准相比仍有明显缺口。现在后端基础能力已经进入项目、源码、环境、任务和 worker 主干阶段，及时补齐单元测试可以降低后续业务切片在边界条件和敏感信息处理上的回归风险。

## What Changes

- 补齐现有 Java 单元测试缺口，重点覆盖服务层异常分支、边界分支和安全/脱敏约束。
- 为主要 Controller 增加轻量 MockMvc 测试，覆盖请求校验、统一错误包络和关键安全边界。
- 为任务、worker、源码、环境、用户管理和凭据模块补充 edge case 测试。
- 复核 `mvn test` 基线，确保新增测试仍不依赖真实 Docker Compose 基础设施，也不触发独立 API E2E。
- 不修改生产业务行为；如测试发现真实缺陷，应在实现阶段以最小修复同步处理。

## Capabilities

### New Capabilities
- 无。

### Modified Capabilities
- `backend-app-skeleton`: 明确当盘点发现既有后端能力缺少正常流程、异常流程或 edge case 覆盖时，必须通过单元测试、轻量集成测试或说明不适用原因进行回补。

## Impact

- 影响范围主要是 `backend/src/test/java/cn/rvport/backend/**`。
- 可能新增少量测试辅助方法或测试 fixture。
- 不新增运行时依赖，不改变 HTTP API、数据库 schema、Docker Compose、E2E 脚本或生产配置。
- 验证命令为 `mvn test`；独立 API E2E 不在本 change 的默认验证范围内。
