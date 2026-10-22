# KB Scanner 依赖清单

[English](dependency-inventory.md) | 简体中文

具体安装版本以 `requirements/runtime.lock`、`requirements/test.lock` 和 Dockerfile 为准；依赖安装与验证均在 Docker 中进行。

## Runtime

| 组件 | 锁定版本 | 用途 | 许可证 |
|---|---:|---|---|
| Python | Ubuntu Noble 3.12 | 扫描器运行时 | PSF-2.0 |
| LLVM/Clang、libclang、Python binding | Ubuntu Noble `1:18.1.3-1ubuntu1` | 可选语义与预处理增强 | Apache-2.0 WITH LLVM-exception |
| tree-sitter | 0.26.0 | 容错语法前端 | MIT |
| tree-sitter-c | 0.24.2 | C grammar | MIT |
| tree-sitter-cpp | 0.23.4 | C++ grammar | MIT |
| tree-sitter-bash | 0.25.1 | 已生成 configure/config.sub 的静态语法分析 | MIT |
| tree-sitter-make | 1.1.1 | Makefile CST 与位置恢复 | MIT |
| NetworkX | 3.6.1 | 首选 GraphStore adapter | BSD-3-Clause |
| Pydantic | 2.13.5 | 输入/输出边界模型 | MIT |
| pathspec | 1.1.1 | Git 风格路径过滤候选 | MPL-2.0 |

`annotated-types`、`pydantic-core`、`typing-inspection` 和 `typing-extensions` 是 Pydantic 的锁定传递依赖，具体版本见 `requirements/runtime.lock`。

## Test-only

| 组件 | 锁定版本 | 用途 | 许可证 |
|---|---:|---|---|
| PyYAML | 6.0.3 | 仅供隔离 Legacy/YAML oracle；默认与 qualification 不导入 | MIT |
| jsonschema | 4.26.0 | `scan-result.json` 兼容契约验证 | MIT |
| specfile | 0.41.1 | 仅用于验证纯 ValueParser 的安全边界，不作为候选 runtime | MIT |

`attrs`、`jsonschema-specifications`、`referencing` 和 `rpds-py` 是 jsonschema 的锁定传递依赖；`rpm` 是 specfile 的锁定传递依赖。test lock 首先引用 runtime lock，因此测试依赖不能替换候选 runtime 版本。
