## Why

KB Scanner 已完成静态分析架构分层，但 C/C++ 前端、证据图、构建文件部分求值和依赖封装仍缺少经过验证的技术选型。现在需要先证明哪些成熟技术可以直接复用，并把安装和测试固定在容器中，避免重写已有解析能力或污染开发者宿主机环境。

## What Changes

- 建立 reuse-first 技术选型：优先验证 Tree-sitter C/C++、LLVM/libclang/LibTooling、NetworkX、Pydantic/JSON Schema、pathspec 和现有 PyYAML/生成知识集，只有无法满足证据保真、安全性或资源约束时才自研对应基础能力。
- 定义双层 C/C++ 前端方向：Tree-sitter 提供无完整构建上下文时仍可运行的容错静态分析，Clang 在 `compile_commands.json` 充分时提供宏、include 和语义增强；任一增强不可用时必须可观测降级而不是使整个扫描失败。
- 为 Makefile、Autoconf、RPM 和其他构建元数据定义安全评估边界：默认扫描不得执行不可信项目中的 shell、M4、RPM、CMake 或构建副作用，只对受支持语法执行有界静态求值。
- 为 Evidence Graph 选择可替换的 `GraphStore` 边界，先以成熟内存图技术完成基准验证，再依据真实项目的时间和内存数据决定是否需要紧凑存储。
- 将 KB Scanner 的 Python、Tree-sitter、LLVM/Clang 和分析库依赖固定在容器镜像中；禁止实现和测试流程要求在宿主机安装这些依赖。
- 在独立的 `tools/kb-scanner/Dockerfile.test` 中增加 `kb-scanner-test` image target，并通过 `tools/kb-scanner/compose.test.yml` 提供一次性测试容器；该容器安装锁定的候选扫描器依赖，在启动后运行现有回归、前端对比、构建解析、安全边界和性能测试，退出码表示测试结果。
- `kb-scanner-test` 不加入或合并到现有根 Compose，不依赖现有 API、worker、数据库、消息队列、缓存或对象存储服务，也不复用它们的网络、卷和业务凭据；测试容器的构建、启动、停止与清理具有独立生命周期。
- 保留 `clang-x86-entries.json`、`gcc-x86-entries.json`、现有 YAML 规则和 `generatedSet` 行为；本 change 不重新生成或转换这些数据。
- 保持 `scan-result.json` 的 `schemaVersion: "1.0"`、现有顶层字段和 `scan-report.html`/`scan.log` artifact 契约，不引入新的主结果结构。

## Capabilities

### New Capabilities

- `kb-scanner-containerized-toolchain`: 定义扫描器候选依赖只在容器中安装，以及 `kb-scanner-test` 独立镜像 target 和专属 Compose 测试容器的可重复构建与测试要求。

### Modified Capabilities

- `kb-scanner-analysis-architecture`: 增加 reuse-first 双层前端、增强能力可观测降级，以及默认静态扫描不得执行不可信构建/打包逻辑的要求。

## Impact

- 影响 `tools/kb-scanner` 的依赖清单、前端适配边界、图存储接口、技术 spike 和容器测试入口。
- 新增独立的 `tools/kb-scanner/Dockerfile.test` 和 `tools/kb-scanner/compose.test.yml`；不修改 `backend/Dockerfile` 或根 `docker-compose.yml`，也不改变现有服务的镜像、启动、停止、网络、卷、环境变量、KB Scan API、任务模型或 CLI 调用契约。候选技术进入生产环境需要后续独立 change。
- 后续实现可能在容器中引入 Tree-sitter C/C++ grammar、LLVM/libclang、NetworkX、Pydantic、pathspec 和开发期 JSON Schema 校验依赖，所有版本必须锁定并可复现。
- 不要求开发者宿主机安装 Python 分析依赖、Clang、GNU Make、Autoconf、RPM 或 CMake；宿主机只需要容器构建与运行能力。
- 不改变操作系统、内核、系统调用、驱动或板级迁移的排除边界，也不把真实 RISC-V 编译或测试纳入 KB Scanner。
