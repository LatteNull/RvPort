# llvm-local-effect-analysis

## Purpose

规范基于 LLVM 21.1.8 的只读局部事实补充、上下文求值、对象和值传播及证据边界，为跨 TU 效果摘要提供可验证输入。

## Requirements

### Requirement: Separate context evaluation requests and bounded results from module facts

系统 SHALL 使用独立 LocalEvaluationRequest/LocalEvaluationResult v1 批量协议，结果绑定完整请求及 canonical request_hash；模块 LocalAnalysisFacts SHALL 不含上下文求值。局部请求 SHALL 明确函数/context/invocation、实参候选、实例表、采用边、摘要和补充依赖及预算。CandidateDomain SHALL 区分非空有限候选和带原因空候选的 unknown；内部 bottom 不得作为合法发布值。候选 guards 为合取，候选间为析取，不任选一项，不以 P1 phi operands 替代。

#### Scenario: A caller passes guarded alternatives

- **WHEN** 局部请求传入经校验的多候选或调用者局部分配
- **THEN** 保留候选与 guard、调用者实例/分配身份及证据，不改外层入口的单值模板契约，不将对象归属改为 callee

#### Scenario: A state is unprocessed rather than unreachable

- **WHEN** 块尚未求值、域仍为内部 bottom 或 callee 尚无可采用结果
- **THEN** 输出 pending/frontier 或 call_requests 与非 complete 状态；只有附带证明的 unreachable 可排除路径，不能发布完整空效果

#### Scenario: Candidate or expression work exceeds a limit

- **WHEN** 候选/路径/转移预算耗尽，或表达式超过 min(64, local_steps) 深度及 local_steps Value 节点上限
- **THEN** 超预算输入拒绝；求值中保留已有结果并退为 unknown、非空 frontier 和 partial，不截取候选或无限构造表达式；重复工作及笛卡尔积尝试计入 local_steps

#### Scenario: Different successor edges share a target block

- **WHEN** br/switch 多条边指向同一块或循环重复观察条件
- **THEN** guard 保留原始 ordinal 和 invocation/multiplicity，不按目标块合并选择，也不把 repeated/unknown guard 用作单次互斥证明

### Requirement: Register original local nodes separately from LLVM analysis evidence

P2 SHALL 在独立 ir_nodes 中登记同 BC 的全部原始指令及 block/opcode/type，复用共享 ID；SHALL 在 analysis_evidence 中以显式 analysis_id 登记 LLVM 生成节点及来源/输入/查询结果。SHALL 区分 MemorySSA 候选依赖、AA-backed clobber、支配关系与确定值证明，不改变 P1 v2 的根闭包和原始 ID。登记超出 local_steps 或分析失败 SHALL 返回可定位 job 错误，不发布悬空或伪完整登记。

#### Scenario: An unused alloca is absent from P1 values

- **WHEN** 原始 BC 含未使用 alloca，P1 根闭包未物化该指令
- **THEN** P2 登记原始指令并允许局部对象引用，P1 values 不变，任意未登记 ID 仍拒绝

#### Scenario: MemorySSA creates nodes without original instructions

- **WHEN** LLVM 生成 live-on-entry 或 MemoryPhi（包括循环回边）
- **THEN** 使用不同于 SourceRef 的 AnalysisRef，保留同函数来源和成对前驱/依赖，不伪造原始 IR 指令或确定 reads-from

#### Scenario: Local evidence construction exceeds its budget

- **WHEN** 登记工作项超出显式收紧的 local_steps，或局部分析失败
- **THEN** 该 job 失败且计划项保留，不输出可被当作完整事实的截断表；无布局/动态大小仅保留范围 unknown

### Requirement: Require singleton allocation evidence for local strong updates

局部对象 SHALL 区分 alloca 源位置与抽象分配实例。single 分配必须隶属 single 调用且不代表循环重复分配；merged/unknown 对象 SHALL 不作为强更新或确定别名/不别名证明。单例性仅是必要条件，不替代范围、存活、非逃逸和到达定义验证。

#### Scenario: An alloca is repeated within one activation

- **WHEN** 单一调用中的循环重复执行同一 alloca，或递归摘要合并该分配位置
- **THEN** 保留原始 source 并标记合并分配，不因外层调用或 source 唯一而将局部读取转发为确定值

### Requirement: Produce verified local analysis supplements without mutating raw facts

系统 SHALL 使用锁定 LLVM 21.1.8 API 读取经 hash/parse/verify 校验的原始 BC，生成独立 LocalAnalysisFacts v1，记录 artifact、BC/ModuleFacts digest、extractor、LLVM、analysis/policy 和模块预算；上下文输入/结果由独立局部求值协议承载。SHALL 通过批量局部请求复用 LLVM 分析，不以正则解析 IR 或每操作数独立进程代替；SHALL 保留原始指令/函数身份，不变换原始 BC、覆盖 ModuleFacts v2 或改变其 extraction/capabilities。

#### Scenario: The same module is analyzed repeatedly

- **WHEN** 原始 BC、v2 facts、局部请求和策略完全相同且未触发墙钟限制
- **THEN** 补充产物的语义内容、身份、排序和原始指令引用稳定，原始 BC/facts 内容不变

#### Scenario: Bitcode changes during local analysis

- **WHEN** BC 与 manifest 的 hash 不同或分析前后 hash 改变
- **THEN** 拒绝发布该补充产物，报告 inputs_changed，不作为成功缓存命中

### Requirement: Export exact function eligibility and supported ABI semantics

