## Context

`user_action_tokens` 已用于用户邀请和忘记密码流程，表中保存 token hash、`expires_at` 和 `consumed_at`。接口实时通过 token 类型、hash、过期时间、消费状态和用户状态判断 token 是否有效。

当前缺口是历史 token 生命周期管理：已过期很久或已消费很久的记录继续保留，会增加表数据量，也会让排查时混入大量无效历史记录。

## Goals / Non-Goals

**Goals:**

- 每天自动清理 30 天前已经不再需要的 `user_action_tokens` 记录。
- 保留 `expires_at` 和 `consumed_at` 作为 token 正确性判断依据。
- 清理任务失败时记录日志，但不影响登录、邀请、忘记密码等主链路。
- 为清理服务补充正常流程、异常流程和 edge case 单元测试。

**Non-Goals:**

- 不改变 token 生成、hash、消费、防重放和过期校验逻辑。
- 不删除 30 天内的已消费 token 或已过期 token。
- 不增加新的数据库字段或表。
- 不把定时清理作为 token 有效性判断的一部分。

## Decisions

### Decision 1: 清理任务只做 GC，不参与 token 正确性

接口仍然实时判断：

```text
token_hash 匹配
token_type 匹配
consumed_at is null
expires_at > now()
user 状态可用
```

清理任务只删除历史数据。这样即使调度器未运行、运行延迟或失败，也不会导致过期 token 重新有效。

### Decision 2: 每天执行一次，保留 30 天

采用每日调度，默认清理：

- `consumed_at < now() - 30 days`
- `expires_at < now() - 30 days`

不采用每分钟清理。原因是 token 过期判断已经由业务查询保证，分钟级物理删除没有业务必要，反而会增加固定数据库负载。

### Decision 3: 使用 Spring Scheduler

项目入口已经启用 `@EnableScheduling`，已有 `@Scheduled` 使用模式。因此新增一个 action token cleanup scheduler 即可，避免引入额外调度依赖。

建议配置：

```properties
rvport.user-action-token.cleanup.enabled=true
rvport.user-action-token.cleanup-cron=0 0 3 * * *
rvport.user-action-token.retention-days=30
```

默认每天凌晨 3 点执行。`retention-days` 保持可配置，但默认值固定为 30。

### Decision 4: 删除条件必须一次性表达清楚

删除条件应只命中已经不再需要的 token：

```sql
delete from user_action_tokens
 where consumed_at < :cutoff
    or expires_at < :cutoff
```

其中 `cutoff = now - retentionDays`。

这个条件会保留：

- 未消费且未过期 token。
- 已消费但未超过保留期 token。
- 已过期但未超过保留期 token。

## Risks / Trade-offs

- [Risk] 系统时间错误可能影响清理边界。  
  Mitigation: 清理只删除 30 天前数据，保留窗口较长；接口实时校验仍以数据库时间/应用时间一致性为基础。

- [Risk] 清理任务 SQL 写错可能误删仍需审计的数据。  
  Mitigation: 单元测试覆盖已消费、已过期、未过保留期、未消费未过期等边界；实现时使用集中服务方法，避免散落 SQL。

- [Risk] 清理任务失败导致历史 token 堆积。  
  Mitigation: 记录失败日志，下一次调度继续执行；失败不影响主链路。

## Migration Plan

- 不需要数据库结构迁移。
- 发布后调度任务按默认配置自动运行。
- 如出现异常，可通过配置关闭清理任务，保留 token 实时校验逻辑不受影响。

## Open Questions

- 暂无。默认策略为每天清理一次，保留 30 天。
