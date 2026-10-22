## Context

当前 Worker 每 10 秒向 `worker_instances` upsert 一次心跳，管理 API 使用 `last_heartbeat_at` 与 60 秒离线阈值动态计算 `ONLINE/OFFLINE`。未配置 `RVPORT_WORKER_INSTANCE_ID` 时，实例标识包含容器 hostname、JVM 标识和随机 UUID，因此容器重建会产生新记录，旧记录不会再次更新，也没有清理入口。

`task_runtime_handles.worker_instance_id` 以文本保存 Worker 标识且没有指向 `worker_instances` 的外键，这允许删除操作型 Worker 注册记录并继续保留任务审计信息。但失联 Worker 可能仍持有非终态 runtime handle，对应任务也可能停留在 `RUNNING`；若直接删除 Worker，会隐藏异常归属而不修复任务状态。

## Goals / Non-Goals

**Goals:**

- 自动标记离线 Worker，并在更长的失联确认时间后收敛其遗留任务和 runtime handle。
- 按保留期自动删除不再承载非终态句柄的失效 Worker 注册记录。
- 在多个后端或 Worker 实例同时执行调度时保持幂等，不重复生成失败事件。
- 保留任务、任务事件、日志和 runtime handle 中的历史 Worker 标识。
- 让清理周期、失联确认时间、保留时间和批量大小可以通过配置调整。

**Non-Goals:**

- 不自动重试或重新认领失联 Worker 的任务；远程或本地命令可能仍在执行，自动重试可能产生重复副作用。
- 不保证终止失联 JVM 中的线程或本地进程，也不在本变更中实现通用远程残留进程回收。
- 不提供管理员手工删除 Worker 的新 API。
- 不删除历史任务、事件、日志、runtime handle 或归档制品。

## Decisions

### 1. 使用离线、确认失联和可删除三段生命周期

单次心跳超时只表示 Worker 暂时不可达，不足以立即判定其任务失败。生命周期采用三个时间边界：

1. `offline-timeout-seconds`：沿用现有默认值 60 秒，管理 API 显示 `OFFLINE`，调度器可将持久化状态同步为 `OFFLINE`。
2. `lost-timeout-seconds`：默认 300 秒。心跳持续缺失后才将其非终态 runtime handle 和 `RUNNING` 任务收敛。
3. `retention-hours`：默认 24 小时。超过保留期且不存在非终态 runtime handle 时，才删除 `worker_instances` 记录。

相比心跳一超时就删除，该方案保留了短时网络抖动和容器重启的观察窗口；相比永久保留，则限制了注册表增长。

### 2. 失联任务终止为 FAILED，不自动重新排队

Worker 消失时，RabbitMQ 可能重新投递未确认消息，但数据库任务已经是 `RUNNING`，而且原本启动的远程命令是否仍执行无法可靠判断。调度器将满足条件的 runtime handle 原子更新为 `WORKER_LOST`，并仅将仍为 `RUNNING` 的对应任务更新为 `FAILED`，错误码使用 `WORKER_LOST`。

该路径必须复用或抽取统一的任务终态副作用，包括 `task.failed` 持久化事件、项目级 SSE 广播、任务级终态通知和临时 secret payload 清理。已经进入其他终态的任务保持不变。

### 3. 以数据库条件更新保证多实例幂等

清理调度器可以存在于多个应用实例中，不依赖单节点内存锁。每个候选 Worker 在短事务内加行锁或使用等价条件更新，并在更新前重新检查 `last_heartbeat_at`。runtime handle 只允许从 `ACTIVE`、`CANCEL_REQUESTED`、`CANCELLING` 转为 `WORKER_LOST`；任务只允许从 `RUNNING` 转为 `FAILED`。

只有实际完成状态迁移的任务才发布失败事件。删除 Worker 时再次携带心跳截止条件，并使用 `NOT EXISTS` 确认没有非终态 runtime handle，避免与恢复心跳或并发调度竞态。

### 4. 清理使用独立配置和有界批处理

新增独立的 `rvport.worker.cleanup` 配置组，避免继续扩张心跳与并发控制使用的 `WorkerProperties`：

- `enabled=true`
- `interval-ms=300000`
- `lost-timeout-seconds=300`
- `retention-hours=24`
- `batch-size=100`

配置加载时要求失联确认时间大于离线阈值、保留时间大于失联确认时间，数值非法时应用启动失败并给出明确配置错误。每次调度按批次处理，单个 Worker 收敛失败时记录脱敏日志并继续后续候选，下一轮可幂等重试。

### 5. Worker 注册表是运行状态，不是历史审计表

`worker_instances` 只保存当前和近期 Worker 的管理状态。任务与 runtime handle 继续保存 `worker_instance_id` 文本作为历史证据，因此删除注册记录不级联清理任何业务数据。配置固定实例 ID 的 Worker 在记录被删除后重新出现时，会以部署配置中的默认并发值重新注册。

### 6. 使用仅测试构建可用的触发接口验证调度逻辑

现有 Worker E2E 通过数据库 fixture 构造不同心跳时间的实例。为避免等待真实调度周期，`src/test-support` 增加手工触发一次 Worker 清理的接口，并返回本轮标记离线、收敛句柄、终止任务和删除实例的数量。该接口复用生产清理服务，不复制清理规则；test-support 源集继续由专用构建开关控制，生产 JAR 不包含相关 Controller 和 Service。

## Risks / Trade-offs

- [数据库暂时不可用导致正常 Worker 超过失联阈值] → 使用独立且更长的失联确认时间；事务提交前重新检查心跳，避免旧候选快照直接生效。
- [失联 Worker 实际仍在执行远程命令] → 不自动重试任务；以 `WORKER_LOST` 明确表示执行结果未知，后续可由专门的资源回收能力处理。
- [多个调度器重复处理同一 Worker] → 使用行锁、条件状态更新和仅对成功迁移记录发布事件，保证至少一次调度下的业务幂等。
- [清理任务量过大影响数据库] → 使用可配置批量大小和索引化的 `last_heartbeat_at` 查询，每轮处理数量有界。
- [删除后丢失管理员设置的并发值] → 保留期内维持原设置；超过保留期的实例视为已经退役，重新注册时使用部署默认值。

## Migration Plan

1. 通过 Liquibase 增加清理查询需要的组合/条件索引（仅在现有索引不足时），不得手工修改数据库 schema。
2. 发布包含清理配置、仓储条件更新和调度服务的新后端镜像。
3. 首次运行先按批次收敛现存失联任务，再删除超过保留期且已无非终态句柄的 Worker。
4. 通过 Worker 管理 API、任务详情、任务事件和 SSE 验证状态收敛。
5. 回滚时禁用 `rvport.worker.cleanup.enabled`；已经删除的 Worker 注册记录不会恢复，但保留的任务和 runtime handle 审计数据不受影响。

## Open Questions

无。
