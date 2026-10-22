## Context

现有 C++ extractor 保留事件、CFG 后继、调用符号和常量 GEP 索引；Python 的 `contracts.py` 使用全局 schema v1，`pipeline.py` 在 collect/import 路径硬编码版本，scope/link 也有独立身份规则。扩展事实必须同时解决消费校验与缓存隔离，否则旧 worker 或旧 JSON 可能被误当作完整新事实。

环境继续锁定 LLVM 21.1.8、C++20、Python 和已有独立开发容器。本设计不需要外部分析框架；根据已有代码和路线定义数据契约，具体 LLVM API 调用在实施中以锁定 SDK 编译和固定 IR 单元测试验证。

## Goals / Non-Goals

**Goals:**

- 提供可引用、可验证、确定性的原始值/条件/调用/范围事实，使 P2 不必从字符串或源码名称反推这些信息。
- 保留原始内存事件、配置/profile、debug、范围和 unknown 边界；结构完整与内容可解释程度分别报告。
- 明确 ModuleFacts v1→v2、extractor 协议和缓存失效行为，覆盖 collect、import-bc、index、link、doctor 全部入口。
- 提供每项需求到单元/集成验证的映射，实际执行全部自有代码至少 90% 行/可用分支覆盖率门槛。

**Non-Goals:**

- 不做常量传播求解、mem2reg 优化、路径可行性判断、调用点特化、函数效果摘要、points-to/alias 结论、线程/MHP/HB/rf 或风险判定。
- 不新增语义分析 CLI，不推断 scope，不执行最终程序/原生链接，不声称 GCC 重放与 Clang 语义等价。
- 不接入新分析后端，不升级 LLVM/标准库，不整合生产容器，不修改旧 checker、历史实验字节或仓库根配置。

## Decisions

### D1. 保持 C++ 原始提取与 Python 编排分层

C++ 使用 LLVM IR API 和 DataLayout；可将 `facts.cpp` 拆为值图、内存布局和主提取模块，头文件尽量仅声明。Python 负责 schema/跨引用校验、身份、完整性汇总和来源映射，不计算 LLVM 类型布局。当前 JSON 进程边界保留，不增加 FFI 或第三方依赖。

备选的“导出全部 IR 文本后 Python 解析”缺少可靠类型/操作语义；“引入全程序框架”超出 P1。P1 也不需要为了值引用立即引入 AliasAnalysis 或 MemorySSA 求解；O0 中 store/load 的地址与操作数先原样保留，内存值传播留给 P2。

### D2. ModuleFacts v2 的值图是有类型的原始关系，不是求解结果

以下是实施契约的最低字段族，最终 JSON Schema 和有效/无效样例必须在功能实现前落地。`values` 使用节点表与 ID 引用，不递归嵌套完整 SSA 图。

| 字段族 | 最低内容 |
| --- | --- |
| 值节点 | `id`、`kind`、类型描述、解释状态；参数的函数/位置，指令的 opcode/块/操作数及相关 flags |
| 整数常量 | 位宽和保留完整位模式的十六进制字符串；不使用 JSON number 保存可能超过 53 位的值 |
| 指令关系 | phi 的 value/predecessor 对，select 的 condition/true/false，cast 的源/目标类型，icmp 的 predicate，GEP 的源元素类型/基址/索引/inbounds，整数算术/位运算及 nsw/nuw/exact 等适用属性 |
| 复合值 | 有界 aggregate 元素或 compact zeroinitializer；extractvalue/insertvalue 索引，特别是 CAS 的旧值与成功位 |
| 特殊值 | null、undef、poison、freeze 与 unsupported 节点明确区分；不将它们替换为常量零 |
| 函数接口 | 参数序号/类型/value 引用、返回类型、vararg、每个 ret 的返回引用或显式 void |
| 全局初始化 | declaration/no-initializer 与定义的 initializer 引用；支持整数、零初始化、指针常量和有界聚合，其他形式带原因 |

LLVM 整数类型本身不赋予源代码 signed/unsigned 属性；由 icmp predicate、sext/zext 和相关操作提供解释依据。浮点及当前不支持的 vector/target-specific 操作记录类型/opcode和 unknown 原因，不伪造运算语义。指针常量表达只解释已支持的 GEP/cast，其他保留 unsupported。freeze 只记录关系，不在 P1 选择其运行值。

