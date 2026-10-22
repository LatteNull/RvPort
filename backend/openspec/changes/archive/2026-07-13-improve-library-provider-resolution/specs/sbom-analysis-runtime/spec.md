## ADDED Requirements

### Requirement: SBOM 分析必须使用 provider 证据匹配库替代
SBOM 分析器 SHALL 优先使用源侧 owner package、目标侧 provider/whatprovides 证据和仓库候选生成库替代结果。

#### Scenario: 源侧库存在 owner package
- **WHEN** 分析器输入中的源侧 `.so` 组件包含 owner package metadata
- **THEN** 分析器 SHALL 将 owner package 作为优先匹配线索
- **AND** 分析器 SHALL 在候选 evidence 中记录 owner package 名称、版本和架构

#### Scenario: 目标侧已安装组件提供同名库
- **WHEN** 目标已安装组件 metadata 表明某个包提供源侧库或其归一化候选
- **THEN** 分析器 SHALL 生成 `TARGET_PRESENT` 候选
- **AND** 候选 SHALL 记录匹配依据为 installed provider evidence
- **AND** 候选 SHALL 给出 confidence

#### Scenario: 目标仓库提供库文件
- **WHEN** 目标仓库组件或 `REPOSITORY_PROVIDE` 记录命中源侧库、normalized name 或 query pattern
- **THEN** 分析器 SHALL 生成 `DIRECT_AVAILABLE` 或 `UPGRADE_AVAILABLE` 候选
- **AND** 候选 SHALL 记录匹配依据为 repository provides evidence
- **AND** 候选 SHALL 包含目标包名、路径或 provides pattern 摘要

### Requirement: SBOM 分析必须处理架构归一化候选
SBOM 分析器 SHALL 使用环境采集生成的架构归一化候选进行跨架构匹配，并保留原始事实与匹配置信度。

#### Scenario: 使用 normalized library name 查询候选
- **WHEN** 源侧库组件包含 normalized library name
- **THEN** 分析器 SHALL 使用 normalized library name 与目标已安装库、目标仓库 provides 和目标包候选匹配
- **AND** 分析器 SHALL 在结果 evidence 中保存原始库名和 normalized library name

#### Scenario: 使用架构替换后的 package candidate
- **WHEN** 源侧组件包含替换为目标架构 token 的 package candidate
- **THEN** 分析器 SHALL 使用该候选查询目标仓库包
- **AND** 命中结果 SHALL 标记为 normalized package match
- **AND** confidence SHALL 低于精确 owner package 或 exact provides 命中

#### Scenario: 归一化候选未命中
- **WHEN** 原始名称、owner package、normalized name 和 package candidates 均未命中目标已安装或仓库组件
- **THEN** 分析器 SHALL 保持 `SOURCE_BUILD_REQUIRED`、`NO_ALTERNATIVE` 或 `MANUAL_CONFIRM_REQUIRED` 结论
- **AND** 分析器 SHALL 在 evidence 中说明 provider evidence 不足或仓库候选不可用

### Requirement: SBOM 分析必须表达仓库证据完整性
SBOM 分析结果 SHALL 表达目标仓库 metadata refresh、repoquery 和 provides 查询是否完整，以便前端解释结果可信度。

#### Scenario: 仓库 metadata 可用
- **WHEN** 目标快照表明仓库 metadata refresh 成功且 repository packages/provides 已采集
- **THEN** 分析器 SHALL 将仓库证据状态标记为完整或部分完整
- **AND** 分析摘要 SHALL 包含 repository evidence counters

#### Scenario: 仓库 metadata 不可用
- **WHEN** 目标快照包含 metadata refresh 失败或 repository scanner warning
- **THEN** 分析器 SHALL 在 warnings 中返回仓库证据不完整摘要
- **AND** 分析器 SHALL 避免把缺少仓库证据等同于目标无替代包

#### Scenario: provider 证据不足
- **WHEN** 源侧或目标侧缺少 owner package、whatprovides 或 normalized metadata
- **THEN** 分析器 SHALL 降低相关候选 confidence
- **AND** 分析器 SHALL 在 evidence 中标明匹配依据来自弱名称匹配
