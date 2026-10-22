## 1. 冻结基线与新增协议

- [x] 1.1 固化 P1 ModuleFacts v2、RunReport v2、ScopeIndex v1 的黄金兼容性输入/断言，记录现有 LLVM/extractor/profile 身份；明确 P1 缺口不是已实现能力。
- [x] 1.2 定义 EffectAnalysisRequest、LocalAnalysisFacts、EffectSummary、EffectAnalysisReport v1 schema 和初始 analysis_version/policy；明确 context/invocation/allocation、模板空绑定和合并 cardinality；增加合法、缺字段、未知字段/kind/未来版本单元测试。
- [x] 1.3 实现派生引用、上下文/实例归属、原始诊断及依赖 digest 校验，覆盖重复/悬空/跨函数引用、循环 parent、合并实例伪造单例、hash 不匹配和 raw unknown 解释证据。
- [x] 1.4 接入独立分析 worker 协议协商和批量请求接口，保持旧 worker 提取操作/CLI 行为；测试旧 worker、错误 policy、日志/JSON 分离及协议失败报告。
- [x] 1.5 按已批准 D2b 增加 LocalEvaluationRequest/Result v1、CandidateDomain 及六 kind 握手；校验有限候选/unknown/bottom、guard/实参/实例归属、请求快照和依赖 digest、表达式结构预算，补充正常/边界/伪造输入单测并实际通过整体及受影响模块行/分支 90% 门槛。
- [x] 1.6 接入独立 --evaluate-batch C++ 操作与 Python 客户端，逐请求核验 BC/原始及局部代际、计划/结果匹配和错误信封；测试重复/遗漏/调包请求、预算/输出/超时、旧 worker 拒绝及 P1 v2 不变。

1.6 于 evaluation-worker-001 全量验证完成；客户端核验完整 P1 快照（含源码一致性补充）和依赖，worker 核验 BC 与重建的局部补充。后续任务已将该协议从初始 pending 计划推进到真实局部求值与跨 TU 摘要组合。

## 2. LLVM 局部补充能力

- [x] 2.1 复用原始 ID 登记并以只读 LLVM 模块生成局部补充产物，检查 BC 读取前后 hash/parse/verify；单测证明原始 facts、事件 ID 和文件内容不变。
- [x] 2.2 提取精确 linkage、visibility、dso_local、COMDAT/selection、LLVM exact-definition/interposable 依据；单测区分 linkonce/linkonce_odr、weak/weak_odr、声明/定义和可替换边界。
- [x] 2.3 结构化函数/调用点 ABI，完成 C calling convention 固定整数/指针接口及 noundef/nounwind/noreturn 支持表，审核可保守忽略属性；测试 byval/sret/vararg/musttail/bundles 等拒绝路径。
- [x] 2.4 接入 LLVM DominatorTree、AA/MemorySSA 及局部对象查询，导出 alloca 分配范围和局部依赖证据；测试 optnone/O0、无布局、动态大小和分析失败，不把 MemorySSA 当作唯一读取来源。

- [x] 2.5 按已批准 D2a 增加 P2 ir_nodes/analysis_evidence 及摘要/报告 local_dependencies；实现命名空间、归属、原始节点角色、补充 digest 和预算消费校验，测试未物化 alloca、MemoryPhi/回边、伪造/悬空/陈旧证据、预算失败及 P1 v2 不变。

实施顺序：先完成 2.5 的登记契约，再接入 2.4 的 LLVM 查询；当前 metadata 的 partial 不等同局部效果分析完成。

## 3. 对象和值域

- [x] 3.1 实现 global/parameter/local/unknown 对象、地址空间及独立 invocation/allocation 身份，补充 extern/static、同实参重复调用和循环 alloca 隔离单测；禁止参数默认 noalias、合并实例强更新或仅凭 ID 判定 must-alias/noalias。
- [x] 3.2 实现常量字段偏移及字节区间 overlap/disjoint/unknown，测试 padding、负/宽偏移、零/动态长度、部分重叠及未支持指针转换。
- [x] 3.3 使用 LLVM 精确整数语义实现受支持算术/位运算/比较/cast/GEP、有限候选与符号关系；测试宽整数、signed/unsigned、nsw/nuw/exact、非法 shift 和 poison/undef/freeze。
- [x] 3.4 实现 phi/select、条件 br/switch 的有界状态合并/筛选与 guard 证据，测试共享后继、循环、不可判定路径以及候选/路径超限降级。

