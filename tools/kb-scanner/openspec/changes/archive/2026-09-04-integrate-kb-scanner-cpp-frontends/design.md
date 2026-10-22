## Context

`establish-kb-scanner-core-pipeline` 已提供不可变 `Entity`/`Evidence`、`ScanContext`、`FrontendSnapshot`、`StageResult`、`Frontend` protocol、`PipelineProfile` 和 `StagedPipelineRunner`。当前 CLI 为保持 82 项回归语义，仍通过 `LegacyPipelineRunner` 调用 `compile_commands.py`、`cpp_frontend.py`、`rules.py` 和 `report.py`；正式 staged pipeline 尚无真实 C/C++ Frontend。

前一个技术选型 change 已在独立 `kb-scanner-test` 容器验证 Tree-sitter 0.26.0、C grammar 0.24.2、C++ grammar 0.23.4，以及版本匹配的 Clang/libclang/Python binding 18.1.3。现有 `kb_scanner/technology/cpp_frontends.py` 证明了容错 CST、detailed preprocessing record 和参数过滤可行，但它使用自己的 spike DTO，不是正式实现。

本阶段必须同时满足两个迁移约束：新 frontend 要直接产生 core 合同并能注入 staged runner；旧 parser、DTO、规则和报告代码冻结为只读基线，不能为了迁就新实现继续修改。由于正式 Knowledge、Normalizer、Detector、Classifier、Assessor 和 Report Projector 尚未实现，本阶段不能把不完整 staged profile 切为默认 CLI，也不能把新 Evidence 伪装成 legacy `ProjectFacts`。

## Goals / Non-Goals

**Goals:**

- 独立重写正式 C/C++ workspace collector、Tree-sitter baseline frontend 和可选 Clang enrichment adapter。
- 对 C/C++ 源文件、头文件、测试源码和不完整代码产生项目相对、带 source span、producer、parse mode 和 confidence 的 core Evidence。
- 提取后续局部检测与关系分析需要的预处理、include、宏、调用、类型、模板、`if constexpr`、inline asm 和注释基础事实，但不在 frontend 做 x86 知识匹配或 RISC-V 可达性分类。
- 在 compilation context 可用时安全运行 libclang 纯解析增强，保留宏定义、宏展开、include 和语义 provenance。
- 对读取错误、Tree-sitter ERROR/MISSING、Clang 参数拒绝和单 TU 失败使用结构化 Diagnostic 与 partial 状态表达，并保留已取得的 baseline Evidence。
- 提供确定性排序、稳定身份、引用完整性、安全参数和 staged 注入合同测试。
- 保持当前 CLI、结果 schema、Finding 语义、知识资产和容器边界不变。

**Non-Goals:**

- 不修改或扩展 legacy `compile_commands.py`、`cpp_frontend.py`、`models.py`、`rules.py` 和 `report.py`。
- 不把 `technology/` spike 直接改名或包装成正式实现；正式代码重新依赖 core 类型。
- 不在本阶段实现 YAML/`generatedSet` Knowledge Provider、x86 Detector、跨文件宏关系、Evidence Graph、架构分支可达性、Finding 分类或项目 readiness。
- 不让默认 CLI 运行双份 parser，也不生成 shadow/debug 主报告。
- 不执行编译、链接、构建、配置、编译器 plugin、response file、项目测试或真实 RISC-V 验证。
- 不处理操作系统、内核、系统调用、驱动或板级迁移。
- 不引入 LibTooling helper；只有后续 fixture 证明 Python libclang 丢失必需 provenance 时才能另立 change。

## Decisions

### 1. 正式实现放入新包，legacy 与 technology 目录均保持只读

新增结构采用：

```text
kb_scanner/frontends/cpp/
  workspace.py              # C/C++ 文件发现与语言候选
  compilation_database.py   # 纯读取并产生 core CompilationUnitContext
  tree_sitter_adapter.py    # 必需 baseline
  clang_adapter.py          # 可选 enrichment
  arguments.py              # Clang 纯解析参数策略
  frontend.py               # Frontend protocol 组合实现
  vocabulary.py             # Evidence kind/value 合同
```

正式包不得导入 `kb_scanner.technology`、legacy `models`、legacy `cpp_frontend` 或 legacy `compile_commands`。`technology/` 继续保存可复现选型证据；旧实现继续由 `adapters/legacy.py` 私有调用。测试将 legacy 五个文件与 `archive/2026-09-04-pre-rewrite` 对应文件做字节比较，阻止为了新 frontend 修改旧代码。

