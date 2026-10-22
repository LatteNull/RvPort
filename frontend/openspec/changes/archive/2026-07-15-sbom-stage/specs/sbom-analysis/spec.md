## ADDED Requirements

### Requirement: SBOM 分析结果 Drawer

系统 SHALL 在用户点击 `sbom` 节点后加载并展示 SBOM 分析任务状态、替代性统计和组件替代结果。

#### Scenario: 已完成分析展示结果

- **WHEN** SBOM 分析已完成
- **THEN** Drawer SHALL 展示 x86 组件、RISC-V 候选和无替代组件统计
- **AND** SHALL 展示选择、x86 组件、x86 版本、架构、来源路径、RISC-V 候选、替代状态和建议列

#### Scenario: 运行或失败分析

- **WHEN** SBOM 分析运行中或失败
- **THEN** Drawer SHALL 展示服务端任务状态或失败原因
- **AND** SHALL 禁止加入迁移输入

### Requirement: SBOM 结果选择与迁移输入

系统 SHALL 仅将用户选中的 SBOM 结果加入迁移输入。

#### Scenario: 选择结果

- **WHEN** 用户操作全选或单行选择
- **THEN** 系统 SHALL 更新已选数量
- **AND** 全选 SHALL 仅作用于当前结果表

#### Scenario: 加入已选项

- **WHEN** 用户确认加入迁移输入且至少选中一项
- **THEN** 系统 SHALL 提交已选结果并刷新迁移输入相关状态
- **AND** SHALL NOT 自动推进 `merge` 阶段

#### Scenario: 未选择结果

- **WHEN** 用户尝试加入迁移输入但未选中结果
- **THEN** 系统 SHALL 阻止提交并提示先选择结果

### Requirement: 执行与重新分析

系统 SHALL 允许用户配置并执行 SBOM 替代性分析。

#### Scenario: 配置分析

- **WHEN** 用户执行或重新分析
- **THEN** 系统 SHALL 在 Modal 中配置 x86 源环境、RISC-V 目标环境、软件源策略、采集范围和分析选项

#### Scenario: 重新分析

- **WHEN** 用户确认重新分析
- **THEN** 系统 SHALL 创建新的 SBOM 分析任务
- **AND** SHALL 明确提示当前结果和选择将被覆盖
