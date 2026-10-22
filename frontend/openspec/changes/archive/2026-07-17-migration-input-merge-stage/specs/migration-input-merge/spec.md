## ADDED Requirements

### Requirement: 迁移输入合并阶段详情

系统 SHALL 在用户打开 `merge` Workflow 节点时展示迁移输入合并 Drawer，并加载当前项目合并阶段的状态、摘要、当前合并集和报告生成资格。

#### Scenario: 打开迁移输入合并阶段

- **WHEN** 用户点击 Workflow 中的 `merge` 节点
- **THEN** 系统 SHALL 使用当前 `projectId` 请求迁移输入合并阶段详情
- **AND** 系统 SHALL 在 `1100px` Drawer 中展示迁移输入结果视图

#### Scenario: 展示合并概览

- **WHEN** 迁移输入合并阶段详情加载成功
- **THEN** 系统 SHALL 展示已合并输入数、高风险问题数和待处理冲突数
- **AND** 系统 SHALL NOT 在结果展示区重复展示输入来源或冲突策略配置

### Requirement: 输入来源配置与重新合并

系统 SHALL 允许用户选择可用上游输入来源和冲突处理策略，并据此重新计算迁移输入合并结果。

#### Scenario: 打开输入来源配置

- **WHEN** 用户在迁移输入列表筛选栏操作输入来源
- **THEN** 系统 SHALL 在同一个 Drawer 内切换至输入来源配置视图
- **AND** 系统 SHALL 展示服务端返回的可用来源及其候选数量

#### Scenario: 重新合并选定来源

- **WHEN** 用户选择至少一个可用来源、设置冲突策略并确认重新合并
- **THEN** 系统 SHALL 将来源和策略提交至服务端重算当前合并集
- **AND** 成功后 SHALL 清除当前表格的临时选择并刷新阶段详情、合并列表和 workflow 状态

#### Scenario: 没有可用输入来源

- **WHEN** 服务端未返回任何可合并的上游来源
- **THEN** 系统 SHALL 展示空状态
- **AND** 系统 SHALL 禁用重新合并提交操作

### Requirement: 迁移输入列表审阅

系统 SHALL 以服务端分页列表展示合并后的迁移输入，并支持按查询条件审阅结果。

#### Scenario: 展示迁移输入列表

- **WHEN** 当前合并集存在迁移输入
- **THEN** 系统 SHALL 使用 BaseTable 展示选择、问题、来源、风险、路径或组件、建议处理、冲突和状态列
- **AND** 系统 SHALL 使用 `small` 表格尺寸、受控横向滚动和内容优先的自动高度

#### Scenario: 筛选迁移输入列表

- **WHEN** 用户设置关键词、风险、冲突或状态筛选条件
- **THEN** 系统 SHALL 将筛选条件和分页参数提交给列表 API
- **AND** 系统 SHALL NOT 在当前页面数据上执行本地筛选

#### Scenario: 选择输入项

- **WHEN** 用户勾选或取消勾选迁移输入项
- **THEN** 系统 SHALL 在 BaseTable 选择工具栏展示当前已选择数量
- **AND** 该选择 SHALL 仅表示待确认范围，不得直接改变服务端确认状态

### Requirement: 冲突处理与问题确认

系统 SHALL 要求用户先处理迁移输入冲突，再确认问题作为评估报告依据。

#### Scenario: 处理冲突项

- **WHEN** 用户对待处理冲突项执行处理冲突操作
- **THEN** 系统 SHALL 在同一个 Drawer 内展示各来源结论和冲突处理方式
- **AND** 系统 SHALL 支持采用一个来源结论或提交手工合并结论

#### Scenario: 提交冲突处理结果

- **WHEN** 用户确认冲突处理结果
- **THEN** 系统 SHALL 将最终结论提交到服务端
- **AND** 成功后 SHALL 刷新阶段摘要和迁移输入列表

#### Scenario: 含冲突项时阻止确认

- **WHEN** 当前已选输入中包含待处理冲突项
- **THEN** 系统 SHALL 禁用确认已选问题操作
- **AND** 系统 SHALL 提示用户先处理所选冲突

#### Scenario: 确认无冲突的已选问题

- **WHEN** 用户选择至少一个无待处理冲突的输入并确认确认已选问题
- **THEN** 系统 SHALL 在二次确认后将所选输入提交为已确认迁移输入
- **AND** 成功后 SHALL 刷新阶段摘要和迁移输入列表

### Requirement: 评估报告生成资格

系统 SHALL 仅在迁移输入基线满足报告生成条件时允许用户从迁移输入合并阶段生成评估报告。

#### Scenario: 存在待处理冲突

- **WHEN** 当前合并集中仍存在待处理冲突
- **THEN** Drawer Footer 的生成评估报告操作 SHALL 禁用
- **AND** 系统 SHALL 展示待处理冲突数量

#### Scenario: 不存在已确认输入

- **WHEN** 当前合并集不存在已确认迁移输入
- **THEN** Drawer Footer 的生成评估报告操作 SHALL 禁用

#### Scenario: 生成评估报告

- **WHEN** 当前存在已确认迁移输入且不存在待处理冲突，用户确认生成评估报告
- **THEN** 系统 SHALL 调用报告生成或阶段推进 API
- **AND** 成功后 SHALL 刷新 workflow 状态
