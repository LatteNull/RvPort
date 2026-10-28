# analyzer-unit-test-quality

## Purpose

规范全部自有执行代码的单元测试、完整覆盖率统计和至少 90% 行/分支门槛，确保质量验收可复现、可审计。

## Requirements

### Requirement: Unit test every P5 owned executable module at ninety percent coverage

所有新增、修改或复用的 P5 runner、schema/引用校验、truth 比较、指标、抽样、资源采集、cache、外部适配器、CLI、报告和决策逻辑 SHALL 有正常、边界、异常和 unknown/partial 路径的有效单元测试。项目整体、Python、C++ 及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须纳入分母，集成/真实工程/外部工具 profile 不得补入单元覆盖。

#### Scenario: An adapter is covered only by an external integration run

- **WHEN** 外部工具实验成功但适配器错误、超时或解析分支未被单元测试命中
- **THEN** P5 质量门禁失败，不能用 live backend 结果替代单元覆盖或缩小统计范围

#### Scenario: Overall coverage passes but a validation module fails

- **WHEN** 项目整体和语言覆盖率达标而任一受影响模块行或分支低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成或提示归档

### Requirement: Exercise P5 validation semantics entirely offline

单元和固定集成验收 SHALL 使用本地 truth/语料、合成 P1–P4 产物、录制 GenMC/herdtools7/DevKit 输出及固定真实工程 profile，覆盖 schema 版本、陈旧 digest、TP/FP/FN/unknown 分母、零分母、确定性抽样、cold/warm digest、预算、损坏缓存、后端不可用和双语决策。日常质量门禁 MUST NOT 访问网络、SSH、运行专有工具、执行用户 CMake 或运行被分析程序。

#### Scenario: Recorded backend evidence is malformed

- **WHEN** 测试输入未来版本、截断 JSON、错误 input hash 或 exit-zero 空报告
- **THEN** 单元断言 failed/partial 和完整诊断，不产生 agreement 或安全结论

#### Scenario: Cold and warm observations are semantically identical

- **WHEN** 固定输入仅在时间、路径和 cache hit 计数上不同
- **THEN** 单元断言 semantic digest 相同，同时原始资源指标分别保留

### Requirement: Publish repeatable P5 quality and validation acceptance

交付前 SHALL 在独立开发容器使用新输出目录实际运行全量单元测试、覆盖率门槛、离线语料集成、真实工程 cold/warm 基线和文档校验，并分别记录命令、版本/hash、测试数、整体/语言/逐模块 hit/total、语料指标、完整性、性能、缓存和报告位置。外部 live backend 若环境不可用 SHALL 明确 not_run/partial，不能阻塞核心离线门禁，也不能伪装已执行。

#### Scenario: Core quality passes while optional live backends are absent

- **WHEN** 单元、覆盖、离线语料和真实工程基线全部通过，但实施环境没有可验证的 GenMC/herdtools7 镜像
- **THEN** 核心验收可记录完成，live backend 明确 not_run，并保留适配器录制夹具测试结果和后续复现命令

#### Scenario: A required offline gate fails

- **WHEN** 任一单元测试、90% 门槛、truth comparison、确定性或真实工程完整性验收失败
- **THEN** 任务保持未完成并保存差距，不以历史 P4 覆盖率、外部工具一致或部分报告提示归档

### Requirement: Unit test all owned executable logic

项目 SHALL 为新增、修改、复用及现有自有可执行代码提供有有效断言的单元测试，覆盖正常、边界、异常和未知状态；范围 SHALL 包含 C++、Python、runner/cache/schema/report/质量脚本及 `doc/experiments/probe_bc.py` 自有逻辑。集成、编译冒烟、第三方扫描和文档检查 SHALL 不替代单元测试。

#### Scenario: Reuse an existing helper

- **WHEN** 从现有项目复用参数解析或产物校验代码
- **THEN** 记录来源并在本项目提供相应单元测试，不以原项目测试或历史运行成功代替

#### Scenario: Existing probe remains executable in this project

- **WHEN** 本项目仍提供 probe_bc.py 作为实验工具
- **THEN** 其自有逻辑纳入测试/覆盖范围，必要时可作可测性重构但保留历史证据含义

### Requirement: Enforce whole-project and module coverage thresholds

单元测试行覆盖率 SHALL 在项目整体、每个实现语言及本次受影响模块达到至少 90%；工具支持分支覆盖时对应分支覆盖率 SHALL 同样至少 90%。全项目 SHALL 按命中数/总数合并而非平均百分比，纳入未被加载或未被调用的自有源码；集成 profile SHALL 不混入单元覆盖统计。

#### Scenario: A new module is never imported by tests

- **WHEN** 某个自有 Python 模块没有被任何测试加载
- **THEN** 其可执行行仍计入总数，不能通过未加载而获得虚高覆盖率

#### Scenario: Line coverage passes but branch coverage fails

- **WHEN** 行覆盖率达到 95% 而可用分支覆盖率为 89%
- **THEN** 质量门槛失败，以非零退出且任务不能标记验收完成

#### Scenario: Integration tests increase measured coverage

- **WHEN** 集成测试命中了单元测试未触达的逻辑
- **THEN** 单元测试门槛仍只用单元 profile 计算，不能合并集成 profile 使其达标

### Requirement: Make coverage accounting auditable

质量报告 SHALL 列出统计源文件范围、排除项和理由、行/分支命中与总数、模块结果、命令和报告位置；只允许有依据地排除第三方、生成代码、测试框架和纯被测输入夹具，不得排除自有业务/工具逻辑。指标不支持 SHALL 明确注明，不得借此关闭原本可用的分支统计。

#### Scenario: A difficult error-handling file is excluded

- **WHEN** 覆盖配置试图把自有错误处理或 runner 逻辑排除
- **THEN** 验收拒绝该统计范围并要求补测，不以缩小范围或降低门槛通过

### Requirement: Provide a repeatable quality gate and exercise its failures

项目 SHALL 提供开发镜像内可重复执行的构建、单元测试、覆盖统计、门槛和独立集成测试入口；验收 SHALL 实际运行并记录结果。门槛逻辑本身 SHALL 有测试覆盖边界和缺失报告，不能在覆盖不足、测试失败或环境阻塞时声称完成。

#### Scenario: Coverage report is missing

- **WHEN** 质量入口无法获得任一自有语言或模块的预期报告
- **THEN** 以失败退出并指出缺失项，不跳过该语言/模块后声称通过

#### Scenario: Threshold boundary is tested

- **WHEN** 使用合成报告分别输入 89.99%、90% 和分支不足数据
- **THEN** 单元测试验证门槛分别失败、通过和失败，并检验全项目/模块范围均被执行

### Requirement: Test independent evaluation protocol semantics and resource boundaries

