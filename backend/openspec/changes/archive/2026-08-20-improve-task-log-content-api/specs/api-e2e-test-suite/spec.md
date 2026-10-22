## ADDED Requirements

### Requirement: API E2E 必须覆盖任务日志内容读取
API E2E 测试套件 SHALL 覆盖完成态任务日志内容读取 API 的正常流程、异常流程和 edge case。

#### Scenario: 默认读取三类日志
- **WHEN** E2E 创建包含 merged/stdout/stderr 日志的任务 fixture 并调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** 响应 SHALL 包含三类日志
- **AND** 每类默认最多返回最后 100 行

#### Scenario: 单类日志读取
- **WHEN** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 响应 SHALL 只包含 stdout 日志内容
- **AND** 响应 SHALL 不包含 merged 或 stderr 内容

#### Scenario: 多类不同 offset
- **WHEN** E2E 使用不同 offset 请求 merged、stdout 和 stderr
- **THEN** 每类日志 SHALL 返回对应 offset 的文本片段
- **AND** `hasMore` SHALL 正确表达是否还有更早日志

#### Scenario: 非法参数
- **WHEN** E2E 使用未知日志类型、负数 offset 或超过上限的 lines
- **THEN** API SHALL 返回统一参数校验错误

#### Scenario: 越权读取日志内容
- **WHEN** 普通用户读取其他用户项目任务的日志内容
- **THEN** API SHALL 返回安全错误
- **AND** 响应 MUST NOT 泄漏日志是否存在

#### Scenario: 构建和测试详情暴露日志引用
- **WHEN** E2E 查询构建详情和自动化测试详情
- **THEN** 响应 SHALL 暴露 merged/stdout/stderr 日志引用或明确缺失状态
- **AND** 前端可使用同一个任务日志内容接口读取这些日志内容
