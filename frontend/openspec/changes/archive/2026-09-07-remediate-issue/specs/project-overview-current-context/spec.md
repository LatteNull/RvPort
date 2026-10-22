## ADDED Requirements

### Requirement: frontend 必须从项目 overview 读取当前上下文

项目详情页 SHALL 使用 `GET /api/projects/{projectId}/overview` 返回的顶层 `project`、`activeSourceRevision`、`runtimeEnvironments`、`recentTasks` 和 `latestTaskEventId`，不得为同一当前事实维护第二套读取链路。

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

- **WHEN** 页面需要展示源码版本或环境资源集合
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
- **AND** 最近终态任务 SHALL NOT 被标记为当前进行中或已完成状态

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
