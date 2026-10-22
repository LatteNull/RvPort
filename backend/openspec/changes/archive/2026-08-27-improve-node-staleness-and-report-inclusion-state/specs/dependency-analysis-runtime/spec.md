## ADDED Requirements

### Requirement: 依赖分析列表必须默认收敛到当前上下文
依赖分析运行列表 API SHALL 默认返回当前 active source revision 和当前运行环境配置版本下的依赖分析记录，并 SHALL 支持显式查看历史记录。

#### Scenario: 默认查询当前依赖分析记录
- **WHEN** 用户调用 `GET /api/projects/{projectId}/dependency-analyses` 且未指定 `sourceRevisionId`、`environmentConfigVersion` 或 `includeStale`
- **THEN** 后端 SHALL 使用项目 active source revision 作为默认源码版本
- **AND** 后端 SHALL 使用当前项目运行环境配置版本作为默认环境版本
- **AND** 响应 MUST NOT 混入旧源码版本或旧运行环境配置版本的依赖分析运行

#### Scenario: 显式查看历史依赖分析记录
- **WHEN** 用户调用依赖分析列表 API 并显式提交历史 `sourceRevisionId`、历史 `environmentConfigVersion` 或 `includeStale=true`
- **THEN** 后端 SHALL 按请求参数返回匹配历史记录
- **AND** 响应 SHALL 标明每条记录是否属于当前源码版本和当前运行环境配置版本

### Requirement: 依赖分析结果必须返回报告纳入状态
依赖分析结果列表和详情 SHALL 返回该结果与当前报告输入池、最新评估报告之间的关系。

#### Scenario: 依赖结果已确认进入下一次报告
- **WHEN** 依赖分析结果存在同一源码版本下的 `sourceType=DEPENDENCY_RESULT` migration input reference
- **AND** reference 状态为 `CONFIRMED`
- **THEN** 依赖结果响应 SHALL 返回 `confirmedForNextReport=true`
- **AND** 响应 SHALL 返回 `migrationInputRefId` 和 `migrationInputStatus`

#### Scenario: 依赖结果已纳入最新报告
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 该报告的 `report_inputs` 包含对应 migration input reference
- **THEN** 依赖结果响应 SHALL 返回 `includedInLatestReport=true`
- **AND** 响应 SHALL 返回 `latestReportId`

#### Scenario: 依赖结果未纳入报告
- **WHEN** 依赖分析结果没有对应 migration input reference 或 reference 未进入最新报告快照
- **THEN** 依赖结果响应 SHALL 返回明确的 `confirmedForNextReport=false` 或 `includedInLatestReport=false`
- **AND** 后端 MUST NOT 要求前端自行联表推断该状态