备选方案是在 `cpp_frontend.py` 中逐段替换正则。该方案会把新 core Evidence 与 legacy `ProjectFacts` 再次耦合，也无法清楚比较新旧行为，因此不采用。

### 2. 提供只发现 C/C++ 输入的静态 Workspace Collector

`CppWorkspaceCollector` 实现现有 `WorkspaceCollector` protocol，只枚举本阶段支持的 C/C++ 源码和头文件，遵守当前 `language`、`exclude` 和 `exclude-path` 过滤语义，不读取构建脚本、RPM 或 OS 专属输入。第一版支持 `.c`、`.cc`、`.cpp`、`.cxx`、`.h`、`.hh`、`.hpp`、`.hxx` 和 `.inc`；测试目录中的同类文件与普通源码同等进入 frontend，测试角色留给后续分类阶段。

目录输入以规范化输入目录为 workspace root；单文件输入以其父目录为 workspace root 并只列出该文件。collector 不跟随逃逸 workspace 的 symlink，所有 `WorkspaceSnapshot.files` 使用 POSIX 风格项目相对路径并确定性排序。无法读取或不受支持的文件产生 Diagnostic，不得让绝对机器路径进入稳定身份。

备选方案是继续调用 legacy `discover_source_files()`。它同时承担构建/RPM 范围且返回 legacy 路径模型，违反冻结和 core 边界，因此不复用。

### 3. Frontend 使用显式组合，不使用 registry 或隐藏全局状态

正式 `CppFrontend` 实现 core `Frontend` protocol，通过构造函数显式接收 Tree-sitter adapter、可选 Clang adapter 和受限策略。对 workspace 中每个文件始终先运行 Tree-sitter baseline；随后只对具有有效 `CompilationUnitContext` 的 translation unit 运行 Clang。所有组件接收同一个只读 `ScanContext` 和 `WorkspaceSnapshot`，不重新解析 CLI 参数。

`CppFrontend` 返回 `StageResult[FrontendSnapshot]`。`FrontendSnapshot` 只包含 core `Entity` 和 `Evidence`；第三方 Node、Tree、Cursor、TranslationUnit 或 diagnostic 对象不得越过 adapter。前端不会调用 Knowledge、Detector 或 Reporter。

### 4. 文件 Entity 是本阶段 Evidence 的稳定引用锚点

每个输入文件产生一个 `kind=source_file` Entity，ID 使用 scanner identity 版本、项目相对路径和语言候选生成。所有前端 Evidence 至少引用所属文件 Entity；定义类语法可以另外产生宏、声明或类型 Entity，但不得为了尚未实现的跨文件图提前推断 Relation。

第一版正式 Evidence vocabulary 包括：

- `preprocessor_condition`、`preprocessor_branch`
- `include`
- `macro_definition`、`macro_expansion`
- `call_expression`、`type_reference`
- `template_declaration`、`constexpr_condition`
- `inline_asm`
- `comment`（仅当 `include_comment_hints` 为 true）
- `parse_error` 不作为普通 Evidence，而作为 Diagnostic

每条 Evidence 使用项目相对 `SourceSpan`、producer/version、parse mode、confidence、稳定 kind/value 和必要的 JSON-safe metadata。value/metadata 只保存后续分析需要的标识符、include path、条件文本或受限源码片段，不保存 parser 对象。

### 5. Tree-sitter 是所有文件的必需容错 baseline

Tree-sitter adapter 直接从 UTF-8 bytes 解析，使用显式 node visitor/query 提取 vocabulary，不执行预处理器或求值条件。`.c` 使用 C grammar，明确 C++ 后缀使用 C++ grammar；`.h`/`.inc` 等歧义头文件在缺少直接语言上下文时分别尝试 C 与 C++ grammar，以错误节点更少的结果为主，并保留所选 grammar/version。两者同样可用时采用固定优先级，保证重复扫描一致。

ERROR/MISSING 节点使对应文件结果为 partial，并产生带位置的 Diagnostic；ERROR 节点之外已经恢复的 Evidence 继续保留。某个文件读取或解析失败只影响该文件，不删除其他文件结果。只有 baseline adapter 整体不可初始化或无法形成所需 core 值时，Frontend 阶段才返回 failed/unavailable。

