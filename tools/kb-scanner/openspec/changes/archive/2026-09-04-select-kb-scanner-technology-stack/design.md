## Context

KB Scanner 当前作为 Python CLI 被复制进 `backend/Dockerfile` 的 runtime 镜像，由后端 worker 通过独立进程调用。当前镜像只显式安装 `python3` 和 `python3-yaml`，API 与 worker 使用同一镜像。扫描器未来可能需要 Tree-sitter、LLVM/Clang、证据图和模型校验等依赖，但本 change 只在独立测试容器中验证这些候选，不修改生产镜像或部署拓扑。这些依赖也不应安装到开发者宿主机，且容器测试不能执行不可信项目中的任意构建逻辑。

现有扫描器已经有 41 个单元测试、24 个 YAML 规则文件、`compile_commands.json` 增强上下文，以及必须原样保留的 `clang-x86-entries.json` 和 `gcc-x86-entries.json`。本 change 的职责是验证和固化技术栈、建立容器化依赖与测试入口，并为后续分析核心实现 change 提供可执行结论；不在本 change 内完成整个扫描器重写。

技术选型遵循 reuse-first：已有成熟技术能够提供解析、图存储、模型校验或忽略规则能力时，优先通过适配器复用；只有目标架构选择、证据解释等领域语义没有合适实现，或者候选技术无法通过安全、准确性和资源验证时，才开发受限自有实现。

## Goals / Non-Goals

**Goals:**

- 选择并验证 C/C++ 基础解析、Clang 语义增强、Evidence Graph、模型校验和工作区过滤技术。
- 明确 Makefile、Autoconf、RPM、CMake 等输入的安全静态分析边界。
- 将 Python 和原生分析依赖锁定在容器镜像中，不修改或依赖宿主机 Python 环境。
- 在独立的 `tools/kb-scanner/Dockerfile.test` 中提供 `kb-scanner-test` image target，并通过专属 `tools/kb-scanner/compose.test.yml` 作为一次性独立容器运行。
- 测试容器与现有根 Compose 完全分离，可独立构建、启动、停止和清理，不接入现有服务的网络、卷或业务凭据。
- 以容器内 fixture、契约、安全和性能 spike 记录可复现选型证据。
- 保持当前 CLI 调用方式、三个 artifact、`schemaVersion: "1.0"` 和后端 parser 兼容。
- 保留全部现有 YAML/生成知识资产及其来源。

**Non-Goals:**

- 不在本 change 内实现完整 Fact/Evidence/Relation/Assessment 核心。
- 不在本 change 内实现 Make/Autoconf 部分求值器、跨文件宏分析器、测试覆盖分析器或 readiness 状态机。
- 不执行真实 RISC-V 编译或测试。
- 不在宿主机安装、升级或卸载 Python、Clang、Make、RPM、CMake 或相关依赖。
- 不修改 `backend/Dockerfile`、根 Compose、生产 API/worker 镜像或生产部署方式；候选技术的生产接入由后续独立 change 决定。
- 不把 GNU Make、Autom4te、RPM 或 CMake configure 直接用于默认的不可信项目扫描。
- 不改变后端 API、数据库 schema、任务队列或 KB Scan 结果结构。

## Decisions

### 1. 继续使用 Python，并把依赖基线定义在容器而不是宿主机

扫描器核心继续使用 Python。现有 CLI、规则、fixture、报告和 memory-model checker 均为 Python，当前没有性能数据证明需要切换语言。Ubuntu Noble runtime 中的 Python 版本和依赖版本由镜像构建固定，开发者宿主机版本不作为受支持运行环境。

扫描器建立显式 runtime/test 依赖清单和锁定结果。候选依赖分为：

- runtime：PyYAML、Tree-sitter runtime、C/C++ grammar、pathspec，以及通过 spike 的图存储和边界模型库。
- native/runtime：版本匹配的 LLVM/Clang、libclang 和必要时预编译的 LibTooling helper。
- test：JSON Schema/契约验证、基准和测试辅助依赖。

备选方案是在宿主机创建 venv。该方案仍会让不同开发机上的 Python、LLVM 和原生 wheel 漂移，因此不采用。

### 2. 使用分层 C/C++ 前端：Tree-sitter baseline + Clang enrichment

Tree-sitter C/C++ 作为 baseline frontend，负责在没有完整 include、宏定义或 compilation database 时提供容错 CST、预处理指令、调用、类型和源码位置。它必须覆盖所有可发现 C/C++ 文件，解析错误通过 Evidence/diagnostic 暴露。

LLVM/Clang 作为 enrichment frontend。存在有效 `compile_commands.json` 时，使用版本匹配的 libclang detailed preprocessing record 验证宏定义、宏实例化、include 和语义实体；如果 Python binding 无法保留所需宏 provenance，再使用容器构建阶段编译的小型 LibTooling `PPCallbacks` helper。Clang 不替代 Tree-sitter，也不因单个 translation unit 失败而终止全项目扫描。

传给 Clang 的 compilation arguments 必须经过 allowlist/denylist 规范化，禁止加载插件、任意 response file 或产生非预期副作用的参数。Clang 缓存和临时输出只能写入任务工作目录。

