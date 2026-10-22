## 1. 兼容性基线与 P4 协议

- [x] 1.1 固化 P1 `ModuleFacts v2`/`RunReport v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1`/`ThreadAnalysisReport v1` 及现有 CLI 的黄金输入输出，增加逐字节和语义回归，证明 P4 不修改旧 kind、身份、缓存、退出码或 `safety/findings`。
- [x] 1.2 定义 `PublicationRiskRequest`、`PublicationLocalFacts`、`SinglePublicationProtocolGraph`、`PublicationRiskReport` v1 schema，以及 `analysis_version=0.1.0`、`single-publication-risks-v1`、`c-cpp-single-publication-v1`；测试合法、缺字段、未知字段/kind、未来版本及中英文字段成对约束。
- [x] 1.3 实现 P4 canonical identity、确定性排序和 BC/P1/P2/P3/P4 跨层 SourceRef/AnalysisRef/Effect/Invocation/ThreadInstance/Object/Guard 引用闭包校验，覆盖悬空、跨函数/实例、陈旧 generation、错误角色、混合 profile 和伪造 digest。
- [x] 1.4 定义局部事实、成功观察、协议候选、assessment、frontier、计数和状态的稳定 ID/枚举，测试输入乱序、重复 ID、相同模板不同实例、零分母及 unknown 不得折叠为 absent。
- [x] 1.5 扩展 worker 协商和批处理操作，保持 P1/P2/P3 操作不变；测试旧 worker、新旧 policy、调包/遗漏/重复响应、stdout/stderr 隔离、超时和输出上限。

## 2. LLVM 初值与发布值局部事实

- [x] 2.1 在只读且 hash/parse/verify 校验的 BC 上登记 plain/atomic load/store 的对象基址、偏移、范围、位宽、order 和 syncscope，并与 P1/P2 原始事件身份核对；覆盖 exact、部分重叠、动态地址和 DataLayout 缺失。
- [x] 2.2 使用 LLVM Constant 与 DataLayout 提取 flag 访问范围对应的零值、整数、聚合子对象初值，测试 C `_Atomic`、C++ `std::atomic` 常见直接 IR、padding/endian、动态初始化和未知布局，未知不得默认为零。
- [x] 2.3 提取 store 的精确整数/布尔发布值及受支持 cast 后值，测试位宽、符号无关位模式、截断/扩展、poison/undef/unknown 和候选预算。
- [x] 2.4 为 initializer/value 事实登记最小 LLVM analysis evidence 和独立 AnalysisRef，验证 owner、输入节点、范围、digest 与原始/分析命名空间不冲突。

## 3. Observation 值依赖与成功 gate

- [x] 3.1 实现 load 结果沿 `icmp eq/ne`、zero/nonzero、布尔反转和语义保持整数 cast 的有限传播，输出规范化成功谓词；测试真假边反转、常量左右位置、非法 cast、算术变换和候选超限。
- [x] 3.2 实现 phi/select 的有限 observation 候选合并与互斥 guard，测试单候选、多候选、循环回边、矛盾 guard、unknown arm 和预算确定性。
- [x] 3.3 使用 CFG、DominatorTree、PostDominatorTree 和 LoopInfo 提取 branch/switch 成功/失败 edge、循环重试和成功 edge 控制区域，覆盖 if、while、do/while、提前返回、两边可达和 payload 先于 gate 的反例。
- [x] 3.4 创建独立 `SuccessfulObservation` 分析节点，绑定原始 read、invocation、ThreadInstance、谓词和成功 edge；测试重复 load 保持 repeated/may、不同动态成功条件身份隔离及不得暗示实际执行/reads-from。
- [x] 3.5 实现 observation 到直接正常 return 的局部依赖接口，区分 normal/unwind/noreturn；测试布尔 wrapper、compare wrapper、多 return、递归、异常和未知返回。
- [x] 3.6 沿 P2 确定 direct callee adoption 与 P3 invocation/anchor 组合跨 TU return wrapper，测试 closed scope 唯一定义、ODR 合同、开放边界、多定义、间接调用、ABI 不兼容和 SCC 超限。
- [x] 3.7 为 observation/gate/return dependency 的正常、边界、失败和 unknown 路径补齐 C++ 单元测试，并校验成功 sidecar 不含悬空或截断但标 complete 的事实。