Tree-sitter 只恢复语法事实，不判断 `__x86_64__` 分支是否对 RISC-V active，不把 `uname`、宏名或注释文本直接升级为 Finding。

### 6. compilation database 在新包中纯读取，不复用 legacy DTO

新增 reader 只读取 JSON，保留一个源码存在多个 command entry 的情况，并直接构造 core `CompilationUnitContext`。它解析 compiler、工作目录、language、include paths、defines、标准和原始 token，但不执行命令。无 file、路径逃逸、格式错误和不可解析 command 产生结构化 Diagnostic；有效 entry 继续使用。

context identity 使用项目相对 source path、entry index、规范化 defines、language standard 和清洗后的参数摘要，不使用绝对 directory 或机器路径。该 reader 为未来 staged `ScanContextFactory` 提供正式输入，但本阶段不替换默认 legacy context factory。

### 7. Clang 只作为按 translation unit 的可选纯解析增强

Clang adapter 使用 `PARSE_DETAILED_PROCESSING_RECORD`，至少提取项目源码位置中的 macro definition、macro expansion 和 inclusion directive，并在稳定可得时补充 declaration/reference 类语义事实。它按 compilation entry 独立运行；同一源码的不同 entry 使用不同 context identity，以保留不同宏和参数条件下的 provenance。

只收集 location 位于 workspace 内的 Evidence；系统头或 workspace 外部依赖不展开为项目实体，但项目源文件中的 include directive 仍保留 include path。每个 translation unit 使用完即释放，第一版串行运行以保持诊断和输出顺序确定。

缺少 context 时不调用 Clang，也不产生错误；该文件只有 Tree-sitter Evidence，需要完整 compilation context 的后续结论保持 unknown。单 TU Clang 错误产生 partial Diagnostic，不能删除 Tree-sitter Evidence或终止其他 TU。

### 8. Clang 参数采用严格 allowlist，而不是补丁式 denylist

参数规范化先移除 compiler executable、输入源、`-c`、输出/依赖产物选项，再只接受纯解析上下文所需类别：语言/标准、`-D`/`-U`、include 搜索路径、target/sysroot、`-nostdinc*` 及明确审计过的目标特性参数。相对路径以 command directory 规范化，但稳定 identity 中不得包含机器绝对路径。

以下类别无条件拒绝并产生带 entry identity 的 Diagnostic：

- `@response-file`
- `-Xclang` 及其透传参数
- `-fplugin*`、`-load`、`-plugin`、`-add-plugin`
- PCH/module/module-map/serialized AST 加载
- `-o`、dependency/diagnostic/trace/save-temps 等写文件参数
- driver offload、linker、assembler 或未在 allowlist 的参数

Clang adapter 不启动 clang executable，只调用容器中版本匹配的 libclang parse API。参数被拒绝时，安全子集仍可用于 enrichment；若剩余参数不足，则降级为 baseline。

### 9. 不在 Frontend 内合并不同 producer 的 Evidence 身份

Tree-sitter 与 Clang 对同一 span/kind/value 的结果保留为两个 Evidence，因为 core 合同要求 producer-specific 稳定 ID 和 provenance。Frontend 只去除同一 producer、同一 compilation context 内的完全重复项；跨 producer 关联与来源集合合并由后续 Normalizer 完成。

输出排序固定为文件相对路径、span、kind、producer、context identity 和 Evidence ID；Entity 按 kind、name、ID 排序，Diagnostic 按 workspace 文件顺序和 adapter 产生顺序聚合并去重。相同输入、scanner/grammar/Clang 版本和 context 必须得到相同 ID 与顺序。

### 10. staged 集成是可注入能力，本阶段不切换默认 CLI

提供一个显式 frontend qualification profile/test harness：使用真实 `CppWorkspaceCollector` 和 `CppFrontend`，其余阶段使用 recording/no-op test components，验证 `StagedPipelineRunner` 的 workspace → frontend → downstream 值传递。正式前端包不构造第二个报告，也不把 core Evidence 转回 legacy DTO。

当前 `create_legacy_application()` 与 CLI 默认选择保持不变。阶段 3/4 为 Knowledge、Normalizer、Detector 和关系阶段提供真实组件，并具备兼容 Report Projector 后，再由后续 change 决定默认切换。这样既能让新 frontend 成为正式可组合实现，又不会双跑 parser 或输出缺少检测结论的“成功报告”。

