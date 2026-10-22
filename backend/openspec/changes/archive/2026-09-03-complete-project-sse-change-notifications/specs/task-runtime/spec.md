## ADDED Requirements

### Requirement: 项目级 SSE 事件必须携带节点和资源元数据
任务运行时 SHALL 在项目级 SSE 事件响应中提供节点和资源元数据，使前端能够判断需要刷新哪个节点、哪类资源或哪条记录。

#### Scenario: 任务事件包含节点元数据
- **WHEN** 后端通过项目级 SSE 推送任务生命周期事件
- **THEN** SSE `data` SHALL 包含 `stageId`
- **AND** `stageId` SHALL 能标识前端工作流节点或等效后端阶段
- **AND** `stageId` MUST NOT 仅依赖前端从展示文本中推断

#### Scenario: 任务事件包含资源元数据
- **WHEN** 任务事件关联某个业务运行记录、报告、扫描、构建、测试或环境
- **THEN** SSE `data` SHALL 包含 `resource`
- **AND** `resource` SHALL 至少包含 `type` 和 `id`
- **AND** `resource` MAY 包含 `mode`、`environmentRole` 或其他用于前端局部刷新的非敏感摘要字段
- **AND** `resource` MUST NOT 包含完整业务结果、完整日志、服务器真实路径、明文凭据、token 或私钥

#### Scenario: 同一任务类型区分不同节点语义
- **WHEN** 同一任务类型可能服务多个节点或运行模式
- **THEN** 后端 SHALL 通过 `stageId`、`resource.mode` 或 `resource.environmentRole` 区分具体语义
- **AND** 前端 MUST NOT 只能依赖 `taskType` 判断刷新范围

### Requirement: 项目级 SSE 必须通知项目上下文变更
任务运行时 SHALL 通过项目级 SSE 通道发布项目上下文变更事件，用于通知源码版本、运行环境选择和环境配置版本等影响后续节点事实来源的变化。

#### Scenario: 源码版本激活后发布上下文事件
- **WHEN** 项目 active source revision 被上传激活、手动激活或 Git 同步任务激活
- **THEN** 后端 SHALL 持久化 `project.context.changed` 事件
- **AND** 事件 SHALL 关联当前 `projectId`
- **AND** 事件 SHALL 标识变化字段包含 active source revision
- **AND** 事件 SHALL 在事务提交后通过项目级 SSE 发布

#### Scenario: 运行环境选择更新后发布上下文事件
- **WHEN** 项目的 source x86 或 target riscv 运行环境选择被更新
- **THEN** 后端 SHALL 持久化 `project.context.changed` 事件
- **AND** 事件 SHALL 标识变化字段包含 runtime environment selection 或 environment config version
- **AND** 事件 SHALL 在事务提交后通过项目级 SSE 发布

#### Scenario: 上下文事件可以没有任务 ID
- **WHEN** 项目上下文变化不是由某个具体任务生命周期直接表达
- **THEN** 后端 SHALL 允许事件不包含 `taskId`
- **AND** 事件响应中的 `taskType` MAY 为空
- **AND** 后端 MUST NOT 为上下文变化伪造业务任务

#### Scenario: 上下文事件触发前端重读事实接口
- **WHEN** 前端收到 `project.context.changed` 事件
- **THEN** 前端 SHALL 能根据事件元数据重读 overview、readiness、节点列表或节点详情
- **AND** 后端 MUST NOT 通过该 SSE 事件返回完整项目详情、完整源码记录、完整环境配置或完整报告

### Requirement: 项目级 SSE 事件必须保持项目隔离
项目级 SSE SHALL 只向有权限访问该项目的连接推送该项目事件，包括任务生命周期事件和项目上下文变更事件。

#### Scenario: 不推送其他项目的上下文事件
- **WHEN** 项目 A 和项目 B 同时存在 SSE 连接
- **AND** 项目 B 的源码版本或运行环境选择发生变化
- **THEN** 项目 A 的 SSE 连接 MUST NOT 收到项目 B 的 `project.context.changed` 事件