3.1–3.3 的实现为 C++ 内部可测试组件；全局绑定资格生产者仍属 5.x。新增接口已于 2026-09-14 获批，先完成 1.5/1.6，再以独立局部求值协议接入 3.4/4.x；不把内部 ScalarSet 塞入 ModuleFacts/LocalAnalysisFacts。3.4 还须验证 bottom 不发布、块 pending/unreachable 区分、候选 guard 析取、重复边 ordinal、表达式/转移预算及非空 frontier。

3.4 最终由 `effect_control` 与 `effect_interpreter` 共同完成：候选析取合流、select 条件组合、br/switch ordinal 筛选、PHI 前驱快照、循环/SCC 保守 widening、条件状态、表达式与转移预算均进入 worker 结果；对应单元与集成断言已通过。

## 4. 受限局部存储传播

- [x] 4.1 实现已初始化非逃逸普通标量栈槽和常量不重叠子范围的安全强更新/load 转发，单测多层 O0 参数栈槽链及到达定义证据。
- [x] 4.2 实现合流、未初始化、部分重叠、lifetime 结束、逃逸及可能别名覆盖后的失效；单测未知调用仅破坏可能触及内存而不清空无关私有栈槽。
- [x] 4.3 增加共享/global、atomic、volatile 读取不从 initializer/前序写传播确定值的负例；验证保留原子观察和事件，不生成 reads-from/HB。
- [x] 4.4 实现 normal/unwind/noreturn 出口与 raw 诊断解释对应关系；单测已采用 nounwind 排除异常边及未证明时保留异常未知影响。

## 5. 派生绑定与受限 ODR

- [x] 5.1 在独立派生层复用 scope 校验并增加 profile/接口/函数体采用复核，测试唯一符号但 ABI 不匹配、未知 provenance、配置冲突、重复强定义和 lineage 重叠；保持旧 ScopeIndex 语义不变。
- [x] 5.2 实现受限 linkonce_odr 本地函数体采用和可见副本规范化结构/接口指纹，输出 ODR 契约假设及采用依据；单测合格 helper、副本冲突、非封闭/interposable/unsupported selection 和普通 linkonce 拒绝。
- [x] 5.3 实现 unknown/候选采用边及诊断到调用点的稳定引用，测试间接调用、外部声明、weak/weak_odr/ifunc 不被任选定义或转换为空影响。

## 6. 参数化效果摘要

- [x] 6.1 实现含对象/范围/值/order/syncscope 的读写、RMW、CAS、fence 摘要及原始事件引用，区分 local 和跨调用可见效果；为每种事件补充单元断言。
- [x] 6.2 实现实例限定的 guard、顺序、出口、may/must 量化范围和重复语义，测试不同调用/递归层及单次调用内循环重复条件的相同 raw guard 不互斥、合并实例不继承 must、正常返回效果不覆盖异常/不返回出口。
- [x] 6.3 实现返回参数、常量偏移、全局地址和常量关系，测试调用者使用返回字段指针，以及失效局部/复杂 heap 返回的 unknown。
- [x] 6.4 实现 escape/unknown 的保守读写与控制影响，测试 opaque asm/intrinsic、缺失函数体及嵌套未知调用对调用者的传播，不将未知效果序列化为空摘要。

## 7. 调用点特化与递归

- [x] 7.1 实现显式入口和合法采用边驱动的实参/形参、对象及返回替换，区分通用摘要复用上下文与抽象调用实例，递归重绑定 guard/返回/escape，保留调用者传入对象的分配身份；单测同函数不同实参及相同实参不同调用点不串用实例。
- [x] 7.2 实现确定调用图和 SCC 稳定顺序固定点/单调合并，测试直接递归、互递归、正常收敛和重复效果，不发布未收敛空集为 complete。
- [x] 7.3 实现 scoped-effects-v1 节点/值候选/条件状态/上下文及实例/SCC/效果边预算和保守 widening，有限 merged/unknown 桶不得证明存储独立或 guard 互斥；逐项测试边界、超限、非空未展开前沿、计划分母及完整性传播。
- [x] 7.4 接入每批 worker 60 秒/16 MiB、总请求 300 秒/64 MiB 的预算、显式收紧及进程终止/合法降级输出，单测超时/输出超限和全失败/部分成功区别。

