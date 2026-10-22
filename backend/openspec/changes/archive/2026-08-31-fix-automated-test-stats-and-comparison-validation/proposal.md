## Why

当前自动化测试比较任务会把 Codex agent 的 transcript 当作最终 JSON 解析，导致提示词中的 schema 示例和占位符被保存为成功比较结果。`test2` 项目已经出现 x86 测试成功、riscv 测试失败但比较结果落库为 `summary="..."`、`status="SUCCEEDED|FAILED|..."` 的无效数据。

## What Changes

- 调整测试结果比较 agent 的输出契约：agent 必须在专用 workspace 写出固定 JSON 文件，后端优先读取这些文件，而不是从 stdout/stderr/mergedOutput transcript 中截取 JSON。
- 后端保存 agent 原始输出 artifact 时同时保存 stdout、stderr、mergedOutput 和读取到的 JSON 文件内容，便于审计。
- 增强测试比较结果语义校验，拒绝 schema 占位符、组合枚举字符串、`...` 摘要、非法状态值、非法差异类型和缺失关键字段。
- 当 agent 未写出有效 JSON 文件或 JSON 校验失败时，比较运行 SHALL 标记为 `FAILED`，不得落库为 `SUCCEEDED`。
- 自动化测试记录继续保存退出码、状态、日志引用、报告 artifact 和输出摘要；测试数量、通过数、失败数和跳过数仍允许为空，避免在后端引入面向不同测试工具的 parser。
- 修正提示词中的示例表达，避免用 `"A|B|C"` 作为字段值示例，改为说明枚举必须是单个值。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `test-result-comparison-runtime`: 修改测试比较 agent 输出契约、结果读取方式和结果校验要求。
- `automated-test-runtime`: 澄清自动化测试本身不负责解析用例统计，但必须提供足够日志与报告引用供比较 agent 生成统计。
- `api-e2e-test-suite`: 增加针对自动化测试比较输出文件、无效 agent 输出拒绝、x86 成功/riscv 失败场景的 E2E 覆盖。

## Impact

- 影响后端测试比较运行时、agent runtime adapter 调用方式、测试比较输出解析与校验逻辑。
- 影响 `TEST_LOG_COMPARE` 任务失败/成功判定。
- 影响测试比较 API 返回数据质量：无效 agent 输出不再作为成功结果返回。
- 不修改前端代码，不改变自动化测试创建 API 的基本形态。
