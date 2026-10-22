## Context

自动化测试节点后续需要比较 x86 与 RISC-V 两侧的大体量测试日志。直接把完整日志塞进业务 API 或一次 LLM 调用不现实，因此设计上需要把日志保存为受控文件，再由 Codex agent runtime 在隔离工作区中读取、分片、归纳并输出结构化比较结果。

这里的“provider”不是后端直接调用某个模型 API，而是后端调用 Codex 作为 agent runtime；Codex 再按配置使用第三方 OpenAI-compatible LLM API。当前后端已经有 `system_configs` 表、secret 加密能力和 `/api/admin/configs/**` 超级管理员权限边界，因此 Codex provider 配置应复用这些基础。

## Goals / Non-Goals

**Goals:**

- 提供一个超级管理员可维护的默认 Codex provider 配置。
- 支持 OpenAI-compatible API 所需的 base URL、模型名、wire API 类型、API key、超时、运行时限制和启用状态。
- 后端 Docker runtime 镜像安装 Codex CLI，确保部署环境具备 agent runtime 可执行文件。
- API key 加密保存，查询响应和日志只暴露配置状态或遮蔽摘要。
- 提供测试接口验证 Codex provider 配置是否可用，并保存最近一次测试摘要。
- 为后续自动化测试日志比较任务提供统一配置来源。

**Non-Goals:**

- 不实现自动化测试执行节点。
- 不实现 x86/RISC-V 测试日志比较任务。
- 不实现多个 provider 的列表管理、租户级 provider 或项目级 provider 覆盖。
- 不让业务代码直接调用第三方 LLM API。
- 不允许通过该配置接口传入任意 shell 命令或任意环境变量。

## Decisions

### 1. Codex 作为 agent runtime，OpenAI-compatible API 作为模型后端

后端只负责配置和调用 Codex CLI，Codex 负责通过第三方 OpenAI-compatible API 访问模型。这样后续日志比较可以复用 Codex 的文件读取、分片分析和结构化输出能力，也避免在业务代码里重新实现一套长日志压缩、提示词编排和工具调用逻辑。

备选方案是后端直接调用 OpenAI-compatible API。暂不采用，因为大日志分析需要 agent 工作区、分批读取和中间结果管理，直接 API 调用更容易出现上下文过大、重试复杂和输出不可审计的问题。

### 2. MVP 只支持一个默认 Codex provider

配置使用 `system_configs` 的 `codex-provider` namespace 保存。MVP 不做 provider 列表，也不做项目级覆盖。这样可以先满足“自动化测试日志比较有一个可用 agent provider”的需求，减少权限和选择逻辑复杂度。

建议的配置 key：

| key | 类型 | 说明 |
| --- | --- | --- |
| `enabled` | BOOLEAN | 是否启用 Codex provider |
| `executablePath` | STRING | Codex CLI 路径，默认 `codex` |
| `modelProviderType` | STRING | 固定为 `OPENAI_COMPATIBLE` |
| `baseUrl` | STRING | 第三方 OpenAI-compatible API base URL |
| `model` | STRING | 模型名称 |
| `wireApi` | STRING | `RESPONSES` 或 `CHAT`，默认 `RESPONSES` |
| `apiKey` | SECRET | API key，加密保存 |
| `timeoutSeconds` | NUMBER | 单次 Codex 探测请求超时 |
| `maxRuntimeSeconds` | NUMBER | 后续 agent 任务最大运行时间 |
| `lastTestStatus` | STRING | 最近一次测试结果状态 |
| `lastTestMessage` | STRING | 最近一次测试结果摘要，必须脱敏 |
| `lastTestedAt` | STRING | 最近一次测试时间，ISO-8601 |

### 3. secret 使用已有配置加密能力

`apiKey` 走 `SystemConfigService.saveSecret`，数据库只保存加密后的 secret JSON。查询接口返回 `apiKeyConfigured` 和可选的 `apiKeyMasked`，不返回明文或密文。

更新接口对 `apiKey` 使用“可选更新”语义：

- 字段不存在：保留已有 API key。
- 字段为空字符串：清空已有 API key。
- 字段为非空字符串：加密后覆盖。

这样可以避免前端每次保存普通配置时被迫重新提交 secret。

### 4. 测试接口不持久化临时 secret

`POST /api/admin/configs/codex-provider:test` 可以使用已保存配置，也可以接收请求体中的临时覆盖字段做测试。临时 API key 只能在本次请求内使用，不能写入 `system_configs`。

测试接口应在隔离临时目录运行最小 Codex smoke test，例如要求输出固定 JSON 结构。测试结果只保存成功/失败状态、脱敏错误摘要和测试时间。错误摘要必须去除 API key、授权头、真实本地路径等敏感信息。

### 5. 后续 agent 执行必须使用受控工作区

虽然本 change 不实现日志比较任务，但配置设计需要为后续调用留出边界：

- Codex 执行目录由后端创建，只包含脱敏后的日志、metadata 和 instructions。
- 调用 Codex 时参数数组化传入，不经过 shell 字符串拼接。
- 默认使用非交互模式，不依赖人工确认。
- 后续任务的输出必须校验固定 JSON schema 后再入库。
- agent stdout/stderr 应作为任务日志或输出制品记录，但不得包含 secret。

### 6. 后端镜像必须安装 Codex CLI

后端 Dockerfile 在 runtime 阶段安装 Node/npm 和 Codex CLI。默认版本固定为 `@openai/codex@0.147.0`，通过 `CODEX_CLI_VERSION` build arg 覆盖。这样后端容器和 worker 容器拥有一致的 Codex CLI 入口，后续 provider 测试和日志比较任务不依赖宿主机安装。

## Risks / Trade-offs

- Codex CLI 未安装或路径错误 -> 测试接口返回受控失败，配置查询保留最近失败摘要。
- 第三方 OpenAI-compatible API 行为不完全兼容 -> 测试接口先验证最小调用，后续任务失败时记录 provider 错误类型。
- API key 泄漏 -> 使用 secret 加密、响应遮蔽、日志脱敏，并禁止返回密文。
- 任意 executable path 带来执行风险 -> 后端必须校验路径格式，调用时使用参数数组，不能接受额外 shell 片段。
- 单 provider 后续不够用 -> 当前 namespace key 设计可平滑扩展到 provider 表或多 namespace，但 MVP 不提前实现。

## Migration Plan

1. 复用现有 `system_configs` 表，无需新增 Liquibase 表结构。
2. 新增 Codex provider 配置服务、DTO、Controller 和 provider smoke test 服务。
3. 更新 Dockerfile 和 compose build arg，确保后端镜像安装 Codex CLI。
4. 将 `/api/admin/configs/codex-provider/**` 置于现有超级管理员权限范围内。
5. 补充单元测试和 E2E 模块测试。
6. 部署时只需配置现有凭据加密主密钥；Codex provider 可由超级管理员在页面或 API 中写入。

回滚时删除接口代码即可，已写入的 `system_configs` namespace 数据可以保留，不影响其他业务配置。

## Open Questions

- 后续是否需要多个 provider、按项目指定 provider 或按任务类型指定 provider。
- 后续 Codex CLI 的运行配置是否需要生成临时 config 文件，还是完全通过环境变量注入。
- 后续自动化测试日志比较的结构化输出 schema 需要在对应 change 中单独定义。
