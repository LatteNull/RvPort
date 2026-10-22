# node-local-migration-input-confirmation Specification

## Purpose
节点内迁移输入确认能力用于把 KB 扫描和依赖分析等节点的结果直接确认为报告输入，避免独立合并节点带来的重复页面和状态管理。
## Requirements
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

### Requirement: 节点结果列表必须暴露迁移输入确认状态
可进入报告的节点结果列表 SHALL 直接返回节点结果对应的 migration input reference 状态，供前端展示确认、撤回和报告纳入信息。

#### Scenario: 节点结果存在 reference
- **WHEN** 节点结果存在同一源码版本、同一 `sourceType`、同一 `sourceRefId` 的 migration input reference
- **THEN** 节点结果响应 SHALL 返回 `migrationInputRefId`
- **AND** 节点结果响应 SHALL 返回 `migrationInputStatus`
- **AND** `confirmedForNextReport` SHALL 根据 reference 状态是否为 `CONFIRMED` 计算

#### Scenario: 节点结果不存在 reference
- **WHEN** 节点结果没有对应 migration input reference
- **THEN** 节点结果响应 SHALL 返回 `migrationInputRefId=null`
- **AND** 节点结果响应 SHALL 返回 `confirmedForNextReport=false`
- **AND** 用户 SHALL 仍可通过节点内确认 API 创建 reference

#### Scenario: 节点结果已经进入最新报告
- **WHEN** 节点结果对应的 migration input reference 已存在于当前源码版本最新成功报告的 `report_inputs`
- **THEN** 节点结果响应 SHALL 返回 `includedInLatestReport=true`
- **AND** 节点结果响应 SHALL 返回对应 `latestReportId`

### Requirement: 专项分析 Finding 必须支持节点内确认
系统 SHALL 为浮点 Finding 和内存序 Finding 创建独立 migration input reference，并 SHALL 在各自 Finding 列表和详情中返回确认状态。

#### Scenario: 自动创建浮点 reference
- **WHEN** 浮点分析成功导入 Finding
- **THEN** 后端 SHALL 使用 `sourceType=FLOATING_POINT_FINDING` 和 Finding ID 创建 reference

#### Scenario: 自动创建内存序 reference
- **WHEN** 内存序分析成功导入正式 risk 或可展示 source candidate
- **THEN** 后端 SHALL 使用 `sourceType=MEMORY_ORDER_FINDING` 和 Finding ID 创建 reference
- **AND** reference 摘要 SHALL 区分 risk 与 source candidate

#### Scenario: 节点内人工加入或撤回
- **WHEN** 用户确认、加入或撤回某条专项分析 Finding
- **THEN** 后端 SHALL 更新对应 reference
- **AND** 后续报告 SHALL 只读取 CONFIRMED reference

### Requirement: 专项 Finding 必须沿用全局风险默认策略
系统 SHALL 将工具风险归一化为 CRITICAL、HIGH、MEDIUM、LOW、INFO 或 COMMENT，并 SHALL 使用现有默认确认策略。

#### Scenario: 非低风险默认确认
- **WHEN** Finding 风险为 CRITICAL、HIGH、MEDIUM 或 INFO
- **THEN** reference SHALL 默认为 CONFIRMED
- **AND** 用户 SHALL 能撤回为 EXCLUDED

#### Scenario: 低风险默认候选
- **WHEN** Finding 风险为 LOW
- **THEN** reference SHALL 默认为 CANDIDATE
- **AND** 用户 SHALL 能人工加入为 CONFIRMED

#### Scenario: 不确定候选风险映射
- **WHEN** memory-order source candidate 没有合法风险等级
- **THEN** 后端 SHALL 使用 INFO 作为受控展示风险并保留原 verdict/status
- **AND** MUST NOT 把候选提升为已证明风险
