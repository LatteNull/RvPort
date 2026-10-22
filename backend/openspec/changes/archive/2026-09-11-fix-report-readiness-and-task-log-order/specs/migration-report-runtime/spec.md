## MODIFIED Requirements

### Requirement: 评估报告节点必须提供生成前 readiness
迁移评估报告运行时 SHALL 提供当前源码版本的报告生成前 readiness 数据，使前端能够在用户创建报告任务前判断是否可生成报告并展示原因；确认迁移输入数量 SHALL 作为报告内容事实而不是报告生成阻塞条件。

#### Scenario: 当前源码版本存在 confirmed 输入
- **WHEN** 项目存在 active source revision
- **AND** 当前源码版本下至少存在一条 `status=CONFIRMED` 的 migration input reference
- **THEN** readiness SHALL 返回 `canGenerate=true`
- **AND** 阶段 readiness 中的 `INCLUDED_FINDINGS` SHALL 返回 `SATISFIED`
- **AND** readiness SHALL 返回当前源码版本摘要、confirmed 输入数量、按来源统计和按风险等级统计
- **AND** readiness SHALL 返回最新评估报告摘要或空值

#### Scenario: 当前源码版本没有 confirmed 输入
- **WHEN** 项目存在 active source revision
- **AND** 当前源码版本下不存在 `status=CONFIRMED` 的 migration input reference
- **THEN** readiness SHALL 返回 `canGenerate=true`
- **AND** 阶段 readiness 中的 `INCLUDED_FINDINGS` SHALL 返回 `SATISFIED`
- **AND** `INCLUDED_FINDINGS.details.count` SHALL 为 0
- **AND** blockers MUST NOT 包含 `REPORT_NO_CONFIRMED_INPUTS` 或等价的输入缺失原因
- **AND** 后端 SHALL 允许创建报告生成任务并生成全零报告
- **AND** 后端 MUST NOT 为 readiness 查询本身创建报告任务

#### Scenario: 项目没有 active source revision
- **WHEN** 项目没有 active source revision 且请求未指定有效源码版本
- **THEN** readiness SHALL 返回 `canGenerate=false`
- **AND** blockers SHALL 包含 `SOURCE_REVISION_REQUIRED`
- **AND** 阶段 readiness 中的 `INCLUDED_FINDINGS` SHALL 返回 `MISSING`
- **AND** 后端 MUST NOT 创建报告生成任务

#### Scenario: 低风险候选提示
- **WHEN** 当前源码版本下存在 `detectedLevel` 归一化为 `LOW` 且 `status=CANDIDATE` 的 reference
- **THEN** readiness SHALL 返回候选数量
- **AND** warnings SHALL 包含低风险候选未进入报告的提示
- **AND** 报告生成 MUST NOT 默认消费这些 `CANDIDATE` reference
