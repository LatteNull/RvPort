## Context

2026-09-10 对 `parse_rpm` 的独立容器复核发现：普通 `%if "%{_target_cpu}" == "x86_64"` 未入条件栈，其下与 `%else` 下的 BuildRequires 都为 selected；`%(uname -m)` 为 unsupported；`%build` 内 Shell uname/case 样例只有 section 记录；Recommends 未提取，Requires/BuildRequires 中宏仅是原始文本。以上是前端输出观察，不等同于最终 Finding 的分类结果。

当前入口是 `frontends/build/adapters.py::parse_rpm`，通过 BuildFrontend、BuildEvidenceNormalizer 接入 BuildSelectionAnalyzer/Detector。Analyzer 主要依赖 `selectionStatus` 和 `conditionGroup` 建图，缺少显式嵌套 provenance；末尾按整个 subject 汇总 x86/通用分支，不能用来证明 RPM 某一独立条件组的路径完整性。现有 `parse_shell` 的行级分支识别也不能直接承诺完整 Shell 语义。

本 change 延续现有新 pipeline。`openspec/config.yaml` 和旧 build-selection 验收文字尚有 V1/YAML 时代描述；输出以已落地的 Schema V2 projection 合同为准：默认 V2，显式 V1，三个 artifact 不变。这里只修订受本 change 影响的验收条款，不借机整理其他模块。

## Goals / Non-Goals

**Goals:**

- 覆盖 RB-0002/3/4 的事实提取、受限语义、证据图、分类及可离线展示结果，而非只添加三个文本正则。
- 保留所有可定位架构事实；条件未知、数据角色或缺少实际依赖只影响后续判断，不改变原始事实。
- 明确宏值、宏已定义性、目标选择和依赖架构属性是不同维度。
- 使用独立测试容器、逐模块隔离单测和人工 oracle 验收，保护现有非 RPM 行为与性能预算。

**Non-Goals:**

- 不执行 spec、RPM、rpmbuild、Shell、Lua、include、编译器或项目测试；不加载宿主 RPM 环境，不查询软件包仓库，不证明包可安装。
- 不实现完整 RPM 宏语言、任意脚本解释器、复杂依赖求解器或整个构建系统；不新增 OS/ARM 迁移规则。
- 不修改前后端、compose、生产镜像、legacy/YAML 或 GCC/Clang 事实文件；不改默认 V2 和 V1 兼容结构，不为 RPM 另造结果文件。

## Decisions

### 1. 复用现有边界，把 RPM 语义拆成有界模块

保留 `parse_rpm` 公共入口，可将实现委托给 `frontends/build/rpm/` 下的 parser、macros、conditions、shell、dependencies 模块（最终文件名允许调整，职责与测试映射不得消失）。固定流程：原始 token/结构与位置 → 显式宏环境/条件求值 → scanner-owned BuildRecord/Evidence → NormalizedFact → 关系/Proof → Detector/Classifier → 现有 Projector。

字面依赖和未知构造照样进入事实层；求值模块只补充状态与 provenance，不直接输出 severity/readiness，也不从事实集合删除 inactive 或未知项。优先复用已经锁定的 tree-sitter-bash 与 `symbolic_uname`，不改变共享 Shell 行为；若抽取共用帮助函数，必须用非 RPM 回归保护原合同。

替代方案：扩展 legacy YAML 无法提供宏作用域和链路，拒绝；直接使用完整 rpm/specfile 环境违背无执行边界，拒绝；把已有 `parse_shell` 输出直接当完整控制流不可靠，拒绝。无需新运行时依赖，若实现阶段发现必须引入依赖，先评估安全和容器部署并更新设计。

### 2. RB-0002：显式、可审计的目标宏环境

宏环境区分 `known(value, provenance)`、`known-undefined`、`unknown(reason)`；宏的值与其是否已定义分别建模。识别 `%{name}`、`%{?name}`、受限 `%{?name:text}`/`%{!?name:text}` 以及 `_arch`、`_target_cpu`、`_isa`、`__isa_name`。可支持非参数化、可静态求值的 `%global/%define` 与局部宏别名，必须区分即时展开和使用时展开、定义先后及条件定义；参数化/递归/动态宏超出子集则 unknown。

`_arch/_target_cpu` 只在有依据的目标 RPM profile 下归一为扫描目标；`_isa/__isa_name` 不可仅凭 uname 字符串拼接猜值。使用显式版本化、来源可追溯的受限内置 profile，初始覆盖 riscv64/riscv32 的可核实值；未核实项保持 unknown，并仍提取事实。实现首项验收先核对 RPM 官方宏定义及展开语义，记录来源/版本；不能以 Scanner 自己的输出建立真值表。该 profile 属于打包选择语义，不修改两份编译器知识 JSON，也不自动导入宿主配置。

