## ADDED Requirements

### Requirement: API E2E 必须覆盖测试比较输出文件和无效输出拒绝
API E2E 测试套件 SHALL 覆盖自动化测试比较的成功文件输出、无效 agent 输出拒绝，以及比较失败不影响测试记录的行为。

#### Scenario: 比较 agent 通过结果文件返回统计
- **WHEN** E2E 使用测试辅助能力创建同批次 source 和 target 自动化测试记录
- **AND** 测试比较 agent 写出合法 `comparison-result.json`
- **THEN** 比较运行 SHALL 标记为 `SUCCEEDED`
- **AND** 比较详情 SHALL 返回 source 与 target 的结构化测试统计
- **AND** finding 列表 SHALL 不包含 schema 占位符

#### Scenario: 无效 agent 输出被拒绝
- **WHEN** 测试比较 agent 返回组合枚举、`...` 或 prompt schema 占位符
- **THEN** 比较运行 SHALL 标记为 `FAILED`
- **AND** 错误码 SHALL 表明 agent 输出无效
- **AND** E2E SHALL 验证无效内容没有写入成功比较结果

#### Scenario: x86 成功 target 失败仍可比较
- **WHEN** source 自动化测试记录为 `SUCCEEDED`
- **AND** target 自动化测试记录为 `FAILED`
- **AND** 两侧记录属于同一个 `testBatchId`
- **THEN** 后端 SHALL 自动创建测试比较运行
- **AND** 比较运行 SHALL 基于两侧日志生成结果或明确失败
- **AND** source 和 target 测试记录本身 SHALL 保持原始状态
