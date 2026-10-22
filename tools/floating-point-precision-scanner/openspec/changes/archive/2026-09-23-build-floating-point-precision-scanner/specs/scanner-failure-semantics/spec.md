## ADDED Requirements

### Requirement: 输入错误在分析前失败
扫描器 SHALL 在启动分析前验证 schema、路径边界、profile、规则配置、抑制语法与资源预算。输入错误 MUST 聚合为结构化诊断并返回 `invalid_request`；不得创建看似完整的空结果。

#### Scenario: 项目根越界
- **WHEN** 输入文件或编译数据库解析后位于允许的项目根之外，且未显式授权该路径
- **THEN** 扫描器拒绝请求，返回路径越界诊断且不读取该文件

#### Scenario: 多个配置错误
- **WHEN** 请求同时包含无效 profile、负资源预算和未知规则 code
- **THEN** 扫描器在安全可行时一次返回全部配置诊断，状态为 `invalid_request`

#### Scenario: 没有 C/C++ 输入
- **WHEN** 输入选择器解析后不存在任何 C 或 C++ 翻译单元
- **THEN** 扫描器返回 `invalid_request` 和 `no_supported_translation_units` 诊断，不尝试分析其他源语言

### Requirement: 翻译单元失败产生保守的部分结果
当部分翻译单元因解析、缺失头文件、编译器不兼容或不支持语义失败时，扫描器 SHALL 保留成功翻译单元的结果，状态为 `partial`，并公开 planned、completed、failed 和 unknown 分母。失败单元 MUST NOT 被解释为无 finding。

#### Scenario: 单个翻译单元解析失败
- **WHEN** 十个计划翻译单元中九个成功、一个因缺失头文件失败
- **THEN** 扫描器发布九个单元的 findings，状态为 `partial`，并为失败单元输出包含阶段和原因的诊断

#### Scenario: 所有翻译单元失败
- **WHEN** 没有任何计划翻译单元产生可用分析结果
- **THEN** 扫描器状态为 `failed` 而非 `partial`，且摘要不会声明工程无浮点风险

### Requirement: 资源预算耗尽可区分
扫描器 SHALL 支持 wall time、CPU、内存、文件数和诊断数预算。预算耗尽时 MUST 停止新增工作、完成可安全落盘的已有结果，并以 `budget_exceeded` 诊断说明具体预算、已用值和未分析范围；存在可用结果时状态为 `partial`，否则为 `failed`。

#### Scenario: 达到翻译单元时间预算
- **WHEN** 分析在部分翻译单元完成后达到 wall time 限制
- **THEN** 扫描器发布确定的部分结果与未完成清单，返回退出码 `4`

### Requirement: 内部错误不伪装成规则结论
未预期异常 SHALL 转换为 `internal_error`，默认仅输出稳定错误 code、失败阶段、关联请求和安全摘要。堆栈、绝对路径、环境变量与源码内容 MUST NOT 在默认模式泄露；显式诊断模式可以写入受控本地日志。

#### Scenario: 规则实现抛出未预期异常
- **WHEN** 某规则执行期间出现未分类异常
- **THEN** 扫描器停止或隔离该分析单元，结果不包含由异常路径构造的 finding，并返回 `internal_error` 或保守的 `partial`

### Requirement: 诊断必须可操作且双语
每条诊断 SHALL 包含 `diagnostic_code`、`stage`、`severity`、中文与英文消息、可选源码位置、可重试性和建议动作。相同根因的大量重复诊断 MUST 被聚合，并保留出现次数和代表性位置。

#### Scenario: 重复缺失同一系统头文件
- **WHEN** 多个翻译单元因同一缺失头文件失败
- **THEN** 扫描器输出聚合诊断、受影响数量和代表位置，而不是无上限重复消息
