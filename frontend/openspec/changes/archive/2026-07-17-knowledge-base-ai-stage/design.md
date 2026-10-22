## Context

固定 Workflow 已包含 `kb-ai` 节点，但当前没有专属 Drawer。原型定义该节点消费知识库扫描 findings，批量生成原因解释、修改方式和验证建议，并将结果作为独立来源交由迁移输入合并。

已有知识库扫描阶段已建立阶段详情、结果分页、BaseTable 选择和 Drawer 内子视图模式。本 change 复用这些边界，不在 Drawer 上叠加 Modal，也不在页面中建立 SSE 或轮询。

## Goals / Non-Goals

**Goals:**

- 提供 AI 扩展建议的阶段状态、摘要、服务端分页结果和选择加入迁移输入能力。
- 将生成配置和结果审阅保留在同一个 Drawer 的内部视图中。
- 让生成范围与结果表选择各自有明确的数据来源，不依赖跨 Drawer 的临时状态。
- 为领域类型、API、mock 和测试建立同一正式响应包络契约。

**Non-Goals:**

- 不实现真实 AI 模型、流式输出、SSE、轮询、历史生成批次或单条建议编辑。
- 不在本阶段增加“忽略建议”或“人工确认”的独立操作；人工确认仅为 AI 结果的判断状态。
- 不支持从知识库扫描 Drawer 跨抽屉携带本地勾选到 AI 生成配置。

## Decisions

### 使用阶段详情与独立分页结果集

`GET /projects/:projectId/workflow/stages/kb-ai` 返回阶段状态、当前 `extensionId` 和三项摘要；`GET /knowledge-base-ai-extensions/:extensionId/suggestions` 以 `page`、`pageSize` 返回建议结果。生成和加入操作成功后失效阶段详情、建议结果和 workflow 状态 query。

该结构与 SBOM、知识库扫描一致：阶段详情提供权威摘要和当前结果集标识，BaseTable 负责服务端分页。前端不持久化建议数组，也不从 Workflow 拓扑推导业务结果。

### 生成范围只接受可稳定表达的知识库 findings 集合

生成请求支持 `ALL_FINDINGS` 与 `HIGH_RISK_FINDINGS` 两种输入范围，输出固定为原因解释、修改方式和验证建议。原型中“输出内容”只有一个值，做成 Select 不会带来业务选择，故不实现该字段。

原型中的“仅已选 findings”需要知识库扫描表跨 Drawer 保留选择集合，现有选择是局部临时状态。当前不提供该范围；未来若从知识库扫描页直接发起生成，应显式提交 `findingIds`，而非共享本地 UI 状态。

### 结果表选择只用于加入迁移输入

建议表包含 `选择`、关联 finding、判断、建议修改方式、建议验证方式和置信度列。表头 checkbox 提供当前页全选/反选；`selectedRowKeys` 仅服务于当前 BaseTable 结果集。

`加入迁移输入` 作为 BaseTable selection 工具栏操作，只提交当前勾选且 `migrationStatus=NOT_ADDED` 的 `suggestionIds`，并在 Popconfirm 确认后刷新结果。已加入建议保留可见状态但禁止再次选择。

替代方案是将“加入迁移输入”放在 Drawer 全局 Footer 并默认提交全部建议。该方式无法清楚表达用户选择范围，也与 SBOM/知识库扫描的批量加入交互不一致，因此不采用。

### Drawer 内部视图与宽度

组件维护 `results` 与 `config` 两个视图：结果视图可正常关闭；配置视图隐藏关闭入口并只允许取消/提交返回结果，避免放弃配置时误关 Drawer。

结果和生成配置作为同一阶段的内部视图，Drawer 均固定使用 `1100px`，避免切换时发生横向尺寸抖动。生成配置按完整 Drawer 内容区布局，不额外限制表单宽度。表格区复用 BaseTable 的内容优先高度策略，少量数据时 selection 与分页紧贴表格，大量数据时内部滚动。

### 建议状态映射

阶段状态为 `PENDING`、`RUNNING`、`SUCCEEDED`、`FAILED`。建议的 `judgment` 表达“必须修改”“条件保留”“需人工确认”；`confidence` 表达高、中、低置信度；`migrationStatus` 只表达“未加入”“已加入”。

“需人工确认”摘要由服务端结果汇总而来，不引入单独的确认 API 或本地判定规则。

## Risks / Trade-offs

- [生成范围暂不支持跨抽屉已选 findings] → 只提供稳定的全部/高风险范围；后续扩展时使用显式 `findingIds` 契约。
- [无 SSE 或轮询时运行中状态不会自动完成] → 提交后刷新阶段详情，用户再次打开 Drawer 时重新读取服务端权威状态。
- [长文本建议导致表格横向空间不足] → 结果 Drawer 使用 `1100px`，长文本列设置可读宽度和受控横向滚动。
- [生成再次执行会更新当前结果集] → 生成操作前明确其会刷新当前展示建议；不在本 change 提供历史批次入口。

## Migration Plan

1. 新增 AI 扩展领域类型、API、mock 状态和 API 契约测试。
2. 新增 `StageDrawer/KnowledgeBaseAi` 组件及其结果/配置子视图，复用 BaseDrawer 和 BaseTable。
3. 在 `StageDrawer/index.tsx` 注册 `kb-ai`，并在 mutation 成功后刷新 workflow 状态。
4. 增加交互测试并执行 OpenSpec、格式、lint、类型和测试验证。

回滚时移除 `kb-ai` Drawer 映射及新增领域 API/mock；固定 Workflow 节点仍可由 Default Drawer 兜底展示。

## Open Questions

- 正式后端是否将 AI 生成建模为独立异步任务并提供任务进度；本 change 先以阶段状态读取建模，不假设事件协议。
- 后续“人工确认”是否需要产生可编辑的审批结论；该需求应在迁移输入或修复阶段单独定义。
