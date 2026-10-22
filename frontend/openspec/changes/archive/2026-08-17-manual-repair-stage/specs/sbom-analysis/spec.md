## RENAMED Requirements

- FROM: `### Requirement: SBOM 分析结果 Drawer`
- TO: `### Requirement: 环境与依赖对比 Drawer`

## MODIFIED Requirements

### Requirement: 环境与依赖对比 Drawer

系统 SHALL 在用户点击 `sbom` 节点后，以“概览”和“替代性结果”为主视图展示当前最新环境与依赖对比及其组件替代结果；分析运行信息、采集详情、产物和历史记录 SHALL 作为次级视图提供。

#### Scenario: 已完成分析展示组件替代结果

- **WHEN** 当前最新环境与依赖对比已完成
- **THEN** Drawer SHALL 在概览中展示紧凑的分析状态、任务标识和完成时间，以及组件替代概览
- **AND** SHALL 使用该分析的正式结果加载替代性结果表
- **AND** 结果表 SHALL 提供组件替代详情入口
- **AND** SHALL 在概览中提供次级的查看分析信息入口

#### Scenario: 无分析、运行中或失败

- **WHEN** 项目不存在分析、分析运行中或分析失败
- **THEN** Drawer SHALL 展示与当前状态对应的空状态、运行状态或失败原因
- **AND** SHALL NOT 展示可操作的替代结果表

#### Scenario: 查看分析信息

- **WHEN** 用户进入分析信息
- **THEN** 系统 SHALL 在同一 Drawer 的次级视图展示该分析的运行信息、采集详情、产物和历史记录入口

### Requirement: 执行与重新分析

系统 SHALL 允许用户在同一环境与依赖对比 Drawer 内配置并手动执行替代性分析。

#### Scenario: 无分析时执行

- **WHEN** 项目尚无环境与依赖对比
- **THEN** 系统 SHALL 在空状态内容区提供“执行环境与依赖对比”主操作
- **AND** 点击后 SHALL 进入同一 Drawer 的分析配置视图

#### Scenario: 已完成分析时重新分析

- **WHEN** 当前分析已完成
- **THEN** Drawer SHALL 在概览区域提供“重新分析”操作
- **AND** SHALL 在确认覆盖当前结果后进入分析配置视图

#### Scenario: 配置分析

- **WHEN** 用户进入分析配置视图
- **THEN** 系统 SHALL 读取并只读展示当前项目级 x86 源环境与 RISC-V 目标环境
- **AND** 配置视图 SHALL 提供返回主视图的取消操作和提交操作

#### Scenario: 分析环境未配置完整

- **WHEN** 项目级运行环境配置不完整
- **THEN** 系统 SHALL 禁用开始分析操作
- **AND** SHALL 引导用户前往环境管理完成配置

#### Scenario: 提交项目级分析环境

- **WHEN** 用户确认开始环境与依赖对比
- **THEN** 系统 SHALL 不在分析创建请求中传递环境 ID
- **AND** SHALL 由服务端使用项目级运行环境配置创建分析
