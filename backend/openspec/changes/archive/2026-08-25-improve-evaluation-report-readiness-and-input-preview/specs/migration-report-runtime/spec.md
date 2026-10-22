## ADDED Requirements

### Requirement: 评估报告节点必须提供生成前 readiness
迁移评估报告运行时 SHALL 提供当前源码版本的报告生成前 readiness 数据，使前端能够在用户创建报告任务前判断是否可生成报告并展示原因。

#### Scenario: 当前源码版本可生成报告
- **WHEN** 项目存在 active source revision
- **AND** 当前源码版本下至少存在一条 `status=CONFIRMED` 的 migration input reference
- **THEN** readiness SHALL 返回 `canGenerate=true`
- **AND** readiness SHALL 返回当前源码版本摘要、confirmed 输入数量、按来源统计和按风险等级统计
- **AND** readiness SHALL 返回最新评估报告摘要或空值

#### Scenario: 当前源码版本没有 confirmed 输入
- **WHEN** 当前源码版本下不存在 `status=CONFIRMED` 的 migration input reference
- **THEN** readiness SHALL 返回 `canGenerate=false`
- **AND** blockers SHALL 包含 `REPORT_NO_CONFIRMED_INPUTS`
- **AND** 后端 MUST NOT 为 readiness 查询创建报告任务

#### Scenario: 项目没有 active source revision
- **WHEN** 项目没有 active source revision 且请求未指定有效源码版本
- **THEN** readiness SHALL 返回 `canGenerate=false`
- **AND** blockers SHALL 包含 `SOURCE_REVISION_REQUIRED`

#### Scenario: 低风险候选提示
- **WHEN** 当前源码版本下存在 `detectedLevel` 归一化为 `LOW` 且 `status=CANDIDATE` 的 reference
- **THEN** readiness SHALL 返回候选数量
- **AND** warnings SHALL 包含低风险候选未进入报告的提示
- **AND** 报告生成 MUST NOT 默认消费这些 `CANDIDATE` reference

### Requirement: 评估报告节点必须提供生成前输入预览
迁移评估报告运行时 SHALL 支持在报告生成前分页预览当前源码版本下的 migration input reference，供用户审计报告输入池。

#### Scenario: 查询输入预览
- **WHEN** 用户查询某项目当前源码版本的报告输入预览
- **THEN** 后端 SHALL 返回分页列表
- **AND** 每条记录 SHALL 包含 reference ID、sourceType、sourceRefId、issueTitle、detectedLevel、locationLabel、status、recommendationSummary、note、更新时间和来源定位摘要
- **AND** 响应 MUST NOT 返回完整来源详情、服务器真实路径、对象存储内部 key 或明文凭据

#### Scenario: 输入预览过滤排序
- **WHEN** 用户按 `sourceType`、`status`、风险等级或关键字过滤输入预览
- **THEN** 后端 SHALL 使用 AND 语义组合过滤条件
- **AND** 后端 SHALL 支持稳定排序白名单
- **AND** 非法排序字段 SHALL 返回统一业务错误

#### Scenario: 输入预览不修改输入状态
- **WHEN** 用户查询输入预览
- **THEN** 后端 MUST NOT 创建、确认、撤回或删除 migration input reference
- **AND** 用户状态变更 SHALL 继续通过节点内确认或 migration input 状态更新接口完成

### Requirement: 评估报告详情必须区分历史快照和当前输入状态
迁移评估报告详情 SHALL 同时表达报告生成时的不可变输入快照摘要和当前源码版本下的输入状态摘要，避免用户误解重新确认后的历史报告内容。

#### Scenario: 查看报告详情包含当前输入摘要
- **WHEN** 用户查看已生成评估报告详情
- **THEN** 响应 SHALL 返回报告生成时的 summary 和 artifact 摘要
- **AND** 响应 SHALL 返回该报告源码版本当前 migration input 的状态统计
- **AND** 当前输入摘要 SHALL 按 `CONFIRMED`、`CANDIDATE`、`EXCLUDED`、sourceType 和风险等级聚合

#### Scenario: 历史报告快照不随当前输入变化
- **WHEN** 报告生成后用户修改同源码版本下 migration input reference 状态或备注
- **THEN** 报告详情中的历史报告 summary 和下载内容 SHALL 保持生成时内容
- **AND** 当前输入摘要 MAY 反映最新状态

### Requirement: 评估报告节点必须暴露历史报告比较准备信息
评估报告运行时 SHALL 在报告页聚合数据中提供历史报告比较准备信息，使前端能从评估报告页进入报告比较。

#### Scenario: 存在可比较历史报告
- **WHEN** 当前源码版本存在最新评估报告
- **AND** 同项目存在早于该报告且状态成功的同类型历史报告
- **THEN** readiness 或 overview SHALL 返回可比较历史报告摘要
- **AND** 后端 SHALL 保持实际比较创建由报告比较 API 完成

#### Scenario: 不存在可比较历史报告
- **WHEN** 当前报告没有可比较历史报告
- **THEN** readiness 或 overview SHALL 返回空比较准备信息
- **AND** 后端 MUST NOT 将该情况视为报告生成 blocker
