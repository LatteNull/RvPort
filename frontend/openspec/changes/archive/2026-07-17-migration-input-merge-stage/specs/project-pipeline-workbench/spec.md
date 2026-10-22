## ADDED Requirements

### Requirement: 迁移输入合并节点详情

项目流水线工作台 SHALL 支持从 `merge` 节点打开专属迁移输入合并 Drawer，并将该阶段 mutation 的服务端状态同步回 Workflow。

#### Scenario: 打开迁移输入合并 Drawer

- **WHEN** 用户点击 Workflow 中的 `merge` 节点
- **THEN** 工作台 SHALL 打开迁移输入合并专属 Drawer
- **AND** 工作台 SHALL 将当前项目 ID 传递给该 Drawer 的领域查询

#### Scenario: 合并阶段操作刷新 Workflow

- **WHEN** 用户成功重新合并输入、处理冲突、确认问题或生成评估报告
- **THEN** 工作台 SHALL 失效并重新读取 Workflow 状态快照
- **AND** 工作台 SHALL 根据服务端返回状态更新固定 Workflow 拓扑的 `merge` 与后续阶段状态
