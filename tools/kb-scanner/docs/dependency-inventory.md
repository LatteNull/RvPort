# Dependency inventory

English | [简体中文](dependency-inventory.zh-CN.md)

## Runtime dependencies

| Dependency | Version/source | License | Purpose |
|---|---|---|---|
| Python | Ubuntu Noble 3.12 | PSF-2.0 | Runtime |
| LLVM/Clang, libclang, Python bindings | Noble `1:18.1.3-1ubuntu1` | Apache-2.0 with LLVM exception | Optional semantic and preprocessing enrichment |
| tree-sitter | 0.26.0 | MIT | Parsing runtime |
| tree-sitter-c | 0.24.2 | MIT | C grammar |
| tree-sitter-cpp | 0.23.4 | MIT | C++ grammar |
| tree-sitter-bash | 0.25.1 | MIT | Shell grammar |
| tree-sitter-make | 1.1.1 | MIT | Make grammar |
| networkx | 3.6.1 | BSD-3-Clause | Graph operations |
| pydantic | 2.13.5 | MIT | Typed contracts and validation |
| pathspec | 1.1.1 | MPL-2.0 | Path matching |

Pydantic's transitive dependencies, including `annotated-types`, `pydantic-core`, `typing-inspection`, and `typing-extensions`, are pinned in the runtime lock file.

## Test dependencies

| Dependency | Version | Purpose |
|---|---|---|
| PyYAML | 6.0.3 | Isolated legacy oracle; not imported by default qualification |
| jsonschema | 4.26.0 | V1/V2 contract validation |
| specfile | 0.41.1 | Pure `ValueParser` boundary checks only; not a runtime dependency; MIT license |

`attrs`, `jsonschema-specifications`, `referencing`, and `rpds-py` are jsonschema transitive dependencies. `rpm` is a specfile transitive dependency. The test lock includes the runtime lock and must not replace its versions.
