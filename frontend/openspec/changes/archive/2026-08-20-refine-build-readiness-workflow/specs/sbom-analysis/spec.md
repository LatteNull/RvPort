## MODIFIED Requirements

### Requirement: 环境与依赖对比 Drawer

系统 SHALL 在用户通过既有入口打开 `sbom` 阶段时，以“概览”和“替代性结果”为主视图展示当前最新环境与依赖对比及其组件替代结果；分析运行信息、采集详情、产物和历史记录 SHALL 作为次级视图提供。固定 Workflow 画布 SHALL NOT 将该 Drawer 作为构建前主路径入口。

#### Scenario: 已完成分析展示组件替代结果

- **WHEN** 当前最新环境与依赖对比已完成且用户通过既有入口打开 Drawer
- **THEN** Drawer SHALL 在概览中展示紧凑的分析状态、任务标识和完成时间，以及组件替代概览
- **AND** SHALL 使用该分析的正式结果加载替代性结果表
- **AND** 结果表 SHALL 提供组件替代详情入口
- **AND** SHALL 在概览中提供次级的查看分析信息入口

#### Scenario: 无分析、运行中或失败

- **WHEN** 项目不存在分析、分析运行中或分析失败且用户通过既有入口打开 Drawer
- **THEN** Drawer SHALL 展示与当前状态对应的空状态、运行状态或失败原因
- **AND** SHALL NOT 展示可操作的替代结果表

#### Scenario: 查看分析信息

- **WHEN** 用户通过既有入口进入分析信息
- **THEN** 系统 SHALL 在同一 Drawer 的次级视图展示该分析的运行信息、采集详情、产物和历史记录入口
