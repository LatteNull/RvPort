# floating-point-target-profiles Specification

## Purpose

定义 x86/RISC-V 浮点目标 profile 的版本、来源、registry、显式 source/target 绑定、冲突处理和可复现指纹。

## Requirements

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

### Requirement: Registry 提供初始 x86 与 RISC-V profiles
内置 registry SHALL 至少提供 Clang 21.1.8 对应的 x86_64 Linux GNU ABI profile 和 RISC-V 64 LP64D Linux GNU ABI profile。profile ID 和版本 SHALL 稳定且可查询，registry 列表 SHALL 按 profile ID 与版本确定性排序。

#### Scenario: 枚举内置 profiles
- **WHEN** 用户执行 `profiles list`
- **THEN** 输出至少包含 x86_64 与 riscv64 profile 的 ID、版本、target triple、状态和指纹，顺序稳定

#### Scenario: 查询未知 profile
- **WHEN** 请求引用 registry 中不存在的 profile ID 或版本
- **THEN** 扫描器在分析前返回 `invalid_request/unknown_profile`

### Requirement: Source 与 target profile 必须显式且相互独立
每个扫描请求 SHALL 显式指定 source profile 和 target profile，扫描器 MUST 分别解析并保留两者身份、版本和指纹。未指定、使用浮动版本别名或 profile 主版本不兼容 SHALL 被拒绝。

#### Scenario: 有效的 x86 到 RISC-V 组合
- **WHEN** 请求指定受支持的固定 x86 source profile 和 RISC-V target profile
- **THEN** 规范化请求和结果 metadata 分别记录两者完整身份与指纹

#### Scenario: 缺少 target profile
- **WHEN** 请求只指定 source profile
- **THEN** 扫描器返回 `invalid_request`，不得从宿主机或 source profile 推断目标

### Requirement: Profile 与编译上下文冲突必须显式失败
若翻译单元显式 target、ABI 或编译器主版本与请求 profile 的约束冲突，扫描器 SHALL 在启动该翻译单元前产生结构化冲突诊断。确定冲突 MUST NOT 降级为 unknown 或被宿主默认值覆盖。

#### Scenario: Target triple 冲突
- **WHEN** 编译命令显式指定 riscv64 而 source profile 声明 x86_64
- **THEN** 该请求或翻译单元按冲突范围失败，并公开预期值、实际值及 provenance

#### Scenario: Profile 字段为 unknown
- **WHEN** 某个非阻断字段在 profile 中显式为 unknown 且 P1 facts 提取不依赖该字段
- **THEN** facts 保留 unknown provenance，但不因此把完整扫描降级为 partial

### Requirement: Profile 序列化与指纹可复现
Profile canonicalization SHALL 固定 UTF-8、对象键顺序、数组语义、数字和字符串表示，并排除展示性描述与加载路径之外的非语义运行数据。相同语义 profile 在不同工作目录、locale 和加载顺序下 MUST 产生相同指纹。

#### Scenario: 相同 profile 位于不同目录
- **WHEN** 字节等价的 profile 从两个不同绝对路径加载
- **THEN** 两者指纹相同且结果不包含其绝对加载路径

### Requirement: 数学库语义必须由版本化 build-context overlay 绑定
扫描请求 MAY 为 source 和 target 分别提供符合版本化 schema 的不可变 `FloatingPointBuildContext`。每个 context SHALL 引用对应 base profile fingerprint，并表达 sysroot/toolchain identity、libm implementation/version、errno policy、浮点异常与特殊值能力、字段级 provenance 和稳定 context fingerprint；本地 sysroot、容器或 materialization 绝对路径 MUST NOT 参与指纹或默认输出。静态架构 profile MUST NOT 根据 target triple 猜测 glibc、musl 或 vendor libm。

#### Scenario: 同一架构绑定不同 libm
- **WHEN** 两个请求使用同一 RISC-V base profile，但分别绑定经过验证的不同 libm build contexts
- **THEN** base profile fingerprint 保持相同、context fingerprints 不同，依赖数学库的 assessments/finding identity 相应变化

#### Scenario: overlay 与 profile 不一致
- **WHEN** build context 引用的 base profile fingerprint、toolchain target 或 ABI 与请求 profile 冲突
- **THEN** 扫描器在规则执行前返回 `invalid_request/build_context_mismatch`

#### Scenario: 数学库身份未知
- **WHEN** 请求没有提供可靠 libm implementation/version 或字段来源
- **THEN** 相应字段保持带 provenance 的 unknown，`math-library-variance` 不借用宿主运行库补齐

### Requirement: 新规则依赖的环境和 API 能力必须显式可比较
profile 或其 build-context overlay SHALL 以可比较形式提供动态 rounding、异常标志、thread-local environment、constrained FP、架构 intrinsic/target feature 和数学库行为的已知值或显式 unknown。规则依赖字段必须通过 descriptor 声明；非依赖字段 unknown 不得无关地阻断 assessment。

#### Scenario: fenv 能力完整
- **WHEN** source/target profiles 都提供 rounding、exception 和 thread-local environment 能力及来源
- **THEN** `floating-environment` 可构造规范化比较视图并引用两个 profile fingerprints

#### Scenario: 无关能力未知
- **WHEN** architecture API 规则所需 target features 完整，但 libm version unknown
- **THEN** `architecture-specific-fp-api` 不因无关 libm 字段而变为 unknown
