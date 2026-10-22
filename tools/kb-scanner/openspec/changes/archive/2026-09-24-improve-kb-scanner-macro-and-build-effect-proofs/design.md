## Context

本 change 位于 `tools/kb-scanner`，接续已归档的候选用途证明，不实现运行时编译。当前主链仍是 frontend → normalizer → analyzer → detector → classifier/assessor → V2/V1 projection。

当前源码核对依据：

| 现有模块 | 已有能力 | 本轮需要补齐的边界 |
| --- | --- | --- |
| `frontends/build/macro_arguments.py` | 字面单源 recipe、简单变量引用、`-D/-U` 来源 | 条件内赋值失效、include 导致整体不确定、自动变量不支持；跨位置 token 不能用一个 span 证明 |
| `frontends/build/cmake/usage.py` | PUBLIC/PRIVATE/INTERFACE 传播和 source-specific 参数 | 传播证明与定义冲突、顺序来源需明确，不能把遍历顺序当 compiler option 顺序 |
| `analyzers/build_macro_binding.py` | 参数→recipe→条件、源码 define/undef 和本地 include | 遇到 elif/else 当前使状态整体未知；缺少对象别名和布尔组合、逐 TU 的合流模型 |
| `analyzers/macro_resolution.py`、`evidence_graph.py` | 可见性消歧、多层宏调用与 replacement 链 | replacement 主要按 call_candidate/名称寻找定义；需要调用时状态、实际参数映射和配置隔离 |
| `frontends/cpp/*` | 定义、形参、替换 token、调用位置及不支持语义标记 | 补齐固定实参、事件顺序及分支范围的纯数据合同 |
| `projection/v2/source_chain.py` | 命中驱动的反向有界查询、真实源码端点 | 多位置来源和不同 TU 不能在相同头文件锚点处拼接成一条确定链 |

这不是“宏分析从零开始”，也不承诺清除 libarchive 历史 26 项用途 unknown；它们还涉及字段、返回、未知调用等独立边界。两份 GCC/Clang compiler facts 继续原样加载，用于识别最终 x86 依赖，不承担构建命令到预定义宏的猜测。

## Goals / Non-Goals

**Goals:**

- 对支持子集，证明某个具体编译单元中的参数如何经条件、include 和宏传递影响当前 x86 命中。
- 把已知、未知、未定义、冲突及 inactive 分开；提供真实断点，避免跨 target/TU/configuration 借用证明。
- 对每条新增确定关系给出可审计来源及正常、边界、异常反例；保留所有原始事实。
- 复用现有 Finding 源码链、双语说明与 20/20 上下文，不改变核心 schema 或要求后端增加接入。

**Non-Goals:**

- 完整 Make/CMake/C 预处理器、执行配置或项目命令、读取 workspace 外内容。
- Make pattern/implicit/static-pattern rules、target-specific 继承、任意函数/eval/shell、通用 response file 解释；CMake 函数/宏执行、generator expression、外部包解析。
- `#`/`##`、变参、模板展开、任意宏算术、编译器内建宏推导、生成缺失头文件；固定参数传递不扩展为通用 C/C++ 值流。
- OS/RVWMO 分析、真实 RISC-V 编译、测试内容语义、跨函数用途消噪、架构实现功能等价、有符号移位。
- 全面替换图存储或共享表大重构；不扩大已有局部图预算来隐藏问题。

## Decisions

### 1. 扩展现有组件，分离来源与求值

继续使用现有解析依赖与 scanner-owned 数据；按职责拆出纯函数/小模块处理构建参数来源、宏状态、受限表达式和实参绑定，具体文件名可在 apply 时调整并同步测试映射。frontend 只采集 token/span/结构，normalizer 检查引用与身份，analyzer 做状态与证明，投影不参与语义判定。

未选择调用 gcc/clang -E、运行 Make/CMake 或引入必需的 LibTooling helper：无 compdb 项目仍须可分析，源环境 x86 预处理结果也不能代替目标 RISC-V 配置。可选 libclang 沿用当前安全入口；增强缺失或冲突只能降级，不作为全部项目的前置依赖。

### 2. 参数作用对象是编译使用实例，不是整个文件

内部身份至少包含 `build entry + target + TU + configuration + command/use occurrence`。头文件 token 的原始 Evidence 可以共享，绑定状态和 Relation 不共享到别的 TU。未提供 context 的 baseline Evidence 只是原始素材，不是能够证明所有配置都相同的通配符。

每个参数维护操作 `-D/-U`、名字、原始值、顺序证据、来源 Evidence 集合、变量引用路径和真实使用点。来源可以是多个不连续 span；不得造一段横跨不同定义的源码。列表可确定排序以输出稳定，但“输出排序”不等同“参数生效顺序”。

