## Context

本设计实现 [proposal.md](proposal.md) 中的 P2。P1 已归档，但“原始事实可追踪”不等于“分析前置能力齐备”。代码核对依据为 `src/facts.cpp`、`src/semantic.cpp`、`python/memory_order_analyzer/scope.py` 和 `report.py`。

| P1 已有 | 本 change 必须补齐，不能假定已有 |
| --- | --- |
| 参数/返回/条件 CFG/原始内存事件 | 参数经过 O0 栈槽后的值传播、受条件限制的事件可达性 |
| 简化 linkage 和 COMDAT 名称 | 精确 linkage、可替换性、函数体采用资格及证据 |
| 原始 ABI 属性字符串及 unknown | 函数与调用点接口、属性支持分类及异常控制依据 |
| DataLayout 访问大小及 GEP 偏移 | alloca 分配范围、私有性/逃逸与安全强更新条件 |
| scope 内唯一强符号绑定 | 逐调用接口复核、实参/返回映射、上下文效果组合 |
| ModuleFacts/RunReport v2 | 独立局部分析、摘要及分析完整性报告 |

2026-09-11 前轮探索在 `memory-order-analyzer-dev:llvm21` 中运行既有 `test_compiler_language_matrix[c++20-clang]`，1 项通过；检查到 `wrapped(p,v,order)` 的参数经过多次局部 store/load 后控制原子写分支，且有 `linkonce_odr` 标准库辅助调用、`noundef` 属性及 invoke/landingpad。辅助返回的 masked order 在该样例中不是 switch 的直接输入，不能据此虚构一条值链。此观察仅用于确定缺口；实施必须将可复现源码/IR、实际版本与新断言固化到项目测试，不能依赖临时 Docker volume 路径。

范围继续为 GCC/Clang 用户态 C/C++；GCC 编译数据库经已有适配后仍由锁定 Clang 产生分析 BC，不声称 GCC 原生输出 LLVM BC。分析显式输入且 compile-only，不运行应用、不要求原生链接，不改兄弟 archived 项目。

## Goals / Non-Goals

**Goals:**

- 在 P1 原始事实之外补齐局部语义基础，交付受限、参数化、可溯源的函数及调用上下文效果摘要。
- 对确定对象/常量字段、已采用的直接调用、可确定返回关系和小型 O0 atomic 包装获得可验证精度。
- 为未知值/别名/外部调用、递归、异常及资源截断保留保守影响和分层完整性。
- 实现离线可重复单元/集成验收，以及整体、语言、逐模块至少 90% 行/分支覆盖率。

**Non-Goals:**

- 不实现线程创建/锁模型、MHP/HB/reads-from、数据竞争或发布风险结论，不以零效果或零诊断证明安全。
- 不实现通用 points-to、复杂堆对象、虚调用求解、一般 weak/COMDAT/ifunc 链接选择、全路径 SMT、完整 C++ EH 或标准库全集。
- 不自动 llvm-link、推断构建 target、混合 source-preserving/build-faithful，不接入 DevKit/SVF/PhASAR，不合并 Dockerfile。

## Decisions

### D1. 分层实现，并保留原始 IR

采用以下数据流；各箭头都是经过版本/内容/引用校验的消费边界：

```text
BCArtifact + 原始 BC + ModuleFacts v2 + 显式 scope/request
       → LLVM 局部分析（C++，按模块批量）→ LocalAnalysisFacts v1
       → 直接调用资格复核（独立派生层）
       → 参数化摘要与上下文/SCC 调度（Python + C++ 局部求值）
       → EffectSummary v1 → EffectAnalysisReport v1
```

C++ 复用 LLVM CFG、DominatorTree、AA/MemorySSA、APInt/常量折叠及对象逃逸/可提升性查询；自有局部解释器定义支持子集、证据和降级。Python 负责显式范围、调用图、SCC、上下文预算、摘要替换/组合、存储及报告；不使用宿主整数重新定义 LLVM 运算。需要基于实参/被调摘要重求值时，向 worker 批量提交局部请求，返回版本化的上下文结果；禁止为每个 operand 启动一个进程。

