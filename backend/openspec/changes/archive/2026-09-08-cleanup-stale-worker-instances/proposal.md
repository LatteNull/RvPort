## Why

Worker 容器重建时会生成新的实例标识，而旧实例目前只会按心跳时间动态显示为离线，不会被收敛或删除，导致管理列表持续累积失效记录。数据库中还可能残留由失联 Worker 持有的活动运行句柄和永久处于 `RUNNING` 的任务，因此不能只删除 Worker 记录，必须先完成任务状态和运行句柄的安全收敛。

## What Changes

- 增加失效 Worker 周期性检查，区分短时离线、确认失联和超过保留期三个阶段。
- 对确认失联 Worker 持有的 `ACTIVE`、`CANCEL_REQUESTED`、`CANCELLING` 运行句柄执行幂等收敛，标记为 `WORKER_LOST`。
- 将仍由失联 Worker 持有且处于 `RUNNING` 的任务收敛为 `FAILED`，记录统一错误码并发布任务失败及项目级 SSE 状态事件。
- 仅在 Worker 超过保留期且不再持有非终态运行句柄后，删除 `worker_instances` 注册记录；保留任务、事件和运行句柄中的历史 Worker 标识。
- 增加失联确认时间、记录保留时间和清理调度周期配置，并为默认值和非法配置提供明确约束。
- 补充正常流程、异常流程和边界场景测试，覆盖瞬时心跳中断、并发清理、任务已终态以及遗留运行句柄等情况。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `worker-observability`: 增加失效 Worker 判定、遗留任务与运行句柄收敛、保留期及自动删除要求。
- `test-support-api`: 增加仅测试构建可用的 Worker 清理触发能力，用于确定性验证定时清理行为。
- `api-e2e-test-suite`: 扩展 Worker E2E 模块，覆盖失联收敛、保留期删除和安全边界。

## Impact

- 影响 Worker 心跳与管理模块、任务状态和 runtime handle 持久化、任务事件及跨进程 SSE 广播。
- 增加 Worker 清理调度服务、仓储查询与批量更新能力，以及对应配置项。
- Worker 管理列表将不再永久展示超过保留期的失效实例；任务和运行句柄历史记录继续保留。
- 不新增前端业务 API，不删除任务、任务事件、日志或运行句柄历史数据。
