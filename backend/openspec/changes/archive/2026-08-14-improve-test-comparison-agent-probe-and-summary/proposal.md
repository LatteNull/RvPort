## Why

当前模型 profile 测试只能证明模型基础调用可用，不能证明模型支持当前被选 agent 读取 workspace 文件、执行工具并回传工具结果的完整闭环。实际测试已经发现同一 OpenAI-compatible 平台内不同模型能力差异明显，导致配置时显示可用但测试结果比较运行时失败。

当前测试结果比较阶段先使用 Codex CLI 作为 agent 执行器，但模型兼容性设计不能绑定死在 Codex 上。后续可能增加其他 agent 执行器，只要该 agent 能适配用户配置的模型并满足当前阶段能力要求，就应该可以被模型 profile 测试、阶段绑定和运行时复用。

当前测试结果比较 summary 偏自然语言，不能稳定回答 x86 与 RISC-V 各自跑了多少测试、通过多少、失败多少、失败项和失败原因。并且 stdout/stderr 分离会破坏错误与测试步骤之间的顺序关系，不利于 agent 判断失败发生的位置。

## What Changes

- 扩展模型 profile 测试能力，增加面向可插拔 agent 的 workspace/tool 闭环探测，并保存分项测试结果与聚合兼容性状态。
- 模型测试结果需要区分基础调用可用、指定 agent 纯文本可用、指定 agent workspace 工具闭环可用、测试比较 JSON schema 可用等分项能力。
- 当前实现默认 agent 类型为 `CODEX`，但测试结果、API 响应和持久化结构需要包含 agent 类型，便于后续扩展其他 agent provider。
- 自动化测试运行时增加有序合并日志，按实际读取顺序记录 stdout/stderr，同一份 merged log 作为前端展示与测试比较 agent 的主要输入。
- 保留 stdout/stderr 原始日志作为调试材料，但测试比较不再以分离日志作为主输入。
- 测试结果比较 agent 输出 schema 增加 x86/source 与 RISC-V/target 的测试统计，包括总数、执行数、通过数、失败数、失败项和失败原因。
- 测试数量、失败项与原因由 agent 从 merged log 和报告材料中提取，不为不同测试工具实现专用 parser。
- 更新 API 响应，使模型 profile 测试和测试比较结果可以返回更细的能力状态与结构化统计摘要。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `model-profile-management`: 模型 profile 测试从最小可用性测试扩展为可插拔 agent 兼容性分项探测。
- `automated-test-runtime`: 自动化测试运行时增加 stdout/stderr 有序合并日志，并将其作为后续比较的主日志材料。
- `test-result-comparison-runtime`: 测试结果比较输出结构化环境测试统计，并由 agent 负责从日志和报告中提取测试数量、失败项和原因。
- `backend-api-design`: 模型测试 API、自动化测试详情 API 和测试结果比较 API 的响应契约增加兼容性状态、merged log 摘要和结构化统计字段。

## Impact

- 影响模型 profile 测试服务、模型 profile API 响应、模型 profile 数据库存储或 JSON 扩展字段。
- 影响自动化测试 worker 的日志采集方式、任务日志文件写入方式和测试运行详情摘要。
- 影响测试结果比较输入聚合器、当前 Codex agent prompt、agent 输出解析、比较结果持久化和查询响应。
- 影响独立 API E2E 与单元测试，需要覆盖正常流程、异常流程和 edge case。
