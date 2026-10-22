## ADDED Requirements

### Requirement: Evidence Graph 必须表达测试资产与覆盖候选关系
组合 Graph Analyzer SHALL 为 test suite、test target、test source 和 coverage candidate 建立稳定 Entity，并 SHALL 通过 `contains_test`、`selects_test`、`exercises`、`covers_candidate` 与 `alternative_test_for` Relation 连接已有 source/build Entity；所有关系 MUST 引用有效 Evidence/endpoint，并 SHALL 保留 configuration、selection status、confidence 和完整性。

#### Scenario: selected test target 使用 x86 依赖
- **WHEN** build graph 和测试角色 Evidence 可连接 RISC-V selector、test target、test source 与 knowledge-backed x86 dependency
- **THEN** AnalysisSnapshot SHALL 包含有界且完整的 selector-to-test-dependency ProofPath
- **AND** Classifier SHALL 只消费该 proof，不得在图层重新推断状态

#### Scenario: 实现与测试具有显式关系
- **WHEN** target/source/call/metadata Evidence 明确关联一个 RISC-V/portable implementation 与测试
- **THEN** Graph Analyzer SHALL 建立 `exercises` 或 `covers_candidate` 关系并保留依据
- **AND** GraphStore MUST NOT 将 coverage candidate 自行升级为测试已执行或通过

#### Scenario: 实现和测试只有名称相似
- **WHEN** 两个资产缺少 target、source、call 或 metadata 关系
- **THEN** Graph Analyzer SHALL 不建立确定 coverage relation
- **AND** 缺失关系 SHALL 保持 unknown，而不是被解释为 covered 或 gap

#### Scenario: 测试图超过预算或形成循环
- **WHEN** 测试/实现/target 关系超过 max depth、visited、paths 或形成循环
- **THEN** proof resolver SHALL 有界终止并保留已有关系与 truncated reason
- **AND** Classifier/Assessor MUST NOT 将截断路径升级为确定结论