新增 worker 操作通过独立分析协议协商；复用原始 ID 登记逻辑，重构后用黄金回归证明 P1 语义输出不变。每次重读 BC 前后验证 hash，原始 Module、BC 和 P1 facts 不运行变换 pass。MemorySSA 只用于函数内候选依赖查询，不表示并发 read-from/HB，也不单独证明 load 值。

实施中的底层传输已采用 `--analysis-protocol` 与 `--local-batch <request.json>`，请求为完整协议对象及明确模块 jobs，响应为版本化逐 job 结果/错误信封；信封不是新增最终报告 kind。当前已接入 eligibility/ABI 元数据及 D2a 局部登记/LLVM 查询，尚无上下文值与效果求解，LocalAnalysisFacts 保留 `local_evaluation_pending` 和 partial。。

备选：纯 Python 从 v2 重建全部局部语义会重复 LLVM 并仍缺少 metadata；对原始 BC 执行 mem2reg/SROA 会改变事件/ID。两者均不作为首轮默认方案。以后若在克隆 IR 上优化，须另行定义变换身份和原始证据映射，不能无映射替代 raw facts。

### D2. 新增协议，不偷偷扩展旧版本

新增 JSON kind 均从 schema v1 开始，按 kind 分派校验，拒绝未知字段、未来版本和悬空/跨函数引用。分析协议独立版本化为初始 `analysis_version=0.1.0`、`policy_id=scoped-effects-v1`，不修改 P1 extractor 0.2.0 的语义。

| Kind | 内容与身份 |
| --- | --- |
| EffectAnalysisRequest v1 | scope 引用、显式入口 `(artifact_key,function_id)` 或显式 `all-defined` 模式、预算、策略和入口抽象实参；两种入口模式互斥 |
| LocalAnalysisFacts v1 | artifact/BC/facts hash、extractor/LLVM/analysis/policy、精确函数属性、模块局部对象和独立 IR/LLVM 登记；不含上下文求值结果 |
| LocalEvaluationRequest v1 | scope/context/function、当前 invocation 及祖先实例表、带 guard 的实参候选、采用边及摘要/补充依赖、有效预算 |
| LocalEvaluationResult v1 | 完整请求快照及 canonical request_hash、原始节点的抽象值、块/边可达性、调用求值需求、出口、效果与证据、未完成前沿及局部状态 |
| EffectSummary v1 | scope/context/function、参数化对象/返回/效果/顺序、采用边、unknown/escape、完整性和依赖身份 |
| EffectAnalysisReport v1 | 请求与完整计划、输入/局部/过程间/定位状态、摘要引用、未完成条目、证据和退出码 |

ModuleFacts v2 的 unknown 和 extraction 状态保持原样；RunReport v2 仍是基础设施报告，`semantic_analysis=not_run`、`safety=not_evaluated`、`findings=null`；ScopeIndex v1 仍仅表示旧直接符号索引。不得在旧 capabilities 中启用摘要/线程能力。

补充分析可以解释原始 `uninterpreted_abi_attributes`，但必须记录 `resolution`：原始诊断 ID、对应调用、解释策略、证明/假设及结果；报告同时保留原始 partial 与新局部状态。未支持节点仅在已证明对请求不可达或与摘要无关时可标为不影响该上下文，并保存依据；不能全局清空原始缺口。

P1 诊断中的 id 是关联节点 ID，而非独立诊断 UUID；派生层以 `(facts digest, id, reason)` 引用原始诊断，不能假定同节点只有一种原因。

### D2a. P2 局部节点与分析证据登记（2026-09-11 用户批准）

`LocalAnalysisFacts.ir_nodes` 登记原始 Module 的全部指令，记录 SourceRef、所属 block SourceRef、opcode 和 LLVM type；包括未进入 P1 values 根闭包的 alloca。函数、参数和块继续使用 P1 身份。原始指令 ID 由共享登记器产生，不执行变换、不往 P1 添加节点。与 P1 已物化节点重合时必须核对 owner/opcode；未物化节点只在同 BC/hash 的受验证补充产物中合法，不允许凭 ID 字符串任意穿透引用检查。

