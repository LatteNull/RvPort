# RvPort

English | [简体中文](README.zh-CN.md)

RvPort supports assessment and implementation of migrations from x86 to RISC-V, including project and source management, execution environment registration, dependency and code risk analysis, build validation, and migration result management.

The backend uses Java 25, Spring Boot 4.1, PostgreSQL, Redis, and RabbitMQ. API nodes receive requests, while worker nodes execute asynchronous tasks. Object storage holds analysis artifacts. KB Scanner, the floating-point scanner, and the memory-order analyzer provide complementary analysis capabilities. The frontend uses React, TypeScript, and Vite.

## Getting started

See the [installation guide](docs/installation.md) for setup and operation, and the [development guide](docs/development.md) for development, builds, and tests. All compilation, code generation, and testing run in Docker. The host does not need Java, Maven, Python, or LLVM installed.

See [testing and coverage scope](docs/testing-and-coverage.md) for coverage requirements and the [frontend guide](frontend/README.md) for frontend development.

## Contributions and releases

- Use `Type: Message` with a `<type>: <English> / <中文>` subject and a bilingual English/Chinese body. Types are `feat`, `test`, `fix`, `refactor`, `ci`, `chconf`, and `docs`.
- AI-generated and human-written code follow the same code audit, PR review, and applicable validation requirements. Automated checks do not replace code review.
- `dev` integrates development; `master` is for releases. Fork upstream, clone locally, create a topic branch from upstream `dev`, push to your fork, and open a PR targeting upstream `dev`.
- Versions use four components, major.minor.bug fix.hotfix, such as `1.2.0.0`. Prereleases append a type and number, such as `1.2.0.0-rc1` or `1.2.0.0-rc2`.
- An agreed Roadmap leads to Issues with assignees. Link PRs to Issues and confirm closure after merging into `dev` and completing acceptance. Once the entire Roadmap is complete, merge `dev` into `master` through a release PR and publish.

See the [development guide's contribution and release policy](docs/development.md#contribution-and-release-policy) for type definitions, bilingual commit examples, and the complete workflow.

## Repository layout

| Directory or file | Purpose |
|---|---|
| `backend/` | API, workers, database migrations, generated jOOQ types, and unit tests |
| `tools/kb-scanner/` | Migration analysis based on rules, build context, and source evidence |
| `frontend/` | Web interface, build configuration, unit tests, and frontend OpenSpec |
| `tools/floating-point-precision-scanner/` | Floating-point migration risks and source evidence |
| `tools/memory-order-analyzer/` | Memory ordering, threads, and publication-pattern analysis |
| `docs/` | Installation, development, testing, and third-party provenance |
| `openspec/` and each subproject's `openspec/` | Specifications, active changes, and historical records |
| `docker-compose.yml` | Frontend, backend, and infrastructure orchestration |
| `.env.example` | Configuration template; contains no master key suitable for a real deployment |

Tool documentation: [KB Scanner](tools/kb-scanner/README.md), [floating-point scanner](tools/floating-point-precision-scanner/README.md), and [memory-order analyzer](tools/memory-order-analyzer/README.md). Backend reference: [API design](backend/docs/API_DESIGN.md) and [database design](backend/docs/DATABASE_DESIGN.md).

## Capability boundaries

Analysis depends on the language, compiler options, and availability of source code and bitcode. Interpret unknown, incomplete-evidence, and degraded results according to the relevant tool's protocol. An absence of reported risks does not prove program correctness or whole-program safety.

The complete tool environment uses Linux containers and pinned Clang/LLVM versions. Production images use an x86_64 toolchain. Prepare RISC-V target environments separately as described by the tools. The first build downloads toolchains and dependencies; its duration depends on network conditions.

## License and source

RvPort is licensed under [Apache License 2.0](LICENSE). The repository is [RvPort/RvPort](https://github.com/RvPort/RvPort). Third-party materials retain their own licenses; see [third-party notices](docs/third-party-notices.md).
