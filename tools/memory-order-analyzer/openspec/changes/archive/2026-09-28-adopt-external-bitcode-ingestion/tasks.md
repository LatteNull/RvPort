## 1. 协议、兼容基线与输入模型

- [x] 1.1 冻结 P1 `BCArtifact`/`ModuleFacts v2`/`RunReport v2`、P2–P4、A1–A6、R1/R1.1、R2、R3 黄金产物和 semantic digest，记录 change 前 CLI、schema 与 artifact-store 布局。
- [x] 1.2 为 `ExternalBitcodeBundleManifest v1`、`ExternalBitcodeArtifactRecord v1` 和 `ExternalBitcodeIngestionReport v1` 增加独立 schema、kind/version/policy manifest、canonical digest 和 producer identity。
- [x] 1.3 定义 standalone record 引用、planned 状态、produced 条件字段、scope record membership、上游诊断、预算、双语 frontier 和 0/2/1 退出语义的交叉字段校验。
- [x] 1.4 增加正常、未来版本、未知字段、替换 digest、悬空引用、重复 record/TU/scope、非法状态组合和伪 complete 的契约单元测试。

## 2. 外部路径、内容与格式校验

- [x] 2.1 实现 bundle root 安全解析，拒绝绝对路径、`..` 穿越、解析后越界、非法符号链接、空文件和非 regular file，并为每个失败提供中英文诊断。
- [x] 2.2 实现有界流式 SHA-256、读取前后稳定性校验、字节/record/output/time 预算和临时文件清理，不把失败/变化输入发布到 store。
- [x] 2.3 实现 raw LLVM bitcode magic 分类，明确拒绝 GCC LTO/GIMPLE、ELF/Mach-O/COFF 容器、文本 IR、截断/损坏和伪 `.bc` 文件，不调用转换工具。
- [x] 2.4 复用只读 worker 完成 parse/verify/ModuleFacts 提取，并交叉验证实际 module hash、target triple 和 DataLayout 与 record 声明。
- [x] 2.5 为 path boundary、symlink、TOCTOU/input-changed、hash mismatch、格式矩阵、reader incompatible、verify failure、预算和独立记录失败隔离补齐单元测试。

## 3. 身份、provenance 与内容寻址发布

- [x] 3.1 定义不信任外部 ArtifactKey 的内部身份算法，纳入 BC digest、规范化 record 语义、extractor/schema/policy，排除宿主路径、时间、顺序和 cache hit。
- [x] 3.2 区分 analyzer-verified 与 producer-attested provenance；验证同字节不同 TU/profile 得到不同 artifact identity，底层内容可安全去重且不合并语义。
- [x] 3.3 实现稳定输入到 owned `OutputStore` 的原子物化和标准 `artifacts/<key>.bc`、`artifacts/<key>.json`、`facts/<key>.json` 发布，任何 partial/failed 不生成空 facts。
- [x] 3.4 实现 record-to-artifact 映射及 bundle scope 到既有 `ScopeManifest` 的规范化转换，保留 missing/failed、开放边界、target/DataLayout/ABI、重复 lineage 和成员冲突。
- [x] 3.5 为重复字节/不同配置、外部伪 key、发布失败、并发目标存在、scope 冲突、partial bundle 和确定性排序补齐单元测试。

## 4. Bundle ingestion、缓存与报告

- [x] 4.1 实现 `ingest-bc-bundle` driver，按确定顺序加载 manifest/records、执行有界逐项校验、发布成功产物并保留全部计划项与失败项。
- [x] 4.2 实现完整 `ExternalBitcodeIngestionReport` 计数：planned、produced、missing、upstream-failed、hash/format/parse/verify、published、facts、source-bound、scope-resolved、cache 和 frontier。
- [x] 4.3 实现 target host/target 分离与 profile 检查：x86 host 交叉 target 可用，x86_64 target 不得冒充 ARM/RISC-V，target/DataLayout/ABI 冲突必须阻止精确采用。
- [x] 4.4 实现 `translation-unit`、显式 `linked`/`lto` 和 optimization/debug profile 边界；linked/LTO 或证据损失必须产生非空 partial/frontier，未声明特征拒绝。
- [x] 4.5 实现 record/local facts 分层 cache，key 包含完整依赖和预算，只发布完整稳定项；损坏、陈旧、partial、failed、开放引用和协议变化不得命中。
- [x] 4.6 为 complete/partial/failed、0/2/1、cold/warm digest、cache invalidation/corruption、host/target、linked/optimized 和零计划分母补齐单元测试。

## 5. CLI、readiness 与兼容入口

- [x] 5.1 在公共 parser/execute/error report 中接入 `ingest-bc-bundle --bundle --output --worker`，要求新输出目录并保证 stdout 仅有机器 JSON、stderr 仅有诊断。
- [x] 5.2 将 `import-bc` 重构为复用 ingestion 的单文件校验/发布 primitive；无 bundle provenance/scope 时固定低完整性，保留既有可读取 artifact/facts 行为。
- [x] 5.3 拆分 reader、source 和 development/quality readiness；纯 ingestion 只要求 worker/protocol/runtime，不检查 GCC、Clang driver、opt、llvm-link 或覆盖率工具。
- [x] 5.4 从生产 CLI 删除 `collect` 和 `link`，删除或隔离所有可触发 dependency discovery、`-emit-llvm` 和 `llvm-link` 的执行分支；旧命令必须以未知请求失败。
- [x] 5.5 更新 `index` 和 scope 消费路径以使用 ingestion 生成的 artifact/scope，并确认跨 TU 不依赖 linked BC。
- [x] 5.6 为 CLI 参数、结构化失败报告、bare import、无 compiler 环境 readiness、removed command 和 scope/index 兼容性补齐单元测试。

