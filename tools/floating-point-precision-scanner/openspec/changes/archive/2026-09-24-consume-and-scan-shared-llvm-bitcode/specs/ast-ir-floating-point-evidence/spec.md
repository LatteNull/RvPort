## ADDED Requirements

### Requirement: AST、IR 和融合证据必须使用独立文档
扫描器 SHALL 分别发布或内部验证 `FloatingPointFactBundle`、`LLVMFloatingPointFactBundle` 和 `FloatingPointEvidenceBundle`。融合 bundle MUST 引用 source/IR bundle 的 kind、schema version、稳定身份和 semantic digest，并 MUST NOT 复制后修改原始事实或把 IR 观察伪装成源码语义。

#### Scenario: source 和 IR bundle 均有效
- **WHEN** 同一 physical TU/context 的 source 与 IR bundle 均通过 schema 和 digest 校验
- **THEN** 融合层创建引用两者不可变身份的 evidence bundle

#### Scenario: 引用 digest 不匹配
- **WHEN** evidence 输入声明的 source 或 IR digest 与实际 bundle 不一致
- **THEN** 融合被拒绝且不发布任何 binding

### Requirement: 绑定必须建立在共同翻译单元和明确 provenance 上
融合层 SHALL 首先验证 physical TU、context、source revision、language、target/profile 和 compile database identity。绑定只可依据已验证的显式 sidecar，或同一 TU/context 内唯一的规范化函数/符号身份、debug location、inline chain 与 AST spelling/expansion range 组合；函数名、demangled 文本或源码字符串相似度 MUST NOT 单独建立确定性关系。

#### Scenario: sidecar 提供有效显式绑定
- **WHEN** sidecar schema、摘要、TU/context 和两端 fact refs 全部有效
- **THEN** evidence 记录 `method=explicit-sidecar`、完整 provenance 和对应 source/IR refs

#### Scenario: 唯一结构化位置匹配
- **WHEN** 同一函数和 inline scope 内只有一个 AST range 与一个 IR debug range 满足规范化包含关系
- **THEN** evidence 可以记录可复现的 derived binding，并明确区别于 producer 显式绑定

#### Scenario: 只有函数名称相同
- **WHEN** source 与 IR 只有相同函数名而缺少可验证位置、符号身份或 sidecar
- **THEN** 不创建确定性 binding，并记录关联证据不足

### Requirement: 证据关系必须支持多对多和优化变换
`FloatingPointEvidenceBundle` SHALL 支持一个 source fact 关联多个 IR facts、多个 source facts 融合为一个 IR fact，以及 source/IR fact 无对应方。每条关系 MUST 记录 relation kind、method、source refs、IR refs、profile、provenance 和 ambiguity 状态，且不得强制一对一丢失 FMA、内联、常量折叠或拆分 lowering 信息。

#### Scenario: 乘法加法融合为 FMA
- **WHEN** source bundle 含乘法与加法两个事实，而 build-faithful IR 含一个已验证 FMA fact
- **THEN** evidence 使用一个多源到单 IR 的 `fused-lowering` 关系保留三个事实引用

#### Scenario: 一个表达式降低为多个指令
- **WHEN** 单个 source 转换或调用产生多个具有共同 debug provenance 的 IR facts
- **THEN** evidence 以单源到多 IR 关系保存全部成员且排序确定

#### Scenario: source 表达式被优化删除
- **WHEN** build-faithful IR 中没有足够证据对应一个 source fact
- **THEN** source fact 保留为 unbound/unknown，不得仅因未匹配就断言其一定被优化删除

### Requirement: 歧义和缺失映射必须显式传播
当多个候选具有相同位置、宏 spelling/expansion 冲突、inline chain 不完整、debug metadata 缺失、sidecar 引用不存在或绑定预算耗尽时，融合层 SHALL 产生带候选数量、原因和 frontier 的 `ambiguous`/`unavailable` 记录。若请求要求完整 source mapping，任何阻断性未绑定事实 MUST 使对应 TU 或整体状态至少为 `partial`。

#### Scenario: 同一行存在多个候选表达式
- **WHEN** 两个 AST 浮点表达式和两个 IR facts 只共享相同行号且无法由列、range、scope 或 sidecar 唯一区分
- **THEN** 四个事实均保留，binding 标记 ambiguous，不任意配对

#### Scenario: 宏 spelling 与 expansion 指向不同文件
- **WHEN** AST 与 IR location 只匹配其中一个位置但宏 provenance 不完整
- **THEN** 融合层保留两个位置并标记所缺 provenance，不伪造 exact binding

### Requirement: evidence 身份、排序和摘要必须确定
binding/evidence ID SHALL 基于 source/IR bundle digest、规范化 relation、排序后的 refs、method 和语义 provenance 生成。输入 materialization 根、进程 ID、并发完成顺序和绝对路径 MUST NOT 影响 evidence ID、顺序或 semantic digest。

#### Scenario: 相同 source/IR facts 重复融合
- **WHEN** 相同 bundle 和 sidecar 在不同本地目录与不同处理顺序下融合
- **THEN** bindings、unknowns、排序、evidence ID 和 semantic digest 完全相同

#### Scenario: binding method 发生变化
- **WHEN** 原 derived binding 后续由经过验证的显式 sidecar 替代
- **THEN** evidence provenance 和 semantic digest 发生变化并可审计
