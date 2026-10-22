## ADDED Requirements

### Requirement: 知识库 AI 扩展阶段结果

系统 SHALL 为项目 Workflow 的 `kb-ai` 阶段提供专属 Drawer，并以服务端阶段详情展示 AI 扩展建议的状态、待解释 findings 数、已生成建议数和需人工确认数。

#### Scenario: 打开 AI 扩展阶段

- **WHEN** 用户点击项目 Workflow 中的 `kb-ai` 节点
- **THEN** 系统 SHALL 使用当前 `projectId` 请求知识库 AI 扩展阶段详情
- **AND** 系统 SHALL 在结果视图展示服务端返回的状态和三项摘要

#### Scenario: 阶段尚未生成建议

- **WHEN** 阶段详情不存在当前建议结果集
- **THEN** 系统 SHALL 展示尚未生成建议的空态
- **AND** 系统 SHALL 提供进入生成配置视图的入口

#### Scenario: 阶段正在生成建议

- **WHEN** 服务端阶段状态为 `RUNNING`
- **THEN** 系统 SHALL 展示生成中的状态
- **AND** 系统 SHALL NOT 将本地提交状态视为生成完成

#### Scenario: 阶段生成失败

- **WHEN** 服务端阶段状态为 `FAILED`
- **THEN** 系统 SHALL 展示服务端返回的失败信息或可理解的失败提示
- **AND** 系统 SHALL 提供重新进入生成配置视图的恢复入口

### Requirement: 生成 AI 扩展建议

系统 SHALL 在同一个 Drawer 内提供生成配置视图，并根据稳定表达的知识库 findings 范围请求生成 AI 扩展建议。

#### Scenario: 选择生成范围

- **WHEN** 用户打开生成配置视图
- **THEN** 系统 SHALL 提供“全部知识库 findings”和“仅高风险 findings”作为输入范围
- **AND** 系统 SHALL 默认选择“全部知识库 findings”

#### Scenario: 固定生成内容

- **WHEN** 用户配置 AI 扩展建议生成
- **THEN** 系统 SHALL 固定生成原因解释、修改方式和验证建议
- **AND** 系统 SHALL NOT 展示只有单一固定选项的输出内容选择控件

#### Scenario: 提交生成

- **WHEN** 用户确认生成 AI 扩展建议
- **THEN** 系统 SHALL 调用生成接口并回到结果视图
- **AND** 系统 SHALL 刷新 AI 扩展阶段详情、建议结果和 Workflow 状态

#### Scenario: 取消生成配置

- **WHEN** 用户在生成配置视图取消操作
- **THEN** 系统 SHALL 返回结果视图且不发起生成请求

### Requirement: AI 扩展建议结果表

系统 SHALL 使用服务端分页展示当前 AI 扩展结果集，并提供可选择的建议行。

#### Scenario: 展示建议列

- **WHEN** 当前建议结果集加载成功
- **THEN** 表格 SHALL 展示选择、关联 finding、判断、建议修改方式、建议验证方式和置信度列

#### Scenario: 表格分页

- **WHEN** 用户切换建议结果页或每页条数
- **THEN** 系统 SHALL 将 `page` 和 `pageSize` 传递给建议结果列表接口
- **AND** 系统 SHALL 以服务端返回的总数和页码渲染分页器

#### Scenario: 全选当前页建议

- **WHEN** 用户操作建议表的表头选择控件
- **THEN** 系统 SHALL 支持全选或取消全选当前页中可加入迁移输入的建议
- **AND** 已加入迁移输入的建议 SHALL 不可被选择

#### Scenario: 少量建议结果的布局

- **WHEN** 建议结果数量未占满 Drawer 可用高度
- **THEN** 选择工具栏和分页器 SHALL 紧贴表格底部
- **AND** 系统 SHALL NOT 将分页器强制固定在 Drawer 底部

### Requirement: 将已选 AI 建议加入迁移输入

系统 SHALL 仅将用户在结果表选择的未加入建议加入迁移输入，并提供二次确认。

#### Scenario: 加入已选建议

- **WHEN** 用户选择至少一条 `NOT_ADDED` 建议并确认加入迁移输入
- **THEN** 系统 SHALL 提交已选 `suggestionIds`
- **AND** 系统 SHALL 刷新建议结果及其持久加入状态

#### Scenario: 已加入建议不可重复提交

- **WHEN** 建议的迁移输入状态为 `ADDED`
- **THEN** 系统 SHALL 展示“已加入”状态
- **AND** 系统 SHALL 禁止用户再次选择或提交该建议

#### Scenario: 未选择建议

- **WHEN** 用户未选择可加入的建议
- **THEN** 系统 SHALL 禁用加入迁移输入操作

### Requirement: Drawer 子视图关闭语义

系统 SHALL 将 AI 扩展的结果和生成配置保留在同一个 Drawer 内，并防止配置过程中意外关闭。

#### Scenario: 结果视图关闭 Drawer

- **WHEN** 用户处于结果视图
- **THEN** 系统 SHALL 保留标准 Drawer 关闭入口

#### Scenario: 配置视图防止意外关闭

- **WHEN** 用户处于生成配置视图
- **THEN** 系统 SHALL 隐藏 Drawer 右上角关闭入口
- **AND** 系统 SHALL 不因遮罩点击或键盘操作离开配置视图

### Requirement: AI 扩展 Drawer 宽度稳定性

系统 SHALL 在知识库 AI 扩展的结果和生成配置视图之间保持 Drawer 宽度稳定。

#### Scenario: 切换内部视图

- **WHEN** 用户在 AI 扩展结果视图和生成配置视图之间切换
- **THEN** Drawer SHALL 保持 `1100px` 宽度
- **AND** 系统 SHALL NOT 因视图切换缩放 Drawer

#### Scenario: 展示生成配置

- **WHEN** 用户查看生成配置视图
- **THEN** 配置表单 SHALL 使用 Drawer 的完整内容区宽度
- **AND** Drawer SHALL 保持 `1100px` 宽度
