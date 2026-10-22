## 1. 基线与协议契约

- [x] 1.1 记录当前 P3、A3、R1 相关单元测试、集成 truth、质量命令和 artifact schema 基线，确认本 change 不修改既有版本与退出语义。
- [x] 1.2 实现 `ThreadEntryDiscoveryRequest v1`、`ThreadEntryLocalFacts v1`、`ThreadEntrySiteIndex v1`、`ThreadEntryRootOverlay v1` 和 `ThreadEntryDiscoveryReport v1` 的严格 contract、canonical identity、依赖 digest 与确定排序。
- [x] 1.3 为五类新 contract 补充正常、未知字段、未来版本、重复身份、悬空/替换依赖、混合 profile 和非法状态组合的单元测试。
- [x] 1.4 将新增 Python/C++ 模块、可执行入口和源码目录纳入项目质量源码枚举，确保未被测试加载的自有代码仍进入覆盖率分母。

## 2. Clang 语义类型与构造事实

- [x] 2.1 扩展 source worker，为入口相关表达式输出 spelled type、canonical semantic type、canonical record/entity、constructor declaration/specialization/kind、alias chain、声明来源、system boundary、宏位置和 profile/model 引用，移除入口表达式的通用 `canonical_type=expression` 占位语义。
- [x] 2.2 基于 canonical entity 与已验证 profile 识别标准线程类型，支持非限定名、typedef/using、inline namespace、copy-init、`auto`、`new` 和 materialized temporary，并拒绝同名用户类型和未经登记的 `boost::thread`。
- [x] 2.3 分类 default、callable construction、move、copy/deleted、factory-return 和 other/unknown，建立 canonical physical callsite identity，保证外层 declaration/new/temporary 与内部 constructor 观察可去重。
- [x] 2.4 扩展 callable/argument 事实以覆盖自由函数、lambda、受限非虚成员函数、唯一简单 functor、`std::jthread` stop-token 注入候选和 `std::async` overload/policy 值流。
- [x] 2.5 为 source worker 增加 C++17/C++20 正常、别名、宏、默认/move/factory、同名类型、歧义 callable、profile 失配、alias/type 深度预算和错误恢复路径单元测试。

## 3. C API、LLVM broker 与入口模型 profile

- [x] 3.1 定义独立入口模型 registry/profile 记录，绑定 API family、canonical source entity、library/vendor/version、ABI、target/DataLayout、header/broker digest、参数角色、成功条件和 wrapper role，并允许引用但不修改 A3 已验证 `std::thread` profile。
- [x] 3.2 扩展 C/LLVM 局部事实，支持直接及受限 adopted wrapper 的 `pthread_create` 和真正 C11/C17 `thrd_create`，保存 C linkage、handle/result、callback SSA、argument 与 success guard。
- [x] 3.3 在锁定开发容器中实测并登记实际可验证的 libstdc++/libc++ `std::jthread` 与 `std::async` broker 指纹；未验证的 vendor/version/ABI/target 组合保持 unsupported，不以近似符号注册。
- [x] 3.4 扩展 C++ IR local facts 和 broker normalization，绑定 `std::thread`、`std::jthread`、`std::async` 的 wrapper role、callback/argument mapping、launch policy 和 source site，禁止用底层 pthread 或单一 mangled name独立采用。
- [x] 3.5 为 C API ABI、no-debug IR-only、callback 基数/冲突、wrapper、target/DataLayout 失配、broker 内联缺失、profile digest 失效和预算耗尽增加 C++/Python 单元测试。

## 4. 创建点索引与 API 语义

- [x] 4.1 实现 AST/BC 候选并集、physical TU/profile/SourceIRBinding/ABI/callback/broker 对齐和 opposed evidence，分别输出 `evidence_status`、`execution_semantics` 与 `root_disposition`。
- [x] 4.2 实现 canonical callsite 去重：合并同一物理 constructor 的多条 source/IR observation，同时保持不同调用点、相同 callback 的独立 site identity。
- [x] 4.3 实现 `pthread_create`/`thrd_create` 的 dual-exact 与受限 ir-exact 采用规则，确保 C11/C17 路径不依赖 C++ 类型或标准库 profile。
- [x] 4.4 实现 `std::thread`/`std::jthread` 的双源精确采用规则、stop-token invocable 歧义处理和 A3 事实引用，不新增或修改 lifecycle 关系。
- [x] 4.5 实现 `std::async` policy 分类：显式 async 可采用、显式 deferred 排除、默认/组合 policy 进入 conditional frontier、未知值流保守降级。
- [x] 4.6 实现自定义 API/平台边界：无显式 descriptor 的 `boost::thread`、`clone`、`submit`/`enqueue`/`post` 保持 unsupported/frontier，Windows/MSVC/clang-cl 明确 excluded。
- [x] 4.7 为索引增加 source-only、IR-only、dual-exact、callback 冲突、重复观察、default/move/factory-return、async 三类 policy、同名负例、开放 scope 和预算异常的单元测试。

## 5. Root overlay 与 R1 组合

