# Shared LLVM bitcode artifact contract v2

English | [简体中文](shared-llvm-bitcode-artifact-contract-v2.zh-CN.md)

SharedLlvmBitcodeArtifactSet@2.1 is RvPort's neutral platform-level BC contract. A non-blocking stage after source/x86 builds produces it in object storage for floating-point and memory-order analysis to reuse. Consumers also read 2.0; new producers publish only 2.1.

## Language-standard context

Each record contains standard, dialect, standard_source, and standard_option. Preserve actual C89/C90, C99, C11, C17/C18, C++98, C++03, C++11, C++14, C++17, and C++20 semantics. C23/C++23 may be accepted according to current Clang capabilities but are outside the initial rule-accuracy commitment. GNU aliases use dialect=gnu. Without -std, record compiler-default and producer identity; never guess C17/C++17.

Failed/missing records retain physical TU, context, source, compilation-record digest, and standard context just like produced records, allowing complete AST denominators even with incomplete BC.

## Consumption modes

- AST_BC_COMPLETE: all planned TUs have validated BC.
- AST_BC_MIXED: only some have BC; every TU still receives AST rules.
- AST_ONLY: BC is absent, all members failed, or worker validation failed. Analysis continues; IR-specific rules degrade to unknown/not-applicable.

## Identity and boundaries

- Manifests contain no project/source-revision/build-record/database/object-storage primary keys. Backend databases retain those associations.
- All identities use SHA-256 of UTF-8 canonical JSON. Sort object keys and arrays by canonical JSON; normalize paths to relative POSIX paths.
- generated_at, diagnostics, external bundle hashes, and business primary keys do not enter artifact-set identity.
- raw_compile_commands_sha256 proves original input bytes for one run and remains audit evidence, outside semantic identity. normalized_digest captures stable compilation semantics after removing controlled deployment roots and participates in semantic_digest/artifact_set_id.
- Platform artifact_key is not the analyzer's internal ArtifactKey; analyzers recompute identity under their own extractor/schema/policy.

## Bundle layout

```text
manifest.json
records/<record_id>.json
bitcode/<record_id>.bc
sidecars/<record_id>/*
scopes/<scope_id>.json
```

Each unique normalized context produces a record; entries converging on the same final record_id count once. Successful members are produced, absent inputs missing, and compilation/verification/budget/timeout errors failed. Failures never disappear from planned denominators.

Current profile source-preserving@1 retains per-TU raw modules, debug/source correlation, floating-point IR, atomic ordering, syncscope, fences, target/DataLayout, and linkage. If the compilation database cannot prove target closure, producers create closed=false fallback scopes by target triple.

## Consumer compatibility

| V2 field | Floating-point scanner | Memory Order Analyzer |
|---|---|---|
| record/status/bitcode | Select produced members, retain failed denominators | Map ExternalBitcodeArtifactRecord, preserve produced/missing/failed |
| producer/target | Validate LLVM reader and floating-point target semantics | Preserve producer, target triple, DataLayout, ABI |
| language/standard/optimization/debug/module_kind | Build analysis contexts | Preserve required external-record fields |
| source/compile_record_digest/input_digests | Source locations/provenance | Preserve fields; gaps stay partial |
| scopes | Project aggregation | Map bundle scopes; open scopes create partial/frontiers |
| capabilities | Select fp.* and source correlation | Select memory.*, target, debug, linkage |
| artifact_key | Platform identity | External reference only, never internal ArtifactKey |

Adapters, object-storage materializers, and analysis runtime integration are separate from this contract upgrade. Tools run as local child processes in backend-worker without dedicated scanner containers or docker.sock.
