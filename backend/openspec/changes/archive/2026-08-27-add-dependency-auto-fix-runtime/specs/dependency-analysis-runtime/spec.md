## ADDED Requirements

### Requirement: 依赖分析结果必须支持自动修复候选派生
依赖分析运行时 SHALL 为依赖自动修复提供稳定的结果字段和候选派生规则，使后端可以基于分析结果判断哪些依赖可以尝试在目标环境安装。

#### Scenario: 派生中风险自动修复候选
- **WHEN** 依赖分析结果 `riskLevel=MEDIUM`
- **AND** 结果存在 `targetProviderPackage`
- **THEN** 该结果 SHALL 可作为自动修复候选项
- **AND** 候选项 SHALL 使用目标侧 provider package/version 作为优先安装依据

#### Scenario: 派生高风险自动修复候选
- **WHEN** 依赖分析结果 `riskLevel=HIGH`
- **AND** 结果存在 `sourceProviderPackage`
- **THEN** 该结果 SHALL 可作为自动修复候选项展示
- **AND** 候选项 SHALL 默认不选中
- **AND** 候选项 SHALL 使用源侧 package name 和 source major version 作为目标源匹配依据

#### Scenario: 保持依赖分析结果只读
- **WHEN** 用户创建依赖自动修复任务
- **THEN** 后端 MUST NOT 修改原依赖分析结果项的 `riskLevel`、`targetMatchStatus`、provider 字段或 evidence
- **AND** 自动修复的安装计划和执行结果 SHALL 写入自动修复运行表和条目表

#### Scenario: 修复后重新分析生成新结果
- **WHEN** 依赖自动修复完成后触发新的依赖分析
- **THEN** 新依赖分析 SHALL 创建独立的依赖分析运行和结果项
- **AND** 原依赖分析运行和结果项 SHALL 作为历史记录保留
