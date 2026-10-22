## 1. 固化前端迁移基线与只读边界

- [x] 1.1 记录当前 82 项容器测试、前端 technology spike、支持输入、CLI 输出和两份生成事实数据哈希，明确本 change 的 baseline 是 core Evidence 而不是新增 Finding。
- [x] 1.2 为 `compile_commands.py`、`cpp_frontend.py`、`models.py`、`rules.py` 和 `report.py` 增加相对 pre-rewrite archive 的字节冻结测试，任何差异均使容器测试失败。
- [x] 1.3 增加正式 frontend import-boundary 测试，禁止新包导入 `kb_scanner.technology`、legacy models/frontend/compile loader/rules/report 或暴露第三方 parser 类型。
- [x] 1.4 固化 C、C++、歧义头文件、不完整源码、宏/include、inline asm、模板/constexpr、comment 和 compilation context 的 Evidence 语义 fixture。

## 2. 建立正式 C/C++ Workspace 与 Evidence vocabulary

- [x] 2.1 创建独立 `kb_scanner/frontends/cpp` 正式包和清晰导出边界，不修改或改名 technology spike。
- [x] 2.2 定义本阶段 `source_file` Entity 及 preprocessor/include/macro/call/type/template/constexpr/inline-asm/comment Evidence vocabulary、值字段、metadata 和稳定排序键。
- [x] 2.3 实现 `CppWorkspaceCollector`，支持目录和单文件输入、C/C++ source/header 后缀、language、现有 exclude/exclude-path 语义及 POSIX 项目相对路径。
- [x] 2.4 实现 workspace root 与 symlink/path 逃逸校验，对不支持或不可读输入产生结构化 Diagnostic，稳定身份材料不得包含机器绝对路径。
- [x] 2.5 增加 workspace 单元测试，覆盖确定性顺序、测试目录源码、目录过滤、单文件 root、非 C/C++ 文件和外部 symlink。

## 3. 重写纯读取 Compilation Database Reader

- [x] 3.1 在新正式包实现 JSON compilation database reader，直接返回 core `CompilationUnitContext`/`StageResult`，不得使用 legacy `CompileCommandContext` 或执行 command。
- [x] 3.2 支持 `arguments` 与 `command`、相对 directory/file、compiler、language、include path、defines、standard 和原始 token 的确定性解析。
- [x] 3.3 保留同一源码的多个有效 entry，并从项目相对 source、entry index、defines、language standard 和规范化参数生成稳定 context identity。
- [x] 3.4 将缺少 file、无效 JSON/command、输入范围外路径和部分有效 entry 映射为结构化 Diagnostic 与 complete/partial/unavailable 状态。
- [x] 3.5 增加 compilation database 合同测试，覆盖多 entry、参数两种表示、部分降级、不存在/整体无效和绝对路径不进入 context identity。

## 4. 实现 Tree-sitter Baseline Frontend

- [x] 4.1 实现版本化 Tree-sitter C/C++ adapter 初始化和 bytes/source-span 转换，只返回 scanner core 类型。
- [x] 4.2 提取条件预处理与分支、include、宏定义、调用、类型引用、模板声明、`if constexpr`、inline asm 和按选项启用的 comment Evidence。
- [x] 4.3 实现明确 source suffix/compilation context 的语言选择，以及 `.h`/`.inc` 双 grammar 固定错误评分、tie-break 和 inferred metadata。
- [x] 4.4 将 ERROR/MISSING、读取失败和单文件解析失败映射为带位置的 partial Diagnostic，同时保留可恢复 Evidence 和其他文件结果。
- [x] 4.5 对同一 producer/context 的完全重复 Evidence 去重，并按项目相对文件、span、kind、producer/context 和 ID 确定性排序。
- [x] 4.6 增加 Tree-sitter 容器测试，覆盖 C/C++ 完整与不完整源码、歧义头文件、缺少 compile context、comment 开关、位置、稳定 ID 和重复运行一致性。

## 5. 实现 Clang 纯解析参数策略

