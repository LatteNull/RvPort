## ADDED Requirements

### Requirement: 评估报告节点详情

项目流水线工作台 SHALL 支持从 `report` 节点打开专属评估报告 Drawer，并在报告操作成功后同步 Workflow 状态。

#### Scenario: 打开评估报告 Drawer

- **WHEN** 用户点击 Workflow 中的 `report` 节点
- **THEN** 工作台 SHALL 打开评估报告专属 Drawer
- **AND** 工作台 SHALL 将当前项目 ID 传递给该 Drawer 的领域查询

#### Scenario: 报告阶段操作刷新 Workflow

- **WHEN** 用户成功重新生成报告或进入修复阶段
- **THEN** 工作台 SHALL 失效并重新读取 Workflow 状态快照
- **AND** 工作台 SHALL 根据服务端返回状态更新固定 Workflow 拓扑的 `report` 与后续阶段状态
