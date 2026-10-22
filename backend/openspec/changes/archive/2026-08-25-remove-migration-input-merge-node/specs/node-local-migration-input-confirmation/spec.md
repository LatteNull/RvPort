## ADDED Requirements

### Requirement: 分析节点必须内置迁移输入确认
系统 SHALL 将迁移输入的确认、撤回和人工加入能力放在各分析节点结果列表中，而不是要求用户进入独立迁移输入合并节点。

#### Scenario: 节点内确认结果
- **WHEN** 用户在 KB 扫描或依赖分析结果列表中确认某条结果进入报告
- **THEN** 后端 SHALL 为该结果创建或更新对应 `migration_input_refs`
- **AND** reference 状态 SHALL 为 `CONFIRMED`
- **AND** 后续报告生成 SHALL 可以读取该 reference

#### Scenario: 节点内撤回结果
- **WHEN** 用户在 KB 扫描或依赖分析结果列表中撤回某条已进入报告的结果
- **THEN** 后端 SHALL 将对应 reference 状态更新为 `EXCLUDED`
- **AND** 后续报告生成 MUST NOT 读取该 reference

#### Scenario: 低风险人工加入
- **WHEN** 用户在节点结果列表中人工加入 `LOW` 风险结果
- **THEN** 后端 SHALL 将对应 reference 状态更新为 `CONFIRMED`
- **AND** 后续报告生成 SHALL 可以读取该 reference

### Requirement: 迁移输入默认状态必须由风险等级决定
系统 SHALL 在节点结果自动创建 migration input reference 时，根据归一化风险等级设置默认确认状态。

#### Scenario: 默认进入报告的风险等级
- **WHEN** 后端为 `CRITICAL`、`HIGH`、`MEDIUM`、`INFO` 或 `COMMENT` 风险结果创建 reference
- **THEN** reference 状态 SHALL 默认为 `CONFIRMED`
- **AND** 用户 SHALL 能人工撤回为 `EXCLUDED`

#### Scenario: 默认不进入报告的低风险等级
- **WHEN** 后端为 `LOW` 风险结果创建 reference
- **THEN** reference 状态 SHALL 默认为 `CANDIDATE`
- **AND** 用户 SHALL 能人工加入为 `CONFIRMED`

#### Scenario: 依赖分析组合 detected level
- **WHEN** 依赖分析结果的 `detectedLevel` 使用 `riskLevel + "/" + targetMatchStatus`
- **THEN** 默认确认判断 SHALL 只使用 `/` 前的风险等级
- **AND** `detectedLevel` 展示值 SHALL 保留完整组合值

#### Scenario: 风险等级归一化
- **WHEN** 来源结果风险等级使用小写或混合大小写
- **THEN** 后端 SHALL 归一化为 `CRITICAL`、`HIGH`、`MEDIUM`、`LOW`、`INFO` 或 `COMMENT`
- **AND** 未知风险等级 SHALL 使用受控默认值并记录可审计信息

### Requirement: SBOM 不得作为新流程前序来源
系统 SHALL 不再将 SBOM 分析结果作为新迁移输入确认流程的前序来源。

#### Scenario: 新流程不创建 SBOM reference
- **WHEN** 新流程自动维护迁移输入 reference
- **THEN** 后端 MUST NOT 自动创建 `sourceType=SBOM_RESULT` 的 reference
- **AND** 节点内确认入口 MUST NOT 展示 SBOM 作为可选前序来源

#### Scenario: 历史 SBOM reference 兼容
- **WHEN** 用户查看历史报告或历史迁移输入中已有 `SBOM_RESULT`
- **THEN** 后端 MAY 保留历史详情读取能力
- **AND** 后端 MUST NOT 将历史兼容解释为新流程可选前序能力
