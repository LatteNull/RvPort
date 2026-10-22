## ADDED Requirements

### Requirement: 数据库必须保存测试结果比较运行
数据库 SHALL 使用专用表保存测试结果比较运行记录，并 SHALL 关联项目、可选任务和两条自动化测试记录。

#### Scenario: 保存自动化测试节点批次
- **WHEN** 后端为一次自动化测试节点创建 source 和 target 两侧测试记录
- **THEN** 数据库 SHALL 保存可关联两侧测试记录的批次标识
- **AND** 批次标识 SHALL 能稳定区分同一项目内多次自动化测试运行
- **AND** 后端 MUST NOT 通过最近创建时间推断两侧测试记录归属

#### Scenario: 保存测试比较运行
- **WHEN** 后端根据自动化测试节点批次创建测试结果比较
- **THEN** 数据库 SHALL 保存 `test_comparison_runs` 记录
- **AND** 记录 SHALL 包含项目 ID、任务 ID、批次标识、source 测试运行 ID、target 测试运行 ID、状态、总体结论、风险等级、置信度、摘要、建议、错误摘要、是否发生输入裁剪和关键时间字段
- **AND** `task_id` SHALL 在存在时唯一关联 `tasks.id`
- **AND** source 和 target 测试运行外键 SHALL 引用 `test_runs.id`

#### Scenario: 保存比较不可用摘要
- **WHEN** 两侧自动化测试完成但模型未配置或不可用
- **THEN** 数据库 SHALL 保存比较运行记录
- **AND** 状态 SHALL 表达 `UNAVAILABLE` 或等效不可用状态
- **AND** 记录 SHALL 保存不可用错误码和前端可展示的脱敏原因
- **AND** `task_id` MAY 为空

#### Scenario: 查询测试比较运行
- **WHEN** 后端查询测试比较列表或详情
- **THEN** 数据库 SHALL 支持按项目、状态、source 测试运行、target 测试运行、源码版本、环境、风险等级和时间范围过滤
- **AND** 数据库 SHALL 支持按创建时间、完成时间、状态和风险等级排序

### Requirement: 数据库必须保存测试结果比较差异项
数据库 SHALL 使用专用表保存 agent 输出的结构化差异项，支持前端分页查看。

#### Scenario: 保存比较差异项
- **WHEN** agent 返回合法结构化差异项
- **THEN** 数据库 SHALL 保存 `test_comparison_findings` 记录
- **AND** 记录 SHALL 包含比较运行 ID、序号、差异类型、严重程度、置信度、标题、说明、source 摘要、target 摘要、建议和创建时间
- **AND** 差异项 SHALL 外键引用 `test_comparison_runs.id`

#### Scenario: 查询比较差异项
- **WHEN** 后端查询比较差异项
- **THEN** 数据库 SHALL 支持按比较运行 ID、严重程度、差异类型、置信度和关键字过滤
- **AND** 数据库 SHALL 支持按序号、严重程度、置信度和创建时间排序

### Requirement: 测试比较原始输出必须保存为受控制品
数据库 SHALL 通过 `stored_artifacts` 保存测试比较原始 agent 输出和必要的调试制品引用。

#### Scenario: 保存 agent 输出制品
- **WHEN** 测试结果比较任务完成、失败或 agent 输出不可解析
- **THEN** 后端 SHALL 将原始 agent 输出保存为 `stored_artifacts`
- **AND** `stored_artifacts.owner_type` SHALL 支持 `TEST_COMPARISON`
- **AND** owner ID SHALL 指向 `test_comparison_runs.id`
- **AND** 数据库 MUST NOT 将完整 agent 输出或完整输入直接塞入普通比较详情字段
