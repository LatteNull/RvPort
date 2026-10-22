## 设计目标

本 change 将 frontend 的项目当前状态收敛到四类后端事实：overview、readiness、latest/List 和 SSE。页面不再根据历史记录、静态 Workflow 状态或 mutation 返回时机推算服务端事实。

环境管理、源码管理和各执行节点的查询职责、mutation 与 SSE 刷新所有权记录在 [`request-refresh-matrix.md`](request-refresh-matrix.md)。新增或修改 Drawer 请求前必须先确定唯一主要刷新所有者。

## 后端契约基线

### Overview

`GET /api/projects/{projectId}/overview` 提供：

- `project`
- `activeSourceRevision`
- `runtimeEnvironments`
- `recentTasks`
- `latestTaskEventId`

overview 只负责项目首屏上下文和项目级 SSE baseline。它不承担具体阶段执行门禁，也不替代领域 latest。

### Readiness

`GET /api/projects/{projectId}/readiness?stageId={stageId}` 返回 `stageId/context/prerequisites[]`。

- `key`：条件身份，也是中文名称和恢复入口的映射依据。
- `status`：`SATISFIED/MISSING/RUNNING/FAILED/STALE/UNAVAILABLE`，决定门禁与中文状态。
- `referenceId`：创建请求或详情跳转需要的关联事实。
- `details`：数量、双端构建 ID 等补充事实。
- `reasonCode`：诊断信息，不参与 frontend 恢复入口组合。

frontend 不读取整体 `ready`，而是对当前操作要求的 prerequisite 做 `key + status` 判断。

### Latest 与 List

领域 latest 使用统一外壳：

```text
context + freshness + execution + result
```

- `CURRENT`：属于当前 Context，可作为当前事实。
- `STALE`：属于旧 Context，只能引导用户查看历史。
- `EMPTY`：当前及历史均无可展示结果。
- `execution`：任务状态、进度、消息、错误与时间。
- `result`：领域结果。

List 负责分页历史或记录型主视图，不负责选择当前事实。x86 构建和构建验证是记录型例外：默认展示 List，由 latest 标记当前行并提供最近配置。

### SSE

项目 SSE 事件包含递增 ID、`projectId`、`stageId`、`resource` 和生命周期状态。frontend 使用 `latestTaskEventId` 建立 baseline，断线后携带最后处理的 ID 重连。

SSE 只表达“事实发生变化”，页面收到事件后重新读取对应事实，不直接用事件 payload 拼装领域最终状态。

## 页面信息架构

### 项目顶部上下文

首屏由三张等高卡片组成：

```text
项目上下文 | 当前迁移上下文                 | 执行上下文
项目/架构  | 当前源码 -> x86 环境 / RV 环境 | 活动任务/消息
```

- 项目卡是迁移过程起点。
- 迁移卡以当前源码和当前环境配置两个主层级表达 Context。
- x86 源环境与 RISC-V 目标环境分两行展示。
- 执行卡只对待执行、排队中和执行中任务展示活动状态；最近终态只作为最近记录摘要。
- 当前阶段和下一步在没有权威 Workflow 事实时不展示。

### Stage Drawer

Drawer 组件身份只由 stage ID 决定。readiness、latest 或任务状态变化不得替换领域组件，否则会丢失表单、滚动位置和内部视图，并造成关闭后重新打开动画。

默认视图并行读取当前操作需要的 readiness 与 latest。历史 List 只在进入历史视图后读取；进入历史、详情或关闭过程时停用不可见的 current observer，关闭动画结束后再重置内部状态。

## 阶段数据矩阵

| 阶段       | Readiness                | 当前事实                     | 历史/记录               | 说明                                       |
| ---------- | ------------------------ | ---------------------------- | ----------------------- | ------------------------------------------ |
| 环境管理   | 写操作自行校验           | overview 当前双环境          | 环境资源和执行记录 List | 当前环境由 PATCH 修改                      |
| 源码管理   | 写操作自行校验           | overview 当前源码            | 源码资源 List           | 当前源码变化由 Context SSE 校准            |
| x86 构建   | `x86-build`              | `SOURCE_ONLY latest`         | `SOURCE_ONLY` 分页记录  | latest 标记当前行并初始化命令              |
| 知识库扫描 | `kb`                     | `kb-scans/latest`            | 扫描分页历史            | `ACTIVE_SOURCE` 是门禁                     |
| 依赖分析   | `rv-dependency-analysis` | `dependency-analyses/latest` | 分析分页历史            | `X86_BUILD` 与 `TARGET_ENVIRONMENT` 是门禁 |
| 评估报告   | `report`                 | `reports/evaluation/latest`  | 报告分页历史            | 首份报告不被 `COMPARABLE_REPORT` 阻断      |
| 构建验证   | `build`                  | `VALIDATION latest`          | `BOTH` 分页记录         | 与 x86 构建统一表格结构                    |
| 自动化测试 | `test`                   | `automated-tests/latest`     | 测试和比较记录          | latest 锚定当前批次                        |
| 优化闭环   | `optimize`               | `optimization-cycles/latest` | 轮次分页历史            | 只展示 `CURRENT` 为当前轮次                |
| 归档       | `archive`                | `archives/latest`            | 归档分页历史            | `ARCHIVE_CANDIDATES` 是唯一创建门禁        |

