## ADDED Requirements

### Requirement: 测试结果比较必须输出结构化环境测试统计
测试结果比较运行时 SHALL 要求 agent 从 merged log 和报告材料中提取 source 与 target 两侧测试统计，并 SHALL 保存结构化摘要。

#### Scenario: 输出 source 测试统计
- **WHEN** 当前配置的 agent 完成测试结果比较
- **THEN** 输出 SHALL 包含 source 环境的状态、退出码、测试总数、执行数、通过数、失败数、跳过数、失败项和失败原因
- **AND** 输出 SHALL 包含统计提取置信度和统计依据

#### Scenario: 输出 target 测试统计
- **WHEN** 当前配置的 agent 完成测试结果比较
- **THEN** 输出 SHALL 包含 target 环境的状态、退出码、测试总数、执行数、通过数、失败数、跳过数、失败项和失败原因
- **AND** 输出 SHALL 包含统计提取置信度和统计依据

#### Scenario: agent 负责提取测试统计
- **WHEN** 后端准备测试结果比较输入
- **THEN** 后端 SHALL 将 merged log 和已回收报告材料提供给 agent
- **AND** 后端 MUST NOT 为不同测试工具实现专用 parser 来提取测试数量或失败项
- **AND** 后端 SHALL 只校验 agent 输出结构、字段类型和脱敏边界

#### Scenario: 无法确定测试数量
- **WHEN** agent 无法从日志或报告中可靠判断测试数量
- **THEN** agent 输出 SHALL 使用空值或低置信度表达不确定
- **AND** agent MUST NOT 编造测试总数、通过数或失败数

#### Scenario: 保存结构化统计
- **WHEN** agent 返回合法结构化测试统计
- **THEN** 后端 SHALL 将 source 与 target 统计摘要保存到测试比较运行
- **AND** API 查询比较详情时 SHALL 返回该结构化统计
- **AND** 数据库普通摘要字段 MUST NOT 保存完整原始日志或完整 agent 输入

### Requirement: 测试结果比较必须基于合并日志判断失败上下文
测试结果比较运行时 SHALL 使用有序 merged log 判断测试步骤与错误输出之间的上下文关系。

#### Scenario: 错误输出与测试步骤相邻
- **WHEN** merged log 中 `STDERR` 错误输出出现在某个测试步骤输出之后
- **THEN** agent SHALL 基于有序上下文判断该错误可能关联的测试项
- **AND** 比较结果中的失败项 SHALL 尽量包含对应测试名称、错误证据和原因

#### Scenario: 分流日志不足以判断上下文
- **WHEN** 只有 stdout/stderr 分流日志而没有 merged log
- **THEN** agent SHALL 在统计依据或摘要中说明上下文顺序可能不完整
- **AND** 后端 SHALL 允许该比较结果使用较低置信度
