## ADDED Requirements

### Requirement: 依赖分析必须基于 CMake 检测调用识别 compiler flag probe
依赖分析运行时 SHALL 使用 CMake 脚本中的 compiler flag 检测调用建立 define 变量和真实 compiler flag 的动态映射，并 SHALL 基于该映射识别 compiler flag probe。

#### Scenario: 解析 CMake C 编译器参数检测
- **WHEN** 源码树或构建目录中的 CMake 文件包含 `check_c_compiler_flag(<flag> <variable>)`
- **THEN** 构建事实采集 SHALL 输出 `<variable>` 到 `<flag>` 的映射
- **AND** 映射 SHALL 标记语言为 `C`
- **AND** 映射 SHALL 记录来源 CMake 文件的受控相对路径

#### Scenario: 解析 CMake CXX 编译器参数检测
- **WHEN** 源码树或构建目录中的 CMake 文件包含 `check_cxx_compiler_flag(<flag> <variable>)`
- **THEN** 构建事实采集 SHALL 输出 `<variable>` 到 `<flag>` 的映射
- **AND** 映射 SHALL 标记语言为 `CXX`
- **AND** 映射 SHALL 支持跨行函数调用

#### Scenario: 解析通用 CMake 编译器参数检测
- **WHEN** CMake 文件包含 `check_compiler_flag(<language> <flag> <variable>)`
- **THEN** 构建事实采集 SHALL 输出 `<variable>`、`<flag>` 和 `<language>` 的映射
- **AND** 无法静态解析的参数 SHALL 记录为低置信度或 unresolved evidence

#### Scenario: 多层级 CMake 脚本扫描
- **WHEN** 项目包含根目录、子目录或 `cmake/` 目录下的 `CMakeLists.txt` 或 `*.cmake`
- **THEN** 构建事实采集 SHALL 扫描这些 CMake 文件
- **AND** 扫描 SHALL 排除 `.git` 和明显无关的缓存目录
- **AND** 子目录 CMake 文件中的 compiler flag probe MUST NOT 被根目录扫描遗漏

#### Scenario: 使用动态映射解释 define
- **WHEN** `compile_commands.json` 或 `strace execve` 中出现 `-D<variable>`
- **AND** `<variable>` 命中 CMake compiler flag probe 映射
- **THEN** 依赖分析结果 SHALL 将该 define 标记为 `compiler_flag_probe`
- **AND** evidence SHALL 包含真实 `compilerFlag`、`probeSource=cmake_check_compiler_flag`、`probeFile` 和 `probeLanguage`
- **AND** 结果 SHALL 使用 `TARGET_INSTALLED` 和 `LOW` 风险表达该项通常属于当前编译器能力

#### Scenario: 不以 FLAG_SUPPORTED 前缀作为强判定
- **WHEN** `compile_commands.json` 或 `strace execve` 中出现以 `FLAG_SUPPORTED_` 开头的 define
- **AND** 该 define 未命中 CMake compiler flag probe 映射
- **THEN** 依赖分析 MUST NOT 仅凭前缀将其标记为 `compiler_flag_probe`
- **AND** 该 define SHALL 按编译器内置宏采集或项目/构建自定义宏规则继续分类

#### Scenario: CMake probe 映射冲突
- **WHEN** 同一 CMake 变量名映射到多个不同 compiler flag
- **THEN** 依赖分析 SHALL 将该变量对应结果降级为 `MANUAL_CONFIRM_REQUIRED`
- **AND** evidence SHALL 保存冲突的候选 flag 和来源文件
