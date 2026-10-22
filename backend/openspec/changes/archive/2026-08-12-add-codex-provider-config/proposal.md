## Why

自动化测试日志可能非常庞大，后续需要由 Codex 作为 agent runtime 读取受控日志文件、分片分析并生成结构化比较结果。Codex 需要能够使用用户在管理页面配置的第三方 OpenAI-compatible LLM API，因此后端需要先提供 Codex provider 配置能力。

## What Changes

- 新增超级管理员可管理的 Codex provider 配置 API。
- Codex provider 配置支持第三方 OpenAI-compatible API，包括 base URL、模型名、wire API 类型、API key、超时、运行时限制和启用状态。
- API key 使用既有配置 secret 加密能力保存，查询响应只返回是否已配置和遮蔽摘要。
- 提供 provider 测试接口，用于验证 Codex provider 配置是否可用。
- 不在本 change 中实现自动化测试运行、测试日志比较或 Codex 实际分析任务。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `backend-api-design`: 增加超级管理员管理 Codex provider 配置和测试连接的 API 约束。
- `backend-database-design`: 增加 Codex provider 配置在 `system_configs` 中的持久化、加密和唯一性约束。
- `backend-app-skeleton`: 增加 Codex provider 配置相关测试必须覆盖正常流程、异常流程和 edge case 的约束。

## Impact

- 后端 API：新增 `/api/admin/configs/codex-provider` 配置查询、保存和测试接口。
- Docker：后端镜像安装 Codex CLI，供后续 agent runtime 调用。
- 数据库：复用 `system_configs`，不新增独立表。
- 安全：API key 加密保存，响应和日志不返回明文或密文。
- 后续能力：为 `add-automated-test-runtime` 和 `add-codex-test-log-comparison` 提供配置基础。