备选方案包括只保留正则、只使用 Clang、Semgrep 或 CodeQL。正则不足以支持结构关系；只使用 Clang 会在缺失构建上下文时失去覆盖；Semgrep 开源版和 CodeQL 的跨文件/构建要求不符合本模块边界，因此不作为核心前端。

### 3. 复用成熟输入元数据，但不主动执行项目配置

以下已有机器可读产物可以直接作为 Evidence 输入：

- `compile_commands.json`。
- 已存在的 CMake File API reply。
- 已存在的 Meson `intro-targets.json`、`intro-tests.json` 和 `intro-benchmarks.json`。
- 已生成的 CTest JSON 或 `CTestTestfile.cmake`。

扫描器默认只读取这些产物，不运行 CMake configure、Meson setup、CTest 测试、Bazel query 或其他可能加载项目代码的生成步骤。产物不存在时维度为 partial/unknown，并继续使用源码级静态分析。

### 4. Make/Autoconf 使用现有语法技术，自研受限语义子集

Makefile 候选采用维护中的 community Tree-sitter Make grammar，仅用于 CST 和位置恢复。由于 GNU Make 在变量展开时可执行 `$(shell ...)`、`!=`、`eval` 等逻辑，扫描器不得使用 `make -p/-n` 对不可信输入求值。后续 change 只实现已确认的变量赋值、条件、有限 include、字符串/列表拼接、架构 selector 和静态源码集合子集；不支持的表达式输出 unknown/diagnostic。

Autoconf 源文件不调用 `autom4te --trace`，因为 M4 可通过 `syscmd/esyscmd` 执行命令。扫描器优先静态识别 `configure.ac`/`.m4` 的宏调用；若项目已有生成的 `configure` 或 `config.sub`，可以用 Tree-sitter Bash 和文本事实分析已有选择逻辑。未来完整 trace 只能进入无凭据、无网络、资源受限的一次性沙箱。

### 5. RPM 默认保留安全轻量解析，只复用无副作用的语法组件

Packit `specfile` 能理解 section、宏和条件，但其完整 parse/expand 路径可能通过 RPM 执行 shell、Lua 和 include。因此不得在默认静态分析进程中对不可信 spec 调用完整 RPM 求值。

本 change 评估只复用 `specfile` 的纯 `ValueParser` 或同等无副作用组件来解析宏表达式；section、条件栈、架构 selector 和 provenance 仍由扫描器控制。如果纯组件也无法在不初始化 RPM 全局状态的情况下稳定运行，则继续扩展现有轻量 parser，而不是启用完整 `rpm.spec`。

### 6. Evidence Graph 通过 GraphStore 隔离，先验证 NetworkX MultiDiGraph

核心定义自己的 `GraphStore` protocol，不向 frontend、analyzer 或 report 暴露 NetworkX 类型。第一候选使用 `NetworkX.MultiDiGraph`，因为它支持有向平行边、节点/边属性和成熟遍历算法，适合快速验证 relation 与 proof path。

容器 spike 使用小、中、大三类真实或等价项目图测量构建时间、查询时间、峰值 RSS 和序列化成本。NetworkX 达不到后续明确的资源预算时，可在不改变领域契约的情况下切换 rustworkx 或紧凑 adjacency store。稳定 ID、provenance、proof selection、循环边界和截断 diagnostic 始终由 KB Scanner 定义。

### 7. 内部对象与边界模型分开

高数量内部 Entity/Fact/Relation 候选使用 `dataclass(slots=True)` 或等价轻量对象；配置、依赖清单、AnalysisResult 边界和兼容报告投影候选使用 Pydantic v2。JSON Schema/jsonschema 主要用于测试时验证当前 `scan-result.json` 合同，不要求后端切换 DTO。

现有 PyYAML、YAML rule、`generatedSet` 和两份 compiler-derived JSON 继续直接加载。新 validator 只能验证和补充来源，不得重写、删除或转换事实数据。

### 8. 保留现有 detector，自研领域关系分析与分类

现有 YAML matcher 和 generated knowledge sets 继续承担高覆盖 Local Detector。Tree-sitter query 可以补充结构化局部匹配，但不强制把所有规则迁移到新 DSL。

不引入通用规则引擎、Datalog 或商业 SAST 作为核心分类器。Make/Autoconf 选择、宏传播、测试覆盖、alternative implementation、目标可达性和 readiness 具有专门的 x86→RISC-V 证据语义，需要由可测试的 analyzer/classifier 实现。成熟图和解析技术负责基础设施，领域结论仍由扫描器控制。

### 9. 独立测试 Dockerfile 提供候选分析依赖层，kb-scanner-test 由专属 Compose 运行

测试镜像的 stage 关系为：

```text
ubuntu:noble
    └── scanner-deps
            └── kb-scanner-test
```

`scanner-deps` 只为本次技术选型固定 Python、Tree-sitter 和 Clang 等候选依赖；`kb-scanner-test` 在其上增加测试依赖、scanner 源码和 fixture。`backend/Dockerfile` 与根 Compose 不引用该 stage，也不在本 change 内验证或改变生产镜像。候选技术后续是否进入生产由另一项 change 决定。