## 4. 局部预算、传输与消费边界

- [x] 4.1 实现 P4 局部节点、值/谓词候选、wrapper/SCC 轮次、worker 秒数和输出字节预算，测试边界值、显式收紧、已知结果保留、非空 frontier 和无法闭包时 job failed。
- [x] 4.2 实现 Python worker 调度、请求/响应快照绑定、失败隔离和 publication sidecar 写入，覆盖部分成员失败、输入 ABA 变化、进程失败、非法 JSON 和未来协议。
- [x] 4.3 实现 `PublicationLocalFacts` 磁盘/缓存消费校验，拒绝错误 scope/profile/budget、陈旧 P1/P2/P3、AnalysisRef 伪造和跨 artifact 依赖。
- [x] 4.4 增加相同输入/预算重复运行的确定性测试，验证语义 JSON 和 identity 稳定、运行时间/日志不进入语义身份。

## 5. 一次性发布候选构造

- [x] 5.1 建立 effect/source/invocation/thread/object 索引，将 P2 effect 值与 multiplicity、P3 ThreadEffect/MHP/order、P4 observation/gate 绑定；测试同模板多 ThreadInstance 不泄漏旧实例。
- [x] 5.2 按同根线程、可能并行、精确 flag/payload 范围和成功控制依赖生成协议计划及候选，测试改名 flag 等价、不同 flag/payload 排除、单线程和已证明 join 后不并行。
- [x] 5.3 实现唯一发布写者枚举、single multiplicity 和 accepted-value 写集合，覆盖一个写者、多写者、同一 effect repeated、递归/循环 merged 实例、开放边界和未知 clobber。
- [x] 5.4 组合 publisher payload write → flag store 与成功 observation → consumer payload read 的独立执行顺序；测试 same-block、跨块、跨确定调用、may/unknown、反向 must-before 和不得读取 P2 order 作为充分证明。
- [x] 5.5 为候选保存 guards、路径、对象/范围、语言/编译配置、所有排除原因及 planned/evaluated/unknown 分母，测试零候选为 null 而非 100%。

## 6. 受限 reads-from 唯一化与发布证明链

- [x] 6.1 实现成功谓词对精确初值/发布值的有限求值，覆盖 eq/ne、zero/nonzero、布尔反转、位宽不兼容、初值也被接受和发布值被拒绝。
- [x] 6.2 仅在初值排除、发布值接受、唯一 accepted writer、无重复/RMW/CAS/clobber、closed boundary 和 compatible system scope 时生成候选级唯一 reads-from；测试每个前提单独缺失均降级且不回写 P3。
- [x] 6.3 实现 store release-capable 与 load acquire-capable 资格表，覆盖 release/acquire/seq_cst、monotonic relaxed、unordered、consume、singlethread 和非法操作/order 组合。
- [x] 6.4 组合 payload 写 → release 发布 → 唯一 reads-from → acquire 成功观察 → payload 使用的条件化证明链，输出 `discharged-within-single-publication-model`；测试正确 C/C++ 对照且不得输出全程序安全。
- [x] 6.5 增加 P2 order、P3 reads-from candidate、相邻源码和硬件指令相同均不能单独建立 synchronizes-with/HB 的负向回归。

## 7. 风险规则与保守降级