采用两遍登记：先按模块遍历建立符号、参数、块和指令 ID，再从内存操作数、调用目标/实参、返回值、条件和全局初始化等根收集所需 SSA 闭包；循环 phi 用引用，不递归展开。常量按完整类型及内容作模块局部 canonical 标识。无关 debug 元数据不进入闭包；不支持但被引用的指令生成可解析的占位节点，不能丢掉引用。

同一 artifact 和 extractor 内保留现有 `:symbol:`、`:bN:iN` 位置 ID；语义 graph 中的 instruction result 复用对应指令身份。跨版本/重新编译导致 ArtifactKey 改变是预期失效，不承诺历史 ID 字符串相同；不同 profile 永远不合并。所有返回 JSON 字符串须拥有存储，不能借用 Module 释放后失效的 StringRef。

### D3. 条件边与调用接口保留原始区分

块保留原有 successors，新增 terminator 与 edges；edge 包含 terminator ID、后继序号、目标块、边种类和条件引用。br true/false、switch case/default 分开，即使多个 case 指向同一块也不合并；case 值使用精确整数表示。默认边表示“未匹配其他 case”，不展开求解条件。ret/void/unreachable 分别记录。

call/invoke 保存 called operand（间接调用也有引用）、原有 direct target、实参顺序、返回值引用或 void、函数类型和 calling convention。invoke 明确 normal/unwind 后继，不能把异常路径变成普通返回；未支持的 callbr/EH terminator 保留实际后继及 unknown reason，不声称已建模其全部控制语义。适用的 ABI 参数属性、operand bundles 和 tail 标志须保留为结构事实或显式 unsupported 诊断，不默默丢弃其存在。

O0 包装验收只验证调用点常量、包装参数、局部 load/store、比较与分支关系均可追溯。P1 不要求沿内存槽推导出唯一 order，不根据函数名猜测包装语义，不设置 `callsite_specialization=true`。

### D4. 范围依据 DataLayout，数值已知不等于访问合法

每个内存访问保留 address value 引用及原有受限对象视图，新增 access size、alignment、address space；标量/固定向量大小采用 DataLayout 的存储大小，而非手工用类型位宽除 8。常量 GEP 使用类型布局和地址空间 index 位宽获得字节偏移，保存带位宽的精确表示和有符号显示解释；不截断成宿主 int64。记录布局来自 BC，不从目标 triple 猜一个布局。

访问大小、GEP 偏移均用 tagged 结果区分 known/unknown/not_applicable；fence/不透明效果没有普通访问范围，未知长度不等于零。动态 GEP、scalable 类型、缺少可靠布局、超预算或不能安全解释的 addrspacecast/inttoptr 保留 reason 与原始操作数。不得用 stripPointerCasts 抹去地址空间变化再声称同一确定对象。

计算常量负偏移只是地址表达事实，不证明 in-bounds、对象仍存活、两个指针不别名或不会发生 poison。保留 GEP flags，P1 不产生对象重叠/无冲突结论。

load 保存结果；store 保存值；RMW 保存输入/旧值结果；CAS 保存 compare/new/result 及 extractvalue 使用链，继续保留 success/failure order、weak、scope。memcpy/memmove 分别保存读源和写目的的地址空间/对齐与共同长度引用，memset 保存填充值；长度常量零与动态未知明确区分。全局 initializer 只代表静态 IR 初始化，不能视为已经执行 C++ 动态初始化或线程启动前必然赋值。

### D5. 有界提取、引用闭合与完整性各自可验

建议首版 extraction policy 固定并版本化：最多 100000 个值节点、500000 条值操作数引用、常量嵌套深度 64；继续使用现有 worker 时间预算及 16 MiB JSON 上限。这些是实现保护参数，不是性能或业务覆盖承诺，边界测试可注入较小预算。

支持范围外的值/操作保留合法 unknown 节点与原因，ModuleFacts 的 `extraction` 记录 policy、status（complete/partial）、roots/nodes/unknown 计数和有 ID 的 diagnostics。分母是明确列出的所需根/节点，不声称统计 LLVM 全部语言语义。partial 指范围中存在未解释事实；complete 只指本版本支持的结构提取完成，不是语义正确性分析完成。

常量深度超限可返回带原因的叶节点并标 partial；节点/引用总量超限或序列化超过上限时整个 TU 事实提取失败，诊断 `extraction_budget_exceeded`，不发布残缺 facts，不把缺少的节点留成悬空引用。时间超限仍为 timed_out。局部 unknown 不是结构错误；重复 ID、悬空引用、跨函数非法参数/指令引用、phi 前驱或 edge 与 CFG 不一致则是 `invalid_reference`，消费者拒绝。

