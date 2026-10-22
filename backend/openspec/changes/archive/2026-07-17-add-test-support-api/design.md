## Context

当前 E2E 已经覆盖认证、项目、源码、环境、任务、SSE、SBOM 和邮件配置等主链路，但部分能力天然依赖异步机制或定时机制：

- SSE 需要稳定地产生事件、补发历史事件和触发 heartbeat。
- 用户 action token 清理依赖每日定时任务。
- pending task dispatch repair 依赖后台调度。
- 邮件 outbox、队列、SBOM artifact 等副作用需要可控查询和清理。
- 现有 `/api/dev/session` 能力位于生产源码目录，虽然有配置开关，但仍会被编译进生产 jar。

本 change 的核心约束是：测试辅助能力不能进入默认生产构建产物。运行时配置开关只能作为附加保护，不能作为唯一边界。

```
默认生产构建
src/main/java ───────────────▶ app.jar
src/test-support/java ──X────▶ 不编译、不打包

显式测试构建
src/main/java ───────────────▶ app-test-support.jar
src/test-support/java ───────▶ 仅 -Ptest-support 时加入
```

## Goals / Non-Goals

**Goals:**

- 新增 `/api/test-support/**` 测试辅助 API，用于 E2E fixture、内部机制触发、副作用查询和测试数据清理。
- 把 test-support 源码放入独立源码目录，并通过 Maven profile 显式加入编译。
- 默认 `mvn package` 产物不得包含 test-support controller、配置类、DTO 或相关资源。
- 迁移现有 dev session 能力到 test-support API，并从生产源码中移除 `/api/dev/session`。
- 为 E2E 提供稳定入口，覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不新增生产可用的运维 API。
- 不提供任意 SQL、任意命令执行、任意 Spring Bean 调用或通用调试控制台。
- 不通过新增 Spring profile 作为主要隔离手段。
- 不替代真实链路 E2E；test-support 只用于稳定准备、触发和断言。

## Decisions

### 1. 使用构建期隔离作为主要安全边界

test-support 源码放在 `src/test-support/java`，默认不属于 Maven source root。新增 `test-support` Maven profile，显式启用时通过 `build-helper-maven-plugin` 把该目录加入编译。

选择原因：

- 默认生产 jar 物理上不包含测试接口类，攻击面更小。
- 符合用户要求：不依赖额外 runtime profile。
- 保留本地和 E2E 构建的便利性。

备选方案：

- 仅使用 `@Profile` 或 `@ConditionalOnProperty`：实现简单，但 class 仍在生产 jar 中，不满足攻击面要求。
- 独立测试服务：隔离更强，但当前项目会增加部署和认证复杂度。

### 2. test-support 仍需要显式 token 保护

即使只有 `-Ptest-support` 构建才包含这些接口，运行时仍要求 `X-RvPort-Test-Support-Token` 与配置值匹配。没有配置 token 时，test-support API 必须拒绝请求或不启用。

选择原因：

- 防止测试构建被误部署后裸露内部触发能力。
- session 创建接口不能依赖已有登录态，因此需要独立 token。

备选方案：

- 仅绑定本机地址：对容器、远程 E2E、CI 不稳定。
- 仅要求超级管理员 session：无法覆盖“创建测试 session”场景。

### 3. 迁移 dev session 到 test-support

现有 `/api/dev/session` 改为 `/api/test-support/session`，请求必须携带 test-support token，并按用户名创建测试 session。

选择原因：

- 现有 dev session 是 E2E 便利能力，不属于生产 API。
- 迁移后可以从 `src/main/java` 删除 controller 和安全 permit 规则。

### 4. 测试辅助接口只暴露白名单动作

test-support API 只允许明确列出的 fixture、触发器、查询和清理能力。清理必须基于 run id、测试前缀或明确资源 ID，不允许执行任意 SQL。

选择原因：

- 方便 E2E 自动化，同时避免把测试接口演变成通用后门。
- 所有动作都可以被测试和审计。

### 5. E2E 优先使用 test-support 稳定触发内部机制

E2E runner 在检测到 test-support API 可用时，可用它触发定时任务、创建 SSE 事件、查询 outbox 和清理测试 runtime。关键真实链路仍保留，例如真实登录、真实 API 调用、真实任务投递和真实 artifact 查询。

选择原因：

- 缩短等待时间，降低异步不确定性。
- 对新增 API 的 E2E 更容易只运行相关模块。

## Risks / Trade-offs

- [Risk] 测试构建被误用于生产环境 → 默认构建不包含 test-support 源码；文档明确生产构建命令；启动时要求 token。
- [Risk] test-support API 权限过大 → 只实现白名单动作，不提供任意 SQL、shell、Bean 调用。
- [Risk] E2E 过度依赖 fixture 导致真实链路退化 → 每个模块保留至少一个真实主链路用例；fixture 用于边界和副作用验证。
- [Risk] Maven profile 造成构建命令混淆 → README 和 E2E 文档分别列出生产构建、测试构建和本地运行命令。
- [Risk] 清理误删真实数据 → 清理接口必须要求 run id 或测试资源前缀，默认拒绝空范围或过宽范围。

## Migration Plan

1. 新建 `src/test-support/java`，迁移 dev session controller。
2. 修改 Maven，新增 `test-support` profile。
3. 从生产安全配置中移除 `/api/dev/session` permit 规则。
4. 实现 test-support token 校验。
5. 实现 E2E 所需的 test-support API。
6. 更新 E2E runner 和文档。
7. 验证默认 jar 不包含 test-support 类，显式 profile 构建可运行 test-support API。

## Open Questions

- test-support token 是否统一放在根目录 `.env` 的 `RVPORT_TEST_SUPPORT_TOKEN`，还是 E2E runner 支持命令行覆盖。
- 队列状态查询是否只返回长度和死信统计，还是需要返回测试 run id 关联消息摘要。
