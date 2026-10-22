## Why

当前后端 worker 默认只有单消费者执行能力，长任务会串行阻塞队列，管理员也无法看到有哪些 worker 在线、每个 worker 正在执行哪些任务，以及单个 worker 当前允许的最大并发。

项目部署会由 Docker Swarm 或未来 Kubernetes 负责实例数量伸缩，RvPort 后端只需要让自动接入的 worker 可观测，并允许管理员控制单个 worker 的任务消费并发。

## What Changes

- 增加 worker 实例注册与心跳能力，worker 启动后自动登记自身实例信息并周期性上报在线状态。
- 增加管理员 worker 观测 API，支持查看 worker 列表、单个 worker 详情、当前运行任务和并发状态。
- 增加管理员控制单 worker 最大并发能力，调整后由对应 worker 周期性拉取并动态应用。
- 修改 RabbitMQ listener 配置，支持按 worker 并发限制启动多个消费者；`prefetch` 固定为 `1`，不展示、不落库、不开放编辑。
- 支持 `concurrencyLimit=0` 表示暂停该 worker 接收新任务，已有运行任务继续执行。
- 增加 API/worker 运行模式拆分，API 节点禁用 worker 消费，worker 节点禁用 HTTP 服务。
- 更新 Compose/部署配置，明确 API 与 worker 使用同一后端镜像，并共享 runtime volume。
- 不实现 Docker Swarm 或 Kubernetes scale 控制；实例数量由部署平台自行管理。

## Capabilities

### New Capabilities
- `worker-observability`: 定义 worker 实例自动注册、心跳、在线状态、运行任务可观测和并发控制能力。

### Modified Capabilities
- `backend-api-design`: 增加管理员 worker 管理 API 的行为约束。
- `task-runtime`: 修改 worker 消费模型，支持单实例可配置并发并保持任务认领、取消和 ack 语义。
- `backend-infrastructure`: 明确 API/worker 运行模式拆分、共享 runtime volume 和固定 `prefetch=1` 的部署约束。
- `api-e2e-test-suite`: 增加 worker 可观测与并发控制的 E2E 覆盖要求。

## Impact

- 后端配置：新增 worker 运行模式、默认并发限制、最大并发上限、心跳间隔和离线判定阈值。
- 数据库：新增 worker 实例状态表，记录实例标识、主机信息、并发限制、实际并发、运行任务数和心跳时间。
- RabbitMQ：任务队列 listener 支持动态并发，手动 ack/nack、quorum queue、DLQ 和取消队列语义保持不变。
- API：新增超级管理员 worker 管理接口。
- 部署：同一后端镜像支持 API 节点和 worker 节点；多节点部署要求 API 与 worker 共享 runtime volume。
- 测试：补充正常流程、异常流程和 edge case 单元测试与 E2E 测试。
