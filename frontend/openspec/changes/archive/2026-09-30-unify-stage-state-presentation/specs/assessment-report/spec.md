## MODIFIED Requirements

### Requirement: 当前报告生成与历史

评估报告 SHALL 使用 `report` readiness 的 `KB_SCAN`、`DEPENDENCY_ANALYSIS` 和 `INCLUDED_FINDINGS` 条件及领域 latest，区分当前报告、旧 Context 报告和尚未生成。

#### Scenario: 生成报告

- **WHEN** 报告前置条件满足且用户确认生成
- **THEN** 页面 SHALL 创建报告任务并通过项目事件刷新执行状态和报告结果
- **AND** 前置条件不满足或查询失败 SHALL 分别展示业务恢复或请求重试

#### Scenario: 浏览历史报告

- **WHEN** 用户选择历史报告
- **THEN** 页面 SHALL 展示该报告绑定的模块、文件、Finding 与源码上下文，不把历史报告当作当前 Context 结果

#### Scenario: 从当前概览进入历史

- **WHEN** 当前报告加载失败、受阻、执行中或已有结果
- **THEN** frontend SHALL 保留标题区历史入口，独立查询项目范围的报告列表
- **AND** 选择记录 SHALL 通过记录 ID 读取详情，沿用模块、文件、问题阅读路径，返回历史后再返回当前概览
- **AND** 历史详情 SHALL NOT 提供生成或重新生成入口
