# project-overview-current-context Specification

## Purpose

定义 frontend 读取、展示和刷新项目当前源码、当前运行环境、活动任务及 SSE baseline 的唯一数据边界，避免使用额外列表或局部缓存推算同一当前事实。

## Requirements

### Requirement: frontend 必须从项目 overview 读取当前上下文

项目详情页 SHALL 使用 `GET /api/projects/{projectId}/overview` 返回的 `project`、`currentContext.activeSourceRevision`、`currentContext.runtimeEnvironments`、`workflow`、`recentTasks` 和 `latestTaskEventId`，不得为同一当前事实维护第二套读取链路。

#### Scenario: 读取完整当前上下文

- **WHEN** 项目已有 active 源码并已配置 x86 源环境与 RISC-V 目标环境
- **THEN** 页面 SHALL 从同一个 overview 响应展示项目、当前源码和两个当前环境
- **AND** frontend SHALL NOT 额外请求 GET `/api/projects/{projectId}/runtime-environments`
- **AND** frontend SHALL NOT 使用源码 List 第一条推断当前源码

#### Scenario: 当前上下文不完整

- **WHEN** `activeSourceRevision` 为空或 `runtimeEnvironments` 缺少 source/target 环境
- **THEN** 页面 SHALL 在对应固定位置展示待配置状态
- **AND** 页面 SHALL NOT 将合法的空值解释为接口失败

#### Scenario: 读取资源历史

- **WHEN** 页面需要展示环境资源集合
- **THEN** frontend MAY 使用对应分页 List
- **AND** 历史 List SHALL NOT 反向决定 overview 中的当前源码或当前环境

### Requirement: 项目顶部必须展示三段连续上下文

项目详情页 SHALL 将首屏摘要组织为项目上下文、当前迁移上下文和执行上下文三张等高卡片，不展示 frontend 静态推算的当前阶段或下一步。

#### Scenario: 展示迁移上下文

- **WHEN** overview 加载成功
- **THEN** 项目上下文 SHALL 展示项目名称和架构方向
- **AND** 当前迁移上下文 SHALL 展示当前源码以及当前环境配置
- **AND** x86 源环境和 RISC-V 目标环境 SHALL 分两行展示
- **AND** 三张卡片标题 SHALL 保持同一水平基线

#### Scenario: 展示执行上下文

- **WHEN** overview 存在待执行、排队中或执行中的任务
- **THEN** 执行上下文 SHALL 在主行展示任务名称、状态和可用进度
- **AND** 过程消息 SHALL 独占次行

### Requirement: 当前运行环境必须保持 overview 读、PATCH 写

frontend SHALL 从 overview 读取当前运行环境，并继续通过 PATCH `/api/projects/{projectId}/runtime-environments` 修改当前 source/target 环境。

#### Scenario: 保存当前运行环境

- **WHEN** 用户设置当前 source 或 target 环境
- **THEN** frontend MAY 将 PATCH 响应合并进 overview 缓存提供即时反馈
- **AND** `project.context.changed` SHALL 负责当前上下文和下游领域事实的权威校准
- **AND** mutation 成功回调 SHALL NOT 重复请求下游 readiness、latest 或 List

#### Scenario: 读取环境资源

- **WHEN** 用户打开环境管理
- **THEN** frontend SHALL 使用 GET `/api/projects/{projectId}/environments` 读取环境资源列表
- **AND** overview 中的当前双环境摘要 SHALL NOT 替代资源列表

### Requirement: overview 必须提供项目 SSE baseline

frontend SHALL 使用 overview 的 `latestTaskEventId` 建立项目级事件流，并将 overview 保持为服务端事实快照而不是事件 payload 的派生缓存。

#### Scenario: 首次建立事件连接

- **WHEN** overview 首次加载成功
- **THEN** frontend SHALL 以 `latestTaskEventId` 作为 SSE baseline
- **AND** frontend SHALL 按递增事件 ID 忽略重复或已处理事件
- **AND** 重连 SHALL 使用最后处理的事件 ID 续传

#### Scenario: 页面恢复可见

- **WHEN** 项目页从后台恢复可见
- **THEN** frontend SHALL 主动刷新一次 overview
- **AND** SSE 断连期间 SHALL NOT 使用固定 overview 轮询掩盖连接问题

