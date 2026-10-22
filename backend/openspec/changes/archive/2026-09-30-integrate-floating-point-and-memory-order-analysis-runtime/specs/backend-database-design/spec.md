## ADDED Requirements

### Requirement: 数据库必须持久化专项分析运行
数据库 SHALL 保存 analyzer type、项目、任务、源码版本、构建、artifact set、可选环境配置版本、协议版本、状态、verdict、退出码、计数、摘要、制品引用和时间字段。

#### Scenario: 保存成功运行
- **WHEN** 工具结果通过协议校验
- **THEN** 运行记录 SHALL 在同一事务中写入终态、计数和结果制品引用

#### Scenario: 保存失败运行
- **WHEN** 输入、工具或结果导入失败
- **THEN** 运行记录 SHALL 保存失败阶段和安全错误摘要
- **AND** MUST NOT 保存成功态 Finding 计数

### Requirement: 数据库必须逐条持久化专项分析 Finding
数据库 SHALL 为每条 Finding 保存外部稳定 ID、领域类型、风险、置信度、状态、规则/类别、双语摘要、主位置、人工确认要求、semantic digest 和单条详情 JSON。

#### Scenario: 防止同运行重复 Finding
- **WHEN** 同一运行重复导入相同 external finding ID
- **THEN** 唯一约束 SHALL 阻止重复记录
- **AND** 导入事务 SHALL 回滚而不是留下半套结果

#### Scenario: 查询索引
- **WHEN** API 按项目、运行、领域、风险、状态、路径、规则或时间查询
- **THEN** 数据库 SHALL 提供对应索引支持分页过滤排序

### Requirement: 大型分析输出不得整体写入数据库单字段
数据库 SHALL 只保存安全摘要和逐条 Finding 详情；完整请求、结果 JSON、HTML 和内存序审计目录 SHALL 保存到对象存储。

#### Scenario: 保存大型结果
- **WHEN** 工具输出包含大量 Scope、证据节点或诊断文件
- **THEN** 数据库 SHALL 保存对象制品引用和聚合计数
- **AND** MUST NOT 把完整结果 bundle 写入单个 JSON 字段
