## MODIFIED Requirements

### Requirement: 固定流程拓扑

画布 SHALL 在现有十二个业务节点基础上增加强弱内存序分析与浮点精度扫描两个节点。拓扑与坐标由前端维护，阶段 ID 与任务事实根据实际后端契约接入。

#### Scenario: 展示准备与分析关系

- **WHEN** 工作台渲染
- **THEN** 画布 SHALL 展示 `project -> env/assets -> x86-build`，并将 x86 构建保持为独立的一列
- **AND** 知识库扫描、依赖分析、强弱内存序分析和浮点精度扫描 SHALL 在后一列并行展示，四者均从 x86 构建取得展示级输入关系
- **AND** 两项新分析 SHALL 位于“扫描与分析”分组，分组边界、汇合线及反馈标签 SHALL 保持间距

#### Scenario: 展示验证与修复关系

- **WHEN** 工作台渲染评估后的流程
- **THEN** 画布 SHALL 保留 `report -> build -> test -> optimize -> archive` 及 `report -> manual`
- **AND** `manual -> assets` 与 `optimize -> assets` SHALL 保持带语义标签的回流边

## ADDED Requirements

### Requirement: 新分析节点的导航与报告输入边界

工作台 SHALL 将两项新分析纳入 Workflow、Step 和有效阶段深链接，并保持既有工作台行为。

#### Scenario: 两种视图切换分析阶段

- **WHEN** 用户在新分析阶段切换 Workflow 与 Step
- **THEN** 页面 SHALL 保留所选阶段，复用同一业务组件及项目上下文
- **AND** SHALL 沿用共享的未保存更改保护、阶段关闭与历史导航规则

#### Scenario: 新分析结果纳入报告输入

- **WHEN** 后端明确将新分析结果纳入报告输入
- **THEN** 工作台 SHALL 保持知识库扫描和依赖分析的 `n/2` 必需输入汇合计数与连线，两项专项分析通过确认后的报告输入纳入结果
- **AND** SHALL NOT 将画布中的可选分析自行升级为报告执行的必需门禁
