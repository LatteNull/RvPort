# C/C++ floating-point precision scanner

English | [简体中文](README.zh-CN.md)

This module provides RvPort's C/C++ floating-point fact-scanning infrastructure. It supports C11, C17, C++17, and C++20, reads `compile_commands.json` or explicit translation units, and uses pinned Clang 21.1.8 to produce versioned canonical floating-point facts.

Optional `bitcode_artifact_set` input consumes immutable LLVM 21.1.8 BC already published by the x86 build pipeline, read-only. The scanner neither generates BC nor polls artifacts while they are being generated. Orchestration must start scanning after the artifact reaches a terminal state. An isolated `fp-ir-worker` converts BC into canonical IR facts, which combine with AST facts in a separate evidence layer.

Request schemas 1.3–1.4 enable ten porting rules by default: the four core architecture rules plus `floating-environment`, `mixed-precision-conversion`, `fragile-fp-comparison`, `reduction-reassociation`, `math-library-variance`, and `architecture-specific-fp-api`. Schemas 1.0–1.2 retain the original four-rule default when `rules` is absent, preventing semantic drift after upgrades. Rules consume normalized AST facts, shared LLVM BC facts, AST↔IR evidence, versioned profiles, and optional build contexts; they do not depend directly on Clang/LLVM internal objects.

Omitting `rules` enables the schema-specific default. `rules.enabled` selects a subset of stable codes; explicit `{"enabled": []}` retains `factsOnly` mode. Unknown, skipped, and failed assessments remain in the denominator. Empty findings do not imply no floating-point risk.

## Installation and environment

Build the isolated development image from PowerShell at the repository root. Install dependencies, compile, and validate inside Docker without creating a host virtual environment:

```powershell
docker build -f tools/floating-point-precision-scanner/Dockerfile.dev -t rvport-fp-dev:local tools/floating-point-precision-scanner
docker run --rm --memory=8g --cpus=2 rvport-fp-dev:local fp-precision-scanner version
```

Real frontend validation uses the Linux/amd64 and Clang/LLVM 21.1.8 environment pinned by `Dockerfile.dev`. If the pinned compiler is unavailable, the scanner does not fall back to another version on PATH.

## CLI

Run these commands inside the development container with `/workspace` as the working directory. Mount external source/request inputs read-only and use a separate writable output directory.

```text
fp-precision-scanner version
fp-precision-scanner profiles list
fp-precision-scanner profiles show x86_64-linux-gnu-clang21@1.0
fp-precision-scanner validate-request --request request.json
fp-precision-scanner scan --request request.json --output result.json --clang /usr/lib/llvm-21/bin/clang-21 --ir-worker /workspace/build/fp-ir-worker
```

Request/result examples are in `examples/`. Requests explicitly choose source/target profiles and exactly one of `input.compile_commands` or `input.translation_units`. Mixed projects plan C/C++ only. Other languages are excluded with bilingual `unsupported_language` diagnostics and do not enter the scan denominator.

Shared BC still requires a compilation database or explicit translation units for the same source revision. Requests pin the manifest SHA-256; the consumer then validates source revision, compilation-input digest, member identity, profile, size, and SHA-256. Only `source-preserving` is required by default; request `build-faithful` explicitly. See [shared bitcode consumption](docs/shared-bitcode-consumer.md).

## Core rules

| Rule | Main inputs | Focus |
|---|---|---|
| `long-double-abi` | AST boundary facts, source/target profiles | Public ABI, varargs, record and persisted-layout differences |
| `x87-excess-precision` | AST operation chains, effective options, IR/evidence | Extended x87 intermediate precision and storage rounding boundaries |
| `fma-contraction` | AST multiply-add candidates, build-faithful IR/evidence | Single versus double rounding for explicit FMA or contractible multiply-add |
| `unsafe-fp-optimization` | Effective options, IR fast-math flags | Relaxed NaN, Inf, ±0, reassociation, approximation, errno, and exception semantics |

## Expression-risk rules

| Rule | Main inputs | Conclusion boundary |
|---|---|---|
| `floating-environment` | fenv pragmas/APIs, function summaries, effective options, profiles/IR | Indirect/external calls or summary-budget frontiers return `unknown` |
| `mixed-precision-conversion` | Canonical source/target types, constants, integer widths, storage/use | Explicit casts normally indicate intent; unrecoverable types/ranges return `unknown` |
| `fragile-fp-comparison` | Operand provenance, NaN/zero/epsilon forms, control-flow use | Definite NaN error patterns; exact-comparison/epsilon risks are heuristic and do not invent business tolerances |
| `reduction-reassociation` | Loop recurrence, compensation algorithms, IR phi/vector reductions and flags | AST-only candidates are heuristic; reliable IR lowering can provide definite evidence |
| `math-library-variance` | Resolved math declarations, argument domains, source/target build contexts | Reports verified errno/exception/special-value differences only; unpinned libm returns `unknown` |
| `architecture-specific-fp-api` | Resolved declaration/builtin/header, target features, active guards | Names alone cannot trigger findings; a clearly portable target branch is not reported |

