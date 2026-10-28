## ADDED Requirements

### Requirement: 归约规则必须按候选有界调度并隔离异常
运行时 SHALL 按稳定顺序分别评估归约候选，将 matched、notMatched、unknown 和 failed 计入各自 assessment。`max_rule_candidates`、`max_rule_assessments` 和证据引用上限 SHALL 在候选处理边界生效；MUST NOT 无界评估全部候选后再截断。候选级可分类异常 SHALL 仅影响当前候选；整份输入无效仍遵循输入层失败协议。

#### Scenario: 正常与异常候选并存
- **WHEN** 同一 TU 包含可确定命中、明确非命中、递推歧义以及可分类输入异常候选
- **THEN** 分别产生 matched、notMatched、unknown、failed，保留命中 Finding，诊断指向受影响范围且整体完整性按现有规则保守计算

#### Scenario: 候选数量超过预算
- **WHEN** 候选或 assessment 预算不足以处理全部归约
- **THEN** 按稳定候选顺序保留已完成结果，停止超预算评估，并以有界诊断/frontier 标明未评估范围和不完整状态，不视为安全

#### Scenario: 单候选引用超限
- **WHEN** 一个候选所需证据超过引用预算而其他候选未超限
- **THEN** 仅按既有预算语义降级该候选，其他候选继续评估，不通过混入或丢弃必要证据伪装完整判断

#### Scenario: 没有归约候选
- **WHEN** 输入中不存在受支持归约候选
- **THEN** 保留 `no_reduction` 的 notMatched 审计结果，不生成 Finding 或虚构候选

### Requirement: 归约候选身份与缓存必须反映独立语义
候选 scope 和结果身份 SHALL 基于规则版本、稳定 TU/编译上下文、函数/循环/表达式语义和本候选证据生成，不依赖绝对工作区、遍历序号、显示文本或无关候选。事实 mapper/schema 或 binding 语义变化时 SHALL 同步对应版本与缓存指纹，防止复用不满足当前身份/证据要求的中间结果。

#### Scenario: 重排与无关候选
- **WHEN** 输入 facts 顺序变化、相同事实重复出现，或增加一个不相关归约候选且预算充足
- **THEN** 已有候选的 scope、Finding ID、证据集合、状态和置信度保持一致，输出按稳定键排序

#### Scenario: 旧缓存与冷暖一致性
- **WHEN** 旧事实缓存不含当前所需的循环身份，或使用新版本执行冷/热缓存扫描
- **THEN** 旧缓存不作为满足新契约的命中使用，相同新版本语义输入的冷/热结果身份、状态、计数与摘要一致
