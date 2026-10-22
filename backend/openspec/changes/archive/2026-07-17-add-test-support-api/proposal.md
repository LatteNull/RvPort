## Why

部分端到端测试需要稳定触发内部机制，例如 SSE 推送、定时清理、任务修复、队列消费和邮件 outbox 校验。仅依赖真实长流程会让 E2E 变慢、不稳定，也难以覆盖边界条件。

同时，这类能力不能进入生产 jar，否则会增加攻击面。需要建立一套只在测试/开发构建中存在的 test-support API。

## What Changes

- 新增 test-support API，统一使用 `/api/test-support/**` 前缀。
- test-support API 源码放入独立源码目录，默认生产构建不编译、不打包进 jar。
- 新增 Maven 构建 profile，仅在显式启用时把 test-support 源码加入编译产物。
- 迁移现有 `/api/dev/session` 能力到 test-support API，并从生产源码中移除该 controller。
- 提供 E2E 需要的测试辅助能力：
  - 创建测试会话。
  - 插入任务事件并触发 SSE。
  - 主动触发 SSE heartbeat。
  - 插入用户 action token fixture。
  - 主动触发用户 action token 清理。
  - 主动触发 pending task dispatch repair。
  - 可选地直接处理指定任务。
  - 查询和清理测试邮件 outbox。
  - 创建 SBOM 轻量 fixture。
  - 查询测试队列状态。
  - 清理指定 run id 的测试 runtime 数据。
- 更新 E2E runner，使需要稳定内部触发的模块优先使用 test-support API。

## Capabilities

### New Capabilities

- `test-support-api`: 测试专用 API 的构建隔离、安全边界、接口范围和行为约束。

### Modified Capabilities

- `api-e2e-test-suite`: E2E 可使用 test-support API 准备 fixture、触发内部机制并验证副作用。
- `backend-app-skeleton`: 后端构建必须支持生产 jar 排除 test-support 源码，并支持显式 test-support 构建。
- `backend-api-design`: 迁移现有 dev session 能力到 test-support API，并明确生产 API 不暴露测试辅助接口。

## Impact

- Maven 构建配置增加 test-support profile 和独立源码目录。
- 安全配置需要对 `/api/test-support/**` 建立单独规则。
- 现有 `DevSessionController` 需要迁移或移除。
- E2E 测试可减少对真实长任务的依赖，但仍需保留关键真实链路验证。
- 生产构建流程需要明确不启用 test-support profile。
