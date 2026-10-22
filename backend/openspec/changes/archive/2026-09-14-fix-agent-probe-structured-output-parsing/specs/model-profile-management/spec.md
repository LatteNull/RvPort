## ADDED Requirements

### Requirement: Agent Probe 必须从稳定的结构化输出边界解析结果
模型 Profile Agent Probe SHALL 优先从 Agent Runtime 的 stdout 提取结构化结果，并仅在 stdout 不包含满足当前检查契约的 JSON 时，才从移除传输包装后的 merged output 回退提取。诊断日志中的通道标签、ANSI 控制字符和输出缓冲分块 MUST NOT 导致有效 Agent 结果被误判为不兼容。

#### Scenario: stdout 直接返回预期 JSON
- **WHEN** Agent Runtime 以零退出码结束且 stdout 包含满足当前 probe 预期字段的 JSON 对象
- **THEN** 后端 SHALL 将该 probe 判定为成功
- **AND** merged output 中是否存在 `[STDOUT]` 标签 MUST NOT 改变结果

#### Scenario: stdout 包含普通日志和多行 JSON
- **WHEN** stdout 在最终结果前后包含普通日志、Markdown 代码块或多行格式化 JSON
- **THEN** 后端 SHALL 提取完整 JSON 对象并按当前 probe 预期字段验证

#### Scenario: merged output 包含 ANSI 和通道标签
- **WHEN** stdout 中没有可用结果，但 merged output 包含 ANSI 控制字符、`[STDOUT]`、`[STDERR]` 和满足契约的 JSON
- **THEN** 后端 SHALL 清除传输包装并成功提取该 JSON
- **AND** 清洗 MUST NOT 改写 JSON 字符串内部的普通内容

#### Scenario: 输出包含多个 JSON 候选
- **WHEN** Agent 输出包含多个合法 JSON 对象，其中只有部分对象满足当前 probe 的预期字段
- **THEN** 后端 SHALL 从后向前选择最后一个满足全部预期字段的对象
- **AND** 不匹配的 CLI 状态 JSON MUST NOT 导致有效结果被忽略或误判成功

#### Scenario: 进程失败但输出包含有效 JSON
- **WHEN** Agent Runtime 超时或以非零退出码结束，同时输出中存在满足字段要求的 JSON
- **THEN** 后端 SHALL 保持超时或执行失败状态
- **AND** MUST NOT 仅因存在 JSON 而将 probe 判定为成功

#### Scenario: 输出不存在匹配对象
- **WHEN** Agent Runtime 零退出但 stdout 与清洗后的 merged output 均不存在满足预期字段的 JSON 对象
- **THEN** 后端 SHALL 返回 `AGENT_PROBE_OUTPUT_INVALID`
- **AND** 失败消息 SHALL 使用脱敏且限制长度的诊断输出

#### Scenario: workspace 写入检查
- **WHEN** Agent 返回 workspace write 成功 JSON
- **THEN** 后端 SHALL 继续验证约定输出文件存在、文件内容为 JSON 对象且 marker 匹配
- **AND** 只有响应与文件检查全部通过时 SHALL 将 workspace write probe 判定为成功

### Requirement: Agent Probe 结构化解析必须具备独立单元测试
后端 SHALL 为结构化输出提取和兼容性判定提供不依赖外部模型、数据库、Redis、RabbitMQ、MinIO、SSH 或 Docker 的单元测试，覆盖正常行为、异常路径和 edge case。项目整体与受影响模块的行覆盖率及可用的分支覆盖率 SHALL 均不低于 90%。

#### Scenario: 独立运行解析测试
- **WHEN** 开发者在无外部服务环境运行 Maven 单元测试
- **THEN** 测试 SHALL 使用 mock 或 fixture 输出覆盖 Codex、DeepSeek Harness 和 OpenCode 的结构化输出形态
- **AND** 测试 SHALL 覆盖 ANSI、通道标签、日志前后缀、多行 JSON、Markdown fence、多个对象、字符串内花括号、截断 JSON、字段不匹配、超时、非零退出和凭据脱敏

#### Scenario: 验收覆盖率
- **WHEN** 本 change 完成实现并执行覆盖率检查
- **THEN** JaCoCo SHALL 将未被测试加载的项目自有可执行代码纳入统计
- **AND** 项目整体与受影响模块行覆盖率、分支覆盖率 SHALL 均达到至少 90%
