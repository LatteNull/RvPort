## Context

浮点精度扫描器当前以 `compile_commands.json` 或显式翻译单元为输入，调用锁定的 Clang 21.1.8 生成 AST JSON，再映射为 `FloatingPointFactBundle`。该链路能够表达源码类型、表达式、转换和调用，却看不到编译后是否形成 FMA、fast-math flags、constrained FP intrinsic、向量归约或具体 libm call。

强弱内存序分析器已有逐翻译单元 BC 的构建、导入和 LLVM worker 模式，但其 `BCArtifact` 包含工具本地路径和面向内存序的自由形态 facts，不是可直接共享的平台协议。RvPort 当前通用 `StoredArtifactService` 按 owner/type upsert 并删除旧对象，任务状态也没有制品依赖等待语义；这些平台能力必须由独立上游 change 建立。

本 change 位于浮点扫描器独立 OpenSpec 根，只实现共享 BC 的不可变消费、LLVM 浮点 facts 和 AST↔IR evidence。上游负责在 x86 构建成功后，根据真实 `compile_commands.json` 使用锁定分析 Clang 生成 artifact-set，通过内容寻址身份、single-flight 和就绪事件提供给所有消费者。

## Goals / Non-Goals

**Goals:**

- 在不重新生成或修改 BC 的前提下，安全、确定地读取 `READY`/`PARTIAL` 共享 artifact-set。
- 从 LLVM 21.1.8 逐翻译单元 BC 提取版本化 canonical floating-point IR facts。
- 以可审计的多对多关系关联 AST/source facts 与 IR facts，无法证明的关系保持 unknown。
- 保持现有 AST-only 本地模式兼容，并在结果中明确 IR 分析是否请求、完成或不可用。
- 对协议、完整性、兼容性、预算和逐 TU 失败采用保守状态，继续保持 facts-only 和空 findings。
- 为全部新增或修改代码提供正常、边界和异常路径单元测试，使项目整体和受影响模块的 line/branch coverage 均至少 90%。

**Non-Goals:**

- 不在本 change 中生成 BC、修改 x86 构建、实现 single-flight registry、对象存储、就绪事件或任务等待调度。
- 不依赖或迁移强弱内存序分析器内部 Python/C++ 包；只参考其已验证的进程隔离和 provenance 模式。
- 不支持跨 LLVM 主版本 bitcode、linked whole-program BC、ThinLTO/full LTO、反汇编目标文件或从二进制重建 IR。
- 不实现任何浮点风险规则、severity、修复建议或 CI 阻断策略。
- 不承诺 Clang 生成的分析 BC 与 GCC 生产编译器内部 IR 完全等价；两种编译器身份必须分别保留。

## Decisions

### 1. 生产者和消费者使用独立 change 与独立协议

`consume-and-scan-shared-llvm-bitcode` 只实现消费者。上游 artifact-set producer 通过版本化 manifest 交付不可变制品，扫描器不得调用 producer API 触发生成、不得轮询状态，也不得回退为自行编译 BC。

选择该边界是为了避免浮点扫描器成为全局编译基础设施 owner，也避免强弱内存序和后续工具反向依赖浮点包。替代方案是直接复用 memory-order-analyzer 的 `collect/import-bc`，但其本地路径、store 布局和领域 facts 会造成跨工具耦合，因此不采用。

### 2. 共享 artifact-set 使用 manifest 加逐 TU 对象

artifact-set manifest 使用 Draft 2020-12 schema，并至少包含：

- `artifact_set_id`、`source_revision`、`build_run_id`、`compile_commands_sha256`；
- producer、manifest schema、Clang/LLVM、分析 profile 和生成策略版本；
- `READY` 或 `PARTIAL` 状态、成功/失败 TU 分母和安全诊断；
- 每个成员的 `physical_tu_id`、`context_id`、`artifact_key`、language、target、ABI、profile、相对对象路径、size、SHA-256；
- 可选 binding sidecar 的相对路径、schema、size 和 SHA-256。

请求在现有源码输入之外增加可选 `bitcode_artifact_set`，包含显式 `artifact_root`、manifest 相对路径、预期 manifest SHA-256 和请求所需 profiles。所有成员路径必须相对 manifest 并在解析符号链接后仍位于 `artifact_root`。托管平台负责把远端对象安全地 materialize 到该根，扫描器不接受 URL、bucket/key 或凭据。

保留逐 TU BC 而不是只交付 linked BC，是为了维持 compile context、失败隔离、缓存粒度和源码映射。linked view 可以是未来派生制品，但不属于本 change。

