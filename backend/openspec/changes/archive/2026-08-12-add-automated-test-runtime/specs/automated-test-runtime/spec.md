## ADDED Requirements

### Requirement: 自动化测试运行时必须支持远程测试执行和日志回收
自动化测试运行时 SHALL 在用户指定的远程环境中运行测试脚本或命令，并 SHALL 回收测试输出、退出码、stdout/stderr 日志和用户指定的测试报告产物。

#### Scenario: 创建远程测试任务
- **WHEN** 用户基于项目、源码版本、执行环境和测试命令创建自动化测试任务
- **THEN** 后端 SHALL 创建 `AUTOMATED_TEST` 任务
- **AND** 后端 SHALL 创建或预留关联的测试运行记录
- **AND** 任务输入 SHALL 包含 `projectId`、`sourceRevisionId`、`environmentId`、可选 `buildRunId`、测试命令或脚本引用、工作目录、超时配置、可选 `environmentVariables` 和可选 `reportTargets` 数组
- **AND** 任务输入 MUST NOT 包含明文凭据、服务器真实路径或完整日志

#### Scenario: 执行远程测试
- **WHEN** worker 处理自动化测试任务
- **THEN** worker SHALL 在指定远程环境执行测试脚本或命令
- **AND** worker SHALL 记录退出码、状态、开始时间、结束时间、stdout 日志和 stderr 日志
- **AND** worker SHALL 将测试输出写入任务日志事件和完整日志文件元数据
- **AND** worker SHALL 在命令结束后按报告回收规则回收测试报告产物

#### Scenario: 测试任务状态
- **WHEN** 远程测试命令完成
- **THEN** 如果退出码为 0，任务 SHALL 标记为 `SUCCEEDED`
- **AND** 如果退出码非 0 或运行失败，任务 SHALL 标记为 `FAILED`
- **AND** 如果任务被取消，任务 SHALL 标记为 `CANCELLED`
- **AND** 如果任务超时，任务 SHALL 标记为 `TIMEOUT`

### Requirement: 自动化测试必须保存输出摘要而不解析用例级报告
自动化测试运行时 SHALL 保存退出码、状态和日志引用，并 MUST NOT 依赖 JUnit、CTest、pytest 或类似结构化报告解析。

#### Scenario: 保存测试输出摘要
- **WHEN** 测试执行完成
- **THEN** 后端 SHALL 保存退出码、状态、耗时、日志引用和受控输出摘要
- **AND** 后端 SHALL 允许通过数、失败数和跳过数字段为空

### Requirement: 自动化测试必须支持文字报告产物回收
自动化测试运行时 SHALL 支持回收测试程序生成的文字报告，使 stdout 内容很少时仍能保留可审计测试结果。

#### Scenario: 回收多个指定报告文件
- **WHEN** 测试任务提交 `reportTargets` 数组且包含多个 `type=FILE` 的相对报告文件路径
- **THEN** worker SHALL 在测试命令结束后从远端读取这些文件
- **AND** 后端 SHALL 将文件保存为受控制品或对象存储 artifact
- **AND** 测试详情 SHALL 返回报告文件名、大小、sha256、content type 和 artifact 摘要

#### Scenario: 回收报告输出目录
- **WHEN** 测试任务提交 `reportTargets` 数组且包含 `type=DIRECTORY` 的相对报告输出目录
- **THEN** worker SHALL 只在该目录下按受控规则扫描可回收报告文件
- **AND** worker SHALL 按配置限制扫描深度、最大匹配数量、单文件大小和总大小
- **AND** 超过限制时 SHALL 保存脱敏警告摘要并继续保留已成功回收的报告

#### Scenario: 报告路径安全
- **WHEN** `reportTargets` 包含非法 `type`、绝对路径、`..` 越界、空路径或不允许的目录扫描
- **THEN** 后端 SHALL 拒绝创建任务或在 worker 阶段标记报告回收失败
- **AND** 后端 MUST NOT 从远端读取工作目录外的文件
- **AND** API、日志和任务事件 MUST NOT 暴露远端敏感绝对路径

#### Scenario: 未配置报告回收
- **WHEN** 测试任务未提交 `reportTargets` 或提交空数组
- **THEN** worker SHALL 只回收退出码、stdout 和 stderr
- **AND** 测试任务 SHALL NOT 因未配置报告文件而失败

### Requirement: 自动化测试必须支持任务级环境变量
自动化测试运行时 SHALL 接收前端传入的任务级环境变量，并 SHALL 在远程测试命令或脚本执行时注入这些变量。

#### Scenario: 注入测试环境变量
- **WHEN** 测试任务请求包含 `environmentVariables`
- **THEN** 后端 SHALL 校验变量名格式和值长度
- **AND** worker SHALL 在远程测试命令或临时脚本执行时注入这些变量
- **AND** 变量只作用于当前测试任务

#### Scenario: 环境变量脱敏
- **WHEN** 后端保存任务输入摘要、任务事件、审计记录或 API 响应
- **THEN** 后端 MUST 对环境变量值进行脱敏
- **AND** 名称包含 `TOKEN`、`PASSWORD`、`SECRET`、`KEY` 或 `PASS` 的变量 MUST 被视为敏感变量

#### Scenario: 不创建用例级结果
- **WHEN** 测试日志或输出中存在结构化测试报告路径
- **THEN** MVP 后端 MUST NOT 解析用例级结果
- **AND** MVP 后端 MUST NOT 创建 `test_cases` 或等效用例级持久化记录

### Requirement: 自动化测试必须支持取消和超时
自动化测试运行时 SHALL 复用运行中任务取消机制终止本地或远程测试执行。

#### Scenario: 取消运行中测试
- **WHEN** 用户取消 `AUTOMATED_TEST` 任务
- **THEN** 后端 SHALL 将任务状态更新为 `CANCELLED`
- **AND** 后端 SHALL 投递取消清理消息
- **AND** worker SHALL 尝试终止正在运行的远程测试命令
- **AND** 已产生的测试输出、日志和已回收报告 SHALL 保留为取消前的事实记录

#### Scenario: 测试超时
- **WHEN** 单侧测试命令超过配置的超时时间
- **THEN** worker SHALL 尝试终止该侧测试进程
- **AND** 后端 SHALL 将该侧结果标记为超时
- **AND** 若任务无法确认远程测试完成状态，任务 SHALL 标记为 `TIMEOUT` 或 `FAILED`

### Requirement: 自动化测试运行时必须保护权限和敏感信息
自动化测试运行时 SHALL 对所有 API、任务输入、日志摘要和审计信息执行项目访问控制与脱敏。

#### Scenario: 权限校验
- **WHEN** 用户创建、查询、取消或下载自动化测试相关资源
- **THEN** 后端 SHALL 校验用户有权访问测试运行所属项目
- **AND** 无权限响应 MUST NOT 泄漏测试运行、任务、环境或日志是否存在

#### Scenario: 敏感信息脱敏
- **WHEN** 后端保存测试命令、任务输入、任务事件、日志摘要或审计记录
- **THEN** 后端 MUST 删除或遮蔽密码、token、SSH 私钥、passphrase、Authorization header 和服务器真实敏感路径
