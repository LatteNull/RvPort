## Why

当前依赖分析会把 `FLAG_SUPPORTED_*` 这类宏按命名前缀推断为编译器参数探测结果。这个规则对 cJSON 示例有效，但不可靠：该前缀不是 CMake 标准，也可能被项目用于其他目的，容易把项目自定义宏误判为编译器能力。

需要改为从 CMake 脚本中的 `check_*_compiler_flag` 调用建立变量到真实 compiler flag 的动态映射，再用该映射解释 `compile_commands.json` 或 `strace execve` 中出现的 `-D` define。

## What Changes

- 扫描源码树多层级 CMake 脚本，包括 `CMakeLists.txt`、`*.cmake` 和常见 `cmake/` 子目录脚本。
- 解析 `check_c_compiler_flag`、`check_cxx_compiler_flag` 和 `check_compiler_flag` 调用，建立 `variable -> flag/language/file` 映射。
- 依赖分析优先使用 CMake 动态映射判断 compiler flag probe，不再单纯因为 `FLAG_SUPPORTED_` 前缀直接判定。
- 对无法解析 flag 的变量保留 evidence，但降级为人工确认或项目/构建自定义宏，避免误报为已安装能力。
- 在依赖结果 evidence 中保存 `compilerFlag`、`probeSource`、`probeFile`、`probeLanguage` 和置信度来源，供前端审计。
- 补充真实 CMake 项目 E2E/验证，确认 `-fstack-protector`、`-fstack-protector-strong`、`-fvisibility=hidden` 等参数能从 CMake 检测调用中还原。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `dependency-analysis-runtime`: 修改 compiler flag probe 的判定规则，从命名前缀启发式改为 CMake 检测调用驱动的动态映射。
- `build-validation-runtime`: 构建事实采集需要输出 CMake compiler flag probe 映射，供依赖分析使用。
- `api-e2e-test-suite`: E2E 需要覆盖 CMake 多层级脚本中的 compiler flag probe 映射和误判防护。

## Impact

- 影响构建 wrapper 中的源码/CMake 脚本扫描逻辑。
- 影响依赖分析规则 `DependencyFactExtractor` 中 define 分类、evidence 和建议文案。
- 影响依赖分析 HTML/JSON 结果展示字段。
- 需要补充单元测试和真实 CMake 项目验证；不涉及前端实现，不改变现有 API 路径。