spec 对内置宏的显式覆盖必须保留原定义与覆盖来源；仅当覆盖值、顺序和作用域均确定时使用该值。未知条件下的定义使用分支环境，分支汇合只在各可达路径等值时保持 known，否则 unknown；不能“最后一个文本定义获胜”。

条件子集覆盖 `%if/%elif/%else/%endif`、既有 `%ifarch/%ifnarch` 与嵌套；允许已知文本/宏引用、字符串 `==/!=`、数值常量真假、`!`、`&&/||` 和分组括号，明确 token/运算优先级。其它算术、函数或表达式不得交给 Python eval 或宿主 shell。宏存在性条件必须基于 definedness，未知不得当成空字符串。

三值求值及路径合成：父路径为假即可证明子项 inactive；父路径或条件未定且没有其他完整排除证据时为 unknown；所有必要条件已证明为真才 selected。`%elif` 必须包含前面各分支均不成立的约束，`%else` 是剩余路径，不是简单反转任意最后一项。损坏/缺失终止符使受影响区域 partial/unknown，不能退回顶层 selected。

### 3. RB-0003：脚本分段、精确探测与有限数据流

先按核实的 RPM 预处理语义恢复 `%prep/%build/%install/%check` 与子包/条件上下文，再将脚本文本交给既有 Bash 语法边界；所有 byte/line/column 映射回原 spec，不能使用虚拟脚本行号。RPM 与 Shell 的注释、转义、引号和 here-document 规则必须分层处理，不能凭 Shell 引号把 RPM 层本应处理的宏或 directive 屏蔽，也不能把预处理后的纯 Shell 文本当作生效的 Shell selector。无法判定预处理或边界时保留 partial，而不是跨 section 建关系。

RPM `%(uname -m)`、Shell `$(uname -m)` 和反引号中的精确无包装命令均复用目标符号化，不产生真实进程。`%(... )` 的探测结果可以进入静态宏定义；脚本变量仅在唯一赋值和可证明作用域内传递。Shell 子集：字面/已知变量赋值、`if/elif/else` 的 `test`/`[` 字符串比较、`case` 的字面架构 alternative 和 `*` 默认分支。按 first-match 求值 case；复杂 glob、fall-through、循环、函数副作用、eval、管道、重定向及额外命令影响的值一律 unknown。

脚本中的源码列表、CFLAGS/CXXFLAGS/CPPFLAGS/LDFLAGS 赋值可产生受控 source/argument 事实；只恢复明确静态声明，不运行 recipe，也不假定每个参数赋值最终都用于构建。RPM 宏插入脚本的未知结构会污染相关控制流，不能仅解析可见文字就生成 complete proof。普通命令文本只能保留上下文；未知副作用若可能修改参与选择的变量，后续使用须失效为 unknown。

没有 RISC-V 分支时，完整匹配的 generic/default 路径可被选择；只有 x86 分支时它在 RISC-V 上 inactive。对于可选优化开关，未匹配可以是正常 no-op，不自动等于“项目缺少 RISC-V 支持”；只有足以证明某个必需选择无目标路径时，才产生确定路径缺口。探测本身不自动形成 Finding。

### 4. RB-0004：依赖 token 与架构语义分离

恢复 Requires、BuildRequires、Recommends（大小写及如 Requires(post) 的限定符），保留原文、版本比较、逐依赖位置、宏引用、所属 package/subpackage、section 和嵌套条件。支持字面依赖、版本约束及有界宏拼接；复杂 rich dependency 表达式整体保留 unknown，不拆碎后误判多个确定依赖。

依赖 `libfoo%{?_isa}` 是“目标限定的依赖”，不是固定 x86 依赖。识别架构宏不意味着存在迁移问题：完整证据证明随目标适配的 occurrence 可不进入问题 Finding，但事实保留；未知宏产生可解释 unknown；包名中出现 x86/avx 等仍只是候选，不能证明包内机器码。只有规范化架构限定/适用知识等明确依据才能确认 x86 属性，并结合目标选择证据判断影响。Recommends 是软依赖，不能直接等同 Requires/BuildRequires 的阻塞影响。

