## Context

P1-P3 已建立仅面向 C/C++ 的 CLI、编译上下文、x86/RISC-V profiles、canonical AST facts、共享 LLVM BC 消费、AST↔IR evidence 和四条核心迁移规则。当前 facts 主要描述局部类型、算术/比较、转换和调用；rule descriptor 只表达是否需要 build-faithful IR；结果 schema 尚未实现主规范已经要求的 `evidence_origin` 和 suppression。六条 P4 规则需要更多结构化语义：表达式的使用上下文、循环/递推、函数与线程边界、预处理分支、解析后的声明身份，以及由 sysroot/运行镜像决定的 libm 身份。

该工具仍是静态扫描器，消费上游生成的不可变共享 BC，不负责构建、等待或修改 BC。分析必须在信息不足时返回 `unknown`，不能用宿主环境、名称匹配或启发式猜测填补证据。

## Goals / Non-Goals

**Goals:**

- 以版本化纯数据 facts 支撑六条新规则，并保持 Clang/LLVM 原始对象不进入规则层。
- 区分“确定发生的语义事实”和“可能造成业务风险的启发式判断”，使每个结论可定位、可复核、可抑制。
- 结合 AST 的源码语义与 source-preserving/build-faithful BC 的实际 lowering，在证据冲突、缺失或歧义时稳定传播 `unknown`。
- 对 libm、fenv、类型转换、比较、归约和架构 API 建立有限、可测试、预算受控的模型。
- 通过向后兼容的协议次版本演进接入十条规则、build-context overlay、suppression 和完整统计。
- 为所有新增/修改项目自有代码提供正常、边界和异常单元测试，并使项目整体与受影响模块的行/分支覆盖率均至少 90%。

**Non-Goals:**

- 不运行 x86/RISC-V 二进制进行动态差分，不生成测试输入或自动证明业务误差阈值。
- 不实现通用跨过程数据流、指针别名、符号执行或全程序线程模型。
- 不让 AI 生成、覆盖或提升确定性 finding；协议可保留 `ai` 来源枚举，但本阶段不产生 AI 结论。
- 不编译、排队、等待或修复共享 BC，也不扫描 C/C++ 之外的语言。
- 不承诺为 x86 intrinsic 或专用数学库自动选择语义等价的 RISC-V 替代实现。

## Decisions

### 1. 先扩展事实图，再扩展规则 registry

新增 facts 均使用稳定引用形成有向事实图：表达式引用操作数与父级用途，转换引用源/目标类型，比较引用 guard/use，归约引用 accumulator、update 与循环，调用引用解析后 declaration、argument 和 preprocessor guard。规则只消费 schema 校验后的纯数据视图。

采用该方案而不是让每条规则自行遍历 Clang JSON，是为了避免六套不一致的 AST 解释、稳定 ID 和 unknown 逻辑。事实图只保留规则需要的有限边，不构建完整 AST 镜像。

### 2. RuleDescriptor 显式声明证据与作用域依赖

descriptor 增加 `source_fact_kinds`、`ir_fact_kinds`、`profile_fields`、`build_context_fields`、`ir_capability`、`assessment_scope`、`evidence_mode`、`default_enabled` 和预算键。`ir_capability` 区分 `none`、`source-preserving`、`build-faithful` 与 `either`，而不是单个布尔值；`evidence_mode` 区分 `deterministic` 与 `heuristic-capable`。

默认规则集合扩展为全部十条，但规则缺少声明的决定性输入时逐 scope 返回 `unknown`。这保持“省略 rules 就执行完整迁移扫描”的既有含义；显式空集合仍为 facts-only。启发式规则默认执行不会降低证据门槛，结果必须显式标记来源并要求人工确认。

### 3. 浮点环境使用函数摘要和有界调用传播

AST facts 记录 `#pragma STDC FENV_ACCESS`、fenv API 的解析后声明、读取/写入/清除/保存/恢复动作、异常类别与源码作用域；IR facts 记录 constrained FP rounding/exception behavior 和实际调用。每个函数生成稳定摘要，例如 `reads_environment`、`changes_rounding`、`tests_exceptions`、`restores_environment`、`unknown_effect`。传播只沿可解析的直接调用边，在配置的深度和候选预算内进行；虚调用、函数指针、外部调用或递归边界保守为 unknown。

