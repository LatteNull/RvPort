## Why

后端现有单元测试虽已覆盖部分核心流程，但当前 JaCoCo 基线仅为行覆盖率 55.22%、分支覆盖率 45.11%，大量 Repository、Handler、Service 与 Controller 路径尚未受到独立、可重复的验证。需要系统性回补测试并建立至少 90% 的质量门槛，同时确保普通单元测试不依赖 PostgreSQL、Redis、RabbitMQ、MinIO、SSH、外部 HTTP 服务或 Docker。

## What Changes

- 盘点后端全部项目自有可执行代码，按 Repository、Service、Handler、Controller、Adapter 与公共逻辑建立覆盖缺口清单。
- 建立纯 JVM 的外部依赖模拟边界：Service/Handler 模拟应用级客户端或适配器返回值，jOOQ Repository 使用模拟连接与数据提供器验证 SQL、绑定参数和结果映射。
- 为既有业务代码补充正常流程、异常流程和 edge case 单元测试，并将项目整体及受影响模块的行覆盖率、分支覆盖率均提升至至少 90%。
- 禁止通过排除项目自有业务代码、缩小统计范围、空断言或仅加载类的方式提高覆盖率。
- 原则上不修改业务实现；仅在无法合理隔离依赖时，允许在不改变原有行为的前提下重构执行边界以提高可测试性。
- 测试发现疑似业务缺陷时不在本 change 中直接修复：规范明确的差异记录为阻塞缺陷，行为定义不明确的情况保留特征测试并登记待确认问题。
- 将依赖真实基础设施或真实环境的测试与普通单元测试生命周期隔离，默认 `mvn test` 和覆盖率检查可在无外部服务环境独立运行。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `backend-app-skeleton`: 强化后端单元测试隔离、覆盖率门槛、覆盖范围、可测试性重构边界与测试发现缺陷的处理要求。

## Impact

- 主要影响 `backend/src/test/java`、Maven 测试与 JaCoCo 配置，以及必要的测试 fixture/helper。
- 可能对少量直接创建外部进程或连接的业务类做等价结构重构，但不得改变业务行为或 API 合约。
- 不新增生产 API，不依赖 Docker/Testcontainers，不连接真实数据库、缓存、消息队列、对象存储、SSH、Agent 或第三方 HTTP 服务。
- 当前基线为 639 个测试（0 失败、0 错误、2 跳过）；整体达到 90% 行覆盖率至少还需覆盖约 7,645 行，Repository 是首要缺口。