#### Scenario: 不补发其他项目的游标后事件
- **WHEN** 前端使用 `afterEventId` 或 `Last-Event-ID` 连接项目 SSE
- **THEN** 后端 SHALL 只按当前 `projectId` 查询游标之后的事件
- **AND** 后端 MUST NOT 因事件 ID 全局递增而返回其他项目事件

## MODIFIED Requirements

### Requirement: 项目级 SSE 必须使用项目事件 baseline
任务运行时 SHALL 提供项目级 SSE 通道，并 SHALL 使用当前项目最新事件 ID 支持首次订阅 baseline；SSE 是轻量变更通知通道，不承担完整历史状态恢复职责。

#### Scenario: 建立项目级 SSE
- **WHEN** 已登录用户请求 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 返回 `text/event-stream`
- **AND** SSE 通道 SHALL 只推送该项目的任务事件和项目上下文变更事件
- **AND** 后端 SHALL 周期性发送心跳以保持连接

#### Scenario: 使用 afterEventId 作为首次订阅 baseline
- **WHEN** 前端请求 `GET /api/projects/{projectId}/task-events?afterEventId={eventId}`
- **THEN** 后端 SHALL 将 `afterEventId` 解析为项目事件数字游标
- **AND** 后端 SHALL 只按当前 `project_id` 查询游标之后的事件
- **AND** 补发顺序 SHALL 按事件数字 ID 升序
- **AND** 后端 MAY 对单次补发数量设置受控上限

#### Scenario: 使用 Last-Event-ID 进行同一页面短线重连
- **WHEN** 前端未提交 `afterEventId` 且携带 `Last-Event-ID` 重新连接
- **THEN** 后端 SHALL 将该值解析为项目事件数字游标
- **AND** 后端 SHALL 只按当前 `project_id` 查询游标之后的事件
- **AND** 后端 MAY 对单次补发数量设置受控上限
- **AND** 前端仍 SHALL 通过 overview、列表或详情接口恢复完整页面状态

#### Scenario: 无游标首次连接使用当前项目最新事件作为 baseline
- **WHEN** 前端请求项目级 SSE 且未提交 `afterEventId` 或 `Last-Event-ID`
- **THEN** 后端 SHALL 查询当前项目最新事件 ID 作为 baseline
- **AND** 后端 SHALL 只推送该 baseline 之后的新事件
- **AND** 后端 MUST NOT 默认补发该项目全部历史事件

#### Scenario: afterEventId 优先于 Last-Event-ID
- **WHEN** 前端同时提交 `afterEventId` 和 `Last-Event-ID`
- **THEN** 后端 SHALL 使用 `afterEventId` 作为游标
- **AND** 后端 SHALL 忽略本次请求中的 `Last-Event-ID`

#### Scenario: 拒绝非法 SSE 游标
- **WHEN** `afterEventId` 或被使用的 `Last-Event-ID` 不是非负数字
- **THEN** 后端 SHALL 返回 `SSE_LAST_EVENT_ID_INVALID` 或等效统一错误
- **AND** 后端 MUST NOT 创建 SSE emitter
- **AND** 后端 MUST NOT 补发历史事件

#### Scenario: 发送 SSE 事件
- **WHEN** 后端向 SSE 连接发送项目事件
- **THEN** SSE `id` SHALL 使用持久化事件数字 ID
- **AND** SSE `event` SHALL 使用持久化事件类型
- **AND** SSE `data` SHALL 包含轻量事件载荷
- **AND** SSE `data` MUST NOT 包含完整业务结果、完整日志、明文凭据、token、私钥或服务器真实路径

#### Scenario: 多项目 SSE 隔离
- **WHEN** 同一用户或不同用户同时打开多个项目的 SSE 连接
- **THEN** 每个 SSE 连接 SHALL 只收到对应 `projectId` 的项目事件
- **AND** 后端 MUST NOT 因全局递增事件 ID 将其他项目事件补发或推送到当前项目连接