不采用全程序数据流分析，因为它会显著扩大范围、资源预算和误判面。线程间环境不做共享状态推断，只根据标准线程局部语义、明确线程入口与 profile 能力描述影响边界。

### 4. 混合精度转换以类型和可表示性为准

conversion fact 记录 source/destination canonical type、implicit/explicit、cast kind、常量值（若可规范表示）、整数位宽/符号、浮点 precision/exponent range、storage boundary 和 use。规则对常量执行精确可表示性判断，对非常量只在类型域证明可能丢失 precision/range 时命中，并区分“必然丢失”和“值域未知但存在风险”。显式 cast 默认是意图证据，不作为该规则的风险 finding；若外层仍存在隐式窄化，则评估外层转换。

不使用源码后缀或展示文本单独判断类型，`auto result = (float)double_value` 等场景以 Clang 推导后的 canonical types 与 cast kind 为准。

### 5. 比较规则分离确定事实与脆弱性判断

AST 可确定记录 `==`/`!=`/关系比较、操作数类型与来源、零/常量/epsilon 形态、NaN/Inf guard、控制流用途。确定性的 NaN 语义错误模式可以产生 deterministic finding；“计算结果精确相等可能脆弱”“epsilon 不适合业务域”等只产生 heuristic finding，包含固定 reason code、证据和人工确认标记。

扫描器不得自动生成唯一 epsilon。建议仅描述绝对、相对、ULP 或领域容差的选择原则和应覆盖的特殊值。

### 6. 归约由 AST 识别递推、由 IR 验证重结合

AST facts 识别 accumulator recurrence、sum/product/dot-product 形态、循环/算法范围、并行或向量提示，以及 Kahan/Neumaier 等受支持补偿形态。IR facts 增加 phi recurrence、use-chain、`llvm.vector.reduce.*`、reassociation flags 和 reduction group。若 build-faithful IR 证明重结合/向量归约且与 source/target policy 形成差异，可给出高置信结论；仅有 AST 顺序敏感形态时为 heuristic。固定小规模表达式、单元素循环和已识别补偿算法进入明确非命中或较低风险分支。

不尝试证明任意循环的数值稳定性，也不把所有 `+=` 都当作浮点归约。

### 7. libm 使用不可变 build-context overlay

静态 target profile 继续描述架构/ABI 能力；请求 schema 1.3 可为 source 和 target 分别绑定 `FloatingPointBuildContext`，包含 sysroot/toolchain identity、libm implementation/version、errno policy、exception/special-value 能力、来源和独立指纹。overlay 必须引用对应 base profile fingerprint，参与 assessment/finding 语义身份，但本地 sysroot 绝对路径不参与指纹或默认输出。

该设计优于把 glibc、musl 或 vendor libm 固化进“x86/RISC-V profile”，因为数学库由构建和运行镜像选择。同一个架构可绑定不同 overlay；未提供可靠 libm 身份时，`math-library-variance` 对依赖差异的 scope 返回 unknown，而不是对每个数学函数发布泛化 finding。

### 8. 架构专用 API 必须绑定解析后声明与目标保护

API fact 使用 canonical declaration identity、namespace、builtin/intrinsic ID、定义头文件、required target features、模板实例与宏 spelling/expansion provenance；同时记录当前翻译单元中已生效的预处理分支/target guard。字符串名称匹配只能形成候选，不能单独产生 deterministic finding。只在目标端无已知等价能力或需要显式替代调查时命中；被排除的 x86 条件分支、不可达声明或已识别的可移植 wrapper 不直接命中。

### 9. evidence origin、suppression 与稳定身份进入协议

scan request/result 升级至兼容次版本 1.3；canonical facts 升级 1.3，LLVM facts/evidence 各升级 1.1，build-context 使用独立 1.0 schema。旧 1.0-1.2 请求仍按其既有四规则默认集合解释，避免默认行为随工具升级漂移。

每个 finding 增加 `evidence_origin=deterministic|heuristic|ai`；本阶段只产生前两者。所有 heuristic finding 以及 `critical`/`high` finding 强制 `requires_human_confirmation=true`。finding ID 在 suppression 前生成，并包括 build-context fingerprints 和确定的证据来源类别，但不包括双语文案或 suppression 理由。

