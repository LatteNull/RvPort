## Context

本 change 位于 tools/kb-scanner，承接已归档的宏与构建作用证明。当前 TestAssetAnalyzer 能识别测试 suite/target/source，TestSelectionAnalyzer 能连接构建选择与知识命中，但源码成员分析仍以文件为主要粒度；文件被某个测试 target 包含，并不能证明其中每个函数都被测试调用或断言验证。CMake evaluator 目前将 enable_testing、add_test、set_tests_properties 放在安全忽略集合中，未恢复注册语义。

已有能力继续作为基础：C/C++ 双层前端、配置隔离的源码图、Build Selection、宏与参数作用证明、架构枚举、用途证明及 V2 源码证据链。不重做解析器，不恢复 legacy。测试内容分析研究的是被扫描项目的原始测试，不是替 Scanner 自动生成测试，也不是执行目标测试。

## Goals / Non-Goals

**Goals:**

- 在同一静态快照中连接测试注册、构建 target、source/TU、测试入口、受限直接调用及带架构事实的断言/条件。
- 区分编译依赖、测试注册选择和测试内容关系，给出可审校的 known/unknown 依据。
- 保留原始 fact/Observation、现有知识来源、真实源码位置及多配置差异；不以测试语境降低已证明的普通源码风险。
- 保持 V2 核心 schema、显式 V1、三个输出工件和后端消费方式；新展示双语。
- 将隔离单元测试、90%/90% 覆盖、反例审校和性能预算纳入交付。

**Non-Goals:**

- 不运行 CMake、CTest、Make、预处理器或原始测试，不认定测试成功、运行覆盖率或行为等价。
- 不做任意跨 TU 调用图、递归/虚调用/函数指针解析、模板实例化、全程序值流或 SMT 断言求解。
- 不完整支持 GoogleTest/Catch2/Boost.Test 等框架的注册、参数化与断言宏。首版可记录这些形态的候选及 unsupported 原因，但不把 TEST 名字或 EXPECT 字样当成确定执行证据。
- 不靠目录/文件名、测试数量、编译成功、未发现问题证明 RISC-V 覆盖完整；不替代运行时补证机制。
- 不涉及 OS 迁移、交叉编译架构误选、有符号移位规则或其他工具。

## Decisions

### 1. 三类证明分开，禁止共现升级

内部测试语境使用三个独立轴：build membership（是否编译）、registration/selection（是否注册且对目标配置选择）、content relation（入口/调用/断言关系）。复用已有 selected/inactive/not_selected/unknown vocabulary，proof 完整性另记，不能把三者压成一个布尔值。

| 静态事实 | 可以得出的结论 | 不能得出的结论 |
|---|---|---|
| 注册的测试 target 编译了含 intrinsic 的 source，且编译作用链完整 | 测试构建含 x86 编译依赖 | 该 intrinsic 一定运行或被断言验证 |
| main 有唯一可解析直接调用，目标函数含 intrinsic | 该入口具有局部调用关联，保留条件状态 | 测试已运行、调用必然发生或断言正确 |
| main 中有效 assert 的参数含已知 x86 fact | 架构依赖参与该断言表达式 | 当前目标一定断言失败 |
| x86 测试注册被 RISC-V 条件排除 | 该测试运行选择被隔离 | 其独立编译目标也被排除 |
| 测试文件只含数据名称 X86/AVX2 | 保留事实及既有用途结果 | 这是执行依赖或必须补 RISC-V 测试 |

不采纳“看到 tests 路径就将全部同文件事实挂为 exercises”的方案。仍允许既有完整构建链证明编译阻断，但链路和建议必须明确是构建问题。测试运行禁用不撤销编译风险；NDEBUG 禁用 assert 也不撤销断言外的依赖。

### 2. 先恢复可证明的注册，不扩展为构建解释器

CMake 首版处理：

- enable_testing 的可定位声明和有效目录范围。
- add_test(NAME <name> COMMAND <local-executable-target> [literal-args...])；旧式无 NAME 签名首版仅保留注册候选，不套用新签名的 target 解析规则。
- 参数可使用现有安全的字面变量/列表展开；目标必须唯一解析到本项目普通可执行 target，保留定义、调用、条件、目录与 configuration。
- 同目录 set_tests_properties(<tests...> PROPERTIES DISABLED <known-bool>) 的有序赋值；未知值、无法确认先后或不支持的影响执行语义的属性使对应运行选择 unknown。不得让禁用属性污染已独立证明的 source 编译关系。
- 注册与目标允许前向引用，通过收集后按配置和目录解析；同名跨目录测试不能合并，矛盾声明不“最后遍历获胜”。

