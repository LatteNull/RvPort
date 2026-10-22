## Context

当前 `POST /api/admin/model-profiles/{profileId}:test-agents` 的输入已经是模型 Profile 和 Agent Runtime ID 列表，但 `CodexProviderProbeService` 会固定执行 `TEST_COMPARE_SCHEMA` 和 `KB_AI_EXTENSION_SCHEMA`。聚合成功要求两个阶段检查均通过，结果表和 DTO 也分别保存阶段兼容性布尔值。这使一个本应稳定的模型与 Agent 组合关系依赖当前已有业务阶段，并要求每新增阶段都扩展兼容性 schema。

模型连通性已有独立同步 API；阶段配置由 `model_stage_assignments` 保存；测试比较和 KB AI 扩展运行时也已有各自的输出 parser。因此通用 Agent 兼容性只需证明该模型能够被指定 Runtime 驱动并完成基础 workspace/tool 闭环。

## Goals / Non-Goals

**Goals:**

- 将兼容性主键和结论稳定为 `model_profile_id + agent_runtime_id`。
- 使用阶段无关的 Agent 调用、workspace 读取、文件写入和 JSON 解析检查计算通用兼容性。
- 从数据库、jOOQ、内部结果模型和管理 API 中移除阶段兼容性字段。
- 保持多 Runtime 异步 probe、单 Runtime 失败隔离、活跃 run 恢复和敏感信息脱敏。
- 保持各阶段在实际执行时对自己的输出文件和 schema 做严格校验。
- 通过正常、异常和边界单元测试，并以项目整体和受影响模块至少 90% 行覆盖率及可用分支覆盖率作为完成门槛。

**Non-Goals:**

- 不删除或重构 `model_stage_assignments`。
- 不改变测试比较、KB AI 扩展等业务任务的阶段选择、提示词或结果 schema。
- 不根据通用 probe 结果自动绑定阶段，也不在本 change 中设计模型质量评分。
- 不兼容继续读取已移除的阶段兼容性 API 字段。

## Decisions

### 1. 兼容性只属于模型 Profile 与 Agent Runtime 组合

`model_profile_agent_probe_results` 继续按 Profile 和 Runtime 保存历史结果，最近兼容性矩阵也继续按这一对 ID 取最新记录。阶段绑定不会被查询或写入 probe run，也不参与聚合状态。

未选择“Profile × Runtime × Stage”，因为这种结构会让每个新阶段都成为兼容性系统的数据库与 API 扩展点，而且阶段 prompt 或 schema 的变化会错误地使同一模型与 Runtime 的基础兼容性反复改变。

### 2. 通用 probe 使用中性 workspace/tool 闭环

每个 Runtime 执行以下受控检查：

1. `AGENT_TEXT`：通过 Runtime 调用模型并返回可解析的固定 JSON。
2. `AGENT_WORKSPACE_READ`：读取 workspace 中的中性输入文件，并在响应中返回约定 marker。
3. `AGENT_WORKSPACE_WRITE`：读取输入后通过 Agent 工具写出中性结果文件，后端校验文件存在、JSON 合法和 marker 正确。

聚合 `agentCompatible` 仅在全部通用检查成功时为真。模型 provider 的纯 HTTP 连通性仍由 `:test-connectivity` 独立负责，不用阶段 probe 代替。

未保留阶段 schema 作为“可选分项”，因为只要它仍出现在同一兼容性结果中，前端和调用方就会继续把阶段能力视为模型兼容性的一部分。

### 3. 阶段输出契约在真实任务边界验证

测试比较继续读取并校验 `comparison-result.json`，KB AI 扩展继续读取并校验结果 JSONL。实际任务输出不合法时，该次任务按现有阶段错误码失败，但不更新 Profile 与 Runtime 的通用兼容性记录。

这种分层允许模型通过通用 Agent probe 后仍可能因某个具体任务质量不足而失败；这是业务执行结果，不是运行时兼容性缺陷。

### 4. 删除阶段兼容性持久化与 API 字段

新增 Liquibase changeset 删除：

- `model_profile_agent_probe_results.test_log_compare_compatible`
- `model_profile_agent_probe_results.kb_ai_extension_compatible`
- `model_profiles.last_test_compare_compatible`

随后重新生成并提交 jOOQ 元数据。`checks` JSON 保留通用分项，`agent_compatible` 保留聚合结论；旧历史记录中的通用字段和 checks 继续存在，但 API 不再解释旧阶段检查。

采用删除而不是长期保留空列，是为了防止后续代码继续读取已经失效的阶段概念。回滚时可重新增加可空列，但被删除的历史阶段布尔值不恢复。

### 5. API 返回通用兼容性矩阵

probe result 返回 Runtime 摘要、状态、`agentCompatible`、通用 `checks`、脱敏详情和时间信息，不再返回任何阶段名或阶段兼容性字段。Profile 列表和详情中的最近测试摘要也移除测试比较兼容性字段；阶段绑定 API 维持现状。

## Risks / Trade-offs

- [前端仍读取旧字段] → 将 API breaking change 写入文档并更新 E2E，前端以 `agentCompatible` 和通用 checks 展示矩阵。
- [历史 checks 含阶段名称] → 最近结果在重新 probe 后自然替换；API 不再提升这些旧 check 为阶段字段，也不让其参与新结果计算。
- [通用 probe 通过但阶段任务失败] → 保留阶段 parser 的严格失败语义，并在业务任务错误中展示阶段输出不合法，而不污染通用兼容性。
- [删列造成不可逆历史数据损失] → 这些字段已被判定为错误建模且不再消费；回滚只恢复结构，不承诺恢复旧值。
- [文件写入 probe 增加运行时间] → 使用极小中性 fixture 和单一输出文件，沿用已有 Runtime 超时与临时目录清理机制。
- [Codex CLI 仅安装 JS 启动器而缺少平台二进制] → 镜像构建显式安装与固定 CLI 版本一致的 `linux-x64` 可选依赖，并以 `codex --version` 作为构建期自检；backend 与 backend-worker 共用同一镜像。

## Migration Plan

1. 增加 Liquibase changeset 删除三个阶段兼容性列。
2. 重新生成 jOOQ 代码，确认生成物不再暴露对应字段。
3. 调整 probe enum、prompt、结果模型、repository、service 和 API DTO。
4. 更新模型管理 API 与数据库中文文档、E2E fixture 和断言。
5. 运行单元测试、整体覆盖率和受影响模块覆盖率；行覆盖率及工具可提供的分支覆盖率均不得低于 90%。
6. 构建并更新后端与 Worker 容器，运行模型管理 E2E 验证异步 run 和多 Runtime 结果。
7. 在镜像构建阶段验证 Codex、DeepSeek Harness 和 OpenCode 命令均能启动，防止缺失平台可选依赖的镜像进入运行环境。

回滚时回退应用版本并以新的前向 Liquibase changeset 恢复可空列；不得修改或删除已执行的历史 changeset。

## Open Questions

无。
