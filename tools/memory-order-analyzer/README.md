# Memory Order Analyzer

English | [简体中文](README.zh-CN.md)

RvPort's C/C++ memory-order analysis tool. It uses pinned LLVM/Clang 21.1.8 to consume external raw BC read-only, combining optional AST evidence, explicit Scopes, thread entries, and demand-driven function analysis to report risks, source candidates, and discharged cases within bounded models.

## Entry point

The backend uses the single project entry point `analyze-project`. See [unified project analysis](doc/UNIFIED_PROJECT_ANALYSIS.md) for requests, DAGs, caching/recovery, and cancellation. Upstream produces BC. The scanner does not compile, link, run build scripts, use the network/SSH, or execute analyzed programs. `compile_commands.json` only assists source alignment and cannot replace bundle Scope.

| Project exit code | Meaning |
|---|---|
| 0 | No Finding within the supported model; not proof of thread safety |
| 3 | A risk exists in a complete bounded model |
| 2 | Partial, unknown, or cancelled; incompleteness remains even when risks exist |
| 1 | Request failure or failure of all Scopes |

AST-only analysis produces only `source-candidate` and nonempty breaks; it cannot independently establish formal risks, discharge, or safety. P1–P3/R1–R3 retain `safety=not_evaluated`; risk layers retain `not_established`. Local object, synchronization, and publication proofs are not general HB, data-race detection, or whole-program safety proofs.

## Development and documentation

Runtime and build processes read resources from these purpose-specific directories:

| Directory | Purpose |
|---|---|
| `protocols/` | 17 protocol definitions: versions, data types, analysis budgets, and worker communication |
| `models/` | Thread-entry models for standard-library entries and lower-level wrappers |
| `config/` | Toolchain version, source, and digest locks |
| `schemas/` | Request, fact, and result validation |
| `cpp-thread-profiles/`, `cpp-raii-profiles/` | C++ standard-library thread and lock recognition profiles |

- [Documentation index](doc/README.md): inputs, semantics, threads, demand analysis, and result contracts.
- [Docker development and quality checks](doc/development.md): isolated images, read-only source, dedicated output volumes, and 90% line/branch gates.
- [Result contract](doc/MEMORY_ORDER_FINDING_SCHEMA.md#doc-memory-order-finding-schema): bilingual conclusions, evidence graphs, source snapshots, and breaks.

Production integration builds through the root `backend/Dockerfile`; standalone development uses this tool's `Dockerfile.dev`. All builds and tests run in Docker.

Historical P5 `validate-and-scale-analysis` completed implementation and quality acceptance, synchronized main specs, and was archived. That validation remains distinct from whole-program safety.
