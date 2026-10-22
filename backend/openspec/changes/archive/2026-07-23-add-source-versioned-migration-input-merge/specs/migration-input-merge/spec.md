## ADDED Requirements

### Requirement: 迁移输入必须按源码版本隔离
系统 SHALL 为每个源码版本维护独立迁移输入集合，使旧源码版本的迁移输入不会自动进入新源码版本。

#### Scenario: 新源码版本迁移输入为空
- **WHEN** 项目成功创建新的 `source_revision`
- **THEN** 后端 SHALL 为该源码版本提供独立迁移输入集合
- **AND** 该集合初始 SHALL 不包含上一源码版本的迁移输入项

#### Scenario: 查询当前源码版本迁移输入
- **WHEN** 用户查询当前 active source revision 的迁移输入列表
- **THEN** 后端 SHALL 只返回该 `source_revision_id` 对应的迁移输入 reference
- **AND** 后端 MUST NOT 混入同项目其他源码版本的迁移输入 reference

### Requirement: 迁移输入列表必须使用 reference 记录统一展示
系统 SHALL 使用迁移输入 reference 记录统一展示不同来源的问题候选，并 SHALL 将真实来源详情保存在各来源原始结果表中。

#### Scenario: 展示迁移输入列表
- **WHEN** 用户查询迁移输入列表
- **THEN** 每条列表项 SHALL 包含问题、来源、风险或状态、路径或组件、建议处理和确认状态
- **AND** 每条列表项 SHALL 包含 `sourceType` 和 `sourceRefId`
- **AND** 列表接口 SHALL 支持分页、过滤和排序

#### Scenario: 查询迁移输入详情
- **WHEN** 用户查询单条迁移输入详情
- **THEN** 后端 SHALL 根据 `sourceType` 和 `sourceRefId` 回查真实来源记录
- **AND** 代码类来源 SHALL 返回对应 finding 详情和可用代码上下文
- **AND** SBOM 来源 SHALL 返回对应 SBOM result item 的结构化详情

### Requirement: 迁移输入必须支持批量导入真实来源记录
系统 SHALL 提供批量导入接口，允许前端传入同一来源类型下的一条或多条真实记录 ID 加入当前源码版本迁移输入。

#### Scenario: 批量导入 KB findings
- **WHEN** 用户提交 `sourceType=KB_FINDING` 和多个 finding ID
- **THEN** 后端 SHALL 校验每个 finding 属于当前项目
- **AND** 后端 SHALL 校验每个 finding 的 `source_revision_id` 等于 URL 中的 `sourceRevisionId`
- **AND** 后端 SHALL 为未导入过的 finding 创建迁移输入 reference

#### Scenario: 批量导入 SBOM results
- **WHEN** 用户提交 `sourceType=SBOM_RESULT` 和多个 SBOM result item ID
- **THEN** 后端 SHALL 校验每个 SBOM result item 属于当前项目
- **AND** 后端 SHALL 将创建出的迁移输入 reference 绑定到 URL 中的 `sourceRevisionId`
- **AND** 后端 MUST NOT 要求 `sbom_runs` 本身绑定源码版本

#### Scenario: 重复导入幂等跳过
- **WHEN** 同一个 input set 中已存在相同 `sourceType` 和 `sourceRefId` 的迁移输入 reference
- **THEN** 后端 SHALL 跳过重复创建
- **AND** 响应 SHALL 返回创建数量和重复跳过数量

### Requirement: 迁移输入必须支持自动合并当前前序结果
系统 SHALL 提供自动合并接口，用于从当前源码版本相关的当前分析节点结果批量生成迁移输入 reference。

#### Scenario: 自动合并代码类结果
- **WHEN** 用户选择知识库扫描、AI 扫描或弱弱内存模型扫描来源并执行自动合并
- **THEN** 后端 SHALL 基于当前 `sourceRevisionId` 查找对应来源的当前有效结果
- **AND** 后端 SHALL 将这些结果导入当前源码版本的迁移输入集合

#### Scenario: 自动合并 SBOM 替代性分析结果
- **WHEN** 用户选择 SBOM 替代性分析来源并执行自动合并
- **THEN** 后端 SHALL 基于当前项目查找当前有效 SBOM 分析结果
- **AND** 后端 SHALL 将 SBOM result items 导入 URL 中 `sourceRevisionId` 对应的迁移输入集合

#### Scenario: 自动合并不处理冲突
- **WHEN** 自动合并遇到重复或潜在冲突候选
- **THEN** 后端 SHALL 对重复项执行幂等跳过
- **AND** 后端 MUST NOT 在本期实现冲突检测或冲突解决

### Requirement: 迁移输入确认状态必须控制报告输入
系统 SHALL 只将人工确认后的迁移输入 reference 作为报告内容来源。

#### Scenario: 确认迁移输入
- **WHEN** 用户将迁移输入 reference 状态更新为 `CONFIRMED`
- **THEN** 后续报告生成 SHALL 可以使用该 reference 和其真实来源详情

#### Scenario: 排除迁移输入
- **WHEN** 用户将迁移输入 reference 状态更新为 `EXCLUDED`
- **THEN** 后续报告生成 MUST NOT 使用该 reference

#### Scenario: 候选迁移输入不进入报告
- **WHEN** 迁移输入 reference 状态为 `CANDIDATE`
- **THEN** 后续报告生成 MUST NOT 使用该 reference
