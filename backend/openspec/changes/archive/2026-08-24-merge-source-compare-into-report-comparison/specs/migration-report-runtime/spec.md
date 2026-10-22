## ADDED Requirements

### Requirement: 评估报告页面必须支持历史报告查看
迁移评估报告 API SHALL 支持前端在评估报告页面查看项目过往评估报告，并 SHALL 允许用户基于历史报告进行比较。

#### Scenario: 查询历史评估报告
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/reports/evaluation`
- **THEN** 后端 MUST 校验当前用户对项目有访问权限
- **AND** 响应 SHALL 返回该项目的历史评估报告分页列表
- **AND** 列表 SHALL 支持按 `sourceRevisionId`、状态、风险等级和生成时间过滤
- **AND** 列表 SHALL 支持按 `createdAt`、`generatedAt`、`status` 和 `riskLevel` 排序
- **AND** 每条报告 SHALL 返回报告 ID、源码版本摘要、状态、风险等级、摘要、制品摘要和关键时间字段

#### Scenario: 查看报告详情中的比较入口
- **WHEN** 已登录用户调用 `GET /api/reports/{reportId}`
- **THEN** 响应 SHALL 包含报告摘要、源码版本摘要、制品摘要和可比较历史报告提示
- **AND** 若存在上一份可比较报告，响应 SHOULD 包含 latest comparison 入口摘要或 base report 摘要
- **AND** 响应 MUST NOT 返回完整报告正文、对象存储内部 key 或服务器真实路径

### Requirement: 评估报告必须作为报告比较主入口
迁移评估报告 SHALL 将历史差异查看建模为报告比较能力，而不是要求前端进入独立源码对比节点。

#### Scenario: 从评估报告发起历史比较
- **WHEN** 用户在评估报告页面点击与历史报告比较
- **THEN** 前端 SHALL 调用报告比较 API
- **AND** 后端 SHALL 基于报告输入快照创建或复用比较结果
- **AND** 前端 MUST NOT 为主流程调用源码 latest compare API 来完成报告比较

#### Scenario: 历史报告下载不受比较影响
- **WHEN** 用户查看或下载任意历史评估报告
- **THEN** 后端 SHALL 继续使用该报告生成时保存的 HTML 和 JSON artifact
- **AND** 报告比较结果 MUST NOT 修改历史报告 artifact 内容
