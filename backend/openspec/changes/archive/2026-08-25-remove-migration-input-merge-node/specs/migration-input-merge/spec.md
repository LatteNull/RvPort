## MODIFIED Requirements

### Requirement: 迁移输入必须按源码版本隔离
系统 SHALL 为每个源码版本维护独立迁移输入集合，使旧源码版本的迁移输入不会自动进入新源码版本。该集合 SHALL 作为各分析节点确认结果的后端 reference 容器，而不是独立合并节点的业务页面状态。

#### Scenario: 新源码版本迁移输入为空
- **WHEN** 项目成功创建新的 `source_revision`
- **THEN** 后端 SHALL 为该源码版本提供独立迁移输入集合
- **AND** 该集合初始 SHALL 不包含上一源码版本的迁移输入项

#### Scenario: 查询当前源码版本迁移输入
- **WHEN** 用户查询当前 active source revision 的迁移输入列表
- **THEN** 后端 SHALL 只返回该 `source_revision_id` 对应的迁移输入 reference
- **AND** 后端 MUST NOT 混入同项目其他源码版本的迁移输入 reference

### Requirement: 迁移输入列表必须使用 reference 记录统一展示
系统 SHALL 使用迁移输入 reference 记录统一展示不同来源的问题候选，并 SHALL 将真实来源详情保存在各来源原始结果表中。该列表 SHALL 作为节点内确认和报告输入审计的后端能力，不再要求独立迁移输入合并页面。

#### Scenario: 展示迁移输入列表
- **WHEN** 用户查询迁移输入列表
- **THEN** 每条列表项 SHALL 包含问题、来源、风险或状态、路径或组件、建议处理和确认状态
- **AND** 每条列表项 SHALL 包含 `sourceType` 和 `sourceRefId`
- **AND** 列表接口 SHALL 支持分页、过滤和排序

#### Scenario: 查询迁移输入详情
- **WHEN** 用户查询单条迁移输入详情
- **THEN** 后端 SHALL 根据 `sourceType` 和 `sourceRefId` 回查真实来源记录
- **AND** 代码类来源 SHALL 返回对应 finding 详情和可用代码上下文
- **AND** 依赖分析来源 SHALL 返回对应依赖分析结果详情和 evidence
- **AND** 历史 `SBOM_RESULT` 来源 MAY 返回对应 SBOM result item 的结构化详情

### Requirement: 迁移输入必须支持批量导入真实来源记录
系统 SHALL 提供批量导入接口，允许各分析节点传入同一来源类型下的一条或多条真实记录 ID 加入当前源码版本迁移输入。该接口 SHALL 作为节点内确认动作的后端能力，不再作为独立合并节点主流程入口。

#### Scenario: 批量导入 KB findings
- **WHEN** 用户提交 `sourceType=KB_FINDING` 和多个 finding ID
- **THEN** 后端 SHALL 校验每个 finding 属于当前项目
- **AND** 后端 SHALL 校验每个 finding 的 `source_revision_id` 等于 URL 中的 `sourceRevisionId`
- **AND** 后端 SHALL 为未导入过的 finding 创建迁移输入 reference
- **AND** 默认确认状态 SHALL 按 finding severity 归一化后的风险等级决定

#### Scenario: 批量导入依赖分析结果
- **WHEN** 用户提交 `sourceType=DEPENDENCY_RESULT` 和多个依赖分析结果 ID
- **THEN** 后端 SHALL 校验每个结果属于当前项目
- **AND** 后端 SHALL 校验每个结果的 `sourceRevisionId` 等于 URL 中的 `sourceRevisionId`
- **AND** 后端 SHALL 为未导入过的结果创建迁移输入 reference
- **AND** 默认确认状态 SHALL 按依赖分析 `riskLevel` 决定

#### Scenario: 拒绝新流程导入 SBOM results
- **WHEN** 新流程提交 `sourceType=SBOM_RESULT` 批量导入
- **THEN** 后端 SHALL 拒绝请求或返回 deprecated 业务错误
- **AND** 后端 MUST NOT 为新流程创建新的 `SBOM_RESULT` reference

#### Scenario: 重复导入幂等跳过
- **WHEN** 同一个 input set 中已存在相同 `sourceType` 和 `sourceRefId` 的迁移输入 reference
- **THEN** 后端 SHALL 跳过重复创建
- **AND** 响应 SHALL 返回创建数量和重复跳过数量

### Requirement: 迁移输入确认状态必须控制报告输入
系统 SHALL 只将状态为 `CONFIRMED` 的迁移输入 reference 作为报告内容来源。状态 MAY 由默认风险规则生成，也 MAY 由用户在来源节点内人工调整。

#### Scenario: 确认迁移输入
- **WHEN** 用户将迁移输入 reference 状态更新为 `CONFIRMED`
- **THEN** 后续报告生成 SHALL 可以使用该 reference 和其真实来源详情

#### Scenario: 排除迁移输入
- **WHEN** 用户将迁移输入 reference 状态更新为 `EXCLUDED`
- **THEN** 后续报告生成 MUST NOT 使用该 reference

#### Scenario: 候选迁移输入不进入报告
- **WHEN** 迁移输入 reference 状态为 `CANDIDATE`
- **THEN** 后续报告生成 MUST NOT 使用该 reference

## REMOVED Requirements

### Requirement: 迁移输入必须支持自动合并当前前序结果
**Reason**: 独立迁移输入合并节点不再作为主流程存在，确认动作下沉到各分析节点内，自动合并入口会造成额外页面和重复状态管理。

**Migration**: 各分析节点在任务完成后创建或维护自己的 migration input reference，并在节点列表中提供人工加入和撤回能力。

### Requirement: 迁移输入必须支持依赖分析结果来源
**Reason**: 该能力不再属于“迁移输入合并节点”。依赖分析仍是新主流程来源，但它应由依赖分析节点内确认能力承载。

**Migration**: 使用 `node-local-migration-input-confirmation` 和 `dependency-analysis-runtime` 中的节点内确认要求表达依赖分析进入报告的规则。