`analysis_evidence` 登记 LLVM 生成的分析节点，使用 `{artifact_key,function_id,analysis_id}`，与三字段 SourceRef 的 `id` 明确区分。analysis_id 采用函数 ID 加 `:p2:<kind>:<稳定序号>`，不得伪装成原始指令。首批 kind 为 dominance、memory_live_on_entry、memory_phi、memory_def、memory_use、aa_clobber；每项保存 ref、原始 source、inputs（SourceRef 或 AnalysisRef）及 result。MemoryPhi 输入保留前驱块/MemoryAccess 成对关系，允许 CFG 循环引起的 MemorySSA 回边，不允许跨函数或未登记输入。dominance 导出可达性和直接支配块；AA-backed walker 导出候选 clobber，不输出确定读取值、HB 或 reads-from。

局部对象保存分配类型/地址空间/已知大小，以及 LLVM 可提升性给出的保守私有候选。无 DataLayout、动态/可伸缩大小保留 null 与原因；可提升性不是初始化、存活、单例性或强更新的完整证明。源节点、对象、分析证据生成工作项共享收紧后的 local_steps 登记预算；登记无法完整完成时该 job 明确失败并保留计划错误，不发布缺项但自称完整的登记表。求值器的重复工作项预算仍按 D6 单独计数。

摘要和报告新增必填 `local_dependencies`（artifact_key、补充产物 canonical digest）。消费处先校验所引用 LocalAnalysisFacts 的 schema/origin/预算和登记，再解引用分析证据及未物化 IR；缺失、重复、陈旧 digest、跨函数、命名空间混用或角色不符均拒绝。局部产物内引用自身登记，不使用自指 digest。证据仅是结构和查询记录；身份校验不能代替语义证明。该修订仍属于未发布 P2 v1 草案（analysis 0.1.0），旧 P2 草案缺字段明确拒绝；P1 v2/协议/历史产物均不迁移。

### D2b. 独立局部求值协议（2026-09-14 用户批准）

新增上述两个 kind，仍属于未发布 P2 v1 / analysis 0.1.0 草案；完整协议握手包含六个 kind，旧四 kind worker 明确不兼容。`--local-batch` 继续只处理模块元数据；独立 `--evaluate-batch` 批量传输 `{id,path,request}`，不能把绑定结果塞入 LocalAnalysisFacts，也不能按 operand 启动进程。结果内嵌经过校验的请求快照，以 canonical request_hash 绑定；消费处必须比对调度器实际提交请求，不接受 worker 自选上下文。原始 BC 仍按请求 origin 前后核验。

传输实施细节：完整 P1 digest 和跨模块依赖闭包由客户端按请求快照核验，worker 核验 BC 前后 hash/parse/verify 及重新生成的局部补充 digest。P1 采集后源码一致性字段依赖输入 manifest，不能仅从 BC 重建完整 facts；不删除或改写这些字段来迎合 worker。C++ 入口只保证传输及已消费字段校验，完整 schema/引用校验经 Python 客户端完成。当前传输初始化返回完整 pending 块计划和 not_run/steps=0，不算局部求解完成。整数数值字段不接受浮点 JSON 表示，宽整数使用 bits/hex，以保持 Python/LLVM canonical 哈希一致。

局部实参使用 `CandidateDomain`，与外层 EffectAnalysisRequest.Root 的单个 Value 分离。域为 `state=finite|unknown`、`candidates`、`reason`；finite 至少一个 `{value,guards,proof}`，每项 value 是既有非 unknown Value，guards 是合取条件，候选之间是可能结果的析取，不是运行概率或任取一值。unknown 为 top，候选必须为空且必须有原因；候选超过有效 value_candidates、路径相关性丢失或不支持时不能截取前 N 个，必须退为 unknown 并保留 frontier/partial。poison/undef/freeze 不是 bottom 或确定常量。符号表达式依旧引用原始指令和绑定实例，不能单独证明非 poison。

bottom 仅是内部工作表尚未获得路径/定义的空集，不在请求或结果 Value 中序列化。块状态单独记录 `reachable|unreachable|pending`：unreachable 必须有证明；pending 必须在 frontier 中保留，不能当成已证明不可达。complete 要求无 pending/frontier、不含未知域且所有相关工作已稳定；真实无效果函数仍可 complete，但不能仅凭空 effects 判定。预算未开始/失败请求必须留下显式前沿与非 complete 状态。

