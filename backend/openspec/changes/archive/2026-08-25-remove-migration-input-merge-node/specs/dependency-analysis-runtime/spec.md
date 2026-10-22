## ADDED Requirements

### Requirement: 依赖分析节点必须支持本节点确认进入报告
依赖分析运行时 SHALL 支持在依赖分析节点内将依赖分析结果加入、撤回或确认为报告输入。

#### Scenario: 依赖结果默认确认
- **WHEN** 依赖分析任务成功写入结果项
- **AND** 结果 riskLevel 为 `CRITICAL`、`HIGH`、`MEDIUM`、`INFO` 或 `COMMENT`
- **THEN** 后端 SHALL 创建或维护对应 `DEPENDENCY_RESULT` migration input reference
- **AND** reference 状态 SHALL 默认为 `CONFIRMED`

#### Scenario: 依赖结果低风险默认候选
- **WHEN** 依赖分析任务成功写入结果项
- **AND** 结果 riskLevel 为 `LOW`
- **THEN** 后端 SHALL 创建或维护对应 `DEPENDENCY_RESULT` migration input reference
- **AND** reference 状态 SHALL 默认为 `CANDIDATE`

#### Scenario: 依赖节点人工撤回
- **WHEN** 用户在依赖分析节点撤回某个结果项
- **THEN** 后端 SHALL 将对应 migration input reference 状态更新为 `EXCLUDED`
- **AND** 报告生成 MUST NOT 使用该依赖结果

#### Scenario: 依赖节点人工加入低风险
- **WHEN** 用户在依赖分析节点人工加入 `LOW` 结果项
- **THEN** 后端 SHALL 将对应 migration input reference 状态更新为 `CONFIRMED`
- **AND** 报告生成 SHALL 可以使用该依赖结果

#### Scenario: SBOM 不再作为依赖前序
- **WHEN** 依赖分析结果进入迁移输入流程
- **THEN** 后端 SHALL 使用 `sourceType=DEPENDENCY_RESULT`
- **AND** 后端 MUST NOT 同时创建 `SBOM_RESULT` reference
