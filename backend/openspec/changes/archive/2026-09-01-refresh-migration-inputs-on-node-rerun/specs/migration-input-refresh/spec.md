## ADDED Requirements

### Requirement: 节点重跑后刷新同来源迁移输入
系统 SHALL 在分析节点成功重跑后，以当前 `project_id`、`source_revision_id` 和 `source_type` 为范围替换该来源类型的迁移输入。

#### Scenario: 依赖分析成功重跑后旧依赖输入被清空
- **WHEN** 同一项目和源码版本下依赖分析重新运行成功
- **THEN** 系统 MUST 清空该项目、源码版本、`DEPENDENCY_RESULT` 来源类型下旧的迁移输入
- **AND** 系统 MUST 仅按本次最新依赖分析结果重新创建 `DEPENDENCY_RESULT` 迁移输入

#### Scenario: KB 扫描成功重跑后旧 KB 输入被清空
- **WHEN** 同一项目和源码版本下 KB 扫描重新运行成功
- **THEN** 系统 MUST 清空该项目、源码版本、`KB_FINDING` 来源类型下旧的迁移输入
- **AND** 系统 MUST 仅按本次最新 KB 扫描结果重新创建 `KB_FINDING` 迁移输入

### Requirement: 来源类型刷新必须相互隔离
系统 SHALL 只刷新本次节点对应来源类型的迁移输入，不得影响其他来源类型。

#### Scenario: 依赖分析重跑不影响 KB 输入
- **WHEN** 依赖分析成功重跑并刷新 `DEPENDENCY_RESULT` 迁移输入
- **THEN** 系统 MUST 保留同一项目和源码版本下 `KB_FINDING` 来源类型的迁移输入

#### Scenario: KB 扫描重跑不影响依赖输入
- **WHEN** KB 扫描成功重跑并刷新 `KB_FINDING` 迁移输入
- **THEN** 系统 MUST 保留同一项目和源码版本下 `DEPENDENCY_RESULT` 来源类型的迁移输入

### Requirement: 失败或取消的节点不得清空迁移输入
系统 SHALL 仅在节点结果成功落库后刷新迁移输入。

#### Scenario: 依赖分析失败时保留旧输入
- **WHEN** 依赖分析重跑失败
- **THEN** 系统 MUST 保留该项目和源码版本下已有的 `DEPENDENCY_RESULT` 迁移输入

#### Scenario: 依赖分析取消时保留旧输入
- **WHEN** 依赖分析重跑被取消
- **THEN** 系统 MUST 保留该项目和源码版本下已有的 `DEPENDENCY_RESULT` 迁移输入

### Requirement: 重建输入使用默认风险确认策略
系统 SHALL 在重建迁移输入时继续使用现有风险策略，低风险默认为候选，其他风险等级默认为确认。

#### Scenario: 低风险结果默认为候选
- **WHEN** 节点结果的检测风险等级为 `LOW`
- **THEN** 系统 MUST 将对应迁移输入状态设置为 `CANDIDATE`

#### Scenario: 非低风险结果默认为确认
- **WHEN** 节点结果的检测风险等级为 `CRITICAL`、`HIGH`、`MEDIUM`、`INFO` 或 `COMMENT`
- **THEN** 系统 MUST 将对应迁移输入状态设置为 `CONFIRMED`

#### Scenario: 重跑后不继承旧人工排除状态
- **GIVEN** 同一项目、源码版本和来源类型下存在用户手动排除过的旧迁移输入
- **WHEN** 该来源类型对应节点成功重跑并重新同步本次结果
- **THEN** 系统 MUST 清空旧迁移输入并重新创建本次迁移输入
- **AND** 系统 MUST NOT 根据旧迁移输入的 `EXCLUDED` 状态自动排除本次新结果
- **AND** 本次新结果 MUST 继续按默认风险确认策略设置状态

### Requirement: 历史报告输入快照保持不变
系统 SHALL 保持已生成报告的 `report_inputs` 快照不可变。

#### Scenario: 刷新当前输入不修改历史报告
- **WHEN** 节点成功重跑并刷新当前迁移输入
- **THEN** 系统 MUST NOT 修改已生成报告中的 `report_inputs`
- **AND** 新报告 MUST 基于刷新后的当前迁移输入生成

### Requirement: 无确认输入时生成成功空报告
系统 SHALL 允许当前源码版本没有 `CONFIRMED` 迁移输入时生成评估报告，并将该报告视为没有待处理项的成功报告。

#### Scenario: 所有输入被撤回后生成完美报告
- **GIVEN** 当前源码版本下不存在 `CONFIRMED` 迁移输入
- **WHEN** 用户生成评估报告
- **THEN** 系统 MUST 将报告任务标记为成功
- **AND** 系统 MUST 写入空的 `report_inputs` 快照
- **AND** 系统 MUST 将报告摘要中的输入数量、高风险数量和预计工作量设置为 0
- **AND** 系统 MUST 将总体风险设置为 `INFO`

#### Scenario: 无确认输入不阻塞报告 readiness
- **GIVEN** 项目存在可用源码版本
- **AND** 当前源码版本下不存在 `CONFIRMED` 迁移输入
- **WHEN** 前端查询评估报告 readiness
- **THEN** 系统 MUST 返回允许生成报告
- **AND** 系统 MUST NOT 返回 `REPORT_NO_CONFIRMED_INPUTS` 阻塞项
