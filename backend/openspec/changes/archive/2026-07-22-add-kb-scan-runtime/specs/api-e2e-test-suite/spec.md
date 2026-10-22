## ADDED Requirements

### Requirement: API E2E 必须覆盖 KB 扫描验证和清理
API E2E 测试套件 SHALL 覆盖 KB 扫描相关的端到端验证入口、真实副作用检查、finding 入库检查和测试数据清理。

#### Scenario: 覆盖 KB 扫描主链路
- **WHEN** 运行 KB API E2E 用例且基础设施、后端服务、worker 和 KB Scanner 可用
- **THEN** 测试 SHALL 创建或复用测试项目和源码版本
- **AND** 测试 SHALL 创建 `KB_SCAN` 任务并等待任务终态
- **AND** 测试 SHALL 校验 `kb_scan_runs`、`findings`、KB artifact metadata、`tasks`、`task_events`、`task_log_events` 和 `tool_runs` 的真实副作用

#### Scenario: 覆盖 KB API 查询
- **WHEN** KB API E2E 用例完成一次成功扫描
- **THEN** 测试 SHALL 调用 `GET /api/projects/{projectId}/kb-scans`
- **AND** 测试 SHALL 调用 `GET /api/kb-scans/{scanId}`
- **AND** 测试 SHALL 调用 `GET /api/kb-scans/{scanId}/findings`
- **AND** 测试 SHALL 调用 `GET /api/findings/{findingId}`
- **AND** 测试 SHALL 校验 API 响应不包含服务器真实路径或完整 scanner output 原文

#### Scenario: 覆盖 KB 扫描异常流程
- **WHEN** 运行 KB API E2E 异常用例
- **THEN** 测试 SHALL 覆盖源码版本不存在、源码版本不属于项目、无 active source、无项目权限和 scanner 失败
- **AND** 测试 SHALL 验证失败不会写入成功态 findings 或成功态 artifact

#### Scenario: 覆盖 KB 查询分页过滤排序
- **WHEN** KB API E2E 创建包含多条 finding 的扫描结果
- **THEN** 测试 SHALL 验证 finding 列表支持分页
- **AND** 测试 SHALL 验证 severity、ruleId、filePath 或 keyword 过滤
- **AND** 测试 SHALL 验证合法排序和非法排序字段拒绝

#### Scenario: 清理 KB E2E 数据
- **WHEN** KB API E2E 运行成功或失败
- **THEN** runner SHALL 清理本次 run id 创建的项目、源码版本、扫描运行、findings、artifact metadata、任务、任务事件、日志和本地测试输出
- **AND** 清理 MUST NOT 删除用户手工创建的真实项目或真实扫描结果

### Requirement: E2E runner 必须支持 KB 模块
API E2E runner SHALL 将 KB 扫描用例作为独立 `kb` 模块运行。

#### Scenario: 按 KB 模块运行
- **WHEN** 开发者执行 `node e2e/runner.js run --module=kb`
- **THEN** runner SHALL 只运行 KB 扫描相关 E2E case
- **AND** runner SHALL 完成公共 setup、管理员登录、CSRF 初始化、基础设施检查和清理
- **AND** runner SHALL NOT 运行 auth、project、task、sbom 等无关模块 case

#### Scenario: KB 模块 post-run assertion
- **WHEN** runner 运行 `kb` 模块
- **THEN** runner SHALL 执行 RabbitMQ 队列可查询、任务消息脱敏、任务事件项目隔离和 KB 结果入库检查
- **AND** runner SHALL NOT 因无关模块的历史数据失败
