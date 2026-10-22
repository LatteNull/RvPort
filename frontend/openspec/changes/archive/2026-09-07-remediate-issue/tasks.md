> 本清单只记录最终可验收结果。实施过程、临时兼容方案和被后续决策替代的视觉迭代保留在 `implementation-log.md`。

## 1. 当前上下文与工作台

- [x] 1.1 映射 overview 顶层 `project/activeSourceRevision/runtimeEnvironments/recentTasks/latestTaskEventId`，作为项目当前上下文和 SSE baseline。
- [x] 1.2 删除 frontend GET `/runtime-environments` 和 `active=true&pageSize=1` 当前源码读取，环境资源和源码历史继续使用领域 List。
- [x] 1.3 将首屏收敛为项目上下文、当前迁移上下文和执行上下文三张等高卡片，统一标题基线和蓝绿视觉衔接。
- [x] 1.4 当前迁移上下文展示当前源码及两行 source/target 环境，不展示静态推算的当前阶段与下一步。
- [x] 1.5 执行上下文只对待执行、排队中和运行中任务展示状态与进度，最近终态不冒充当前任务状态。

## 2. Readiness、latest 与历史

- [x] 2.1 x86 构建、知识库扫描、依赖分析、评估报告、构建验证、自动化测试、优化闭环和归档接入对应 stage readiness。
- [x] 2.2 readiness 是唯一执行门禁；页面按 prerequisite `key + status` 判断，`details` 仅补充事实，展示层不使用 `reasonCode` 组织恢复入口。
- [x] 2.3 知识库扫描、依赖分析、评估报告、自动化测试、优化闭环和归档使用领域 latest 区分 `CURRENT/STALE/EMPTY`，不使用 List 第一条推算当前事实。
- [x] 2.4 x86 构建和构建验证使用分页记录作为主视图，以 latest 标记当前行并初始化最近配置，状态筛选进入 List 请求与 Query Key。
- [x] 2.5 自动化测试只用 readiness 判断门禁、用 latest 锚定当前批次；List 兼容读取只补齐同批另一侧结果或创建参数，不参与当前事实选择。
- [x] 2.6 历史 List 和历史详情保持只读，不参与当前门禁、当前批次和当前结果判断。
- [x] 2.7 进入历史、详情或关闭过程时停用不可见 current 查询，关闭动画完成后再重置内部视图。

## 3. 共享交互与领域页面

- [x] 3.1 使用共享前置条件面板展示全部条件，恢复操作归属具体 prerequisite，并支持响应式换行。
- [x] 3.2 使用 `StageStateNotice` 统一 prerequisite、ready、processing、execution-error 和 request-error，区分业务失败与接口失败。
- [x] 3.3 统一唯一主操作、普通重新执行按钮和末尾历史文字入口的操作层级。
- [x] 3.4 依赖分析提供受控自动修复候选选择；历史分析只读，自动修复任务不覆盖依赖分析 latest。
- [x] 3.5 知识库 finding 与依赖结果在当前 Context 提供互斥单条纳入/排除操作，更新后同步详情、来源列表、报告 readiness 和相关聚合。
- [x] 3.6 构建验证与 x86 构建统一记录字段、状态样式、当前标记和日志层级；自动化测试统一前置条件、配置、结果和比较结构。
- [x] 3.7 优化闭环按本轮结论、闭环进度、问题收敛、验证结果和待处理事项组织，未通过结果比较时不引导归档。
- [x] 3.8 归档按交付结论、交付快照、完整性和交付清单组织；`ARCHIVE_CANDIDATES` 是唯一创建门禁。
- [x] 3.9 删除 frontend 无生产入口的知识库 AI、迁移输入合并、SBOM、源码对比和旧 Workflow realtime 实现。

## 4. SSE 与请求刷新所有权

- [x] 4.1 以 overview `latestTaskEventId` 建立项目 SSE，按递增事件 ID 去重，使用最后处理游标重连，页面恢复可见时校准 overview。
- [x] 4.2 SSE 只按 `stageId/resource.type/mode/environmentRole` 路由领域查询，不使用旧 `taskType` 推断；`task.log` 只推进游标。
- [x] 4.3 overview 按事件语义调度：Context 250ms 合并、created/queued/started 5 秒合并、progress 10 秒节流、terminal 立即刷新并取消被覆盖任务。
- [x] 4.4 领域非终态事件按 Query Key 在 250ms 内合并，terminal 取消待执行刷新并立即读取最终事实。
- [x] 4.5 异步 mutation 成功只反馈提交结果，不抢跑刷新 latest/List/overview；SSE 是运行态和终态主要刷新所有者。
- [x] 4.6 Context mutation 只即时合并 overview，下游 readiness/latest/List 由 `project.context.changed` 权威刷新。
- [x] 4.7 current、history、detail 和 log 只启用当前可见查询；共享 overview 和分页 List 禁用挂载、聚焦和重连隐式 refetch。
- [x] 4.8 移除领域 latest 固定轮询，保留 SSE 重连和用户手动刷新。
- [x] 4.9 建立并更新 `request-refresh-matrix.md`，记录环境、源码及全部执行节点的查询职责和唯一刷新所有者。

## 5. Change 收口与验证

- [x] 5.1 proposal、design 和 specs 已按当前后端契约重写，删除旧动态 Workflow、overview 内 readiness、独立源码部署、SBOM 和批量纳入规划。
- [x] 5.2 历史实施过程保留在 `implementation-log.md`，最终 tasks 只保留当前可验收结果。
- [x] 5.3 运行 frontend Prettier、ESLint 和 TypeScript typecheck。
- [x] 5.4 运行受影响页面、共享组件、SSE 与 API 测试，修复失败或超时用例。
- [x] 5.5 运行 `openspec validate remediate-issue --strict` 并确认最终文档一致。
