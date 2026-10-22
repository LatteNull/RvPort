# Dependencies and licenses

English | [简体中文](dependency-licenses.zh-CN.md)

| Dependency | Pinned version | License | Purpose |
|---|---|---|---|
| Python | 3.11+ | PSF-2.0 | Runtime |
| Clang/LLVM | 21.1.8 | Apache-2.0 WITH LLVM-exception | C/C++ frontend |
| jsonschema | 4.23.0 | MIT | Draft 2020-12 contract validation |
| pytest | 8.3.5 | MIT | Unit/integration tests |
| coverage.py | 7.6.12 | Apache-2.0 | Line and branch coverage |
| Ruff | 0.9.10 | MIT | Formatting and static checks |
| mypy | 1.15.0 | MIT | Type checking |
| types-jsonschema | 4.23.0.20250516 | Apache-2.0 | jsonschema type stubs |
| CMake | 3.28+ | BSD-3-Clause | C++ worker build |
| Ninja | 1.11+ | Apache-2.0 | C++ build executor |
| GoogleTest | 1.14 | BSD-3-Clause | C++ unit tests |
| zlib | Ubuntu 24.04 repository version | Zlib | LLVM Support link dependency |
| zstd | Ubuntu 24.04 repository version | BSD-3-Clause/GPL-2.0 | LLVM Support link dependency |
| libedit | Ubuntu 24.04 repository version | BSD-3-Clause | LLVM Support link dependency |
| libcurl | Ubuntu 24.04 repository version | curl | LLVM Support link dependency |

`toolchain.lock.json` and requirements lock files are authoritative. Container builds must verify the LLVM signing-key digest. Dependency upgrades must update this table, lock files, and validation evidence together.
