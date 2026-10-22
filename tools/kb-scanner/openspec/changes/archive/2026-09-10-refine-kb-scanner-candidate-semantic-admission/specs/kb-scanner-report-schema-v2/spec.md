## ADDED Requirements

### Requirement: Unknown candidate 必须在结论和链路中一致表达
V2 SHALL 对所有未决 candidate（包括 identifier 与 enum）一致表达 unknown completeness/conclusion/chain，并提示当前无法确定执行架构依赖，可由后续分析补齐。核心 schema 与 V1 合同 SHALL 保持不变。

#### Scenario: codec 名称只有候选证据
- **WHEN** Classifier 对 identifier candidate 返回 unknown
- **THEN** V2 conclusion 与 chain SHALL 保持 unknown，且 suggestion MUST NOT 宣称已确认需要替换实现
- **AND** fact、occurrence、上下文和知识来源 SHALL 保留

### Requirement: Intrinsic 与替代标签必须具有对应证据
V2 SHALL 只将对应 symbol/call Evidence 精确命中的适用 intrinsic/builtin 知识标为 intrinsic_call；普通调用 SHALL 为 source_evidence。相同 kind 或 _mm 前缀 MUST NOT 构成 intrinsic/alternative_to 证明。

#### Scenario: 普通函数与真实 intrinsic 混合
- **WHEN** 同链有普通 checksum 函数、伪 _mm 名称与知识确认调用
- **THEN** 仅适用精确知识调用 SHALL 标 intrinsic，辅助调用不能抢占主 fact
- **AND** 真实行号/context/highlight 与引用 SHALL 保持

#### Scenario: 相同 kind 和真实 alternative relation
- **WHEN** 同链多个代码节点具有相同 kind
- **THEN** 无证明节点 SHALL 使用中性展示关联，只有可定位两端的 Analysis alternative_to relation 才可生成相应替代 edge
- **AND** 不新增核心 kind/必填字段、候选选项 extension 或第二主结果
