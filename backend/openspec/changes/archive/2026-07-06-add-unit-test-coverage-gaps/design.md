## Context

当前后端已有 66 个 Maven 测试，其中认证、安全过滤器、密码策略、Redis/RabbitMQ 封装、任务主干和部分领域 Service 已有基础覆盖。但盘点发现测试分布不均：部分模块只有 happy path，Controller 请求校验和 Repository 查询条件覆盖不足，worker 和任务异常分支也偏薄。

项目已经确立全局测试约定：后续后端变更需要覆盖正常流程、异常流程和 edge case。本 change 不是新增业务能力，而是对既有 Java 单元测试进行补强，让当前代码基线更接近该约定。

## Goals / Non-Goals

**Goals:**

- 按模块补齐已有 Java 单元测试缺口。
- 优先覆盖高风险分支：敏感信息脱敏、凭据边界、任务投递、worker 失败处理、跳板机约束、源码激活和日志路径安全。
- 增加轻量 MockMvc 测试，覆盖 Controller 请求校验、统一错误包络和关键权限边界。
- 保持 `mvn test` 可本地直接运行，不依赖真实 PostgreSQL、Redis、RabbitMQ 或 Docker Compose。

**Non-Goals:**

- 不新增业务功能。
- 不调整 HTTP API 契约、数据库 schema、Liquibase changelog 或 Docker Compose 配置。
- 不把独立 API E2E 并入 `mvn test`。
- 不为 Repository 引入必须依赖真实基础设施的测试；如需要数据库级验证，应使用可跳过或显式开启的轻量集成测试。

## Decisions

### 优先补 Service 层异常和 edge case

Service 层承载最多业务规则，例如跳板机校验、源码导入、任务创建和凭据脱敏。优先补这些测试能用较低成本覆盖最多业务风险。

备选方案是先补 Controller 测试，但 Controller 多数只是委托 service 和参数绑定，先补 service 能更直接锁住核心规则。

### Controller 测试使用 MockMvc 轻量验证

Controller 层补测以 standalone MockMvc 或最小 Spring Security context 为主，覆盖请求校验、错误包络、权限和强制改密边界。

不使用完整 Spring Boot 集成测试作为默认方案，避免 `mvn test` 变慢或依赖真实基础设施。

### Repository 测试作为低优先级可选项

Repository 当前缺少直接测试，但它们依赖 jOOQ 和 PostgreSQL 行为。除非发现具体查询风险，本 change 优先通过 service/mock 和 E2E 兜底，避免引入新的数据库测试复杂度。

如果补 Repository 测试，应显式隔离为可跳过的轻量集成测试，并保持普通 `mvn test` 不要求 Docker。

### 测试只断言安全可见的行为

涉及密码、token、SSH 私钥、脚本文本和本地路径时，测试应断言响应、任务 input snapshot、审计 details 或队列消息不包含明文秘密，而不是断言具体加密密文。

这样可以避免测试和加密实现细节过度耦合。

## Risks / Trade-offs

- 单元测试过度 mock 可能遗漏真实数据库映射问题 → 通过已有 E2E 和必要时的显式迁移测试兜底。
- 补测过程中可能发现生产代码真实缺陷 → 允许在 apply 阶段做最小修复，并在任务中记录原因。
- Controller 测试过多可能重复 E2E 覆盖 → Controller 单测只覆盖参数校验、安全过滤和错误包络，完整业务链路仍由 E2E 覆盖。
- 对日志、审计和凭据的脱敏断言容易漏字段 → 使用统一的敏感词断言集合，并覆盖 password、token、privateKey、passphrase、script 等典型字段。
