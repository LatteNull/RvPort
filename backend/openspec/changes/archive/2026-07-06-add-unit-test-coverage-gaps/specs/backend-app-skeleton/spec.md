## MODIFIED Requirements

### Requirement: 后端骨架提供健康检查和基础测试
后端应用 SHALL 提供最小健康检查接口、可运行的 Maven 测试命令，并 SHALL 为后续 API change 预留独立 E2E 测试约定。

#### Scenario: 调用健康检查
- **WHEN** 客户端调用 `GET /health` 或 `GET /api/health`
- **THEN** 后端 SHALL 返回统一响应包络
- **AND** 响应 SHALL 表示应用进程可用

#### Scenario: 运行测试
- **WHEN** 开发者执行 Maven 测试命令
- **THEN** 应用 SHALL 运行基础测试
- **AND** 测试 SHALL 至少覆盖应用启动、配置绑定和健康检查
- **AND** 独立 API E2E 测试 MUST NOT 随普通 `mvn test` 自动运行

#### Scenario: 编写后续 change 测试
- **WHEN** 后续 OpenSpec change 涉及后端代码实现
- **THEN** 该 change SHALL 在任务或设计中明确测试覆盖范围
- **AND** 测试 SHALL 覆盖正常流程、异常流程和 edge case
- **AND** 如果该 change 不补充测试，必须在任务或设计中说明原因

#### Scenario: 编写后续 API change 测试
- **WHEN** 后续 OpenSpec change 新增或修改 HTTP API
- **THEN** 该 change SHALL 同步新增或更新独立 API E2E 测试用例
- **AND** E2E 测试 SHALL 覆盖该 API 的正常流程、异常流程和 edge case
- **AND** 如果该 API 不适合 E2E 测试，change 的设计或任务 MUST 说明原因

#### Scenario: 覆盖正常流程
- **WHEN** 为后端能力编写单元测试、API 测试、轻量集成测试或独立 E2E 测试
- **THEN** 测试 SHALL 覆盖合法输入下的成功创建、查询、更新、任务投递或状态流转

#### Scenario: 覆盖异常流程
- **WHEN** 为后端能力编写单元测试、API 测试、轻量集成测试或独立 E2E 测试
- **THEN** 测试 SHALL 覆盖鉴权失败、资源不存在、参数非法、状态不允许、外部依赖不可用、凭据或敏感配置缺失等错误路径

#### Scenario: 覆盖 edge case
- **WHEN** 为后端能力编写单元测试、API 测试、轻量集成测试或独立 E2E 测试
- **THEN** 测试 SHALL 覆盖空列表、可选字段为空、重复请求、边界分页、边界数值、重复状态切换、幂等行为、脱敏输出和路径隐藏等边界场景

#### Scenario: 回补既有测试覆盖缺口
- **WHEN** 盘点发现既有后端能力缺少正常流程、异常流程或 edge case 覆盖
- **THEN** 后端 SHALL 通过单元测试、API 测试或轻量集成测试回补缺口
- **AND** 如果某个缺口不适合在当前测试层回补，change 的设计或任务 MUST 说明不适用原因和替代验证方式
