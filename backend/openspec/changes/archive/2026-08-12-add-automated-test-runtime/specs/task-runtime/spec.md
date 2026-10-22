## ADDED Requirements

### Requirement: 任务运行时必须支持自动化测试任务
任务运行时 SHALL 支持 `AUTOMATED_TEST` 任务类型，用于异步执行远程自动化测试并回收输出日志。

#### Scenario: 创建自动化测试任务
- **WHEN** 自动化测试 API 创建任务
- **THEN** 任务运行时 SHALL 创建任务类型为 `AUTOMATED_TEST` 的 `tasks` 记录
- **AND** `tasks.input_snapshot` SHALL 包含项目、源码版本、执行环境、可选构建运行、脚本引用、工作目录、超时摘要、环境变量摘要和报告回收目标摘要
- **AND** `tasks.input_snapshot` MUST NOT 包含明文凭据、服务器真实路径或完整日志

#### Scenario: 自动化测试任务事件
- **WHEN** 自动化测试任务进入 `QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 任务运行时 SHALL 追加对应任务事件
- **AND** 项目级 SSE SHALL 只向测试任务所属项目推送事件

#### Scenario: 自动化测试日志事件
- **WHEN** worker 捕获远程测试 stdout/stderr
- **THEN** 任务运行时 SHALL 写入任务日志文件和任务日志事件
- **AND** 日志事件 SHALL 允许前端通过任务日志 SSE 查看运行中输出
- **AND** 日志事件 MUST NOT 包含明文凭据或服务器真实敏感路径

#### Scenario: 自动化测试任务取消
- **WHEN** 用户取消 `AUTOMATED_TEST` 任务
- **THEN** 任务运行时 SHALL 按运行中任务取消机制更新任务状态并投递取消清理消息
- **AND** 取消处理 SHALL 尝试终止正在运行的远程测试命令

### Requirement: 自动化测试 handler 必须通过执行上下文写状态和日志
自动化测试 handler SHALL 复用任务执行上下文更新进度、写日志、写终态和报告错误。

#### Scenario: 更新测试进度
- **WHEN** 自动化测试进入远程执行或结果保存阶段
- **THEN** handler SHALL 通过执行上下文更新任务进度和可展示消息
- **AND** handler SHOULD NOT 直接写入 `tasks` 或 `task_events`

#### Scenario: handler 失败
- **WHEN** 自动化测试 handler 因输入非法、环境不可用、SSH 执行失败或日志保存失败而无法完成
- **THEN** 任务运行时 SHALL 将任务标记为受控终态
- **AND** 错误摘要 MUST 为脱敏后的业务错误信息

### Requirement: 构建和测试任务运行时必须支持任务级环境变量
任务运行时 SHALL 支持构建任务和自动化测试任务携带前端传入的任务级环境变量，并 SHALL 在远程命令或临时脚本执行时注入。

#### Scenario: 构建任务注入环境变量
- **WHEN** 构建任务输入包含 `environmentVariables`
- **THEN** 构建 handler SHALL 在远程构建命令或脚本执行时注入这些变量
- **AND** 变量只作用于当前构建任务

#### Scenario: 测试任务注入环境变量
- **WHEN** 自动化测试任务输入包含 `environmentVariables`
- **THEN** 自动化测试 handler SHALL 在远程测试命令或脚本执行时注入这些变量
- **AND** 变量只作用于当前测试任务

#### Scenario: 环境变量不泄漏
- **WHEN** 任务运行时保存输入快照、任务事件、日志摘要或错误摘要
- **THEN** 环境变量值 MUST 被脱敏
- **AND** 任务运行时 MUST NOT 将任务级环境变量写入正式环境配置或凭据表