guard 引用原始 terminator 的具体后继 ordinal（不以 target block 代替，允许多个边指向同一后继），绑定产生它的 invocation。只在相同 single invocation 和 single 条件观察下允许利用不同 ordinal 的互斥；循环 repeated 或合并 unknown 不保留该证明能力。输入候选的 guard 只能引用传入实例表中的当前/祖先激活；求值不能为输入添加未证明条件。重复候选去重，但合流不能把互斥候选的 guards 拼成一个合取，也不能把有条件候选当成必然值。

请求保存 `origins`、完整 `local_dependencies` 和 `dependencies`（已采用被调 EffectSummary 的 context/digest）及 `adoptions`；`call_bindings` 以原始调用 source 显式选择其中的 context_id，必须对应非 unknown 采用目标及该摘要 root，不能按数组顺序猜测调用和依赖关系。它们均是本轮不可变快照；尚未就绪的 callee 不伪造空摘要，而以结果中的 `call_requests`（source、实参域、guards）交给 Python 调度器，并保留 frontier。仅存在依赖摘要不代表采用资格已证明；5.x 资格校验及实参/返回替换是利用其返回/效果前置条件。缺失/重复/陈旧 digest、跨 scope/profile/预算、错误参数数量/位宽/地址空间、外来实例、错误调用目标均拒绝。局部对象实参必须来自登记且绑定的当前/祖先分配，保持调用者身份；不再施加外层入口的“仅全局对象”限制。

结果复用请求身份，另含 `values`（source + domain）、`blocks`（source/state/proof）、`call_requests`、`effects/order/returns/escape/resolutions`、`frontier/diagnostics/status` 和 `steps`。所有局部结果源必须属于请求函数，外来值/guard 仅可通过合法实参/被调快照绑定传播；effect/call/出口角色按原始事实校验。结果证据通过请求的补充 digest 解引用；原始未物化节点与 LLVM analysis_id 不混用。重绑定仍遵循 D4a，不允许缓存命中把调用者对象重归属。

预算不新增不兼容 P1 字段：结构计数复用 local_steps，每次指令转移、工作表重访和候选笛卡尔积尝试均计一次；候选数按每域、condition_states 按当前保留路径状态、effect_items 按效果及顺序边合计。嵌套表达式在传输/消费前迭代预检，深度上限为 min(64, local_steps)，Value 节点总数不超过 local_steps；不等到递归 schema/常量折叠栈溢出才处理。达到预算的求值保留已知结果并产生非空未知前沿；非法超预算输入拒绝。默认输出/墙钟/请求总预算沿用 D6。缓存身份包括全部绑定、实例表及依赖快照；可复用模板 key 与本次求值 request_hash 分开。

### D3. 精确调用接口和函数体采用边界

局部事实保存精确 LLVM linkage、visibility、dso_local、COMDAT 及 selection kind、声明/定义、LLVM exact-definition/interposable 查询结果、函数类型/调用约定、参数与返回类型和函数/调用点属性。opaque pointer 类型相同不代表接口兼容；需要 ABI 类别与可见类型信息。

采用边分为 `unique-definition`、`odr-body-under-contract`、`unknown`，均是派生产物，不更改 P1 bindings。先复用 scope 的 target/layout/配置/lineage 校验，再检查同 profile、调用接口、边界与重复定义；缺少关键配置证据进入 partial，不能从目录或符号名推断。

- 首轮 ABI 支持：非 vararg 的 C calling convention、固定个数的直接整数/指针参数与 void/整数/指针返回，及明确建模的 `noundef`、`nounwind`、`noreturn`。`noundef` 不等于 nonnull、noalias 或已知值；其语义前提要保留，poison/undef 实参不作为确定常量。普通 `tail` 仅保留调用标记，不构造额外同步。
- 属性按“已建模 / 已审核可保守忽略 / 不支持”分类、版本化并列出理由。例如不利用 noalias/nocapture/readonly 进行精度提升时，保守忽略不等于事实不存在；未知属性默认不支持。`byval/sret/inalloca/preallocated`、vararg、未支持 calling convention、musttail/bundles 等先 unknown，不照位置直接绑定。
- 已有唯一强绑定仍须通过 ABI/函数体检查，不以符号唯一为充分条件。函数内部符号用 artifact + symbol ID 隔离。
- 为已实测 atomic 辅助函数允许受限 ODR 语义采用：调用直接指向本 TU 可见 `linkonce_odr` 函数体；LLVM 判定非 interposable、具备 dso-local 依据；已声明封闭 scope；没有冲突强定义或已知不兼容副本；函数接口及局部语义受支持。记录“遵守 LLVM ODR 契约”的假设和该体作为语义代表的理由，不输出“最终链接选择已知”。同 scope 可见同名副本需进行保守的规范化结构/接口指纹比较，无法证明兼容即 unknown；指纹一致不证明未知外部实现一致。一般 `linkonce`、weak、weak_odr、ifunc、动态边界或未支持 COMDAT selection 保持 unknown，首轮只支持经过测试的 ODR `any` 组合。
- 采用体的 nounwind 可用于排除该 invoke 的 unwind 边，但必须有属性适用性和采用边证据。否则保留异常路径及未知效果；noreturn 不产生正常返回摘要。