局部求值协议及消费代码 SHALL 有有效单元断言，覆盖有限候选/unknown/bottom、guard 条件析取、重复边、绑定/祖先对象、依赖/请求调包、结构/工作预算和旧协议拒绝；所有代码纳入项目整体/语言/受影响逐模块行及可用分支至少 90%，P1 v2 黄金兼容不变。

#### Scenario: Empty or over-budget evaluation pretends to be complete

- **WHEN** 测试注入 pending 块、空有限域、unknown、陈旧请求 hash 或过深表达式
- **THEN** 验证器拒绝伪完整/非法结果且不栈溢出，合法有界输入与 P1 回归继续通过；未执行覆盖率不得勾选验收

### Requirement: Test local registry identities and LLVM query boundaries

新增登记与查询代码 SHALL 纳入整体/语言/逐模块行和分支至少 90% 单元门槛；SHALL 固定测试未物化 alloca、optnone/O0、MemoryPhi/回边、无布局/动态范围、登记预算错误、跨函数/陈旧/伪造证据及 P1 输出不变。集成通过 SHALL 不替代这些断言。

#### Scenario: An analysis node is disguised as a raw instruction

- **WHEN** 将 analysis_id 作为原始 SourceRef 或把未登记指令作为合法证明
- **THEN** 单测断言拒绝，合法同 BC 的独立登记和 P1 黄金回归仍通过

### Requirement: Include all P2 executable modules in unit-only coverage

P2 新增/修改/复用的 C++ 局部分析与 worker、Python schema/绑定/摘要/SCC/缓存/CLI/报告/质量逻辑及其他自有执行代码 SHALL 有正常、边界、异常、unknown 单元测试并纳入完整源码枚举。SHALL 保留整体、每语言和现有逐模块行/可用分支覆盖率至少 90% 门槛；未加载 Python、未调用 C++、新子目录及可执行头文件不得消失，缺少模块报告必须失败，集成 profile 不得补入。

#### Scenario: A new executable module is missed by the build or tests

- **WHEN** 新子目录中的模块或可执行头文件未被单元目标链接/调用，或 Python 模块未被加载
- **THEN** 统计将其纳入或因缺失报告失败，不缩小统计范围使覆盖率达标

#### Scenario: Overall coverage passes but a P2 module fails

- **WHEN** 项目整体行/分支均达标而某自有模块任一可用指标低于 90%
- **THEN** 质量入口非零退出，不把该模块排除、放宽门槛或标记验收完成

### Requirement: Assert semantic soundness boundaries independently of integration success

单元验收 SHALL 使用固定 IR/结构化输入有效断言参数/局部存储/精确整数/对象范围/返回/条件/未知传播、ABI 与 ODR 正反例、递归固定点/超限及协议/缓存失效。SHALL 包含禁止共享/atomic/volatile 常量转发、禁止参数默认不别名、未知外部效果非空、未收敛摘要非 complete、may 不提升 must 的负例。真实编译集成 SHALL 独立验证三个物理 TU、同名 static、字段范围、多调用实参和固定 atomic 包装。

#### Scenario: Raw instruction presence is insufficient for specialization

- **WHEN** atomic 包装内存在多个 order 分支而调用点传入 release
- **THEN** 测试断言调用上下文只含可达 release 原子写、对象和值正确、原始事实不变及相关未知状态正确，不只断言生成 BC 或含有 atomic 指令

#### Scenario: Conservative behavior prevents an unsound constant

- **WHEN** 反例包含共享/atomic load、逃逸局部或未知调用覆盖
- **THEN** 单元断言不能错误得到确定值/空效果，并检查 unknown 原因、条件和调用证据传播

#### Scenario: Identity reuse cannot manufacture semantic proofs

- **WHEN** 单测覆盖同实参不同调用点、递归相同 alloca/guard、循环内分配、模板缓存重绑定和预算合并
- **THEN** 分别断言实例隔离、调用者对象归属保留以及禁止合并实例强更新/must-alias/noalias/互斥提升；相关代码纳入整体及逐模块行/分支至少 90% 门槛

### Requirement: Execute and publish repeatable P2 quality acceptance

实施交付前 SHALL 在独立开发容器离线运行完整单元测试、覆盖率门槛和分离集成测试，使用新的输出目录，记录命令、测试结果、工具/标准库版本、整体/每语言/逐模块行与分支 hit/total、完整统计范围、排除理由和报告位置。SHALL 测试 89.99%/90% 边界、缺失报告、预算/超时、来源/引用错误以及输出确定性。未执行、环境阻塞、失败或覆盖不足 SHALL 不标记完成或提示归档。

#### Scenario: Quality or semantic acceptance cannot complete

- **WHEN** 任一单元/语义集成失败、覆盖不足、报告缺失或执行环境阻塞
- **THEN** 保存实际证据和差距，任务保持未完成并提示继续 apply/修复，不以历史 P1 覆盖率或 DevKit 零建议替代本次验收

### Requirement: Unit test every P3 owned executable module

所有新增、修改或复用的 P3 自有 C++/Python 执行逻辑 SHALL 有带有效断言的单元测试，覆盖正常行为、边界条件、异常输入和保守 unknown 路径。质量枚举 SHALL 纳入未被测试加载的 Python、未调用的 C++、新增子目录和可执行头文件；集成测试、编译成功、schema 校验或静态检查 MUST NOT 替代单元测试。

#### Scenario: A new thread-analysis source is not loaded by tests

- **WHEN** 新增 Python/C++ 模块进入项目自有执行源码但没有 coverage 数据或单元执行
- **THEN** 质量入口失败并列明文件，不能因该文件没有命中记录而从统计范围排除

#### Scenario: P2 order is accidentally reused as proof

- **WHEN** 测试输入只有 P2 EffectSummary.order 而没有合法 P3 ExecutionOrderFacts
- **THEN** 单元测试断言不得生成 must-before/HB，并覆盖分支、循环和跨调用反例

### Requirement: Enforce ninety-percent P3 and project coverage gates

交付 P3 代码前 SHALL 实际执行可重复的单元覆盖率入口；项目整体、Python、C++ 以及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%。统计 SHALL 使用 hit/total 聚合且包含未加载源码，不得缩小范围、降低门槛或用无有效断言测试凑数。

#### Scenario: A module has 89.99 percent branch coverage

- **WHEN** 整体覆盖率达标但任一受影响模块的行或分支覆盖率低于 90%
- **THEN** 质量验收失败，相关任务不得勾选，补测或修复后必须使用新的报告目录重新执行

#### Scenario: All thresholds are satisfied

- **WHEN** 单元测试全部通过，整体、语言和逐受影响模块行/分支 hit/total 均不少于 90%
- **THEN** 质量报告记录精确命令、工具版本、统计范围、排除理由和报告位置，集成结果另行列示

