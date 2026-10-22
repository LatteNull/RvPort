## Context

当前基础入口把两种职责放在同一进程中：`collect` 读取编译数据库、探测 GCC/Clang、发现依赖并执行 `-emit-llvm`，随后 worker 读取 BC 生成 `ModuleFacts v2`；`link` 还会调用 `llvm-link` 生成 linked BC。实际部署已经由外部 x86 构建系统产生 BC，分析器应只消费不可变产物。继续保留生产侧编译不仅重复构建职责，也让纯 IR 分析依赖源树、SDK、编译器和链接工具，并使“上游没有产出”和“分析失败”难以区分。

既有 P1–A6、R1–R3 已通过 `artifact-store/artifacts` 与 `artifact-store/facts` 消费 `BCArtifact` 和 `ModuleFacts`，因此可以在输入边界增加独立 ingestion sidecar，而不迁移下游协议。AST 仍是独立可选事实层：有可信源码和编译记录时可运行 Clang source worker；没有时保持 IR-only。`compile_commands.json` 不是完整 target/link 图，外部 bundle 必须单独声明 planned 分母和 scope。

## Goals / Non-Goals

**Goals:**

- 让生产分析进程只读取外部 raw LLVM BC，不执行 compiler、dependency generation、`llvm-link`、configure/build、网络、SSH 或目标程序。
- 以独立版本化 bundle/record/report 表达上游计划、成功、缺失、失败和目标成员关系，避免目录扫描与成功子集偏差。
- 对每个产物执行内容、格式、LLVM reader、target/DataLayout/profile、TU、scope 和 source lineage 校验，并安全发布既有 `BCArtifact`、`ModuleFacts v2` 与规范化 scope。
- 保持 P1–A6、R1/R1.1、R2、R3 的 schema、semantic digest、缓存和报告语义不变。
- 允许 AST+IR、IR-only 和保守 AST-only，且将外部 artifact 缺口传播为 candidate-relevant partial/unknown。
- 维持 C11、C17、C++17、C++20 及 GCC/Clang 源 profile 范围，同时明确 LLVM BC producer、host 与 target 的区别。

**Non-Goals:**

- 不在分析器内生成、优化、链接、反汇编或修复 BC。
- 不从 `compile_commands.json`、文件名、目录布局、debug path 或符号集合猜测完整 scope、链接成员或 TU 对应关系。
- 不支持 GCC LTO/GIMPLE、ELF/Mach-O/COFF 内嵌 bitcode、MSVC/clang-cl、未知 LLVM dialect、任意 linked/LTO 恢复为逐 TU 或跨 target 结论迁移。
- 不把 x86_64 target BC 的结论推广到 ARM/RISC-V，也不新增硬件内存模型、通用 data-race 或全程序安全证明。
- 不在本 change 合并生产 Dockerfile；开发镜像仍可保留 fixture 编译工具。

## Decisions

### 1. 在既有 artifact store 前增加独立 ingestion adapter

生产数据流固定为：

```text
external build
  -> ExternalBitcodeBundleManifest
  -> ExternalBitcodeArtifactRecord[]
  -> ingest-bc-bundle
  -> BCArtifact + ModuleFacts v2 + normalized ScopeManifest
  -> existing P2/P3/P4/A1-A6/R1-R3 consumers
```

ingestion 不向 `BCArtifact` 或 `ModuleFacts` 添加字段。外部 provenance、分母、映射和诊断保存在 `ExternalBitcodeIngestionReport` 及 bundle sidecar 中。这样下游无需识别新的事实版本，旧 artifact store 仍可读取。

备选方案是直接扩展 `BCArtifact`/`RunReport`；这会迁移所有消费者和缓存，并可能把外部 producer 声明误当成分析器自证，因此拒绝。

### 2. Bundle 以显式记录而不是目录扫描定义计划分母

`ExternalBitcodeBundleManifest v1` 包含 bundle identity、producer/build identity、记录引用、scope 声明、可选 compile database/source root 引用和全局边界。每个 `ExternalBitcodeArtifactRecord v1` 是独立、带 digest 的计划项，至少包含：

- 外部稳定 `record_id` 和 `physical_tu_id`；
- `status=produced|missing|failed` 及受限上游诊断；
- produced 时的 bundle-root 相对 BC 路径与 SHA-256；
- producer family/version、LLVM/Clang 版本、module kind；
- host triple 与 target triple、DataLayout、ABI；
- C/C++、语言标准、优化/debug profile；
- 源路径/摘要、compile record digest、依赖或生成输入摘要（可缺失但影响完整性）；
- target/scope membership evidence。

