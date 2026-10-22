## Why

项目工作台和阶段 Drawer 曾分别从 overview、列表首条、局部缓存和定时轮询推断当前状态，导致同一项目上下文出现重复请求、状态冲突和 Drawer 重挂载。现有后端已经提供项目 overview、阶段 readiness、领域 latest 和项目级 SSE，本 change 负责让 frontend 严格按这些事实来源展示和刷新。

## What Changes

- 项目页只用 `GET /api/projects/{projectId}/overview` 读取项目、当前源码、当前运行环境、最近任务和 SSE baseline；frontend 不再额外 GET `/runtime-environments` 或用源码 List 查询当前源码。
- 顶部摘要收敛为“项目上下文、当前迁移上下文、执行上下文”三张卡片；迁移上下文展示当前源码及两行运行环境，不展示前端推算的当前阶段和下一步。
- 执行类 Drawer 使用 `readiness(stageId)` 作为唯一执行门禁，使用领域 `latest` 作为当前 Context 事实，使用分页 List 展示历史或记录集合。
- x86 构建和构建验证是记录型页面：默认展示分页记录，以 latest 标记当前记录并初始化最近配置，不增加单条当前结果二级视图。
- 知识库扫描、依赖分析、评估报告、自动化测试、优化闭环和归档按 `CURRENT/STALE/EMPTY` 区分当前事实、旧 Context 事实和首次执行。
- 阶段前置条件由 `prerequisites[]` 驱动：`key` 决定条件名称和恢复入口，`status` 决定状态与门禁，`details` 仅补充事实；展示层不使用 `reasonCode` 组织交互。
- 项目 SSE 只通知变化，不直接成为业务状态源。frontend 按 `stageId/resource` 失效 readiness、latest 和 List，并按事件语义合并 overview 刷新。
- 异步 mutation 成功只反馈任务已提交，不抢跑刷新；SSE 是运行态和终态的主要刷新所有者，用户手动刷新仍立即读取。
- Drawer 进入历史、详情或关闭过程时停用不可见的 current 查询；关闭动画结束后再重置内部视图。
- 知识库 finding 和依赖结果保留当前 Context 下的单条纳入/排除操作，历史详情保持只读。
- 删除 frontend 已无生产入口的知识库 AI、迁移输入合并、SBOM、源码对比以及旧 Workflow realtime 实现。

## Capabilities

### New Capabilities

- `project-overview-current-context`：定义 frontend 对 overview 当前源码、当前运行环境、最近任务和 SSE baseline 的消费边界。

### Modified Capabilities

- `project-pipeline-workbench`：定义 readiness、latest、List 与 SSE 的职责和阶段 Drawer 的当前/历史展示规则。
- `frontend-code-reuse`：统一前置条件、页面状态、恢复操作和报告纳入交互。

## Impact

- Frontend：项目详情页、Stage Drawer、TanStack Query key、SSE 刷新调度、领域 API 类型、共享状态组件及测试。
- Backend：本 change 消费现有 overview、readiness、latest、List、mutation 和 SSE 契约，不新增后端接口要求。
- API：保留 PATCH `/runtime-environments`；frontend 不调用独立 GET `/runtime-environments`。历史 List 继续按各领域现有分页契约读取。
- Runtime：不新增依赖，不改变 Workflow 节点 ID 和 React Flow 拓扑。

## Delivery Boundary

- 当前后端响应是本 change 的契约基线；不再保留动态 Workflow、overview 内 build/source-deployment readiness、复合构建 `resource.step`、批量报告纳入或删除后端兼容路由等旧规划。
- 实施过程和被后续决策替代的方案保留在 `implementation-log.md`，不再作为最终验收任务。
- 最终验收以 frontend 格式、lint、typecheck、相关测试和 `openspec validate --strict` 全部通过为准。