### 3. AST-only 继续可用，AST+BC 是增强模式，不提供 BC-only 扫描

P2 请求仍必须提供 `compile_commands` 或显式翻译单元，`bitcode_artifact_set` 是可选增强输入。提供 BC 时，manifest 的 source revision、compile database digest 和 context identity 必须与规范化源码输入一致；不一致在启动 LLVM worker 前拒绝。

不提供 BC 时沿用现有 AST-only 行为，metadata 明确 `ir_analysis=not_requested`。提供 BC 时不得因某个成员缺失而偷偷重新编译；成功 AST 与 IR facts 均保留，缺失范围进入 partial/unknown 分母。BC-only 模式被排除，因为当前结果契约要求项目相对源码证据，并且无法证明源码快照一致时不应发布融合证据。

### 4. source-preserving 为首期必需 profile，build-faithful 为显式可选 profile

共享 manifest 可同时列出：

- `source-preserving`：使用调试信息和降低优化的分析构建，服务源码绑定；
- `build-faithful`：尽量保留生产优化语义，服务 FMA、fast-math 和向量化事实。

请求显式声明 `required_profiles`。首期默认只要求 `source-preserving`；缺少未请求的 `build-faithful` 不降低状态。未来规则必须声明所需 profile/capability，不能把 source-preserving 的“没有优化结果”解释为生产构建没有该行为。

### 5. LLVM 读取由隔离的锁定 worker 完成

新增 `fp-ir-worker`，链接锁定 LLVM 21.1.8，在独立进程中完成 bitcode parse、verifier 和事实提取。Python 层负责 schema、路径、摘要、预算、进程状态和输出校验，不直接绑定 LLVM Python API。worker 每次处理一个 artifact，接收最小版本化请求并只在 stdout 输出一个 JSON 文档，stderr 受字节预算限制。

worker 输出必须回显 artifact key、module SHA-256、target、data layout、reader/extractor 版本。Python 层将其与 manifest 和实际文件重新比对，防止 worker 输出串线或 TOCTOU。worker 不加载项目动态库、不访问网络、不执行 IR，也不写入 artifact root。

### 6. LLVM facts 与 AST facts 使用独立 schema

新增三种文档：

- `LLVMFloatingPointFactBundle`：artifact/module、profile、target/layout、functions、IR facts、unknowns、diagnostics、budgets 和 semantic digest；
- `FloatingPointEvidenceBundle`：引用 AST bundle digest 与 LLVM bundle digest，保存 bindings、unbound facts、歧义和 semantic digest；
- `SharedBitcodeArtifactSet`：共享输入 manifest。

IR facts 覆盖浮点标量/向量类型，`fadd/fsub/fmul/fdiv/frem/fneg/fcmp`，`fptrunc/fpext/sitofp/uitofp/fptosi/fptoui`，phi/select 中的浮点值，call/libm，`llvm.fma`/`llvm.fmuladd`、constrained FP、vector reductions、fast-math flags、function/module 属性和 debug/inline location。

IR fact ID 由 artifact key、规范化函数身份、稳定基本块/指令序号和语义载荷生成，只承诺在相同 BC 字节和 extractor 版本下稳定。跨重新编译的 finding 身份未来仍应优先基于源码语义，不直接使用 IR 序号。

### 7. AST↔IR binding 是显式的多对多证据关系

绑定优先级如下：

1. producer 提供且 digest/identity 校验通过的显式 binding sidecar；
2. 同一 physical TU/context 内，唯一函数身份、debug location、inline chain 与 AST spelling/expansion range 的结构化匹配；
3. 无法唯一证明时标记 `ambiguous` 或 `unavailable`。

每条 binding 记录 source refs、IR refs、relation、method、provenance 和 confidence class；允许一个 AST 表达式映射多个指令，也允许 FMA 等一个指令关联多个 AST 运算。函数名、demangled 文本、源码片段相似度不能单独产生确定性绑定。被优化删除、无 debug location、宏/内联链冲突或多个候选相同时保留 unknown。

### 8. 状态按输入、制品、TU 和证据层分级

