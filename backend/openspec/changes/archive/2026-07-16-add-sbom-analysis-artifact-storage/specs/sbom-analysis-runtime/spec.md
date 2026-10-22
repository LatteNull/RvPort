## ADDED Requirements

### Requirement: SBOM 分析成功后必须持久化结果明细和轻量 artifact
Java SBOM runtime SHALL 在 `SBOM_ANALYSIS` 成功完成后按行持久化分析结果明细，并生成轻量、非敏感、可审计的分析 artifact。

#### Scenario: 按行保存分析结果明细
- **WHEN** 分析器成功输出 package、library、tool 或 native file 对比结果
- **THEN** 后端 SHALL 将每条结果分别写入 `sbom_analysis_result_items`
- **AND** 每条结果 SHALL 关联对应 `project_id`、`task_id` 和 `sbom_run_id`
- **AND** 每条结果 SHALL 保存可用于分页、排序和过滤的普通列
- **AND** 后端 MUST NOT 将完整结果数组整体塞入单个 JSON 字段

#### Scenario: 生成审计摘要 artifact
- **WHEN** 分析器成功输出结果且后端完成结果明细导入
- **THEN** 后端 SHALL 生成 `AUDIT_SUMMARY_JSON` artifact
- **AND** artifact SHALL 包含运行 ID、项目 ID、任务 ID、源/目标环境摘要、源/目标快照摘要、组件数量、replacement status counts、risk counts、match counts、warnings 和工具信息
- **AND** artifact MAY 包含有限样本和结果列表查询入口
- **AND** artifact MUST NOT 保存完整结果明细数组
- **AND** artifact SHALL 关联对应 `project_id`、`task_id` 和 `sbom_run_id`

#### Scenario: 生成分析器输入摘要 artifact
- **WHEN** 后端准备分析器输入 JSON
- **THEN** 后端 SHALL 在成功路径中保存 `ANALYZER_INPUT_SUMMARY_JSON` artifact
- **AND** artifact SHALL 包含输入 schema version、源/目标快照 ID、采集范围、仓库策略和输入组件数量
- **AND** artifact MUST NOT 保存完整组件数组

#### Scenario: 生成分析器输出摘要 artifact
- **WHEN** 后端解析分析器输出 JSON
- **THEN** 后端 SHALL 在成功路径中保存 `ANALYZER_OUTPUT_SUMMARY_JSON` artifact
- **AND** artifact SHALL 包含输出 schema version、summary、warnings、tool、组件数量和候选数量
- **AND** artifact MAY 包含有限候选样本
- **AND** artifact MUST NOT 保存完整分析器输出原文

#### Scenario: 结果明细或 artifact 写入失败
- **WHEN** SBOM 分析结果明细或 artifact 写入失败
- **THEN** worker SHALL 将 `SBOM_ANALYSIS` 任务标记为 `FAILED`
- **AND** 后端 SHALL 将 `sbom_runs` 标记为 `FAILED`
- **AND** 后端 SHALL 保存脱敏失败摘要

### Requirement: SBOM artifact 内容必须使用白名单构造
SBOM artifact builder SHALL 使用字段白名单构造 artifact 内容，不得直接复制完整 analyzer input、analyzer output、raw snapshot 或任务日志。

#### Scenario: 过滤敏感内容
- **WHEN** 后端生成 SBOM artifact
- **THEN** artifact 内容 MUST NOT 包含明文凭据、私钥、token、passphrase 或完整任务日志
- **AND** artifact 内容 MUST NOT 包含服务器真实绝对路径
- **AND** artifact 内容 MUST NOT 包含未经筛选的 `raw_snapshot`

#### Scenario: 保存路径类信息
- **WHEN** artifact 需要表达工具路径、库路径或文件路径
- **THEN** 后端 SHALL 只保存远端采集到的非敏感路径、文件名、遮蔽路径、哈希或摘要
- **AND** 后端 MUST NOT 保存后端服务器本地 runtime 绝对路径

#### Scenario: 计算 artifact 摘要
- **WHEN** 后端保存 SBOM artifact
- **THEN** 后端 SHALL 基于实际写入的 JSON 内容计算 `sha256`
- **AND** 后端 SHALL 保存实际 JSON 字节数为 `size_bytes`
