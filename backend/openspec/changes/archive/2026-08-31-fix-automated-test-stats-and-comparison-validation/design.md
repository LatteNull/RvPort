## Context

`test2` 项目暴露了测试结果比较链路的一个确定性缺陷：`AUTOMATED_TEST` 两侧完成后确实自动触发了 `TEST_LOG_COMPARE`，但比较结果保存了提示词中的 schema 占位符，而不是 agent 最终生成的真实 JSON。当前实现从 Codex CLI 的 `mergedOutput` 中截取第一个 `{` 到最后一个 `}`，而 `mergedOutput` 同时包含 prompt、工具执行 transcript、stdout 和 stderr，天然不适合作为唯一结构化结果来源。

自动化测试已有约束是不为每种测试工具实现专用 parser。因此，本 change 不把 CTest、pytest、JUnit 等日志解析固化到后端业务逻辑中，而是把结构化统计仍交给 agent，同时加强输出契约和校验边界。

## Goals / Non-Goals

**Goals:**

- 让测试结果比较 agent 将最终结果写入固定 JSON 文件，后端读取文件作为结构化结果来源。
- 保存 agent stdout、stderr、mergedOutput 和 JSON 文件内容，保证失败时可审计。
- 增加严格语义校验，防止 schema 示例、占位符和组合枚举值被保存为成功结果。
- 保留自动化测试原有职责：保存退出码、状态、日志引用和报告 artifact，不做测试工具专用 parser。
- 增加单元测试和 E2E 覆盖，验证 x86 成功、riscv 失败时仍能得到可用比较或明确失败。

**Non-Goals:**

- 不修改前端页面。
- 不引入 `test_cases` 或用例级持久化表。
- 不实现面向 CTest、pytest、JUnit、Maven Surefire 等测试框架的后端专用 parser。
- 不重跑历史无效比较结果；历史数据可在后续维护任务中清理或重新生成。

## Decisions

### 1. Agent 输出改为文件契约

agent workspace 中固定要求输出：

- `comparison-result.json`：唯一的结构化比较结果。
- 可选 `comparison-notes.txt`：非结构化说明，后端只保存为诊断材料，不参与业务字段解析。

后端执行 agent 后先读取 `comparison-result.json`。只有文件不存在时，才允许从 stdout 中提取 fenced JSON 作为兼容降级；不得从 `mergedOutput` 中直接截取 JSON 作为正常路径。

选择原因：CLI transcript 中会包含 prompt、工具输出、用户消息和 agent 文本说明，结构化结果应该和 transcript 解耦。文件契约能显著降低解析错误。

### 2. stdout/stderr/mergedOutput 只作为诊断 artifact

`AGENT_OUTPUT` artifact 保存以下字段：

- `stdout`
- `stderr`
- `mergedOutput`
- `exitCode`
- `timedOut`
- `agentType`
- `agentRuntimeId`
- `resultFilePresent`
- `resultFileContent`
- `parseSource`

其中 `resultFileContent` 是后端实际用于解析的内容。API 普通详情仍不直接返回完整 transcript。

### 3. 严格校验结构和语义

后端 SHALL 校验：

- 顶层必须包含单值枚举 `overallStatus`、`riskLevel`。
- `sourceStats.status` 和 `targetStats.status` 必须是单个合法状态，不能是 `A|B|C`。
- `findings[].differenceType` 和 `findings[].severity` 必须是单个合法值。
- `summary`、`recommendation`、`testCountBasis`、finding 文本字段不得为 `...`、空模板或明显 schema 占位符。
- 统计数字允许为 `null`，但不能是非法字符串。
- `confidence` 和 `extractionConfidence` 必须在 `[0, 1]`。

校验失败时，`test_comparison_runs.status=FAILED`，`error_code=TEST_COMPARE_AGENT_OUTPUT_INVALID`。

### 4. 提示词只描述 schema，不把枚举组合写成字段值

提示词不再使用：

```json
"status": "SUCCEEDED|FAILED|CANCELLED|TIMEOUT|UNKNOWN"
```

改为说明：

```text
status 必须是以下单个字符串之一：SUCCEEDED、FAILED、CANCELLED、TIMEOUT、UNKNOWN。
```

这样可以降低模型照抄模板的概率。即便模型仍照抄，后端校验也会拒绝。

### 5. 自动化测试统计字段暂不由后端 parser 填充

`test_runs.passed_count`、`failed_count`、`skipped_count` 继续允许为空。测试统计展示主要来自 `test_comparison_runs.source_test_stats` 和 `target_test_stats`。如果后续要做规则 parser，应另开 change 明确破坏当前“后端不为不同测试工具实现专用 parser”的边界。

## Risks / Trade-offs

- [Risk] 某些 agent 不支持写文件或不遵守文件输出契约。→ Mitigation：模型 profile 的 agent probe 需要覆盖 workspace 写文件能力；运行时缺失文件则明确失败，不再伪成功。
- [Risk] 过严校验导致部分可读但格式不完美的输出失败。→ Mitigation：错误会保存原始 artifact，用户可以审计；后续可基于真实失败样本调整 schema。
- [Risk] stdout 降级解析仍可能误读。→ Mitigation：只允许从 stdout 提取 fenced JSON 或最后一个完整 JSON，并且必须通过语义校验；`mergedOutput` 不作为正常解析来源。
- [Risk] 历史无效比较结果仍留在数据库中。→ Mitigation：本 change 不做历史迁移；可通过后续维护脚本按占位符特征标记失败或重新比较。
