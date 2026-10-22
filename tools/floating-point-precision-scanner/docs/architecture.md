# Floating-point scanner architecture and maintenance

English | [简体中文](architecture.zh-CN.md)

## Inputs and processing

`Scan Request → profile/input validation → C/C++ TU planning → canonical AST facts → optional shared BC/IR facts → AST↔IR evidence → rule assessment → suppression → V2 result projection`.

Only C11, C17, C++17, and C++20 are planned. Clang/LLVM is pinned to 21.1.8. Other languages receive bilingual `unsupported_language` diagnostics and are excluded from the C/C++ denominator. Choose either a compilation database or explicit TUs and pin source/target profiles.

BC comes from terminal upstream artifacts; the scanner never generates it. Path, digest, version, source-revision, or member-identity failures explicitly degrade or fail analysis. Never align files by matching names. Rules consume only canonical facts, versioned profiles, evidence, and build contexts, not Clang internal objects.

## Rules and versions

The [README](../README.md) lists all ten rules and their evidence boundaries. Request schemas 1.3–1.4 default to ten rules; 1.0–1.2 retain four. `rules.enabled=[]` means factsOnly. Request versions and result `schemaVersion: 2.0` are separate contracts.

AST candidates, IR facts, and proven differences remain distinct. Unrecoverable types, indirect calls, unknown libm/runtime, failures, and exhausted budgets remain in unknown/failed denominators. Zero Findings does not prove numerical equivalence. The tool does not run analyzed programs, invent business tolerances, or replace real porting tests.

## Results and maintenance

Findings contain facts, conclusions, occurrences, and evidenceChain. Stable identity does not depend on absolute workspace paths. See [evidence steps](evidence-step-descriptions.md) for bilingual descriptions. Suppressions require a rule, relative path, and reason. `expires_on` requires explicit `policy_as_of`; suppressions remain valid on their expiration date, and expired Findings become visible again.

Caches hold only facts/evidence, never final findings or suppressions. Version or source-location semantic changes must produce ordinary cache misses, not in-place field upgrades. See [caching](analysis-cache.md) and [shared bitcode](shared-bitcode-consumer.md).

## Docker validation

Run `make verify` in the README's development container for lint, typing, full Python unit/contract coverage, human-oracle validation, and C++ coverage. `make verify-release` adds benchmarks. Run `make integration` separately for real Clang integration; it cannot count as unit coverage.

Overall and affected-module line/branch coverage must each reach 90%. Python scope includes unloaded source; C++ scope includes all project-owned worker implementation. Reports are in the container's `artifacts/coverage/` directory.
