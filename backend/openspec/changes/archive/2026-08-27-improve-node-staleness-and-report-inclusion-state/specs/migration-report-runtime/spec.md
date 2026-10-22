## ADDED Requirements

### Requirement: 评估报告必须返回当前输入更新状态
评估报告 readiness 和详情 API SHALL 比较当前 confirmed migration input refs 与最新评估报告输入快照，并返回报告是否需要更新。

#### Scenario: 最新报告覆盖当前输入
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 当前 `CONFIRMED` migration input reference 集合与该报告 `report_inputs` 快照集合一致
- **THEN** readiness 和报告详情 SHALL 返回 `reportUpToDate=true`
- **AND** 更新摘要 SHALL 显示新增、移除和变化数量均为 `0`

#### Scenario: 当前输入多于最新报告
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 当前 `CONFIRMED` migration input reference 中存在未进入最新报告快照的记录
- **THEN** readiness 和报告详情 SHALL 返回 `reportUpToDate=false`
- **AND** 更新摘要 SHALL 返回新增输入数量和示例摘要

#### Scenario: 当前输入少于最新报告
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 最新报告快照中的输入已被撤回或不再处于 `CONFIRMED`
- **THEN** readiness 和报告详情 SHALL 返回 `reportUpToDate=false`
- **AND** 更新摘要 SHALL 返回移除输入数量和示例摘要

#### Scenario: 当前输入字段发生变化
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 同一 migration input reference 的报告可见字段与最新报告快照不一致
- **THEN** readiness 和报告详情 SHALL 返回 `reportUpToDate=false`
- **AND** 更新摘要 SHALL 返回变化输入数量

#### Scenario: 尚未生成报告
- **WHEN** 当前源码版本不存在成功评估报告
- **THEN** readiness SHALL 返回 `reportUpToDate=false`
- **AND** 更新摘要 SHALL 标明 `latestReportMissing=true`
