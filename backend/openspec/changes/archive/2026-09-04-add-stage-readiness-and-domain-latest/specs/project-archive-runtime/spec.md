## ADDED Requirements

### Requirement: 项目归档必须提供 latest
项目归档领域 SHALL 提供当前 Context 下的 latest 接口，用于展示最近归档记录和归档物摘要。

#### Scenario: 查询归档 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/archives/latest`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `result` SHALL 包含最近归档记录、归档 item 摘要和下载入口信息

#### Scenario: 当前 Context 没有归档
- **WHEN** 当前源码版本下没有归档记录
- **THEN** latest SHALL 成功返回
- **AND** `freshness` SHALL 为 `EMPTY` 或 `STALE`

### Requirement: 项目归档 readiness 必须返回可归档事实
项目级 readiness 在 `stageId=archive` 时 SHALL 返回归档所需前置条件。

#### Scenario: 当前 Context 存在可归档内容
- **WHEN** 当前源码版本下存在归档候选或已完成报告
- **THEN** readiness SHALL 返回对应 prerequisite 为 `SATISFIED`
- **AND** `referenceId` SHALL 指向候选、报告或执行记录

#### Scenario: 当前 Context 无可归档内容
- **WHEN** 当前源码版本下没有可归档内容
- **THEN** readiness SHALL 返回 `MISSING`
- **AND** `reasonCode` SHALL 为 `ARCHIVE_CANDIDATES_MISSING`
