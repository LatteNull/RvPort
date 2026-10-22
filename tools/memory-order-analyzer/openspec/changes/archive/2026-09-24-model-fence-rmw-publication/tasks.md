## 1. 协议与兼容基线

- [x] 1.1 为 `FenceRmwPublicationRequest v1`、`AtomicSourceConstructFacts v1`、`AdvancedAtomicFunctionFacts v1`、`AdvancedAtomicLocalFacts v1`、`BoundedAtomicCommunicationGraph v1`、`AdvancedPublicationProtocolOverlay v1` 和 `FenceRmwPublicationReport v1` 增加 schema、manifest 登记、稳定 ID、digest 与引用校验。
- [x] 1.2 定义 atomic event/outcome、RF edge、MO constraint/assignment、release-sequence member、fence pairing、assessment、dependency denominator 和双语 frontier 的枚举与交叉字段约束。
- [x] 1.3 增加协议正常、边界、非法枚举、悬空/跨请求引用、陈旧 digest、伪 complete 和版本拒绝单元测试，并确认 P1–P4、A1–A5、R1–R3 黄金产物不变。
- [x] 1.4 固化 A6 0/3/2/1 退出码、`safety=not_established`、风险与 unknown 共存的既有 P4 聚合优先规则及其契约测试。

## 2. C/C++ 原子源码事实

- [x] 2.1 在 Clang source worker 中实现 C11/C17 `AtomicExpr` 的 canonical operation、对象、值、compare/desired、success/failure order、fence kind、宏/source range 和 C profile 提取。
- [x] 2.2 在 Clang source worker 中实现 C++17/C++20 canonical `std::atomic<T>` specialization、selected method/overload、spelled/canonical type、order 参数、声明来源及 libstdc++/libc++ profile/ABI 绑定。
- [x] 2.3 分类 atomic load/store/fence/RMW/CAS，排除用户同名类型/方法、默认名字匹配、未知 profile 和不受支持 overload，并生成明确 source frontier。
- [x] 2.4 将 A1 SourceIRBinding 与源码构造对齐为候选/精确绑定，保证 AST-only 只形成 source candidate/partial，不输出 RF/MO/SW/HB、risk 或 discharged。
- [x] 2.5 为 C/C++ source classifier、宏、alias、overload、动态 order、错误恢复 AST、同名负例、profile mismatch 和 AST-only 路径补齐独立单元测试。

## 3. LLVM 高级原子局部事实

- [x] 3.1 在 eager LLVM worker 中生成规范化 fence/atomicrmw/cmpxchg event，保留 instruction identity、object/range、ordering/failure ordering、syncscope、RMW operation、weak、guard 和 multiplicity。
- [x] 3.2 提取 RMW 输入/observed old value 和 CAS compare/desired/observed value/success flag，将 CAS 拆为互斥 success read-modify 与 failure read-only outcome。
- [x] 3.3 在 R3 worker 中增加独立 A6 function/context shard 和 demand layer，复用 lazy module parse/materialize，但不得修改或冒充 P1/R3 既有 fact 协议。
- [x] 3.4 实现 eager/R3 事件 identity 与语义规范化比较器，保证调度、cache hit、worker 顺序不进入 semantic digest。
- [x] 3.5 实现 `-O0` 标准库 dispatcher 的 source binding/guard/profile 归一化和 `-O2` direct lowering 等价检查，不按静态 IR 变体数制造动态操作。
- [x] 3.6 为 fence、整数 RMW operation、CAS success/failure、weak spurious、extractvalue/control、no-debug、异常/损坏 IR、eager/lazy 和 O0/O2 路径补齐 C++/Python 单元测试。

## 4. 按需编排与精确身份绑定

- [x] 4.1 从 R1/R1.1 root slice、R2 atomic handoff 和 R3 AnalysisDemandGraph 生成 A6 function/context demand，确保相关 fence 即使无 R2 对象 pair 仍被提取。
- [x] 4.2 组合 P3 ThreadInstance/MHP、A5 must/may/unknown runtime object、byte range/address space/lifetime 与 P4 flag/payload/gate，形成 candidate-specific dynamic event domain。
- [x] 4.3 对 must-singleton exact object 允许正式求解，对 may/unknown、union overlap、range/lifetime/call target 不完整和开放 scope 生成 candidate-relevant frontier。
- [x] 4.4 验证同一字段声明的不同运行时对象不合并、跨 TU 直接 wrapper 可绑定同一实例，以及无关失败不污染独立候选。
- [x] 4.5 为 root/demand 去重、fence demand、不同 ThreadInstance、同名字段实例、跨 TU 参数/返回/receiver、开放 scope 和依赖失败补齐单元测试。

## 5. 有界 RF/MO 求解器

- [x] 5.1 实现按 exact atomic object/range 分桶的事件域、初始化 modification、value/guard/path-compatible RF 候选和确定性排序。
- [x] 5.2 实现 MO 偏序、RMW/CAS-success 成员、CAS-failure 非成员以及 RMW 读取 MO 直接前驱的约束传播和 assignment 验证。
- [x] 5.3 为首版整数 `xchg/add/sub/and/or/xor` 实现精确有限 value transition；将未白名单 operation、动态位宽/值、浮点、指针和不闭合 transition 降为 frontier。
- [x] 5.4 实现对象、事件、RF edge、MO node/branch、assignment、guard、递归、CPU、wall 与输出预算；预算耗尽时保存已探索分母但禁止从子集 discharged。
- [x] 5.5 实现“全部闭合有效 assignment”消解和“存在完整有效反例 assignment”风险 witness 的量词逻辑，以及风险/unknown 并存保留。
- [x] 5.6 为唯一/多 RF、冲突 MO、RMW predecessor、CAS failure、guard 不相容、初值、竞争 modification、组合爆炸、确定性与预算边界补齐单元测试。