此通道有意区别于一般 linker 求解。对完全相同的原始输入，P1 index 仍可报告 COMDAT unknown，而 P2 在明确策略和假设下产生可审计语义采用边。

副本指纹仅消除 debug 和局部 SSA 命名差异，保留类型、语义属性、操作数/CFG、调用目标及被引用全局的存储身份；引用不同 TU 私有全局的函数不能因文本名称相同而通过兼容检查。不能规范化的关系保持 unknown。

### D4. 有界对象、值和局部存储域

对象域为 Global(scope 内确定定义)、Param(function,index)、Local(artifact,function,alloca,context)、Unknown；对象引用包含地址空间、常量字节偏移或 unknown、访问长度及存储身份依据。extern 不新建对象，同名 static 不合并。不同参数默认可能 alias，不能以参数编号或数值偏移证明对象不同；地址空间转换和 inttoptr 不静默剥离。

同一确定对象用半开字节区间判断 overlap/disjoint，动态长度/偏移保持 unknown；零长度保留零访问含义。不同确定对象只有存储身份独立时才判不重叠。偏移可计算不代表 in-bounds、存活或源语言合法。

值域为有精确位宽的常量、参数/对象表达式、有界候选集合及 unknown（含原因）。支持整数算术/位运算、比较、select/phi、受支持 casts/GEP 和返回替换；使用 APInt 和 LLVM flags 规则处理 signed/unsigned、nsw/nuw/exact、无效 shift、poison/undef/freeze。未知路径保留可能分支，不猜运行值，不推导完整路径可行性。

局部强更新只允许：确定大小且未逃逸的普通栈对象、受支持的精确子范围、已初始化值、有已证明的到达定义且没有可能别名覆盖。分支合流合并候选，循环有限迭代；不满足条件则退到未知。首轮保证直接标量栈槽及常量不重叠字段；部分重叠写不做字节拼装，退化受影响读取。lifetime 边界使旧值失效。

向未知代码传地址、返回栈地址、存入外部可达位置等导致逃逸/失效；未知调用可影响可达/可能别名内存，不能当作空效果，但不得无依据抹掉所有未逃逸私有栈槽。普通共享/global 与 atomic/volatile load 不按 initializer 或词法前序 store 转发。原子值可保留符号结果、order/syncscope 和路径，但不建立 reads-from。

### D4a. 可复用上下文与实例身份（2026-09-11 用户批准的补充）

`context_id` 是函数、抽象实参及分析环境的可复用摘要身份，不代表一次调用。每个摘要另有 `root_invocation_id` 和有限 `invocations` 表；表项记录 id、复用 context_id、函数 SourceRef、parent_id、callsite、cardinality（single/merged/unknown）与 reason。根调用没有 parent/callsite，子调用必须指向先登记的父项及其真实调用指令。同一实参两个调用点允许相同 context_id，但必须得到不同 invocation id。原始 SourceRef 不变；引用函数符号时 function_id 为 null。

确定的非递归调用路径按根身份、父实例和调用点稳定派生实例 ID。single 仅表示当前抽象入口求值中的一个激活，不声称进程生命周期只调用一次。循环调用、递归 SCC 及预算合并用有限的 merged/unknown 桶；桶身份绑定 scope/根及抽象合并原因，不枚举无限栈帧，不把桶的 ID 相等理解为同一具体激活。实例数同样受 contexts_per_request 限制，并计入效果工作预算；达到上限保留未知前沿，不静默丢项。