JSON Schema 负责结构/枚举/必填字段；独立引用校验负责闭合和所属关系。对 worker 输出及 index/link 从磁盘加载的事实都执行，不能只在 collect 校验一次。

### D6. 按 kind 升级并统一所有产物身份路径

版本表：ModuleFacts=2、RunReport=2；BuildSnapshot/TUManifest/BCArtifact/ScopeManifest/ScopeIndex 仍为 1。此版本调整已获用户确认：旧 RunReport 顶层禁止未知字段，新增 fact_extraction 不是 v1 兼容扩展。其他 v1 对象仅使用已有允许扩展的元数据位置；严格 schema 与测试同步更新。旧 ModuleFacts/RunReport v1 和未知未来版本明确拒绝，不提供伪装的 JSON 自动迁移器。旧报告保留为历史证据，不填造提取状态；事实迁移方式是使用已有可信 BC 重新读取或从源码重新 collect。

extractor 初始升级为 0.2.0，采用单一受版本控制的协议元数据源，由构建生成或核对 C++/Python 使用的一致值。内部 worker 新增机器可读协议查询（例如 `--protocol`），保留 `--version` 的 LLVM 版本行为。doctor 与处理输入入口检查 worker 的 LLVM、facts version、extractor 和 policy；版本或查询不匹配立即诊断，不能仅看到同一 LLVM 就接纳旧 worker。

| 入口 | 身份与失效策略 |
| --- | --- |
| collect/缓存命中 | ArtifactKey 纳入 facts version、extractor、policy；继续保留上下文/输入/SDK/profile。升级后旧缓存自然 miss，不扫描删除旧文件 |
| import-bc 无 manifest | 新 key 由实际 BC hash 与当前提取身份形成，provenance 仍 unknown；不得因重新提取升为 verified |
| import-bc 有旧 manifest | 保留并核验 hash/context/profile/inputs/provenance；由旧 key 与当前身份派生新 key，记录旧 key 及既有 lineage，保留祖先重叠拒绝能力 |
| import-bc 有当前 manifest | 在提取身份及 hash 一致时保持 key；重复导入不无限追加相同祖先，身份算法必须可重现 |
| index | 强制 v2 引用校验；index 身份纳入 facts/extractor/policy 与 index 版本，拒绝异代混合输入 |
| link | key 纳入链接范围、linker 和提取身份；新 linked BC 再读取为 v2，保留所有输入祖先；不修改 triple/layout |

BCArtifact 的 toolchain 元数据记录提取身份。scope 仍显式引用 ArtifactKey：重采集或导入重键后，用户应使用报告映射更新 scope，不能自动替换用户目标成员。本 change 不建立通用跨历史别名映射：缺 lineage 的输入继续 unknown，不按 BC 文件名猜祖先。

备选“全对象统一升 v2”制造不必要迁移；“只改 JSON 字段，不改 key”让旧缓存/旧 worker 混入。按 kind 版本表与显式重新提取兼顾现有接口与正确性。旧 v1 manifest 保留可读，旧 v1 facts 保留为历史文件而非新消费者输入。

### D7. 报告显式升级且不提前进入风险分析

RunReport v2 增加必填 `fact_extraction` 汇总，记录 complete/partial/failed/not_run、模块计数和原因，保留原有字段含义但不承诺旧 v1 消费者读取新报告。成功 parse/verify 与事实部分可解释独立表达；缺 debug 仍只影响原 source_mapping。对请求新事实的 collect/import/index/link，partial 事实输出退出 2；全部无法提供可用请求结果退出 1；无相关缺口退出 0。有效部分产物可保留，但不能伪装完整；未知地址的既有约束不被消除。

`semantic_analysis=not_run`、`safety=not_evaluated`、`findings=null`、points_to/effect_propagation/callsite_specialization/threads/memory_model=false 不变。新增结构能力标志只描述 values/conditional_cfg/call_operands/memory_ranges，不能与真正的值流求解能力混淆。doctor 的 fact_extraction 为 not_run。

### D8. 验证分三层且覆盖所有自有执行逻辑

