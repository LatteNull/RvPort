## Context

当前任务日志同时存在两套存储：`task_logs` 指向按任务和日志类型保存的完整日志文件，`task_log_events` 以最大 4000 字符的 stdout/stderr 切片保存可恢复的实时日志事件。`GET /api/tasks/{taskId}/log-content` 面向完成态日志查看，使用“从最新展示页向更旧内容翻页”的 offset；`GET /api/tasks/{taskId}/log-events` 则直接通过 SSE 补发并实时传输日志正文。

API 与 Worker 以独立进程运行。日志事件写入发生在 Worker，日志页面 SSE 连接保存在 API 进程。现有实现借助 Redis 将日志事件引用广播到 API，但终态通知仍存在依赖 Worker 本地 emitter 的路径。新的交互只需要 SSE 告知前端“日志发生变化”，正文应通过普通 HTTP 增量读取，并以数据库为恢复依据。

## Goals / Non-Goals

**Goals:**

- 为任意任务提供统一、按任务隔离且受项目权限保护的日志变化通知 SSE。
- 每 5 秒检查订阅任务的日志变化和终态，并在同一任务存在多个浏览器连接时复用查询结果。
- 使用稳定的任务日志事件游标增量读取正文，避免运行中日志增长造成 offset 漂移。
- 确保终态前最后一批日志可读取，并让已终态任务连接后立即结束。
- 保持现有完成态 `log-content` 接口和项目级 SSE 的行为不变。

**Non-Goals:**

- 不通过新 SSE 传输日志正文或补发历史日志。
- 不修改完整日志文件的存储格式、归档方式或下载接口。
- 不在本 change 删除旧 `/log-events` 接口或 `task_log_events` 数据。
- 不让前端通过 SSE 通知本身确认日志正文已经消费。

## Decisions

### 1. 新建通知 SSE，不改变旧日志 SSE 的语义

新增：

```http
GET /api/tasks/{taskId}/log-notifications?afterEventId={lastConsumedEventId}
```

旧 `/log-events` 标记为废弃但继续工作，避免现有调用方在前端切换期间被破坏。新 SSE 只发送：

- `task.log.updated`：数据库中出现比连接已知游标更大的日志事件。
- `task.log.completed`：任务进入 `SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`。
- `heartbeat`：保持代理和浏览器连接。

通知不携带日志正文、服务器路径或任务输入。`task.log.updated` 包含 `taskId`、`latestEventId` 和当前任务状态；终态事件额外包含安全的任务消息。

备选方案是直接修改 `/log-events`。该方式会让同一路由从“正文事件流”突然变成“变化通知流”，属于高风险破坏性修改，因此不采用。

### 2. SSE 通知不作为消费确认

SSE 事件不设置可被误解为已消费游标的 `id`，`afterEventId` 只表示前端已经通过增量 API 成功取得的最后日志事件。前端必须：

1. 打开或重建日志页面连接后立即调用一次增量 API。
2. 收到 `task.log.updated` 后继续调用增量 API，直至 `hasMore=false`。
3. 只在增量响应成功后更新本地游标。
4. 收到 `task.log.completed` 后使用其中的 `latestEventId` 判断是否还需执行最后一次增量读取。

这样即使 SSE 通知丢失或连接中断，重新建立连接时也能按最后成功消费的游标恢复。SSE 是唤醒信号，数据库日志事件才是事实来源。

### 3. 用 task_log_events.id 作为唯一前向游标

新增：

```http
GET /api/tasks/{taskId}/log-increments?afterEventId={lastConsumedEventId}&limit=500
```

查询固定为当前 `taskId` 且 `id > afterEventId`，按 `id ASC` 返回。响应将本批事件聚合为三个内容块：

```json
{
  "taskId": "...",
  "fromEventId": 124,
  "latestEventId": 168,
  "hasMore": false,
  "logs": {
    "merged": { "content": "...", "returnedEvents": 20 },
    "stdout": { "content": "...", "returnedEvents": 18 },
    "stderr": { "content": "...", "returnedEvents": 2 }
  }
}
```

`merged` 按事件 ID 顺序组合 stdout/stderr，并保留日志类型标记；另外两类只组合对应类型。单次读取同时受事件条数和聚合内容字节数上限保护。若仍有后续事件，返回 `hasMore=true`；`latestEventId` 表示本次实际返回并成功聚合的最后事件，而不是查询时任务的全局最大值。

