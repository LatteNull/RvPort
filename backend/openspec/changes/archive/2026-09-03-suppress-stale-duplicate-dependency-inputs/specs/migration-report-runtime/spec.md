## ADDED Requirements

### Requirement: 评估报告必须过滤过期依赖输入
迁移评估报告 readiness、输入预览和报告生成 SHALL 只消费当前源码版本下有效的 `DEPENDENCY_RESULT` 输入，避免历史依赖分析 run 的重复或过期 reference 进入当前报告。

#### Scenario: readiness 统计排除过期依赖输入
- **GIVEN** 当前源码版本存在旧依赖分析 run 的 `CONFIRMED` reference
- **AND** 同一源码版本存在更新的成功依赖分析 run
- **WHEN** 用户查询评估报告 readiness
- **THEN** readiness 的 confirmed 输入统计 MUST 排除旧 run 的过期依赖 reference
- **AND** readiness MUST 基于当前有效输入池返回统计

#### Scenario: 输入预览不展示过期依赖输入
- **GIVEN** 当前源码版本存在历史重复的 `gcc` dependency reference
- **WHEN** 用户查询评估报告输入预览
- **THEN** 输入预览 MUST NOT 同时展示多个语义重复的 `gcc` 依赖输入
- **AND** 输入预览 MUST 优先展示当前最新成功依赖分析 run 对应的输入

#### Scenario: 报告生成不消费旧 confirmed gcc
- **GIVEN** 旧依赖分析 run 中存在 `gcc` reference 且状态为 `CONFIRMED`
- **AND** 当前最新依赖分析 run 中对应 `gcc` reference 状态为 `CANDIDATE`
- **WHEN** 用户生成评估报告
- **THEN** 报告 MUST NOT 因旧 `CONFIRMED` reference 将 `gcc` 写入报告
- **AND** 报告 MUST 按当前最新 reference 状态决定是否纳入该依赖

#### Scenario: 历史报告详情继续使用快照
- **GIVEN** 用户查看已经生成的历史评估报告
- **WHEN** 当前输入池中的过期依赖 reference 已被清理或过滤
- **THEN** 历史报告详情 SHALL 继续显示报告生成时保存的 `report_inputs` 快照
- **AND** 后端 MUST NOT 因当前输入池过滤而改变历史报告内容
