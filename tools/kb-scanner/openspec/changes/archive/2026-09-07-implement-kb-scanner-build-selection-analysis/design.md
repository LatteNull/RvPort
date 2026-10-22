## Context

阶段 1—5 已建立 scanner-owned core、正式 C/C++ frontend、generated/curated knowledge、Local Detector 和 Evidence Graph。当前 qualification 可以解释源码内 include、宏、调用、条件 sibling 与 alternative，但输入工作区只正式恢复 C/C++ 文件；Make、Autoconf、CMake/Meson 机器产物和 RPM 的选择语义仍在 Legacy 或 technology spike 中，无法证明某个 x86 源文件、参数或依赖在目标 RISC-V 构建中是 selected、inactive 还是 unknown。

已有技术选型已经在独立 `kb-scanner-test` 容器中锁定 tree-sitter-make 1.1.1、tree-sitter-bash 0.25.1 和 NetworkX 3.6.1，并拒绝把会初始化 RPM 求值环境的 `specfile` 作为 runtime。本 change 把这些结论正式化，但不修改 Legacy parser/evaluator，不切换默认 CLI，也不安装任何宿主机或生产镜像依赖。

## Goals / Non-Goals

**Goals:**

- 从项目内受支持的构建、配置、机器产物和 RPM 文件恢复稳定、可定位、可追溯的 Entity/Evidence/NormalizedFact。
- 对 Make 和有限架构 selector 执行无副作用、有预算、可解释的静态部分求值。
- 以目标 `riscv64`/`riscv32` 为输入，建立“selector → condition → source/directory/argument/dependency → target/package”的 Relation 与 ProofPath。
- 明确区分 selected、inactive、not-selected 和 unknown；缺失输入、动态表达式和预算截断不能被解释为 RISC-V ready。
- 将构建选择 Observation 接入 staged qualification，为阶段 7 Classifier/Assessor 提供事实，不在本阶段决定最终 blocker、severity 或 readiness。
- 以 AVX 4 个 Makefile 的 24 个 x86 flag 和专门构建 fixture 作为人工审计 correctness baseline。
- 保持现有 schema 1.0、三个 artifact、Legacy 行为、YAML/`generatedSet` 和两份 compiler-derived JSON 原样不变。

**Non-Goals:**

- 不执行 Make、shell、configure、Autom4te、CMake configure、Meson setup、CTest、RPM 宏、Lua、compiler、linker 或项目测试。
- 不实现完整 GNU Make、POSIX shell、M4、CMake language、Meson DSL 或 RPM 宏求值器。
- 不分析交叉编译环境中 `uname` 选错分支；精确识别的 `uname -m` 始终按 ScanContext 的目标 RISC-V 值作符号替换。
- 不分析操作系统、内核、系统调用、驱动和板级迁移，不重实现 RVWMO 检查。
- 不完成测试覆盖分析、最终分类、项目级评估或兼容报告切换。

## Decisions

### 1. 保持现有管线阶段，使用组合 frontend/normalizer/analyzer

不新增一个会迫使所有 profile 改签名的顶层 `BuildSnapshot` 阶段。新增 `ProjectWorkspaceCollector` 发现 C/C++ 与构建输入，`CompositeProjectFrontend` 将输入路由给 C/C++ 和 build frontend 后合并为现有 `FrontendSnapshot`；`CompositeNormalizer` 合并源码与构建事实；`CompositeAnalyzer` 先运行现有源码 Evidence Graph，再运行 Build Selection Analyzer 并验证统一 `AnalysisSnapshot` 引用。

选择该方案是因为核心 `FrontendSnapshot`、`NormalizedSnapshot` 和 `AnalysisSnapshot` 已经是技术无关的 Entity/Evidence/Fact/Relation 容器，可以表达多输入而无需制造第二套内部结果。备选方案是新增 BuildSnapshot 和新 orchestrator stage，但它会扩大 protocol、recording test 和 projector 参数面，却没有提供额外语义隔离。

所有组合器必须确定性合并状态和 Diagnostic：任一可恢复 adapter partial 时保留其他结果并使整体 partial；引用不完整或核心不变量失败时才 failed。现有 `CppWorkspaceCollector`、`CppFrontend` 和 `CppEvidenceNormalizer` 保持行为不变，由新组合器调用而不在 Legacy 或既有模块中塞入构建逻辑。

### 2. 构建 frontend 只恢复语法和已存在机器事实

新增 `kb_scanner/frontends/build/` 正式包，输出 scanner-owned 对象：

