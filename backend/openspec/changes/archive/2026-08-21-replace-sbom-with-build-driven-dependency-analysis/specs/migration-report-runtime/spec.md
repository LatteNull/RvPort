## ADDED Requirements

### Requirement: 迁移报告必须支持依赖分析输入
迁移评估报告 SHALL 在新流程中使用 confirmed 的 `DEPENDENCY_RESULT` 迁移输入生成依赖替代性说明，并 SHALL 保留历史 SBOM 输入快照兼容。

#### Scenario: 生成报告读取依赖分析输入
- **WHEN** 报告生成任务读取 confirmed migration input reference
- **AND** reference 的 `sourceType` 为 `DEPENDENCY_RESULT`
- **THEN** 后端 SHALL 回查依赖分析结果明细
- **AND** 报告 SHALL 展示依赖类型、目标匹配状态、风险等级、建议和 evidence 摘要

#### Scenario: 报告摘要统计依赖缺口
- **WHEN** 报告生成任务完成
- **THEN** 报告摘要 SHALL 统计依赖分析输入总数、按风险等级统计、按目标匹配状态统计和主要依赖风险
- **AND** 依赖替代性注意点 SHALL 优先来自 `DEPENDENCY_RESULT`

#### Scenario: 历史 SBOM 报告兼容
- **WHEN** 用户查看历史报告且报告输入快照中包含 `SBOM_RESULT`
- **THEN** 后端 SHALL 继续使用报告生成时保存的输入快照展示
- **AND** 后端 MUST NOT 因 SBOM deprecated 而破坏历史报告下载或详情查询
