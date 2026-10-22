## Why

模型 Profile 的 Agent 兼容性探测已经能够驱动 DeepSeek Harness 和 OpenCode 成功返回预期 JSON、读取工作区并写入结果文件，但后端优先解析带 `[STDOUT]`、`[STDERR]` 与 ANSI 控制字符的 `mergedOutput`，导致有效结果被误判为 `AGENT_PROBE_OUTPUT_INVALID`。该行为还受进程输出缓冲分块影响，使不同 Agent Runtime 甚至同一运行时的判断具有偶然性，需要统一结构化输出边界并补齐真实形态验证。

## What Changes

- Agent Probe 将独立 stdout 作为结构化结果的首选来源，不再直接把 merged output 当作机器可读 JSON。
- 当 stdout 无法解析时，对 merged output 执行通道标签与 ANSI 控制字符清洗后再作为兼容回退。
- 结构化 JSON 提取支持普通日志前后缀、Markdown 代码块、多行对象和多个候选对象，并选择最后一个满足当前 probe 预期字段的对象。
- 退出码、超时和结构化内容校验继续保持独立；失败消息使用脱敏后的诊断输出，不暴露 API key。
- 增加覆盖 DeepSeek Harness、OpenCode、Codex 输出形态的单元测试和 API E2E 场景，覆盖正常、异常和边界情况，并维持后端整体及受影响模块至少 90% 的行覆盖率与分支覆盖率。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `model-profile-management`: 明确 Agent Probe 的结构化输出来源、清洗回退、JSON 候选选择和稳定判定行为。
- `api-e2e-test-suite`: 增加真实 Agent CLI 通道标签、ANSI 日志和多行 JSON 输出下的兼容性探测验证。

## Impact

- 主要影响 `CodexProviderProbeService` 的结构化输出提取及其单元测试。
- 可能提取可复用的 Agent 结构化输出解析辅助组件，但不改变 Agent CLI 的原始 stdout、stderr 和 merged output 采集语义。
- 不改变现有模型 Profile、Agent Runtime、Probe Run API 及数据库 schema。
- 修复后，历史误判记录保持不变；重新运行兼容性探测会产生新的正确结果。
