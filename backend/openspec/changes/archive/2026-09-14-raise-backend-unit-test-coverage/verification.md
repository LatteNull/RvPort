# 验证记录

## 最终结果

- 验证命令：`mvn -B clean verify`
- 测试数量：1,529
- 失败：0
- 错误：0
- 跳过：2
- 行覆盖率：96.91%（21,247 / 21,925）
- 分支覆盖率：91.02%（7,561 / 8,307）
- 统计业务 package：52 个
- 最低 package 行覆盖率：90.48%（`cn.rvport.backend.source.archive`）
- 最低 package 分支覆盖率：90.00%（`cn.rvport.backend.workflow`、`cn.rvport.backend.useraction`、`cn.rvport.backend.worker`）
- JaCoCo 报告：`target/site/jacoco/index.html`

## 覆盖率门禁

- BUNDLE 的行覆盖率与分支覆盖率均不得低于 90%。
- 每个项目自有业务 PACKAGE 的行覆盖率与分支覆盖率均不得低于 90%。
- 唯一覆盖率排除项为自动生成的 `cn/rvport/backend/jooq/**`。
- `mvn -B clean verify` 已通过 JaCoCo BUNDLE 与 PACKAGE 两级检查。

## 独立运行与跳过项

普通单元测试通过 `unit` profile 禁用外部基础设施副作用，不启动或访问 PostgreSQL、Redis、RabbitMQ、S3、SSH 服务及 Agent CLI。Repository、客户端和连接行为均使用 jOOQ mock、Mockito 或可注入执行边界模拟返回值。

两个跳过项均为显式隔离的真实环境测试：

- `LiquibaseMigrationTests`：缺少 `RVPORT_MIGRATION_TEST_ENABLED` 时跳过，需要显式 PostgreSQL 测试环境。
- `RealAdapterEnvironmentInfoSmokeTest`：缺少 `RVPORT_REAL_SSH_SMOKE_ENABLED` 时跳过，需要显式真实 SSH 环境。

## 缺陷与生产代码审查

- 新增测试发现的 3 个疑似业务问题已记录在 `test-discovered-issues.md`，本 change 未修改其业务行为。
- 生产代码变更仅用于注入进程、SSH、S3、邮件等外部执行边界，提取纯解析函数，或删除不可达的重复/废弃私有代码。
- 对外 API、持久化结构和业务语义未作调整。
- 测试代码未新增 `@Disabled`、真实凭据或隐式网络调用；本机地址仅作为不会建立连接的测试数据。