- [x] 7.1 实现已识别协议内普通 flag/payload 冲突的 `potential-data-race`，按重叠范围、至少一方写、可能并行和缺少完整 HB 判定；测试普通 flag 不得被当作有效原子通信。
- [x] 7.2 实现 relaxed/缺少 release、relaxed/缺少 acquire 的 `publication-order-risk`，测试 relaxed+普通 payload 同 protocol 分组 data race 与 publication risk。
- [x] 7.3 实现 `acquire-too-late`，要求控制 payload 的 observation 为非 acquire 且另一个 acquire 已证明位于 payload 使用之后；测试 acquire 在前、在后、不同 flag 和顺序 unknown。
- [x] 7.4 实现 `publication-store-too-early`，仅在 flag store must-before payload write 时 finding；无法证明 payload-before 不得用“缺证据”生成同类 finding。
- [x] 7.5 实现 all-atomic relaxed 的 publication-order-risk 且不产生 ordinary data race，覆盖不同 payload 对象和 atomic payload order 对照。
- [x] 7.6 将 consume、fence、RMW/CAS release sequence、多写者、重复发布、ABA、复杂 mutex、unknown synchronization、通用 alias、`std::thread`/RAII 和对象回收传播为 unsupported/unknown/frontier；测试未知既不充当同步也不被假设不存在。
- [x] 7.7 实现候选证明切片的完整性传播：相关缺口阻止确定 verdict，无关 TU partial 不删除局部 assessment 但降低顶层完整性；测试严重性与证据置信度独立。

## 8. 协议图、报告和双语诊断

- [x] 8.1 生成 `SinglePublicationProtocolGraph`，保存静态事件、成功观察、线程/对象、顺序、MHP、候选/唯一 reads-from、证明链、assessment、排除和 frontier；测试 schema、引用和排序确定性。
- [x] 8.2 生成 `PublicationRiskReport` 分层状态及成员/根/局部事实/计划/candidate/evaluated/finding/discharged/unknown/unsupported/excluded 明确分母，覆盖部分失败、全失败、零分母和预算截断。
- [x] 8.3 实现 `safety=not_established` 和 `risks_found`/`no_supported_risk_found`/`inconclusive`/`failed` verdict，回归零候选、零 finding、全部 discharged、缓存命中和 complete 均不得显示全程序安全。
- [x] 8.4 为每项 assessment 输出稳定 code、规则/模型、protocol ID、语言配置、线程/对象/事件、谓词、路径、已有/缺失边、假设、证据等级和 IR/source 位置；无 debug 时保留 IR 证据。
- [x] 8.5 实现所有用户诊断的 `detail/detail_en` 与可选 `suggestion/suggestion_en` 成对校验，测试翻译变化不影响身份、去重、规则和退出码；建议必须匹配普通/原子对象且不统一要求 seq_cst。
- [x] 8.6 实现失败时的小型合法 P4 报告，覆盖非法请求、结构错误、输出限制、全部 worker 失败和无法加载 P3 依赖。

## 9. 缓存、CLI 与退出码

- [x] 9.1 实现 P4 局部事实、协议模板和实例化图分层缓存 key，纳入 BC/P1/P2/P3、完整 thread request、scope/profile/boundary、语言模型、worker/policy、实际预算和传递依赖；测试 callee-only 变化、模型/预算变化、损坏/未来版本缓存。
- [x] 9.2 实现缓存模板命中后的 ThreadInstance、invocation、guard 和 SuccessfulObservation 重新绑定，测试不同 create site/父线程不复用旧实例身份。
- [x] 9.3 实现 `detect-publication-risks --request --artifact-store --output --worker`，解析相对 thread request、生成/复用精确 P3 依赖并拒绝非空输出、隐式 roots、目录最新图、scope 不一致及运行目标程序。
- [x] 9.4 实现新命令 `0=完整无 finding`、`3=完整有 finding`、`2=partial/unknown/unsupported`、`1=失败`，规定 partial 优先于 finding；回归 collect/index/link/summarize/model-threads 原 0/2/1 语义。
- [x] 9.5 验证 stdout 只有最终报告 JSON、stderr 日志隔离、输出路径确定且旧结果不覆盖；异常路径尽力发布结构合法报告。

## 10. 语言与构建身份