source-only 推导与 compdb/File API 的 observed configuration 分开；只允许有明确同一 TU/configuration 身份的交叉佐证。x86 观察记录不使 RISC-V selected。缺少 target 也不能按 basename 关联其他目标。静态规则存在只证明有条件的使用关系，不证明目标一定是必需构建入口。

### 3. Make 扩展限定为可以恢复的静态事件

复用已有 Make 条件和 include 边界，为参数桥接保留按读取顺序的赋值及引用事件。支持单字面本地 include、已支持的 ifeq/ifneq/ifdef/ifndef/else/endif、简单变量引用及 `=`/`:=`/`+=`/`?=`。保留递归/立即展开差异，未知分支分别分析后合流，不能把两个分支依次写进一个环境。

支持明确单 target 规则中 `$@` 与 `$<`：前者为该 target，后者必须是已证明的首个普通 prerequisite，并且实际命令只编译一个可定位 C/C++ source。`$^`、隐式规则、模式匹配、多源单命令、环境覆盖来源不明等不强行猜测。多个明确编译命令各自有 use identity，不能共享最后一条 recipe 的状态。

条件架构仍使用目标值和已有正确 uname 假设；不执行 shell。动态 include/eval、未知外部环境或命令副作用使受影响状态 unknown；无法界定影响范围时保守失效当前环境。确定 inactive 的副作用不污染其他可达分支。可知的独立事实保留，不能因桥接失败删掉字面 x86 flag。

### 4. CMake 复用已有 usage 传播，拒绝虚假的覆盖顺序

沿现有本地 target/source 及 PUBLIC/PRIVATE/INTERFACE 关系传播，保留每条参数定义、link 使用点和源文件成员关系。PRIVATE 不向消费者传播，INTERFACE 不用于目标自身编译；未知外部依赖、循环、动态引用维持 unknown。

只对语义已证明有序的选项序列应用 last-write。不同 target 或独立 definition 来源对同一宏给出不同值、或者 `-D/-U` 覆盖顺序无法从输入确认时，记录所有候选与 `conflicting-build-macro` 或 `unknown-argument-order`，不按文件行号/图遍历顺序选赢家。相同操作/值可合流，但保留所有实际来源。目录变量和顺序仍遵守现有 CMake 适配器范围，不把子目录参数反向施加到父目录。

### 5. 每个 TU 的宏环境按控制流推进

宏状态包含定义存在性、replacement token/值、定义身份、来源和完整性；区分 explicitly undefined、known defined、unknown/conflicting。扫描没找到定义不等于已证明未定义，外部宏和不完整 include 不采用默认 0。已证明的 `#undef` 可将该名字恢复为明确未定义。

对象宏按使用时可见环境递归求值，而不是定义时提前固化。例如 `#define A B` 后重新定义 B，A 在不同使用点可以有不同结果。首版条件语法限定整数、标识符、括号、`defined`、`!`、`&&`、`||`、`==`、`!=`，保留 0 的存在性与真假差别；不支持或有实现相关整数行为时 unknown，不用 Python 求值项目文本。

每个条件组按顺序处理 if/elif/else；未知条件对可行分支建立独立环境，包含“没有任何分支执行”的路径。合流逐名字比较定义状态和规范化 replacement：相同则可确定，但保留全部来源；不同则 unknown/ambiguous。false 父分支下的 define/undef/include 不改变环境。逻辑短路可证明条件真假，但不能抹掉原始不支持语法或来源不完整记录。

include 按当前 TU 顺序展开；不能按文件名永久去重，因为同一头文件可能在不同宏状态下再次包含。仅对完整证明的 include guard/pragma once 应用对应跳过规则；否则在预算内重新处理，环和缺失文件给出断点。未知 include 可能引入或取消宏，不能悄悄继承先前的确定状态。

### 6. 固定参数宏以调用 occurrence 为单位绑定

首版支持固定参数个数、完整 token 边界、平衡括号且没有 stringification/token-pasting/变参的包装。优先交付标识符、整数及这些 token 的括号包装传递，例如 `OUTER(f,x) → INNER(f,x) → f(x)`；字符串、模板逗号、无法确认参数边界的复杂表达式不纳入完整证明。

实参来源、形参声明、replacement 中的参数引用和最终终端符号分别保留；嵌套包装在调用时宏环境中查找，重定义/undef 和递归禁用规则参与解析。同名普通函数不能仅因项目别处存在宏而被强制展开。递归/间接递归在首版保留 partial，而不是无限展开或错误终止为完整。