局部指针携带 allocation 字段（invocation_id、cardinality、reason），原始 alloca SourceRef 标识分配位置。全局对象 allocation=null；形参/符号表达式用 invocation_id=null 表示模板槽，用非空 invocation_id 表示已绑定实例。guard、效果、返回和诊断解释带显式 invocation_id；实例化必须递归重绑定值、guard、escape、返回及证明的实例归属，不重写 raw IR ID。调用者传入的对象仍属于调用者分配实例，不能重归属到 callee。

分配的单例性不能强于所属调用实例；即使调用为 single，循环内 alloca 仍是 merged。仅有独立存储身份和已证明单例性时才可作局部强更新的必要条件；它并不替代 D4 的范围、到达定义、存活和非逃逸证明。任何 merged/unknown 分配不作 must-alias、不凭不同 ID 作 noalias、也不作强更新。不同参数仍可能别名。返回失效局部保持 unknown，不因实例 ID 完整而恢复有效性。

互斥 guard 只能在同一 single invocation 内比较同一 terminator 的不同后继边，且两个 guard 的 multiplicity 必须均为 single（需局部分析证明该条件观察不重复）。单一调用内部的循环也会重复执行条件，因此调用单例性本身不够；重复/未证明的条件观察记录 repeated/unknown。不同实例或合并桶中的同一 raw guard 不能互相消去。merged/unknown 实例效果保持 may 及非 single multiplicity，不继承模板中的 must-normal-return，guard 也降为 unknown。递归/预算合并丢失的相关性必须产生诊断与 partial，保留已知效果和非空未知前沿；不以重命名或缓存命中消除该状态。

### D5. 摘要结构和跨 TU 组合

摘要保存 read/write/RMW/CAS/fence、对象/范围、值关系、atomic/volatile/order/syncscope、调用点、路径 guard、正常/异常/不返回出口、返回关系、escape/unknown。局部栈访问标记为 local，不冒充跨调用共享效果；参数化效果实例化后保留原始与调用上下文两层身份。

效果与依赖边组成有界事件图，保留控制条件和已知先后，不把跨分支集合串成一个必然序列。初始 `occurrence=may`；只有已证明覆盖相应路径/出口的事件可设置 `must`，且明确 `normal-return` 等量化范围。循环/递归保留重复或 unknown multiplicity，不能把一次源码事件视为运行时恰好一次。

直接调用组合按采用边替换参数对象/值，传播返回关系和未知影响；两个调用同一函数但实参不同，context 身份与筛选后的效果分离。返回参数/参数加常量偏移/全局地址属于支持范围；返回已失效局部或复杂 heap 保留诊断，不输出有效确定对象。

atomic 验收从源码实际生成的分支证明 `publish → wrapped(&x,1,release)` 的可达原子写为 release；不能用函数名识别 std::atomic 或把源枚举数值作为跨标准库通用模型。未解释的 helper/ABI/EH 必须完成有证据的解释或仍保留 unknown，不能因 order 已知便宣称整段效果完整。首个成功矩阵锁定 LLVM/Clang 21.1.8、容器 libstdc++ 13（实际 package 清单和 hash 随报告记录），C++17/20 分别编译断言；其他标准库只有经可见体推导或独立版本模型验证才能宣称支持。

### D6. 上下文、递归与预算

先构造确定采用边的调用图，再以 SCC 进行稳定顺序迭代。函数通用摘要保留符号参数，按显式入口及实际可达调用按需生成上下文，不假定 main 是唯一入口，也不无限内联。递归候选域采用单调合并；达到上限执行保守 widening/unknown，保留已知效果与待分析前沿。不能在递归计算尚未收敛时发布暂时的空集作为完整摘要。

初始 `scoped-effects-v1` 默认预算（请求可显式收紧，修改策略需留痕）：每上下文最多 100000 局部分析节点、32 个条件状态、每符号值 8 个候选；每函数 32 个上下文、每请求 4096 个上下文；SCC 最多 16 轮；每摘要 10000 个效果节点/顺序边合计。局部 worker 每批 60 秒/16 MiB 输出、请求总计 300 秒/64 MiB 派生产物；输出超限不发布残缺 JSON，生成小型失败/截断报告。请求范围大小不作为上述预算的分母替代品。