- [x] 10.1 从 artifact/编译记录登记 GCC/Clang 来源、分析 BC producer、target/layout、C/C++ 语言和显式 `-std`，测试 C11/C17/C++17/C++20、缺失/冲突标准、不同 profile 和不支持编译器。
- [x] 10.2 对缺少可验证标准、跨 C/C++ atomic 互操作或不兼容 ABI 的候选降级，禁止采用宿主默认标准；测试 source-preserving/build-faithful 不拼接证据。
- [x] 10.3 验证 compile database 只参与 TU 编译身份，P4 scope/跨 TU wrapper/写者枚举仍来自显式 scope 和边界，不从共同目录/头文件猜完整程序。

## 11. 固定语义矩阵与集成验收

- [x] 11.1 新增直接 pthread 的 C11/C17 和 C++17/C++20 单 TU 固定输入，覆盖普通 flag、relaxed+普通 payload、release/acquire、seq_cst、fence、过晚 acquire、改名 flag和 all-atomic relaxed。
- [x] 11.2 新增发布过早、不同 flag、多写者、重复发布、初值等于发布值、单线程、成功 join 后访问、unknown call 和相关/无关完整性缺口的成对反例。
- [x] 11.3 新增三个或更多物理 TU 的 producer/consumer/observation wrapper，覆盖确定 direct return、不可解析 wrapper、无 debug、closed/open scope 和配置/profile 冲突。
- [x] 11.4 为 CASE0–CASE7 pthread 等价矩阵逐项断言候选、finding/discharged/unknown、证据链、分母、verdict 和退出码；期望来自语言语义与人工核对，不采用 DevKit 数值作真值。
- [x] 11.5 保留现有 `std::thread` publication 实验为 IR 表达回归，并断言 P4 端到端不得借其声称支持 std::thread。
- [x] 11.6 离线运行完整 compile-only → P1 → P2 → P3 → P4 集成，不依赖网络、SSH、DevKit、llvm-link、原生链接或执行目标程序；集成结果与单元覆盖 profile 分别记录。

## 12. 质量、文档和交付验证

- [x] 12.1 为所有新增、修改或复用的 C++/Python/schema/cache/CLI/report/quality 逻辑补齐有效单元断言，覆盖正常、边界、异常和 unknown；更新质量枚举以包含未加载的新源码和可执行头文件。
- [x] 12.2 运行 C++ 与 Python 全部单元测试、文档/链接检查和独立 P4 集成测试，修复所有失败；编译冒烟或集成通过不得代替单元测试。
- [x] 12.3 在独立开发容器使用新的持久输出目录执行 `python3 -m memory_order_analyzer.quality --output <new-directory> --integration`，确认项目整体、Python、C++ 及每个受影响模块行/分支 hit/total 均至少 90%；不足时不得勾选并须补测后换新目录重跑。
- [x] 12.4 编写 `doc/SINGLE_PUBLICATION_RISKS.md`，说明协议/CLI/产物、LLVM 与自研边界、成功观察、唯一 reads-from、风险分类、unknown/预算、退出码、双语诊断和非全局安全边界。
- [x] 12.5 编写 `doc/SINGLE_PUBLICATION_RISKS_VALIDATION.md`，映射全部 requirement/scenario 到单元/集成断言，记录工具/语言/target、输入 hash、精确命令、测试数、完整性、逐模块覆盖率、报告位置和排除理由。
- [x] 12.6 更新 README、`doc/IMPLEMENTATION_ROADMAP.md` 和相关 P1/P2/P3 文档的真实阶段状态与链接；保留历史 DevKit/SSH 证据含义，不把扫描成功或零建议改写为正确性依据。
- [x] 12.7 校验全部 OpenSpec/文档相对链接、kind/schema/analysis/model/预算/退出码/支持边界一致性，执行 `openspec validate detect-single-publication-risks --strict`；所有实现、测试和覆盖率任务通过后才提示 sync/archive，并给出下一阶段完整命令。
