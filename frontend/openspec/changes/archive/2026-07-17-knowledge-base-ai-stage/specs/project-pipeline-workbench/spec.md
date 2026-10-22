## ADDED Requirements

### Requirement: 知识库 AI 扩展阶段详情入口

项目流水线工作台 SHALL 将固定的 `kb-ai` Workflow 节点映射为知识库 AI 扩展 Drawer，并以服务端状态作为节点状态事实来源。

#### Scenario: 打开知识库 AI 扩展 Drawer

- **WHEN** 用户点击 Workflow 中的 `kb-ai` 节点
- **THEN** 系统 SHALL 使用当前项目上下文打开知识库 AI 扩展 Drawer

#### Scenario: AI 扩展操作同步 Workflow 状态

- **WHEN** 用户成功提交 AI 扩展建议生成或加入迁移输入操作
- **THEN** 系统 SHALL 失效并重新读取项目 Workflow 状态
- **AND** `kb-ai` 节点 SHALL 映射服务端返回的最新阶段状态
