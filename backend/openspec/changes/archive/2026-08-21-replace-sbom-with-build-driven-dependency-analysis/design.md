## Context

当前 SBOM 分析能力从 source/x86 与 target/RISC-V 两个环境全量采集组件，再进行组件替代性分析。这个模型在两个环境操作系统或发行版不同的情况下，会把大量与当前源码无关的 OS 差异纳入结果，导致迁移分析发散。

新的设计把分析锚点改为“当前源码在 x86 源环境中的真实构建事实”。系统先通过构建验证 runtime 执行一次 source/x86 前置构建，收集构建命令、构建日志、编译/链接线索和构建产物，再对这些事实提取依赖，并查询 RISC-V 目标环境是否已经安装或仓库可提供对应依赖。

源码部署继续作为构建验证 runtime 的内部能力。后续正式构建验证仍然默认双环境运行，用来验证迁移后源码是否同时不破坏 x86 且能在 RISC-V 构建。依赖分析本身不依赖 RISC-V 构建或测试失败证据。

## Goals / Non-Goals

**Goals:**

- 将新主流程中的依赖缺口判断改为构建事实驱动的依赖分析。
- 保留旧 SBOM API、旧任务和旧数据兼容，并将其标记为 deprecated。
- 构建验证增加 `SOURCE_ONLY` 构建范围，用于依赖分析前置 x86 构建；默认仍为 `BOTH`。
- 依赖分析结果绑定 `projectId`、`sourceRevisionId`、前置 source 构建运行和任务 ID。
- 依赖分析基于 x86 构建事实提取构建依赖、链接依赖、运行依赖和可选测试依赖。
- 依赖分析查询 RISC-V 目标环境的已安装、仓库、provides/whatprovides、pkg-config、header 和工具能力。
- 新流程迁移输入、报告、归档和 E2E 使用 `DEPENDENCY_RESULT`。
- 历史 `SBOM_RESULT` 和 SBOM 报告/归档输入继续保留查询和历史兼容能力。

**Non-Goals:**

- 不做 x86 与 RISC-V 操作系统全量差异比较。
- 不把 RISC-V 构建失败日志作为依赖分析必要输入。
- 不取消后续正式双环境构建验证。
- 不要求前端单独调用源码部署 API。
- 不在本 change 中实现 AI 对构建日志的自由诊断；依赖提取应优先使用确定性规则和受控工具输出。

## Decisions

### 依赖分析以 x86 构建事实为输入

依赖分析 SHALL 要求当前源码版本存在成功的 source/x86 构建运行。该构建运行可以来自 `buildScope=SOURCE_ONLY` 的前置构建，也可以来自包含 source 成功结果的 `BOTH` 构建。

输入事实包括：

- 构建脚本摘要和受控脚本引用。
- 构建命令、工作目录、环境变量名称摘要。
- merged/stdout/stderr 构建日志引用。
- 基于 `PS4` + `set -x` 的 shell 执行 trace 摘要，用于记录用户脚本实际执行的命令、目录和脚本行号。
- 可选的 `strace -f -e execve` 进程启动观测摘要，用于捕获脚本封装后的真实子进程、编译器、linker、pkg-config、构建工具和测试工具调用。
- 编译数据库和构建系统中间产物摘要，例如用户构建自然生成的 `compile_commands.json`、`CMakeCache.txt`、`build.ninja`，以及可选 Bear 生成的 `compile_commands.json`。
- 构建产物清单，包括 ELF、可执行文件、动态库、静态库和可审计路径摘要；构建前已存在的仓库自带 ELF/.so 需要继续分析，构建后新增的本次构建产物只作为排除证据。
- 从构建日志提取的编译器、构建系统、pkg-config、`-l`、`-I`、`-L`、header、linker error 和 tool 线索。

不采用 RISC-V 构建失败日志作为输入，是为了避免把依赖分析变成失败诊断。RISC-V 构建验证在后续节点继续作为实际验证步骤。

### 构建系统识别采用多信号观测

用户提交的是自定义构建脚本，后端不能假设脚本直接对应某一种构建系统。构建系统识别 SHALL 是多值、证据驱动、带置信度的结果，而不是单个 `buildSystem` 字段。

采集信号分为五类：