结构预算为确定性主要限制，墙钟是最后保护并单独记录；同输入/策略、未触发墙钟限制时结果排序和身份可重复。超限可能产生 partial（其他条目可用）或 failed（全部不可用），不能以空效果、空计划或未运行后续项获取 complete。进入预算前保存完整成员/入口计划，未展开前沿标为 unknown，实际发现上下文计数不冒充全部可能上下文总数。

局部节点预算按工作项处理次数计数，重复访问也消耗预算，不只统计不同 IR 节点；因此局部循环在没有增长新节点时也不能无限迭代。计数定义与生效预算一同写入策略和报告。

### D7. 缓存与不可混合身份

LocalAnalysisFacts key 包含 artifact/BC/facts digest、P1 extractor、LLVM、局部分析版本/策略及局部请求；EffectSummary key 再包括显式 scope/边界、profile、入口绑定、上下文、预算和依赖摘要 digest。递归内部使用 SCC 内容与最终摘要集合建立稳定组身份，避免循环 hash 定义；更新任一成员使 SCC 和调用者传递失效。不要把时间戳混入语义身份。

消费磁盘/worker/cache 均检查完整 schema 和引用，并检查 BC 前后 hash、scope/lineage/profile 一致性。新分析策略仅重算派生产物，不使原始 BC/P1 facts 无故重键。输入变化、依赖变化、损坏缓存不得当作命中；原始历史产物不覆盖，未知 provenance 不因补充分析而升级。

缓存复用的是参数化模板，而不是调用者已经实例化的栈对象。模板缓存身份不混入某次调用位置；实例化产物身份包含根、实例表及抽象化策略，命中模板后重新绑定。消费时拒绝悬空/循环 parent、跨函数 callsite/guard、强于父项的单例声明和外来实例。递归合并桶不以自身摘要 digest 递归定义身份；稳定 SCC 组身份与实例路径分开。

### D8. CLI、完整性和报告

拟新增（实施前不可用）：`python3 -m memory_order_analyzer summarize --request <request.json> --artifact-store <store> --output <fresh-directory> --worker <worker>`。请求引用显式 scope，并选择非空具体入口或 `all-defined`，不得省略后默认扫描目录。固定入口用函数 ID 而非含糊名称；空请求、非法引用或配置/lineage 冲突拒绝。

报告分开保存 input_integrity、raw_fact_extraction、local_analysis、interprocedural_analysis、source_mapping；各分析状态为 complete/partial/failed/not_run。`complete` 仅表示在已声明范围、支持策略和列明语义前提下完成效果推导，不表示全程序闭合或安全。对 ABI 已解释或已证不可达的 raw unknown 保留诊断对应关系；仍相关的未解输入缺口沿依赖传播，source unavailable 单独展示。

统计原始计划成员、读取/局部完成/部分/失败/未运行数，入口计划、已发现上下文及已处理/截断数、未展开前沿、unknown 调用/对象、事件定位比例；明确每个分母，零分母为 null。不得因不可读取成员或未知根被过滤而显示 100%。

新增命令退出码：0 为请求完成且无相关完整性/来源/定位缺口；2 为有可用摘要但存在未知、输入/定位缺口或截断；1 为非法请求或全部不可用。无 debug 时仍产出 IR 摘要，定位 unavailable 导致 2，但不伪称局部语义失败。旧 collect/index/link 的退出语义不变。stdout 只输出新报告 JSON，日志到 stderr；任何非零结果尽力输出合法报告，始终 `safety=not_evaluated`、`findings=null`，不创建风险退出码。

### D9. 验收与文档交付

单元测试覆盖所有新增/修改/复用 C++/Python 执行逻辑，包括 worker 入口、schema/ref validator、缓存/策略/预算/报告/质量脚本。保留现有递归源码枚举，并验证新增子目录、未调用函数与可执行头文件确实进入编译及 coverage export；仅枚举到文件但没有报告也必须失败。整体按 hit/total 合并，语言与所有逐模块门槛均为行/分支至少 90%；集成 profile 不混入。

