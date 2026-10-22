## ADDED Requirements

### Requirement: 迁移报告必须支持浮点和内存序 Finding
迁移报告 SHALL 消费当前源码版本已确认的 `FLOATING_POINT_FINDING` 与 `MEMORY_ORDER_FINDING` reference，并 SHALL 将其作为代码 Finding 组织到模块、文件、问题类型和行号层级。

#### Scenario: 组织浮点 Finding
- **WHEN** 报告输入包含已确认浮点 Finding
- **THEN** 报告 SHALL 展示规则、风险、影响、建议、测试建议、validation plan 和源码位置
- **AND** 多 occurrence SHALL 能在文件视角中高亮

#### Scenario: 组织内存序 Finding
- **WHEN** 报告输入包含已确认内存序 Finding
- **THEN** 报告 SHALL 展示并发问题、风险、置信度、同步缺口、建议、假设、限制和证据断点
- **AND** MUST 区分 formal risk 与 source candidate

#### Scenario: Finding 没有位置
- **WHEN** 已确认 Finding 不具有可信文件位置
- **THEN** 报告 SHALL 将其放入未定位分组
- **AND** 报告生成 MUST NOT 因缺少位置失败

### Requirement: 报告摘要必须计入专项分析风险
报告 SHALL 将两类已确认 Finding 计入总问题数、高风险数量、风险分布、模块/文件统计、优先处理项和预计工作量。

#### Scenario: 统计严重专项 Finding
- **WHEN** 报告包含 CRITICAL 或 HIGH 浮点/内存序 Finding
- **THEN** 高风险数量 SHALL 包含这些 Finding
- **AND** 主要风险 SHALL 能引用其双语标题与建议

#### Scenario: PARTIAL 证据提示
- **WHEN** 已确认 Finding 或其来源运行为 PARTIAL、unknown 或 source candidate
- **THEN** 报告 SHALL 显示证据限制和人工确认提示
- **AND** MUST NOT 把不确定结论描述为确定缺陷

### Requirement: 报告 JSON 与 HTML 必须共享专项分析口径
JSON 和 HTML 报告 SHALL 使用同一输入快照和聚合数据，且 SHALL 保留专项分析来源类型以供前端分组和报告比较。

#### Scenario: 生成双格式报告
- **WHEN** 报告包含任一专项分析 Finding
- **THEN** JSON 与 HTML 的数量、风险、模块、文件和 Finding ID SHALL 一致
- **AND** 两种格式 MUST NOT 暴露工具工作目录或对象存储内部信息
