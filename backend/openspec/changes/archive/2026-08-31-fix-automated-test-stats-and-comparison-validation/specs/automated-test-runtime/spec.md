## ADDED Requirements

### Requirement: 自动化测试必须为比较 agent 提供稳定输入材料
自动化测试运行时 SHALL 保存足够的事实材料供测试结果比较 agent 生成结构化统计，但 MUST NOT 在后端引入面向具体测试工具的用例级 parser。

#### Scenario: 保存比较输入材料
- **WHEN** 自动化测试任务进入终态
- **THEN** 后端 SHALL 保存测试状态、退出码、stdout 日志引用、stderr 日志引用、merged log 引用、输出摘要和报告 artifact 摘要
- **AND** 这些材料 SHALL 足以让 `TEST_LOG_COMPARE` agent 读取测试统计证据
- **AND** 后端 SHALL 允许 `passedCount`、`failedCount` 和 `skippedCount` 为空

#### Scenario: 不在自动化测试运行时解析测试框架
- **WHEN** 自动化测试日志包含 CTest、pytest、JUnit、Maven Surefire 或其他测试框架输出
- **THEN** 自动化测试运行时 MUST NOT 为这些框架实现专用 parser 来填充用例级统计
- **AND** 测试统计 SHALL 由测试结果比较 agent 从日志和报告材料中提取

#### Scenario: 比较失败不影响测试事实
- **WHEN** 自动化测试已完成但后续测试结果比较失败
- **THEN** 自动化测试记录 SHALL 保持自身真实状态
- **AND** 自动化测试 API SHALL 继续返回测试日志引用、退出码和报告 artifact 摘要
- **AND** 后端 MUST NOT 因比较失败修改自动化测试运行状态
