## 1. 固化基线与容器约束

- [x] 1.1 记录当前 backend/worker 镜像结构、KB Scanner 独立 CLI 调用方式、41 项单元测试和 24 个规则文件基线。
- [x] 1.2 记录 `clang-x86-entries.json` 与 `gcc-x86-entries.json` 的内容哈希、六类条目计数和 `generatedSet` 回归基线，确认本 change 不重生成或转换它们。
- [x] 1.3 在扫描器开发说明中明确所有依赖安装、技术 spike 和正式测试只在容器中执行，宿主机不运行 pip/npm/系统包安装。

## 2. 建立可复现的扫描器依赖层

- [x] 2.1 为 KB Scanner 建立 runtime/test 依赖清单、锁定版本和许可证清单，区分纯 Python、Tree-sitter grammar、LLVM/Clang 原生组件和测试专用依赖。
- [x] 2.2 在独立 `tools/kb-scanner/Dockerfile.test` 中增加 scanner dependency stage，并让 `kb-scanner-test` 从锁定 runtime 文件和固定原生包版本构建。
- [x] 2.3 在容器中验证 Python、Tree-sitter C/C++ grammar、LLVM/libclang 和 Python binding 的版本匹配、import、基础解析与版本输出。
- [x] 2.4 评估 Ubuntu Noble 发行版 LLVM、官方 LLVM 包和成套 libclang bundle，记录镜像体积、版本匹配和可维护性后固定一种来源。

## 3. 增加独立的 kb-scanner-test 容器

- [x] 3.1 在独立 `tools/kb-scanner/Dockerfile.test` 中创建名为 `kb-scanner-test` 的 image target，继承其 scanner dependency stage 并复制 scanner tests/fixtures。
- [x] 3.2 新增专属 `tools/kb-scanner/compose.test.yml`，只定义一次性的 `kb-scanner-test` 服务，并设置独立 Compose project identity；不得把该服务加入根 Compose。
- [x] 3.3 让测试容器启动后运行当前 `python -m unittest discover -s tests -v`，任一测试失败时返回非零容器退出码。
- [x] 3.4 验证测试 Compose 不依赖现有 API/worker/基础设施服务，不加入现有网络、不挂载业务卷、不注入数据库、消息队列、缓存或对象存储凭据。
- [x] 3.5 验证测试容器可独立 build/up 或 run/down，停止和清理测试 project 时现有 Compose 服务状态不发生变化。
- [x] 3.6 在 `kb-scanner-test` 中增加 `scan-result.json` schemaVersion 1.0、顶层字段、Finding trace 和三个 artifact 的兼容契约测试。
- [x] 3.7 从不含扫描器 Python/Clang 依赖的宿主机前提验证 target 可构建和运行，正式验证记录只引用容器内版本和输出。

## 4. 验证分层 C/C++ 前端

- [x] 4.1 在容器中用 Tree-sitter C/C++ 运行条件编译、宏定义、多行 inline asm、模板/if constexpr、不完整源码和缺失 include fixture，记录节点覆盖、ERROR/MISSING 和耗时。
- [x] 4.2 在容器中用 libclang detailed preprocessing record 运行具有完整与不完整 compile context 的同一 fixture，记录宏定义、宏实例化、include、诊断和降级行为。
- [x] 4.3 比较 Tree-sitter 与 libclang Evidence，定义按 source span、fact kind 和 producer 合并去重的规则，并确认基础前端不被增强前端替代。
- [x] 4.4 增加 compilation arguments 安全 fixture，验证 plugin、response file 和其他未允许参数被拒绝或移除且不会执行项目代码。
- [x] 4.5 根据宏 provenance 结果决定 Python libclang 是否足够；不足时只设计并验证最小 LibTooling PPCallbacks helper 接口，不实现跨文件宏分析器。

## 5. 验证 Evidence Graph 与边界模型

- [x] 5.1 定义最小 GraphStore spike 契约，覆盖有向平行 Relation、稳定 Entity ID、属性、邻接遍历和 bounded proof path，禁止 NetworkX 类型泄漏到领域接口。
- [x] 5.2 在容器中实现 NetworkX MultiDiGraph spike，并用小、中、大三档等价项目图测量构建时间、查询时间、峰值 RSS 和序列化成本。
- [x] 5.3 根据测量结果记录 NetworkX 接受条件或拒绝证据；若拒绝，仅比较 rustworkx/紧凑 adjacency store，不在本 change 内实现完整 Evidence Graph。
- [x] 5.4 验证 `dataclass(slots=True)` 内部对象、Pydantic v2 边界模型和测试期 JSON Schema 校验的时间、内存与 schema 兼容性。

## 6. 验证构建与 RPM 安全解析边界

- [x] 6.1 在容器中评估 Tree-sitter Make grammar 对赋值、条件、include、变量引用、源码列表和 unsupported 构造的位置保真度，并记录支持矩阵。
- [x] 6.2 在容器中评估 Tree-sitter Bash 对已有 `configure`/`config.sub` 架构选择片段的覆盖，并记录 `configure.ac`/M4 仍需自研的纯静态调用语义。
- [x] 6.3 增加含 `$(shell)`、`!=`、M4 `syscmd/esyscmd`、CMake `execute_process` 的恶意 fixture，验证 `kb-scanner-test` 不执行命令且稳定输出 unsupported/unknown 证据。
- [x] 6.4 验证 `specfile.value_parser` 或候选纯 RPM 语法组件是否会初始化 `rpm.spec`、宏展开或其他可执行路径；不满足无副作用要求时记录拒绝并保留现有轻量 parser。
- [x] 6.5 增加 RPM shell/Lua/include 恶意 fixture，确认默认静态扫描路径不调用完整 RPM 求值。

## 7. 固化选型并验证测试容器边界

- [x] 7.1 生成 `technology-selection.md`，逐项记录采用、可选增强、拒绝和自研边界，并附容器版本、许可证、fixture、性能和安全证据。
- [x] 7.2 确认本 change 不拆分或修改 production images，`backend/Dockerfile` 与根 Compose 保持不变，候选技术的生产接入留给后续独立 change。
- [x] 7.3 只构建独立 `kb-scanner-test` 镜像，并验证容器中的 Scanner CLI 及缺失 compilation context 时的可观测降级行为。
- [x] 7.4 在测试容器中运行全部 KB Scanner 回归与结果契约测试，确认 schemaVersion 1.0、既有 Finding 语义、三个 artifact 及生成知识数据均未退化。
- [x] 7.5 分别验证根 Compose 与 `tools/kb-scanner/compose.test.yml` 配置，确认测试 project 不改变现有 API/worker 镜像选择、服务集合、路径、网络、卷和环境变量。
- [x] 7.6 更新容器构建与测试文档，只提供 Docker 命令作为正式 KB Scanner 依赖安装和验证方式。
- [x] 7.7 运行 `openspec validate select-kb-scanner-technology-stack --strict` 并修复所有规格格式或一致性问题。