### Requirement: Exercise fixed pthread semantic fixtures independently

项目 SHALL 提供固定离线 pthread C/C++ 物理 TU 和 IR 夹具，覆盖同入口多实例、main/worker、create 成败、join 前后、handle 覆盖、相同/不同 mutex、lock 失败/提前 unlock、递归/循环合并、未知 callback/wrapper、原子候选、跨 TU、无 debug 及损坏依赖。语义集成测试 SHALL 与单元覆盖率分别报告，且不得依赖 SSH、DevKit 或网络。

#### Scenario: The fixed multi-TU fixture is analyzed offline

- **WHEN** 在独立开发容器中对三个或更多物理 TU 执行 compile-only、P1/P2 和 P3 流程
- **THEN** 断言线程实例、生命周期、MHP、mutex/atomic 候选和证据链符合预期，无需 llvm-link、原生链接或运行目标程序

#### Scenario: An unsupported construct is present

- **WHEN** 固定反例包含 std::thread/RAII、自定义 wrapper、未识别 mutex 或间接 callback
- **THEN** 测试断言相关项进入 partial/unknown 且不产生虚假确定顺序、同步或安全结论

### Requirement: Exercise the P4 publication semantic matrix offline
项目 SHALL 提供直接 POSIX pthread 的 C11/C17 与 C++17/C++20 固定单 TU、物理跨 TU 和 IR 输入，覆盖普通 flag、relaxed flag 与普通 payload、release/acquire、seq_cst、fence unsupported、过晚 acquire、改名 flag、all-atomic relaxed、发布过早、不同 flag、多写者、重复发布、初值与发布值相同、单线程、join 后访问、未知调用、无 debug、开放 scope、预算及 wrapper 可解析/不可解析。期望 SHALL 来自明确语言语义和人工核对，不以 DevKit、SSH、运行频率或编译成功作为 oracle。

#### Scenario: CASE0 through CASE7 equivalents are analyzed with pthread
- **WHEN** 开发容器离线运行 P1/P2/P3/P4 固定矩阵
- **THEN** 对每例断言候选、finding/discharged/unknown、证据链、完整性和退出码，且不需要网络、SSH、DevKit、llvm-link 或运行目标程序

#### Scenario: The existing std-thread experiment remains in the repository
- **WHEN** `doc/experiments/publication.cpp` 继续使用 `std::thread`
- **THEN** 测试只把它作为 IR 表达对照，P4 端到端测试不借此宣称 P3 支持 std::thread

### Requirement: Unit test every P4 owned code path at ninety percent coverage
所有新增、修改或复用的 P4 C++、Python、schema/引用校验、cache、CLI、report 和质量入口逻辑 SHALL 有正常、边界、异常及 unknown 单元测试；项目整体、Python、C++ 和每个受影响自有模块的行覆盖率及分支覆盖率 MUST 均至少 90%。未被测试加载的新增源码 MUST 纳入分母，语义集成与单元 profile 分开统计。

#### Scenario: Risk logic passes integration but lacks branch coverage
- **WHEN** pthread 矩阵通过，但任一受影响规则/worker/report 模块分支覆盖率低于 90%
- **THEN** 质量验收失败，任务不得标记完成或提示归档

#### Scenario: All P4 quality gates pass
- **WHEN** 单元、文档和独立集成测试通过，整体、语言及逐受影响模块行/分支 hit/total 均至少 90%
- **THEN** 验证文档记录精确命令、版本、统计范围、排除理由、结果和新报告目录

### Requirement: Unit test every AST-assisted owned module at ninety percent coverage

所有新增、修改或复用的 LibTooling worker、schema/引用校验、profile identity、entity index、binding、overlay、下游适配、预算、cache、CLI、报告和双语诊断 SHALL 有正常、边界、异常和 unknown/partial 路径的有效单元测试。项目整体、C++、Python 及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%；未被测试加载的项目源码、子目录和可执行头文件必须进入分母。

#### Scenario: Overall coverage passes but the entity resolver does not

- **WHEN** 项目整体和语言覆盖率达标而 entity resolver 任一行或分支指标低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成或提示归档

#### Scenario: Integration cases execute untested worker branches

- **WHEN** 集成矩阵成功但 worker 的错误或预算分支缺少单元断言
- **THEN** 不能用集成执行补入单元覆盖率或缩小统计范围

### Requirement: Exercise AST-assisted semantics entirely offline

日常单元和固定集成门禁 SHALL 使用本地 C/C++ fixture、合成/固定 P1–P5 产物和锁定开发容器，覆盖编译 profile、linkage/ABI、USR 缺失、定义歧义、绑定基数、no-debug、候选相关完整性、预算、缓存损坏、CLI 退出码和双语字段。测试 MUST NOT 访问网络/SSH、执行用户 CMake、运行 ARM DevKit/外部后端或运行被分析目标程序。

#### Scenario: Cached overlay references a replaced binding

- **WHEN** 单元测试提供 schema 有效但 dependency digest 陈旧的 cache fixture
- **THEN** 系统拒绝复用并产生确定中英文诊断，不静默返回旧结果

### Requirement: Publish repeatable AST-assisted quality acceptance

交付前 SHALL 在独立开发容器使用新输出目录实际运行全量单元测试、整体/语言/受影响模块覆盖率门槛、离线 truth 矩阵、旧协议回归、TinyCThread cold/warm 基线和文档校验，并记录命令、版本/hash、测试数、line/branch hit/total、truth 指标、完整性、性能、缓存和报告位置。任一必需门禁失败时任务 MUST 保持未完成。

#### Scenario: Host Python lacks pytest but the development image is available

- **WHEN** 宿主机不能执行单元测试而锁定开发容器包含测试依赖
- **THEN** 验收必须在开发容器实际执行并记录结果，不能把宿主环境缺失声明为通过

#### Scenario: A previously accepted supported case is a false negative

- **WHEN** 验收后审计证明一个明确支持范围的 reviewed risk case 因实现错误返回 unknown
- **THEN** change 重新打开并增加针对性单元/集成回归；修复后重跑全量单元、逐模块 line/branch 90% 门禁和固定 truth，旧验收数字不得继续当作最终结果

### Requirement: Unit test all degraded analysis owned code at ninety percent coverage

新增、修改或复用的编排、schema/引用验证、failure taxonomy、evidence availability、SourceCandidate、dependency slice、SynchronizationGap、P3/P4 adapter、cache、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python和每个受影响自有模块的行覆盖率与分支覆盖率 MUST 均至少 90%，未加载源码、子目录和可执行头文件必须进入分母。

#### Scenario: Overall coverage passes but failure classification is untested

- **WHEN** 项目整体和语言覆盖达标，但任一 failure/cache/slice 模块行或分支低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成或提示归档

#### Scenario: Integration fixtures cover an untested branch

