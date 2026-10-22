## Context

当前 `ProjectWorkspaceCollector` 已执行输入过滤和路径边界检查；`CompositeProjectFrontend` 合并 C/C++ 与构建输入；`CompositeAnalyzer` 依次生成源码图、构建选择和测试关系。源码图的 `alternative_to` 来自同一条件组，而不是路径相似度。V2 Finding 必须有真实源位置，因此文件名本身不适合伪装成一条代码 Finding。

本设计接续 proposal 中的“结构候选发现”范围：扩充已知信息，但不通过文件名替代证明。现有默认 V2、显式 V1 和两份编译器事实数据保持不变。

## Goals / Non-Goals

**Goals:**

- 在没有 compile database 或构建绑定时，仍能发现局部架构实现家族。
- 回答找到哪些 x86/RISC-V/通用候选、为什么分到一起、哪些选择关系已证明、哪些仍未知。
- 保持结果确定性、引用完整性、输入安全、线性分桶及有界输出；不影响已有 confirmed fact 和 occurrence。

**Non-Goals:**

- 不证明函数行为等价，不做跨模块任意同名函数匹配、函数多版本 default 分析或跨函数值流。
- 不补齐任意构建 DSL、预处理器，也不把所有未知候选都变成问题。
- 不执行扫描项目、不扫描根外文件、不安装本机依赖、不修改后端/UI 或生产容器。
- 不包含 ARM 迁移、操作系统、独立汇编、真实编译/测试和交叉编译误选。

## Decisions

### 1. 从一次授权清单传递路径观察，不重新扫描文件系统

在 frontend 组合边界增加轻量 scanner-owned inventory adapter，消费同一次 WorkspaceSnapshot 的 C/C++ 文件清单与收集状态。复用 C++ source file 的稳定 ID；解析失败或空文件仍可有路径实体，但不得声称存在代码事实。通过实体 properties/现有 snapshot metadata 合同传递 `pathObservation` 与收集范围，不将文件名送进 intrinsic/宏检测器，不创建虚假行号。实现在既有字段承载不足时只能扩展内部默认值字段，不能改变外部 schema。

新增 `ArchitectureFamilyAnalyzer` 放在源码/构建/测试分析完成之后、Detector 之前，消费当前同一快照的文件实体、关系和 proof。它不重复访问磁盘或重跑 parser。单文件扫描仍可形成一个成员的候选家族，但必须说明观察范围只有该输入。

替代方案：Analyzer 内 `rglob` 会绕过排除与安全边界；只消费有 intrinsic 的文件会漏掉尚未绑定的 generic/RISC-V 实现，均不采用。

### 2. 使用可解释的局部路径模板，不做全项目模糊聚类

首批规则固定且版本化，角色词按独立路径组件或 basename 前后缀匹配，不做任意子串匹配。路径存储和 ID 保留大小写，角色比较可大小写无关；同名大小写碰撞记录歧义，不合并实体。

| 模式 | 候选分组 | 隔离边界 |
|---|---|---|
| `src/foo_x86.cpp` / `src/foo_generic.cpp` | 同目录，移除有界角色前后缀后的相同非空 basename 与相同扩展名 | 保留完整父目录，不跨 vendor 或子项目 |
| `src/arch/x86/math/foo.cpp` / `src/arch/riscv/math/foo.cpp` | 角色目录替换为占位符后，剩余完整相对路径一致 | 保留架构目录前缀及其后的相对路径 |
| `src/foo_x86.cpp` / `src/foo.cpp` | 有 x86 锚点的同目录精确剩余 basename | 无后缀者为 unlabelled 候选，不自动标记 generic |
| `arch/x86/foo.cpp` / `arch/arm/foo.cpp` | 可保留 foreign 成员作结构上下文 | 不产生 ARM 迁移 Finding |

候选词表包括 x86/i386/i686/x86_64/amd64/x64 及有边界的 AVX/SSE 变体、riscv/riscv32/riscv64、generic/portable/scalar/fallback；foreign 仅保留 arm/arm64/aarch64 等上下文。词表是路径启发式配置，不能冒充已经收集的 compiler knowledge；每个命中保留原词、匹配规则 ID/版本和路径片段。

第一版仅支持单个可识别角色槽位。多角色冲突或多个非等价模板均保留 ambiguous，不猜最近目录，不用传递闭包把多个弱相似关系合成大组。`.h` 与 `.cpp` 不自动成为替代实现，跨目录裸文件名不自动匹配。家族至少有一个 x86 角色候选才进入本次 x86→RISC-V 目录；纯 RISC-V/ARM 项目不新增家族问题。

