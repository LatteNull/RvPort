## Context

`memory-order-analyzer` 是独立的新项目，目前仅有 `doc/` 技术记录与 compile-only 探针，不具备生产分析能力。已有文档覆盖 BC 流水线、内存语义、Clang 实验与 DevKit 验证计划；后续讨论补充了多编译器场景和跨文件关联，需要归并到可供实现使用的文档中。

本设计描述如何整理这些知识，不是分析器实现设计的批准或运行时功能承诺。归档项目只保留背景价值，不引入其代码或依赖。本 change 的规划根为当前项目的 `openspec/`。

## Goals / Non-Goals

**Goals:**

- 让读者明确输入条件、BC 生成边界、跨 TU 关联机制及不完整信息的影响。
- 为后续实现保留配置身份、证据出处、覆盖状态和可验证示例。
- 保持现有文档入口有效，每个主题有主要归属文档，避免相互矛盾的重复解释。

**Non-Goals:**

- 不编写编译命令适配器、AST/IR 分析、链接器、线程/别名分析或检测规则。
- 不接入后端，不删除归档目录，不迁移根目录或兄弟项目的 OpenSpec。
- 不要求本次重新访问 ARM、安装工具链或执行 DevKit；不把未来的验证计划写成完成结果。
- 不承诺 Clang 分析结果与任意生产编译器生成的机器码完全等价。

## Decisions

### 1. 按主题补齐现有文档，不建立第二套平行说明

| 文档（相对项目根） | 主要职责及可观察验收点 |
|---|---|
| `README.md`、`doc/README.md` | 标明当前阶段、归档边界；链接全部专题并给出阅读顺序 |
| `doc/BC_PIPELINE.md` | 展示构建上下文→逐 TU 编译→模块索引/可选限定范围链接→分析的流程；区分前端编译和最终链接 |
| `doc/BUILD_CONTEXT_AND_COMPILER_ADAPTATION.md`（新增） | 编译数据库字段与缺口、编译器参数分类、隐式环境、生成文件、配置身份及失败处理 |
| `doc/CROSS_TRANSLATION_UNIT_ANALYSIS.md`（新增） | 包含/构建/符号/共享对象/线程关系分层；跨文件案例、链接范围、候选关系及增量失效 |
| `doc/BC_ANALYSIS.md` | 语言/IR/硬件层次、同步语义、普通数据竞争与全原子协议风险、未知关系如何限制结论 |
| `doc/BC_EXPERIMENT_RESULTS.md` | 保留 2026-09-10 实测基线、环境/命令/原始证据、未测试项和解释边界 |
| `doc/DEVKIT_BC_VALIDATION.md` | 区分官方工作流、历史 SSH 阻塞和未执行验证矩阵；成功判据不依赖零告警 |

选择专题拆分并互相引用，而不是把所有内容追加到一篇 BC 文档，便于读者按构建、关联或证据问题定位。上述新文件由 apply 阶段创建，本 change 不提前执行任务。

### 2. 将构建重放与生产编译器语义等价分开说明

BC 是 LLVM IR 的二进制表示。生成它仍然需要可解析源码、预处理、类型检查和 IR 生成；不必完成最终机器码链接，也不必运行程序。项目的配置/生成步骤可能仍需执行以产生头文件或源文件；缺少被调用函数的实现可形成外部声明，缺少必须的声明或头文件则不能据此承诺编译成功。

专题文档按“保留、转换、移除、无法支持”组织参数示例：保留语言标准、宏、包含目录、目标 ABI、sysroot 等语义配置；适配驱动器和兼容选项；替换原输出与产物阶段参数；遇到无法等价适配的扩展/内建函数记录失败或偏差。还需讨论 response file、工作目录、环境与编译器隐式搜索路径。不能用简单替换 GCC/MSVC 为 Clang 并忽略未知参数来宣称等价；Clang 自身的预定义宏可能改变条件分支。

`compile_commands.json` 是逐 TU 命令来源，`output` 可辅助区分记录但不是通用目标图。头文件实际依赖可在相同预处理配置下采集，AST 信息与 BC 生成也可协同获取，无需先实现独立的全项目文本依赖扫描。目标归属、链接输入、库边界则来自构建系统适配（例如 CMake File API）或链接命令记录。

文档给出概念身份而非冻结接口：`TUKey = source path + effective compile configuration identity`，并在编译记录中关联工作目录、工具链、目标、宏、包含路径与构建变体。源文件/实际头文件内容哈希等进入缓存有效性条件；目标成员关系单独保存。只有编译数据库而没有目标证据时，只能描述部分范围或候选关联。

替代方案“无配置源码扫描”无法恢复条件编译语义；“完全模拟原编译器”超出本阶段。文档采用显式记录适配差异和覆盖缺口的方案。

### 3. 用分层关系解释自动跨文件关联

逐 TU BC 保留定义、引用与链接属性；在已知程序/库范围内，用符号索引解析直接调用、全局对象引用，并以函数摘要传递影响。共享头文件只能证明包含关系，不能证明函数调用或共享内存访问。

