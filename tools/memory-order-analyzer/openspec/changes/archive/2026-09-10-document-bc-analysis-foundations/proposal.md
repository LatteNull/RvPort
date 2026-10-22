## Why

新项目已经保存了初步 BC 设计和编译实验，但关于多编译器适配、编译数据库边界、翻译单元身份以及跨文件关联的讨论尚未形成完整、可追溯的文档体系。需要在独立项目内固化这些结论，避免后续实现把“生成 BC”“拼接文件依赖”和“证明内存序安全”混为一谈。

## What Changes

- 本 change **仅整理、补充和校验文档**，不实现分析器、编译适配器、符号解析器或 DevKit 集成。
- 补充源码到 BC 的阶段说明：仍需预处理、语义检查和 IR 生成，但不要求生成本机可执行程序、完成最终链接或运行被分析程序。
- 记录生产编译器与分析用 Clang 的关系、参数适配和语义偏差，以及生成头文件、工具链、宏、目标架构和 sysroot 等前置条件。
- 明确 `compile_commands.json` 能表达逐翻译单元编译命令，不能单独提供完整头文件依赖、目标/链接关系、调用图或线程同步关系。
- 说明以构建配置区分翻译单元、逐 TU 生成 BC、按程序范围建立符号索引与函数摘要的跨文件流程；区分文件包含关系和真正的函数/共享对象关联。
- 统一内存模型分析的语义层次、覆盖状态和证据标注，保留 Clang 18 实验的适用范围与 DevKit 历史上未执行的事实。
- 在现有 `doc/` 中补齐专题文档和阅读索引，复用已有记录，不复制归档项目作为新实现基础。

## Capabilities

### New Capabilities

- `bc-build-context-documentation`: 定义 BC 生成、多编译器适配、编译数据库与构建上下文的文档要求。
- `cross-translation-unit-documentation`: 定义跨翻译单元关联、链接范围、符号解析、不确定性与增量更新的文档要求。
- `memory-order-evidence-documentation`: 定义内存序分析边界、实验溯源、DevKit 待验证状态以及文档导航与验收要求。

### Modified Capabilities

无。本项目尚无已发布的本地规格；不修改根目录或兄弟项目的规格。

## Impact

- 所有规划文件位于 `tools/memory-order-analyzer/openspec/`，文档变更范围限于本项目的 `README.md` 与 `doc/`。
- 计划新增 `doc/BUILD_CONTEXT_AND_COMPILER_ADAPTATION.md`、`doc/CROSS_TRANSLATION_UNIT_ANALYSIS.md`，更新既有流水线、分析设计、实验和 DevKit 验证文档及索引。
- 不改变运行时 API、依赖、构建流程或生产代码；不删除或修改归档目录 `memory-model-ir-checker`、`memory-model-checker-legacy`。
- 文档验收使用已有实测证据和官方资料，不以 ARM 可连接或 DevKit 新实测成功为完成前提；任何未实测能力必须明确标为待验证。
