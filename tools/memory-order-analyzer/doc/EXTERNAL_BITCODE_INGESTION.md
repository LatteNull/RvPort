# External LLVM bitcode ingestion

English | [简体中文](EXTERNAL_BITCODE_INGESTION.zh-CN.md)

`adopt-external-bitcode-ingestion` makes production analysis consume externally generated raw LLVM bitcode only. It no longer runs compilers, dependency generators, assemblers, llvm-link, configure/build, network, SSH, or analyzed programs. Allowed external processes are protocol-negotiated read-only LLVM readers and explicitly enabled source workers.

## Input responsibilities

Upstream x86 builds prepare per-TU BC, source/compilation-record digests, and target membership from real GCC/Clang configurations. Record producer host separately from BC target: an x86_64 host can produce AArch64 BC, but x86_64-target BC cannot claim ARM/RISC-V coverage. The formal path is per-TU raw BC. Reject GCC LTO/GIMPLE, BC embedded in ELF/Mach-O/COFF, textual .ll, damaged files, and reader-incompatible files. Explicit linked/LTO BC is partial IR-only evidence.

compile_commands.json optionally supplies AST CompilationProfileIdentity/SourceIRBinding inputs, never BC generation or scope proof. Align source/compile records explicitly by digest, physical TU, source hash, target/ABI/profile. Do not guess by filename, debug path, or symbol similarity.

## Bundles and records

Manifests reference separate record files. Paths must be normalized relative paths: no absolute paths, `..`, symlinks, or directory scanning. Record count is the planned denominator; scopes are explicit:

```json
{
  "schema_version": 1,
  "kind": "ExternalBitcodeBundleManifest",
  "ingestion_version": "0.1.0",
  "policy_id": "external-bitcode-ingestion-v1",
  "bundle_id": "build-20260924",
  "producer": {"family":"clang","version":"21.1.8","llvm_version":"21.1.8","host_triple":"x86_64-pc-linux-gnu"},
  "records": [{"path":"records/main.json","sha256":"<record-file SHA-256>"}],
  "scopes": [{"target_id":"app","record_ids":["main-tu"],"evidence":"upstream target inventory","closed":true,"external_boundaries":[],"target_triple":"aarch64-unknown-linux-gnu"}],
  "budgets": {"max_records":10000,"max_artifact_bytes":1073741824,"max_total_bytes":8589934592,"max_worker_seconds":120,"max_output_bytes":16777216},
  "semantic_digest": "<canonical semantic digest>"
}
```

Retain produced, missing, and failed planned records. Only produced records contain bitcode.path/sha256/bytes. Also record producer, target triple, DataLayout, ABI, standard, optimization/debug, module kind, physical TU, source, compilation record, and input digests. Generate semantic_digest with external_document(...), never handwrite a false complete state.

Minimal produced record; physical_tu_id, SHA-256 values, and semantic digest are 64-character lowercase hexadecimal digests:

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
  "target": {"triple":"aarch64-unknown-linux-gnu","data_layout":"<actual DataLayout>","abi":{"family":"aapcs64"}},
  "language": "c",
  "standard": "c17",
  "optimization": "O0",
  "debug": "full",
  "module_kind": "translation-unit",
  "source": {"path":"src/main.c","sha256":"<source SHA-256>"},
  "compile_record_digest": "<compilation-record SHA-256>",
  "input_digests": {"include/config.h":"<input SHA-256>"},
  "semantic_digest": "<canonical semantic digest>"
}
```

Producer, ABI, optimization/debug, and module_kind are producer-attested. The importer independently checks BC digest, format, reader protocol, parse/verify, actual target, and DataLayout. Linked/LTO attestations cannot become per-TU proof and require partial frontiers.

## Commands, artifacts, exits

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

Outputs retain artifacts/<ArtifactKey>.bc/.json and facts/<ArtifactKey>.json, adding ingestion report.json, record-to-artifact mappings, and normalized ScopeManifest. Internal keys bind BC digest, record semantics, P1 extractor/schema/policy, and ingestion policy. External keys are not trusted. Host paths, time, order, and cache hits do not enter identity. Identical bytes in distinct TUs/profiles have distinct semantic identities.

ExternalBitcodeIngestionReport v1 counts planned, produced, missing, upstream-failed, hash/format/reader, published, facts, source binding, scope, and cache. Zero-denominator ratios are null. Exit 0 means complete ingestion, 2 usable artifacts with frontiers, 1 invalid request/no usable artifacts. Reports always retain semantic_analysis=not_run, safety=not_evaluated, findings=null.

import-bc remains a low-completeness single-file compatibility entry, publishing readable BCArtifact/ModuleFacts without bundle denominators/scopes and with unknown provenance. collect and link have been removed from the public parser.

## Updating existing workflows

1. Generate per-TU raw BC outside the analyzer in the build pipeline. Record failed TUs as well as successes.
2. Upstream build graphs produce records/manifests/explicit scopes. Do not ask the analyzer to scan directories or replay databases.
3. ingest-bc-bundle creates the artifact store; pass scopes and record mappings to index, P1–A6, and R1–R3.
4. Do not rewrite/delete historical artifact stores. Re-extraction under new extractor/policy identities creates new identities.
5. Tests may pregenerate fixtures with pinned Clang before product CLI startup, explicitly as test preparation. Audit product argv for absence of compiler/linker/build/network/SSH/target execution.

Production readiness checks only read-only readers and P1 protocol. AST/source readiness and development/coverage tools are separate. Pure ingestion therefore needs no GCC, Clang driver, opt, llvm-link, or llvm-cov.