文档至少包含 `shared.h` 声明、`producer.cpp` 调用、`publish.cpp` 定义函数及全局对象的例子，逐一标明包含边、调用边和对象访问边。另列同名 `static`、同源码不同宏配置、不同可执行目标、缺失第三方实现、函数指针/虚调用的反例。内部链接符号要保持模块身份；C++ 名字、弱符号/COMDAT、静态库成员选择和动态符号覆盖等不得简单按字符串同名合并。未实现的解析细节作为后续设计问题，而不是声称已解决。

首选文档主线为“多 BC 模块＋范围内符号索引＋摘要”。限定范围的 `llvm-link` 可作为另一种表示，但不能自动补齐库选择、运行时加载和线程关系；不要求所有 BC 链成一个全局文件。间接调用/别名给出候选集或未知，不能伪造唯一目标。源码位置由调试信息关联并记录优化导致的缺失或一对多映射。

增量说明区分：头文件变化使实际包含它的对应配置 TU 失效；命令/工具链变化使相关 BC 失效；符号或摘要变化传播到相关分析消费者；链接范围变化需要更新范围索引。以上是后续实现约束的文档化，不引入缓存实现。

### 4. 以证据等级约束内存序结论

文档分别标注“本地实测”“官方文档”“设计建议”“待验证”。每个实测结论可回溯环境、输入、命令和原始结果；每个外部能力说明注明来源及版本范围。

保持现有 Clang 18.1.3 的 27 个 BC 模块、74 项表达/产物检查基线，并指向 `doc/experiments/results/clang18-evidence.json`。这些数字不代表缺陷样本数、召回率或并发安全证明。ARM SSH 阻塞是带日期的历史观察，DevKit BC 接受能力、跨模块能力和报告行为仍未实测；后续网络恢复的复测是独立工作。

分析说明必须区分 C/C++ 语言内存模型、LLVM IR 与目标硬件指令约束；普通数据竞争、全原子但协议顺序错误、硬件迁移风险不能混同。BC 保留 atomic/fence 不等于已经推导出 happens-before；跨线程关系还依赖线程入口、共享对象、锁及正确的 reads-from/同步条件。`volatile`、编译器屏障、信号 fence 不能直接视为通用跨线程同步。优化级别改变可观察 IR，O0/O2 结果应带配置解释。

记录构建覆盖与分析完成度是两个维度：partial/failed 编译、缺失实现、未建模同步、超时等均限制结论；零告警不能覆盖这些缺口。

### 5. 以官方资料和现有原始记录为引用入口

apply 阶段补充或核对相关出处，优先复用以下已知资料；若页面版本与本地实测版本不同，应明确区分：

- [Clang 编译数据库格式](https://clang.llvm.org/docs/JSONCompilationDatabase.html)、[编译阶段](https://clang.llvm.org/docs/Toolchain.html)、[交叉编译](https://clang.llvm.org/docs/CrossCompilation.html)。
- [CMake File API](https://cmake.org/cmake/help/latest/manual/cmake-file-api.7.html)：构建目标信息来源示例，不是所有构建系统的通用契约。
- [LLVM 18 llvm-link](https://releases.llvm.org/18.1.8/docs/CommandGuide/llvm-link.html)、[Atomics](https://releases.llvm.org/18.1.8/docs/Atomics.html)、[MemorySSA](https://releases.llvm.org/18.1.8/docs/MemorySSA.html)、[调试信息](https://releases.llvm.org/18.1.8/docs/SourceLevelDebugging.html)。
- [C++ 数据竞争](https://eel.is/c++draft/intro.races)、[原子 fence](https://eel.is/c++draft/atomics.fences)：注明在线草案属性及示例语言版本。
- [DevKit 25.1 BC 生成](https://www.hikunpeng.com/doc_center/source/zh/kunpengdevkithistory/devkit_25_1_0/cliuserguide/KunpengDevKitCli_0043.html)、[内存一致性检查](https://www.hikunpeng.com/doc_center/source/zh/kunpengdevkithistory/devkit_25_1_0/cliuserguide/KunpengDevKitCli_0027.html)：不能替代目标环境的版本和命令帮助实测。

## Risks / Trade-offs

- [把规划写成现成能力] → 正文标记当前阶段，规范主语统一为“文档”，示例明确是说明还是实测。
- [多文档重复导致冲突] → 每个主题设主文档，其他位置只摘要并链接；验收检查数值、状态与术语一致。
- [跨文件例子过度承诺精度] → 同时提供边界案例，将唯一解析、候选与未知分开描述。
- [编译器适配丢失语义] → 记录隐式环境、预定义宏和未支持参数，不把 BC 成功生成当作等价验证。
- [DevKit 长期不可访问] → 保留日期、阻塞原因与待执行矩阵，文档任务可独立完成，不伪造结论。

## Migration Plan

这是文档增量整理，无运行时迁移。按构建专题、跨 TU 专题、既有设计/证据更新、入口和一致性验收顺序执行。保留原始实验源码与 JSON 不变；需要勘误时在说明中记录原因。回退仅限本 change 实施时引入的文档编辑，不删除目录或其他用户工作。

## Open Questions

- 实际 DevKit 版本接受哪些 LLVM BC、如何处理多个模块、库与间接调用？保持待实测。
- 首个分析器版本支持哪些编译器扩展、构建系统和动态链接语义？留给实现 change 定义，不阻塞文档整理。
- 初版采用哪些别名分析、摘要和精度预算？这里只记录它们对跨 TU 与内存序结论的影响，不选定实现依赖。