不推断 include(CTest) 的未知 option/cache 默认值。shell wrapper、外部 executable、生成器表达式、动态发现、函数/宏里的注册、运行参数涉及未知过滤均保留原始事实与断点；字面命令参数只能证明传参，不用于猜测 main 的运行分支。禁止执行 gtest_discover_tests 等来获取注册。现有 CTest metadata 只代表其已声明配置，源 x86 构建产物不自动成为 RISC-V selected 证据。Make/RPM 继续使用已支持的显式构建关系；check 目标和 %check 文本本身不证明某个 C++ 函数执行。

### 3. 在前端建立独立、有界的测试内容清单

新增 scanner-owned 测试内容 records，提取函数名、签名/局部身份、body span、main 候选、直接调用、assert 调用及参数 span、局部变量定义/写入、相关条件与既有 fact 引用。身份由 path、span、TU/configuration、producer 组成，不仅使用函数名。

利用已有解析遍历和 SourceByteIndex，只复制字符串、整数、span 等普通数据，不持有 Tree-sitter Node/Tree/Parser 或 Clang cursor。不得把仅面向函数多版本属性的 function inventory 当作完整函数清单，也不能仅复用现有“候选枚举函数”过滤而漏掉普通测试函数。对显式测试 source 和含实际相关事实的测试候选需求建立索引；若构建关系较晚产生，使用已缓存标量摘要，必要时只在前端补一次受限提取，分析器不得再次读取源码或调用 parser。

普通测试 executable 的唯一 main 是首版可确认入口。同 TU 一跳辅助调用只支持普通函数的直接唯一解析；遮蔽、重载、模板、成员/虚调用、间接调用、跨 TU、递归、二跳及更深调用保留 unknown。lambda/嵌套 callable 的 body 不归给外层 main；未调用辅助函数仅建立 lexical containment，不建立入口调用证明。作用范围和 statement membership 必须由结构/span 决定，不能用字符串行搜索。

采用“结构清单 + 既有事实锚点查询”，不为每个断言扫描全项目 facts；没有架构事实的普通测试不制造 Finding。对解析错误区间、missing/error 节点或结构不完整的 body 保留 partial，不补造完整边。

### 4. 标准 assert 首版与有限局部值绑定

只确认标准 assert 受支持形态：有可追踪标准头来源、无生效的局部重定义/未知覆盖，且配置宏证据能够确定其适用性。NDEBUG 与宏重定义复用既有宏环境；环境不足时记录 assert-shaped candidate 和 unknown，不能将函数同名当作标准宏。

实施细化：首版使用已有 Clang 的宏实例→定义引用，要求定义来自系统 assert.h 且 token 序列匹配受支持的 glibc profile；记录当前观测 TU 的 enabled/disabled/unknown。该来源证明不复制系统头全文、不执行预处理器；其他 libc、未知 profile 保守保留 unknown。观测 x86 compilation database 的 NDEBUG 状态不作为目标 RISC-V 的宏环境证明，因此目标适用性仍可为 unknown，同时展示观测配置，避免混用三类证明。

直接参数包含已知 intrinsic、已确认架构探测/执行 selector 时，关联现有事实；允许同一函数、同一直线 block 内的普通 scalar 变量“一次初始化 → 后续 assert 使用”连接。只建立用途关系，不求值期望结果。中间重赋值、分支合流、引用/指针/别名、取地址、外部调用逃逸、复杂表达式、跨作用域或绑定预算耗尽都终止确定绑定并保留断点。不将断言变量反向传播成整个被调函数的结果语义。

例子：

- assert(_mm_cvtsi128_si32(v) == expected)：intrinsic 参与断言；其 x86 依赖来自编译器知识，断言是否成功未知。
- int value = known_arch_probe(); assert(value == known_x86_selector)：仅在既有 probe/selector 语义、局部绑定和配置证据完整时描述“断言期待 x86 条件”；不能根据任意函数名认定 known_arch_probe。
- assert(value == 42)、assert(sizeof(long) == 8)：没有其他确定架构来源时，不得仅凭常量/大小生成 x86 专属问题。
- enum Codec { X86_FILTER = 4 }; assert(codec == X86_FILTER)：保留原 fact，复用用途证明的纯数据排除或 unknown，不能因处于 assert 自动升级为执行要求。