### Requirement: 项目 SSE 必须按节点元数据刷新事实

frontend SHALL 将项目 SSE 作为变化通知，并按 `stageId` 与 `resource.type/mode/environmentRole` 失效对应 overview、readiness、latest 和 List。

#### Scenario: 接收任务生命周期事件

- **WHEN** frontend 收到带节点和资源元数据的任务事件
- **THEN** frontend SHALL 按节点和资源路由领域 Query Key
- **AND** frontend SHALL NOT 仅依赖 `taskType` 猜测节点
- **AND** terminal 事件 SHALL 展示一次全局通知
- **AND** `task.log` SHALL 只推进游标，不刷新业务查询

#### Scenario: 接收 Context 变化

- **WHEN** frontend 收到 `project.context.changed`
- **THEN** frontend SHALL 使用 `changedFields` 和 `resource.type` 区分源码与运行环境变化
- **AND** frontend SHALL 刷新 overview 及受影响的下游 readiness、latest 和 List
- **AND** 未识别字段 SHALL 使用保守的完整 Context 刷新

#### Scenario: 合并 overview 刷新

- **WHEN** 同一项目连续收到事件
- **THEN** `project.context.changed` SHALL 在 250ms 固定窗口合并
- **AND** `task.created/queued/started` SHALL 在 5 秒固定窗口合并
- **AND** `task.progress` SHALL 最多每 10 秒刷新一次
- **AND** `task.succeeded/failed/cancelled/timeout` SHALL 取消被覆盖的延迟刷新并立即读取

#### Scenario: 刷新领域查询

- **WHEN** 同一领域连续收到非终态事件
- **THEN** 对应 Query Key SHALL 在 250ms 短窗口内只失效一次
- **AND** terminal SHALL 取消待执行刷新并立即读取最终事实
- **AND** SSE 正常期间 SHALL NOT 为同一 latest 配置固定轮询

### Requirement: 项目执行上下文展示最近任务

项目流水线工作台 SHALL 使用 Overview V2 的 `recentTasks` 展示当前或最近任务，而不是重复展示 Workflow 推荐阶段。

#### Scenario: 存在活动任务

- **WHEN** `recentTasks` 包含 `RUNNING`、`QUEUED` 或 `PENDING` 任务
- **THEN** 执行上下文 SHALL 优先展示活动任务的类型、状态、进度和消息

#### Scenario: 仅存在终态任务

- **WHEN** `recentTasks` 不包含活动任务但至少包含一条终态任务
- **THEN** 执行上下文 SHALL 展示列表中的第一条最近任务及其终态和消息

#### Scenario: 不存在任务

- **WHEN** `recentTasks` 为空
- **THEN** 执行上下文 SHALL 显示尚无任务记录的空状态

#### Scenario: 查看最近任务列表

- **WHEN** 用户点击执行上下文中的“最近任务 N”入口
- **THEN** 系统 SHALL 按后端返回顺序展示最多五条任务的类型、状态、时间和消息
- **AND** 活动任务 SHALL 额外展示当前标记和执行进度

### Requirement: overview 查询订阅所有权统一

同一项目视图树 SHALL 在项目公共边界建立一个 overview 查询订阅，页面与阶段 SHALL 消费该边界提供的类型化数据、查询状态及刷新能力，不复制当前事实或建立兜底重复订阅。当前上下文与 SSE 刷新规则遵循本能力既有要求。

#### Scenario: 页面与多个阶段读取当前上下文

- **WHEN** 项目页、源码、环境及构建上下文需要同一 overview
- **THEN** 它们 SHALL 读取公共查询结果，当前事实更新 SHALL 同步到全部消费方
- **AND** 阶段 SHALL 不各自注册 overview 查询或保存第二套当前事实

#### Scenario: 加载、恢复及阶段关闭

- **WHEN** overview 加载失败、用户重试、mutation 合并缓存或 SSE 使缓存失效
- **THEN** 消费方 SHALL 保留既有加载、错误、恢复与当前事实反馈，刷新所有权 SHALL 明确
- **AND** 关闭或切换阶段 SHALL 不重建项目 SSE 或停止项目级 overview 更新，不增加固定轮询
