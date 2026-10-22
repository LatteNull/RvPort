## Context

模型 profile 测试当前由 `POST /api/admin/model-profiles/{profileId}:test` 同步完成，并把模型基础可用性、agent runtime 纯文本能力、workspace/tool 闭环、测试比较 schema 校验串行放在同一次请求里。一个 profile 如果配置 30 秒 timeout，四个 probe 的最坏耗时会接近 120 秒，前端经 Nginx 代理时容易触发 upstream timeout，页面被前端统一跳转到 500。

同时，系统已经支持多种 agent runtime。模型是否可用不等价于模型是否适合某个 agent，单一 `last_test_*` 字段无法表达“同一个模型对多个 agent 的兼容性结果”。

## Goals / Non-Goals

**Goals:**

- 将模型连通性测试和 agent runtime 兼容性测试拆成两个独立 API。
- 支持前端提交 `agentRuntimeIds` 列表，按所选 agent runtime 生成兼容性测试结果。
- 避免 agent probe 长请求阻塞 HTTP 连接，降低前端 500/504 风险。
- 持久化 profile 与 agent runtime 的分项兼容性结果，支持列表、详情和后续阶段绑定判断。
- 保持旧 `:test` 接口的兼容边界，降低前端迁移风险。

**Non-Goals:**

- 不新增任意 prompt 执行接口。
- 不改变 `TEST_LOG_COMPARE` 阶段仍只能绑定一个模型 profile 和一个 agent runtime 的事实来源。
- 不在本 change 中实现前端页面改造。
- 不改变各 agent adapter 的核心执行协议，只调整 probe 编排和结果记录。

## Decisions

### 拆分连通性测试和 Agent Probe

新增 `POST /api/admin/model-profiles/{profileId}:test-connectivity`。该接口只使用模型 profile 的 provider 参数执行最小模型调用，例如 JSON 文本返回校验，不启动任何 agent runtime。它用于回答“这个模型配置是否能连上并返回可解析内容”。

新增 `POST /api/admin/model-profiles/{profileId}:test-agents`。该接口接收 `agentRuntimeIds`，创建一次后台 probe run，立即返回 `runId`、初始状态和所选 runtime 摘要。后端后台逐个或并发执行所选 runtime 的 agent probe，并把每个 runtime 的结果独立记录。

模型 profile 列表和详情需要返回最近一次连通性测试摘要，但不需要返回活跃连通性 run，因为 `test-connectivity` 不创建后台任务，请求结束即完成或失败。如果未来发现连通性测试也会稳定超过网关超时，再把它升级为同样的 run 模式。

模型 profile 列表和详情需要返回当前是否存在活跃 agent probe run。如果某个 profile 有 `PENDING` 或 `RUNNING` 的 probe run，响应中应包含该 `runId`、状态、所选 agent runtime 摘要和创建时间。前端刷新页面或重新进入配置页时，可以根据这个字段继续轮询 run 结果，而不是误以为测试已经结束。

选择拆分的原因是连通性失败通常是 base URL、API key、模型名、wire API 问题；agent probe 失败则可能是 CLI 安装、模型 tool/use 能力、输出 schema 或运行时参数问题。两者混在一起会让用户无法判断故障层级。

### Agent Probe 使用可查询 Run

agent 兼容性测试可能运行较久，不能继续用一个同步 HTTP 请求承载。后端应创建 `model_profile_agent_probe_runs` 表记录批量测试 run，并创建 `model_profile_agent_probe_results` 表记录每个 profile + agent runtime 的最新结果和历史 run 归属。

接口形态：

- `POST /api/admin/model-profiles/{profileId}:test-agents`
- `GET /api/admin/model-profile-agent-test-runs/{runId}`
- `GET /api/admin/model-profiles/{profileId}/agent-probe-results`

这样前端可以轮询 run 状态，也可以在 profile 列表或详情中展示最近兼容性矩阵。

profile 列表/详情的 active run 只返回当前仍未终态的最新 run。终态 run 的详细结果通过 run 查询接口和 profile-agent 结果列表查询，不在列表接口中展开全部历史。

### 结果状态分层

连通性结果保存为 profile 级结果：`SUCCESS`、`FAILED`、`TIMEOUT`。

agent probe run 保存聚合状态：`PENDING`、`RUNNING`、`SUCCESS`、`PARTIAL_SUCCESS`、`FAILED`、`TIMEOUT`。

单个 agent result 保存分项状态：

- `AGENT_TEXT`
- `AGENT_WORKSPACE_TOOL`
- `TEST_COMPARE_SCHEMA`

每个分项记录 `status`、`errorCode`、`message`、`durationMillis` 和脱敏后的摘要。一个 agent runtime 失败不影响其他 runtime 的结果写入。

### 旧接口兼容

旧 `POST /api/admin/model-profiles/{profileId}:test` 暂时保留。它可以继续执行现有单 agent 同步测试，或内部转向默认/指定 agent 的 probe run 并返回兼容响应；但新前端 SHALL 使用新的连通性和批量 agent 测试接口。旧接口应在 API 文档中标记为兼容入口，不再作为新功能扩展目标。

### 安全与脱敏

所有测试结果和错误信息必须脱敏。响应和数据库字段不得保存 API key、授权头、完整 prompt、完整 agent 命令、服务器真实敏感路径或临时 workspace 绝对路径。临时覆盖配置允许参与测试，但 API key 不得因为测试被持久化到 profile。

## Risks / Trade-offs

- [Risk] 增加后台 run 表和结果表会带来迁移与清理成本。
  Mitigation: run 表保留必要状态和摘要，详细输出只保存脱敏分项；后续可以复用现有定时清理机制处理过旧 run。

- [Risk] 旧同步 `:test` 仍可能被旧前端调用并触发超时。
  Mitigation: 在接口文档中明确新前端必须迁移到 split API；必要时给旧接口增加较短超时和明确提示。

- [Risk] 多 agent 并发测试会占用容器 CPU 和外部模型额度。
  Mitigation: 后端限制单次 `agentRuntimeIds` 数量，默认按受控线程池执行，单 profile 同时只允许有限个活跃 probe run。

- [Risk] 连通性测试通过不代表 agent probe 必然通过。
  Mitigation: API 和列表摘要明确区分 connectivity status 与 per-agent compatibility status。