替代方案：全项目 basename 匹配会把不同压缩算法、vendor 和测试文件混在一起；编辑距离/嵌入聚类难以审计且误合并风险高，本次不采用。

### 3. 分离三个独立维度

内部 `FamilyRecord` 保存稳定 ID、局部 scope、模板、成员、候选状态、发现范围与截断信息；`MemberRecord` 保存路径、复用 file ID、角色线索、规则来源、解析状态。配置相关选择保存在独立 binding 中，不把一个配置的状态写成文件全局属性。

- `discoveryStatus`：在已授权扫描清单中，候选枚举是否完成。complete 仅表示该清单/模板处理完毕。
- `roleHint` / `candidateStatus`：路径推测及其歧义，不是执行架构确认。
- `bindings`：同一成员、同一 configuration 的现有 selection/proof，以及它与已有替代关系的关联；不存在时保持 unknown。

允许记录 `no-candidate-observed-in-scope`，禁止输出“已证明没有 generic/RISC-V”。即使收集范围完整，未命名的另一种实现也可能未被模板覆盖。路径叫 generic 但内含 AVX 时，保留 generic 名称线索及真实 AVX fact，不互相覆盖。

### 4. 图关系仅作候选索引，复用已有证明而不生产等价证明

增加 `architecture_family` 实体及 `candidate_member_of` 非执行关系；关系 properties 明确 `semanticRole=candidate`、规则来源和观察路径。没有代码 Evidence 时不虚构 evidence ID，结构来源在内部成员记录中可核查。

家族 Analyzer 复用 source file ID，并建立按 `(fileId, configuration)` 索引到已有选择/替代 proof 的绑定。第一版不凭名称创建 `alternative_to`；只有已存在且通过端点/范围/配置校验的真实 sibling/build/source proof 才能被展示为“已有证据支持的候选关系”。同 target 中共同编译两个文件、同名函数、相邻目录均不构成互斥替代证明。

审计图查询、proof closure 和 projector 的关系白名单，保证 `candidate_member_of` 不进入执行依赖或源码 primaryPath。已有证明仍由既有分析器和分类策略解释，家族分组不改变它的语义。

### 5. 候选丰富解释，不按名字改变风险

不为纯路径成员创建迁移 Observation/Classification，也不因路径增加 issue/blocking/portability-gap 计数。已有关联 Finding 获得候选补充，但 fact、主 occurrence、severity、blocking 和现有证据结论不因名称变化。

未绑定 generic 候选不能消除已证明 AVX blocker；同样，只有 x86 名称也不能制造 blocker。家族发现失败或截断以独立诊断/完整性字段表达，不把整个项目自动升级为 ready，也不抹掉已有独立完整 proof。发现到但未证明的候选不伪装成“已验证替代路径”。

本 change 不增加新的缺口判定算法：是否有替代、是否必选、是否阻断仍使用已有闭合 proof。这样可独立验收家族能力，后续再扩展功能/选择语义。

### 6. 通过已有 extension 表达路径信息，保持 Finding 自包含

使用 `org.rvport.kb-scanner.architecture-family` namespace：

- V2 顶层既有 `extensions` 内输出有界 family catalog：规则版本、发现范围、候选家族及成员、状态、遗漏计数/原因。路径-only 或空文件家族也可见，不新增顶层核心字段或核心枚举。
- 相关 Finding 的 `fact.extensions` 内嵌所属家族必要成员、原始路径/角色依据、当前配置 binding 状态和可核查来源；不要求消费者回查 catalog。仅以确切 source file ID 关联，不按 symbol 名跨文件挂载。
- 可展示的 source/proof 引用必须在该 Finding 内闭合；不能闭合时仅输出路径结构描述及 unknown，不发布悬空 typed ref。extension 不是绕过引用检查的后门。
- 纯路径描述不进入 `fact.primaryLocation`、`occurrences` 或代码 step，禁止用文件第一行冒充名称命中。真实选择/源码链仍沿已有边展示，各节点有自己的 ±20 行上下文；没有关系不能把两个实现串成一条执行链。
- 新增面向用户的候选说明提供中文/英文配对（如 explanation/explanation_en）；标识和 role 枚举保持机器值。已有 suggestion/suggestion_en 不改变。
- 显式 V1 保持既有字段形状及 Findings；路径-only 目录不强塞成 V1 代码 finding。遇到截断等运行诊断沿既有 diagnostic 合同报告。HTML 仅增加有界中文家族摘要或关联候选提示，不做交互图页面；需 HTML 转义和无位置成员展示回归。