使用全局自增 ID 不会混入其他任务，因为所有读取都必须同时限制 `task_id`。相比行 offset，事件 ID 在文件追加、部分行和多字节 UTF-8 内容下都保持稳定。

### 4. 每个 API 进程按本地订阅任务聚合轮询

通知 broker 维护：

```text
taskId
  ├── emitters[]
  ├── lastObservedEventId
  └── lastObservedStatus
```

固定 5 秒调度只处理至少有一个本地 emitter 的 taskId。一次调度批量查询这些任务的状态和日志最大事件 ID，再向同一 taskId 下的全部 emitter 广播，避免连接数直接放大数据库查询数。多个 API 副本分别扫描各自持有连接的任务，这是可接受的水平扩展行为。

连接建立顺序为：权限校验、注册 emitter、读取当前快照、按快照立即决定是否发送 updated/terminal。注册在快照读取之前，后续轮询会再次比较最新状态，避免连接建立窗口遗漏变化。

轮询只查询 `tasks` 和 `task_log_events` 元数据，不扫描共享日志文件。现有 `(task_id, id)` 索引支持游标读取和最大 ID 查询；实现阶段应检查执行计划，只有确认需要时才增加索引。

### 5. 终态以 API 进程查询结果为准

若本轮同时发现新增日志和终态，发送顺序固定为：

```text
task.log.updated -> task.log.completed -> emitter.complete()
```

连接已经终态的任务时直接发送 `task.log.completed` 并关闭；终态 payload 必须包含当时最新的日志事件 ID，使前端可以补拉最终内容。终态判断统一使用 `SUCCEEDED`、`FAILED`、`CANCELLED`、`TIMEOUT`。

这条路径不依赖 Worker 直接访问 API 进程内的 emitter，也不依赖 Redis 日志广播是否成功。现有 Redis 项目事件广播继续保留。

### 6. 权限和错误契约沿用任务 API

两个新接口都先通过 `ProjectAccessService.requireTaskAccess` 校验任务所属项目权限。无权限与不存在继续返回统一的不可枚举响应，校验失败前不得创建 emitter、查询日志正文或泄露最新事件 ID。

非法负数游标、超限 limit 和不支持的日志类型返回 400；超过当前最大事件 ID 的游标返回空增量并保留该游标语义，不回退补发历史内容。

## Risks / Trade-offs

- [风险] 5 秒轮询使日志提示最多延迟约 5 秒。 -> 这是产品明确接受的节流策略；连接建立时立即检查，终态也最多延迟同一周期。
- [风险] 大量不同任务同时打开日志页会增加数据库轮询。 -> 按 taskId 去重、批量查询并只扫描存在 emitter 的任务，限制单实例最大订阅量并记录调度耗时指标。
- [风险] 通知发送后前端尚未拉取便断线。 -> SSE 不表示消费成功；前端以增量 API 成功响应游标恢复，并在每次连接后主动拉取。
- [风险] 单批事件聚合后响应过大。 -> 同时限制事件数量和 UTF-8 内容字节数，通过 `hasMore` 分批续读。
- [风险] 旧日志 SSE 与新通知 SSE 并存造成误用。 -> 使用不同路由和清晰事件名，在 API 文档中标记旧路由废弃并提供迁移说明。
- [风险] `task_log_events` 只保存 stdout/stderr，而完整日志还可能存在其他类型。 -> 新增量接口的契约明确覆盖 merged/stdout/stderr；merged 由两类实时事件合成，TOOL 等非实时日志继续通过现有接口读取。

## Migration Plan

1. 增加增量查询仓储和服务，验证索引与响应上限。
2. 增加通知 broker、5 秒聚合轮询和新 SSE controller。
3. 补齐终态、断线恢复、权限和多连接测试。
4. 发布新 API 文档，前端切换到通知 SSE + 增量 API。
5. 观察旧 `/log-events` 使用情况，后续单独 change 删除旧正文 SSE 及不再需要的 Redis 日志广播路径。

回滚时可停用新路由和轮询组件，旧 `/log-events` 与 `/log-content` 均保持可用，数据模型无需回滚。

## Open Questions

无。接口命名、5 秒轮询周期、终态集合及旧接口保留策略均在本 change 中确定。
