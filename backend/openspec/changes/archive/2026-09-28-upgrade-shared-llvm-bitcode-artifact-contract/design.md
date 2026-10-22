## Context

后端当前生成 `llvm-bitcode-artifact-set.v1`，字段主要围绕 RvPort 构建记录组织；浮点精度扫描工具已有另一套同名意义的 manifest schema，要求更完整的翻译单元身份、target、ABI、profile 和 capabilities。两者无法直接互认，且把 `projectId`、`buildRunId`、`sourceRevisionId` 放入共享协议会让独立工具被 RvPort 数据模型绑定。

`memory-order-analyzer` 已实现外部 BC ingestion，并严格使用 `ExternalBitcodeBundleManifest v1`、`ExternalBitcodeArtifactRecord v1` 和 `ExternalBitcodeIngestionReport v1`。它只接受逐 TU raw LLVM BC，要求 planned records、produced/missing/failed、显式 scope、producer host、实际 target/DataLayout/ABI、语言标准、优化/debug、module kind、source hash、compile record digest、input digests 和 semantic digest；导入后由分析器基于 BC 内容与 extractor/schema/policy 自行生成内部 `ArtifactKey`。平台协议必须能够无猜测地适配这套入口，不能把平台 artifact key 冒充分析器内部身份。

共享 BC 已由 source/x86 真实构建后的非阻断阶段生成，manifest 与 bundle 保存到对象存储，构建事实保存安全摘要。本次升级必须保持真实构建结果不受 BC 成败影响，并允许历史 v1 记录继续被查询。后续分析工具直接安装在 `backend-worker` 镜像中，由 worker 以本地子进程运行；本设计不引入独立扫描容器、Docker socket 或容器调度。

## Goals / Non-Goals

**Goals:**

- 定义平台级 `SharedLlvmBitcodeArtifactSet@2.0`，供多个 LLVM 分析工具复用。
- 将可移植制品身份与 RvPort 项目、源码版本、构建记录等业务关联分离。
- 统一翻译单元、编译上下文、producer host、target、ABI、profile、capability、路径和哈希语义。
- 同时满足浮点精度分析输入和 `memory-order-analyzer` external bundle/record/scope 的通用 BC 需求。
- 提供严格 JSON Schema、Java 模型、生产脚本、bundle 校验及两类消费者的确定性字段映射。
- 让新构建只发布 v2，同时保持历史 v1/无 BC 记录可读。

**Non-Goals:**

- 不实现浮点精度或强弱内存序扫描任务、finding、人工确认、迁移报告及归档闭环。
- 不修改 `memory-order-analyzer` 的 P1–A6、R1–R3 内部协议或分析算法。
- 不实现跨制品 resolver、对象存储流式 materializer、等待构建制品或任务唤醒。
- 不增加独立扫描容器，不挂载 `docker.sock`，不改变 worker 部署拓扑。
- 不回填、重写或删除历史 v1 制品。

## Decisions

### 1. 使用中立的 v2 envelope 和完整计划记录

manifest 顶层使用 snake_case，核心结构如下：

```json
{
  "kind": "SharedLlvmBitcodeArtifactSet",
  "schema_version": "2.0",
  "artifact_set_id": "sha256:...",
  "source_identity_digest": "sha256:...",
  "compile_context": {
    "raw_compile_commands_sha256": "sha256:...",
    "normalized_digest": "sha256:..."
  },
  "producer": {},
  "status": "PARTIAL",
  "counts": {},
  "records": [],
  "scopes": [],
  "generated_at": "..."
}
```

`records` 是完整计划分母，每项状态为 `produced`、`missing` 或 `failed`。只有 produced record 引用 BC；missing/failed record 保留稳定 TU/context/profile 身份和双语安全诊断。十个计划 TU 只生成八个 BC 时仍表达 planned=10，而不是扫描现存文件得到八个并错误声明完整。

manifest 不包含 project、source revision、build run、数据库 ID、对象存储 bucket/key、凭据、环境变量值、绝对路径或完整命令。RvPort 业务关联继续由 `stored_artifacts.owner_type/owner_id`、构建事实和制品元数据维护。

选择新主版本而非扩展 v1，是因为字段命名、身份边界和必填语义均发生不兼容变化；继续称为 v1 会掩盖消费者不兼容。

### 2. 区分原始输入哈希与规范化上下文摘要

`raw_compile_commands_sha256` 对原始文件字节计算，用于证明输入文件是否完全一致。`normalized_digest` 对移除受控部署根差异、排序并规范化后的有效编译上下文计算，用于判断两个制品是否具有相同分析语义。

`source_identity_digest` 来源于当前不可变源码快照的内容身份，不使用数据库 UUID。若现有源码制品暂时只有稳定内容哈希，则直接使用该哈希；不得退化为路径或记录 ID。

### 3. 稳定计算平台身份但不占用消费者身份域