替换后 token 没有独立原文件位置时不伪造坐标，使用原始实参/替换 token 的来源关系。最终 intrinsic 由现有 Knowledge Provider/Matcher 和两份事实数据确认；新出现的 x86 终端也必须通过正式 Fact/Observation 路径，不能在投影层新增风险。宏没有被调用时保留定义事实，不构造已执行路径。

为保持阶段顺序，normalizer 先保留实参/别名 replacement 的原始 token fact，Analyzer 把可验证终端及调用身份连接回这些 fact，Detector 再通过正式 matcher 和展开证明产生 Observation。仅命中 intrinsic 名称不证明该实参确实被调用；无法完成绑定时保持候选/unknown。Analyzer 不回写 NormalizedSnapshot，也不绕过 Knowledge 直接创建最终 Finding；新增 fact kind 若有必要必须纳入 normalizer/detector 的隔离单测和原事实保留断言。

### 7. 图查询从现有命中反向取证，保持预算

新分析复用正式 facts、宏调用和 build bindings 确定需求，按 TU/configuration 建索引；每个命中有界查询上游，不为每条 Finding 重扫全部源码或复制整个环境。别名/实参可能暴露新终端时，需求入口还应包括已有宏调用事实，不能因尚无 intrinsic Finding 漏掉它。

TU 内处理条件所需的有序事件可以扫描一次；无需求 TU 不物化新证明。使用状态快照/共享前缀及按完整环境身份缓存；仅按宏名或文件名缓存不安全。作用图不能被当成候选用途的 `non_execution_data` 证明，家族成员和 default 标签也不能据此提升为功能等价。

新增硬预算：每 TU 最多 100000 个事件、宏展开深度 32、单调用最多 4096 个展开 token、每扫描最多 100000 个新增作用关系；Make include 深度 8/文件 128、C/C++ include 深度 16/访问 128 沿用既有量级。新增关系额度只计本阶段增量，不因继承旧图大而提前耗尽。源码展示查询 depth=16/visited=256/paths=32、20/20 上下文及 256 行/65536 字符上限不变。预算耗尽明确记录 visited/limit/断点，保留原始事实并阻止不完整证明降低风险。

### 8. 使用现有 V2 源码链，不增核心类型

通过现有 source/build step、selects/defines/invokes_macro/expands_to/includes 等语义表达真实端点；变量来源与实际使用点分别展示，不把参数列表简单排成一个虚假执行链。参数拼接可以显示为多条来源旁支。无位置的状态合流实体仅在引用可验证时折叠，不能成为伪代码节点。

同一个 Finding 保留各 occurrence/configuration 的上游，primaryPath 只取实际连通路径。知识仍为命中旁支，classification/assessment 不进入 evidenceChain。新增原因码及补充 provenance 可进入既有 namespace extension，扩展必须自包含、双语、有界且不能成为理解基本链路的必需后端新协议；不新增核心 kind/required 字段。V1 不增加 V2 图字段，仍允许有新证明支撑的结论修正，不能把 schema 兼容误解为输出语义永不变化。

### 9. 测试映射与验收

以下为职责映射；apply 必须登记实际文件，一项职责拆分多文件时逐文件纳入 inventory，未加载源码同样计覆盖。

| 新增/修改职责 | 隔离单元与边界 |
| --- | --- |
| C++ token/实参/分支采集，Tree-sitter/Clang 接线 | fake Node/Cursor/token 和诊断；空参数、嵌套、坏语法、UTF-8/CRLF、超限、原生对象生命周期 |
| Make 参数事件/include/recipe，构建 token provenance | fake 文件 reader/parser；展开时机、条件合流、自动变量、缺文件/根外、动态构造、未使用参数 |
| CMake usage 与冲突分析 | 纯 records；传播方向、多 target/目录、重复值/冲突、未知顺序、环及预算 |
| normalizer 与新内部 DTO | 纯 DTO；悬空引用、分散 span、顺序缺失、配置冲突、稳定 ID |
| 宏环境/表达式/实参 resolver | 纯事件；真/假/未知、undef、别名使用时求值、分支合流、include 重入、参数绑定/递归/预算 |
| Evidence Graph/build binding/索引/接线，若改动 Detector/Classifier | fake snapshot/knowledge；唯一/歧义、配置隔离、无需求路径、原事实保留、完整 proof 消费和风险不误降 |
| V2 SourceChainIndex/mapper/context/validator/renderer | fake reader/graph；真实端点、multi-source、TU 隔离、20/20、双语、HTML 转义、V1 兼容 |
| 新增测试驱动/测量辅助可执行代码 | 独立测试子 suite；fake subprocess/filesystem，超时、失败、缺指标不能通过 |