- **WHEN** 四语言集成矩阵命中某错误路径但单元 profile 没有有效断言
- **THEN** 不得把集成覆盖合入单元门槛或排除该自有代码

### Requirement: Exercise C and C++ degradation semantics offline

单元及独立集成 SHALL 离线覆盖 C11、C17、C++17、C++20 的四种模式、失败分类、错误恢复 AST、source candidate 证明边界、candidate-relevant gap、无关 TU、预算、cache corruption、CLI 退出码和中英文字段。C fixture SHALL 独立覆盖 pthread、C linkage、struct/union、宏和 C atomic；测试不得访问网络/SSH、运行目标程序、DevKit 或外部后端。

#### Scenario: C tests are absent while C++ tests pass

- **WHEN** C++17/C++20 矩阵通过但 C11 或 C17 任一必需 profile 没有计划/完成 fixture 和断言
- **THEN** 语义验收失败，不能用 C++ 或合并覆盖率替代 C 结果

### Requirement: Publish repeatable degraded analysis acceptance

交付前 SHALL 在锁定开发容器和全新输出目录实际运行 OpenSpec/schema、全量单元、整体/语言/逐模块行分支覆盖率、四语言 truth、旧协议回归、mutex conservatism、归档样例筛选、cold/warm 确定性和文档门禁，并记录命令、版本/hash、测试数、hit/total、TP/FP/FN/abstention、性能、cache、排除理由及报告位置。任一必需门禁失败时任务 MUST 保持未完成。

#### Scenario: Unknown RAII remains a risk finding

- **WHEN** 最终回归仍将未建模 `std::lock_guard` 相关访问报告为确定 potential-data-race
- **THEN** 语义验收失败，即使单元覆盖率和其他 truth 指标达到门槛也不得归档

### Requirement: Unit test every A3 owned executable module at ninety percent coverage

A3 新增、修改或复用的 C++/Python worker、schema/引用验证、library profile、callable/binding、对象状态机、lifecycle graph、P3/A2 adapter、cache、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须进入分母，集成 profile 不得补入单元覆盖率。

#### Scenario: Overall coverage passes but the ownership state machine does not
- **WHEN** 项目和语言覆盖率达标而对象状态机任一行或分支指标低于 90%
- **THEN** 质量入口非零退出，任务不得完成、同步或归档

#### Scenario: Integration exercises an untested ABI rejection branch
- **WHEN** profile mismatch 集成用例通过但对应自有拒绝逻辑没有单元断言
- **THEN** 不得用集成命中补足单元门槛或排除该模块

### Requirement: Exercise A3 semantics and regressions entirely offline

独立集成 SHALL 在锁定开发容器离线运行 C11/C17 pthread 回归、C++17/C++20 生命周期 truth、至少一个 libstdc++ 与一个 libc++ 实测 profile、单/跨 TU、无 debug、开放 scope、异常、预算、缓存损坏、CLI 退出码和中英文字段；测试 MUST NOT 访问网络/SSH、运行目标程序、用户 CMake、ARM DevKit 或外部后端。

#### Scenario: A required standard-library profile cannot be validated
- **WHEN** libstdc++ 或 libc++ 任一 required profile 没有实际编译、提取和 truth 断言
- **THEN** A3 语义验收保持未完成，不以合成 schema fixture 或另一 vendor 替代

### Requirement: Publish repeatable A3 quality acceptance

交付前 SHALL 在全新输出目录实际运行 OpenSpec/schema、全量单元、整体/语言/逐受影响模块行分支覆盖率、四语言语义矩阵、旧 P1–A2/P4 回归、profile fingerprint、cold/warm 确定性、性能/预算和文档门禁，并记录命令、版本/hash、测试数、hit/total、truth 指标、缓存、排除理由和报告位置。任一 required gate 失败时任务 MUST 保持未完成。

#### Scenario: Lifecycle truth has one false relation
- **WHEN** 覆盖率全部达标但人工 truth 出现一个错误 callback、实例或 join/detach relation
- **THEN** 验收失败并增加针对性单元/集成回归，不能以 90% 覆盖率或零风险 finding 替代修复

### Requirement: Unit test every A4 owned executable module at ninety percent coverage

A4 新增、修改或复用的 C++/Python worker、schema/引用验证、profile、binding、mutex/owner 状态机、wrapper 摘要、图组合、P3/A3/A2/P4 adapter、cache、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python 和每个受影响自有模块的行覆盖率与分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须进入分母，集成覆盖不得补入单元覆盖率。

#### Scenario: Overall coverage passes but the owner state machine does not
- **WHEN** 项目和语言覆盖率达标而任一 A4 状态机模块行或分支低于 90%
- **THEN** 质量入口非零退出，任务不得完成、同步或归档

#### Scenario: Integration executes an untested exception branch
- **WHEN** RAII 异常清理集成用例通过但对应自有错误/cleanup 分支没有单元断言
- **THEN** 不得用集成命中补足单元门槛或排除该模块

### Requirement: Exercise A4 semantics and regressions entirely offline

独立集成 SHALL 在锁定开发容器离线运行 C11/C17 pthread mutex 回归、C++17/C++20 RAII truth、至少一个实际 libstdc++ 和一个实际 libc++ profile、单/跨 TU、全局/字段对象、move、异常、无 debug、开放 scope、profile/ABI 失配、预算、缓存损坏、CLI 退出码和中英文字段；测试 MUST NOT 访问网络/SSH、运行目标程序、用户 CMake、ARM DevKit 或外部后端。

#### Scenario: Archived safe sample still remains unknown with complete evidence
- **WHEN** `safe/03_pthread_mutex.cpp` 已满足声明的 A4 profile、对象、路径和线程证据而最终仍返回 unknown 或 risk
- **THEN** 语义验收失败并增加针对性单元/集成回归，不能以其他 truth 或覆盖率通过替代

#### Scenario: Unsupported mutex is accidentally discharged
- **WHEN** try/timed/recursive/robust 或未知自定义 mutex 用例产生正式互斥 proof/discharged
- **THEN** 语义验收失败，即使没有 FP 风险 finding 也不得归档

### Requirement: Publish repeatable A4 quality acceptance

交付前 SHALL 在全新输出目录实际运行 OpenSpec/schema、全量单元、项目整体/语言/逐受影响模块行分支覆盖率、四语言语义矩阵、P1–A3/P4 回归、profile probe、cold/warm 确定性、性能/内存/预算和文档门禁，并记录精确命令、版本/hash、测试数、hit/total、truth 指标、缓存、排除理由和报告位置。任一 required gate 失败时任务 MUST 保持未完成。

#### Scenario: A required gate is unavailable
- **WHEN** 任一实际 vendor profile、单元测试、覆盖率、语义 truth 或文档校验未执行、失败或环境阻塞
- **THEN** 验收记录真实状态且相关任务不勾选，不使用历史 A3 数据、DevKit 零建议或合成结果宣称完成

