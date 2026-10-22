## ADDED Requirements

### Requirement: SBOM result items 必须可加入迁移输入
SBOM 分析结果明细 SHALL 能作为迁移输入 reference 的来源，但 SBOM run 本身 SHALL 继续保持环境分析维度，不强制绑定源码版本。

#### Scenario: SBOM result 导入迁移输入
- **WHEN** 用户将 SBOM result item 加入迁移输入
- **THEN** 后端 SHALL 校验该 result item 属于当前项目
- **AND** 后端 SHALL 将创建出的迁移输入 reference 绑定到 URL 中的 `sourceRevisionId`
- **AND** 后端 MUST NOT 要求 `sbom_runs` 或 `sbom_analysis_result_items` 持有 `source_revision_id`

#### Scenario: SBOM detected level
- **WHEN** 后端为 SBOM result item 创建迁移输入 reference
- **THEN** `detectedLevel` SHALL 使用 `riskLevel + "/" + targetMatchStatus`
- **AND** 示例值 MAY 为 `HIGH/SOURCE_BUILD_REQUIRED` 或 `LOW/TARGET_PRESENT`

#### Scenario: SBOM location label
- **WHEN** 后端为 SBOM result item 创建迁移输入 reference
- **THEN** 软件包条目 SHALL 使用 `package:name@version`
- **AND** 独立库文件 SHALL 使用 `lib:path`
- **AND** native 文件 SHALL 使用 `native:path`
- **AND** 工具条目 SHALL 使用 `tool:name@version`
- **AND** 缺少版本或路径时 SHALL 使用可用的组件名称 fallback

#### Scenario: SBOM 详情查询保留结构化字段
- **WHEN** 用户查询 SBOM 来源的迁移输入详情
- **THEN** 后端 SHALL 返回对应 SBOM result item 的 `riskLevel`、`targetMatchStatus`、源组件摘要、目标候选摘要、匹配策略、建议和证据
- **AND** 响应 MUST NOT 暴露明文凭据、完整 analyzer output 或服务器真实路径