## 6. AST/profile 与降级分析适配

- [x] 6.1 将 compile database 处理收缩为可选 `CompilationProfileIdentity`/AST 输入，移除 BC emission effective argv 和 analyzer-side dependency/artifact-key 职责，保留受限参数/响应文件解析。
- [x] 6.2 通过 explicit compile record digest、physical TU、source hash、target/ABI/profile 将 source facts 与外部 record 对齐；禁止文件名、debug path 或符号相似自动绑定。
- [x] 6.3 更新 A2 availability/failure 分类，新增 external-artifact-missing、external-build-failed、format-unsupported、reader-incompatible，并只为历史报告保留旧 ir-generation-failed 解释。
- [x] 6.4 验证 AST+IR、IR-only、AST-only、failed/mixed 及候选依赖切片传播；AST/source worker 不得使用 `-emit-llvm`、写 BC/object 或关闭缺失 IR frontier。
- [x] 6.5 为 C11/C17 与 C++17/C++20 独立 profile、record mismatch、无源码、GCC source/Clang BC、generated-header upstream failure 和 candidate-related/unrelated 缺口补齐单元测试。

## 7. 禁止执行边界与真实外部 fixture

- [x] 7.1 建立 C11、C17、C++17、C++20 的逐 TU external bundle fixtures，覆盖单 TU、跨 TU scope、no-debug、O0/O2、AST+IR、IR-only、missing/failed 和 record/source mismatch。
- [x] 7.2 在产品 CLI 调用前由独立 harness 预生成真实 Clang BC，并在验收记录中区分 fixture preparation 与受测 ingestion；不得把 harness 编译计为产品能力。
- [x] 7.3 增加 GCC LTO/GIMPLE、ELF 容器、文本 IR、损坏/未来 BC、显式/未声明 linked/LTO、x86 host ARM target 和 x86 target 冒充 ARM 的负例。
- [x] 7.4 使用注入 runner 与集成进程审计验证 ingestion、import、index、AST 和下游分析不执行 compiler、dependency generator、assembler、linker、CMake/configure/build、网络、SSH 或目标程序。
- [x] 7.5 将依赖 `collect` 的既有真实集成改为消费外部预生成 bundle，持续回归 P1–A6、R1/R1.1、R2、R3 四语言 truth、跨 TU identity 和安全边界。

## 8. 文档、示例与迁移

- [x] 8.1 更新 README、`doc/BC_PIPELINE.md`、`FOUNDATION_IMPLEMENTATION.md`、构建上下文、AST/降级、架构文档和 `doc/IMPLEMENTATION_ROADMAP.md`，统一说明生产分析器只消费外部 BC。
- [x] 8.2 提供最小 bundle/record/scope 示例、ingestion/index/分析命令、record-to-artifact 映射与 0/2/1 完整性解释；删除生产 collect/link 和 analyzer-side `-emit-llvm` 示例。
- [x] 8.3 文档明确 raw per-TU、producer/LLVM 版本、host/target、DataLayout/ABI、优化/debug、GCC LTO/容器拒绝、linked/LTO partial 与 x86/ARM/RISC-V 边界。
- [x] 8.4 编写从 collect/link 工作流迁移到外部 bundle 的指南，说明历史 artifact store 不重写、bare import 的低完整性及上游 bundle 生成不属于分析器职责。
- [x] 8.5 更新文档索引并运行本地链接、示例 JSON/schema、命令帮助和禁止过时状态检查，保留历史实验为历史证据而非当前工作流。

## 9. 单元测试与覆盖率 required gate

- [x] 9.1 枚举全部新增、修改、复用和删除后残留的 Python/C++ 执行模块，确认 contracts、path/hash、reader、identity、publication、scope、cache、CLI、readiness、AST/degraded、report 均有正常、边界、异常和 unknown 单元断言。
- [x] 9.2 更新质量源码枚举与门槛测试，确保未加载 Python、未调用 C++、新子目录、可执行头文件和不可达旧 producer 逻辑不从分母消失，并覆盖 89.99%、90%、缺失报告与逐模块失败。
- [x] 9.3 在锁定开发容器的新输出目录运行全量 unit-only 质量入口，验收项目整体、Python、C++ 和每个受影响模块行覆盖率与分支覆盖率均至少 90%，不得混入集成 profile。
- [x] 9.4 独立运行 external bundle 四语言 truth、禁止执行审计、AST/IR 模式、跨 TU、host/target、格式拒绝、cold/warm cache 和全部既有回归；任何失败保持任务未完成。
- [x] 9.5 发布精确命令、镜像/LLVM/Clang/schema hash、测试数、line/branch hit/total、统计范围、排除理由、truth/完整性指标、禁止执行结果、失败差距和报告位置。

## 10. 最终一致性与 OpenSpec 门禁

- [x] 10.1 对比 change 前黄金产物，确认 P1 ModuleFacts/RunReport、P2–P4、A1–A6、R1–R3 schema、semantic digest、缓存和报告语义未被 ingestion sidecar 修改。
- [x] 10.2 运行 OpenSpec 严格校验、schema/reference、文档链接/示例/命令、Git whitespace 和全仓相关回归，确认没有新增在线、SSH、DevKit 或兄弟项目依赖。
- [x] 10.3 仅在实现、单元、整体/语言/逐模块双 90%、四语言 truth、禁止执行、既有回归、缓存、文档和 required gate 全部通过后，更新 tasks/验收记录并准备同步归档。
