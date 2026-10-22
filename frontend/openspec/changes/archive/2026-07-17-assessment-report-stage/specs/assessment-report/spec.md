## ADDED Requirements

### Requirement: 评估报告阶段详情

系统 SHALL 在用户打开 `report` Workflow 节点时展示评估报告 Drawer，并加载当前项目已生成报告的状态、风险概览和结构化摘要。

#### Scenario: 打开评估报告阶段

- **WHEN** 用户点击 Workflow 中的 `report` 节点
- **THEN** 系统 SHALL 使用当前 `projectId` 请求评估报告阶段详情
- **AND** 系统 SHALL 在 `800px` Drawer 中展示报告结果视图

#### Scenario: 展示风险概览

- **WHEN** 当前评估报告加载成功
- **THEN** 系统 SHALL 展示总体风险、高风险问题数量和预计工作量三项摘要
- **AND** 系统 SHALL NOT 展示迁移输入来源、冲突策略或输入选择状态

#### Scenario: 展示报告摘要

- **WHEN** 当前评估报告加载成功
- **THEN** 系统 SHALL 展示评估结论、主要风险、依赖替代性、建议路线和下一步动作

#### Scenario: 尚未生成报告

- **WHEN** 评估报告阶段不存在当前报告结果
- **THEN** 系统 SHALL 展示空状态或服务端返回的阶段状态
- **AND** 系统 SHALL NOT 伪造报告指标或摘要内容

### Requirement: 重新生成当前报告

系统 SHALL 允许用户在报告阶段重新生成当前评估报告，并明确告知覆盖影响。

#### Scenario: 确认重新生成

- **WHEN** 用户操作重新生成报告并在二次确认中确认
- **THEN** 系统 SHALL 调用服务端重新生成当前报告
- **AND** 系统 SHALL 明确提示本次操作会覆盖当前报告结果

#### Scenario: 重新生成成功

- **WHEN** 服务端成功重新生成当前报告
- **THEN** 系统 SHALL 刷新报告详情和 Workflow 状态
- **AND** 系统 SHALL 展示服务端返回的最新报告内容

### Requirement: 导出评估报告

系统 SHALL 支持在报告 Drawer 内导出当前评估报告。

#### Scenario: 打开导出配置

- **WHEN** 用户在报告 Footer 操作导出报告
- **THEN** 系统 SHALL 在同一个 Drawer 内切换至导出视图
- **AND** 系统 SHALL 提供文件名和 HTML、JSON、Markdown 格式选择

#### Scenario: 格式切换文件扩展名

- **WHEN** 用户切换导出格式且未手动修改文件名
- **THEN** 系统 SHALL 将默认文件名扩展名同步为该格式对应的扩展名

#### Scenario: 导出当前报告

- **WHEN** 用户提交格式和有效文件名
- **THEN** 系统 SHALL 请求服务端导出当前报告并触发文件下载或展示服务端返回的下载入口
- **AND** 系统 SHALL NOT 因导出操作修改报告内容或 Workflow 状态

### Requirement: 从报告进入修复阶段

系统 SHALL 允许用户从已有评估报告进入修复阶段。

#### Scenario: 确认进入修复阶段

- **WHEN** 当前报告存在且用户确认进入修复阶段
- **THEN** 系统 SHALL 调用服务端阶段推进 API
- **AND** 成功后 SHALL 刷新 Workflow 状态

#### Scenario: 没有报告时阻止推进

- **WHEN** 当前不存在评估报告
- **THEN** 系统 SHALL 禁用进入修复阶段操作
