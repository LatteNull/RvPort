# 依赖与许可证清单

[English](dependency-licenses.md) | 简体中文

| 依赖 | 固定版本 | 许可证 | 用途 |
|---|---:|---|---|
| Python | 3.11+ | PSF-2.0 | 运行时 |
| Clang/LLVM | 21.1.8 | Apache-2.0 WITH LLVM-exception | C/C++ 前端 |
| jsonschema | 4.23.0 | MIT | Draft 2020-12 协议校验 |
| pytest | 8.3.5 | MIT | 单元/集成测试 |
| coverage.py | 7.6.12 | Apache-2.0 | 行与分支覆盖率 |
| Ruff | 0.9.10 | MIT | 格式与静态检查 |
| mypy | 1.15.0 | MIT | 类型检查 |
| types-jsonschema | 4.23.0.20250516 | Apache-2.0 | jsonschema 类型声明 |
| CMake | 3.28+ | BSD-3-Clause | C++ worker 构建 |
| Ninja | 1.11+ | Apache-2.0 | C++ worker 构建执行器 |
| GoogleTest | 1.14 | BSD-3-Clause | C++ 单元测试 |
| zlib | Ubuntu 24.04 仓库版本 | Zlib | LLVM Support 链接依赖 |
| zstd | Ubuntu 24.04 仓库版本 | BSD-3-Clause/GPL-2.0 | LLVM Support 链接依赖 |
| libedit | Ubuntu 24.04 仓库版本 | BSD-3-Clause | LLVM Support 链接依赖 |
| libcurl | Ubuntu 24.04 仓库版本 | curl | LLVM Support 链接依赖 |

版本以 `toolchain.lock.json` 与 requirements lock 文件为准。容器构建必须验证 LLVM
签名密钥摘要；依赖升级必须同步更新本表、锁文件和验证证据。
