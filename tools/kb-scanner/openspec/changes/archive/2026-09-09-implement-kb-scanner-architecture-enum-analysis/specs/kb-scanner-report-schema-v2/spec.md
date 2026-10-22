## ADDED Requirements

### Requirement: Schema V2 必须在 Finding 内自包含展示架构枚举链路
Schema V2 Projector SHALL 将架构枚举结论投影为 `fact.kind=architecture_probe`，并 SHALL 使用现有 `source_evidence` step 与 `defines`、`contains`、`selects`、`guarded_by`、`matches_knowledge`、`classified_as` edge 表达 enum declaration、member、reference、condition 和 downstream dependency。enum 特有字段 SHALL 位于合法 `org.rvport.kb-scanner.architecture-enum` extension；Projector MUST NOT 增加未经 schema 定义的核心 fact/step/edge kind 或要求消费者读取内部 snapshots。

#### Scenario: 用户查看 constexpr 架构枚举 Finding
- **WHEN** v2 Projector 接收完整 enum selection Classification
- **THEN** 单个 Finding SHALL 展示 enum 定义、member declaration/reference、condition、下游 x86 Evidence、Knowledge、Classification 和 Assessment impact
- **AND** 每个代码 step SHALL 携带自己的完整 span、真实行号上下文和命中高亮

#### Scenario: 枚举链路只有候选证据
- **WHEN** enum member/reference 可验证但 downstream 或 target selection 仍未知
- **THEN** Finding conclusion 与 evidenceChain SHALL 标记 unknown/partial，包含稳定 break 和 reason
- **AND** summary MUST NOT 将其计为 blocking 或从其缺失推断 ready

#### Scenario: 旧 V2 consumer 忽略 enum extension
- **WHEN** consumer 不认识 `org.rvport.kb-scanner.architecture-enum` extension
- **THEN** consumer SHALL 仍能依据 Schema V2 核心 `architecture_probe`、`source_evidence`、source/context 和既有 edges 验证并展示 Finding
- **AND** extension MUST NOT 覆盖或改变核心字段、引用与状态语义

#### Scenario: 多个成员引用聚合为一个根因
- **WHEN** 同一 enum member 根因在多个 condition/case 位置被引用
- **THEN** Finding SHALL 无损保留全部 occurrences，确定性选择 primary occurrence，并在 chain 中保留各自上下文
- **AND** Finding 计数与 occurrence 计数 MUST 保持区分

#### Scenario: 枚举引用闭包无效
- **WHEN** declaration/member/condition/downstream 任一引用缺失、类型冲突或超过预算
- **THEN** Referential Integrity Validator SHALL 阻止无效 step/edge/path 进入序列化结果，并保留可验证局部 Finding 与 Diagnostic
- **AND** Projector MUST NOT 回退到 V1、Legacy 或字符串 trace 补造链路