### Requirement: Unit test every A5 owned executable module at ninety percent coverage

A5 新增、修改或复用的 Clang/LLVM C++ worker、schema/引用验证、对象/路径身份、候选 lattice、AA/MemorySSA/CaptureTracking 证据、pointer-field 传播、跨 TU 参数/返回/receiver 组合、A4/P4 adapter、cache、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python 和每个受影响自有模块的行覆盖率与分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须进入分母，集成覆盖不得补入单元覆盖率。

#### Scenario: Overall coverage passes but provenance composition does not
- **WHEN** 项目和语言覆盖率达标而任一候选、pointer-field、跨 TU composition或 adapter 模块的行/分支低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成、同步或归档

#### Scenario: Integration executes an untested conservative branch
- **WHEN** clobber、候选超限或 AST-only 集成用例通过但相应自有 unknown/partial 分支没有单元断言
- **THEN** 不得用集成命中补足单元门槛、排除模块或用无有效断言测试凑数

### Requirement: Exercise A5 C and C++ provenance semantics entirely offline

独立集成 SHALL 在锁定开发容器离线运行 C11、C17、C++17、C++20 独立 truth，覆盖单/跨 TU、struct/union、嵌套和 pointer field、参数/返回值、C++ `this`/对象/mutex 字段、phi/select/cast/GEP、唯一/多重/未知 clobber、无 debug、AST+IR、IR-only、AST-only、failed、开放 scope、ABI/profile 失配、预算、缓存损坏、CLI 退出码和中英文字段。C fixture MUST 独立于 C++ AST/标准库模型；测试不得访问网络/SSH、运行目标程序、用户 CMake、ARM DevKit、SVF、PhASAR 或外部后端。

#### Scenario: Different instances share one field declaration
- **WHEN** C 或 C++ fixture 中两个 storage instances 访问同一声明的 mutex/payload field
- **THEN** truth 断言对象身份不合并、may 不提升 must，A4/P4 adapter 不产生虚假同对象证明

#### Scenario: The same instance crosses a direct wrapper
- **WHEN** 四语言对应 fixture 具有唯一直接 definition、相容 ABI/profile 和完整参数/返回或 receiver 证据
- **THEN** truth 断言跨 TU 保持同一 storage/subobject identity及完整 proof chain，无需 llvm-link、目标链接或运行程序

#### Scenario: One language profile is missing
- **WHEN** C11、C17、C++17 或 C++20 任一 required profile 没有 planned/completed 数、truth 和诊断断言
- **THEN** A5 语义验收失败，不能用其他语言、合并分母或覆盖率替代

### Requirement: Publish repeatable A5 quality acceptance

交付前 SHALL 在全新输出目录实际运行 OpenSpec/schema、全量单元、项目整体/语言/逐受影响模块行分支覆盖率、四语言 provenance truth、P1–P4/A1–A4 黄金回归、A4 同名字段实例回归、cold/warm 确定性、性能/内存/预算和文档门禁，并记录精确命令、LLVM/Clang/profile/version/hash、测试数、hit/total、各语言 planned/completed/TP/FP/FN/abstention、模式完整性、缓存、排除理由和报告位置。任一 required gate 未执行、失败、覆盖不足或环境阻塞时任务 MUST 保持未完成。

#### Scenario: A supported exact case remains unknown
- **WHEN** 人工审计确认一个 required 范围的 C/C++ 直接调用对象绑定证据完整但最终为 unknown或错误对象
- **THEN** 验收失败并增加针对性单元/集成回归，不能以其他 truth、90% 覆盖率或零风险 finding 替代修复

#### Scenario: All A5 gates pass
- **WHEN** 全量单元与离线语义测试通过，整体、C++、Python和每个受影响模块行/分支 hit/total 均至少 90%，四语言 truth 无支持范围内错误且旧协议回归稳定
- **THEN** acceptance 记录实际结果和 `safety=not_established` 限制，方可标记实现完成并提示同步/归档

### Requirement: Unit test every execution-root R1 owned module at ninety percent coverage

R1 新增、修改或复用的 C++/Python worker、schema/引用验证、AST/BC 候选发现、证据对齐、root identity、reachable planner、P2/P3 编排、cache、预算、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python和每个受影响自有模块的行覆盖率与分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须进入分母，集成覆盖不得补入单元覆盖率。

#### Scenario: Overall coverage passes but root alignment does not
- **WHEN** 项目和语言覆盖率达标而任一候选合并、证据分类、reachable planner或 P2/P3 adapter 模块的行/分支低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成、同步或归档

#### Scenario: Integration executes an untested frontier branch
- **WHEN** 间接调用、profile 冲突或 root 预算集成用例通过但对应自有 partial/unknown 分支没有单元断言
- **THEN** 不得用集成命中补足单元门槛、排除模块或用无有效断言测试凑数

### Requirement: Exercise four-language root discovery semantics entirely offline

独立集成 SHALL 在锁定开发容器离线运行 C11、C17、C++17、C++20 独立 truth，覆盖显式 root、唯一 main、库导出入口、直接 pthread、跨 TU wrapper、std::thread profile、AST+IR、IR-only、AST-only、无 debug、开放 scope、callback 冲突、间接调用、递归、预算、缓存损坏、CLI 退出码和中英文字段。C fixtures MUST 不依赖 C++ AST 或标准库模型；测试不得访问网络/SSH、运行目标程序、用户 CMake、ARM DevKit 或外部后端。

#### Scenario: Candidate union preserves an unmatched source site
- **WHEN** AST truth 含创建候选而 BC 侧无法匹配
- **THEN** 集成断言候选以 source-candidate 和非空 frontier 保留，不因缺少交集而消失

#### Scenario: Exact IR-only pthread is retained
- **WHEN** 无 AST/no-debug 输入具有受支持直接 pthread ABI 和唯一 callback SSA target
- **THEN** 集成断言创建点为 ir-exact、源码完整性降低且 root plan仍可审计

#### Scenario: One language profile is absent
- **WHEN** C11、C17、C++17 或 C++20 任一 required profile 没有 planned/completed、root truth 和诊断断言
- **THEN** R1 语义验收失败，不能由其他语言或合并分母替代

### Requirement: Publish repeatable R1 quality acceptance

交付前 SHALL 在全新输出目录实际运行 OpenSpec/schema、全量单元、项目整体/语言/逐受影响模块行分支覆盖率、四语言 root truth、P1–P4/A1–A5 黄金回归、cold/warm 确定性、性能/内存/预算和文档门禁，并记录精确命令、LLVM/Clang/profile/version/hash、测试数、hit/total、各语言 planned/completed/exact/candidate/ambiguous/unsupported/failed、root/reachable coverage、缓存、排除理由和报告位置。任一 required gate 未执行、失败、覆盖不足或环境阻塞时任务 MUST 保持未完成。

