## ADDED Requirements

### Requirement: KB 扫描列表必须默认收敛到当前源码版本
KB 扫描运行列表 API SHALL 默认返回当前 active source revision 下的扫描记录，并 SHALL 支持显式查看历史源码版本记录。

#### Scenario: 默认查询当前 KB 扫描记录
- **WHEN** 用户调用 `GET /api/projects/{projectId}/kb-scans` 且未指定 `sourceRevisionId` 或 `includeStale`
- **THEN** 后端 SHALL 使用项目 active source revision 作为默认源码版本
- **AND** 响应 MUST NOT 混入旧源码版本的 KB 扫描运行

#### Scenario: 显式查看历史 KB 扫描记录
- **WHEN** 用户调用 KB 扫描列表 API 并显式提交历史 `sourceRevisionId` 或 `includeStale=true`
- **THEN** 后端 SHALL 按请求参数返回匹配历史记录
- **AND** 响应 SHALL 标明每条记录是否属于当前源码版本

### Requirement: KB finding 必须返回报告纳入状态
KB finding 列表和详情 SHALL 返回该 finding 与当前报告输入池、最新评估报告之间的关系。

#### Scenario: finding 已确认进入下一次报告
- **WHEN** KB finding 存在同一源码版本下的 `sourceType=KB_FINDING` migration input reference
- **AND** reference 状态为 `CONFIRMED`
- **THEN** finding 响应 SHALL 返回 `confirmedForNextReport=true`
- **AND** 响应 SHALL 返回 `migrationInputRefId` 和 `migrationInputStatus`

#### Scenario: finding 已纳入最新报告
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 该报告的 `report_inputs` 包含对应 migration input reference
- **THEN** finding 响应 SHALL 返回 `includedInLatestReport=true`
- **AND** 响应 SHALL 返回 `latestReportId`

#### Scenario: finding 未纳入报告
- **WHEN** KB finding 没有对应 migration input reference 或 reference 未进入最新报告快照
- **THEN** finding 响应 SHALL 返回明确的 `confirmedForNextReport=false` 或 `includedInLatestReport=false`
- **AND** 后端 MUST NOT 要求前端自行联表推断该状态
