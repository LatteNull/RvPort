# Project collaboration conventions

English | [简体中文](AGENTS.md)

## Execution environment

- Compilation, testing, coverage measurement, dependency installation, and code generation run in Docker. The host only edits files, invokes Docker, and reads exported reports.
- Use dedicated test containers, networks, and volumes. Do not connect tests to existing deployment databases or real SSH environments.
- Build and test modules sequentially, with suitable CPU, memory, and compilation-concurrency limits. Keep caches and outputs in containers or dedicated volumes.
- See `docs/development.md` and each tool's README. Old images or reports cannot replace validation of current source.

## Code and validation

- Add and maintain unit tests for new, modified, or reused owned code, covering normal behavior, boundaries, and error paths.
- Require at least 90% line coverage overall and for affected modules, plus 90% branches where supported. Preserve stricter existing gates.
- Frontend coverage acceptance is temporarily deferred by project decision; lint, type checks, ordinary unit tests, and production builds remain required. Backend and tools retain the coverage requirements above.
- Final acceptance requires a complete Compose build from this root and a single `docker compose up -d --wait` starting all default services. Check health, logs, and representative business flows.
- Include unloaded owned executable source. Explain exclusions for third-party and generated code; do not narrow scope to evade gates.
- Integration tests, builds, and static checks do not replace unit tests. Report actual commands, results, line/branch coverage, scope, and report paths. State failures, missing execution, and environmental blockers accurately.
- Documentation-only changes require content and link checks, not invented code-coverage results. Report large historical testing gaps and confirm scope before unrelated refactoring.

## Documentation and specifications

- Chinese documentation remains available alongside the requested English editions. Keep code identifiers and proper nouns unchanged where appropriate. User-facing business explanations retain Chinese and English fields as required by their protocols.
- Product naming is RvPort; engineering identifiers use `rvport`, and environment variables use the `RVPORT_` prefix.
- Root, backend, frontend, and tool OpenSpec stores are independent. Confirm the working root and do not automatically archive unfinished changes.
- Phase handoffs state the completed phase, next phase, and an actual usable command. Historical checkboxes and validation claims are not current acceptance results.
- CI, E2E, real-environment test support, and retired features are outside the current project scope. Restoring or adding them requires an explicit new requirement.

Real `.env` files, credentials, private keys, runtime data, logs, and `.migration-reports/` are not public source.
