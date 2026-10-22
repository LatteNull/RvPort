## ADDED Requirements

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
