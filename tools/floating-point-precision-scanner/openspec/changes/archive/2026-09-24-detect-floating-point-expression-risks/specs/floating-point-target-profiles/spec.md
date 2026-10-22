## ADDED Requirements

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
