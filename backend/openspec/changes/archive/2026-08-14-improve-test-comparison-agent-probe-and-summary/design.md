## Context

当前模型 profile 测试只验证基础文本调用或 Codex CLI 纯文本输出，不能验证测试结果比较阶段真正依赖的能力：读取 workspace 文件、执行工具、回传工具结果并继续输出结构化 JSON。近期真实测试显示，同一 OpenAI-compatible 平台内不同模型在工具闭环上的兼容性不同，基础调用成功不能代表可用于 `TEST_LOG_COMPARE`。

当前测试结果比较先使用 Codex CLI 作为 agent 执行器，但这里的能力探测不应该被建模为 Codex 专属能力。模型 profile 需要表达“某个模型是否兼容某个 agent 的某个阶段能力”，这样后续接入其他 agent 执行器时，可以复用同一套 profile 测试、阶段绑定和兼容性展示。

当前自动化测试保存 stdout/stderr 分离日志。测试失败信息常常分布在两个流中，分离读取会破坏测试步骤与错误输出之间的顺序关系。测试比较 agent 应该看到一份按实际读取顺序排列的合并日志，同时保留 stream 标记用于说明来源。

当前测试结果比较 summary 偏自然语言，缺少源环境和目标环境各自的测试数量、通过数量、失败数量、失败项和失败原因。RvPort 使用 agent 的目的就是避免为 JUnit、CTest、pytest、make test 等不同工具分别实现 parser，因此这些统计应由 agent 从 merged log 和报告材料中提取，并在置信度不足时明确表达不可确定。

## Goals / Non-Goals

**Goals:**

- 模型 profile 测试能够判断模型是否支持指定 agent 工作模式，而不是只判断基础调用是否可用。
- 模型测试结果返回分项 probe 状态，前端可以提示“基础调用可用但不支持当前 agent”。
- 模型测试结果包含 agent 类型，当前默认支持 `CODEX`，后续可以增加其他 agent provider。
- 自动化测试运行时产生有序 merged log，测试比较 agent 默认读取 merged log。
- 测试比较结果输出结构化 source/x86 与 target/RISC-V 测试统计。
- 测试统计、失败项和失败原因由 agent 从日志与报告中提取，不新增 per-framework parser。

**Non-Goals:**

- 不实现自动 fallback 到其他模型。
- 不实现 JUnit、CTest、pytest、TAP、Go test 等专用解析器。
- 不改变自动化测试执行命令、远程执行协议或报告回收路径。
- 不要求前端在本 change 中完成展示调整。

## Decisions

### 模型测试分为基础可用和 agent 兼容两类

模型 profile 测试 SHALL 至少包含以下分项：

- `BASIC_TEXT`: provider 能返回基础 JSON。
- `AGENT_TEXT`: 指定 agent 在不执行工具时能完成输出。
- `AGENT_WORKSPACE_TOOL`: 指定 agent 在专用 workspace 中读取文件、执行工具、回传工具结果并输出最终 JSON。
- `TEST_COMPARE_SCHEMA`: 使用接近测试比较场景的输入，验证指定 agent 能返回可解析的比较 JSON schema。

每次 agent probe SHALL 记录 `agentType`，当前实现取值为 `CODEX`。后续新增其他 agent 时，可以增加新的 `agentType` 和对应 runner，但不应改变模型 profile 的上层测试结果结构。

聚合状态应明确区分：

- `basicAvailable`: 基础调用是否可用。
- `agentCompatible`: 是否支持指定 agent workspace/tool 闭环。
- `testLogCompareCompatible`: 是否可用于 `TEST_LOG_COMPARE`。

理由：DeepSeek/Kimi 类型问题发生在工具结果回传阶段，纯文本 probe 无法提前发现；同时，同一个模型可能不兼容 Codex，但未来可能兼容另一个 agent，因此兼容性必须带 agent 维度。

### agent 能力结果需要可扩展

模型 profile 最近一次测试摘要 SHALL 使用可扩展结构保存，例如：

- `agentType`: 当前测试的 agent 执行器类型，例如 `CODEX`。
- `checks[]`: 分项检查列表，每项包含 `name`、`status`、`message`、`durationMs`。
- `capabilities`: 聚合能力，例如 `basicAvailable`、`agentCompatible`、`testLogCompareCompatible`。

API 可以为了前端使用保留扁平字段，但原始分项结果需要保留 agent 类型，避免未来新增 agent 时重新设计表结构。

### merged log 在执行阶段生成

自动化测试 worker 在读取远程进程 stdout/stderr 时 SHALL 同步写入一份 merged log。每个日志片段保存：

- 顺序号或采集时间。
- stream: `STDOUT` 或 `STDERR`。
- 内容。

实现上可以继续保留 stdout.log 与 stderr.log 作为调试材料，但 agent 输入以 merged log 为主。禁止在任务结束后简单拼接 stdout.log 与 stderr.log 作为 merged log，因为这种方式无法恢复真实顺序。

### agent 负责测试统计提取

测试结果比较 prompt SHALL 明确要求 agent 输出 source/target 两侧测试统计：

- `totalTests`
- `executedTests`
- `passedTests`
- `failedTests`
- `skippedTests`
- `failedItems`
- `extractionConfidence`
- `testCountBasis`

当日志或报告无法可靠判断数量时，agent SHALL 返回 `null` 或低置信度，而不是编造数字。后端只校验结构和类型，不实现测试工具专用 parser。

### 结构化结果持久化

测试比较运行可以通过新增 JSON 字段或受控摘要字段保存两侧环境统计。差异项仍保存到 `test_comparison_findings`。如果采用 JSON 字段，字段只保存结构化摘要，不保存完整原始日志或完整 agent 输入。

### API 暴露分项结果但不暴露 secret

模型 profile 测试 API 响应 SHALL 返回 agent 类型、分项 probe 名称、状态、错误码、脱敏消息和测试时间。响应 MUST NOT 返回 API key、授权头、完整 agent 命令或服务器真实路径。

测试比较详情 API SHALL 返回结构化测试统计摘要和差异项引用，完整日志仍通过既有日志或 artifact 能力按权限查询。

## Risks / Trade-offs

- [Risk] agent 对测试数量的提取可能不准确。→ Mitigation: 输出 `extractionConfidence` 和 `testCountBasis`，不确定时允许返回 `null`。
- [Risk] merged log 体积增加。→ Mitigation: 继续复用日志大小控制、裁剪和 artifact 引用策略，agent 输入仍走确定性裁剪。
- [Risk] 模型 probe 执行时间增加。→ Mitigation: probe 使用最小 workspace 文件和短 prompt，按 profile 的测试超时限制运行。
- [Risk] 旧数据没有 merged log。→ Mitigation: 旧测试记录查询时可回退显示 stdout/stderr 摘要，但新比较优先使用 merged log；无 merged log 时记录输入降级摘要。
- [Risk] 部分模型基础调用可用但当前 agent probe 失败。→ Mitigation: 明确展示带 agent 类型的分项失败，不自动阻止保存 profile，但阶段绑定或运行时应能提示不兼容。