在独立 `kb-scanner-test` 容器运行 `tests/run_source_chain_unit_tests.py --output /output/unit`，所有生产自有 `kb_scanner/`、`scripts/`、`tools/`（含未加载文件）整体及受影响模块至少 90% 行/90% 分支，无分支记不适用；排除测试夹具、非部署 archive、非可执行规则数据和第三方，禁止排除难测业务代码。测试驱动若新增/修改可执行逻辑，另行统计覆盖，不用集成测试冒充隔离单元。

真实 parser/CLI 组件测试和人工 oracle 分开验收。最小案例须覆盖 Make 与 CMake 的同一源码链、不同 TU 共享头文件、对象别名晚绑定、if/elif/else 相同与冲突合流、重复 include/undef、固定实参传递、分散 -D 来源，以及 inactive、未引用目标、动态构造、预算和恶意项目命令反例。逐项核对 fact、关系端点、位置、状态、风险、断点与上下文，不只比较总数。

回归包括既有 source-chain、CMake demo、枚举、家族、函数多版本、候选用途、RPM/Autoconf、native crash 三项目、AVX 和固定 libarchive 822 文件输入；保存旧人工账本，新差异另行审校。两份 compiler facts 字节哈希不得变化。

性能以候选用途版本 `44c756f` 的 scanner 为对照：同镜像、输入、功能开关、2 CPU/2 GiB/无 swap、每次扫描 <300 秒，无 OOM；保持现有 1万/2万稀疏/密集矩阵并增加宏调用/多 TU 样例。计时分离采集、环境/索引、查询、投影、发布，记录新增关系、缓存、预算、工件体积。新增功能的耗时差是诊断，不恢复旧“10%+1秒”否决规则；原功能不得被关闭来达标。执行前冻结新 fixture 清单及计数期望，预算截断必须有记录而不是静默少报。若绝对资源门禁仍无法达到，先诊断并在本设计内修复；需要整体图重构或调整门禁时再请求用户确认。

## Risks / Trade-offs

- [少量支持被误认为完整预处理] → 文档、reason 和 oracle 明确子集；`#`/`##` 等边界不静默跳过。
- [宏名相同但 TU 环境不同] → 作用身份、环境缓存和 proof 消费均按 TU/configuration 隔离，测试同一头文件相反结果。
- [Make/CMake 看似有序但真实参数顺序未证明] → 语义顺序与输出排序分离，冲突保留 unknown；不采用任意 last-write。
- [状态合流/多实参导致规模爆炸] → 共享不可变状态、命中驱动物化、硬预算及统计；不扩大默认报告查询额度。
- [新正确证据改变旧结论] → 逐 occurrence 人工差异账本，禁止自动刷新所有 golden；confirmed x86 不因路径缺失被删除。
- [更精确的隔离使旧 complete 降级] → 如实报告旧证明不完整，保留局部事实，不承诺 unknown 数量只降不升。

## Migration Plan

### 2026-09-24 实施中的局部收敛

实测确认，宏作用绑定应只在各构建语言收敛后的公共入口执行一次，CMake 内部不重复绑定。宏需求索引从正式 knowledge 符号经 replacement/对象别名反向闭包选择调用；原始实参 records/facts 不裁掉。环境合流对同一不可变状态使用快速路径，语义仍按各可行分支。

共享头文件规模用例发现旧文件 include 图会把其他 TU 带入单调用查询。为此 SourceChainIndex 增加调用身份邻接索引，按当前 invocation/configuration 的已证作用文件范围限制 include 旁支；不把其他调用/TU 的边作为当前链路。关系新增额度在实体物化前检查，避免预算耗尽后遗留孤立实体。上述均为本设计内的按需查询和配置隔离落地，不改变 schema 或预算。

先冻结对照与 oracle，再按构建输入、宏状态/参数、图接线、报告四步实施，每步同步隔离单测。最后执行全量覆盖、组件/真实项目审校和规模矩阵，更新支持矩阵中的旧 CMake/输出描述及开发计划。

无需后端迁移或数据库变更，不部署生产容器。若验收发现回归，保持 change 未完成并修复；发布后回退可使用上一 scanner 版本，不能删除历史结果或 facts。同步主规范、归档及 Git 提交推送均等待对应授权。

## Open Questions

没有阻塞提案的产品选择。具体模块拆分与既有事件记录的复用在 apply 第一步确认；若必须依赖执行项目、引入原生 helper、新核心 schema 或扩大到完整预处理器，则属于超范围设计变更，须先说明理由并确认。