测试不在镜像构建步骤中隐式执行，而是在 `kb-scanner-test` 启动为一次性测试容器后运行：

- 当前 scanner 单元测试。
- `scan-result.json` 兼容契约测试。
- Tree-sitter/Clang 对比和降级测试。
- 不可信 Make/M4/RPM/CMake 构造不得触发命令执行的安全测试。
- 有界的图存储性能 smoke；完整 benchmark 可由同一 target 的显式参数启用。

`tools/kb-scanner/compose.test.yml` 只定义 `kb-scanner-test` 测试服务，并固定独立的 Compose project identity。该服务不声明对现有 API、worker、PostgreSQL、RabbitMQ、Redis 或对象存储的依赖，不加入现有外部网络，不挂载现有业务卷，也不注入生产业务凭据。默认测试入口执行完毕后退出，任一必需测试失败必须产生非零容器退出码。

正式测试命令通过专属 Compose 文件完成构建和一次性运行，并以测试容器退出码作为结果；停止或清理该 Compose project 只能影响测试容器及其专属临时资源。宿主机只运行 Docker build/Compose 命令，不解析或安装 Python 包。

### 10. 所有新信息继续投影到现有结果

前端来源、解析模式、降级原因和库版本进入 Evidence，关系证明优先投影到既有 Finding `trace`。项目级状态仍进入可选 `summary.readiness`。顶层 `schemaVersion` 保持 `1.0`，`tool`、`rulePack`、`project`、`summary`、`findings`、`diagnostics` 及三个 artifact 不变。

技术 spike 的 benchmark/selection 记录是开发文档或测试输出，不成为新的主扫描结果文件。缺少 Clang、构建元数据或完整关系时输出 unknown/partial，不因 baseline 没有命中而声明 `riscv_ready`。

## Risks / Trade-offs

- [风险] LLVM 与 Python binding 版本不匹配。→ 在同一容器 stage 固定发行版包或成套 binary/binding，并增加 import、parse 和宏事件 smoke test。
- [风险] 测试镜像因 LLVM 变大。→ 记录镜像体积、清理包缓存，并把该成本作为后续生产接入 change 的输入。
- [风险] Tree-sitter 与 Clang 对同一位置产生重复事实。→ 通过稳定 source span、fact kind 和 producer priority 合并，保留 producer 集合。
- [风险] NetworkX 在大项目上内存过高。→ 只通过 GraphStore 使用，并以容器峰值 RSS 作为替换依据。
- [风险] 第三方 build/RPM parser 隐式执行代码。→ 默认只允许纯解析 API，并提供恶意 fixture 验证测试进程不执行项目代码。
- [风险] 测试候选依赖不可复现。→ 独立 Dockerfile 的 runtime/test 层使用锁定文件和固定原生包版本。
- [风险] 测试容器误接入现有 Compose，启动或清理影响开发环境。→ 使用专属 Compose 文件和 project identity，不声明现有服务、外部网络、业务卷或业务凭据，并验证独立 up/run/down。
- [风险] 宿主机测试结果与容器结果混用。→ OpenSpec tasks 和开发文档只接受容器命令作为正式验证证据。
- [风险] 技术栈一次引入过多依赖。→ 本 change 只安装、验证和记录选型；后续 analyzer 按独立 change 分批接入。

## Migration Plan

1. 建立扫描器 runtime/test 依赖清单、版本锁定和许可证清单，不改变现有生成数据。
2. 在 `tools/kb-scanner/Dockerfile.test` 中创建 scanner dependency stage 与 `kb-scanner-test` image target，并新增专属 `tools/kb-scanner/compose.test.yml`，先让现有 41 个测试在独立的一次性容器中通过。
3. 在容器中完成 Tree-sitter、Clang、GraphStore、Make/Autoconf、RPM 安全 spike，记录选择、拒绝原因和资源数据。
4. 根据 spike 结果固定测试容器中的候选技术结论；未通过的候选不得进入后续核心实现。
5. 在测试容器中验证现有 CLI 与 `schemaVersion: "1.0"`、三个 artifact、Finding 和生成事实数据兼容契约。
6. 结束本 change 时保持 `backend/Dockerfile`、根 Compose 和生产镜像不变；生产接入另行提案。

回滚时只删除独立测试 Dockerfile、Compose、候选依赖和 spike 文件；生产 runtime 从未改变。由于本 change 不改变结果 schema、数据库或生成事实数据，回滚不需要数据迁移。

## Open Questions

- LLVM 使用 Ubuntu Noble 发行版包、官方 LLVM apt 包还是成套 PyPI libclang bundle；由容器内版本匹配和镜像体积 spike 决定。
- NetworkX 的具体资源预算和替换阈值，需要从代表性真实项目规模得出。
- `specfile.value_parser` 的纯解析路径是否完全不初始化可执行 RPM 上下文，需要恶意 fixture 和调用链验证。
- 完整性能 benchmark 是作为 `kb-scanner-test` 参数运行，还是另设 `kb-scanner-benchmark` target；默认 target 只保留确定性 smoke。
