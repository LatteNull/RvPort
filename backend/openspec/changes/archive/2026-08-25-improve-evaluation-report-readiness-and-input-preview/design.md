## Context

独立迁移输入合并节点已经移除，迁移输入确认改为在 KB 扫描、依赖分析等来源节点内完成。评估报告生成仍基于 `migration_input_refs.status=CONFIRMED`，并在生成时写入不可变 `report_inputs` 快照。

当前缺口在于报告页缺少生成前可见性：用户无法在评估报告节点直接判断当前源码版本有哪些输入会进入报告、哪些低风险项不会进入报告、是否可以生成报告，以及生成后的报告与当前输入状态是否一致。

## Goals / Non-Goals

**Goals:**

- 为评估报告页提供 readiness/overview 数据，支持前端展示当前源码版本、最新报告、历史报告、输入统计、阻塞原因和警告。
- 提供生成前输入预览，分页展示当前源码版本下的 migration input reference，支持过滤和排序。
- 报告详情补充输入状态摘要，使用户能区分“历史报告快照”和“当前源码版本输入状态”。
- 保持报告生成逻辑只读取 `CONFIRMED` 输入，历史报告继续不可变。
- 补充单元测试和 E2E，覆盖正常流程、异常流程、edge case。

**Non-Goals:**

- 不恢复独立迁移输入合并节点。
- 不新增复杂冲突合并逻辑。
- 不改变 KB 扫描、依赖分析节点内确认入口的基本行为。
- 不改变报告 HTML/JSON 制品的对象存储机制。
- 不处理前端页面实现。

## Decisions

### 使用现有 migration input reference 作为 readiness 来源

readiness 直接读取当前 `project_id + source_revision_id` 下的 `migration_input_refs`，按 `status`、`source_type` 和归一化风险等级聚合。

原因：
- 这是报告生成实际消费的事实来源。
- 不需要新增中间表，避免重新引入“合并节点状态”。
- 可以自然反映节点内人工加入、撤回后的状态。

备选方案是引入报告草稿表，但这会产生新状态同步问题，且真实报告仍要读取 confirmed input，收益不明显。

### readiness 返回 blockers 和 warnings

生成报告前的问题分两类：
- `blockers`：没有 active source revision、源码版本不属于项目、没有 confirmed 输入等会导致不能生成报告的问题。
- `warnings`：存在 LOW candidate、存在 excluded、没有最新报告、存在较旧报告等不阻止生成但需要前端提示的问题。

这样前端可以直接控制按钮状态，并展示具体原因。

### 输入预览是报告页视角的只读列表

输入预览接口返回当前源码版本下所有 `CONFIRMED`、`CANDIDATE`、`EXCLUDED` reference，可按来源、状态、风险等级、关键字过滤。用户要改变状态仍调用已有 migration input 更新接口或节点内确认接口。

这样避免把评估报告页变成新的合并节点，同时保留生成前审计能力。

### 报告详情同时表达快照和当前状态

报告详情继续返回报告生成时的快照摘要，同时补充当前源码版本的输入状态摘要。两者语义必须分开：
- `report.inputs` 或 `report.summary` 表示生成时快照。
- `currentInputSummary` 表示同源码版本当前 migration input 状态。

这样用户重新确认/撤回后能理解旧报告为何不变，以及是否需要重新生成报告。

## Risks / Trade-offs

- **风险：前端误把 current input summary 当作历史报告内容。** → DTO 字段命名区分 `snapshot` 与 `current`，文档明确历史报告不可变。
- **风险：readiness 聚合和报告生成查询口径不一致。** → service 内复用同一套 confirmed 查询/统计逻辑，并增加单元测试。
- **风险：输入预览返回过多来源详情导致响应过大。** → 预览只返回展示字段和来源定位；完整详情仍回到来源节点接口查询。
- **风险：LOW 默认不进入报告造成用户遗漏。** → readiness 必须返回 LOW candidate 统计和 warning，E2E 覆盖人工加入后可进入报告。