- workspace/router：按确定优先级识别 Makefile/包含文件、`configure`、`config.sub`、`configure.ac`/M4、CMake File API reply、Meson introspection、CTest 元数据、`compile_commands.json` 和 RPM spec；只接受 workspace 内路径。
- Make adapter：tree-sitter-make 恢复 assignment、condition、include、target、recipe 边界和 SourceSpan。
- Shell adapter：tree-sitter-bash 仅从已有 `configure`/`config.sub` 恢复 assignment、case/if、架构模式和命令替换，不执行脚本。
- M4 recognizer：scanner 自有 tokenizer/有界调用识别，仅恢复已批准宏调用、架构条件和字面参数。
- CMake/Meson/CTest readers：使用严格边界 model 读取已经存在的版本化 JSON/index/reply；绝不生成这些文件。`CTestTestfile.cmake` 只做有界声明识别，测试角色解释留到阶段 7。
- RPM adapter：在新正式模块中实现 scanner-owned 轻量 section、`%ifarch/%ifnarch`、`ExclusiveArch/ExcludeArch`、依赖和命令 section 边界；Legacy RPM 逻辑只作为 fixture 行为参考，不导入、不修改，`specfile` 仍不进入 runtime。

原始语法节点、Pydantic model 或第三方异常不得离开 adapter。机器产物中的绝对路径只有在可证明位于 workspace 内时才规范化，否则产生 partial Diagnostic；文件缺失表示 unavailable/unknown，不表示未选择。

### 3. Make 使用 scanner 自有受限值域和求值器

Make evaluator 消费已解析 Evidence，不重新读取任意文件。值域使用 `KnownScalar`、`KnownList`、`Alternatives` 和带 reason/evidence 的 `Unknown`；环境是不可变快照，变量定义保留 simple/recursive/append/conditional 赋值类型和 provenance。首版支持：

- 字面文本、空白分词、已知变量引用、`:=`/`=`/`+=`/`?=`；
- `ifeq`/`ifneq`/`ifdef`/`ifndef` 及其 else 链；
- 解析后为 workspace 内静态相对路径的有限 include；
- 静态列表拼接、常见源码后缀和编译/链接参数集合；
- 明确的 target/ prerequisite/变量绑定和 architecture alias 比较。

include 深度、读取文件数、变量展开步数、候选值数和输出关系数全部使用显式常量预算；循环、动态 include、pattern/function/call/eval/foreach/wildcard 或超预算进入 Unknown。配方文本永不求值。这样比调用 `make -n/-p` 安全，也比仅做正则命中能恢复变量流和分支 provenance。

### 4. `uname -m` 是不执行的符号 selector 特例

安全扫描仍把 shell 路径视为不可信。唯一特例是语法和 token 均精确匹配、没有重定向/管道/额外命令的 `uname -m` probe：adapter 记录 architecture-probe Evidence，evaluator 直接从 `ScanContext.target_arch` 注入规范化的 `riscv64` 或 `riscv32`，从不调用 subprocess。它可出现在已生成 shell 的 command substitution、case selector，或 Make 的 shell/`!=` 赋值中；后者同时保留“包含命令型语法但已由安全符号语义处理”的 provenance。

任何拼接、包装、环境前缀、未知参数或其他命令都保持 unsupported/unknown。分析假定 probe 返回正确机器架构，不创建“交叉编译选择错误”路径。若有 RISC-V 分支则选择它；若没有专用分支但有 generic/portable/scalar/fallback 则选择通用路径并将 x86 路径标为 inactive；两类路径都没有时创建 `missing_target_path` Observation，而不是声称 RISC-V 会选择 x86。

### 5. 已有机器产物是可追溯 Observation，不是自动真相

CMake File API、Meson introspection、CTest 元数据和 compilation database 只表示某次已生成配置。reader 必须保存 schema/version、逻辑文件、target/configuration identity 和原始字段位置或 JSON pointer，并在可能时关联源码、参数、依赖和产物。若产物架构与 ScanContext target 可确认一致，可作为 RISC-V selection proof；架构缺失或不一致时只作为 observed candidate/partial，不能覆盖源码级 selector 结论。

不采用运行 CMake/Meson 生成 metadata 的方案，因为生成过程会加载项目代码。也不把 compilation database 中某文件出现简单等价为它一定进入 RISC-V 目标；必须有目标架构和 target provenance，或者保持 unknown。

### 6. Build Selection Analyzer 向同一 Evidence Graph 添加有类型关系

新增的 build entity 至少包括 architecture selector、build variable、condition group/branch、source set、directory、compile/link argument、dependency、target、package 和 package section。关系至少包括 `defines`、`depends_on`、`has_branch`、`guarded_by`、`selects`、`excludes`、`adds_argument`、`requires`、`produces`、`alternative_to` 和 `reachable_from`。

Relation status 统一为 `selected`、`inactive`、`not_selected` 或 `unknown`，并保留 target architecture、producer、Evidence ID、求值原因和 completion metadata。ProofPath 从 architecture selector 或 observed target configuration 出发，到达源码/参数/依赖/target；每一步必须是已注册关系。`not_selected` 只用于被完整、互斥且可确定条件排除的分支；没有发现关系不得推导为 not-selected。

Build Selection Analyzer 经 scanner-owned GraphStore 合并已有源码 Entity/Relation，使构建 source path 能关联 C/C++ source file，编译参数可关联 knowledge-backed x86 Observation。GraphStore 不自行执行求值或推断，所有选择状态来自有 provenance 的 analyzer 结果。

### 7. Detector 产生构建选择 Observation，最终分类仍延后

组合 Detector 在保留现有 LocalX86Detector 输出的基础上消费 build relations/proofs：