## 前置条件展示

前置条件展示完整遍历 `prerequisites[]`：

1. 用 `key` 查找中文标题和恢复 stage。
2. 用 `status` 映射“已满足、未满足、进行中、失败、已过期、不可用”。
3. 用 `details` 补充候选数量或关联 ID。
4. 不将 `reasonCode` 拼进用户文案，也不用它选择恢复入口。

多个条件同时阻断时全部展示，恢复操作放在各自条件旁。满足条件时保留相同结构但切换成功语义。

## 页面状态

`StageStateNotice` 是纯展示组件，统一五类状态：

- `prerequisite`：当前门禁不满足。
- `ready`：门禁满足且当前 Context 暂无结果。
- `processing`：最新任务等待、排队或运行中。
- `execution-error`：最新业务执行失败、取消或超时。
- `request-error`：readiness/latest 请求失败。

接口失败与业务失败必须分开；“重新加载”只用于接口读取，“重新执行”只用于业务任务。

## 记录型页面

x86 构建和构建验证默认展示分页记录，不额外设置当前结果卡：

- 状态筛选位于 `BaseTable` 筛选区并进入 Query Key。
- latest `result.id` 对应行显示“当前” Tag。
- ID 单元格只展示 ID 和当前标记；状态、时间、环境与操作使用独立列。
- 构建命令优先从当前 latest 初始化，没有当前记录时使用默认值。
- latest 异步变化不覆盖用户已经编辑的表单。
- 退出码只在日志详情中展示。

## 自动化测试兼容边界

自动化测试的门禁和当前批次只认 readiness/latest。若 latest 只返回当前批次单侧运行，frontend 可以用当前源码测试 List 补齐同一批次另一侧；该兼容读取不得选择其他批次或改变门禁。

若 readiness 未提供创建请求所需的双端 build ID，frontend 可以读取当前源码构建记录补齐请求参数。该读取属于参数补全，不是执行事实来源。

## SSE 刷新调度

### Overview

- `project.context.changed`：250ms 固定窗口合并。
- `task.created/queued/started`：5 秒固定窗口合并。
- `task.progress`：最多每 10 秒刷新一次。
- `task.succeeded/failed/cancelled/timeout`：取消已覆盖的延迟任务并立即刷新。
- `task.log`：只推进游标。

### 领域查询

- 非终态事件按 Query Key 在 250ms 内合并一次失效。
- terminal 取消对应待执行刷新并立即读取最终事实。
- 路由只使用 `stageId/resource.type/mode/environmentRole`，不使用旧 `taskType` 推断。
- 未识别的 Context 变化使用保守的完整下游刷新。

### Mutation 所有权

异步 mutation 成功只提示任务已提交，不失效同一领域 latest/List，也不额外刷新 overview。SSE 生命周期负责运行态和终态；用户手动刷新继续立即读取。

同步 Context mutation 可以合并 overview 提供即时反馈，但下游 readiness/latest/List 仍由 `project.context.changed` 负责权威刷新。

## 查询作用域

- overview 使用共享 Query Key，并禁用挂载、窗口聚焦和网络重连的隐式 refetch。
- 分页 List 同样不因窗口聚焦或网络重连重复读取。
- current、history、detail、log 每次只启用当前可见视图需要的查询。
- 刷新历史只刷新 List；刷新详情只刷新对应记录；环境管理只刷新当前环境视图。
- SSE 正常期间不配置固定 latest 轮询。

## 报告纳入状态

当前 Context 的知识库 finding 和依赖结果提供互斥单条操作：未纳入或已排除时只显示“纳入报告”，已纳入时只显示“排除”。成功后同步更新详情与来源列表，并刷新报告 readiness 和受影响聚合。历史 Context 一律只读。

## 退役范围

frontend 已删除没有生产入口的知识库 AI、迁移输入合并、SBOM、源码对比 Drawer 及专属 API，并删除被项目级任务事件流替代的旧 Workflow realtime。历史实现和被后续决策覆盖的视觉方案只保留在 `implementation-log.md`。

## 验证

收口必须通过：

- Prettier format check
- ESLint
- TypeScript typecheck
- 受影响页面、共享组件和 SSE 测试
- `openspec validate remediate-issue --strict`
