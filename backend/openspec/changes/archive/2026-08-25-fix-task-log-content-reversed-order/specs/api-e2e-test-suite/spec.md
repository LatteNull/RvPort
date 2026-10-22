## MODIFIED Requirements

### Requirement: API E2E 必须覆盖任务日志内容读取
API E2E 测试套件 SHALL 覆盖完成态任务日志内容读取 API 的正常流程、异常流程和 edge case。

#### Scenario: 默认读取三类日志
- **WHEN** E2E 创建包含 merged/stdout/stderr 日志的任务 fixture 并调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** 响应 SHALL 包含三类日志
- **AND** 每类默认最多返回最新展示页 100 行

#### Scenario: 单类日志读取
- **WHEN** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 响应 SHALL 只包含 stdout 日志内容
- **AND** 响应 SHALL 不包含 merged 或 stderr 内容

#### Scenario: 多类不同 offset
- **WHEN** E2E 使用不同 offset 请求 merged、stdout 和 stderr
- **THEN** 每类日志 SHALL 返回对应展示顺序 offset 的文本片段
- **AND** `hasMore` SHALL 正确表达是否还有更早日志

#### Scenario: 倒序日志首屏返回最新内容
- **WHEN** E2E 创建文件头为最新日志、文件尾为最早日志的任务日志 fixture
- **AND** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=0&lines=2`
- **THEN** 响应 SHALL 返回文件头部的最新两行
- **AND** 响应 MUST NOT 返回文件尾部的最早两行

#### Scenario: 倒序日志 offset 返回更旧内容
- **WHEN** E2E 创建文件头为最新日志、文件尾为最早日志的任务日志 fixture
- **AND** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=2&lines=2`
- **THEN** 响应 SHALL 跳过最新两行并返回更旧日志
- **AND** `hasMore` SHALL 正确表达是否仍有更旧日志

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
