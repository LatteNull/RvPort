## ADDED Requirements

### Requirement: Keep roadmap and navigation aligned with archived P4 and active P5

项目路线图、README 和文档索引 SHALL 明确 P4 `detect-single-publication-risks` 已实现、质量验收、同步并归档，登记 P5 `validate-and-scale-analysis` 的实际 proposed/applying/validated/archived 状态及边界；不得继续显示 P4 待 sync/archive，也不得把提案状态写成已实现。

#### Scenario: A reader follows the roadmap after P5 proposal

- **WHEN** 读者从 README 或 `doc/IMPLEMENTATION_ROADMAP.md` 查看阶段状态
- **THEN** 能定位 P4 归档、P4 使用/验证文档和当前 P5 change，并清楚区分已完成与计划能力

#### Scenario: P5 has not run an optional backend

- **WHEN** GenMC、herdtools7 或新 DevKit 实验未执行
- **THEN** 文档标为 not_run/待验证，不使用设计计划或历史结果冒充本轮观察

### Requirement: Document P5 evidence layers and reproducible validation

文档 SHALL 分开描述人工 truth、P1–P4 observation、真实工程人工抽样、外部 backend comparison、性能/缓存测量和后续决策，提供版本/hash、命令、分母、报告入口和限制。准确率只引用完整人工 truth 分母；真实工程样本、DevKit success、BC 编译、零 finding 和工具一致 MUST NOT 表述为全工程准确率或并发安全证明。面向用户的诊断和建议示例 SHALL 同时给出中文和英文字段。

#### Scenario: Validation results are published

- **WHEN** P5 离线语料和真实工程基线完成
- **THEN** `doc/VALIDATION_AND_SCALING_VALIDATION.md` 记录精确环境、命令、hash、truth/观察/抽样/性能结果、覆盖率及报告位置，并链接自 README 与文档索引

#### Scenario: A real-project sample looks accurate

- **WHEN** 已裁决样本全部与 P4 一致但未穷尽工程真值
- **THEN** 文档只报告样本分母与选择方法，不外推 100% precision/recall 或安全结论