#### Scenario: A supported exact root remains ambiguous
- **WHEN** 人工审计确认 required 范围内 AST/IR/ABI/callback 证据完整而结果仍为 ambiguous、遗漏或错误 root
- **THEN** 验收失败并增加针对性单元/集成回归，不能以其他 truth、90% 覆盖率或零 finding 替代修复

#### Scenario: All R1 gates pass
- **WHEN** 全量单元与离线语义测试通过，整体、C++、Python和每个受影响模块行/分支 hit/total 均至少 90%，四语言 truth 无支持范围内错误且旧协议回归稳定
- **THEN** acceptance 记录实际结果和 `safety=not_evaluated` 限制，方可标记实现完成并提示同步/归档

### Requirement: Unit test every R2 owned executable module at ninety percent coverage
所有新增、修改或复用的 R2 schema/引用校验、effect projection、execution-instance binding、MHP normalization、object/range comparison、bucket/pair builder、protection overlay、frontier/completeness、budget、cache、CLI、报告、acceptance及 C++ worker逻辑 SHALL 有正常、边界、异常和 unknown/partial 路径的有效单元测试。项目整体、Python、C++及每个受影响自有模块的行覆盖率和工具支持的分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件 MUST 纳入分母，集成 truth、编译冒烟、归档样例或历史覆盖率不得替代单元覆盖。

#### Scenario: Overall coverage passes but one pairing module fails
- **WHEN** 项目整体和实现语言覆盖率达标而任一受影响 R2 模块的行或分支覆盖率低于 90%
- **THEN** required quality gate非零退出，任务保持未完成且不得提示同步或归档

#### Scenario: Unknown and budget branches lack assertions
- **WHEN** 正常候选路径被覆盖但对象 unknown、MHP unknown、cache损坏或预算耗尽分支没有有效单元断言
- **THEN** R2质量任务不得以集成 fixture通过为由完成

### Requirement: Validate R2 semantics offline for all four language profiles
项目 SHALL 在本项目内维护可编译、人工标注且离线的 C11、C17、C++17、C++20 R2 truth，分别报告 planned、completed、failed、expected/actual candidate pairs、protected、excluded、frontier、TP、FP、FN和abstention。truth MUST 覆盖单 TU、跨 TU、no-debug、AST+IR、IR-only、AST-only、字段/指针、同名字段不同对象、mutex内外、single/merged/repeated、开放 scope、预算和缓存；C profile不得依赖 C++模型。测试运行时 MUST NOT 读取兄弟归档目录、访问网络/SSH、运行专有工具或执行被分析程序。

#### Scenario: Four language matrices are reported separately
- **WHEN** required semantic gate完成
- **THEN** C11、C17、C++17、C++20 各自有独立分母和结果，任一语言的 FN、FP或abstention不得被合并统计掩盖

#### Scenario: An archived sample is reused
- **WHEN** 从 `memory-model-ir-checker/samples` 选择样例进入 R2 truth
- **THEN** 样例必须最小化复制到本项目、记录原路径/摘要/改写原因并人工重标 candidate/protected/excluded/frontier，旧 safe/unsafe 标签不得直接作为 oracle

### Requirement: Publish repeatable R2 quality acceptance before synchronization
交付前 SHALL 在锁定的独立开发容器和全新输出目录实际运行全量单元测试、整体/语言/逐模块覆盖率门禁、四语言 truth、既有 P1–P4/A1–A5/R1/R1.1 回归、cold/warm cache、预算/性能/内存及文档/OpenSpec严格校验。acceptance MUST 记录精确命令、环境/版本/hash、测试数、覆盖 hit/total、truth分母、TP/FP/FN/abstention、资源指标、缓存一致性和报告路径；任一 required gate失败时不得把 change声明为实现完成、可同步或可归档。

#### Scenario: A required truth or coverage gate fails
- **WHEN** 任一单元测试、90%行/分支门槛、四语言 truth、确定性缓存、旧协议回归或文档校验失败
- **THEN** acceptance记录失败和差距，相关任务保持未完成且下一阶段命令只能是继续 apply/修复验证

#### Scenario: All required offline gates pass
- **WHEN** 全部 required gate在记录环境中通过且 artifact/文档一致
- **THEN** acceptance可标记 R2实施完成并具备后续同步条件，但不得把覆盖率、exact match或零候选描述为安全证明

### Requirement: Unit test every R3 owned executable module at ninety percent coverage
所有新增、修改或复用的 R3 schema/引用校验、lazy module index、function-local identity、semantic/effect/thread shard、demand graph/worklist、SCC/递归、scheduler/batch、worker manifest、只读适配、失败/frontier、预算、缓存、CLI、报告、acceptance 及 C++ worker 逻辑 SHALL 有正常、边界、异常和 unknown/partial 路径的有效单元测试。项目整体、Python、C++及每个受影响自有模块的行覆盖率和工具支持的分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件 MUST 纳入分母，集成等价、编译冒烟、性能结果或历史覆盖率不得替代单元覆盖。

#### Scenario: Overall coverage passes but a scheduler module fails
- **WHEN** 项目整体和实现语言覆盖率达标，而任一受影响 R3 模块的行或分支覆盖率低于 90%
- **THEN** required quality gate 非零退出，任务保持未完成且不得提示同步或归档

#### Scenario: Failure paths lack effective assertions
- **WHEN** 正常 lazy 路径已覆盖，但 worker crash、timeout、损坏缓存、递归预算或 AST-only frontier 没有有效单元断言
- **THEN** R3 质量任务不得以集成 fixture 或 eager/lazy happy-path 通过为由完成

### Requirement: Validate R3 semantics and scale offline for all four language profiles
项目 SHALL 在本项目内维护可编译、人工标注且离线的 C11、C17、C++17、C++20 R3 fixtures，并分别报告 planned、completed、failed、eager/lazy exact、identity/effect/thread/R2 mismatch、frontier 和 abstention。验收 MUST 覆盖单 TU、跨 TU、no-debug、AST+IR、IR-only、AST-only、不可达函数、精确 demand 扩展、递归、失败隔离、cold/warm cache、固定稀疏可达规模和 TinyCThread；C profile不得依赖 C++模型。测试运行时 MUST NOT 读取兄弟归档目录、访问网络/SSH、运行专有工具、执行 configure/build/link 或被分析程序。

#### Scenario: Four language matrices are reported separately
- **WHEN** required semantic gate 完成
- **THEN** C11、C17、C++17、C++20 各自有独立分母、eager/lazy 等价结果、R2 truth 回归和 frontier 统计，任一语言缺口不得被合并统计掩盖

