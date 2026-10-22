## Context

当前 KB 扫描已经可以在同一项目、同一源码版本下自动复用最新成功 source/x86 构建生成的 `compile_commands.json`。现有实现主要把 compile database 用作构建上下文：补充 include 路径、宏定义、语言标准、构建可达性和扫描摘要。

这个能力还没有把真实编译命令中的迁移风险转换为 finding。实际迁移场景中，一些 x86 相关问题只出现在构建参数中，例如 `-mavx2`、`-msse4.2`、`-march=x86-64` 或通过 `-D` 注入的 SIMD 开关。源码正文没有这些文本时，当前扫描不会产出对应 finding。

本 change 只处理 KB Scanner 与后端 KB scan 结果导入链路，不改变前端提交参数，也不改变 `POST /api/projects/{projectId}/kb-scans` 的请求结构。

## Goals / Non-Goals

**Goals:**

- 从 `compile_commands.json` 的 `arguments` 或 `command` 中提取真实编译 token。
- 对 x86/SIMD 相关编译参数生成稳定 KB finding。
- 对明确启用 x86/SIMD 路径的命令行宏生成 finding 或 evidence。
- 保持 compile database 不会减少源码扫描 finding；它只能补充上下文或新增构建命令 finding。
- 当同一构建参数风险已经被源码或构建文件扫描为 finding 时，不重复展示 compile command finding，只补充 compile command evidence。
- 在 finding evidence 中说明来源文件、命中 token、token 类型和 compile command 索引。
- 继续执行路径脱敏，API、SSE、数据库可见内容不得暴露服务器真实路径、远端绝对路径或对象存储 key。
- 补充单元测试和 E2E 覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不新增前端 API 参数。
- 不把 compile database 解析扩展为完整构建系统分析器。
- 不替代构建驱动依赖分析能力。
- 不在本 change 中新增人工确认 UI 或迁移报告展示字段。
- 不对每一种编译器参数做完整语义推理，只处理已有规则能明确识别的架构相关风险。

## Decisions

### 1. 将 compile command 作为 finding 来源，而不是源码过滤器

实现 SHALL 把 compile database 看作额外 evidence source。源码扫描的默认结果不得因为某个文件没有出现在 compile database 顶层 entry 中而被隐藏。

原因是 header、Makefile、CMakeLists、内联汇编片段等文件常常不会直接出现在 `compile_commands.json` 的 `file` 字段中，但仍然可能参与构建或定义迁移风险。compile database 可以证明某些命令确实发生过，不能反向证明未列出的源码风险不存在。

替代方案是把 compile database 作为强过滤器。该方案会减少误报，但已经在真实 `simdinfo` 流程中导致 finding 数量异常减少，因此不采用。

### 2. 优先基于 token 解析，而不是对完整命令字符串做模糊匹配

Scanner SHALL 同时支持 `arguments` 数组和 `command` 字符串：

- `arguments` 存在时优先使用数组，避免 shell quoting 歧义。
- 只有 `command` 存在时才做 shell-like token 拆分。
- 规则匹配基于规范化 token，例如 `-mavx2`、`-march=x86-64`、`-D__AVX__`。

这样可以减少双引号、空格、转义字符导致的误判，也便于 evidence 精确指出命中的 token。

### 3. compile command finding 使用独立 source kind

compile database 派生 finding SHALL 标记为 `sourceKind=compile_command` 或等效字段，并在 evidence 中保存：

- compile database entry index；
- 关联源码相对路径；
- 命中 token；
- token 类型，例如 `compiler_flag`、`define`、`language_standard`；
- 脱敏后的命令片段或 token 列表摘要。

若现有 finding 模型必须提供行号，MVP 可使用 `line=1`，但 evidence MUST 明确该 finding 来自编译命令而不是源码第一行。

### 4. 内部构建探测命令和未实际参与命令必须过滤

compile command finding 只应来自实际扫描范围内的项目文件。实现 SHALL 复用已有 include/exclude 规则，过滤以下内容：

- 不在项目源码根目录下的 `file`；
- 被排除目录或文件命中的 entry；
- CMake、Meson、Ninja 等构建系统内部探测文件，除非其 file 明确映射到项目源码；
- 只因为仓库里存在配置文件但本次构建没有执行的工具名。

这个判断不应固定为某几个工具白名单，而应基于“是否出现在真实编译命令 entry 中”和“是否通过 scanner 范围校验”来决定。

### 5. 构建参数风险需要跨来源去重

同一扫描中，相同 `sourceKind + ruleId + relativePath + token` 的 compile command finding SHALL 幂等去重。

如果源码或构建文件扫描已经命中同一个构建参数风险，例如 Makefile 中已有 `-mavx2` finding，而 compile database 中的真实命令也包含同一个 token，Scanner SHALL 不再新增一条 compile command finding。实现应把 compile command 的命中 token、entry index 和命令摘要合并到已有 finding evidence，或通过稳定 fingerprint 让后端导入时只保留一条展示记录。

原因是这两类信息在这种场景下表达的是同一个用户需要处理的问题：构建参数中存在 x86 专属选项。compile command 的价值是证明该参数实际参与了构建，不应该让前端和报告重复展示同一问题。

只有当源码扫描没有覆盖到该构建参数风险时，compile command 才 SHALL 产生新的 finding。

### 6. 后端保持 API 契约不变，只扩展结果内容

后端 KB scan worker 仍然按已有逻辑查找、下载、传入 compile database。新增 finding 由 scanner 输出，后端导入逻辑 SHALL 按现有 findings 入库流程保存。

后端需要确认 evidence 脱敏仍覆盖 compile command 中的路径、临时文件、对象存储信息和远端路径。若 scanner 输出未脱敏，后端导入前仍必须执行统一脱敏。

## Risks / Trade-offs

- [Risk] 编译参数规则过宽导致误报。→ Mitigation: 优先匹配明确 x86/SIMD token，并把 token 类型、来源和命令索引写入 evidence，便于审计。
- [Risk] `command` 字符串解析不完全等价于 shell。→ Mitigation: 优先使用 `arguments`；字符串解析失败时降级为 warning，不应导致整次扫描失败。
- [Risk] CMake 或编译器探测命令被误判为项目真实风险。→ Mitigation: 复用源码扫描排除规则，并要求 compile command entry 关联项目源码文件。
- [Risk] 与源码 finding 重复展示。→ Mitigation: 对构建参数风险做跨来源去重；源码已有同一 token finding 时，只补充 compile command evidence。
- [Risk] evidence 暴露本机或远端路径。→ Mitigation: 后端导入前继续执行统一路径脱敏，测试覆盖绝对路径和临时路径。

## Migration Plan

该 change 不需要数据迁移。上线后新 KB 扫描会产生 compile command 派生 finding；历史 KB 扫描结果保持不变。

回滚时可关闭 scanner 对 compile command finding 的生成逻辑，后端仍可继续传入 compile database 作为上下文，不影响原有源码扫描。

## Open Questions

- compile command 中的命令行宏是否全部转换为 finding，还是仅把 x86/SIMD 宏转换为 finding，其他宏仅作为 evidence 保存？本 change 默认只处理明确 x86/SIMD 相关宏。
- 后续是否需要在报告中单独标记“该风险已被真实编译命令确认参与构建”？本 change 先把该信息保存在 finding evidence 中。
