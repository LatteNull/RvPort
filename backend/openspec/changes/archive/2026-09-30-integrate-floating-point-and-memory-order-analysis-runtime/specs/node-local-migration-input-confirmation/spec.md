## ADDED Requirements

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
