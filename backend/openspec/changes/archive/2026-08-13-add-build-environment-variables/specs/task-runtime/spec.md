## MODIFIED Requirements

### Requirement: 构建和测试任务运行时必须支持任务级环境变量
任务运行时 SHALL 支持构建任务和自动化测试任务携带前端传入的任务级环境变量，并 SHALL 在远程命令或临时脚本执行时注入。

#### Scenario: 构建任务注入环境变量
- **WHEN** 构建任务输入包含 `environmentVariables`
- **THEN** 构建 handler SHALL 在远程构建命令或脚本执行时注入这些变量
- **AND** 变量只作用于当前构建任务
- **AND** 变量注入 MUST 支持空格、引号、等号和其他常见 shell 特殊字符

#### Scenario: 测试任务注入环境变量
- **WHEN** 自动化测试任务输入包含 `environmentVariables`
- **THEN** 自动化测试 handler SHALL 在远程测试命令或脚本执行时注入这些变量
- **AND** 变量只作用于当前测试任务

#### Scenario: 环境变量不泄漏
- **WHEN** 任务运行时保存输入快照、任务事件、日志摘要或错误摘要
- **THEN** 环境变量值 MUST 被脱敏
- **AND** 任务运行时 MUST NOT 将任务级环境变量写入正式环境配置或凭据表
- **AND** 任务运行时 MUST NOT 将环境变量明文写入 RabbitMQ 消息、SSE data 或审计详情

#### Scenario: 构建任务环境变量校验失败
- **WHEN** 构建任务创建阶段发现环境变量输入非法
- **THEN** 任务运行时 MUST NOT 创建可执行构建任务
- **AND** API SHALL 返回统一参数校验错误

#### Scenario: 构建任务执行失败
- **WHEN** 构建 handler 因环境变量注入失败、远程 shell 不支持或 SSH 执行失败而无法完成
- **THEN** 任务运行时 SHALL 将任务标记为 `FAILED`
- **AND** 失败摘要 MUST NOT 包含环境变量明文、远端敏感绝对路径或完整命令输入