Schema 1.3 can bind separate `FloatingPointBuildContext@1.0` contexts. Context fingerprints exclude local sysroot and materialization absolute paths. Unpinned libm, runtime, or target features must explicitly remain `unknown`. Request suppressions require a stable rule code, repository-relative POSIX path, optional complete line range, and nonempty reason. Source comments use `fp-precision-scanner: ignore <code> -- <reason>`. Suppressions apply after Finding IDs are generated; audits enter `org.rvport.floating-point-scanner.suppressions` and count toward `summary.suppressed`.

Schema 1.4 adds unified runtime budgets, canonical intermediate caches, and suppression lifecycles. A suppression with `expires_on` requires explicit `policy_as_of`; it remains valid on the expiration date, and expired findings remain visible. Only source facts, LLVM IR facts, and AST↔IR evidence are cached. Final findings, assessments, suppressions, and results are always recomputed. See [analysis caches](docs/analysis-cache.md) and [validation corpus](docs/validation.md#doc-validation-corpus).

The LLVM worker propagates bounded resolvable same-module direct-call environment summaries to callers, retaining callees, call sites, propagation depth, and stable frontiers. `max_function_summary_depth`, `max_ir_summary_call_edges`, and `max_ir_use_chain` separately limit summary depth, call edges, and IR use chains. Recursion, indirect/external calls, and truncation conservatively produce `unknown_effect`.

Rules requiring build-faithful IR return unknown assessments and bilingual diagnostics when artifacts are absent, bindings ambiguous, or profile fields unknown. High findings require human confirmation; findings alone do not change a successful exit code.

## Status and exit codes

Results publish only `schemaVersion: "2.0"`, with top-level `scan/project/summary/findings/diagnostics/extensions` and camelCase public fields. There is no legacy result serializer, dual write, converter, or result-version selector. Each Finding uses `fact/conclusion/occurrences/primaryOccurrenceId/evidenceChain` for facts, conclusions, locations, and resolvable evidence. AST/IR/binding/profile/build-context/assessment audit objects resolve into analysis extensions through typed references with producer, schema, and digest. Raw facts/IR/evidence are not unrestricted top-level arrays.

| Status | Exit | Meaning |
|---|---:|---|
| `complete` | 0 | `scan.status=complete`; all planned facts, evidence, and rule assessments completed; findings may exist |
| `invalid_request` | 2 | Invalid schema, path, profile, or input selection |
| `failed` | 3 | No translation unit produced usable results |
| `partial` | 4 | Usable results exist alongside failures or blocking unknowns |
| `internal_error` | 5 | Unclassified internal error or unsafe result publication |

## Determinism and safety

- Stable IDs and semantic digests use versions, repository-relative POSIX paths, semantic positions, and payloads only.
- Timestamps, PIDs, temporary directories, absolute workspaces, and concurrent completion order do not enter digests.
- JSON collections use fixed key ordering. Files publish through same-directory temporary files, fsync, and atomic replacement.
- Default diagnostics provide Chinese and English without credentials, environment-variable values, or absolute paths outside the project root.
- Shared BC results expose separate artifact/source/IR/evidence denominators and immutable digests. If every required IR member fails, the overall result is `failed` even when AST facts are available.

## Validation

Run from the repository root using the development image built above. Keep coverage reports in a dedicated container and export them before removing it:

```powershell
docker run --name rvport-fp-unit --memory=8g --cpus=2 --network=none -e CMAKE_BUILD_PARALLEL_LEVEL=2 rvport-fp-dev:local make coverage cpp-coverage
docker cp rvport-fp-unit:/workspace/artifacts/coverage ./fp-coverage
docker rm rvport-fp-unit
```

Full release checks also include lint, typing, corpus, and performance baselines through `make verify-release` in the same image. Record these separately from ordinary unit tests.

Coverage explicitly includes all project-owned source under `src/floating_point_precision_scanner`, including unloaded files. Overall and affected-module line and branch coverage must each reach 90%. The only configured exclusion is the static-import branch `if TYPE_CHECKING:`; business logic is not excluded. The LLVM worker uses source-based coverage with line/branch gates over all project source in `src/cpp`. Third-party LLVM, GTest, and generated build files are excluded.

See [validation corpus and performance baselines](docs/validation.md#doc-benchmark) for reviewed corpus and fixed S/M/L benchmark maintenance and acceptance.

## Documentation

The [documentation index](docs/README.md) covers architecture, input contracts, caching, validation, and dependencies. Historical stage status is recorded in [OpenSpec](openspec).
