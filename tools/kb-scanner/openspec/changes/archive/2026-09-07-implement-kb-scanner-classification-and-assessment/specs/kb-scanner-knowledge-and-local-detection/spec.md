## MODIFIED Requirements

### Requirement: 未支持的知识和关系能力必须显式延后
行为验收矩阵 SHALL 覆盖已确认的 C/C++ 迁移能力；Detector/Classifier SHALL 只执行有当前事实、明确结构依据或 Graph Analyzer Relation/ProofPath 支持的 matcher/policy。已实现的宏链、include、sibling/alternative、build selection、test selection 和 classification/assessment SHALL 标记为对应 graph/classification-backed；真实编译、测试执行、兼容投影或输入不完整的能力 SHALL 标记为 deferred/provisional/unknown，MUST NOT 被当作未命中即安全。

#### Scenario: 规则依赖已支持的源码、构建或测试关系
- **WHEN** 一个迁移行为可由完整 include/macro/guard/alternative、selector/condition/source/argument/dependency/target 或 test selection/coverage proof 支持
- **THEN** Detector/Classifier SHALL 使用有效关系引用产生 Observation/Classification
- **AND** Assessor SHALL 只从这些可追溯对象合成项目维度，不得绕过前序阶段扫描文本

#### Scenario: 结论仍依赖真实编译测试或兼容投影
- **WHEN** 一个行为需要真实 RISC-V compile/link/run、测试执行、外部 RVWMO 分析或最终兼容 Projector 才能完整成立
- **THEN** staged qualification SHALL 输出 capability identity、scope 和 deferred/unknown reason
- **AND** Classifier/Assessor MUST NOT 用静态局部或构建关系伪造外部验证结果

#### Scenario: 当前能力和未知输入同时存在
- **WHEN** acceptance matrix 同时包含 classification-backed 项与缺失/冲突/截断输入
- **THEN** pipeline SHALL 返回可确认的 Observation/Classification/Assessment 维度并保留 provisional/unknown 状态
- **AND** 未知能力 MUST NOT 删除已经恢复的 Knowledge、Fact、Relation、ProofPath、Observation 或确定分类

#### Scenario: 更新行为验收矩阵
- **WHEN** 本 change 完成 staged qualification
- **THEN** build source/RPM selection SHALL 不再标为 needs-build/needs-packaging，test selection 与 blocking/readiness SHALL 标记为 classification-backed 或明确的 external-validation-deferred
- **AND** 每个状态 SHALL 具有代表性 fixture 和稳定 reason，不得通过修改 Legacy YAML 伪装完成