- 静态探测：扫描源码树和脚本文本中的 `CMakeLists.txt`、`Makefile`、`*.spec`、`configure`、`meson.build`、`build.ninja` 等，作为低成本 hint。
- shell trace：在受控 wrapper 中启用 `set -x` 并设置 `PS4` 前缀，记录实际执行命令、目录和脚本行号。
- exec trace：如果 source/x86 环境存在 `strace`，使用 `strace -f -e execve` 记录真实 `execve` 调用链；如果不存在，worker MAY 在构建前按目标环境包管理器执行一次受控、有限安装尝试。
- 编译数据库：优先采集用户构建自然生成的 `compile_commands.json`、`CMakeCache.txt` 和 `build.ninja`；如果环境存在 Bear，则 MAY 使用 Bear 包裹用户构建脚本生成 `compile_commands.json` 作为增强观测。
- 编译器内置宏：构建 wrapper SHALL 在 source/x86 构建环境中对实际存在的 `cc`、`gcc`、`clang`、`c++`、`g++`、`clang++` 执行 `-dM -E` 采样，记录本次构建环境的 C/C++ 内置宏集合。依赖分析 SHALL 使用该集合区分编译器内置宏和项目/构建自定义宏。
- 产物与日志反推：构建前后扫描 ELF、rpm/deb 包、`compile_commands.json`、`CMakeCache.txt`、测试报告和构建错误日志。构建前后 manifest 对比用于区分仓库原有 ELF/.so 与本次构建新增产物；新增产物不得作为依赖分析结果项。

`strace` 是增强信号，不是构建成功的硬依赖。安装尝试失败、环境不允许安装或用户没有权限时，构建 SHALL 继续执行，并在构建事实中记录 `straceUnavailable` warning。依赖分析 MUST 能在没有 `strace` 的情况下退回到 PS4 trace、构建日志和产物扫描。

Bear 与编译数据库同样是增强信号，不是构建成功的硬依赖。后端 SHALL 遵守以下约束：

- 优先读取用户构建自然生成的 `compile_commands.json`、`CMakeCache.txt`、`build.ninja`，不得假设这些文件必然存在。
- 不得为了生成 `compile_commands.json` 强行改变用户构建系统、CMake generator、构建目录或用户传入的构建参数。
- 如果 Bear 已存在，worker MAY 使用 `bear -- <user-build-wrapper>` 包裹构建脚本。
- 如果 Bear 不存在，worker MAY 在构建前执行一次受控、有限安装尝试；安装失败、无权限或环境不支持时 SHALL 降级，不得阻断用户构建。
- Bear 生成的 `compile_commands.json` 只能作为命令观测证据之一，依赖分析仍需结合 strace、PS4 trace、日志和产物扫描。

`make`、`cmake`、`ninja`、`meson` 等构建系统不是 C/C++ 预处理器内置宏来源。构建系统生成的 `FLAG_SUPPORTED_*` 等探测宏 SHALL 归类为编译器参数能力探测结果；真正的 C/C++ 内置宏判断 SHALL 以实际编译器采样输出为主，静态内置宏表只作为兜底。

观测结果建议保存为：

- `detectedBuildSystems[]`：类型、置信度、evidence 摘要。
- `observedCommands[]`：脱敏后的命令摘要、来源类型、工作目录摘要。
- `compileDatabases[]`：自然生成或 Bear 生成的编译数据库摘要、来源类型、文件数量、命令数量和脱敏后的 include/define/compiler 摘要。
- `observationWarnings[]`：strace 不可用、trace 被用户脚本关闭、日志截断等非阻断问题。

### 构建验证增加 buildScope

构建创建请求增加可选 `buildScope`：

- `BOTH`：默认值，按当前运行双环境同时创建 source/x86 和 target/RISC-V 构建运行。
- `SOURCE_ONLY`：只创建 source/x86 构建运行，作为依赖分析前置事实来源。

`TARGET_ONLY` 暂不作为前端公开能力，除非后续明确需要单独复跑 target 构建。后端内部可以保留枚举扩展位，但 API 文档应明确 MVP 只支持 `SOURCE_ONLY` 和 `BOTH`。

源码部署由构建 runtime 内部按 `buildScope` 自动执行或复用成功部署记录；依赖分析不触发源码部署。

### 新增 dependency-analysis 数据模型

建议新增独立表，而不是复用 `sbom_*` 表名：

- `dependency_analysis_runs`：运行记录，绑定项目、源码版本、source 构建运行、target 环境、环境配置版本、任务、状态、摘要。
- `dependency_analysis_result_items`：逐条结果，保存依赖类型、名称、版本、来源证据、目标匹配状态、风险、建议、可分页过滤字段和 evidence JSON。
- `dependency_analysis_artifacts` 或复用 `stored_artifacts`：保存输入摘要、输出摘要、HTML/JSON 报告等制品元数据。

旧 `sbom_*` 表不应继续承载新写入。历史数据可以保留只读，或者在后续单独迁移。

### 依赖类型和匹配状态

依赖类型建议为：

- `BUILD_TOOL`：gcc、clang、cmake、make、ninja、pkg-config 等。
- `BUILD_PACKAGE`：构建期 dev package、header provider、pkg-config module owner。
- `LINK_LIBRARY`：链接阶段 `-lxxx`、SONAME、ELF NEEDED。
- `RUNTIME_LIBRARY`：构建产物运行期动态库。
- `TEST_TOOL`：测试命令依赖的 pytest、ctest、shell 工具等。
- `TEST_PACKAGE`：测试报告或测试命令推断出的测试依赖。