`ExclusiveArch/ExcludeArch` 继续支持，宏展开未知不得按“不包含目标”直接排除。约束本身的目标许可与外层条件激活是两个维度；inactive 的条件内有 ExcludeArch 不得变成全包拒绝 RISC-V。

### 5. occurrence 级完整图，不依赖全文件角色汇总

每个 RPM 条件组有独立稳定 identity（规范路径、package/section、位置），分支保存 branch ordinal、父条件、先行排除、来源 Evidence 和 complete/partial。宏定义/引用和脚本赋值/使用以显式引用 ID 连接；依赖/参数保存完整条件路径。不能用“同文件出现 generic”覆盖另一个条件组的 x86 路径，也不能以 `role=generic` 的包名证明实际 fallback。

Normalizer 保留这些内部元数据；Analyzer 将其转换为已有 defines/depends_on/selects/requires/adds_argument 等关系，逐 occurrence 连接到实际端点。不支持的宏/条件必须成为断点，不能仅凭单个 `selectionStatus` 标志生成 complete ProofPath。为 RPM 引入完整组与必需性门槛，替换其全 subject 缺口推断；其他格式保持原合同，除非共享帮助函数的修正有独立证据和回归覆盖。

Detector 继续产生非最终候选，Classifier 才决定影响。限定“x86 属性”“目标选择”“依赖强弱”“目标包存在性”等证据不同，任一必要维度未定都不能借另一维度补齐。沿用 fact-first 和逐 occurrence admission，禁止用一个已证明 occurrence 过滤同名但 unknown 的其它 occurrence。

预算使用现有输入上限和构建图局部额度（10,000 新关系/4,096 新 proof，不把继承图算入本地消耗）；新增宏深度、候选值、条件深度及脚本 token 预算具名且可测，禁止隐式无限递归。默认建议宏展开深度 32、条件深度 64、单值 64 KiB、候选值 64；达到边界保留事实/原因并停在 partial/unknown，不放宽现有图上限。

### 6. 输出与知识资产维持原合同

V2 复用现有 fact、occurrences、evidenceChain、source context/highlights、typed provenance 与 Classification/Assessment。宏名、展开依据、依赖限定符、package、条件组等非核心细节可用 `org.rvport.kb-scanner.rpm` 可选 extension，不改变核心枚举或顶层结构。主链按 selector → 宏/变量定义与引用 → 条件 → package/section → 命中依赖/参数 → 知识 → 判断排列，存在不确定项时明确 breaks/reason。输出中的可执行脚本文本保持转义；展示不能引入 HTML/script 执行。

V1 继续使用现有 rule/finding/trace 等兼容槽位和三个 artifact，必要的新 RPM 语义走受支持的可选信息，不移除字段或改变字段类型。某一识别事实没有 Finding 属于后续有依据的过滤，不允许从原始 snapshot 抹去。

GCC/Clang x86 数据只沿已有 KnowledgeIndex 用于参数等真正适用的匹配，其类别、ID、来源、加载方式及文件哈希不变。RPM macro profile 的 provenance 独立保存，不伪装为编译器知识。

### 7. 单测映射与验收

以下为计划职责映射；如实现改名/拆分，inventory 必须与业务文件一对一覆盖，每个实质修改文件单独达到 90% line / 80% branch，不能只看总体值。

| 业务职责/拟定模块 | 隔离单元测试 | 必须覆盖的边界 |
|---|---|---|
| rpm/parser.py、adapter 接线及 BuildFrontend | tests/unit/build_selection/test_rpm_parser.py + 既有 frontend suite | section、子包、换行/注释、损坏结构、原始位置；fake 输入读取和 delegated adapter |
| rpm/macros.py | test_rpm_macros.py | definedness、profile、define/global 时机、覆盖、条件合流、循环和预算；fake profile provider |
| rpm/conditions.py | test_rpm_conditions.py | 三值真值表、elif 残余、嵌套、unknown 与 false-parent、约束激活 |
| rpm/shell.py、safety.py 的改动 | test_rpm_shell.py | fake Bash 节点/adapter、精确 uname、变量污染、first-match、源映射、禁执行 |
| rpm/dependencies.py | test_rpm_dependencies.py | 三字段、限定符/版本、多依赖、宏、软依赖、rich dependency 降级 |
| 构建 Normalizer 的修改 | test_rpm_normalization.py | fake Evidence、引用合法性、逐 occurrence、unknown 不丢事实 |
| analyzers/build_selection.py 的 RPM 关系与缺口逻辑 | test_rpm_graph.py | fake snapshot、条件组隔离、闭合/断链、必需/可选、预算和输入乱序 |
| detectors/build_selection.py 及必要分类策略修改 | test_rpm_policy.py | fake fact/proof/knowledge、目标限定≠x86、软依赖、仅名候选、过滤与 unknown |
| 必要 V2/V1 projector/HTML 修改 | test_rpm_projection.py | fake snapshot/context reader、完整引用、精准源码高亮、HTML 转义、兼容字段 |

