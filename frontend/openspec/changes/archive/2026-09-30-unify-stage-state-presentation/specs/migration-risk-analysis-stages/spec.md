## MODIFIED Requirements

### Requirement: 分析风险与完整性独立表达

前端 SHALL 分别展示执行状态、结果完整性及风险结论，并保留后端提供的未知、跳过、失败和源码证据。

#### Scenario: 当前前置条件阻塞且已有分析记录

- **WHEN** 当前前置条件未满足且项目已有分析记录
- **THEN** 最新分析入口 SHALL 优先展示当前阻塞原因与上游处理入口，不同时展示旧终态完整结果或重试操作；若真实任务仍在运行，SHALL 按 project-stage-runtime 保留辅助运行事实与日志入口
- **AND** SHALL 保留历史记录入口，历史详情按所选记录展示执行状态和日志，不受当前前置条件阻塞覆盖
- **AND** Workflow Drawer 与 Step Panel SHALL 使用相同状态优先级

#### Scenario: 返回部分分析结果

- **WHEN** 扫描结果包含 partial、unknown、skipped 或 failed 的分析范围
- **THEN** 页面 SHALL 显示已分析与未确定的范围，不将未知项隐藏为成功

#### Scenario: 没有风险发现

- **WHEN** 结果返回零 finding
- **THEN** 页面 SHALL 展示真实空结果与分析边界
- **AND** SHALL NOT 将零 finding 表达为全程序安全或迁移无风险

#### Scenario: 查看执行历史与源码证据

- **WHEN** 用户查看历史分析或风险详情
- **THEN** 页面 SHALL 显示后端给出的源码版本、新鲜度及证据
- **AND** SHALL 沿用阶段共享的日志、正文滚动及列表详情往返规则
