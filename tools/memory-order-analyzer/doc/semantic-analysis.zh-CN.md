# 语义事实与对象证据

[English](semantic-analysis.md) | 简体中文

本页按语义层次组织仍使用的协议、CLI、预算和限制。以 [统一项目入口](UNIFIED_PROJECT_ANALYSIS.zh-CN.md) 为产品调用入口；各分层 CLI 用于开发排查，不能把候选或局部证明解释为全程序安全。示例命令仅在 Docker 开发容器内执行。

- [ModuleFacts / RunReport v2：原始语义事实](#doc-semantic-facts)
- [P2 受限跨 TU 效果摘要](#doc-effect-summaries)
- [AST 与 IR 跨 TU 证据层](#doc-ast-cross-tu-evidence)
- [A5 受限对象与指针 Provenance](#doc-bounded-object-provenance)

<a id="doc-semantic-facts"></a>

## ModuleFacts / RunReport v2：原始语义事实

`enrich-ir-semantic-facts` 实现 P1。工具链仍为 LLVM 21.1.8；生成 BC 需要预处理、语义检查和 IR 编译，不需要链接或运行目标程序。本阶段不做内存序缺陷判断。

### 版本与职责

| 对象 | 当前版本 | 行为 |
| --- | --- | --- |
| ModuleFacts | 2 | 新增值表、条件边、调用接口、内存范围、初始化和提取完整性 |
| RunReport | 2 | 必填 fact_extraction、artifact_migrations；原字段含义保留 |
| BuildSnapshot / TUManifest / BCArtifact / ScopeManifest / ScopeIndex | 1 | 保留原契约，提取身份放在已有 toolchain 元数据中 |

[protocols/extractor-protocol.json](../protocols/extractor-protocol.json) 是协议/policy 元数据源：extractor=0.2.0、facts=2、report=2。CMake 生成 C++ 元数据头，Python 读取同一个文件；worker `--protocol` 输出机器 JSON，`--version` 仍输出 LLVM 版本。doctor 和每次读取均检查完整身份，不仅检查 LLVM。

新消费者明确拒绝旧 ModuleFacts/RunReport v1 及未来版本。旧 RunReport 顶层禁止额外字段，不能把增加 fact_extraction 称为兼容 v1 扩展；历史报告不填造状态、不原地升级。完整字段定义见 [JSON Schema](../schemas/contracts.json)，引用一致性见 [semantic.py](../python/memory_order_analyzer/semantic.py)。

### 值图与类型

C++ [semantic.cpp](../src/semantic.cpp) 先登记模块内符号、参数、块和指令，再从内存事件、实参/调用目标、条件、返回和全局初始化收集所需操作数闭包。不是导出全部 LLVM 指令，也不是执行数据流求解。

- `values[]`：id、kind、type、type_kind、function/block、operands、details、status；整数有 bits，指针有 address_space。类型字符串来自 LLVM 类型 API，不解析 `.ll`。
- 参数 ID 为函数 ID 加 `:arg:N`；指令复用 `:bN:iN`。命名符号保留 `:symbol:`；未命名符号用独立 `:unnamed-symbol:` 命名空间与 LLVM 模块槽位，避免空名称冲突。同名局部实体由 artifact/函数位置隔离。
- 常量 ID 根据完整类型和值的 LLVM 表示生成模块局部 hash；整数内容为 bits + 十六进制字符串，128 位值不会经 JSON number 截断。LLVM integer 本身没有源语言 signedness。
- `kind` 区分 argument/instruction/integer/null/undef/poison/zero/aggregate/symbol/expression/unknown。freeze 是保留输入的 instruction，不选取运行值。零聚合采用 compact zero，声明的无初值与整数零不同。
- `operands` 保留 LLVM 操作数顺序；select 是 condition/true/false，cast 的输入节点类型和结果类型给出源/目标类型。phi details.incoming 保留 value_ref/predecessor，循环用引用闭合；icmp 保留 predicate，整数运算保留 nsw/nuw/exact，extractvalue/insertvalue 保留 indices。
- globals.initializer 为 state=value + value_ref 或 state=declaration + null；alias 不冒充普通全局初始化。静态初值不是 C++ 动态构造已执行的证明。

浮点值/运算、部分 vector/target-specific 语义、inttoptr/addrspacecast 等不能解释的节点保留类型/原始关系、unknown 原因和定位诊断。不存在“未知填零”或“缺字段视为无效果”。

### CFG 与调用

函数保留 parameters、return_type、vararg。块保留原 successors，并有 terminator（id/opcode/condition_ref/return_ref/status/edges）。edges 隶属 terminator，含 ordinal/target/kind/condition_ref/case_ref；相同目标的不同 switch case 不合并。ret void 的 return_ref=null，unreachable 的 opcode 单独保留。

调用保留 called_ref、arguments、result_ref（void=null）、function_type、calling_convention、normal/unwind。直接 target 仍供 scope 使用；间接 called_ref 存在不代表目标已解析。未命名目标不参与按空名称猜测的直接绑定。

tail 保留 LLVM CallInst 枚举数值字符串（非 CallInst 为 none）；ABI attributes 保存 LLVM 原始文本，非空时 attribute_status=unknown，并产生 uninterpreted_abi_attributes。bundles 保存 tag/inputs，存在时显式标记 opaque_call_features。未知终结指令仍保留实际后继，给出 unsupported_terminator。不会把这些字段的存在宣称为 ABI 或 EH 语义已建模。

### 内存访问范围

每个事件含 inputs、result_ref、ranges、range_status。range_status=available 表示有范围描述（其 size 仍可 unknown），fence=not_applicable，不透明效果=unknown。

范围含 role（read/write/read_write）、address_ref、address_space、alignment（未知为 null）、size：已知为 `{status: known, bytes: 十进制字符串}`，未知为 `{status: unknown, reason: 原因}`。大小来自模块 DataLayout 的 store size；不能用 bitwidth/8 或 triple 猜测布局。结构 padding、访问类型大小和字段偏移分别处理。

GEP 节点保存 source_type、原始基址/索引 operands、inbounds/nuw/nusw；offset 已知时为 bits/hex/signed_decimal，使用该地址空间的 index 位宽计算。动态 GEP、缺布局为 unknown。负偏移或已知偏移不证明 in-bounds、对象有效、alias 或访问合法。旧受限 address 视图不剥离指针转换，避免跨地址空间误判同对象。

load 引用结果；store/RMW inputs.value；CAS inputs.compare/new 及 result_ref，可通过 extractvalue 的索引追踪旧值/成功位和条件分支，原有成功/失败 order、weak、volatile、syncscope 保留。memcpy/memmove 分别记录目的写/源读范围和 length 引用，各自地址空间/对齐独立；memset 另有 fill 引用。零长度是 known 0，动态长度是 unknown，不以 0 替代。

### 预算和完整性

policy v1：最多 100000 值节点、500000 值操作数引用、常量嵌套深度 64、worker JSON 16777216 字节；继续使用进程时间限制。只限制常量嵌套，不把 SSA 链长当常量深度。常量深度超限保留可引用的 constant_depth 叶节点；节点/引用/输出总量超限返回 extraction_budget_exceeded，不发布该 TU 成功 facts。时间失败仍是 timed_out。

ModuleFacts.extraction 有 status、roots（唯一所需根数）、nodes、references（值表 operands 边数）、unknown（诊断条数）、diagnostics（id/reason）。这里 unknown 不等于未知值节点数：动态范围、未解释 ABI 等也产生诊断。诊断非空即 partial；无所需根可为 complete，但不是安全扫描。

RunReport.fact_extraction 独立于 parse/verify 与 source_mapping，含 planned/complete/partial/failed、complete_ratio、diagnostics。分母为完整计划，零分母为 null；doctor=not_run。存在可用但部分事实退出 2，全部不可用退出 1，无相关完整性缺口退出 0。缺 debug 不阻止值图，只降低定位。P1 的任何情况均保持 semantic_analysis=not_run、safety=not_evaluated、findings=null，points_to/effect_propagation/callsite_specialization/threads/memory_model=false；后续 P2–P4 使用独立产物，不改写该语义。P4 边界见 [一次性发布分析](publication-analysis.zh-CN.md#doc-single-publication-risks)。

### 缓存迁移与使用

CLI 命令不增加，沿用 [基础设施用法](development.zh-CN.md) 的 collect/import-bc/index/link/doctor，使用新输出目录和重新编译的 worker。终端中的 `python3 -m memory_order_analyzer --help` 可核对当前参数；开发环境与生产容器整合仍是独立 change。

1. collect 的 key 包含 context/输入/profile/SDK/完整提取身份，旧代缓存自然 miss；当前缓存仍重新发现依赖并检查身份。
2. 无 manifest 的 import-bc 按 BC hash + 当前协议产生 key，provenance 保持 unknown，不猜旧祖先。
3. 旧 manifest 先验 hash，由旧 key + BC hash + 当前协议重键，保留 context/profile/inputs/provenance 和旧 key/lineage；当前 manifest 再导入保持 key，不重复增加祖先。
4. RunReport.artifact_migrations 给出 from/to。用户据此显式重建 ScopeManifest.members；不会自动改变目标范围。index/link 每次都校验 v2 结构和引用、配置兼容和祖先重叠。linked key 包含范围及协议，链接后重新读取 v2。
5. 保留旧 BC、facts、report 和 scope；不实施有损 JSON 迁移、不覆盖历史产物。

覆盖率不是检测准确率；调用点绑定、存储值传播和效果摘要由下文独立 P2 层处理。

<a id="doc-effect-summaries"></a>

## P2 受限跨 TU 效果摘要

状态：`add-scoped-effect-summaries` 已实现。P2 在不改变 ModuleFacts v2、RunReport v2 和 ScopeIndex v1 的前提下，增加独立、版本化的局部求值与效果摘要产物。它支持显式 scope 内 GCC/Clang C/C++ compile-only BC 的确定直接调用组合，但不实现线程模型、happens-before、风险判定或通用 points-to 分析。

### 1. 分层与工具分工

P1 原始事实继续保存 IR 值、CFG、调用和原子事件的源码保真描述。P2 的 C++ worker 直接读取 LLVM 21.1.8 BC，以只读方式建立 DominatorTree、BasicAA/AAResults、MemorySSA、本地对象和控制流证据，并执行有界局部解释。Python 层负责显式 scope、采用资格、调用上下文、跨 TU 调度、实例重绑定、缓存、完整性传播和报告。

LLVM 提供局部语义查询，不负责项目的目标范围、跨 TU 符号选择、摘要契约和调用实例身份；这些属于自有实现。P2 不依赖 llvm-link、原生链接、执行被分析程序、SSH 或 DevKit。

新增产物均为 schema v1、`analysis_version=0.1.0`、`policy_id=scoped-effects-v1`：

- `LocalAnalysisFacts`：精确 linkage/ABI、P2 原始 IR 节点、局部对象和 LLVM 分析证据；其 `partial` 表示它只是补充事实，不表示效果求值失败。
- `LocalEvaluationRequest` / `LocalEvaluationResult`：一次函数上下文的候选值、调用绑定、预算、局部效果和未展开前沿。
- `EffectSummary`：可复用的参数化函数摘要以及独立 invocation/allocation 身份。
- `EffectAnalysisRequest` / `EffectAnalysisReport`：用户请求、分层状态、计划计数、依赖和诊断。

### 2. 用户入口

先完成 P1 `collect` 与 `index`，并创建只包含同一目标/配置成员的显式 ScopeManifest。随后创建请求：

```json
{
  "schema_version": 1,
  "kind": "EffectAnalysisRequest",
  "analysis_version": "0.1.0",
  "policy_id": "scoped-effects-v1",
  "scope": "D:/work/scope.json",
  "mode": "roots",
  "roots": [{"artifact_key": "<64-hex-artifact-key>", "function_id": "<P1-function-id>", "arguments": []}],
  "budgets": {
    "local_steps": 100000,
    "condition_states": 32,
    "value_candidates": 8,
    "contexts_per_function": 32,
    "contexts_per_request": 4096,
    "scc_iterations": 16,
    "effect_items": 10000,
    "worker_seconds": 60,
    "worker_output_bytes": 16777216,
    "request_seconds": 300,
    "request_output_bytes": 67108864
  }
}
```

运行：

```text
python -m memory_order_analyzer summarize \
  --request D:/work/effect-request.json \
  --scope D:/work/scope.json \
  --artifact-store D:/work/artifacts \
  --worker /workspace/build/moa-worker \
  --output D:/work/effect-output
```

`--output` 必须是新目录；命令不会覆盖历史结果。输出包括 `request.json`、`report.json`、`local/<artifact>.json` 和 `summaries/<digest>.json`。stdout 只输出报告 JSON，日志进入 stderr。退出码为：0=全部根上下文 complete，2=部分完成且保留 unknown/frontier，1=请求或分析失败。三种情况的 `safety` 都是 `not_evaluated`，`findings` 都是 null。

底层 worker 还提供 `--analysis-protocol`、`--local-batch` 和 `--evaluate-batch`，用于 Python 客户端的协议协商与批处理，不建议绕过完整的输入/依赖消费校验直接作为用户 API。

### 3. 支持边界

| 主题 | 已支持 | 保守边界 |
| --- | --- | --- |
| 编译输入 | GCC/Clang 的 C11/C17/C++17/C++20 compile-only 流水线；BC 由锁定 Clang reader 读取 | MSVC/clang-cl、源程序执行和最终链接不在范围内 |
| ABI | C calling convention；固定整数/指针参数；void/整数/指针返回；原生 noundef/nounwind/noreturn | vararg、浮点/聚合 ABI、byval/sret/inalloca/preallocated、musttail、bundles、未知属性保持 unsupported/unknown |
| 函数采用 | scope 内唯一、ABI 一致、不可替换的精确定义；受限 closed-scope `linkonce_odr` + COMDAT any + 同一规范化函数体 | weak/weak_odr、普通 linkonce、ifunc、冲突副本、开放边界和间接调用不任选目标 |
| 对象 | internal/private 或可证明 dso_local 且不可替换的已定义全局；参数；单实例 alloca；常量 GEP 字节偏移 | TLS、unnamed_addr 可合并对象、复杂堆、inttoptr/addrspacecast、动态偏移和未绑定 extern 保持 unknown |
| 标量/控制 | LLVM 精确位宽整数运算、cast/比较、phi/select、br/switch；guard 析取；路径和候选有界合并 | poison/undef/freeze、溢出 flags、不可判定路径和预算超限不猜测常量或互斥性 |
| 局部内存 | 已初始化、未逃逸、普通非 volatile 单实例栈槽的精确范围强更新/load 转发 | 合流未初始化、部分重叠、lifetime end、逃逸、可能别名覆盖会失效；atomic/volatile/shared/global load 不从 initializer 或前写推值 |
| 效果 | read/write/RMW/CAS/fence；地址、大小、值、ordering、failure ordering、syncscope、guard、may/must-normal-return、multiplicity、原始证据 | unknown 调用/内联汇编/未支持 intrinsic 产生显式 unknown effect，不序列化为空摘要 |
| 组合 | 确定直接调用、实参/形参和返回替换、调用点特化、调用实例与模板上下文分离、依赖闭包 | 递归或上下文/实例/SCC预算到达边界时 widening 为 partial unknown；merged 实例不提供强更新或 must |

函数体指纹对 SSA 名称和等价本地编号规范化；若函数引用 private/internal 全局或函数，则把 artifact 限定身份纳入指纹，避免两个 TU 中同名 static 被错误视为同一 ODR 内容。受限 ODR 采用是分析契约，不声称复现链接器最终选择。

### 4. 值、对象和实例语义

有限候选域的 candidates 是析取，每个 candidate 内的 guards 是合取；内部 bottom 只表示工作表尚无贡献，不能发布为完整空集。unknown 吸收不确定信息，候选或条件超限时整体 widening，不截取前 N 个继续作精确结论。

context 标识可复用的“函数+模板实参+scope+策略+预算”；invocation 标识一次抽象调用实例；allocation 归属于 invocation。同一模板命中缓存后仍会按调用点重新绑定实例。相同函数的两个调用点、同一实参的两个调用、以及递归层不会共享 allocation 身份。循环内 allocation 或递归合并实例的 cardinality 为 merged/unknown，不能用于 must-alias/noalias、强更新、guard 互斥或 must-effect 证明。

返回值支持参数、全局地址和参数/对象加常量偏移。返回失效局部 allocation 会生成 `expired_local_return`；无法安全表示的复杂返回保持 unknown。跨 TU 字段指针在调用者处保留调用者对象和 invocation，而不会把所有权错误转给 callee。

### 5. 调用图、缓存与完整性

调度器只沿明确采用边构造确定调用图，以稳定顺序计算 SCC 信息。正常非递归子调用先生成模板摘要，再用显式 dependency/call_binding 让调用者局部重求值，最后组合可见子效果。递归回边、SCC 迭代不足、上下文上限、worker 超时或输出上限都产生非空 unknown effect/frontier；不发布未收敛空集为 complete。

缓存 key 分为局部补充、模板、实例和 SCC，包含 scope、profile/ABI 采用、策略、预算及局部依赖闭包。内容按 canonical digest 校验；写入使用同目录临时文件、fsync 和无覆盖发布。损坏、陈旧、未来版本或同 key 不同内容均拒绝；只命中模板时必须重新绑定 invocation 后才能发布实例结果。

报告分别列出 input integrity、raw fact extraction、local analysis、interprocedural analysis、source mapping、member/root/context 计数和 frontier。P1 原始诊断保留在 P1 产物；P2 只有在能引用相同 facts hash、原始诊断 ID/reason 和分析证据时才允许登记 resolution，不能通过删除原始 partial 来抬高 provenance。

### 6. 明确不提供的结论

P2 只回答“在明确范围、调用上下文和预算下，哪些局部/跨调用效果可达，以及哪些工作仍未知”。它不建立线程实例、may-happen-in-parallel、reads-from 或 happens-before，不判断 data race、release/acquire 协议正确性，也不因没有已知效果而声称安全。P3/P4 已分别在独立产物中实现线程上下文与受限一次性发布规则，见 [线程与同步上下文](thread-analysis.zh-CN.md#doc-thread-and-sync-contexts)和[一次性发布分析](publication-analysis.zh-CN.md#doc-single-publication-risks)；P2 语义保持不变。

<a id="doc-ast-cross-tu-evidence"></a>

## AST 与 IR 跨 TU 证据层

状态：`integrate-ast-cross-tu-evidence` 已完成 2026-09-20 跨 TU 漏报纠偏和最终质量门禁，并已同步主规格、归档。该层是 P1–P5 之外的 additive sidecar；P1 `ModuleFacts v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1` 和 P4 报告语义均未修改。

### 1. 为什么同时需要 AST 与 BC

BC 仍是执行语义、原子 ordering、CFG、局部值传播和线程模型的依据；AST 补充源码声明、canonical declaration、USR、mangled name、linkage、visibility、TLS、类型/ABI、宏 spelling/expansion range，以及 `pthread` 源级 callback/handle 线索。AST 不能替代 LLVM 的执行顺序、reads-from、synchronizes-with 或 happens-before 证明。

`compile_commands.json` 只为逐 Translation Unit（TU，翻译单元）的 AST profile 提供目录和参数。分析器不再用它生成 BC；外部 record 通过 compile-record digest、physical TU、source hash、target/ABI/profile 与源码事实精确对齐。目标成员关系不从目录或编译数据库猜测，仍由 bundle/显式 `ScopeManifest` 决定。

### 2. 版本化协议

`protocols/source-evidence-protocol.json` 与 `schemas/source_evidence.json` 定义下列 v1 产物：

| 层 | 请求/产物 | 责任 |
| --- | --- | --- |
| 编译身份 | `CompilationProfileIdentity` | 固定 compiler family/version、语言标准、宏、include、target/ABI、debug/优化、依赖 hash、路径映射和 GCC→Clang 重放状态 |
| AST 提取 | `SourceSemanticRequest/Facts` | 每个物理 TU 的声明、定义、源码范围、有限值流、原子和直接 pthread 事实 |
| LLVM 绑定补充 | `LLVMSourceBindingRequest/Facts` | 从同一 BC 提取 linkage/visibility/TLS/COMDAT、definition role 和类型 ABI；不修改 P1 v2 |
| 全 scope 实体 | `ProgramEntityIndex` | external、internal、tentative/common、inline/template/ODR、weak/COMDAT/TLS 的保守实体分组 |
| AST–IR 绑定 | `SourceIRBinding` | 实体和表达式到 artifact-local LLVM 节点的候选集合、基数、支持/反对证据 |
| 只读覆盖 | `CanonicalObjectOverlay` | 将多个 TU 的精确声明/定义符号映射到一个 program object，同时保留原 LLVM identity |
| 下游补充 | `AstAssistedCandidateSlices` | P4 每个候选实际依赖的 AST 报告、overlay、artifact 和缺失项 |

`LLVMSourceBindingFacts` 是必要的独立补充层：P1 v2 没有精确表达 AST–IR 绑定所需的完整类型化符号 ABI，直接扩展 P1 会破坏已冻结语义。

### 3. Profile 与物理 TU 身份

profile digest 覆盖原始 GCC/Clang 命令、工作目录、源码和 include hash、target/ABI 以及 Clang 21.1.8 重放状态。同一路径的 GCC 与 Clang、不同宏、标准、target、ABI 或优化/debug 配置都是不同 profile。物理 TU identity 由 profile 和规范化源码路径共同确定。

GCC 输入只在标记为 `compatible` 时由 LibTooling 重放；GCC-only 选项、缺失 include、fatal diagnostic 或 profile/BC 不一致进入 `partial/failed` 与 frontier，不能静默删除后继续声称完整。

### 4. 实体解析与绑定语义

- external 声明只在类型、ABI、TLS、visibility 和 profile 兼容且存在唯一强定义时解析。declaration-only TU 若未引用对象而未发射 LLVM declaration，在全 scope 唯一定义已证明时是中性证据；有引用却缺少符号仍为 unresolved。
- file-static、internal linkage 和匿名 namespace 以 physical TU 隔离，同名不合并。
- C tentative/common 只在白名单兼容条件下合并；唯一强定义可覆盖 compatible tentative。
- C++ inline/template 多定义必须具有相同 definition digest；不等价是 ODR conflict。
- weak/linkonce/COMDAT 不按输入顺序挑选；无法唯一选择时保持 ambiguous。
- 一个精确的跨 TU canonical object 可以对应多个 artifact-local LLVM 符号（多个声明、恰好一个 distinct 定义），这不是一对一绑定；相同 `(artifact_key, id, kind)` 经多条 source binding 到达时先去重，不能伪造多个定义。
- 已建模的 pthread/标准库 declaration-only 实体登记为系统 external boundary，不污染用户 flag/payload 的候选相关完整性；未知外部实体仍保守 unresolved。

实体级 exact 要求 profile/TU、mangled name、definition role、LLVM linkage/visibility/TLS 和类型 ABI 的集合级证据一致。表达式映射依赖 debug location、宏范围、所属函数、对象和 opcode 上下文；同一行多操作时用受限 column/source range 区分候选，缺少 column 或仍多义时降级。优化折叠或无 debug 时只能是 candidate/unresolved，永不以最近行号猜测内存模型顺序。

### 5. CLI、缓存与预算

上游先依据同一 `compile_commands.json`、BC artifact 和显式 scope 生成逐 TU `SourceSemanticRequest`、逐 artifact `LLVMSourceBindingRequest`，再创建 `AstAssistedAnalysisRequest`。当前命令为：

```bash
python3 -m memory_order_analyzer.cli index-source-evidence \
  --request ast-request.json \
  --artifact-store out \
  --output source-evidence-run \
  --worker /output/build/memory-order-source-worker
```

`--output` 必须是新目录。缓存只位于显式 artifact store 的 `derived/ast-cross-tu-evidence-v1/`，key 包含请求和依赖 digest；损坏、陈旧或混合代际条目不会当命中。预算覆盖 TU、AST node、reference、diagnostic、entity group、binding candidate、dependency item、worker/request 时间与输出字节；截断保留原始分母并输出 frontier。

P2/P3/P4 仅在显式传入时消费：

```bash
python3 -m memory_order_analyzer.cli detect-publication-risks \
  --request publication-request.json \
  --artifact-store out \
  --output publication-with-source \
  --worker /output/build/moa-worker \
  --source-evidence source-evidence-run
```

省略 `--source-evidence` 时走原 IR-only 路径。source report、binding 或 overlay 的 scope/digest 不匹配会拒绝消费，不扫描“最新产物”。

### 6. 完整性、诊断与安全边界

报告分别给出 profile replay、source extraction、LLVM binding facts、entity resolution、entity/expression binding、overlay 和 downstream consumption 的 planned/visited/emitted/failed 分母。面向用户的诊断同时提供 `detail/detail_en` 和 `suggestion/suggestion_en`。

AST callback、一般源码文本先后、唯一符号、canonical object 或 P3 reads-from candidate 均不能单独生成 SB、RF、SW、HB，也不能把 `unknown` 提升为 `discharged`。受限例外是：Clang 对同一 `CompoundStmt` 中相邻 expression statement 登记精确 source `sequenced-before`，遇到 declaration/control/loop/return 即断开；且关系两端都唯一绑定到同一线程实例中的实际 IR memory effect 时，P4 可把它作为局部 must-before 补充。它不能生成 RF、SW、HB 或安全结论，`EffectSummary.order` 仍不得用于此证明。

P4 完整性同时保留全请求与 candidate-relevant 切片。无关系统实体或其他 TU 的缺口不会清空已有候选；相关 thread/atomic/payload 事实存在但组合后协议数为零时，报告必须输出中英文 `publication-candidate-unresolved` 和结构化缺失原因。P4 的 `safety` 始终是 `not_established`；零 finding、缓存命中、AST/IR 一致或固定语料全匹配均不是全程序安全证明。

当前仍未支持：`std::thread`/RAII、通用 points-to、fence/RMW/CAS release sequence、consume、线程池、自定义同步、复杂 mutex 和自动 CMake target scope 导入。

<a id="doc-bounded-object-provenance"></a>

## A5 受限对象与指针 Provenance

### 1. 目标与非目标

`extend-bounded-object-provenance` 为 GCC/Clang 的 C11、C17、C++17 和 C++20 增加独立 A5 sidecar。它回答“这个受支持的指针值可能对应哪个存储实例及子对象”，供 A4 mutex 与 P4 publication 的 exact-only adapter 使用；它不修改 P1 `ModuleFacts v2`、P2 `EffectSummary v1`、P3、P4 或 A1–A4 的既有协议和报告语义。

A5 不输出 risk、discharged 或 safe。报告固定 `safety=not_established`、`findings=null`，退出码仅为：完整 `0`、部分 `2`、失败 `1`。AST-only 事实不建立运行时 alias/noalias、reads-from、synchronizes-with 或 happens-before。

首版不支持堆对象、容器内部别名、虚调用、通用函数指针、任意指针算术、通用 points-to、fence、RMW/CAS 或安全判定。SVF/PhASAR 未成为依赖；若后续评估，必须单独锁定版本、许可证、LLVM 兼容性、性能和精度。

### 2. 协议与分层

协议清单为 [`protocols/bounded-object-provenance-protocol.json`](../protocols/bounded-object-provenance-protocol.json)，schema 为 [`bounded_object_provenance.json`](../schemas/bounded_object_provenance.json)。新增产物均为 v1：

- `BoundedObjectProvenanceRequest`：显式 scope、根、按物理 TU 的 profile、AST/IR 请求与全部预算。
- `SourceObjectPathFacts`：Clang AST 源路径；始终是独立事实层，不是 BC 失败时临时执行的脚本。
- `LLVMObjectProvenanceFacts`：LLVM 局部对象候选、查询证据、直接调用与返回事实。
- `BoundedObjectProvenanceGraph`：AST/IR 对齐、有限候选、直接调用组合和 exact-only adapter。
- `BoundedObjectProvenanceReport`：模式、完整性、双语诊断、缓存和退出码；不承载风险结论。

CLI：

```bash
python3 -m memory_order_analyzer analyze-object-provenance \
  --request /input/a5-request.json \
  --artifact-store /cache \
  --output /output/a5-run \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker
```

输出包括 `request.json`、`source-path-facts/*.json`、`llvm-provenance-facts/*.json`、`graphs/*.json` 和 `report.json`。输出目录是本次运行目录，`artifact-store` 是独立的内容寻址缓存。

### 3. 对象身份与 lattice

运行时对象身份由以下部分共同决定：

1. `StorageInstance`：global/stack/parameter/receiver/external/unknown、物理 artifact、函数、调用实例、allocation、lifetime 和 address space；
2. `SubobjectPath`：字段声明、字段序号、`.`/`->`、数组下标、显式解引用/cast、布局 offset/size/alignment 和 union overlap group；
3. `ByteRange`：DataLayout 下可证明的常量字节范围。

`FieldDecl` 只是一段路径，不能单独作为运行时实例。两个 `Box` 实例中的同一 `mutex` 字段因此不会合并；同一 storage 经确定 wrapper 传递时仍保持身份。union 的不同成员共享 overlap group，不能因为字段名不同就判定 disjoint。

内部 lattice 有 bottom，但序列化产物只允许：

- `must`：唯一、无反对证据的候选；
- `may`：有限候选或候选带反对证据；
- `unknown`：必须携带原因，可保留已知候选，不能将预算截断伪装为 complete。

每个候选保留 guard、proof、opposed evidence 和依赖切片。candidate、guard、path depth、load hop、AA、MemorySSA、capture、call context 和递归预算都进入版本化请求；命中上限进入 frontier。

### 4. Clang AST 源路径

Clang 21.1.8 worker 通过 `--object-path-request` 提取：

- C struct/union 字段、嵌套字段、指针字段、参数、返回值、地址/解引用、常量/动态数组下标和宏 spelling/expansion；
- C++ `this`、对象字段、receiver、成员/自由函数实参和返回；
- `ASTRecordLayout` 的字段序号、offset、size 和 alignment；
- 位域、柔性数组、不完整/匿名 record、动态下标、lossy/address-space cast 和不支持表达式的 candidate/unknown 原因。

语言路径彼此独立：C 使用 C AST、C linkage、全局/struct/union 和直接 pthread 语义，不依赖 C++ 类型或标准库 profile。

### 5. LLVM 局部分析

LLVM worker 通过 `--object-provenance-request` 在只读 module 上组合：

- DataLayout 与 `GetPointerBaseWithConstantOffset`；
- ValueTracking `getUnderlyingObjects`；
- DominatorTree、LoopInfo；
- BasicAA/AAResults 的 `MemoryLocation` 查询；
- MemorySSA 的 defining/clobber 查询；
- CaptureTracking。

global、alloca、parameter/receiver、phi/select、cast/GEP 和 pointer load 均登记输入、结果、analysis node 与预算类别。ptr-int、addrspacecast、null/undef/poison、unknown origin 等保持 unknown。

私有栈槽或 pointer field 只有在 exact range、唯一 reaching store、store 支配 load、MemorySSA 无相关 clobber、存储未逃逸、lifetime 有效且不是 atomic/volatile pointer load 时才强更新。多 store、MemoryPhi、MayAlias/部分覆盖、未知 call、capture、lifetime end 和 load-hop 超限不会提升为 must。

### 6. AST/IR 对齐与跨 TU

对齐同时检查物理 TU、profile、源 base、DataLayout offset 和候选 cardinality。源字段声明本身不能建立对象身份；只有 AST 与 IR 证据共同唯一时才能生成 exact alignment。

跨 TU exact 组合必须显式消费 A1 `ProgramEntityIndex` 的唯一 function definition 和 P2 `EffectSummary.adoptions` 的 adopted direct call，组合 actual-to-formal、返回值和 C++ receiver；source path 到 LLVM 对象的 exact 对齐还要求同 scope 的 `SourceIRBinding`、唯一 artifact target 和一致偏移。缺少这些依赖时，LLVM 中恰好只有一个同名函数也只能保留 candidate。间接/虚调用、ABI/profile/target/DataLayout 冲突、scope 外定义、weak/COMDAT 冲突、expired local return、context 或递归预算耗尽均降级。`EffectSummary.order` 不用于建立对象身份、sequenced-before 或 happens-before。

A4/P4 adapter 仅接受单一、无反对证据的 must 对象。may/unknown 对 A4 保持 `mutex-provenance-ambiguous`，对 P4 保持 `object-provenance-ambiguous`，不改变原风险严重度、退出码或安全语义。

### 7. 模式、缓存与完整性

每个 TU 记录 `ast+ir`、`ir-only`、`ast-only` 或 `failed`。scope 完整性按候选依赖切片聚合；无关失败 TU 不应污染独立候选，相关证据缺失则进入 partial/unknown。完整空候选、失败造成零候选和根本没有请求是不同状态，零 finding 从不描述为安全。

缓存 namespace 固定为 `bounded-object-provenance-v1`。键包含 layer、请求 payload 和依赖闭包；读取时重验 schema、semantic digest 和依赖，拒绝损坏、陈旧、failed、timeout 或非确定性结果。report semantic digest 排除 cold/warm cache hit 计数，因此相同语义输入的 cold/warm digest 一致。

### 8. 验证入口

定向单元测试：

```bash
python3 -m pytest -q -p no:cacheprovider tests/unit/test_object_provenance.py
/output/build/moa-unit --gtest_filter=ObjectProvenance.*:SourceFacts.*Object*
```

四语言真实 worker 验证：

```bash
MOA_WORKER=/output/build/moa-worker \
python3 -m pytest -q -p no:cacheprovider tests/integration/test_object_provenance.py
```

最终 required gate 使用全新输出目录：

```bash
python3 -m memory_order_analyzer.quality --output /output/quality-a5 --integration
```
