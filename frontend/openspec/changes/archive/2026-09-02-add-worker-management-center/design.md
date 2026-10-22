## Context

后端已提供 `GET /api/admin/workers`、`GET /api/admin/workers/{workerInstanceId}` 和 `PUT /api/admin/workers/{workerInstanceId}/concurrency`。列表响应不包含全局聚合统计或最大并发上限，因此前端不得推导全局 Worker 数量，也不在表单中伪造固定最大值。

## Goals / Non-Goals

**Goals:**

- 让超级管理员查看 Worker 状态、负载和运行任务。
- 允许设置单实例期望并发，并准确表达暂停和动态生效语义。
- 复用管理中心现有 BaseTable、BaseDrawer 和 BaseModal。

**Non-Goals:**

- 不负责创建、删除或伸缩 Worker 实例。
- 不修改 Worker 配置、RabbitMQ prefetch 或运行中任务取消逻辑。
- 不新增自动轮询。

## Decisions

### Worker 管理使用独立页面

Worker 属于平台任务执行基础设施，与模型 Profile 的兼容性和绑定不同，因此使用 `/admin/workers` 独立标签页，不放入模型配置页面。

### 列表与详情保持后端事实语义

列表直接展示 `status`、`concurrencyLimit`、`activeConcurrency`、`activeTaskCount` 和 `lastHeartbeatAt`。详情请求仅在 Drawer 打开时触发，关闭后不继续请求；列表和详情均由用户通过刷新按钮主动更新。

### 并发设置不伪造最大值

表单仅校验非负整数。超过部署端 `maxConcurrencyLimit` 时展示后端错误，不硬编码一个可能与部署配置不一致的前端上限。提交 `0` 时明确提示“暂停接收新任务”，且不得暗示会终止运行中任务。

## Risks / Trade-offs

- Worker 心跳状态可能在页面停留期间变化。通过显式刷新入口保持用户控制，后续若后端提供事件推送可再扩展。
- 降低并发不会立即降低已运行任务数量。界面分别展示期望并发、实际并发和运行任务数，避免混淆。