## 8. 缓存与新增 CLI/报告

- [x] 8.1 实现局部/上下文/SCC 派生 key、依赖闭包和传递失效，分离模板 key 与实例化结果 key，命中模板后重绑定实例；单测仅 callee、scope/边界/profile、预算或策略变化时结果重算，原始 BC/P1 key 不变。
- [x] 8.2 实现派生缓存消费校验和新输出目录发布，测试损坏/陈旧/未来版本缓存、输入 hash 变化、重复运行确定性和不覆盖历史结果。
- [x] 8.3 实现 summarize 的 request/scope/artifact-store/worker/output 参数及显式入口或 all-defined，测试缺失/空/冲突入口、非成员引用、抽象实参错误和不自动链接/运行应用。
- [x] 8.4 实现 EffectAnalysisReport 分层状态、完整计划/前沿计数和 raw 诊断解释证据；测试部分成员失败、零分母、source unavailable、不抬高 provenance 和不输出安全结论。
- [x] 8.5 实现新命令 0/2/1 退出码和 stdout JSON/stderr 日志隔离，单测正常/partial/全部失败/非法请求，回归旧 collect/index/link/doctor 输出及退出语义。

## 9. 真实编译与语义回归

- [x] 9.1 增加三个物理 TU 的 compile-only 集成样例，断言对象/值/order/返回沿直接调用传播，并验证同名 static、字段范围及不同 scope 隔离；不依赖 llvm-link 或原生链接。
- [x] 9.2 固化 Clang 21.1.8/libstdc++ 13 的 C++17/20 O0 atomic 包装源码与证据，断言 release/relaxed/seq_cst 不同实参得到各自可达效果，raw 分支不丢失；记录实际标准库 package/hash，不按名称硬编码。
- [x] 9.3 增加未支持库/helper/ABI/EH 的 partial 对照、外部未知影响、递归预算及无 debug 集成；断言已知 order 不掩盖其他未知效果。
- [x] 9.4 回归 GCC/Clang C11/C17/C++17/C++20 原有输入适配矩阵，以及合法 P1 v2 重用/旧版本拒绝；验证不同 profile 结果不混合和离线无需 SSH/DevKit。

## 10. 单元覆盖率与质量门槛

- [x] 10.1 将所有新增/修改/复用 C++、Python、worker、schema、质量脚本纳入源码/构建/报告枚举；测试未加载 Python、未调用 C++、新子目录、可执行头文件和缺失 coverage 报告。
- [x] 10.2 维护质量入口及自测，验证整体 hit/total 合并、每语言/逐模块行与分支至少 90%、89.99%/90% 边界和集成 profile 不混入；列明第三方/生成物/纯夹具等排除依据。
- [x] 10.3 在现有独立开发容器使用新输出目录实际运行 `python3 -m memory_order_analyzer.quality --output /output/quality-p2-001 --integration`（完整宿主命令见 design.md D9），记录实际命令、所有测试及覆盖报告；失败或不足则补测/修复后换新目录复验，不提前勾选。

## 11. 文档与最终一致性验收

- [x] 11.1 编写 doc/EFFECT_SUMMARIES.md，说明 P1 缺口补齐、LLVM/自研分工、协议/CLI/请求样例、对象/值/ABI/ODR 支持表、unknown、预算和无安全结论边界；更新 README、路线图及相关事实文档阶段状态。
- [x] 11.2 编写 doc/EFFECT_SUMMARIES_VALIDATION.md，建立本 change 全部 requirement/scenario 到有效单元/集成断言的映射，记录固定输入、版本/hash、证据链、资源预算/确定性及整体/语言/模块行/分支覆盖结果和报告位置。
- [x] 11.3 校验新增文档及 OpenSpec 链接、协议版本/预算/支持边界一致性、历史 ARM/mm-check 证据未改，运行严格 OpenSpec 校验和文档测试；所有实施与质量任务实际完成后才提示 sync/archive，并提供下一阶段完整技能命令。