固定 IR 单测负责精确语义，至少覆盖宽整数和 poison、合流/循环、局部重叠/逃逸/未初始化/lifetime、共享/原子不转发、属性/ODR 正反例、返回指针、多个上下文、递归固定点/截断、未知调用内存失效、引用损坏和缓存传递失效。三个物理 TU 与真实 C/C++ 原子包装使用离线集成验证，GCC/Clang C11/C17/C++17/C++20 原有适配矩阵回归；未支持组合不能伪装成功。

实际实施验收沿用现有入口，使用新的输出目录（已存在则换新目录，不删除旧报告）：

```powershell
docker run --rm --network none --mount "type=bind,source=D:/projects/RvPort/tools/memory-order-analyzer,target=/workspace,readonly" --mount "type=volume,source=moa-dev-output,target=/output" memory-order-analyzer-dev:llvm21 python3 -m memory_order_analyzer.quality --output /output/quality-p2-001 --integration
```

报告包括 `coverage-summary.json`、`python.json`、`cpp.json` 和 HTML，均在该输出目录；列出命令、工具版本、整体/语言/逐模块 hit/total、排除理由和独立集成结果。此命令是未来 apply 验收，不代表本提案已运行质量门槛。

实施阶段新增 `doc/EFFECT_SUMMARIES.md`（支持矩阵、协议/CLI/算法/unknown/示例）和 `doc/EFFECT_SUMMARIES_VALIDATION.md`（复现环境、逐场景证据、预算/确定性、覆盖率及结果），更新 README、路线图及事实文档的阶段边界。校验相对链接与证据来源，记录默认策略及标准库 package hash。仅在真实验证通过后更新已完成状态，不修改历史 ARM/mm-check 观察。

## Risks / Trade-offs

- [错误的局部 store/load 转发会抹掉并发读语义] → 私有非逃逸普通栈对象白名单，共享/atomic/volatile 反例必须有负向断言。
- [ODR 函数体采用被误解为 linker 求解] → 独立采用边、保留 ODR 假设、可见冲突检查和旧 index unknown，拒绝不满足子集的 weak/COMDAT。
- [过度保守导致真实 atomic 仍 unknown] → 首个固定标准库样例是成功验收项，不允许靠过滤诊断过关；补齐所需局部/ABI 能力或报告阻塞并修订设计，不暗中扩大支持。
- [上下文/路径/递归状态爆炸] → 有界抽象域、SCC、固定预算、保守 widening 和未完成前沿，结果不得丢未知效果。
- [双层事实出现矛盾或陈旧缓存] → BC/P1/派生 hash 与跨产物引用校验、原始 ID 回归、协议分代、传递失效测试。
- [覆盖率门槛诱导拆分/排除难测逻辑] → 保留全项目和逐模块门槛、未加载源码检查、语义断言与集成独立统计。

## Migration Plan

1. 添加新 kind/schema/分析协议及兼容性测试；旧 v2 facts/report、v1 manifest/index 不升级、不覆写。
2. 添加局部分析及派生层；相同 BC 经校验生成独立 sidecar，旧缓存可继续供旧命令使用。
3. 开放显式 summarize，提供请求样例和合法错误报告；旧命令无隐式分析行为。
4. 完成离线质量/语义验收和文档后再提示 sync/archive。回退仅停用新命令/新产物读取，保留原始输入和历史产物，不执行删除式迁移。

## Open Questions

2026-09-11 局部登记缺口已获用户批准，实施契约见 D2a。固定 IR 复现 `Effects.RegisteredInstructionDoesNotNecessarilyHaveAP1ValueNode` 保留为兼容性反例，不再作为等待确认项。

2026-09-11 对象/标量基础实施后发现的上下文协议缺口已于 2026-09-14 获用户批准，契约见 D2b；不再等待确认。既有拒绝测试调整为模块事实/外层入口不可混入局部候选数据的分层回归。先完成新增协议及边界测试，再接入局部求值；底层 ScalarSet 本身仍不作为 JSON kind。

默认使用现有开发镜像/LLVM 和 libstdc++ 的已验证组合；具体 package 修订与 hash 在实施复现时记录，不用浮动库名宣称普适支持。首个真实业务 target、其他标准库、完整 EH、一般 ODR/COMDAT 链接与线程模型仍留待后续 change。
