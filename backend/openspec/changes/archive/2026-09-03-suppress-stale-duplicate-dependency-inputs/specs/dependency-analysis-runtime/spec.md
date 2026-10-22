## ADDED Requirements

### Requirement: 依赖分析同步必须只绑定本次最新结果
依赖分析成功完成后，系统 SHALL 使用本次成功 run 的 result item 重建当前源码版本的 `DEPENDENCY_RESULT` migration input reference，并 SHALL 避免历史 run 的同语义结果重新进入当前输入池。

#### Scenario: 成功重跑替换旧依赖输入
- **GIVEN** 同一项目和源码版本下存在旧依赖分析 run 的 `DEPENDENCY_RESULT` migration input reference
- **WHEN** 新的依赖分析 run 成功完成并写入结果项
- **THEN** 后端 MUST 删除当前项目、源码版本和 `DEPENDENCY_RESULT` 范围内的旧 reference
- **AND** 后端 MUST 只根据本次 run 的 result item 创建新的 reference

#### Scenario: 同一工具多来源结果只同步一条
- **GIVEN** 依赖提取过程从构建日志、compile database 或 strace 中识别到同一个工具 `gcc`
- **WHEN** 依赖分析结果同步到 migration input reference
- **THEN** 后端 MUST 只同步一条语义上的 `gcc` reference
- **AND** reference SHOULD 指向当前 run 中置信度最高或目标匹配信息最完整的 result item

#### Scenario: 显式历史查看仍可读取旧 run
- **GIVEN** 数据库中存在历史依赖分析 run 及其重复 result item
- **WHEN** 用户显式查询该历史 run 的依赖分析结果
- **THEN** 后端 SHALL 保留历史 run 的原始结果可审计
- **AND** 历史查看 MUST NOT 自动改变当前 migration input reference

#### Scenario: 新 run 失败不清空当前输入
- **GIVEN** 当前源码版本已有有效 `DEPENDENCY_RESULT` migration input reference
- **WHEN** 新的依赖分析 run 失败或取消
- **THEN** 后端 MUST 保留当前已有 reference
- **AND** 后端 MUST NOT 因失败 run 删除当前报告输入池