1. C++ 固定 IR 单元测试：值身份/循环/宽整数/poison/undef、条件边、实参/返回/异常、范围/layout/CAS/intrinsic/初始化、预算/无 debug/Module 生命周期。断言精确字段和引用，不靠“结果非空”。
2. Python 单元测试：按 kind schema、值引用所属/完整性、collect/import/index/link 的版本与身份、旧 worker、scope 更新提示、汇总退出码和预算错误。缓存、失败路径、质量工具及历史 probe 继续纳入。
3. 镜像内独立集成：GCC/Clang × C11/C17/C++17/C++20 compile-only，多 TU 的调用实参记录，O0 原子包装原始关系，两个 profile 分离，旧数据拒绝与真实 BC 重提取。固定 IR 的异常/宽数/layout 样例弥补 C 源码无法稳定生成的结构。不运行被分析程序，不 SSH。

每项 spec scenario 映射到具名测试和断言目的，保存到 `doc/SEMANTIC_FACTS_ACCEPTANCE.md`；行为/迁移说明写 `doc/SEMANTIC_FACTS.md`，实际命令、覆盖率、未通过项和报告位置写 `doc/SEMANTIC_FACTS_VALIDATION.md`，更新 README/文档索引及路线状态，不改写 FOUNDATION 的历史结果。

继续使用 GoogleTest/llvm-cov、pytest/coverage.py 的单元 profile。枚举全体自有可执行源（含新增文件、未加载模块、必要时的可执行头文件），构建目标须包含所有自有 C++ 实现；只允许排除第三方、自动生成物及纯测试输入并记录理由。整体按计数汇总、各语言及每个模块行/支持的分支均至少 90%；集成 profile 不混入，缺报告或未枚举模块必失败。新增目录/头文件实现若超出现有枚举方式必须同步补强门槛，不能为了省测试把逻辑放在统计范围外。

## Risks / Trade-offs

- [SSA/O0 存储关系被误称求解结果] → 只记录原始操作数/地址链，明确无 mem2reg、路径选择和调用点特化。
- [大整数/负 GEP 在 JSON 或宿主整数中截断] → 位宽加精确字符串，边界断言，不以 double/int64 作通用表示。
- [循环 phi、深层常量或巨大输出耗尽资源] → 两遍节点引用、visited、固定 policy 与预算失败，不发布悬空图。
- [未知 operation 过多使普通 C++ 结果 partial] → 保留逐项原因，先明确可用子集；不得隐藏 unsupported 以提高成功率。
- [新 worker 配旧编排或旧 linked/import key] → 机器协议检查和所有入口版本单元测试，检查双方身份而不只检查 LLVM。
- [重键丢失 object/linked 重叠证据] → 继承 lineage、重复导入幂等测试和新旧祖先交叉测试；未知仍未知。
- [GEP 数值可计算被误作合法对象证明] → 独立保留 flags/地址空间和 unknown，不输出 alias 或安全结论。
- [提取器拆分后覆盖率漏统计] → 构建/源码清单对照及未调用文件/可执行头文件检测；90% 门槛不降低。

## Migration Plan

1. 先落地 v2 字段/引用协议、版本元数据和单元夹具，明确不兼容边界；保持主规格和历史归档不改写。
2. 实现值图、控制/调用、范围及预算；同步 C++ 单元测试。再接入 Python schema、协议、身份和报告，更新消费入口。
3. 从新的输出目录运行质量入口与真实编译集成，保留旧缓存、旧 reports 和旧 scope。用户可重新 collect 或 import-bc，并按返回新 ArtifactKey 更新显式 scope。
4. 更新当前使用文档和规划状态，记录实际验证与未知项；验收全部通过后才提示 sync/archive。此提案阶段不自动 apply。
5. 回退时使用原 extractor/编排及原产物目录，停止消费 v2；不做 v2→v1 的有损转换，不删除用户数据或修改被分析源码。

## Open Questions

- 首版固定预算是保护性默认值，需在锁定容器中用有界样例记录时间/内存；若需要改变默认值，更新 policy 身份和测试，而非静默放宽。
- 标准库 O0 包装的实际形态需用当前锁定 libstdc++ 编译确认；验收范围是原始关系齐全，不要求可传播到唯一 order。新的标准库支持或求解需求另归 P2。
- v2 schema 的具体小字段命名以实施第一步产出的 schema/样例为准，但本设计要求的字段族、版本行为、引用语义和 unknown 边界不得削减；若无法实现，应更新提案并报告原因，不能悄悄转为字符串输出。
