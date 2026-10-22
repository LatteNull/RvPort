## ADDED Requirements

### Requirement: E2E 必须覆盖阶段 readiness
API E2E 测试套件 SHALL 覆盖项目级阶段 readiness 接口的正常流程、异常流程和边界情况。

#### Scenario: readiness 正常返回前置事实
- **WHEN** E2E 创建项目、源码、运行环境和相关执行记录
- **THEN** E2E SHALL 调用 `GET /api/projects/{projectId}/readiness?stageId=...`
- **AND** 响应 SHALL 包含预期 prerequisite key、status、referenceId 和 reasonCode

#### Scenario: readiness 返回缺失和过期状态
- **WHEN** E2E 构造缺失 active source、缺失环境或旧 Context 记录
- **THEN** readiness SHALL 返回 `MISSING` 或 `STALE`
- **AND** 后端 MUST NOT 将旧 Context 结果判定为满足当前阶段

#### Scenario: readiness 权限隔离
- **WHEN** 普通用户访问其他用户项目的 readiness
- **THEN** E2E SHALL 验证请求失败
- **AND** 响应 MUST NOT 暴露被访问项目的执行记录信息

### Requirement: E2E 必须覆盖领域 latest 外壳
API E2E 测试套件 SHALL 覆盖各领域 latest 接口的统一外壳、无记录、失败记录和旧 Context 行为。

#### Scenario: latest 返回统一外壳
- **WHEN** E2E 调用任一领域 latest 接口
- **THEN** 响应业务数据 SHALL 包含 `context`、`freshness`、`execution` 和 `result`
- **AND** `result` SHALL 保持对应领域结构

#### Scenario: latest 不回退到旧成功记录
- **WHEN** E2E 构造当前 Context 最新失败记录和更早成功记录
- **THEN** latest SHALL 返回失败 execution
- **AND** 后端 MUST NOT 返回更早成功记录作为当前 latest

#### Scenario: latest 无记录成功返回
- **WHEN** E2E 对没有执行记录的领域调用 latest
- **THEN** 响应 SHALL 成功
- **AND** `execution` 和 `result` SHALL 为 `null`

### Requirement: E2E 必须覆盖写接口二次校验
API E2E 测试套件 SHALL 验证执行类写接口不会信任前端先前获得的 readiness 结果。

#### Scenario: Context 改变后写接口拒绝创建任务
- **WHEN** E2E 先查询 readiness 得到满足状态
- **AND** 随后修改源码版本或运行环境版本
- **THEN** 创建依赖分析、自动化测试、报告或归档任务 SHALL 返回 `PREREQUISITE_NOT_SATISFIED`
- **AND** 错误详情 SHALL 包含不满足的 prerequisite 状态