- `physical_tu_id`：规范化源码身份、语言和源码内容摘要的 SHA-256。
- `context_id`：`physical_tu_id`、规范化编译参数、语言标准、target/ABI、工作目录映射和 response-file 展开结果的 SHA-256。
- 平台 `artifact_key`：`context_id`、profile、profile version、toolchain identity 和 BC 内容身份的 SHA-256。
- `artifact_set_id`：schema 主版本、source identity、normalized compile context、producer/toolchain identity、按 record identity 排序的完整计划分母以及 scope digest 的 SHA-256。

身份输入使用 UTF-8 canonical JSON、固定键顺序和稳定数组排序。`generated_at`、诊断文本、bundle 外部哈希及 RvPort 元数据不参与身份。

平台 `artifact_key` 仅标识共享制品，不是 `memory-order-analyzer` 内部 `ArtifactKey`。后者必须继续由分析器根据 BC digest、record 语义、extractor/schema/policy 计算；适配器不得把平台 key 填入或伪装成内部 key。

### 4. 每个计划 record 显式声明 production context

每个 record 至少包含稳定 record ID、physical TU ID、context ID、profile、状态和 semantic digest。produced record 还至少包含：

- source 相对路径与 SHA-256、language、language standard
- production compiler 身份与 BC producer family/version/LLVM version/host triple
- target triple、DataLayout、结构化 ABI，以及可用的 CPU/sysroot/SDK provenance
- optimization、debug、`module_kind=translation-unit`
- compile record digest 和有界的 source/header/response/generated input digests
- profile、profile version、通用 capabilities 和可选版本化 sidecars
- BC 相对路径、大小和 SHA-256

字段必须区分 producer-attested 与后端实际验证。后端独立从 BC 验证 raw bitcode、SHA-256、target triple、DataLayout 和 reader/verifier 兼容性；不能因 producer 自述而提升 provenance。

missing/failed record 不引用 BC，也不从计划分母中消失。source 或 input digest 不完整时，BC 可以保留为 produced 供 IR-only 分析，但 provenance 必须标记 partial，不能声称 source/profile 等价或完整缓存覆盖。

### 5. profile 与 capability 同时服务两类消费者

`source-preserving` 表示保留 debug location、变量关联及源级操作，并使用适合源码关联的受控优化参数；`build-faithful` 表示尽可能保持真实构建优化和代码生成语义。当前生产器只承诺 `source-preserving@1`，但协议允许同一 `context_id` 同时发布多个 profile，平台 artifact key 必须包含 profile 与版本。计数同时区分 planned contexts 和 planned profile records。

capability 使用平台级名称，不采用 `llvm-fp-facts` 或 `memory-model-facts` 等消费者私有名称。v2 至少定义：

- `llvm.ir-readable`
- `debug.locations`
- `debug.variables`
- `source.correlation`
- `fp.operations`
- `fp.fast-math-flags`
- `memory.atomic-ordering`
- `memory.syncscope`
- `memory.fence`
- `target.triple`
- `target.data-layout`
- `symbols.linkage`

能力只表示 producer/validator 已确认 BC 保存相应信息，不表示分析器已经生成 facts 或 finding。浮点扫描器按 capability 选择成员；`memory-order-analyzer` adapter 主要映射 record 的结构化 production context，并仍由其 reader/extractor 验证 LLVM 事实。

sidecar 使用 `{kind, schema_version, path, size, sha256, capabilities}`，可承载 source binding、symbol/linkage index 或 scope manifest。未声明 sidecar 不得被假定存在。

### 6. 显式表达 target scope，缺失时不得伪造完整性

v2 支持 scope 声明，至少包含稳定 target ID、record IDs、成员证据、closed、external boundaries、target triple 和 semantic digest。scope 身份独立于 record/artifact identity：目标成员变化可改变 scope 与 artifact-set identity，但不重键未变化的 BC record。

只有构建图或明确目标成员证据足够时才能声明 `closed=true`。v2 artifact-set 至少包含一个 scope；若当前 producer 只有逐 TU compile database，无法确定完整 target membership，则按 target triple 将全部计划 records 放入稳定的 fallback scope，声明 `closed=false`，记录证据为 compile-database planned set，并把未知目标边界写入 external boundaries。后续 `memory-order-analyzer` 适配由此生成合法但 partial 的 scope/frontier，不能扫描目录、按文件名猜成员或声称全程序完整。

### 7. 保留逐 TU raw module，不默认预链接

共享制品保持“每 TU、每 profile 一个 raw module”。预链接可能改变 linkage、内联、原子操作和 debug mapping，并损失物理 TU 边界；这与 `memory-order-analyzer` 的正式精确路径一致。linked/LTO 只能作为显式标注的受限 IR-only record，不能冒充 translation-unit record。

bundle 逻辑布局为：

