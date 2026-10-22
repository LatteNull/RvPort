## MODIFIED Requirements

### Requirement: 项目流水线工作台内容

项目流水线工作台页面 SHALL 汇总当前迁移项目状态并渲染迁移流程，但 MUST NOT 在页面渲染时自动执行流水线任务。

#### Scenario: SBOM 阶段状态

- **WHEN** workflow 状态快照包含 `sbom` 任务状态
- **THEN** 页面 SHALL 将其映射到前端固定的 `sbom` 节点
- **AND** SBOM 任务的执行、完成或失败 SHALL 以服务端返回状态为事实来源