#### Scenario: Sparse scale metrics are collected
- **WHEN** 固定稀疏可达规模 fixture 运行 cold 和 warm R3 分析
- **THEN** acceptance 记录 indexed、demanded、scheduled、materialized、completed、partial、failed、cache-hit、module parse、CPU、wall、RSS 和输出大小，并区分确定性语义门禁与环境敏感性能观测

### Requirement: Publish repeatable R3 quality acceptance before synchronization
交付前 SHALL 在锁定的独立开发容器和全新输出目录实际运行全量单元测试、整体/语言/逐模块覆盖率门禁、eager/lazy 规范化等价、R2 四语言 truth、TinyCThread、不可达不物化、cold/warm cache、递归/失败/预算、稀疏规模以及文档/OpenSpec 严格校验。acceptance MUST 记录精确命令、环境/版本/hash、测试数、覆盖 hit/total、各语言分母、mismatch/frontier、资源指标、缓存一致性和报告路径；任一 required gate 失败时不得把 change 声明为实现完成、可同步或可归档。

#### Scenario: A required equivalence or coverage gate fails
- **WHEN** 任一单元测试、90% 行/分支门槛、eager/lazy 等价、R2/TinyCThread 回归、缓存确定性、不可达不物化或文档校验失败
- **THEN** acceptance 记录失败和差距，相关任务保持未完成且下一阶段命令只能是继续 apply/修复验证

#### Scenario: All required offline gates pass
- **WHEN** 全部 required gate 在记录环境中通过且 artifact、报告和文档一致
- **THEN** acceptance 可标记 R3 实施完成并具备后续同步条件，但不得把覆盖率、等价、资源下降、零 frontier 或零 finding 描述为并发安全证明

### Requirement: Unit test every A6 owned executable path
所有新增、修改或复用的 A6 Clang/LLVM worker、协议/schema/引用校验、事件归一化、对象和线程绑定、RF/MO 求解、release sequence、fence pairing、P4 overlay、frontier、预算、cache、CLI、报告与质量脚本 SHALL 有带有效断言的单元测试，覆盖正常、边界、异常和 partial/unknown 路径。集成 truth、编译成功、静态检查、外部工具或零 finding MUST NOT 替代单元测试。

#### Scenario: The truth matrix passes but a solver error branch is untested
- **WHEN** 四语言集成 truth 全部匹配，但 RF/MO solver 的预算、损坏约束或未闭合分支缺少单元断言
- **THEN** A6 质量门禁失败，相关任务不得标记完成或提示归档

#### Scenario: Existing code is reused by A6
- **WHEN** A6 复用 P1/R3 event helper、A5 binding、P4 aggregator 或现有 cache 逻辑
- **THEN** 受 A6 修改或新增行为的代码进入本次单元测试与受影响模块覆盖分母，不以历史验收替代

### Requirement: Enforce A6 project language and affected-module coverage
交付 A6 前 SHALL 实际运行单元覆盖率入口；项目整体、Python、C++ 以及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%。统计 SHALL 纳入未加载 Python、未调用 C++、新增子目录和可执行头文件，按 hit/total 聚合；不得缩小范围、排除自有业务逻辑、降低阈值或把集成 profile 合入单元覆盖。

#### Scenario: Overall coverage passes but one atomic module is below threshold
- **WHEN** 项目整体与实现语言覆盖率达标，但 source classifier、event extractor、solver 或 overlay 任一受影响模块的行或分支低于 90%
- **THEN** required gate 非零退出并列明模块，不能通过排除文件或平均百分比验收

#### Scenario: A new source file is not loaded
- **WHEN** 新增 A6 自有源码没有单元 coverage record
- **THEN** 质量入口将其纳入总数或因报告缺失失败，不因零加载从分母消失

### Requirement: Publish repeatable offline A6 quality acceptance
实施交付前 SHALL 在锁定的独立开发容器和新输出目录运行完整单元测试、整体/语言/逐受影响模块双 90% 门禁、四语言 truth、`-O0`/`-O2` 归一化、eager/R3 等价、既有全量回归、cold/warm cache 和文档/schema 校验。验收记录 MUST 包含精确命令、工具/标准库版本与 hash、测试数、line/branch hit/total、统计范围、排除理由、truth 指标、完整性、预算、报告位置和失败差距；日常 required gate MUST NOT 访问网络、SSH 或运行专有工具/被分析程序。

#### Scenario: An optional external comparison is absent
- **WHEN** 核心离线门禁通过但 GenMC、herdtools7 或 ARM DevKit 环境不可用
- **THEN** 核心验收可完成，外部对照明确记录 `not_run`，不得伪造一致性或安全结论

#### Scenario: Any required gate fails
- **WHEN** 单元、覆盖率、truth、归一化、等价、回归、缓存、schema 或文档校验任一失败
- **THEN** 任务保持未完成并保存实际差距，只能提示继续 apply/修复，不得提示同步归档

### Requirement: Unit test every external ingestion executable path
所有新增、修改、删除或复用的 external bundle/record/report 契约、路径边界、流式 hash/copy、格式与 reader 校验、identity、artifact/scope 发布、cache、CLI、readiness、AST 对齐、降级、报告和迁移逻辑 SHALL 有带有效断言的单元测试，覆盖正常、边界、异常和 partial/unknown。集成 fixture 编译、Clang 成功、静态检查、零 finding 或历史 collect 测试 MUST NOT 替代单元测试。

#### Scenario: A path or identity error branch is untested
- **WHEN** 正常 bundle 集成通过但 path escape、输入变化、duplicate identity、stale digest 或 cache corruption 分支缺少单元断言
- **THEN** required gate 失败，相关任务不得完成或提示同步归档

#### Scenario: Removed producer code remains reachable
- **WHEN** parser、driver 或兼容层仍可触发 collect、dependency emission、Clang BC generation 或 llvm-link
- **THEN** 单元测试必须失败并指出禁止执行路径，不以该命令未被文档展示为通过

### Requirement: Enforce no-execution boundaries in unit and integration tests
项目 SHALL 使用注入 runner、argv 审计或进程边界测试证明 `ingest-bc-bundle`、`import-bc`、`index` 和下游生产分析不执行 compiler、dependency generator、assembler、linker、configure/build、网络、SSH 或目标程序。真实 fixture BC SHALL 在进入受测产品流程前预生成并清楚计为 test preparation；测试 MUST 覆盖无 GCC/Clang/llvm-link 环境下纯 ingestion 成功。

#### Scenario: A malformed input tempts a repair subprocess
- **WHEN** 输入为 ELF、GCC LTO、截断 BC 或 verify failure
- **THEN** 断言产品只返回格式/reader诊断且禁止工具 argv 集合保持为空