- [x] 5.1 实现独立 Clang argument normalization 结果对象，移除 compiler/source/compile-only token，并只允许语言、宏、include、target/sysroot、标准和已审计目标特性参数。
- [x] 5.2 完整拒绝 `-Xclang` 透传、plugin/load、response file、PCH/module/module-map/serialized AST、输出/dependency/diagnostic/trace/save-temps、driver offload/linker/assembler 和未知参数组。
- [x] 5.3 规范化 paired/joined 参数和 command directory 下的相对路径，为每个拒绝组产生包含 entry identity 但不泄漏机器路径的结构化 Diagnostic。
- [x] 5.4 增加恶意参数 fixture 和 marker 测试，确认混合参数只保留安全子集，plugin/response/PCH/module 不加载且输出、依赖或 trace 文件不产生。

## 6. 实现可选 Clang Enrichment Adapter

- [x] 6.1 实现 Clang 18 `PARSE_DETAILED_PROCESSING_RECORD` adapter，按 compilation entry 提取 macro definition、macro expansion、inclusion directive 和稳定可得的语义 Evidence。
- [x] 6.2 将 Clang location 规范化为项目相对 SourceSpan，只保留 workspace 内源码 Evidence，并为每条 Evidence 记录 Clang 版本和 context identity。
- [x] 6.3 对无 context 文件不调用 Clang；对单 TU 初始化、参数或 parse diagnostic 失败返回 partial Diagnostic 并释放资源，不影响其他 TU 或 Tree-sitter baseline。
- [x] 6.4 保留同一源码不同 compilation entry 的独立 provenance，并只去除同一 producer/context 的完全重复 Evidence。
- [x] 6.5 增加 Clang 容器测试，覆盖宏定义/展开、include、多个 context、缺失头/无效 TU、workspace 外位置过滤、稳定 ID 和 baseline 不丢失。

## 7. 组合正式 Frontend 并接入 Staged Pipeline

- [x] 7.1 实现显式依赖注入的 `CppFrontend`，对每个 workspace 文件先运行 Tree-sitter，再对匹配的 compilation entry 运行可选 Clang，返回 `StageResult[FrontendSnapshot]`。
- [x] 7.2 实现 Entity/Evidence 引用完整性、跨 adapter Diagnostic 稳定聚合和整体 complete/partial/failed 状态传播，不在 Frontend 内合并不同 producer。
- [x] 7.3 建立仅用于 qualification 的 staged profile/test harness，使用真实 Workspace Collector 与 CppFrontend、recording/no-op downstream，且 projector 不写正式 artifact。
- [x] 7.4 验证正式 Frontend 不加载知识数据、不产生 Finding、不判断 RISC-V 可达性/readiness、不重新解析 CLI 参数，也不把 core Evidence 转换为 legacy DTO。
- [x] 7.5 增加 staged 集成测试，确认统一 ScanContext、workspace → frontend → downstream 值传递、Clang partial 降级和默认 legacy application/profile 未被替换。

## 8. 验证旧行为、数据与无副作用边界

- [x] 8.1 仅在独立 `kb-scanner-test` 容器中运行原有 82 项测试和本 change 新增测试，任一失败必须产生非零容器退出码。
- [x] 8.2 回归默认 CLI 的成功、规则失败和 compile context 降级路径，确认 `schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义与三个 artifact 均未改变且没有第二主结果文件。
- [x] 8.3 验证 Clang/GCC 事实 JSON 的 SHA-256、六类计数、source 和 YAML `generatedSet` 引用保持不变，新 Frontend 不读取或转换这些资产。
- [x] 8.4 使用 marker 与静态调用边界测试确认新 collector/reader/frontend 未执行 compiler executable、构建、配置、plugin、response file、项目测试或真实 RISC-V 编译。
- [x] 8.5 验证本 change 没有扩展到 OS/内核/驱动迁移，没有实现 uname 交叉编译误选模型、跨文件图、Detector、Classifier 或 readiness。

## 9. 文档、容器与 OpenSpec 收尾

- [x] 9.1 更新开发文档，说明正式 C/C++ frontend 的模块、Evidence vocabulary、grammar 选择、Clang allowlist/降级和 legacy 只读规则。
- [x] 9.2 更新 `docs/kb-scanner-rewrite-development-plan.md` 的阶段 2 状态、实际覆盖、已知 unknown 和阶段 3 Knowledge/Detector 输入边界。
- [x] 9.3 只通过 `tools/kb-scanner/compose.test.yml` 构建、运行和清理测试容器，确认未安装宿主机依赖，未修改或构建 `backend/Dockerfile`、根 Compose 和生产镜像。
- [x] 9.4 运行 `openspec validate integrate-kb-scanner-cpp-frontends --strict` 并修复全部规格格式或一致性问题。
