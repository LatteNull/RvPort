## ADDED Requirements

### Requirement: 节点结果列表必须暴露迁移输入确认状态
可进入报告的节点结果列表 SHALL 直接返回节点结果对应的 migration input reference 状态，供前端展示确认、撤回和报告纳入信息。

#### Scenario: 节点结果存在 reference
- **WHEN** 节点结果存在同一源码版本、同一 `sourceType`、同一 `sourceRefId` 的 migration input reference
- **THEN** 节点结果响应 SHALL 返回 `migrationInputRefId`
- **AND** 节点结果响应 SHALL 返回 `migrationInputStatus`
- **AND** `confirmedForNextReport` SHALL 根据 reference 状态是否为 `CONFIRMED` 计算

#### Scenario: 节点结果不存在 reference
- **WHEN** 节点结果没有对应 migration input reference
- **THEN** 节点结果响应 SHALL 返回 `migrationInputRefId=null`
- **AND** 节点结果响应 SHALL 返回 `confirmedForNextReport=false`
- **AND** 用户 SHALL 仍可通过节点内确认 API 创建 reference

#### Scenario: 节点结果已经进入最新报告
- **WHEN** 节点结果对应的 migration input reference 已存在于当前源码版本最新成功报告的 `report_inputs`
- **THEN** 节点结果响应 SHALL 返回 `includedInLatestReport=true`
- **AND** 节点结果响应 SHALL 返回对应 `latestReportId`