#### Scenario: AST assistance is enabled
- **WHEN** ingestion 后显式运行 source worker
- **THEN** 仅允许协议化 AST/source 解析请求，不出现 `-emit-llvm`、BC/object 输出或构建命令

### Requirement: Enforce project language and affected-module coverage for ingestion
交付本 change 前 SHALL 在锁定开发容器的新输出目录实际运行 unit-only 覆盖率入口；项目整体、Python、C++ 以及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%。统计 SHALL 纳入未加载 Python、未调用 C++、新增子目录、可执行头文件以及删除后仍残留的生产路径；不得缩小范围、排除自有业务逻辑、降低阈值或把集成 profile 合入单元覆盖。

#### Scenario: Overall coverage passes but the ingestion driver fails
- **WHEN** 整体与实现语言覆盖率达标，但 contracts、path validation、publication、readiness、CLI 或 report 任一受影响模块行/分支低于 90%
- **THEN** required gate 非零并列出模块，不能通过排除文件或平均百分比验收

#### Scenario: A formerly compiled module becomes unreachable
- **WHEN** 删除 collect/link 后旧自有执行文件不再被产品或单元加载但仍保留在源码范围
- **THEN** 质量入口仍将其纳入分母或要求删除/补测，不因不可达而自动消失

### Requirement: Publish repeatable external-ingestion acceptance
实施交付前 SHALL 独立运行全量单元测试、整体/语言/逐受影响模块双 90% 门禁、C11/C17/C++17/C++20 逐 TU bundle、跨 TU scope、IR-only、AST+IR、missing/failed、损坏/版本不兼容、x86 host/target、linked/optimized、cold/warm cache、既有 P1–A6/R1–R3 回归以及 schema/文档/OpenSpec 严格校验。验收 MUST 记录精确命令、环境/工具版本与 hash、测试数、line/branch hit/total、统计范围、排除理由、truth/完整性指标、禁止执行审计和报告位置。

#### Scenario: Optional source inputs are unavailable
- **WHEN** 外部 BC ingestion 和 IR-only 回归完成，但某用例没有源码/compile database
- **THEN** 核心 IR 输入验收可完成，该用例明确 source unavailable/partial，不伪造 AST 对齐

#### Scenario: Any required gate fails
- **WHEN** 单元、双 90%、bundle truth、禁止执行、既有回归、缓存、schema 或文档校验任一失败
- **THEN** 任务保持未完成并记录差距，只提示继续 apply/修复，不提示同步归档

### Requirement: 以真实协议断言覆盖工具结果修复
本工具涉及的自有代码 SHALL 同步具备正常、边界、异常和 partial/unknown 单元测试。适配器合同测试 MUST 调用真实 schema/reference validator，不得同时 mock 生产请求和校验为成功；进程 I/O 可注入。离线真实 worker 集成 SHALL 独立运行，不替代单元测试或混入其覆盖 profile。

#### Scenario: 多 TU 与特殊文件名回归
- **WHEN** 测试 TU/artifact 反序、重复同值/冲突及 thread-0/thread-entry 共存
- **THEN** 实际 validator 接受正确请求、拒绝冲突，发布分析选择正确 P3 依赖

#### Scenario: 支持与降级场景对照
- **WHEN** 测试普通循环负例、线程/原子/同步候选、AST-only、IR-only、partial 混合、缺摘要、零成员、profile 和多标准组
- **THEN** 断言候选准入、证据边界、分母、诊断及完整性，不只检查退出码或文件存在

#### Scenario: 工具投影与历史版本回归
- **WHEN** 测试 2.0/3.0、未知版本、frontier-only、主路径引用、截断及冷/热缓存
- **THEN** 本工具的校验、投影、计数和不可变制品符合合同，不把外部页面或报告业务当成本工具已验证功能

#### Scenario: 多 Scope 并发发布
- **WHEN** 某个 Scope 索引/缓存时另一 Scope 正在写任务目录或原子写入临时文件
- **THEN** 只读取已发布产物，不因临时文件消失而丢弃当前 Scope 结果

### Requirement: 实际执行工具全量与受影响模块覆盖门槛
实施交付前 SHALL 在 Docker 中运行本工具全部自有 Python/C++ 单元覆盖；整体、每语言和受影响模块的行及可用分支覆盖率 MUST 至少 90%，现有更严格逐模块门槛保持。统计 MUST 纳入未加载源码、可执行头和自有质量入口，不得缩小范围或混入集成 profile。外部项目的质量结果不得替代本工具门槛。

#### Scenario: 整体达标但模块不足
- **WHEN** 整体超过 90% 但某个受影响模块的行或可用分支为 89%
- **THEN** 自动门槛非零，验收未完成，不用变更行或平均百分比替代

#### Scenario: 文件未被单元加载
- **WHEN** 自有可执行源码未被单元测试加载
- **THEN** 仍纳入分母，不通过排除文件或降低阈值取得通过

#### Scenario: 历史缺口需要扩大范围
- **WHEN** 全量门槛失败且补齐需要超出当前 root 或无关大规模改造
- **THEN** 记录差距并停止范围外修改，不能自行扩大实施边界或标记通过

### Requirement: 工具 Docker 验证隔离且遵守文件边界
编译、安装、代码生成、单元和集成测试 SHALL 在独立 Docker 环境中按顺序执行，限制 CPU、内存和编译并发，使用专用卷。宿主机新写入文件 MUST 位于当前工具 root 内；不得连接真实 SSH、已有部署数据库或用旧分析结果代替当前源码验证。

#### Scenario: 执行真实组合验收
- **WHEN** 使用 Docker 预生成的合成 BC 和源码夹具运行统一入口
- **THEN** 验证诊断、候选、证据引用、跨 Scope 和 partial 语义，不运行被分析程序

#### Scenario: 必需检查失败或受阻
- **WHEN** 本工具 Docker 构建、单元、集成或覆盖检查失败/受阻
- **THEN** 如实记录并保留未完成，不用历史报告冒充本次通过

### Requirement: 验证证据可复现且责任范围明确
验收 SHALL 记录源码/镜像/工具版本、精确命令、测试结果、行/分支 covered/total、范围、排除理由和报告位置；跨语言合计按命中数和总数加权。公开夹具 MUST 为合成或授权脱敏数据。真实源码、日志、凭据和审计包不得进入公开源码。外部任务移出范围 MUST 明确记为移交，不能记为本工具已完成。

#### Scenario: 纯 artifact 范围修订
- **WHEN** 只修改 proposal/design/specs/tasks 或规则文本
- **THEN** 校验内容、链接、边界和 OpenSpec，保留历史测试日期，不声称重新执行代码测试或新增覆盖率结果

#### Scenario: 外部消费问题移交
- **WHEN** 输出合同需要前端或后端配合
- **THEN** 仅给出非规范性接口影响和交接，由对应 root 管理实现，不在本 change 留跨 root 实施任务