scope 使用 `record_id` 引用成员；ingestion 成功后输出 `record_id -> artifact_key` 映射并生成规范化 `ScopeManifest`。缺失/失败记录仍属于 planned 分母，不因没有 BC 文件消失。

备选方案是复用内部 `BCArtifact` 作为外部 manifest；该类型要求内部 artifact identity/path，并不能表示未产出计划项或 bundle scope，因此拒绝。

### 3. 内部身份由分析器计算，外部身份只作 provenance

分析器不接受上游提供的 `artifact_key`。内部身份由 BC digest、规范化 record 语义字段、extractor protocol 和 schema/policy 计算；运行目录、绝对 bundle 路径、调度顺序和时间戳不进入语义身份。相同字节但不同 TU/profile 的记录保持不同 artifact identity，底层字节可内容去重。

record、manifest 和 scope 引用都必须验证 digest、唯一性和闭包。输入读取前后重新计算 BC hash；只有稳定且完整通过校验的产物才复制到 `OutputStore` 的内容寻址路径并原子发布。partial/failed 记录不得写成成功 artifact 或缓存命中。

### 4. 校验流水线只读取，不转换输入

每个 produced 记录按以下顺序处理：路径必须在显式 bundle root 内且不能通过解析后路径逃逸；文件存在且非空；hash 与记录一致；格式是受支持的 raw LLVM bitcode；锁定 LLVM 21 reader 能 parse/verify；worker 协议匹配；实际 target/DataLayout 与声明一致；语言/profile/TU/source/scope 引用不冲突；读取后 hash 不变。任何失败按记录隔离，报告 0/2/1 完整性退出码，不调用 compiler 或尝试修复。

GCC LTO/GIMPLE 和对象容器直接拒绝。`module_kind=translation-unit` 是正式完整路径；显式声明的 linked/LTO LLVM BC 可以作为受限 IR-only 输入导入，但必须产生非空 frontier，不能恢复 physical TU、覆盖 AST 对齐或形成 closed scope。未声明却呈现 linked/LTO 特征时拒绝。

### 5. x86 host 与分析 target 分开建模

`producer_host` 只说明构建执行位置；正式兼容性由 BC 内实际 target triple、DataLayout、ABI 与 record 声明决定。x86 主机交叉生成 ARM BC 可以按 ARM profile 分析；x86_64 target BC 只能覆盖该 x86 配置，不能代表 ARM/RISC-V 条件编译、布局、intrinsic 或 inline asm。报告同时展示 host 与 target，并在请求 target 不一致时失败而非改写 triple。

优化后的 build-faithful BC 可以分析现存 IR，但优化消除的访问不可恢复。缺少分析友好 profile 或 debug/source 映射时，报告降低证据完整性；AST 可保留源码候选，但不能单独建立 RF、SW、HB、risk 或 discharged。

### 6. 编译数据库只服务可选 AST/profile，不产生 BC

外部 record 通过 compile record digest 和 physical TU 显式绑定可选 `CompilationProfileIdentity`。source worker 可在 AST 模式解析源码，但不能调用 `-emit-llvm`、写 object/BC 或运行构建系统。没有源码/编译记录时继续 IR-only；记录不匹配时保留独立事实并进入 partial/unknown，不按文件名自动对齐。

现有 `context.py` 中仅为 analyzer-side emission 服务的命令适配、依赖发现和 artifact key 逻辑移除；仍需要的参数解析迁移或收敛到 source profile 层。C 与 C++ profile、标准库/ABI 身份继续独立。

### 7. 生产 CLI 删除 collect/link，新增批量 ingestion

`ingest-bc-bundle --bundle MANIFEST --output STORE --worker READER` 是正式入口，要求全新输出目录并输出 bundle、record、scope、facts 和报告。`import-bc` 保留为单文件兼容入口，内部复用相同读取/发布 primitive，但没有 bundle 分母和 scope 时必须标记低完整性。`index` 继续消费显式 scope；`link` 与 `collect` 从生产 parser、执行分支和文档删除。

