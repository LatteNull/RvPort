## ADDED Requirements

### Requirement: 迁移输入必须支持依赖分析结果来源
迁移输入合并能力 SHALL 支持 `DEPENDENCY_RESULT` 来源，并 SHALL 在新流程中优先使用依赖分析结果替代 SBOM 结果。

#### Scenario: 批量导入依赖分析结果
- **WHEN** 用户提交 `sourceType=DEPENDENCY_RESULT` 和多个依赖分析结果 ID
- **THEN** 后端 SHALL 校验每个结果属于当前项目
- **AND** 后端 SHALL 校验每个结果的 `sourceRevisionId` 等于 URL 中的 `sourceRevisionId`
- **AND** 后端 SHALL 为未导入过的结果创建迁移输入 reference

#### Scenario: 自动合并依赖分析结果
- **WHEN** 用户选择依赖分析来源并执行自动合并
- **THEN** 后端 SHALL 基于当前 `sourceRevisionId` 查找当前有效依赖分析结果
- **AND** 后端 SHALL 将这些结果导入当前源码版本的迁移输入集合

#### Scenario: 历史 SBOM 输入兼容
- **WHEN** 用户查询或查看历史 `SBOM_RESULT` 迁移输入
- **THEN** 后端 SHALL 保留历史展示和详情回查能力
- **AND** 新流程自动合并 SHALL 默认不再使用 `SBOM_RESULT`

#### Scenario: 依赖分析展示字段
- **WHEN** 后端创建 `DEPENDENCY_RESULT` 迁移输入 reference
- **THEN** `detectedLevel` SHALL 使用 `riskLevel + "/" + targetMatchStatus`
- **AND** `locationLabel` SHALL 表达构建工具、包、库或测试依赖位置
- **AND** 详情 SHALL 能回查依赖分析结果 evidence
