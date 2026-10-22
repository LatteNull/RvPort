## ADDED Requirements

### Requirement: KB 扫描运行时必须使用 schema v2

KB 扫描任务 MUST 显式调用新版 KB Scanner 并请求 `schemaVersion: "2.0"` 的结果。

#### Scenario: 成功运行 schema v2 扫描

- **WHEN** 后端执行知识库扫描任务
- **THEN** 扫描命令 MUST 包含 `--schema-version 2.0`
- **AND** 后端 MUST 读取 `scan-result.json` 中的 `schemaVersion`
- **AND** 当版本为 `2.0` 时 MUST 继续导入 finding、保存 artifact 并完成任务
- **AND** 保存的扫描结果 artifact MUST 标记为 schema v2

#### Scenario: 拒绝非 schema v2 结果

- **WHEN** `scan-result.json` 缺失 `schemaVersion` 或版本不是 `2.0`
- **THEN** 后端 MUST 将任务标记为失败
- **AND** 错误信息 MUST 明确说明 KB Scanner 结果版本不兼容
- **AND** 后端 MUST NOT 按旧 v1 DTO 继续导入 finding

### Requirement: KB 扫描运行时必须逐条导入 schema v2 finding

KB 扫描结果导入 MUST 基于 v2 finding 的 `fact`、`conclusion`、`occurrences` 和 `evidenceChain` 建立查询投影。

#### Scenario: 导入带主位置的 finding

- **GIVEN** v2 finding 包含 `fact.primaryLocation`
- **WHEN** 后端导入扫描结果
- **THEN** 后端 MUST 将 `conclusion.severity` 投影为风险等级
- **AND** 后端 MUST 将 `conclusion.title` 投影为标题
- **AND** 后端 MUST 将 `fact.kind` 和 `conclusion.findingType` 投影为来源与类型
- **AND** 后端 MUST 将 `fact.primaryLocation.file`、起始行和结束行投影到可查询字段
- **AND** 后端 MUST 在 evidence 中保存完整 v2 finding payload

#### Scenario: 导入缺少主位置的 finding

- **GIVEN** v2 finding 没有 `fact.primaryLocation`
- **WHEN** 后端导入扫描结果
- **THEN** 后端 MUST 保留该 finding
- **AND** 位置投影字段 MAY 为空
- **AND** 完整 v2 finding payload MUST 仍保存在 evidence 中

#### Scenario: 导入结构化 diagnostics

- **GIVEN** v2 扫描结果包含结构化 diagnostics
- **WHEN** 后端保存扫描摘要和 artifact metadata
- **THEN** 后端 MUST 保留 diagnostics 的结构化内容或可审计摘要
- **AND** 后端 MUST NOT 假设 diagnostics 是字符串数组

### Requirement: KB 扫描结果必须继续支持报告纳入状态

schema v2 finding 导入后 MUST 继续支持用户确认、排除、报告纳入状态以及后续报告输入预览。

#### Scenario: 新 finding 进入报告候选

- **WHEN** v2 finding 被导入
- **THEN** 后端 MUST 按现有风险策略生成或刷新报告候选状态
- **AND** 列表接口 MUST 能返回该 finding 是否已纳入报告
- **AND** 用户后续手动排除或加入 MUST 作用于当前 finding 记录
