## ADDED Requirements

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
