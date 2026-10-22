## Why

现有新管线已经能识别 C/C++ 中的 x86 局部事实并建立源码关系，但仍无法静态回答“目标为 RISC-V 时，哪些源码、目录、编译参数、依赖和打包路径会被选择”。这使 AVX 项目 4 个 Makefile 中已审计的 24 个 x86 flag 以及 Make/Autoconf/CMake/Meson/RPM 选择逻辑只能保持 deferred，无法为后续分类与项目评估提供可靠的目标可达性证据。

## What Changes

- 新增构建输入发现、格式识别和 scanner-owned Evidence/Fact 合同，覆盖 Makefile、已有 `configure`/`config.sub`、受限 `configure.ac`/M4、已有 CMake File API、Meson introspection、CTest 元数据、`compile_commands.json` 和 RPM spec；不运行任何生成、配置、构建、RPM 宏或测试命令。
- 基于已锁定的 tree-sitter-make、tree-sitter-bash 和 scanner 自有轻量解析器实现安全有界的静态子集；Make 支持变量赋值、条件、有限 include、字符串/列表拼接、架构 selector 和静态源码集合，动态或越界表达式传播为 `unknown/partial`。
- 将目标 RISC-V 的架构选择来源、配置条件、源码/目录/参数/依赖和目标产物建模为稳定 Entity、Relation 与 ProofPath；明确区分 selected、inactive、not-selected 和 unknown，并保留完整 provenance。
- 实现既定 `uname -m` 语义：假设探测值正确；存在 RISC-V 分支时分析该分支，只有通用 fallback 时 x86 分支 inactive，二者都不存在时产生“缺少 RISC-V 选择路径”的可追溯 Observation；不建模交叉编译误选 x86 分支。
- 除可被纯静态替换为目标架构值的精确 `uname -m` probe 外，识别 `$(shell)`、`!=`、Make `eval`、M4 `syscmd/esyscmd`、CMake `execute_process`、RPM shell/Lua/include 等可执行或不支持构造，只记录 Evidence 与稳定 Diagnostic，绝不执行。
- 将真实构建选择 frontend/normalizer/analyzer/detector 接入 staged qualification；Classifier、Assessor 和兼容 Projector 仍保持 recording/no-op，默认 CLI 继续使用 Legacy compatibility profile。
- 保持现有 `scan-result.json` 的 `schemaVersion: "1.0"`、顶层字段和三个 artifact，不创建第二套主结果；内部选择 proof 未来只投影到现有 Finding `trace` 等兼容位置。
- 原样保留 legacy YAML、`generatedSet`、`clang-x86-entries.json` 和 `gcc-x86-entries.json`，不重生成、不转换，也不把操作系统、内核、系统调用、驱动或板级迁移纳入权威结论。
- 为每个新增或实质修改的构建发现、解析、受限求值、归一化、关系分析和 detector 业务模块同步建立隔离单元测试映射，在唯一 `kb-scanner-test` 容器中使用 fake/mock 覆盖文件系统、parser、机器产物和危险执行边界，并执行至少 90% line / 80% branch 覆盖门禁。

## Capabilities

### New Capabilities

- `kb-scanner-build-selection-analysis`: 定义多格式构建/打包输入的无副作用静态恢复、有界求值、RISC-V 选择语义、选择关系与 proof、未知传播、安全门禁和验收基线。

### Modified Capabilities

- `kb-scanner-core-pipeline`: 使正式 qualification 能组合 C/C++ 与构建输入，归一化构建事实并运行真实 Build Selection Analyzer/Detector，同时保持默认 CLI 和输出兼容。
- `kb-scanner-evidence-graph`: 扩展图实体、关系和 ProofPath，使其承载从架构 selector 到条件、源码/参数/依赖和目标产物的构建选择链及完整性状态。
- `kb-scanner-knowledge-and-local-detection`: 使 detector 消费已验证的构建选择关系，产生可追溯的 selected/inactive/gap/unknown Observation，而不提前承担最终 blocking、severity 或 readiness 分类。

## Impact

- 预计新增 `kb_scanner/frontends/build/`、构建事实归一化和 build-selection analyzer/detector 模块，并扩展 core vocabulary、组合 workspace/frontend/normalizer、Graph Analyzer 与 qualification profile；Legacy 模块保持只读。
- 复用测试容器中已锁定的 tree-sitter-make 1.1.1、tree-sitter-bash 0.25.1、NetworkX 3.6.1 和现有边界校验依赖；不在宿主机安装依赖，不修改生产镜像或根 Compose，不引入已拒绝的 `specfile` runtime。
- 增加多格式安全 fixture、Make 有界求值 fixture、RISC-V selector/fallback/gap fixture、AVX 24 flag 人工审计回归、机器产物 schema fixture、恶意无副作用 fixture、模块测试 inventory 与覆盖门禁。
- 不修改当前 CLI 参数、退出码、报告 schema、artifact 名称、后端消费方式或编译器事实数据；正式 staged 结果仍不替换默认 Legacy 输出。