请求 suppression 使用稳定 code、仓库相对 POSIX path pattern、可选行范围和非空中英文或语言中立理由；源码 suppression 使用严格语法 `fp-precision-scanner: ignore <code> -- <reason>` 并只作用于可验证的相邻声明/表达式范围。无理由、未知 code、越界路径、歧义范围或通配全部规则的 suppression 在分析前拒绝。命中的候选不进入 `findings`，而进入有界、可审计 `suppressions` 记录，并计入 `summary.suppressed`。

### 10. 排序、预算和异常保持逐 scope 可复现

候选在截断前按 rule order、scope、normalized location、semantic fact IDs 排序。函数摘要传播、比较/归约候选、IR use-chain、related locations 和 suppression records 均有独立预算与稳定 frontier。证据缺失/冲突为 `unknown`，规则可隔离异常为 `failed`，协议/registry 身份损坏为 `internal_error`；不得由并发完成顺序决定保留哪个候选。

### 11. 验证建议使用结构化 validation plan

每个新规则 finding 除中英文 `test_suggestion` 外，还包含稳定 `validation_plan`：`input_classes` 描述普通值、边界值、次正规数、NaN/Inf、抵消或病态顺序等适用输入；`error_metrics` 从 absolute、relative、ULP、classification、errno、exceptions 中选择；`threshold_source` 只能是 standard、profile、project-policy、user-provided 或 unknown；`repeat_strategy` 描述平台、优化级别、rounding mode、顺序和重复次数要求。规则不得把 unknown threshold 替换为自造数值，启发式 finding 应明确要求项目或领域负责人提供阈值。

采用结构化计划而不是只有自然语言，是为了让后续 RvPort 集成和 P7 动态差分能够机器消费，同时继续保留双语展示字段。本阶段只生成计划，不执行动态验证。

## Risks / Trade-offs

- [默认启用六条新规则会增加 unknown 或 heuristic 数量] → 结果公开 evidence origin、逐规则分母和人工确认，旧请求版本保持原默认集合，并允许显式选择规则子集。
- [函数级 fenv 摘要无法覆盖虚调用、函数指针和复杂线程传播] → 保留稳定 unknown frontier，限制直接调用传播深度，不声称全程序安全。
- [归约和比较规则可能误报] → 将结构事实与风险判断分层，固定排除项，heuristic 不得升级为确定事实或生成业务容差。
- [libm 元数据难以从现有构建系统获得] → 使用可选 build-context overlay；缺失时只阻断依赖该字段的 assessment，不借用宿主库。
- [事实与结果 schema 同时演进影响消费者] → 使用独立次版本、严格兼容矩阵、golden fixtures 和旧版本回归测试，未知字段仍拒绝。
- [大量 use-chain/循环事实增加内存和输出] → 只保留规则相关边，设置 per-TU/per-function 预算、稳定截断和摘要引用。
- [源码 suppression 注释可能被宏或模板复制] → 同时记录 spelling/expansion/instantiation provenance；作用域不唯一时拒绝 suppression 而非扩大范围。
- [validation plan 被误解为自动证明] → 显式记录 threshold source 与 unknown，文本说明仍需人工/领域确认，本阶段不执行计划。

## Migration Plan

1. 先增加新 schema、版本常量、旧版本兼容 fixtures 和 build-context 校验，不启用新规则。
2. 扩展 AST/LLVM facts 与 evidence binder，以 golden fixtures 验证身份、排序、unknown 和预算。
3. 扩展 registry descriptor，依次接入 deterministic-first 规则、heuristic 规则和 libm 规则。
4. 增加 suppression pipeline、结果统计与双语模板，执行全套兼容性和确定性测试。
5. 更新默认 analysis version，使 1.3 请求启用十条规则；如需回滚，可恢复旧 analysis version/default set，同时保留新 schema reader 和显式规则选择。

## Open Questions

- 首批内置 libm capability fixtures 采用 glibc 与 musl 的哪些已验证版本，由实施时可获得的锁定工具链/sysroot 决定；若没有可靠来源，只提供 schema 和 unknown fixture，不伪造 profile 数据。
- 可移植 SIMD wrapper 的首批 allow-list 仅接受项目内明确配置和已验证声明身份，还是提供内置列表；实施前应以现有代码库样本确定最小集合。
