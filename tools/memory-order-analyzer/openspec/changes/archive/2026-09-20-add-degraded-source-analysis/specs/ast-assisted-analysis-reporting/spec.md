## ADDED Requirements

### Requirement: Report degraded evidence modes and failures without overstating analysis

AST-assisted/degraded 报告 SHALL 分别列出每个 TU、候选及请求级的 ast-ir、ir-only、ast-only、failed/mixed 状态，记录 available/missing evidence、failure class/stage、完整性分母和中英文 detail/suggestion。AST-only、failed 和未运行 MUST NOT 折叠为 source extraction complete 或 P4 complete。

#### Scenario: A request contains all four modes

- **WHEN** 不同 TU/候选分别为 ast-ir、ir-only、ast-only 和 failed
- **THEN** 报告给出四类 hit/total、请求 mixed/partial、各依赖路径和稳定双语诊断，不选择单一模式覆盖其他项

### Requirement: Keep source candidates separate from findings and discharges

报告 SHALL 将 SourceCandidate、P4 finding、P4 discharged、unknown 和 unsupported 分开存储和计数；source candidate 的 verdict 固定 unknown 且 safety 未建立，任何汇总、缓存或渲染层 MUST NOT 将其计入风险或已消解数量。

#### Scenario: Source candidate and unrelated formal risk coexist

- **WHEN** 一个 AST-only 候选与另一个完整 P4 risk 同时存在
- **THEN** 报告分别展示两者及请求 partial 状态，不把 source candidate 合并为第二个 finding