`doctor` 拆为 reader readiness 与 source readiness。纯 BC ingestion 只探测 worker protocol/LLVM reader 所需能力；不得因没有 GCC、Clang driver、`llvm-link`、`opt` 或覆盖率工具失败。开发/质量 doctor 可另行检查构建和 coverage 工具，不能混入生产 readiness。

### 8. 完整性与缓存独立于下游风险判定

`ExternalBitcodeIngestionReport` 分别统计 planned、produced、missing、upstream-failed、hash-valid、format-valid、parsed、verified、published、facts-complete/partial/failed、source-bound、scope-resolved 和 frontier。退出 0 表示请求的 ingestion 分母完整且无相关缺口，2 表示有可用 artifact 但 partial/unknown，1 表示请求非法或没有可用 artifact；它不包含安全 finding，并固定 `safety=not_evaluated`。

下游仍根据 candidate dependency slice 决定缺失记录是否阻断具体候选，但 request-level completeness 必须保留。ingestion cache 只复用 digest、record、reader protocol、target/profile 和预算完全一致的完整结果；输入文件每次使用仍校验 hash。

### 9. fixture 编译与产品行为严格分离

真实 C/C++ fixture 可以由测试 harness 在调用分析器前生成 BC，用于证明 reader 对真实 Clang 输出的兼容性；这些命令必须被记录为 fixture preparation，不能由 `memory_order_analyzer` CLI、ingestion driver 或下游 runner 发起。单元测试注入禁止执行 runner，集成测试审计 argv/进程边界，确保生产路径不出现 compiler、linker、CMake、网络、SSH 或目标程序。

质量入口继续覆盖全部自有 Python/C++，包括未加载模块。整体、每种实现语言和每个受影响模块行/分支均至少 90%，集成 profile 不补入单元覆盖率。

## Risks / Trade-offs

- [外部 bundle 自述可能不真实] → 所有可从 BC 导出的 target/DataLayout/hash 都交叉验证；无法独立验证的 producer/profile/source 声明标为 attested 而非 analyzer-proven，不提升安全证据。
- [只有优化 BC 导致访问消失] → 保存 optimization/module-kind，降低完整性并建议上游另产分析友好 BC；不在分析器内重编译。
- [删除 collect/link 破坏现有脚本] → 提供明确迁移文档、低级 `import-bc` 兼容路径和 fixture bundle 生成示例；不保留会静默编译的别名。
- [大 bundle 复制带来磁盘开销] → 内容寻址去重并使用流式 hash/copy；首版不提供未经验证的外部引用模式，优先保证输入稳定性。
- [linked/LTO 输入看似信息更多但破坏 TU 身份] → 仅显式受限导入并强制 partial/frontier，正式完整路径限定逐 TU raw BC。
- [reader 无法读取更高版本或定制 LLVM BC] → 明确 `reader-incompatible`，保留 planned 分母；不调用外部转换工具或用扩展名假装成功。
- [AST 仍需前端解析，容易被误解为生成 BC] → 文档和进程测试明确 AST source worker 只解析源码，禁止 `-emit-llvm`/输出 BC；AST 阶段与 ingestion 分开报告。

## Migration Plan

1. 新增 bundle/record/report schema、契约验证、内容寻址 ingestion primitive 和 `ingest-bc-bundle`，先保持下游 artifact layout 不变。
2. 拆分 reader/source/development readiness，并让 `import-bc` 复用新 primitive。
3. 将现有集成 fixture 改为“外部预生成 BC → bundle ingestion → 原分析链”，加入禁止执行断言和四语言/跨 TU/partial truth。
4. 删除生产 `collect`、`link`、依赖发现和 BC emission 分支；删除不再使用的 compiler adaptation/runtime subprocess 路径，保留 AST profile 所需解析。
5. 更新主文档、示例、路线图和 specs，运行全量单元、集成、覆盖率及 OpenSpec 严格校验。

归档的历史报告和 artifact store 不重写；仍可由既有下游读取。回滚只需恢复旧 CLI/入口代码，不需要迁移 P1–A6 数据。新 bundle schema 在未完成 change 前不承诺稳定。

## Open Questions

- 外部 x86 构建系统最终如何生成 bundle 文件属于上游集成工作；本 change 固定消费协议与示例生成器/fixture，不把任何特定构建系统适配纳入分析器。
- 首版是否使用文件复制或在同文件系统尝试只读 hardlink 可在实施时以安全性和跨平台测试决定；无论方式如何，artifact store 都必须拥有稳定内容并在消费时验证 digest。