- [x] 5.1 实现只读消费 `ExecutionRootIndex v1`/`RootDrivenAnalysisPlan v1` 的 `ThreadEntryRootOverlay`，不修改 base artifact，并以 adopted-from 引用消除已存在 pthread/std::thread root。
- [x] 5.2 分离 canonical callable context、physical creation site、线程对象/handle lineage 和动态 root origin；同 callable 多 site 保持多实例来源，循环/递归使用 repeated/merged cardinality。
- [x] 5.3 将 source/IR candidate、conditional、ambiguous、unsupported、failed 和预算项传播到 root/reachable coverage、候选相关依赖切片与非空 frontier；证明无关 TU 失败时只降级顶层 scope 状态。
- [x] 5.4 生成显式的 overlay reachable demand，供后续 root-driven 深度分析消费者选择 `R1 base + overlay`，同时保持原 R1 命令、cache、报告和结果不变。
- [x] 5.5 为 base/overlay 重复 root、callback 冲突、相同 callback 不同 site、循环创建、conditional async、相关/无关 TU 失败和 R1 artifact 不可变性增加单元测试。

## 6. 预算、缓存、CLI 与双语报告

- [x] 6.1 实现 TU、事实、type/alias depth、site/binding/callback/profile、wrapper、root/context、递归/SCC、frontier、诊断、输出字节、worker/request 和 wall-clock 预算及 hit/limit 统计。
- [x] 6.2 实现包含协议、工具链、scope/profile、source/BC、全部依赖、入口模型/descriptor、预算类别和 root 配置的缓存键，拒绝损坏、陈旧、failed、timeout 和 wall-clock partial 命中。
- [x] 6.3 实现 `discover-thread-entries --request --artifact-store --output --source-worker --ir-worker`，只读取显式依赖、拒绝已有输出目录且不执行构建、链接、目标程序、网络或 SSH。
- [x] 6.4 实现 `0/2/1` 退出码、固定 `safety=not_evaluated`/`findings=null`、中英 `detail/detail_en`、`limitation/limitation_en`、`suggestion/suggestion_en` 及四语言/证据/完整性统计。
- [x] 6.5 为每类预算、cold/warm digest、一项依赖变化、缓存损坏、worker crash/timeout、已有输出目录、零候选 complete/failed 分母及全部退出码增加单元测试。

## 7. 离线语料与语义验收

- [x] 7.1 审计并最小化复制 `memory-model-ir-checker/samples` 中有价值的线程入口用例到本项目，创建 provenance manifest，记录原相对路径、SHA-256、改写原因和平台排除，测试运行时不得访问兄弟目录。
- [x] 7.2 建立独立 C11/C17 fixture 与 truth，覆盖 pthread、真正 `<threads.h>` `thrd_create`、C linkage、宏、单/跨 TU、wrapper、no-debug、callback 冲突、开放 scope 和预算。
- [x] 7.3 建立独立 C++17/C++20 fixture 与 truth，覆盖现有 `std::thread` 形式、别名/default/move/factory/同名负例、lambda/member/functor；C++20 增加 `std::jthread`，两种标准按已验证 profile 覆盖 `std::async` policy。
- [x] 7.4 增加 `Form.submit`、`boost::thread`、`clone`、重复 AST observation、profile/ABI 失配和 Windows excluded 清单，断言 excluded/unsupported/ambiguous/unknown 不会被计为精确入口。
- [x] 7.5 运行四语言 AST+IR、IR-only、AST-only/no-debug 适用矩阵，分别报告 planned、completed、failed、expected/actual site、exact match、TP、FP、FN、abstention、frontier 和候选相关完整性。
- [x] 7.6 回归全部现有 P3、A3、R1、A2 降级和 A5 provenance 语义集，确认既有 artifact digest 规则、生命周期关系、风险结果和退出码未被重解释。

## 8. 文档与用户契约

- [x] 8.1 编写 `doc/THREAD_ENTRY_DISCOVERY.md`，说明 AST semantic type、constructor、BC broker、SourceIRBinding、二维 site 状态、API 支持矩阵、overlay、完整性、缓存、CLI 和非安全结论边界。
- [x] 8.2 编写 `doc/THREAD_ENTRY_DISCOVERY_VALIDATION.md`，记录锁定工具链/profile、归档样例 provenance、四语言 truth、负例、cold/warm、预算、测试和覆盖率实测结果。
- [x] 8.3 更新 README、整体架构文档和 `doc/IMPLEMENTATION_ROADMAP.md`，标明本 change 状态、与 R1/R2/A3/A6/框架 profile 的关系及下一阶段，不把成功编译、精确入口或零 findings描述为安全证明。
- [x] 8.4 运行 OpenSpec、Markdown、文档链接、命令示例、schema/version 和中英字段一致性检查，修复断链、过时状态和不一致表述。

## 9. 单元覆盖率与最终门禁

- [x] 9.1 运行全部 Python 与 C++ 单元测试，确认所有新增/修改/复用自有代码均覆盖正常、边界、异常和 unknown 路径，且集成测试未被当作单元测试替代品。
- [x] 9.2 运行项目统一质量命令 `python3 -m memory_order_analyzer.quality --output <全新输出目录> --integration`，保存机器可读报告、完整统计范围、未加载源码检查和逐模块结果。
- [x] 9.3 验收项目整体、Python/C++ 实现语言及每个受影响模块的行覆盖率和分支覆盖率均至少 90%；低于门槛、测试失败或自有源码未纳入统计时保持任务未完成。
- [x] 9.4 运行 `openspec validate expand-thread-entry-discovery --type change --strict --no-interactive` 和最终 required gate，确认 proposal/design/spec/tasks、实现 artifact、四语言 truth、文档与验收记录一致后再声明可同步归档。
