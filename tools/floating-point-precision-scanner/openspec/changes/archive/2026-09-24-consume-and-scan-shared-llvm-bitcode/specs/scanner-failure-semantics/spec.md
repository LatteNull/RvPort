## MODIFIED Requirements

### Requirement: 输入错误在分析前失败
扫描器 SHALL 在启动分析前验证 scan schema、源码和 artifact 路径边界、profile、规则配置、抑制语法、资源预算、artifact-set manifest schema/摘要以及 source revision、compile database、context、target/ABI 的跨输入一致性。输入错误或确定冲突 MUST 聚合为结构化诊断并返回 `invalid_request`；不得启动 Clang/LLVM worker或创建看似完整的空结果。共享 artifact 尚未就绪属于可重试外部依赖失败，不得误分类为 schema 输入错误。

#### Scenario: 项目根或 artifact root 越界
- **WHEN** 源码、manifest、BC 或 sidecar 路径解析后位于其允许根之外
- **THEN** 扫描器拒绝请求或对应 artifact，返回路径越界诊断且不读取越界文件

#### Scenario: 多个配置错误
- **WHEN** 请求同时包含无效 profile、负资源预算和未知规则 code
- **THEN** 扫描器在安全可行时一次返回全部配置诊断，状态为 `invalid_request`

#### Scenario: 没有 C/C++ 输入
- **WHEN** 输入选择器解析后不存在任何 C 或 C++ 翻译单元
- **THEN** 扫描器返回 `invalid_request` 和 `no_supported_translation_units` 诊断，不尝试分析其他源语言或孤立 BC

#### Scenario: source revision 与 artifact-set 冲突
- **WHEN** 两个输入包含完整但不同的 source revision 或 compile database SHA-256
- **THEN** 扫描器返回 `invalid_request` 和跨输入冲突诊断，不启动任何 facts 提取

### Requirement: 翻译单元失败产生保守的部分结果
当部分翻译单元因 AST 解析、缺失头文件、artifact 缺失/损坏、LLVM 不兼容、verifier/worker 失败、不支持语义或必需 evidence 无法绑定而失败时，扫描器 SHALL 保留其他成功翻译单元的 source facts、IR facts 和 evidence，状态为 `partial`，并分别公开各层 planned、completed、failed 和 unknown 分母。任一失败范围 MUST NOT 被解释为无 finding、无浮点操作或不受架构影响。

#### Scenario: 单个 AST 翻译单元解析失败
- **WHEN** 十个计划翻译单元中九个 source facts 成功、一个因缺失头文件失败
- **THEN** 扫描器保留九个单元事实，状态为 `partial`，并为失败单元输出包含阶段和原因的诊断

#### Scenario: 单个 BC verifier 失败
- **WHEN** source facts 全部成功但一个必需 BC 成员 verifier 失败
- **THEN** 成功的 source/IR facts 被保留，IR failed 分母增加且整体状态至少为 `partial`

#### Scenario: 所有必需事实提取失败
- **WHEN** 没有任何计划翻译单元产生请求所需的可用 source/IR 事实
- **THEN** 扫描器状态为 `failed` 而非 `partial`，且摘要不会声明工程无浮点风险

### Requirement: 资源预算耗尽可区分
扫描器 SHALL 支持 wall time、CPU、内存、文件数、artifact/BC 总字节、单 BC 字节、worker 输出、IR facts、evidence candidates 和诊断数预算。预算耗尽时 MUST 停止新增工作、终止或隔离受影响 worker、完成可安全落盘的已有结果，并以 `budget_exceeded` 诊断说明具体预算、已用值、profile/TU 和未分析范围；存在可用结果时状态为 `partial`，否则为 `failed`。

#### Scenario: 达到翻译单元时间预算
- **WHEN** 分析在部分翻译单元完成后达到请求 wall time 限制
- **THEN** 扫描器发布确定的部分结果与未完成清单，返回退出码 `4`

#### Scenario: BC 总字节超过预算
- **WHEN** manifest 声明的必需 BC 总大小超过请求允许值
- **THEN** 扫描器在读取 BC 前拒绝新增 worker 工作，并公开受影响成员和预算差额

### Requirement: 诊断必须可操作且双语
每条诊断 SHALL 包含 `diagnostic_code`、`stage`、`severity`、中文与英文消息、可选规范化源码或 artifact 身份、可重试性和建议动作。共享制品未就绪、摘要不符、LLVM 版本不兼容、verifier 失败、debug/source mapping 不足等 MUST 使用不同稳定 code；相同根因的大量重复诊断 MUST 被聚合，并保留出现次数、受影响 profile/TU 和代表性位置或 artifact key。

#### Scenario: 重复缺失同一系统头文件
- **WHEN** 多个翻译单元因同一缺失头文件失败
- **THEN** 扫描器输出聚合诊断、受影响数量和代表位置，而不是无上限重复消息

#### Scenario: artifact-set 正在生成
- **WHEN** 共享 artifact 状态为 `MISSING`、`QUEUED` 或 `GENERATING`
- **THEN** 扫描器输出 `artifact_not_ready` 双语诊断、`retryable=true` 和 artifact-set 身份，不在诊断中暴露对象存储凭据或临时路径

## ADDED Requirements

### Requirement: 共享制品失败与 x86 构建结果必须分离
扫描器 SHALL 将 artifact 未就绪、损坏或 LLVM 提取失败描述为分析输入/执行失败，不得改写或推断上游 x86 构建状态。结果 MAY 引用 build run identity，但 MUST NOT 将“BC 失败”等价为“项目构建失败”。

#### Scenario: x86 构建成功但 BC 成员损坏
- **WHEN** manifest 引用成功 build run，而一个 BC 文件摘要不符
- **THEN** 扫描结果报告该 artifact 分析失败，且不声称上游 x86 构建失败
