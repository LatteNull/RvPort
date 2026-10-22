# Testing and coverage scope

English | [简体中文](测试与覆盖率范围.md)

All tests, dependency installation, compilation, and code generation run in Docker. This document distinguishes measurement scope from acceptance status; checks that have not run must not be reported as passing.

## Project-owned executable code

| Scope | Included code | Tests and gates |
|---|---|---|
| Backend Java | Project-owned classes in `backend/src/main/java` | Maven `clean verify`; JaCoCo requires at least 90% line and branch coverage overall and for each package |
| Backend Python | The two scripts in `backend/src/main/resources/analysis` and `bitcode`, including unloaded source | `src/test/python`; coverage.py JSON requires at least 90% lines and branches overall and for each script |
| KB Scanner | Python source in `kb_scanner`, `scripts`, and `tools`, including unloaded files | `tests/unit` and existing domain-specific module gates; overall and affected modules must separately reach 90% lines and branches |
| Floating-point tool, Python | All Python source in `src/floating_point_precision_scanner`, including quality-check code | `make coverage`; coverage.py and `coverage_gate` check overall and affected modules |
| Floating-point tool, C++ | Project-owned implementation in `src/cpp`; current translation units are `ir_facts.cpp` and `ir_worker.cpp` | `make cpp-coverage`, GoogleTest/CTest, and llvm-cov; at least 90% lines and branches |
| Memory-order tool | Recursive enumeration of `python/**/*.py` and owned C/C++ source and executable headers in `src` | `memory_order_analyzer.quality`; at least 90% lines and branches for Python, C++, the weighted total, and every module; separate unit and integration profiles |
| Frontend | Executable TS/TSX in `src` and owned `scripts` | Coverage acceptance is currently deferred by project decision; lint, type checking, ordinary unit tests, and production builds must still pass |

The latest complete KB Scanner unit run in Docker on October 21, 2026 passed 855 tests and included all 190 project-owned Python files, including unloaded source. Overall coverage was 98.772% lines and 96.211% branches. This update corrected the current knowledge manifest digest chain and added tests for invalid manifests, missing or mismatched references, source identity and semantic validation, and symlink path escapes. The relevant loader, `knowledge/provider.py`, reached 100% line and branch coverage. These figures apply only to that KB unit run; they do not establish renewed acceptance of other modules or later changes.

## Exclusions and separate validation

- Generated jOOQ types come from the database schema and generator, and are excluded from the owned Java business-logic denominator. Empty-database initialization, repeated migrations, complete code generation, and compilation are validated separately.
- Unit-test code, test runners, and pure input fixtures are excluded from production-source denominators. Owned quality gates, tools, and helper scripts called by production code remain in scope.
- Unimplemented Python `Protocol` declarations and static `TYPE_CHECKING` imports contain no runtime business logic. Do not exclude exception paths to increase coverage. The previous KB metadata runtime-validation exclusion has been removed.
- LLVM, GoogleTest, npm/Python/Java dependencies, and upstream MinIO source are third-party implementations. They are excluded from owned-code coverage, but must still pass image build and runtime validation.
- The memory-order tool excludes only recorded, checksummed declaration headers without executable content. The quality entry point reevaluates changed files. The early Clang 18 experimental collector is no longer part of the delivered executable code.
- Dockerfiles, Compose, SQL, build descriptions, and Nginx configuration are checked through configuration parsing, actual builds, empty-database migrations, and full startup. These checks do not replace language unit tests.
- Two image directories and shell entry points used only for early SSH integration have been removed. The KB performance-container PowerShell launcher is a test runner with offline command-contract checks; it is outside production-source coverage. No PowerShell line/branch coverage report exists, so no coverage compliance is claimed for it.

## Reports and aggregation

Local `.migration-reports/` holds JaCoCo XML, coverage.py JSON, llvm-cov JSON, memory-order combined reports, and test logs. This directory, real configuration, image artifacts, and temporary acceptance scripts are excluded from the public repository.

For cross-language results, add covered and total counts before calculating a percentage; do not average percentages. Preserve independent gates for each language and affected module. Do not omit unvalidated scopes and claim that the whole repository meets the threshold. Regular API runtime checks, documentation checks, OpenSpec validation, and complete Compose startup are recorded separately and do not add unit-test coverage.
