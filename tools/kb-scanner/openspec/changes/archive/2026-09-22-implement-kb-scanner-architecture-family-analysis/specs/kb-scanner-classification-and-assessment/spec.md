## ADDED Requirements

### Requirement: 路径家族候选不得独立改变迁移风险结论

Classifier 和 Assessor SHALL 保持路径角色提示与执行依赖证明分离。纯路径候选 MUST NOT 创建迁移 Classification、增加问题或阻断计数、证明 portability gap、撤销已有 blocker 或提升 readiness；已有 source/build proof 继续按既有规则分类。家族发现完整性 MUST NOT 替代功能或目标选择完整性。

#### Scenario: 已有 blocker 旁边出现 generic 文件

- **WHEN** selected x86 dependency 已有闭合阻断 proof，但同家族 generic 成员没有被证明选择或可替代
- **THEN** SHALL 保留原 blocker，候选信息仅作为待核查补充

#### Scenario: 路径-only 家族

- **WHEN** 只有 `foo_x86.cpp` 等路径提示，没有真实架构依赖事实
- **THEN** SHALL 不因路径创建新的迁移 Finding 或更高 readiness
- **AND** 家族仍 SHALL 在支持的结构化候选输出中可见

#### Scenario: 既有互斥排除证明完整

- **WHEN** 真实 proof 已证明目标选中通用路径并排除 x86 occurrence
- **THEN** SHALL 保持既有 inactive、非阻断结论，并可展示关联家族上下文
- **AND** 其他家族的 unknown 或裁剪 MUST NOT 抹掉此独立完整 proof
