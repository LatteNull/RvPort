## ADDED Requirements

### Requirement: Projector 必须阻止非 x86 噪声重新进入 Finding
V2 默认和显式 V1 Projector SHALL 只投影具有有效 Classification 的 Observation。标记为 foreign、not-architecture-related、duplicate-child 或缺少候选资格的对象 MUST NOT 生成 Finding；真正 unknown candidate SHALL 继续使用现有低严重度、非阻断、非操作语义。两种版本 MUST NOT 为此新增顶层结果结构、第二个主文件或不一致的 HTML/log 过滤。

#### Scenario: zlib ARMCRC32 与通用属性
- **WHEN** staged snapshots 包含九条已证明属于 ARMCRC32 分支的 asm Evidence 和 `no_sanitize("memory")` attribute Evidence
- **THEN** V2 与 V1 均不得为这些 Evidence 生成 x86 Finding
- **AND** JSON、HTML、log 和 summary 的 Finding 数量 SHALL 一致

#### Scenario: 真正未知的汇编候选
- **WHEN** Classification 为有效 `unknown / candidate-evidence-not-sufficient` 且引用一个完整最外层 asm occurrence
- **THEN** Projector SHALL 生成至多一个低严重度、非阻断、非操作候选 Finding
- **AND** evidence chain/trace SHALL 指向完整 asm span 而不是 qualifier 或 operand 子节点

#### Scenario: 防御性收到 foreign Classification
- **WHEN** Projector 收到违反分类合同的 foreign 或无架构语义 Classification
- **THEN** Projector SHALL 产生结构化 Diagnostic 并拒绝发布对应 Finding
- **AND** 它 MUST NOT 静默把该对象改写为 candidate 或 confirmed x86 finding

### Requirement: 候选过滤必须保持版本化输出兼容
候选噪声修复 SHALL 保持默认 Schema V2、显式 V1、现有必需字段、artifact 名称和旧消费者读取能力。被移除的重复/foreign/通用属性 Finding 数量变化 SHALL 作为 approved correctness correction 固化在 golden；合法 x86 Finding 的字段类型、证据引用和稳定排序 MUST 保持兼容。

#### Scenario: 默认和显式版本回归
- **WHEN** 同一 zlib/AVX fixture 分别使用默认、显式 V2 和显式 V1 扫描
- **THEN** 默认与显式 V2 SHALL 生成 Schema 2.0，显式 V1 SHALL 生成 Schema 1.0，且每次只发布固定三类 artifact
- **AND** 三种结果均不得恢复 ARM asm 重复候选或通用 attribute 候选

#### Scenario: 既有 x86 finding
- **WHEN** fixture 包含知识支持的 x86 intrinsic、asm、target feature 或架构条件
- **THEN** V2/V1 SHALL 继续投影现有兼容字段、状态、严重度和 evidence trace
- **AND** 候选去重不得合并不同 source span 或不同 configuration 的合法 occurrence

### Requirement: 候选投影修复必须通过独立容器回归门禁
修改的 V2/V1 projection policy、mapper、renderer 或 summary 模块 SHALL 具有逐模块隔离单元测试并在 `kb-scanner-test` 达到 90% line / 80% branch；此外 SHALL 运行 zlib ARMCRC32、真正未知 asm、AVX、架构枚举、原生崩溃和全量兼容回归。

#### Scenario: 固定 zlib 数量上限
- **WHEN** 容器扫描固定 zlib ARMCRC32 回归输入
- **THEN** 九条 ARM asm 和一个 `no_sanitize` MUST 产生零个对应 x86 findings，真实 x86 mixed condition SHALL 保留既有 inactive 结果
- **AND** Evidence、Observation、Classification 与 Finding 数量上限 SHALL 被明确断言，防止父子节点爆炸恢复
