## MODIFIED Requirements

### Requirement: 自动化测试运行时必须支持远程测试执行和日志回收
自动化测试运行时 SHALL 基于关联构建运行或项目当前运行环境配置确定远程测试环境，并 SHALL 回收测试输出、退出码、stdout/stderr 日志和用户指定的测试报告产物。

#### Scenario: 创建远程测试任务
- **WHEN** 用户基于项目、源码版本、构建运行和测试命令创建自动化测试任务
- **THEN** 后端 SHALL 创建 `AUTOMATED_TEST` 任务
- **AND** 后端 SHALL 从关联构建运行确定测试环境
- **AND** 后端 SHALL 校验构建运行属于同一项目、同一源码版本且属于当前环境配置版本
- **AND** 后端 SHALL 创建或预留关联的测试运行记录
- **AND** 任务输入 SHALL 包含 `projectId`、`sourceRevisionId`、环境 ID、环境配置版本、可选 `buildRunId`、测试命令或脚本引用、工作目录、超时配置、可选 `environmentVariables` 和可选 `reportTargets` 数组
- **AND** 任务输入 MUST NOT 包含明文凭据、服务器真实路径或完整日志

#### Scenario: 执行远程测试
- **WHEN** worker 处理自动化测试任务
- **THEN** worker SHALL 在任务输入确定的远程环境执行测试脚本或命令
- **AND** worker SHALL 记录退出码、状态、开始时间、结束时间、stdout 日志和 stderr 日志
- **AND** worker SHALL 将测试输出写入任务日志事件和完整日志文件元数据
- **AND** worker SHALL 在命令结束后按报告回收规则回收测试报告产物

#### Scenario: 测试任务状态
- **WHEN** 远程测试命令完成
- **THEN** 如果退出码为 0，任务 SHALL 标记为 `SUCCEEDED`
- **AND** 如果退出码非 0 或运行失败，任务 SHALL 标记为 `FAILED`
- **AND** 如果任务被取消，任务 SHALL 标记为 `CANCELLED`
- **AND** 如果任务超时，任务 SHALL 标记为 `TIMEOUT`

#### Scenario: 请求不再提交环境 ID
- **WHEN** 用户创建自动化测试任务
- **THEN** 请求 MUST NOT 要求提交 `environmentId`
- **AND** 后端 MUST NOT 让请求体中的 `environmentId` 覆盖关联构建运行确定的环境
