## Why

用户邀请和忘记密码使用 `user_action_tokens` 保存一次性 token hash。token 的正确性已经由 `expires_at` 和 `consumed_at` 实时判断保证，但历史过期或已消费 token 如果长期保留，会增加数据量并影响排查效率。

## What Changes

- 增加用户 action token 后台清理机制，每天执行一次。
- 清理范围限定为 30 天前已经不再需要的 token：
  - 已消费且 `consumed_at` 早于 30 天前的 token。
  - 已过期且 `expires_at` 早于 30 天前的 token。
- 保留 `expires_at` 和 `consumed_at` 作为业务正确性判断字段。
- 清理任务只做数据生命周期管理，不参与 token 是否有效的判断。
- 增加清理任务的单元测试和 E2E/运维验证说明。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `backend-api-design`: 增加用户 action token 清理行为边界，明确清理不改变邀请和忘记密码 API 的实时校验逻辑。
- `backend-database-design`: 增加 `user_action_tokens` 历史数据保留和删除规则。
- `api-e2e-test-suite`: 增加 action token 清理任务的覆盖要求。

## Impact

- 后端应用增加定时任务配置和清理服务。
- 数据库 schema 不需要新增字段；复用 `expires_at`、`consumed_at` 和已有索引。
- 单元测试需要覆盖正常清理、未到保留期不清理、未过期未消费不清理等场景。
- E2E 或运维验证需要确认清理任务不会影响未过期、未消费 token。