- manifest schema/路径/请求组合无效或 source/context 确定冲突：`invalid_request`；
- artifact-set 为 `MISSING/QUEUED/GENERATING`：`failed`、退出码 3、`retryable=true`，扫描器不等待；
- 文件缺失、摘要不符、LLVM 不兼容、verifier/worker 失败：受影响 TU failed；有其他可用 TU 时整体 `partial`，否则 `failed`；
- IR facts 成功但必需 evidence 无法绑定：TU facts 保留，unknown 增加，整体至少 `partial`；
- 缺少未请求的可选 profile：不降低状态，但在 metadata 公开 unavailable capability；
- 未提供 BC：现有 AST-only 请求可 `complete`，但 metadata 必须说明 IR facts/evidence 未请求，不能被解释为完成 IR 风险检测。

### 9. 确定性、预算和安全边界从协议层固定

扫描器对 manifest 数量/字节、单 BC 和总 BC 字节、TU 数、worker wall time、stdout/stderr、IR fact/unknown/diagnostic 数设置显式预算。处理顺序按 profile、physical TU、context 和 artifact key 固定；并发完成顺序不得改变输出。所有外部错误默认脱敏，不输出 artifact root、对象存储信息、环境变量或项目根外绝对路径。

### 10. 测试使用固定小型 BC 和 fake worker 双层验证

大多数单元测试使用手工固定 manifest、最小合法/损坏 BC fixture 和可注入 fake worker，覆盖协议、路径、摘要、状态、聚合和绑定分支。少量本地集成测试使用锁定 Clang/LLVM 21.1.8 重新生成并验证 C11、C17、C++17、C++20 fixture，但集成测试不替代单元测试。

覆盖率使用现有 coverage.py branch 配置，将全部项目自有 Python 源码纳入分母；若新增 C++ worker，则使用 LLVM coverage/`llvm-cov` 单独统计 worker 项目整体和受影响模块 line/branch，二者均至少 90%。生成 schema、第三方 LLVM 和固定二进制 fixture 可排除，但必须记录理由。

## Risks / Trade-offs

- [上游 artifact-set 尚未实现，消费者可能先完成] → 固定 schema 和本地 fixture contract；apply 验收明确区分消费者就绪与平台端到端未就绪。
- [Clang 分析 BC 与 GCC 生产行为不同] → manifest 同时记录 production compiler 与 analysis compiler，facts 只陈述观察到的分析 BC，不宣称 GCC 内部 IR 等价。
- [debug location 不是完整 AST 身份] → 使用多对多 binding、method/provenance 和 unknown，不以单行号直接生成 exact 绑定。
- [build-faithful 优化会删除或合并源码表达式] → AST 和 IR bundle 独立保存，融合层表达 optimized/ambiguous frontier，不把缺少 IR 当作源码不存在。
- [BC 体积和 worker 输出可能造成资源压力] → 逐 TU 流式/受限处理、总量预算、内容摘要缓存和严格输出上限。
- [LLVM bitcode 跨版本兼容脆弱] → 首期精确锁定 21.1.8，版本不匹配保守失败，不调用 PATH 中替代工具。
- [通用 artifact store 会覆盖旧制品] → 本 change 不直接接入该 mutable owner/type 语义；要求上游提供不可变 artifact key 和 materialized snapshot。
- [请求同时包含 source 与 BC，配置可能漂移] → 在任何 worker 启动前校验 source revision、compile database digest、context 和 target/profile。

## Migration Plan

1. 增加新 schemas、版本常量和固定 fixtures，不改变现有 AST-only 默认行为。
2. 实现 manifest consumer 与完整性校验，先以 fake worker 验证失败语义和确定性。
3. 实现并锁定 `fp-ir-worker`，接入逐 TU LLVM facts schema。
4. 实现 AST↔IR evidence binding 和结果 metadata/summary 次版本字段。
5. 在本地 artifact-set fixture 上完成单元、契约和锁定工具链集成验证，并通过 Python 与 C++ 双 90% 门禁。
6. 上游平台 producer 就绪后执行 consumer contract/E2E；在此之前不宣称 RvPort 自动等待和共享复用已完成。

回滚时可以停止传递 `bitcode_artifact_set`，扫描器继续使用原 AST-only 模式。已发布的新版本结果仍可按 schema 读取；不得用旧版本程序静默忽略 IR/evidence 字段。

## Open Questions

- 上游 producer 的正式 change 名称、artifact-set owner 和跨任务保留/垃圾回收策略由平台提案确定。
- 首次平台集成是否默认同时生产 `build-faithful`，还是只在后续规则声明需要时按 capability 生成，由生产者成本评估决定。
- 显式 binding sidecar 是由共享 producer 生成，还是先仅依赖 debug metadata，再在后续 change 增强，需要在双方 contract review 时决定；消费者协议允许其缺省但不得伪造 exact binding。
