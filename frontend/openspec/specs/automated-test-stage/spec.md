## Purpose

定义项目流水线自动化测试阶段的前置构建条件、双端测试批次、结果对比、日志和历史记录的可观察前端行为。

## Requirements

### Requirement: 自动化测试节点可从构建后阶段进入

系统 SHALL 将“自动化测试”作为项目流水线中构建后的可操作节点，并在用户打开节点时显示专用的自动化测试 Drawer。

#### Scenario: 从成功构建后打开自动化测试

- **WHEN** 用户在项目流水线中选择“自动化测试”节点
- **THEN** 系统显示自动化测试 Drawer，而不是通用占位 Drawer

### Requirement: 测试前置条件由当前源码的成功构建对派生

系统 SHALL 使用 `test` readiness 的 `BUILD_VALIDATION` 条件作为服务端门禁，并优先根据其 details 中的双端构建 ID 读取测试输入；未提供 ID 时从当前源码的有效成功双端构建中解析。输入不可读取时不得提交测试。系统 MUST 展示每侧的环境名称、构建状态和构建目录，且用户 MUST NOT 在此阶段选择环境或任意构建记录。

#### Scenario: 两侧构建均可用于测试

- **WHEN** 当前源码在 x86 和 RISC-V 中均有有效的成功构建
- **THEN** 系统展示两侧构建前置条件并启用运行自动化测试操作

#### Scenario: 任一侧缺少有效构建

- **WHEN** 当前源码在任一环境没有有效的成功构建或构建已不对应当前环境配置
- **THEN** 系统禁用运行自动化测试操作并明确指出需要重新构建的环境

### Requirement: 共享测试配置发起成对测试批次

系统 SHALL 让用户配置一套共享测试命令、超时和环境变量，并使用同一个新生成的 `testBatchId` 提交两个测试请求。每个请求 MUST 使用相应前置构建的 `buildRunId`、明确的源端或目标端批次角色及该侧构建目录，且 MUST NOT 发送 `environmentId`。

#### Scenario: 成功提交两个环境的测试

- **WHEN** 用户在两侧前置条件均满足时提交有效的共享测试配置
- **THEN** 系统为 x86 和 RISC-V 各创建一个属于同一批次的测试运行，并由项目事件刷新运行状态和历史

#### Scenario: 仅一侧测试创建成功

- **WHEN** 成对提交中一个测试请求成功而另一个失败
- **THEN** 系统保留并展示已创建的测试运行、提示失败侧的原因，且不得将该批次显示为已比较

### Requirement: 独立展示两侧测试运行和日志

系统 SHALL 分别展示批次中 x86 与 RISC-V 测试运行的状态、退出码、通过/失败/跳过聚合计数、构建目录与环境配置是否仍为当前。当前结果卡片 SHALL 使用紧凑的纵向间距，并将日志与取消操作和统计信息放在同一内容行。运行中的测试 SHALL 提供取消操作。点击日志 SHALL 打开二级详情 Drawer，复用 task-log-viewer 展示可复制、可换行的任务日志。

#### Scenario: 查看某一环境的测试日志

- **WHEN** 用户查看某侧当前测试结果
- **THEN** 日志操作与通过、失败、跳过统计位于同一内容行
- **AND WHEN** 用户点击日志
- **THEN** 系统在二级 Drawer 中展示该任务概要和按时间排列的日志内容

#### Scenario: 取消运行中的测试

- **WHEN** 用户取消仍在排队或执行中的某侧测试
- **THEN** 系统请求取消对应任务并由项目事件刷新该测试运行的状态

### Requirement: 自动呈现批次比较状态和结论

系统 SHALL 依据 `testBatchId` 查询并展示后端自动生成的测试比较。两侧测试未均为终态时系统 MUST 显示等待状态；比较运行中时 MUST 显示进行中；比较完成或不可用时 MUST 显示后端返回的结论、风险/摘要或不可用原因。前端 SHALL 将 `EQUIVALENT`、`DIFFERENT_ACCEPTABLE`、`DIFFERENT_BLOCKING` 和 `INCONCLUSIVE` 映射为中文标签、标题与对应语义色，不得直接展示后端英文枚举。系统 MUST NOT 提供手动发起比较操作。

#### Scenario: 两侧完成后显示自动比较结果

- **WHEN** 同一批次的源端和目标端测试均已结束且后端比较完成
- **THEN** 系统显示该批次的中文比较结论和风险信息

#### Scenario: 比较无法生成

- **WHEN** 后端将该批次比较标记为不可用或返回不可用原因
- **THEN** 系统展示不可用状态及原因，而不把它显示为测试失败

### Requirement: 可追溯自动化测试批次历史

系统 SHALL 在默认页将当前条件和配置与项目跨源码版本的批次记录并列展示。记录 SHALL 按批次关联两侧运行与比较状态，支持单侧日志与比较详情，并遵循 project-stage-runtime 的独立读取和聚合分页规则。

#### Scenario: 查看已完成的测试批次

- **WHEN** 用户浏览自动化测试 Drawer 的历史记录
- **THEN** 系统 SHALL 按服务端创建时间倒序展示批次及源码版本、两侧运行状态和比较状态，并可进入只读详情；接口未提供创建时间字段时不得伪造时间

### Requirement: 自动化测试必须以 latest 锚定当前批次

自动化测试 SHALL 使用 `test` readiness 的 `BUILD_VALIDATION` prerequisite 作为唯一门禁，`automated-tests/latest` 的 `CURRENT` 结果 SHALL 用于当前配置参考与记录补齐，不替代默认跨版本批次列表。

#### Scenario: latest 仅返回批次单侧结果

- **WHEN** backend latest 只包含当前批次的一侧运行
- **THEN** frontend SHALL 从项目测试记录聚合同一批次两侧结果
- **AND** List SHALL NOT 改变当前执行门禁

#### Scenario: 展示结果比较

- **WHEN** 当前或历史批次存在比较结果
- **THEN** 页面 SHALL 分层展示一致性状态、风险、摘要和处理建议
- **AND** 失败时 SHALL 提供按需日志入口，不得将 Agent 原始输出直接铺成业务摘要
