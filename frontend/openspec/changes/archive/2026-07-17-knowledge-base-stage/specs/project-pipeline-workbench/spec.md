## ADDED Requirements

### Requirement: 知识库扫描阶段状态

项目流水线工作台 SHALL 将后端返回的知识库扫描任务状态映射到前端固定维护的 `kb` 节点。

#### Scenario: 映射知识库扫描任务状态

- **WHEN** workflow 状态快照包含 `kb` 任务状态
- **THEN** 页面 SHALL 将其映射到前端固定的 `kb` 节点
- **AND** 知识库扫描任务的执行、完成或失败 SHALL 以服务端返回状态为事实来源

#### Scenario: 打开知识库扫描阶段详情

- **WHEN** 用户点击 Workflow 中的 `kb` 节点
- **THEN** 系统 SHALL 打开知识库扫描阶段 Drawer
- **AND** 系统 SHALL 使用当前 `projectId` 请求该项目的知识库扫描任务和结果数据
