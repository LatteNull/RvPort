## Why

仓库已提供 `memory-order-analyzer` 与 `floating-point-precision-scanner`，并升级了共享 LLVM Bitcode 制品协议。项目工作台尚未展示这两项分析能力，用户无法理解 x86 构建制品与后续迁移风险分析的关系。需要为强弱内存序分析、浮点精度扫描增加阶段入口，后端已发布专项分析运行时（d64b3362），本轮接入真实任务与结果。

## What Changes

- 在“扫描与分析”分组增加“强弱内存序分析”和“浮点精度扫描”两个节点；x86 构建保持独立的一列，四项分析位于其后的并行列。
- Workflow、Step、阶段深链接及 Drawer/Panel 使用同一阶段定义与业务组件。
- 两节点沿用现有阶段状态与前置条件辅助状态；以真实 Overview/readiness 与分析接口替换示例数据，不新增阶段状态。
- 根据真实 Overview、readiness、任务事件和结果接口展示执行、历史、完整性、风险及源码证据。
- 报告输入范围与必需性以实际后端契约为准，不因画布连线自行增加门禁。

## Capabilities

### New Capabilities

- `migration-risk-analysis-stages`：两项分析的阶段状态、真实任务接入及结果语义。

### Modified Capabilities

- `project-pipeline-workbench`：十四阶段拓扑、两项分析的入口与可用输入汇合计数。

## Impact

仅修改 `frontend/`。影响阶段 ID 类型、Workflow 拓扑与展示推导、Step 导航、路由校验、阶段载体、领域 API/类型/query keys、任务事件消费与测试。

本 change 已完成两个节点的示例展示，本轮以正式 API 替换运行时示例。阶段 ID 使用 `memory-order-analysis` 与 `floating-point-analysis`；显示名称保持不变。不修改后端或工具，不管理扫描容器。示例 fixture 只保留在测试中，任何请求失败都不回退为示例结果。既有工作台载体、当前节点样式和会话边界工作保持其原有范围。