诊断只针对实际相关的候选/事实与缺失关系，不为每个普通 assert 生成 unknown Finding。第三方框架宏可作为候选入口/断言形态记录，但不进入本轮确认规则。

### 5. 测试内容分析接入现有图与分类

在已有源码/构建图和测试资产识别后，加入 TestContentAnalyzer，消费标量清单并建立 testcase/入口、调用/断言、事实间有来源的内部关系，再由测试选择消费者及检测器解释。不能要求真实执行才保留编译依赖；不能因 role 未证明就删除本地 intrinsic。

源代码 relation 必须匹配具体 occurrence、TU、configuration 和控制条件。完整结论需要引用闭合、无截断、无冲突且每个必要关系受支持；一个 complete proof 不能掩盖同配置的相关 unknown。不同配置分别输出，不借另一配置的已知状态。

测试 blocker 继续使用既有 observation/classification vocabulary：构建阻断来自完整编译选择与知识依赖；内容语义只增加测试用途证据，不让“断言期待架构”在没有充分静态证明时自动变成 blocking。guarded 仅限已证明排除的对应路径；未知 runtime 条件不作为 RISC-V 互斥证明。断言是否通过保持未知。

以原始 fact + occurrence + configuration + 语义根因去重；测试语境补充到已有源码问题，不重复计数相同 intrinsic。独立注册配置错误可以独立成问题，但不把每层链各算一次。覆盖关系最多增加显式关联候选，不设置 testInventoryComplete，不推断 generic/RISC-V 功能等价或项目 ready。未知不静默降级为 low。

### 6. 结果兼容与真实源码链

V2 通过既有 extensions 的 org.rvport.kb-scanner.test-content 命名空间附加有界测试语境。包含测试身份、注册/编译/内容各自状态、proof 完整性、真实来源、用途描述及 unknown 原因；本 Finding 内引用闭合，不依赖顶层 catalog 或内部 snapshot。没有 Finding 需要解释时可有界摘要展示，不制造无风险问题占位。

不增加核心 schemaVersion、required、fact/step/edge enum。图中新增内部语义通过既有合法源码/build 节点类型与 extension 映射；抽象测试角色放在语境中，不伪造代码节点。evidenceChain 展示实际 add_test、target_sources/编译参数、include/条件、函数调用、断言和命中位置，不能硬串不连通路径，classification/assessment 不进入链。

每个真实代码锚点保留默认上下各 20 行、高亮、原始 span，受既有预算裁剪且标明原因。显示标题、解释、建议成对提供中文与英文；suggestion/suggestion_en 保持。HTML 默认中文并转义，V1 使用现有字段表达结论，不要求消费 V2 extension。合并现有 namespace，不能覆盖家族、多版本、用途、宏作用数据。

### 7. 性能与资源预算

按 path/TU/configuration 建立一次函数区间、调用与 fact 位置索引，使用需求驱动查询；复杂度计数须证明没有“每个测试 × 全部 facts”的扫描。默认测试阶段现有资产 4096、关系 10000、proof 4096、深度 8、访问 20000 上限保持，按阶段新增量计费，不能用继承图挤占预算。一跳是语义限制，不能通过提高 depth 变成任意调用图。

新清单每文件最多 10000 条内容记录、每次扫描最多 100000 条，每个断言局部绑定最多检查 128 个相关语句；计数包括候选和失败解析的已收集项。上限集中配置、单测冻结，超限发稳定 Diagnostic 并保持受影响关系 unknown，不能声称清单完整。源码上下文与报告继续使用现有独立预算，不按 case 复制整份源码。

实施细化：前端在提取前传入剩余全扫描预算，达到上限后仍保留原始架构事实，不先物化超额清单再丢弃。清单自身记录 partial 原因；只有实际关联测试语境的清单不完整才发测试内容诊断，避免非测试文件的新内部结构预算污染原有项目报告。

验收沿用已批准的 libarchive 822 文件 manifest（保留旧 810 文件历史）、两次独立进程、2 CPU/2 GiB/无额外 swap、每次含工件发布在 300 秒内及 exit 0。新增功能成本和阶段时间单独记录，不用生产容器或缩小输入通过。1万/2万规模分别覆盖普通无关 assert、稀疏架构事实和预算截断；记录查询次数、时间、峰值资源及报告体积，不能只看墙钟速度。既有宏/TU 与用途规模样例不得回退；若资源门槛确需大改，先报告原因再请求变更。

### 8. 模块与隔离单元验收

