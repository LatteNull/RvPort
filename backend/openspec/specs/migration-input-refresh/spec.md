## Purpose

规范分析节点重跑后当前迁移输入的刷新语义，确保同一源码版本下的旧节点输入不会污染新结果，并定义评估报告在无有效输入时的生成规则。
## Requirements
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

### Requirement: 当前依赖迁移输入必须抑制历史重复项
系统 SHALL 保证当前源码版本下的 `DEPENDENCY_RESULT` 迁移输入只代表当前有效依赖分析结果，不得让历史重复依赖输入继续污染当前输入池。

#### Scenario: 历史 gcc confirmed 不进入当前输入池
- **GIVEN** 同一项目和源码版本下存在旧依赖分析 run 产生的 `gcc` migration input reference
- **AND** 旧 reference 状态为 `CONFIRMED`
- **WHEN** 同一项目和源码版本下存在更新的成功依赖分析 run
- **THEN** 当前输入池 MUST NOT 默认消费旧 run 的 `gcc` reference
- **AND** 当前输入池 MUST 只保留或展示最新成功依赖分析 run 对应的 `gcc` reference

#### Scenario: 多来源工具项按语义收敛
- **GIVEN** 同一源码版本下存在 `build:gcc`、`compile-db:gcc`、`execve-summary:gcc` 或 `execve:gcc` 等多来源工具 reference
- **WHEN** 后端清理或读取当前 `DEPENDENCY_RESULT` 输入池
- **THEN** 系统 MUST 将这些同名工具视为同一语义依赖
- **AND** 当前输入池 MUST NOT 同时返回多条 `gcc` 工具输入

#### Scenario: 不合并不同库依赖
- **GIVEN** 同一源码版本下存在 `libgcc.so` 和 `libgcc_s.so` 两条依赖输入
- **WHEN** 后端清理或读取当前 `DEPENDENCY_RESULT` 输入池
- **THEN** 系统 MUST 保留二者作为不同依赖
- **AND** 系统 MUST NOT 仅因名称包含 `gcc` 就合并不同库文件

### Requirement: 历史重复清理不得修改历史报告快照
系统 SHALL 允许清理当前迁移输入中的历史重复 `DEPENDENCY_RESULT` 引用，但 MUST 保持已生成报告输入快照不可变。

#### Scenario: 清理当前输入不改历史报告
- **GIVEN** 某个历史评估报告的 `report_inputs` 快照包含旧依赖输入
- **WHEN** 后端清理当前 `migration_input_refs` 中的重复依赖输入
- **THEN** 已生成报告详情和下载内容 MUST 保持原快照内容
- **AND** 清理操作 MUST NOT 更新、删除或重写已有 `report_inputs`

#### Scenario: 清理后新报告使用收敛输入
- **GIVEN** 当前源码版本存在重复的 `DEPENDENCY_RESULT` migration input reference
- **WHEN** 清理完成后用户生成新的评估报告
- **THEN** 新报告 MUST 基于清理后的当前输入池生成
- **AND** 新报告 MUST NOT 包含被清理或被判定为过期的重复依赖输入

### Requirement: 专项分析重跑必须刷新同类当前输入
系统 SHALL 在当前源码版本的专项分析结果成功并完整落库后，仅清空并重建对应 source type 的当前 migration input references。

#### Scenario: 浮点分析重跑
- **WHEN** 同一项目和源码版本的新浮点运行成功或发布可查询的 PARTIAL 结果
- **THEN** 系统 SHALL 清空旧 `FLOATING_POINT_FINDING` 当前 references
- **AND** SHALL 只根据本次 Finding 重建 references

#### Scenario: 内存序分析重跑
- **WHEN** 同一项目和源码版本的新内存序运行成功或发布可查询的 PARTIAL 结果
- **THEN** 系统 SHALL 清空旧 `MEMORY_ORDER_FINDING` 当前 references
- **AND** SHALL 只根据本次 Finding 和 source candidates 重建 references

#### Scenario: 来源类型隔离
- **WHEN** 任一专项分析刷新当前 references
- **THEN** 系统 MUST NOT 修改 KB、依赖或另一专项分析来源的 references

### Requirement: 无效结果不得清空旧专项输入
系统 SHALL 仅在新结果完成 schema 校验、逐条导入和制品保存后刷新当前 references。

#### Scenario: 工具执行失败
- **WHEN** 新运行失败、取消且没有可发布结果、结果损坏或事务回滚
- **THEN** 系统 MUST 保留旧的同类当前 references

#### Scenario: 不继承旧人工排除
- **WHEN** 新运行成功并重建同类 references
- **THEN** 新 references SHALL 按全局风险默认策略初始化
- **AND** MUST NOT 自动继承旧 Finding 的 EXCLUDED 状态

### Requirement: 历史运行与报告快照不得被刷新修改
当前 migration input 刷新 SHALL 不修改历史分析运行、历史 Finding 或已有报告输入快照。

#### Scenario: 重跑后查看历史报告
- **WHEN** 当前输入已被新运行替换
- **THEN** 历史报告 SHALL 继续显示生成时固定的专项 Finding 快照
- **AND** 历史运行详情 SHALL 保持可查询
