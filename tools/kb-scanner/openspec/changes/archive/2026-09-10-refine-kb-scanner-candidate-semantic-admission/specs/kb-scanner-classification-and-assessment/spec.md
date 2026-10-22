## MODIFIED Requirements

### Requirement: 架构枚举候选必须按关系证明进行保守分类
Classifier SHALL 结合 enum candidate Observation、member binding、selection condition、下游 x86 dependency 和目标可达性 proof 决定影响；名称命中本身 SHALL 保持 `unknown`，只有完整关系证明才可升级。Assessor SHALL 将 unresolved/ambiguous enum selection 计入输入完整性，MUST NOT 因零 blocker 或零其他 Finding 推导 RISC-V ready。

#### Scenario: 孤立架构枚举成员
- **WHEN** enum member 名称匹配 x86 architecture/feature knowledge但没有 reference 或 guarded dependency proof
- **THEN** Classification SHALL 为 unknown、non-blocking、non-actionable，并使用稳定的 candidate-insufficient reason
- **AND** Finding SHALL 仍可展示声明位置和 Knowledge provenance

#### Scenario: 枚举条件保护真实 x86 依赖但选择未知
- **WHEN** complete proof 表明 enum condition 保护 knowledge-backed x86 dependency，但没有证明 RISC-V 选择或排除该条件
- **THEN** Classification SHALL 为 actionable non-blocking，并说明目标选择仍未知
- **AND** 它 MUST NOT 声称该分支已被 RISC-V 构建选中

#### Scenario: RISC-V 选择 x86 枚举分支
- **WHEN** complete target/build proof 连接 RISC-V selector 到保护 x86 dependency 的 enum member condition
- **THEN** Classification SHALL 为 blocking issue，并引用完整 selection 与 dependency proof
- **AND** blocker MUST NOT 仅由 enum 名称或模板声明产生

#### Scenario: RISC-V 排除 x86 枚举分支
- **WHEN** complete proof 表明 RISC-V 选择 RISC-V/generic/portable sibling 并排除 x86 enum branch
- **THEN** Classification SHALL 为 guarded inactive、non-blocking、non-actionable
- **AND** 原 x86 Evidence 和排除它的 condition/alternative chain SHALL 保留

#### Scenario: 枚举关系歧义或输入不完整
- **WHEN** member binding、condition、downstream dependency 或 selection proof 为 ambiguous、partial、dynamic 或 truncated
- **THEN** Classification 与 Assessment SHALL 保持 unknown/provisional 并保留 blocking dimension/reason
- **AND** 系统 MUST NOT 选择最乐观分支或从没有命中推导 ready

#### Scenario: 数据角色证明驱动排除
- **WHEN** 候选具有满足同 fact/subject/configuration/occurrence 合同的完整数据角色 proof 且没有执行角色冲突
- **THEN** Classifier SHALL 保留 Observation 但省略其迁移 Classification，记录 INFO 排除审计
- **AND** 没有证明的候选 MUST 保持 unknown 或已有执行 proof 结论，不强制过滤或强制报告全部候选

#### Scenario: Identifier 未决完整性
- **WHEN** 非 enum 的 candidate 被分类为 unknown
- **THEN** Classification completeness SHALL 同样为 unknown
- **AND** Assessment MUST NOT 从过滤后计数或缺少 RISC-V 数据格式名称推导 ready 或迁移缺口