补充分析 SHALL 保留精确 linkage、COMDAT/selection、visibility、dso_local、声明/定义及 LLVM 可替换性/精确定义查询依据，结构化函数和调用点类型、calling convention、参数/返回属性、nounwind/noreturn 等控制信息。SHALL 按版本化支持表将属性分为已建模、已审核可保守忽略、不支持；未知属性默认不支持，不将原始 ABI unknown 静默改成已知。

#### Scenario: Ordinary scalar calls carry noundef

- **WHEN** 非 vararg 的 C calling convention 直接调用使用受支持整数/指针参数、void/整数/指针返回并携带 noundef
- **THEN** 校验接口后可保留参数关系和 noundef 前提，不推导 nonnull/noalias/固定数值，并记录对原始属性诊断的解释依据

#### Scenario: Unsupported ABI changes parameter passing

- **WHEN** 调用包含 byval/sret/inalloca/preallocated、vararg、未知 calling convention、musttail 或未支持 operand bundle
- **THEN** 保留接口与不支持原因，禁止仅凭参数位置进行确定替换，产生未知调用效果

#### Scenario: An invoke targets an adopted nounwind body

- **WHEN** 已有合法函数体采用边且适用 nounwind 属性被解释
- **THEN** 可依据该证据排除 unwind 边；没有该证明时保留异常路径和其未知影响，不把 invoke 自动等同普通 call

### Requirement: Resolve bounded objects and byte ranges conservatively

系统 SHALL 表达带 artifact/scope/context 身份的 global、parameter、local 和 unknown 对象及地址空间、常量偏移/unknown、访问长度；SHALL 补充 alloca 分配范围。SHALL 仅在对象身份和范围证据充足时判断 overlap/disjoint，不把可计算 GEP 当作 in-bounds/生命周期/别名证明，不默认不同形参互不别名。

#### Scenario: Constant fields overlap or are disjoint

- **WHEN** 同一确定对象的两次访问具有已知常量字节范围
- **THEN** 按 DataLayout 和半开区间输出 overlap/disjoint，保留零长度访问语义，不以源码字段名判断

#### Scenario: Object identity or pointer conversion is uncertain

- **WHEN** 地址来自可能相同的两个形参、动态 GEP、未知 inttoptr 或未解释地址空间转换
- **THEN** 保留可能别名/unknown 与原始关系，不因参数编号不同或剥离 cast 输出确定不重叠

### Requirement: Propagate values through proven private local storage

系统 SHALL 支持受限非逃逸普通栈槽的 store/load 传播，包括确定标量和常量不重叠子范围；强更新 SHALL 要求分配/访问范围、初始化、到达定义和无可能覆盖证据。SHALL 在 CFG 合流/循环合并候选，在逃逸、lifetime 结束、部分重叠或未知别名破坏条件时使受影响值未知，不执行无依据的字节拼装。

#### Scenario: An O0 parameter passes through multiple stack slots

- **WHEN** order 形参经多个已证明私有标量栈槽 store/load 到达 switch
- **THEN** 保留从形参到 switch 的值关系，给定确定实参时筛选可达边，证据能回溯每个必要的局部定义

#### Scenario: A stack value is uninitialized or invalidated

- **WHEN** 读取之前不存在确定初始化，或地址逃逸、生命周期结束、部分重叠写/未知调用可能覆盖读取范围
- **THEN** 不返回旧常量，记录相应 unknown 原因；未逃逸且不能被该调用触及的其他私有栈槽不被无依据全部清空

#### Scenario: Branches store different values

- **WHEN** 两条尚未排除的 CFG 路径向同一局部栈槽存入不同常量
- **THEN** 合流保留候选及条件，不能任选最后遍历的一次 store；达到候选/路径预算时保守降级

### Requirement: Preserve LLVM value semantics and concurrent observation boundaries

系统 SHALL 使用精确位宽及 LLVM 整数/flags 语义解释受支持算术、比较、phi/select/cast/GEP；SHALL 区分 poison/undef/freeze 和未知，不以宿主整数截断或任意选择值完成路径证明。共享/global、atomic 和 volatile load SHALL 不从静态 initializer 或词法前序写进行确定值转发；局部 MemorySSA 关系 SHALL 不被当作线程 HB 或 reads-from。

#### Scenario: Arithmetic cannot yield a valid definite constant

- **WHEN** 传播涉及宽整数、nsw/nuw/exact 约束违反、非法 shift 或 poison/undef/freeze
- **THEN** 使用精确位宽处理支持运算，其余保留相应未知/特殊语义，不据猜测常量删除可达效果

#### Scenario: A shared or atomic value appears locally predictable

- **WHEN** 全局已有 initializer 或先前 store，后续存在共享普通/atomic/volatile load
- **THEN** 不把该 initializer/store 当作读取确定来源，保持符号观察及原始内存事件，不生成并发同步关系

### Requirement: Preserve conditional local effects and explain unresolved facts

系统 SHALL 导出受 guard 限制的局部效果、返回关系和 normal/unwind/noreturn 出口，保留原始内存事件及已知先后关系；无法解释的 reachable 操作/调用 SHALL 产生未知效果。原始 partial 诊断 SHALL 保留，只有以支持规则解释或证明对特定上下文不可达/不相关后才允许不影响该上下文摘要完整性，并记录诊断到证据的对应关系。

#### Scenario: An unknown operation remains reachable

- **WHEN** 请求路径包含未支持操作、opaque asm/intrinsic 或未采用调用体
- **THEN** 保留已知效果并增加可定位未知影响，局部结果 partial，不以空效果表示该操作

#### Scenario: An unsupported exception block is proven unreachable

- **WHEN** 合法采用边和控制属性证明该上下文的异常块不可达
- **THEN** 保存排除证明和原始诊断，允许相应上下文不受该缺口影响，但不更改 P1 extraction 状态或其他上下文
