## ADDED Requirements

### Requirement: 报告比较必须基于评估报告快照
后端 SHALL 提供评估报告比较能力，并 SHALL 使用报告生成时保存的 `report_inputs.input_snapshot` 作为比较事实来源。

#### Scenario: 创建报告比较
- **WHEN** 已登录用户调用 `POST /api/reports/{reportId}/comparisons`
- **THEN** 后端 MUST 校验当前用户对该报告所属项目有访问权限
- **AND** 后端 MUST 使用 `reportId` 对应报告作为 target report
- **AND** 后端 MUST 使用 target report 的 `report_inputs.input_snapshot` 作为 target 比较输入
- **AND** 后端 MUST NOT 动态读取当前 `migration_input_refs` 或原始扫描结果替代报告快照

#### Scenario: 指定历史报告比较
- **WHEN** 创建报告比较请求包含 `baseReportId`
- **THEN** 后端 MUST 校验 base report 与 target report 属于同一项目
- **AND** 后端 MUST 校验 base report 早于 target report 或明确返回比较方向
- **AND** 后端 MUST 使用 base report 的 `report_inputs.input_snapshot` 作为 base 比较输入

#### Scenario: 自动选择上一份可比较报告
- **WHEN** 创建报告比较请求未包含 `baseReportId`
- **THEN** 后端 SHALL 自动选择同项目、同报告类型、早于 target report 且已成功生成的最近一份可比较报告
- **AND** 找不到可比较报告时 SHALL 返回明确业务错误

### Requirement: 报告比较结果必须表达问题变化
报告比较 SHALL 生成差异项，表达历史报告到当前报告之间的问题修复、新增、仍存在和变化。

#### Scenario: 生成报告差异项
- **WHEN** 报告比较任务执行完成
- **THEN** 后端 SHALL 为差异项生成 `RESOLVED`、`UNCHANGED`、`NEW` 或 `CHANGED` 状态
- **AND** 差异项 SHALL 包含 old/new 两侧报告输入快照引用
- **AND** 差异项 SHALL 包含标题、来源类型、位置标签、风险等级、建议、匹配置信度和匹配原因

#### Scenario: 报告输入已修复
- **WHEN** base report 中存在某个已确认输入且 target report 中不存在匹配项
- **THEN** 后端 SHALL 生成 `diffStatus=RESOLVED` 的差异项

#### Scenario: 报告输入新增
- **WHEN** target report 中存在某个已确认输入且 base report 中不存在匹配项
- **THEN** 后端 SHALL 生成 `diffStatus=NEW` 的差异项

#### Scenario: 报告输入仍存在或变化
- **WHEN** base report 与 target report 中两个输入匹配为同一问题
- **THEN** 后端 SHALL 根据核心展示字段和风险字段是否变化生成 `UNCHANGED` 或 `CHANGED`

### Requirement: 报告比较查询必须支持分页过滤排序
后端 SHALL 提供报告比较详情、差异列表和差异详情查询 API，并 SHALL 支持项目访问权限校验。

#### Scenario: 查询报告比较详情
- **WHEN** 已登录用户调用 `GET /api/report-comparisons/{comparisonId}`
- **THEN** 后端 MUST 校验当前用户对比较所属项目有访问权限
- **AND** 响应 SHALL 返回 base report 摘要、target report 摘要、状态、任务引用、差异摘要和关键时间字段
- **AND** 响应 MUST NOT 暴露服务器真实路径、对象存储内部 key、明文凭据或完整任务输入快照

#### Scenario: 查询报告比较差异列表
- **WHEN** 已登录用户调用 `GET /api/report-comparisons/{comparisonId}/diff-items`
- **THEN** 后端 MUST 校验当前用户对比较所属项目有访问权限
- **AND** 响应 SHALL 支持分页
- **AND** 响应 SHALL 支持按 `diffStatus`、`sourceType`、`severity`、`matchConfidence` 和关键字过滤
- **AND** 响应 SHALL 支持按 `diffStatus`、`sourceType`、`severity`、`matchConfidence`、`title`、`locationLabel` 和创建时间排序

#### Scenario: 查询报告比较差异详情
- **WHEN** 已登录用户调用 `GET /api/report-comparisons/{comparisonId}/diff-items/{diffItemId}`
- **THEN** 后端 MUST 校验差异项属于该比较
- **AND** 响应 SHALL 返回 old item 与 new item 快照
- **AND** `RESOLVED` 差异 SHALL 只包含 old item
- **AND** `NEW` 差异 SHALL 只包含 new item
- **AND** `UNCHANGED` 和 `CHANGED` 差异 SHALL 同时包含 old item 与 new item

### Requirement: 报告比较必须可异步执行并复用已有结果
报告比较 SHALL 使用长任务运行模型，并 SHALL 避免重复创建同一组报告之间的并发比较任务。

#### Scenario: 创建异步报告比较任务
- **WHEN** 后端接受报告比较创建请求
- **THEN** 后端 SHALL 创建或复用报告比较运行记录
- **AND** 后端 SHALL 创建任务类型为 `REPORT_COMPARE` 或等效类型的长任务
- **AND** 响应 SHALL 返回比较运行 ID、任务 ID 和初始状态

#### Scenario: 重复创建同一报告比较
- **WHEN** 同一 base report 与 target report 已存在 `PENDING`、`QUEUED`、`RUNNING` 或 `SUCCEEDED` 比较
- **THEN** 后端 SHALL 返回已有比较运行或已有任务
- **AND** 后端 MUST NOT 创建重复并发比较任务

#### Scenario: 不支持的历史报告
- **WHEN** base report 或 target report 缺少可用 `report_inputs.input_snapshot`
- **THEN** 后端 SHALL 返回 `REPORT_COMPARISON_UNSUPPORTED` 或等效业务错误
- **AND** 后端 MUST NOT 创建比较任务