替代方案：新增 Finding kind 或把路径伪造成第 1 行会破坏位置语义并增加噪声；引入第二个结果文件会增加后端接入，本次均不采用。

### 7. 确定性与性能预算

按规范化路径模板做哈希分桶，再进行稳定排序；最多每文件两个非冲突候选模板，不全量两两比较、不生成成员笛卡尔积边。ID 只使用规则版本、项目相对 scope、模板/路径，不含绝对路径、扫描时序或对象地址。

初始 scanner-owned 上限：参与路径 100000、家族 10000、每家族 128 成员、proof 绑定复用既有图预算；V2 catalog 最多 1000 家族/10000 成员，每个 Finding 最多 8 家族/128 成员并服从既有输出预算。上限应作为具名常量/预算对象可单测；实际调整须记录测量依据且不能静默丢失。截断先稳定排序，保留已观察总数、已输出数、稳定 reason；扫描推导状态与输出裁剪状态分别记录。不得为丰富报告重新运行 proof 搜索。

### 8. 单元测试映射和验收

| 业务职责/预期位置 | 隔离测试重点 | 隔离边界 |
|---|---|---|
| frontend inventory adapter / composite frontend、normalizer 的传递 | 空/失败解析文件、排除后清单、source ID 复用、不丢原事实 | WorkspaceSnapshot 与 parser fake |
| `analyzers/architecture_family/paths.py` | 分隔符/大小写/角色边界、非空 key、扩展名、冲突词 | 纯路径输入，不访问磁盘 |
| `analyzers/architecture_family/grouping.py` 及内部 records | 局部 scope、单成员、foreign、歧义、排序/ID/预算 | 合成清单、具名预算 |
| `analyzers/architecture_family/bindings.py` 与图接入 | source ID、配置隔离、proof 完整性、非法引用、候选边白名单 | 合成图或 GraphStore fake |
| `pipeline/composite.py`、受影响的 classifier/assessor/query | 顺序/失败传播、候选不改变原结论、完整 proof 不被抹掉 | 各 analyzer fake，禁止真实解析代替单测 |
| V2 family projector、mapper/projector/validation/renderers 与 V1 受影响路径 | 自包含、无假行号、合并而非覆盖其他 extension、双语、HTML 转义、预算 | 合成 snapshots、source reader/publisher fake |

文件名可在实现中按既有结构细化，但全部新增/实质修改业务模块必须进入机器可读 unit inventory。独立容器内执行现有 `tests/run_source_chain_unit_tests.py`，统计所有自有 `kb_scanner/`、`scripts/`、`tools/` 可执行代码，含未加载模块；整体与受影响模块行/分支均至少 90%。排除第三方、生成 JSON、测试 fixture/runner 和未部署 archive 的理由沿用现有记录，不排除业务逻辑。

另建固定人工 oracle 覆盖正例和反例、默认 V2/显式 V1/HTML 合同、Make/CMake/Autoconf 选择绑定，并跑现有完整回归。性能使用合成 10000/20000 路径和固定真实 fixture，记录分桶次数、关系数、运行时间与峰值内存；操作计数不得出现两两枚举，真实项目中家族步骤开销超出基线总时长 10% 且超过 1 秒时必须调查修复或说明并经确认，不能默默接受。

## Risks / Trade-offs

- [名称不等于架构语义] → 所有路径角色是候选；保留 compiler-backed 事实和原有风险。
- [模板覆盖窄，漏掉混合命名或跨目录 fallback] → 首版宁可明确 unknown，不跨模块猜测；以后用人工样例扩展规则版本。
- [路径实体污染执行图] → 独立关系 kind、遍历白名单与对抗单测；不得新增候选到执行 proof 的隐式转换。
- [相同家族在多个 Finding 重复] → 单个 Finding 自包含优先，使用双层输出预算、稳定 ID 和显式截断。
- [旧 reader 忽略 extension] → 原 Findings 仍可用；新家族展示为可选增强，不要求同步部署后端。

## Migration Plan

先固化人工 fixture/oracle，再实现候选发现、证明绑定和投影，最后运行隔离覆盖率、完整回归、字段差异和性能检查。仅更新独立测试容器，不重建生产。实现完成后提交验证文档，等待用户授权同步/归档；部署另行授权。

无数据库或输出 schema 迁移。回滚可以恢复上一个 scanner 版本；新增 extension 可被旧消费者忽略，禁止为回滚修改原始知识和历史报告。

## Open Questions

暂无阻塞性用户选择。混合扩展名、多个架构槽位以及更广泛命名词表，首版明确不自动合并；后续依据真实项目审校决定是否单开 change 扩展。
