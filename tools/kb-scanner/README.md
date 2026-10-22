# KB Scanner

English | [简体中文](README.zh-CN.md)

A static knowledge scanner for porting C/C++ projects from x86 to RISC-V. It reads source code, an optional compilation database, existing build metadata, and a versioned knowledge bundle. It does not build or test the scanned project.

## Run with Docker

Run from the repository root:

```powershell
docker compose -f tools/kb-scanner/compose.test.yml build kb-scanner-test
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test -m kb_scanner --help
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test
```

Run the scan inside the development container, with read-only inputs and a separate writable output directory:

```sh
python -m kb_scanner scan --input /input/project --rules rulesets/riscv-porting --output /tmp/scan --format json,html
```

The default output schema is 2.0; select `--schema-version 1.0` explicitly for V1. The scanner publishes `scan-result.json`, `scan-report.html`, and `scan.log` together. A version-specific failure never silently falls back to another version. `--exclude` accepts comma-separated directory names; repeat `--exclude-path` to exclude exact project-relative directories.

## Interpret results

Each Finding contains its own fact, conclusion, occurrences, and evidence chain. Missing inputs, ambiguous relationships, and exhausted budgets retain `unknown`/`partial` states. Readiness covers static inputs only: `staticScopeOnly=true`, `compiled=false`, and `testsExecuted=false`. Zero blockers does not mean the port has compiled successfully.

## Documentation

- [Documentation index](docs/README.md)
- [Capabilities and limitations](docs/analysis-capabilities.md)
- [Result contract](docs/schema-v2-design.md)
- [Knowledge maintenance](docs/knowledge.md)
- [Development and quality checks](docs/development.md)

Designs and changes are recorded in [OpenSpec](openspec).