下表为职责映射；实施可将过大模块拆分，但实际新增/修改的每个自有可执行模块都必须登记 unit inventory，不能仅登记目录。测试不能调用完整 CLI 代替单元隔离。

| 模块职责/现有入口 | 隔离测试内容及替身边界 |
|---|---|
| C/C++ 测试清单新模块及适配器接入 | fake AST/cursor、UTF-8 span、普通 main、嵌套 callable、partial、生命周期与预算；真实原生解析另跑组件用例 |
| CMake project evaluator 与注册辅助模块 | 注入命令/token、目录/配置、前向引用、DISABLED、动态输入、命令预算；不调用 CMake |
| records/core vocabulary/normalizer（若修改） | 合成 records、身份、去重、无效引用、乱序、配置隔离、旧数据缺省 |
| TestAssetAnalyzer / 新 TestContentAnalyzer / 索引与绑定模块 | 合成 facts/graphs、唯一一跳、遮蔽、重写/逃逸、未调用函数、查询计数、每类预算及异常 |
| TestSelectionAnalyzer / TestSelectionDetector / classifier / assessor（若修改） | fake snapshot、构建与运行分离、完整性冲突、已知依赖不丢失、unknown/guarded、去重及 coverage 保守性 |
| composite 管线接入 | fake stages、顺序、失败/partial 传播、不重复读源和无相关输入 |
| V2/V1 投影、HTML/双语说明及支撑模块 | 合成完整/断裂链、扩展共存、自包含、20/20、转义、确定性、兼容缺省 |
| 新验收脚本与现有 runner/inventory 门禁（若修改） | fake process/时钟/资源/路径、超时/OOM/缺少输入、失败传播；不能仅测成功输出 |

沿用 tests/source-chain-test-inventory.json 及实际受影响专项清单；全体自有 kb_scanner、scripts、tools 范围与既有门禁保持，新增源码即使未被加载也计入。第三方依赖、自动生成数据等仅沿用有理由的排除，不排除自有业务逻辑。独立容器内运行 tests/run_source_chain_unit_tests.py，整体及每个受影响模块行覆盖率和分支覆盖率均至少 90%；完整回归 tests/run_container_tests.py --regression-only 单独报告，不充当单元覆盖。

新增手写 oracle/反例与实际报告逐项对照，记录原 fact、关系、分类、严重性、源码链和 extension 的变化；不直接把 scanner 输出生成期望。两份编译器事实 SHA-256 必须前后相同。固定 libarchive 以及已有 AVX/临时架构目录测试项目有输入可用时补人工抽查，不保证清除原有 unknown。

## Risks / Trade-offs

- [标准 assert 的宏环境不完整] → 仅保留结构用途和 unknown；不猜测 NDEBUG 或本地重定义，不执行预处理器。
- [一跳与框架候选限制导致漏掉较深测试内容] → 明示首版范围，保留已有普通源码检测与 unknown；后续框架/调用图单开 change。
- [禁用测试被误当成不用编译] → 构建成员和运行选择分轴，专门反例验证 DISABLED 与 NDEBUG 不会撤销其他依赖。
- [新的用途关系使报告变大或扫描变慢] → 事实锚点查询、增量预算、共享索引、固定资源与完整输出验收；不缩短正常上下文。
- [多个 producer 或配置混合产生重复/矛盾] → 以 occurrence/TU/configuration 为边界，真实来源合流，冲突保留 unknown。
- [注册语义变化波及现有风险] → 最小配对样例与真实项目差异审校；不以兼容为理由冻结旧误判，也不自动重写历史基线。

## Migration Plan

1. 固定现有报告、事实哈希、最小手写 oracle 和单元映射。
2. 完成前端清单及注册恢复，再接入有界内容关系与分类；逐层运行隔离测试。
3. 更新可选 extension、双语展示、合同样例与用户文档，进行 V1/V2/HTML/log 对照。
4. 独立测试容器完成整体/模块 90%/90%、全回归、规模和固定项目两轮性能审校后方可标记 apply 完成。
5. 不修改后端、不重建生产服务；若回退，整体回退本 change 的生产逻辑和对应合同/测试，不引入另一条 legacy 管线。

## Open Questions

当前无阻塞提案的选择。第三方框架的完整支持与更深调用分析明确 deferred；若实施发现标准 assert 的环境证明需要完整预处理或新增跨项目系统，应暂停该扩展并确认范围，不因普通测试失败立即停止定位与修复。