更新现有 build-selection inventory 和容器 runner；分类/投影有改动则同步相应 inventory，不以空实现或覆盖率排除逃避门禁。隔离单测 mock 原生 Parser 和进程调用；另设真实 tree-sitter-bash 组件测试验证语法边界，不能计作隔离覆盖的替代。

人工 oracle 冻结 RB-0002/3/4 的正例、反例、unknown、恶意输入与定位预期。端到端同时比较事实保留、选择状态、每个证明端点、Finding 影响和 V1/V2 投影，不只比条数。现有 AVX、枚举、候选语义及 libarchive 等可用真实项目基线继续回归；没有 fixture 的真实项目不临时扩大下载/执行范围，需明确缺失记录。

## Risks / Trade-offs

- [RPM profile 与发行版有差异] → 只采用核实并记录来源的 profile；未知或覆盖不清楚时保留 unknown，不以宿主环境补齐。
- [Shell/RPM 双层展开造成错位或伪控制流] → 原始位置映射、明确分段和宏 provenance；未知结构污染对应选择链，不能生成完整 proof。
- [条件修正引起报告数量变化] → 用逐 occurrence 人工 oracle 解释新增/消失，不以旧条数阻止正确修复，也不自动重写 oracle。
- [过度扩大范围成完整解释器] → 明确语义白名单、预算和断点；不执行任何项目命令，不扩大到包可用性或真实构建。
- [新增事实增加图成本] → 沿用局部图预算、避免跨条件组笛卡尔积；用低预算和大量无关继承图验证确定性。

## Migration Plan

1. 冻结现状样例和独立人工预期，核实 RPM 宏 profile，补齐单元 inventory。
2. 分别完成有界条件/宏、脚本、依赖事实，再接入正式关系、分类与投影；每阶段带对应单测。
3. 在独立 `rvport-kb-scanner-test:local` 容器中执行新增门禁和完整回归；不安装宿主依赖、不重建生产镜像。
4. 更新本地支持矩阵、RPM 分析基线与重写开发计划。飞书状态不得在实现验收前改成已完成；本 change 不自动写远端文档。
5. 验收通过后按 OpenSpec 流程同步归档。若需回退，只回退本 change 的实现与映射，保留事实 JSON 及报告格式；不重启 legacy runtime，不执行危险 Git 重置。

## Open Questions

- 实现前需锁定 RPM 官方宏来源版本以及 riscv32/riscv64 profile 中可核实的 ISA 值；无法核实的项明确 unknown，不阻止该宏的识别与链路输出。
- RPM optional extension 是否必需由既有 projector 能力决定；若现有 slots 足够则不添加，任何新增字段必须是可选且有契约测试。
- 无需用户额外选择即可进入 apply；以上问题是实现期可通过官方定义、fixture 与现有合同解决的技术核对项，不授权放宽静态边界。

## Implementation resolution (2026-09-10)

- Profile 固定为 upstream RPM 4.20.0：riscv64 ISA 为 riscv/64；riscv32 ISA 未核实，保持 unknown。来源与边界见 `docs/rpm-architecture-analysis.md`，不读取宿主配置。
- 启用可选 `org.rvport.kb-scanner.rpm` extension。RPM occurrence 图复用既有 target selector 身份，避免改变非 RPM 测试证明；V2 源码边以真实端点投影。
- 新增 `rpm/records.py` 和 `analyzers/rpm_selection.py`；Normalizer/Detector/Policy 的 RPM 隔离案例统一在 `test_rpm_graph.py`，投影在 `test_rpm_projection.py`。最终逐模块映射为 `tests/rpm-architecture-test-inventory.json`。
- 宏采用单值/unknown 合流，而非枚举 64 个候选值；增加共享展开工作上限 4,096，避免递归别名指数展开。RPM 条件深度到限停止后续结构恢复并明确 partial；不声称未解析部分已覆盖。
- 391 项专项单元门禁、213 项完整回归和 libarchive 最终复扫通过；14 个模块均达到 90% line / 80% branch。兼容矩阵仅更新人工审校过的诊断哈希，不更新既有 Finding 语义哈希或编译器事实。
