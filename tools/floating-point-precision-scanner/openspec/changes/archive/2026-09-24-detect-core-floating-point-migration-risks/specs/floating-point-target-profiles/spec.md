## MODIFIED Requirements

### Requirement: Profile 文档具有版本、身份和来源
每个 profile SHALL 符合版本化 schema，并 SHALL 包含 `profile_id`、`profile_version`、target triple、ABI、编译器约束、浮点类型属性、求值策略、FMA/contraction、特殊值/浮点环境能力、数学库标识、字段级来源和维护审批信息。支持核心迁移规则的 profile 还 MUST 以可直接比较的规范形式提供 `long double` 的格式、storage bits、precision、alignment、ABI class、calling convention 与 variadic 语义，x87/excess-precision/`FLT_EVAL_METHOD` 和强制舍入策略，以及 FMA 可用性、默认 contraction policy 和选项约束。未知事实 MUST 使用带原因和 provenance 的显式 unknown 表达，不得省略后由宿主默认值补齐。

#### Scenario: 加载完整 profile
- **WHEN** profile 文档符合 schema 且交叉字段一致
- **THEN** registry 生成不可变 profile 和基于 canonical JSON 的稳定 SHA-256 指纹

#### Scenario: 来源缺失
- **WHEN** 一个确定值没有字段级来源或来源标识不可解析
- **THEN** registry 拒绝该 profile 并返回双语 `profile_source_missing` 诊断

#### Scenario: 核心规则字段可比较
- **WHEN** x86 source profile 与 RISC-V target profile 都提供完整的 long-double、evaluation 和 contraction 字段
- **THEN** registry 生成规范化比较视图，规则无需读取宿主 ABI、编译器默认值或展示文本

#### Scenario: 核心规则字段显式 unknown
- **WHEN** profile 的 `long double` ABI class、x87 evaluation method 或 FMA contraction policy 无可靠来源
- **THEN** 该字段保持 unknown 并由依赖规则传播，不以同架构其他 profile 或宿主值补齐