- x86 源码/参数/依赖对 RISC-V `selected`：产生 `build_selected_x86_dependency` Observation；
- x86 路径被完整 selector proof 排除：产生或补充 `build_inactive_x86_path` 上下文；
- 无 RISC-V 或通用选择路径：产生 `missing_riscv_selection_path` Observation；
- 动态表达式、缺失 metadata 或预算截断：产生 `build_selection_unknown` Observation/Diagnostic。

这些类型只表达可追溯事实和候选迁移缺口，不携带最终 blocker、severity 或项目 readiness。阶段 7 负责结合源码依赖、替代实现和测试选择进行分类。

### 8. 兼容投影和迁移方式

本 change 只接入 staged qualification；默认 `ScanApplication` 继续选择 Legacy compatibility profile。新 build Entity/Evidence/Relation/ProofPath/Observation 留在内部 snapshot，recording/no-op Projector 不写 artifact。后续 cut-over 时 proof 只能投影到现有 Finding `trace` 或其他可选兼容字段，不能产生第二个主结果；`schemaVersion: "1.0"`、顶层字段、三个 artifact 和退出码语义不变。

两份 compiler-derived x86 JSON 仍由现有 Knowledge Provider 原样加载，build compile arguments 经 Normalizer 与同一 KnowledgeEntry 匹配并保留 source provenance；本 change 不修改它们的内容、哈希、六类计数或 YAML `generatedSet`。

### 9. 每个业务模块必须有隔离单元测试映射

新增 `tests/build-selection-test-inventory.json`，逐项映射 workspace/router、各格式 adapter、Make value/evaluator、build normalizer、selection analyzer、detector 和组合器。纯模块用内存字符串/对象；文件系统用临时只读 fixture；Tree-sitter、JSON reader 和 GraphStore 边界使用 fake/mock 精确触发成功、partial、failed 和异常；subprocess/命令入口必须用拒绝型 fake，并以 marker 文件断言零副作用。

隔离 unit suite 在唯一 `kb-scanner-test` 容器中对新增/修改业务包执行至少 90% line、80% branch 门禁。parser/component、真实机器产物、AVX、staged qualification、Legacy compatibility 和完整回归单独运行，不计入隔离 unit 覆盖数字。Dockerfile.test/compose.test.yml 可增加测试命令或锁定 runtime 依赖，但不修改宿主机、生产镜像或根 Compose。

## Risks / Trade-offs

- [Risk] Make/M4/RPM 语言远大于支持子集，用户可能误把 partial 当完整结论。 → 每个 unsupported/budget/missing-input 原因进入稳定 Diagnostic 和 path completion，qualification 总状态传播 partial。
- [Risk] `uname -m` 特例被宽泛匹配后可能掩盖命令执行。 → 只接受解析后精确 token 形状，绝不调用 shell；任何 wrapper、管道、重定向和额外参数都拒绝。
- [Risk] 同时存在源码配置和过期机器产物时产生冲突。 → 保留 producer/configuration identity，冲突状态为 unknown/partial，不使用覆盖优先级猜测。
- [Risk] 构建图的平行关系和候选值组合爆炸。 → 对 include、展开、候选值、关系和 proof 设置预算，确定性截断并保留已证明路径。
- [Risk] 新组合 frontend 影响已有 C/C++ identity 或排序。 → C/C++ adapter 不改，组合器按稳定 ID 合并；以现有 frontend/graph baseline 和完整回归做契约门禁。
- [Risk] 轻量 RPM 实现与真实 RPM 宏语义不同。 → 只对明确支持的 section/架构条件作结论，其他宏、Lua、shell/include 一律 unknown；不引入完整 rpm/specfile runtime。

## Migration Plan

1. 固化多格式行为矩阵、AVX 24 flag oracle、安全恶意 fixture 和机器产物 fixture。
2. 添加 scanner-owned build vocabulary、发现/router 与各格式纯解析 adapter及隔离单元测试。
3. 添加 Make 受限值域/evaluator、RISC-V selector 语义和预算测试。
4. 添加 build normalizer、Build Selection Analyzer、图关系/proof 与 detector Observation，并逐层通过引用完整性测试。
5. 接入新的 qualification 组合 profile，运行 build-selection unit coverage、parser/component、AVX、staged、Legacy/output 和 full regression。
6. 保持默认 Legacy profile；若 qualification 失败，可移除新 profile 接线而无需迁移或回滚现有报告数据。

## Open Questions

- 真实项目若提供多个 CMake/Meson configuration，首版是否全部并列保留，还是仅对能证明与 target_arch 一致的 configuration 建立 selected proof？默认设计为全部保留、仅可证明匹配者 selected。
- `config.sub` 对不认识 RISC-V triplet 的判断需要覆盖哪些历史拼写和版本？实施时由人工 fixture 与 accepted architecture alias knowledge 固化最小集合，不通过宽泛子串猜测。
- CTest 元数据在本阶段只恢复 target/command/source 关联；测试角色和覆盖关系是否需要额外字段，将在阶段 7 proposal 中决定。
