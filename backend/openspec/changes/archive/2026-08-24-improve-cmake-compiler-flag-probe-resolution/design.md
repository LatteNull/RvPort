## Context

依赖分析目前已经基于 x86 构建事实提取工具、链接库、include、define、ELF 和目标环境能力。上一轮实现中，为了降低 CMake 项目产生的 `FLAG_SUPPORTED_*` 噪声，后端把这类宏按命名前缀归为 `compiler_flag_probe`。

这个规则存在误判风险。`FLAG_SUPPORTED_*` 不是 CMake 标准，也不是编译器内置宏；它通常来自项目 CMake 脚本中 `check_c_compiler_flag()` 或类似调用的结果变量。正确的判断依据应该是 CMake 脚本里变量名与真实 compiler flag 的绑定关系，而不是变量名格式。

## Goals / Non-Goals

**Goals:**

- 从多层级 CMake 脚本中解析 compiler flag 检测调用，建立 `variable -> flag` 动态映射。
- 使用该映射解释 `compile_commands.json` 和 `strace execve` 中出现的 `-D<variable>`。
- 移除“只要以 `FLAG_SUPPORTED_` 开头就判定为 compiler flag probe”的强规则，避免误判项目自定义宏。
- 在依赖结果 evidence 中保留可审计的来源文件、语言、真实 flag、解析来源和置信度。
- 保持没有 CMake 映射时的保守行为：证据不足则人工确认，不伪造成目标已满足。

**Non-Goals:**

- 不实现完整 CMake 解释器，不展开复杂变量、函数、宏或 generator expression。
- 不修改前端页面。
- 不为每个项目命名习惯维护硬编码宏前缀白名单。
- 不改变现有依赖分析 API 路径和数据库结构，除非实现中发现 evidence 字段无法表达。

## Decisions

### 1. 构建 wrapper 负责输出 CMake flag probe 映射

构建 wrapper 在构建完成后扫描源码树和构建目录中的 CMake 文件，输出结构化观测：

```text
RVPORT_OBSERVATION cmakeCompilerFlagProbe FLAG_SUPPORTED_fstackprotectorstrong    language=C    flag=-fstack-protector-strong    file=cmake/CompilerChecks.cmake
```

这样依赖分析只消费构建事实，不需要重新访问远端目录。该模式和现有 `compileDatabase`、`execveTool`、`compilerBuiltinMacros` 一致。

### 2. 扫描多层级 CMake 文件

扫描范围包括：

- `**/CMakeLists.txt`
- `**/*.cmake`
- 常见 `cmake/` 子目录中的脚本

排除 `.git`、构建产物中的第三方缓存目录和明显无关目录。扫描深度沿用现有构建事实采集策略，但实现应支持配置或较高默认值，避免漏掉子模块中的 `CMakeLists.txt`。

### 3. 使用轻量 tokenizer 解析 CMake 调用

不能用单行正则直接匹配，因为 CMake 调用可能跨行：

```cmake
check_c_compiler_flag(
  "-fstack-protector-strong"
  FLAG_SUPPORTED_fstackprotectorstrong
)
```

实现采用轻量 tokenizer：

- 去掉注释。
- 识别函数名和括号块。
- 支持双引号、单引号、多行和空白。
- 暂不展开 `${VAR}`、函数封装和 generator expression；这类输出 `unresolved=true` 或跳过，并记录 warning。

首批支持：

- `check_c_compiler_flag(<flag> <variable>)`
- `check_cxx_compiler_flag(<flag> <variable>)`
- `check_compiler_flag(<language> <flag> <variable>)`

### 4. 依赖分析优先使用动态映射

当 `compile_commands.json` 或 `strace execve` 中出现 define：

- 如果 define 命中 `cmakeCompilerFlagProbe.variable`：
  - `macroKind=compiler_flag_probe`
  - `compilerFlag=<flag>`
  - `probeSource=cmake_check_compiler_flag`
  - `probeFile=<file>`
  - `probeLanguage=<language>`
  - `targetMatchStatus=TARGET_INSTALLED`
  - `riskLevel=LOW`
- 如果 define 命中编译器实际内置宏采集：
  - 继续归类为 `compiler_builtin`
- 如果未命中任何动态映射或内置宏：
  - 归类为 `project_or_build_custom`
  - 不再仅凭 `FLAG_SUPPORTED_` 前缀认定为 `compiler_flag_probe`

保留很小范围的 fallback 可选，但如果启用，必须明确 `confidence=LOW` 且 `probeSource=heuristic_prefix_fallback`，不得覆盖动态映射判断。

## Risks / Trade-offs

- [Risk] CMake 语法非常灵活，轻量 tokenizer 无法覆盖所有函数封装和变量展开。  
  Mitigation: 只对直接 `check_*_compiler_flag` 调用给高置信度；其他情况保持人工确认，后续按真实项目扩展。

- [Risk] 扫描过深可能增加构建后处理时间。  
  Mitigation: 排除 `.git`、构建缓存和依赖下载目录；单文件大小和总文件数可设置上限，但不得影响用户构建结果。

- [Risk] 构建目录和源码目录都可能存在 CMake 文件，重复映射可能冲突。  
  Mitigation: 以变量名为 key 聚合，若同一变量对应多个不同 flag，结果降级为人工确认并保存冲突 evidence。

- [Risk] 旧结果中的 `FLAG_SUPPORTED_*` 仍然按旧规则展示。  
  Mitigation: 历史结果不重写；新任务使用新规则。前端可根据 evidence 的 `probeSource` 区分新旧结果。

## Migration Plan

1. 在构建 wrapper 中增加 CMake flag probe 扫描输出。
2. 在依赖分析器中新增 `cmakeCompilerFlagProbe` 解析和 define 分类映射。
3. 移除或降级 `FLAG_SUPPORTED_` 前缀强判断。
4. 补充单元测试覆盖多行 CMake 调用、子目录 CMake 文件、冲突变量、未命中前缀宏。
5. 使用 cJSON 真实流程验证 `FLAG_SUPPORTED_fstackprotectorstrong` 能映射到 `-fstack-protector-strong`。

Rollback 策略：该变更只影响新依赖分析任务的分类和 evidence。若出现误判，可关闭 CMake probe 解析并恢复为保守的 `project_or_build_custom` 分类，不影响构建执行。

## Open Questions

- 是否需要在后续支持 `try_compile()` 或项目自定义 CMake wrapper 函数，目前先不做。
- 是否需要把 CMake probe 映射写入 `build_runs.build_facts`，目前可先通过任务日志 evidence 传递。