### 11. 现有知识和报告只做回归，不由 Frontend 消费

本阶段不加载或解释 YAML、`generatedSet`、`clang-x86-entries.json` 和 `gcc-x86-entries.json`；这些资产保持原样并继续由 legacy profile 产生当前 Finding。新 frontend 只提供可供阶段 3 Knowledge/Detector 消费的稳定 Evidence vocabulary。

默认 CLI 回归继续验证 `schemaVersion: "1.0"`、七个顶层键、Finding 语义以及 `scan-result.json`、`scan-report.html`、`scan.log`。前端内部 Entity/Evidence 不直接序列化为新主结果文件；未来 provenance 只通过兼容 projector 进入 Finding `trace`。

### 12. 所有正式验证继续只运行独立测试容器

现有 runtime lock 已包含所需 Tree-sitter 版本，Dockerfile.test 已固定 Clang 18.1.3；本阶段不新增依赖版本。所有 parser、参数安全、降级、稳定性和全量回归测试只通过 `compose.test.yml` 构建与运行。不得在宿主机安装或执行 scanner Python/Clang 依赖，也不得修改或尝试构建生产镜像。

## Risks / Trade-offs

- [风险] 歧义头文件使用错误 grammar，遗漏 GNU C 或 C++ 特有结构。→ 双 grammar 试解析并以固定错误评分选择，使用 C/C++ 头文件 fixture 固化行为；语言仍无法确认时在 metadata 标记 inferred。
- [风险] Tree-sitter 与 Clang span 细节不同，后续无法关联。→ 本阶段保留 producer-specific Evidence，不做跨 producer 强合并；fixture 固定行列和源码片段，Normalizer 后续用明确策略关联。
- [风险] libclang 接受的某些参数会读取 PCH/module 或写文件。→ 使用严格 allowlist，专门拒绝透传、plugin、response、PCH/module 和输出类别，并用 marker fixture 验证无副作用。
- [风险] Clang 缺失系统头导致大量 error。→ baseline 始终先运行；Clang diagnostic 聚合限量并标记 TU partial，不影响其他文件。
- [风险] Clang 遍历系统头导致证据量和内存膨胀。→ 只保留 workspace 内 location，串行处理并及时释放 translation unit。
- [风险] 新 frontend 已实现但默认 CLI 尚未使用，短期存在两套解析代码。→ 明确 staged qualification 入口和后续替换顺序；legacy 冻结且不接收新能力，避免双轨无限扩张。
- [风险] legacy 冻结使发现的旧 bug 无法直接修复。→ 先把该行为写成 baseline；修复只进入新实现，并由后续 cut-over 明确评估兼容差异。
- [风险] 只实现 frontend 无法产生新 Finding。→ 本阶段验收对象是 core Evidence 与 staged 注入，不声称提升最终检测；阶段 3 才接入 Knowledge/Detector。

## Migration Plan

1. 固化 legacy 五个文件、82 项当前测试、前端 spike fixture、事实数据哈希和报告结构基线。
2. 在新正式包实现 workspace collector、Evidence vocabulary 与 Tree-sitter baseline，先完成无 compilation database 的 C/C++、歧义头文件和错误恢复测试。
3. 实现新的 compilation database reader、Clang 参数 allowlist 与 enrichment adapter，验证多 entry、宏 provenance、include、失败降级和无副作用。
4. 组合为 core `Frontend` protocol 实现，通过真实 workspace/frontend + recording downstream 的 staged runner 测试，不接入默认 CLI。
5. 在独立 `kb-scanner-test` 容器运行全部旧回归与新增合同测试，确认 legacy 文件、知识数据和三个 artifact 未变。
6. 更新开发计划阶段 2 状态，并记录阶段 3 消费的 Evidence vocabulary 与尚为 unknown 的能力。

回滚只删除新 `frontends/cpp` 正式包、对应测试与文档；默认 CLI 始终使用未修改的 legacy profile，因此不需要恢复报告、数据或部署配置。

## Open Questions

无。Tree-sitter/Clang 版本、安全边界、legacy 冻结、默认 profile 和本阶段 Evidence 范围均已由前序选型、核心管线合同及本 proposal 确定。
