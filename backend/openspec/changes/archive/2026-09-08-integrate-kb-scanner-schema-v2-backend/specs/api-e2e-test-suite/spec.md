## ADDED Requirements

### Requirement: API E2E 必须覆盖 KB Scanner schema v2 链路

API E2E 测试 MUST 覆盖后端调用真实 KB Scanner v2、导入 finding、查询详情和下载 artifact 的完整链路。

#### Scenario: 真实 scanner v2 扫描成功

- **GIVEN** 后端、worker、数据库、Redis、RabbitMQ 和对象存储均已启动
- **WHEN** E2E 通过 API 创建源码、触发 KB 扫描并等待任务完成
- **THEN** 任务 MUST 成功
- **AND** 保存的 `scan-result.json` MUST 包含 `schemaVersion: "2.0"`
- **AND** finding 列表 API MUST 返回扫描出的 v2 finding 摘要
- **AND** finding 详情 API MUST 返回完整 v2 payload
- **AND** artifact 下载 API MUST 能下载 JSON 和 HTML 两种格式

#### Scenario: 非 schema v2 结果失败

- **WHEN** E2E 或测试辅助能力注入 schema v1 或无版本扫描结果
- **THEN** 后端 MUST 拒绝导入
- **AND** 扫描任务 MUST 进入失败状态
- **AND** 失败原因 MUST 能通过任务状态或日志 API 查询

#### Scenario: 缺少主位置的 finding

- **WHEN** E2E 或 fixture 导入缺少 `fact.primaryLocation` 的 v2 finding
- **THEN** 后端 MUST 保留该 finding
- **AND** finding 详情 MUST 返回完整 evidence
- **AND** 代码上下文查询 MUST 返回明确的不可定位结果，而不是服务端异常

### Requirement: API E2E 仍必须遵循三类测试策略

新增和修改的 E2E MUST 覆盖正常流程、异常流程和 edge case。

#### Scenario: KB schema v2 E2E 分类

- **WHEN** 编写 KB schema v2 相关 E2E
- **THEN** 正常流程 MUST 覆盖真实扫描与查询
- **AND** 异常流程 MUST 覆盖版本不兼容或 scanner 依赖缺失
- **AND** edge case MUST 覆盖缺少位置、空 findings、结构化 diagnostics 等边界数据
