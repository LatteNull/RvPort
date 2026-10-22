## ADDED Requirements

### Requirement: 测试结果比较实现必须覆盖三类测试
测试结果比较实现 SHALL 配套单元测试、轻量集成测试和独立 API E2E 测试，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常流程测试
- **WHEN** 为测试结果比较能力编写测试
- **THEN** 测试 SHALL 覆盖同一自动化测试批次完成后自动创建比较任务、读取两条测试记录、聚合日志和报告、解析阶段模型、调用 agent、保存比较摘要、保存差异项、保存 agent 输出 artifact 和 SSE 状态事件

#### Scenario: 异常流程测试
- **WHEN** 为测试结果比较能力编写测试
- **THEN** 测试 SHALL 覆盖无权限访问、项目不存在、测试记录不存在、测试记录非同项目、测试记录未完成、模型未配置、模型不可用、agent 超时、agent 退出失败和 agent 输出不可解析

#### Scenario: Edge case 测试
- **WHEN** 为测试结果比较能力编写测试
- **THEN** 测试 SHALL 覆盖空日志、只有 stdout、只有 stderr、报告 artifact 缺失、大日志裁剪、大报告裁剪、无差异项、低置信度输出、重复创建比较、取消运行中比较和敏感信息脱敏

#### Scenario: test-support 手动触发接口测试
- **WHEN** 为测试结果比较能力编写 E2E 或开发辅助测试
- **THEN** 测试 MAY 使用 test-support only 的手动触发比较接口
- **AND** 测试 SHALL 验证默认生产构建不包含该接口
- **AND** 测试 SHALL 验证该接口不接受模型参数、prompt、完整日志或 provider secret