目标匹配状态建议为：

- `TARGET_INSTALLED`
- `REPO_AVAILABLE`
- `PROVIDES_MATCH`
- `VERSION_MISMATCH`
- `SOURCE_BUILD_REQUIRED`
- `MISSING`
- `MANUAL_CONFIRM_REQUIRED`

`detectedLevel` 在迁移输入中继续使用 `riskLevel + "/" + targetMatchStatus`，例如 `HIGH/MISSING`、`LOW/TARGET_INSTALLED`。

### 目标 RISC-V 能力查询

依赖分析 worker 在执行时 SHALL 对 target/RISC-V 环境执行受控能力查询：

- 已安装包与工具版本。
- 仓库 metadata refresh。
- package search。
- provides/whatprovides 查询。
- pkg-config module 查询。
- header owner 查询。
- ELF SONAME/provider 查询。

查询失败不应默认解释为目标不存在依赖。结果必须记录 warning，并把对应项降级为 `MANUAL_CONFIRM_REQUIRED` 或证据不足状态。

### 迁移输入和报告

依赖分析结果进入迁移输入时：

- `sourceType=DEPENDENCY_RESULT`。
- `sourceRefId=dependency_analysis_result_items.id`。
- `locationLabel` 根据依赖类型生成，例如 `build:gcc`、`package:openssl-devel`、`lib:libssl.so.3`、`test:pytest`。
- `issueTitle` 表达具体缺口或确认事项。
- `suggestion` 表达安装目标包、调整构建脚本、源码构建或人工确认。

报告中的依赖替代性注意点改为读取 confirmed 的 `DEPENDENCY_RESULT` 输入。

### 旧 SBOM 主流程标记 deprecated

对外新主流程不再默认创建 `SBOM_ANALYSIS`。旧 SBOM API、旧 `SBOM_ANALYSIS` 任务类型、旧 `sbom_*` 表和历史 `SBOM_RESULT` 迁移输入 SHALL 保留兼容，并在 API 文档、OpenSpec 和响应摘要中标记 deprecated。新前端节点、自动合并和新报告默认使用 `DEPENDENCY_RESULT`。

## Risks / Trade-offs

- [Risk] 构建日志格式差异大，依赖提取可能漏项。  
  Mitigation: 结合构建日志、命令、产物 ELF、pkg-config、headers 和 owner package 多源证据；证据不足时显式标记人工确认。

- [Risk] 前置 x86 构建失败会阻断依赖分析。  
  Mitigation: 这是有意约束；没有成功构建事实时依赖分析不应伪造结果。前端应先引导用户修复 x86 构建。

- [Risk] 旧 SBOM API 和新依赖分析 API 在一段时间内并存，前端或测试可能误用旧入口。  
  Mitigation: 文档和 API 响应明确 deprecated 状态；新流程默认入口、自动合并、报告和归档优先使用依赖分析结果。

- [Risk] `SOURCE_ONLY` 构建范围可能被误用于正式验证。  
  Mitigation: API 响应和构建记录必须展示 `buildScope`；正式构建验证节点默认使用 `BOTH`。

- [Risk] 目标仓库查询失败会产生误判。  
  Mitigation: 查询失败必须进入 warning 和 evidence，不允许把缺失证据当作 `MISSING` 的强结论。

## Migration Plan

1. 扩展构建验证 API、运行记录和 worker，支持 `buildScope=SOURCE_ONLY|BOTH`。
2. 新增依赖分析数据库 schema、jOOQ 生成代码、任务类型和 worker handler。
3. 新增 dependency analyzer 工具或替换旧 SBOM analyzer 的入口与 JSON 契约。
4. 新增依赖分析 API、结果分页过滤排序、artifact 下载和 E2E。
5. 修改迁移输入、报告、归档，新流程使用 `DEPENDENCY_RESULT`，历史 `SBOM_RESULT` 保留兼容。
6. 将旧 SBOM 主流程 API 标记为 deprecated，并从新流程默认入口中移除。
7. 更新中文文档和真实环境验证脚本。

Rollback 策略：旧 SBOM API、旧 `sbom_*` 表和历史数据保留；如果新依赖分析不可用，可暂时隐藏新节点，历史 SBOM 查询仍可使用。构建 `SOURCE_ONLY` 不影响默认 `BOTH` 行为。

## Open Questions

- 旧 `/api/projects/{projectId}/sbom-analyses` 是否继续允许创建 deprecated 任务，还是只保留历史查询和读取？
- `tools/sbom-analyzer` 是重命名为 `tools/dependency-analyzer`，还是新建工具并保留旧目录到后续清理？
- 前置 x86 构建由前端显式调用构建 API 传 `SOURCE_ONLY`，还是依赖分析创建接口自动触发缺失的前置构建？
