## MODIFIED Requirements

### Requirement: Evidence Graph 必须产生稳定且引用有效的实体与关系
Graph Analyzer SHALL 为 project、source file、macro definition、macro invocation、condition group、branch、symbol/call site、implementation、architecture selector、build variable、source set、directory、compile/link argument、dependency、target、package 和 package section 建立确定性 Entity，并 SHALL 产生 `defines`、`includes`、`invokes_macro`、`expands_to`、`calls`、`has_branch`、`guarded_by`、`depends_on`、`selects`、`excludes`、`adds_argument`、`requires`、`produces`、`alternative_to` 与 `reachable_from` Relation；所有端点和 Evidence 引用 MUST 存在于同一分析快照。

#### Scenario: 相同输入重复分析
- **WHEN** 使用相同 scanner/knowledge 版本、ScanContext、源码和构建输入重复运行组合 Graph Analyzer
- **THEN** Entity、Relation、ProofPath 的 ID 与排序 SHALL 完全一致
- **AND** 身份材料 MUST NOT 包含机器绝对路径、随机值、对象地址或遍历时序

#### Scenario: 关系引用未知端点
- **WHEN** Relation builder 尝试建立含未知 Entity 或 Evidence ID 的源码或构建关系
- **THEN** Analyzer SHALL 拒绝该关系并返回 failed Diagnostic
- **AND** 无效引用 MUST NOT 进入 AnalysisSnapshot

#### Scenario: 构建项关联现有源码实体
- **WHEN** build Evidence 中规范化的源码路径匹配 C/C++ Frontend 已注册的 source file Entity
- **THEN** Analyzer SHALL 复用该 source file Entity 建立 target selection 关系
- **AND** scanner MUST NOT 因 producer 不同而创建语义重复的源码实体

### Requirement: Evidence Graph 不得承担构建选择和最终分类职责
Evidence Graph/GraphStore SHALL 只存储和查询 scanner-owned 静态证据关系，不得自行求值 Make/Autoconf/CMake/Meson/RPM/test selection；专用 Build Selection Analyzer MAY 将有 provenance 的选择结果写入同一图，但 scanner MUST NOT 执行项目代码、compiler、配置、构建或测试，也 MUST NOT 在图层产生最终 blocking、severity 或 RISC-V readiness。

#### Scenario: Build Selection Analyzer 提供完整选择关系
- **WHEN** 专用 analyzer 证明某源码、参数或依赖对目标 RISC-V selected/inactive
- **THEN** GraphStore SHALL 保留 relation status、Evidence 和 proof sequence
- **AND** GraphStore MUST NOT 自行升级、覆盖或重新求值该状态

#### Scenario: 关系存在但目标选择仍未知
- **WHEN** x86 实现具有 include、macro、sibling 或部分 build relation 但缺少完整选择 proof
- **THEN** AnalysisSnapshot SHALL 保留关系并将目标可达性保持 unknown/partial
- **AND** Analyzer MUST NOT 猜测该实现会或不会进入 RISC-V 产物

#### Scenario: 项目包含可执行构建构造
- **WHEN** 输入需要执行 shell、Make、M4、CMake、RPM、plugin、response file 或项目测试才能消解
- **THEN** scanner SHALL 返回 unsupported/unknown Diagnostic
- **AND** scanner 和测试 MUST NOT 执行该构造
