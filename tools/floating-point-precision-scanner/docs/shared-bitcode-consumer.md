# Shared LLVM bitcode consumption and operations

English | [简体中文](shared-bitcode-consumer.zh-CN.md)

## 1. Boundaries

The floating-point scanner is a read-only shared-BC consumer. It does not compile source to BC, modify x86 build results, hold single-flight locks, or poll `QUEUED`/`GENERATING`. Upstream build/orchestration produces one shared artifact set and submits scans only after it reaches a terminal state. Only `READY`, or `PARTIAL` with at least one complete member, permits extraction. `MISSING`, `QUEUED`, and `GENERATING` return retryable failure; `FAILED` returns non-retryable production failure. All BC-dependent analyzers reuse the same immutable artifact set without occupying workers while waiting.

## 2. Request prerequisites

Source input is always required to reconstruct matching C/C++ compilation contexts and AST facts. Optional `bitcode_artifact_set` contains:

- `artifact_root`: trusted root for the manifest and members.
- `manifest`: manifest path relative to that root.
- `manifest_sha256`: caller-pinned content digest.
- `required_profiles`: defaults to `source-preserving`; explicitly add `build-faithful` if needed.
- `source_mapping`: `best-effort` or `required`.

If provided, `source_revision` must exactly match the manifest. Its `compile_commands_sha256` must match current compilation inputs: raw-file SHA-256 for `compile_commands.json`, or normalized-context semantic digest for explicit translation units.

## 3. Validation order

Before starting LLVM, the consumer rejects untrusted input in this order:

1. Resolved manifest/member paths remain inside `artifact_root`.
2. Manifest SHA-256, JSON, and schema are valid.
3. Source revision and compilation-input digest match.
4. State, counts, members, and failures are consistent; artifact keys and `(context_id, profile)` pairs are unique.
5. Each member matches the current physical C/C++ TU, compilation context, and language.
6. Every required profile has a successful member or explicit failure record.
7. BC and optional binding-sidecar sizes, budgets, and SHA-256 match.

Global identity/integrity failures return `invalid_request`. Upstream member-production failures remain in layered counts and make results `partial` or `failed`, never “no risk.”

## 4. Worker and compatibility

`fp-ir-worker` is an isolated C++20 process pinned to LLVM reader `21.1.8`, reader contract `1.0`, extractor contract `1.1`, and worker protocol `1.1`. Python probes `--version-json` before reading BC and rejects any mismatch, without falling back to host PATH LLVM.

The worker emits `LLVMFloatingPointFactBundle@1.1`, covering floating-point scalar/vector instructions, conversions, comparisons, calls/intrinsics, fast-math flags, target triples, data layouts, and debug locations. Facts have stable IDs and semantic digests, ordered by deterministic module/function/basic-block/instruction order. Input protocol is `1.1`; the version probe exposes tool, LLVM, reader, extractor, and worker-protocol versions. Any mismatch fails before BC reads.

At the Python boundary, debug paths become project-relative POSIX paths. Outside-project locations retain only the filename and add `debug_location_outside_project` unknown; absolute materialization roots do not enter default output. Every IR bundle exposes fact-budget usage and truncation frontiers. Explicit budgets cover wall time, CPU, address space, stdout/stderr, per-member/total BC bytes, IR facts, and evidence candidates. Exceeded budgets cannot imply “no additional floating-point behavior.”

## 5. Evidence and interpretation

Source facts, IR facts, and evidence are separate layers and never overwrite each other:

- Sidecars produce `explicit-sidecar`/`exact` evidence only after artifact/context, source/IR bundle digests, and both endpoint fact IDs validate.
- Derived bindings require matching context, stable function/symbol identity, structured debug/inline and AST spelling/expansion positions, and compatible operation kinds; they yield `derived-debug`/`strong` evidence.
- Function names, demangled text, or source-string similarity alone never create bindings.
- Multiple candidates enter `ambiguities`; unmatched facts retain their IDs and produce bilingual diagnostics.

With `source_mapping=required`, every unmatched IR fact is a blocking unknown, making the result at least `partial`. `best-effort` emits warnings but still preserves the unmatched set. Core rules use typed binding evidence references. `x87-excess-precision` and `fma-contraction` return unknown when required IR or reliable bindings are absent, not a no-match result. `unsafe-fp-optimization` checks effective options against build-faithful IR fast-math flags and also returns unknown on conflicts.

## 6. Troubleshooting

| Diagnostic family | Action |
|---|---|
| `artifact_manifest_*` | Obtain a terminal manifest again and pin its new SHA-256 |
| `artifact_*_mismatch` | Check source revision, compilation database, profiles, and upstream publication records |
| `bitcode_*` | Republish the member; never overwrite a published artifact set in place |
| `ir_worker_version_mismatch` | Rebuild the worker in the repository-pinned container |
| `ir_worker_failed` | Check LLVM 21 BC compatibility and verifier/reader errors |
| `source_mapping_incomplete` | Add debug information or an upstream binding sidecar |

Output publishes through same-directory temporary files, `fsync`, and atomic replacement. Failure/interruption cannot leave a target file that appears complete.

Result V2 analysis/artifacts extensions expose `planned/completed/failed/unknown` separately for artifact, source, IR, and evidence layers. They retain the manifest SHA-256 and source/IR/evidence bundle digest lists without mutable local-path references. If shared BC was requested and all required IR members fail, overall status is `failed`; `partial` requires some successful members.

## 7. Backend validation stages and project TU denominator

Before delivery to the scanner, the backend validates identity using the manifest's original schema representation. Schema 2.0 has no `dialect/standard_source/standard_option`; the current Java model must not inject nulls. Schema 2.1 requires these explicit fields and language-context validation. Failure stages are manifest parse/schema/identity, bundle layout, member integrity, source/compile binding, materialization, or LLVM worker, with stable bilingual reasons and sanitized summaries.

Coverage uses unique project C/C++ TUs, not raw compilation-database row counts or the maximum manifest planned count. Record raw commands, C/C++ candidates, project TUs, produced, failed, missing, and excluded separately. CMake CompilerId/ABI probes, TryCompile, linking, archiving, other languages, and duplicate contexts do not enter project coverage. Generated source not proven to be a build probe remains a project candidate or is explicitly classified; location under a build directory alone is not an exclusion reason.
