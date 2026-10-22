## ADDED Requirements

### Requirement: API E2E 可以使用 test-support API 稳定触发内部机制
API E2E runner SHALL 在显式配置 test-support API 时，使用该 API 准备 fixture、触发内部机制、查询副作用和清理测试数据。

#### Scenario: test-support 可用
- **WHEN** E2E runner 配置了 test-support base URL 和 token
- **THEN** runner SHALL 能调用 `/api/test-support/**` 完成 fixture 准备、定时任务触发、SSE 触发和 outbox 查询

#### Scenario: test-support 不可用
- **WHEN** E2E runner 未配置 test-support token 或后端未以 test-support 构建启动
- **THEN** runner SHALL 对依赖 test-support 的用例给出明确错误或跳过原因
- **AND** runner MUST NOT 静默假装该用例通过

### Requirement: API E2E 必须保留关键真实链路验证
API E2E 使用 test-support API 时，仍 SHALL 保留关键真实 API 和真实副作用验证。

#### Scenario: 真实认证链路
- **WHEN** E2E 覆盖认证模块
- **THEN** 测试 SHALL 继续覆盖 CSRF、登录、当前用户、修改密码和退出登录的真实 API 调用

#### Scenario: 真实任务链路
- **WHEN** E2E 覆盖任务创建模块
- **THEN** 测试 SHALL 继续验证真实任务创建、任务事件、数据库状态和队列副作用
- **AND** test-support 只 MAY 用于缩短等待、触发 repair 或制造边界事件

### Requirement: API E2E 必须验证 test-support 安全边界
API E2E SHALL 覆盖 test-support API 的 token 校验和生产构建隔离边界。

#### Scenario: token 错误
- **WHEN** E2E 使用缺失或错误的 test-support token 调用测试辅助 API
- **THEN** 后端 SHALL 拒绝请求

#### Scenario: 默认生产构建
- **WHEN** E2E 或构建验证使用默认生产 jar 启动后端
- **THEN** `/api/test-support/**` SHALL 不可访问

### Requirement: API E2E 清理可以委托 test-support runtime 清理
API E2E runner MAY 使用 test-support runtime 清理接口清理本次 run id 关联的数据，但 SHALL 保留失败报告。

#### Scenario: 使用 run id 清理
- **WHEN** E2E 运行结束并配置了 test-support API
- **THEN** runner MAY 调用 `POST /api/test-support/runtime:cleanup` 清理本次 run id 的测试数据

#### Scenario: 清理失败
- **WHEN** test-support runtime 清理返回失败
- **THEN** runner SHALL 返回失败状态或明确输出未清理资源
