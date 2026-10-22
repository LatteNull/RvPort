# 外部 LLVM BC 导入

[English](EXTERNAL_BITCODE_INGESTION.md) | 简体中文

状态：`adopt-external-bitcode-ingestion` 将生产分析入口改为只消费外部生成的 raw LLVM bitcode。分析器不再执行 compiler、dependency generator、assembler、`llvm-link`、configure/build、网络、SSH 或被分析程序；唯一允许的外部进程是经过协议握手的只读 LLVM reader，以及用户显式启用的 source worker。

## 输入责任边界

上游 x86 构建负责按真实 GCC/Clang C/C++ 配置准备逐 TU BC、源码/编译记录摘要和目标成员清单。BC producer host 与 BC target 分开登记：x86_64 host 可以产生 AArch64 target BC，但 x86_64 target BC 不能声明覆盖 ARM/RISC-V 配置。正式路径是逐 TU raw BC；GCC LTO/GIMPLE、ELF/Mach-O/COFF 内嵌 BC、文本 `.ll`、损坏或 reader 不兼容文件会被拒绝。显式声明的 linked/LTO BC 仅作为 partial IR-only 证据。

`compile_commands.json` 只是可选 AST `CompilationProfileIdentity` 与 `SourceIRBinding` 输入，不触发 BC 生成，也不能单独证明 scope。源码与 compile record 必须通过 digest、physical TU、source hash、target/ABI/profile 显式对齐，禁止按文件名、debug path 或符号相似度猜测。

## Bundle 与 record

manifest 引用独立 record 文件；所有路径必须是规范化相对路径，禁止绝对路径、`..`、符号链接和目录扫描。manifest 以 record 数量作为计划分母，并显式列出 scope：

```json
{
  "schema_version": 1,
  "kind": "ExternalBitcodeBundleManifest",
  "ingestion_version": "0.1.0",
  "policy_id": "external-bitcode-ingestion-v1",
  "bundle_id": "build-20260924",
  "producer": {"family":"clang","version":"21.1.8","llvm_version":"21.1.8","host_triple":"x86_64-pc-linux-gnu"},
  "records": [{"path":"records/main.json","sha256":"<record 文件 SHA-256>"}],
  "scopes": [{"target_id":"app","record_ids":["main-tu"],"evidence":"上游目标清单","closed":true,"external_boundaries":[],"target_triple":"aarch64-unknown-linux-gnu"}],
  "budgets": {"max_records":10000,"max_artifact_bytes":1073741824,"max_total_bytes":8589934592,"max_worker_seconds":120,"max_output_bytes":16777216},
  "semantic_digest": "<canonical semantic digest>"
}
```

record 必须保留 `produced`、`missing` 或 `failed` 计划项。只有 `produced` 包含 `bitcode.path/sha256/bytes`；另外登记 producer、target triple、DataLayout、ABI、语言标准、优化/debug、module kind、physical TU、source、compile record 和输入摘要。`semantic_digest` 应由 `external_document(...)` 生成，不能手填伪 complete。

最小 produced record 如下；`physical_tu_id`、所有 SHA-256 和末尾 semantic digest 均是 64 位小写十六进制摘要：

```json
{
  "schema_version": 1,
  "kind": "ExternalBitcodeArtifactRecord",
  "ingestion_version": "0.1.0",
  "policy_id": "external-bitcode-ingestion-v1",
  "record_id": "main-tu",
  "physical_tu_id": "<physical TU identity>",
  "status": "produced",
  "diagnostic": null,
  "bitcode": {"path":"bc/main.bc","sha256":"<BC SHA-256>","bytes":4096},
  "producer": {"family":"clang","version":"21.1.8","llvm_version":"21.1.8","host_triple":"x86_64-pc-linux-gnu"},
  "target": {"triple":"aarch64-unknown-linux-gnu","data_layout":"<实际 DataLayout>","abi":{"family":"aapcs64"}},
  "language": "c",
  "standard": "c17",
  "optimization": "O0",
  "debug": "full",
  "module_kind": "translation-unit",
  "source": {"path":"src/main.c","sha256":"<源码 SHA-256>"},
  "compile_record_digest": "<编译记录 SHA-256>",
  "input_digests": {"include/config.h":"<输入 SHA-256>"},
  "semantic_digest": "<canonical semantic digest>"
}
```

`producer`、ABI、优化/debug 和 `module_kind` 是 producer-attested；导入器独立验证 BC 内容摘要、格式、reader 协议、parse/verify、实际 target 与 DataLayout。linked/LTO 的自述不能提升为逐 TU 证明，必须进入 partial frontier。

## 命令、产物和退出码

```sh
python3 -m memory_order_analyzer ingest-bc-bundle \
  --bundle /bundle/manifest.json \
  --output /output/ingestion-001 \
  --cache /output/external-bc-cache \
  --worker /output/build/moa-worker

python3 -m memory_order_analyzer index \
  --scope /output/ingestion-001/scopes/app.json \
  --artifact-store /output/ingestion-001 \
  --output /output/index-001
```

输出继续包含 `artifacts/<ArtifactKey>.bc/.json` 与 `facts/<ArtifactKey>.json`，并新增 ingestion `report.json`、record-to-artifact 映射和规范化 `ScopeManifest`。内部 ArtifactKey 由 BC digest、record 语义、P1 extractor/schema/policy 和 ingestion policy 计算；不信任外部 key，不含宿主路径、时间、顺序或 cache hit。同一字节在不同 TU/profile 下具有不同语义 identity。

`ExternalBitcodeIngestionReport v1` 统计 planned、produced、missing、upstream-failed、hash/format/reader、published、facts、source binding、scope 和 cache。零分母比例为 `null`。退出码 `0` 表示 ingestion 完整，`2` 表示已有可用产物但存在 frontier，`1` 表示非法请求或无可用产物。报告始终为 `semantic_analysis=not_run`、`safety=not_evaluated`、`findings=null`。

`import-bc` 保留为单文件低完整性兼容入口：它发布可读 BCArtifact/ModuleFacts，但无 bundle 分母和 scope，provenance 为 unknown。`collect` 与 `link` 已从公共 parser 删除。

## 迁移旧工作流

1. 在分析器外部的构建/CI 阶段生成逐 TU raw BC，并记录失败 TU，不能只复制成功文件。
2. 由上游构建图生成 record、manifest 和显式 scope；不要让分析器扫描目录或重放编译数据库。
3. 用 `ingest-bc-bundle` 生成 artifact store，再把 scope 和 record-to-artifact 映射交给 `index`、P1–A6、R1–R3。
4. 历史 artifact store 不重写、不删除；相同 BC 在新 extractor/policy 下重新提取会获得新 identity。
5. 测试可在产品 CLI 启动前用锁定 Clang 预生成 fixture BC，但必须把该步骤标为 test preparation，并审计产品 argv 中没有 compiler/linker/build/网络/SSH/目标程序。

生产 readiness 只检查只读 reader 与 P1 协议；AST/source readiness 和开发/覆盖率工具链分别检查。因此纯 ingestion 环境不需要 GCC、Clang driver、`opt`、`llvm-link` 或 `llvm-cov`。