## 6. Release sequence 与 fence 证明

- [x] 6.1 实现版本化语言策略：C11/C17/C++17 接受连续同线程 modification 或 RMW，C++20 只接受连续 RMW，并把标准/policy version 加入请求、证据与缓存 key。
- [x] 6.2 在一般多写者拒绝前识别精确 release head/RMW follower 链；对竞争 head、plain writer、链连续性未知和开放 modification set 生成 frontier。
- [x] 6.3 实现 release-fence/acquire-fence、release-fence/acquire-operation、release-operation/acquire-fence 三类 pairing，要求 carrier write/read、精确 RF、局部 must-before、ThreadInstance 和 control/path 证据闭合。
- [x] 6.4 拒绝 `atomic_signal_fence`/`syncscope("singlethread")` 的线程间证明，对 target-specific syncscope 和需要全局 SC total order 的协议输出明确 frontier。
- [x] 6.5 为正确/错误 fence 位置、过晚 acquire、RMW follower 跨线程、同线程 relaxed store 的四语言差异、signal fence、target scope 和 seq_cst 局部/全局边界补齐单元测试。

## 7. P4 overlay、CLI、缓存与报告

- [x] 7.1 实现 `AdvancedPublicationProtocolOverlay`，只读引用 P4 protocol/candidate/assessment 并附加 A6 event、RF/MO、release/fence proof 或 frontier，不改写 P4 artifact。
- [x] 7.2 实现 A6 assessment 与双语 finding/reason/limitation/suggestion，完整展示依赖分母、反例或全称证明范围，并始终声明非全程序安全证明。
- [x] 7.3 实现显式离线 A6 CLI、输入/输出校验、0/3/2/1 退出码和确定性输出；禁止 configure、build、link、目标程序执行、网络或 SSH。
- [x] 7.4 实现 local-fact 与 solver-result 分层缓存，覆盖完整 digest/profile/ABI/target/DataLayout/标准/policy/function/context/object/依赖/预算失效边界，拒绝 partial、failed、开放搜索及损坏/陈旧条目。
- [x] 7.5 为 overlay 引用、P4 不变、风险/unknown 聚合、双语字段、CLI 各退出码、cold/warm 等价、缓存失效/损坏和 forbidden execution 补齐单元测试。

## 8. 四语言 truth 与回归语料

- [x] 8.1 建立 C11、C17、C++17、C++20 独立 fixture manifest、人工 truth、planned/completed/TP/FP/FN/abstention 分母和诊断断言。
- [x] 8.2 增加 direct release/acquire 基线、三类 fence、错误 fence 位置、RMW chain、C++20 release-sequence 差异、CAS success/failure、weak/spurious、signal fence 和 competing modification 用例。
- [x] 8.3 增加单 TU、物理跨 TU wrapper、no-debug、AST+IR、IR-only、AST-only、failed/open scope、对象 may/unknown、预算以及 cold/warm cache 用例。
- [x] 8.4 增加 `-O0`/`-O2` 与 eager/R3 规范化等价验收，并持续运行 P1–P4、A1–A5、R1/R1.1、R2、R3 既有四语言 truth 和黄金协议回归。
- [x] 8.5 为 GenMC、herdtools7、ARM DevKit 提供隔离、可选且版本化的录制/对照入口；环境不可用时记录 `not_run`，不纳入核心 oracle 或 required 在线门禁。

## 9. 单元测试与覆盖率 required gate

- [x] 9.1 枚举所有新增、修改或复用的 C++、Python、schema/引用、solver、cache、CLI、报告和质量脚本，确认每个自有执行模块均有正常、边界、异常及 partial/unknown 单元断言。
- [x] 9.2 更新质量入口以将未加载 Python、未调用 C++、新增子目录和可执行头文件纳入分母，并测试 89.99%、90%、缺失报告和逐模块不足的失败行为。
- [x] 9.3 在锁定开发容器的新输出目录运行全量单元测试，验收项目整体、Python、C++ 及每个受影响模块行覆盖率和分支覆盖率均至少 90%，且不混入集成 profile。
- [x] 9.4 独立运行四语言 truth、O0/O2、eager/R3、既有全量回归、cold/warm cache、schema/reference 和确定性门禁；任何失败均保持任务未完成。
- [x] 9.5 发布精确命令、工具/标准库版本和 hash、测试数、line/branch hit/total、源码范围、排除理由、truth 指标、完整性、预算、失败差距及新报告位置。

## 10. 文档与最终一致性

- [x] 10.1 更新 README、架构/协议/使用文档和 `doc/IMPLEMENTATION_ROADMAP.md`，说明 A6 数据流、证据边界、四语言差异、frontier、CLI/退出码和“非安全证明”语义。
- [x] 10.2 记录 A6 LLVM/Clang/语言标准依据、O0/O2 实测 provenance 与可选外部对照版本，严格区分观察结果、规范依据、设计推断和 unknown。
- [x] 10.3 运行 OpenSpec 严格校验、文档链接/示例/命令/schema 一致性检查和全仓相关回归，确认未修改既有协议且未引入 Windows/MSVC/clang-cl 或在线依赖。
- [x] 10.4 仅在全部实现、单元、双 90% 覆盖、四语言 truth、回归、缓存、文档和 OpenSpec required gate 通过后，更新 tasks/验证记录并准备 sync/archive。