```text
manifest.json
records/<record_id>.json
bitcode/<record_id>.bc
sidecars/<record_id>/*
scopes/*.json
```

所有路径必须是 POSIX 相对路径。校验器拒绝绝对路径、`..`、反斜杠逃逸、符号链接、硬链接、设备文件、重复条目、超预算、未声明文件、缺失 record 和 hash/size 不一致。外部 bundle SHA-256 保存于 stored artifact 元数据和构建事实，不参与 manifest semantic identity。

### 8. 为两类消费者定义 adapter contract

后端资源中保存 v2 JSON Schema、有效/无效 fixture、协议说明和消费者字段映射。Java 模型、远端 producer 与后端校验器必须针对同一 schema；后端不能只信任脚本退出码。

浮点扫描器通过 adapter 将 v2 record 映射为其 artifact-set 输入。`memory-order-analyzer` adapter 将 v2 records/scopes 确定性转换为其 `ExternalBitcodeBundleManifest/ArtifactRecord v1`，保留 producer、target、profile、source、compile/input digests、planned failures 和 scope；分析器 ingestion 再计算内部 ArtifactKey。适配不得修改 P1–A6、R1–R3 既有协议。

本 change 冻结平台协议并提供兼容 fixture；两个工具内的 adapter 实现分别属于后续集成 change。

### 9. 历史兼容仅限读取

新 BC 一律生成 v2。历史 v1 构建响应继续返回已有安全摘要，并明确 `schemaVersion=v1`、`legacy=true`；没有 BC 字段的记录继续返回 `NOT_ATTEMPTED/LEGACY_RECORD`。后端不把 v1 运行时转换为 v2，也不让严格依赖 v2 的消费者误用历史制品。

### 10. 测试边界

单元测试使用 fixture 和 mock 的 SSH/SFTP、对象存储及数据库连接返回值，覆盖 canonical identity、READY/PARTIAL/FAILED、planned 分母、produced/missing/failed records、开放/闭合 scope、路径逃逸、损坏 bundle、重复 record、计数/hash 错误、历史读取和主构建隔离。

增加与真实 `memory-order-analyzer` external-bitcode schema 对齐的兼容 fixture，证明 v2 可以无丢失地映射其必填 bundle/record/scope 字段，并证明平台 artifact key 未被用作分析器内部 ArtifactKey。测试不得访问真实 SSH、MinIO、PostgreSQL、Redis 或 RabbitMQ。

项目整体与受影响模块的行覆盖率及工具可用的分支覆盖率均至少为 90%；未被测试加载的项目源码也必须纳入统计。

## Risks / Trade-offs

- [v2 会使现有消费者暂时不能读取新制品] → 在工具集成前冻结并提供 schema、fixture 和兼容矩阵；消费者必须显式声明支持 v2。
- [source-preserving 与 build-faithful 对两类分析的价值不同] → 允许同一 context 发布多 profile；当前只承诺 source-preserving，不虚假声明 build-faithful。
- [当前构建流程可能无法证明 closed target scope] → 按 target triple 发布覆盖全部计划 records 的开放 fallback scope，使分析器返回 partial/frontier；禁止扫描目录或把现存 BC 当作完整分母。
- [平台与分析器都使用 artifact key 名称造成身份混淆] → 协议明确身份域，adapter 只传 record 语义，分析器始终重新计算内部 ArtifactKey。
- [输入依赖摘要收集不完整] → 显式标记 provenance partial，允许 IR-only 使用但不提升源码绑定和缓存完整性。
- [canonical identity 在 Java/Python 间不一致] → 固定 UTF-8、键顺序、数组排序、路径格式和测试向量，并执行交叉测试。
- [manifest 随 TU 和输入摘要数量增长] → 设置数量/体积预算，input digest 有界，不保存完整命令、环境或文件内容。
- [历史 v1 与 v2 同时存在增加查询复杂度] → 响应明确 schema/legacy，写路径只支持 v2。

## Migration Plan

1. 增加 v2 JSON Schema、canonical identity、消费者映射和 fixture，不切换生产。
2. 更新 Java 模型、远端 producer、bundle 校验及单元测试，使同一输入稳定生成 v2。
3. 更新构建事实和响应映射，部署后将新生成制品切换为 v2；保留 v1/无字段读取。
4. 使用真实 source/x86 构建验证 planned records、production context、scope、manifest、bundle、哈希、路径安全和 MinIO 元数据，但 BC 失败仍不得改变构建结果。
5. 用兼容 fixture 验证可映射到浮点扫描输入和 `memory-order-analyzer` external bundle/record；实际工具运行留到各自集成 change。
6. 回滚时可以停止生成新 BC 或回滚 producer；已保存的 v2 制品保持不可变，不删除历史对象。

## Open Questions

无阻断性开放问题。浮点精度与强弱内存序分析器的 adapter、制品 materializer 和 Worker 内扫描运行时分别在后续 change 中实现。
