## ADDED Requirements

### Requirement: 迁移评估报告必须基于确认后的迁移输入生成
后端 SHALL 基于指定项目和源码版本下人工确认的迁移输入 reference 生成迁移评估报告。

#### Scenario: 生成报告读取确认输入
- **WHEN** 报告生成任务开始执行
- **THEN** 后端 SHALL 查询同一 `project_id` 和 `source_revision_id` 下 `status='CONFIRMED'` 的 `migration_input_refs`
- **AND** 后端 SHALL 根据每条 reference 的 `source_type` 和 `source_ref_id` 回查真实来源详情
- **AND** 后端 MUST NOT 将 `CANDIDATE` 或 `EXCLUDED` 迁移输入写入报告

#### Scenario: 没有确认输入
- **WHEN** 报告生成任务发现当前源码版本没有 `CONFIRMED` 迁移输入
- **THEN** 后端 SHALL 将报告任务标记为 `FAILED`
- **AND** 错误码 SHALL 为 `REPORT_NO_CONFIRMED_INPUTS`
- **AND** 后端 MUST NOT 生成空报告文件

### Requirement: 迁移评估报告必须保存不可变输入快照
后端 SHALL 在报告生成时保存报告输入快照，使历史报告不受后续迁移输入或原始分析结果变化影响。

#### Scenario: 写入报告输入快照
- **WHEN** 报告生成任务使用某条 confirmed migration input reference
- **THEN** 后端 SHALL 在 `report_inputs` 中写入一条记录
- **AND** `input_type` SHALL 为 `MIGRATION_INPUT_REF`
- **AND** `input_id` SHALL 为 `migration_input_refs.id`
- **AND** `input_snapshot` SHALL 包含 reference 展示字段、确认状态、备注和真实来源详情

#### Scenario: 历史报告不随输入状态变化
- **WHEN** 报告生成完成后用户修改迁移输入状态或备注
- **THEN** 已生成报告详情和下载内容 SHALL 继续使用生成时的 `report_inputs.input_snapshot`
- **AND** 后端 MUST NOT 重新从当前 migration input 状态动态拼接历史报告内容

### Requirement: 迁移评估报告必须生成 HTML 和 JSON 输出
后端 SHALL 为成功的迁移评估报告生成 HTML 和 JSON 两种受控输出，并 SHALL 通过对象存储制品能力保存输出内容。

#### Scenario: 成功生成报告制品
- **WHEN** 报告生成任务成功完成
- **THEN** 后端 SHALL 生成 HTML 报告文件
- **AND** 后端 SHALL 生成 JSON 报告文件
- **AND** 后端 SHALL 将两种报告内容保存到对象存储
- **AND** 后端 SHALL 为两种报告内容写入 `stored_artifacts` 元数据
- **AND** `stored_artifacts.owner_type` SHALL 为 `MIGRATION_REPORT`
- **AND** `stored_artifacts.owner_id` SHALL 为 `reports.id`
- **AND** API 响应 MUST NOT 返回服务器真实文件路径、bucket 或 object key

#### Scenario: 报告摘要聚合
- **WHEN** 报告生成任务完成
- **THEN** 后端 SHALL 写入 `reports.summary`
- **AND** 后端 SHALL 写入 `reports.risk_level`
- **AND** 摘要 SHALL 至少包含 confirmed 输入总数、按来源类型统计、按风险等级或替代状态统计和生成 schemaVersion

### Requirement: 迁移评估报告下载必须受控
后端 SHALL 通过报告下载接口读取对象存储中的报告制品，并 SHALL 防止内部存储位置泄露。

#### Scenario: 下载 HTML 报告
- **WHEN** 用户下载 `format=HTML` 的报告
- **THEN** 后端 SHALL 返回 HTML 文件内容
- **AND** 响应文件名 SHALL 使用安全文件名
- **AND** 后端 MUST NOT 在响应体或响应头中暴露服务器真实路径、bucket 或 object key

#### Scenario: 下载 JSON 报告
- **WHEN** 用户下载 `format=JSON` 的报告
- **THEN** 后端 SHALL 返回 JSON 文件内容
- **AND** 响应文件名 SHALL 使用安全文件名
- **AND** JSON 内容 SHALL 使用生成时保存的报告快照
- **AND** 后端 MUST NOT 暴露对象存储内部位置

#### Scenario: 拒绝不存在的报告制品
- **WHEN** 报告记录存在但请求格式对应的对象存储制品不存在
- **THEN** 后端 SHALL 返回统一业务错误
- **AND** 后端 MUST NOT 返回服务器路径、bucket、object key 或底层存储异常细节
