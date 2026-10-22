# Worker 失联与领域运行收尾

[English](worker-lost-domain-finalization.md) | 简体中文

## 适用范围与交付状态

本说明介绍 worker 丢失后的领域任务收敛行为。对已有部署升级时仍须遵循下文排空流程。

## 状态规则

- 失联清理将仍为 `RUNNING` 的 Task 置为 `FAILED`，错误码为 `WORKER_LOST`。
- 同一事务内，将此 Task 关联的领域运行及 `tool_runs` 的非终态记录结束，清理临时 secret，持久化任务事件和节点变化事件。提交后沿已有 Redis/SSE 通道通知客户端。
- 仅更新 `PENDING/QUEUED/RUNNING`。已有成功、部分成功、失败等终态，以及已有 findings、制品和摘要均保留。
- 历史对账将失败、取消、超时 Task 的非终态领域记录分别收敛至 `FAILED/CANCELLED/TIMEOUT`。自动修复 item 没有超时枚举，映射为 `FAILED`，父运行和 Task 仍保留 `TIMEOUT`。
- `SUCCEEDED` Task 关联非终态领域记录时只审计，不凭空产生成功结果。
- 使用真实 `task_id` 关联，不按项目最近一次运行更新。双环境任务和不同源码版本不会互相收尾。
- 没有独立领域运行的 `ENV_RUN_SCRIPT` 通过 Task 和 `tool_runs` 表达结果。没有原生结束时间列的领域记录仍可通过关联 Task 查询结束时间；其他记录写入原生列或摘要。

## 执行归属与事务

当前尝试使用 `task_runtime_handles.id` 标识。已有部分唯一索引保证同一 Task 最多一个活动句柄，不另建尝试表。

认领先锁 Worker，再原子更新 Task 并建立句柄。发布时锁 Task，要求 Task 为 `RUNNING` 且活动句柄 ID 完全匹配。清理按 Worker、Task、句柄顺序加锁，避免与发布形成相反锁序。

SSH、扫描进程、模型调用及对象存储上传不应放入持有 Task 锁的事务。制品上传后再校验并登记；失效尝试不得更新已有制品引用。新上传对象在明确回滚后清理，提交后才清理被替换对象；提交结果未知时保留对象供核对。

普通重试结束原句柄并将 Task 置为 `QUEUED`；下一次认领建立新句柄。抛出重投异常必须发生在事务提交后。旧句柄不能因为 Task 再次运行而恢复写权限。

## 调度与历史修复

沿用 `rvport.worker.cleanup` 配置：

- `enabled`：清理和历史对账的总开关。
- `interval-ms`：扫描周期。
- `lost-timeout-seconds`：失联判定阈值，必须大于普通离线阈值。
- `retention-hours`：Worker 记录保留期限。
- `batch-size`：每批处理上限。

历史对账仅在 API/combined 节点运行，不依赖 Worker 记录仍然存在。按 Task UUID 的稳定游标分批处理，每项独立事务；单项异常不阻塞后续项。扫描至末尾后重置游标，失败项在下一轮重试。

处理前先备份数据库并记录异常 Task ID。处理后检查 Task、领域状态、latest、overview 与 SSE。重复执行不应改写已有终态，也不应补发重复 `task.failed`。日志只输出标识、计数及异常类型，不记录凭据或完整业务载荷。

## 部署与回滚

1. 停止旧 Worker 接收新任务并排空正在执行的任务。禁止新旧 Worker 混跑，旧代码可能绕过执行归属保护。
2. 更新 API 与 Worker 镜像，先使用隔离 fixture 验证，再恢复消费。
3. 回滚前同样排空 Worker；必要时关闭 cleanup 调度。不得为了恢复运行将已结束 Task 批量改回 `RUNNING`，需要重跑时创建新任务。

数据库收尾只表示平台不再接受该执行尝试的结果，不保证远程进程已退出。失联期间已发生的远程安装、文件写入等副作用不能回滚，需要单独核查。已有历史记录无法通过状态推断缺失的 findings，不能自动补造。
