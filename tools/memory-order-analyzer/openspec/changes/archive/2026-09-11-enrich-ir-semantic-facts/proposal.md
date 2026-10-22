## Why

已完成的 LLVM 基础设施能列出事件和直接调用，但缺少实参/返回值、SSA 依赖、条件边与内存字节范围，无法支持下一阶段可靠的对象与效果传播。

## What Changes

- 本 change 是**运行时代码实现变更**；本次 propose 仅生成规划材料，不执行实现。
- 增加模块局部的值引用图：参数、整数常量、指令结果、返回值、phi/select/cast/GEP/comparison 及相关整数运算；保留位宽、操作语义和 poison/undef/unsupported 状态。
- 增加 branch/switch 条件边、call/invoke 实参及返回结果、正常/异常后继；保留原始函数、事件、块和指令定位方式，不做调用点特化或路径求解。
- 使用锁定 LLVM 的 DataLayout 增加访问大小、对齐、地址空间、可确定字节偏移；保留初始化值、store/RMW/CAS 操作数和内存 intrinsic 长度。动态或不支持的语义有显式原因，不填零。
- **BREAKING**：ModuleFacts 与 RunReport 一起升为 schema v2，拒绝将旧 v1 facts/report 按新契约消费；其他对象继续 v1，改为按 kind 校验版本。统一 extractor 身份与 collect/import/link 的产物/缓存身份，使旧事实和旧 worker 不能伪装成新结果。旧 BC 字节允许经新 reader 重提取，不自动覆写旧产物或伪造来源；旧报告仅作为历史证据保留，不补造提取状态。该修订已获用户确认。
- 为提取能力、逐项 unknown 和资源截断提供独立完整性说明，继续保持 `semantic_analysis=not_run`、`safety=not_evaluated`、`findings=null`。
- 补齐所有自有新增/修改代码单元测试，落实整体、各语言和逐模块至少 90% 行/可用分支覆盖率；增加独立 C/C++ compile-only 集成验收及文档映射。

## Capabilities

### New Capabilities

- `ir-semantic-value-flow`: 值引用、精确整数表示、操作数关系、条件控制流与调用/返回接口，以及有界且显式不完整的事实提取。
- `ir-memory-access-ranges`: 基于模块 DataLayout 的访问范围、地址空间、对齐、初始化值与内存操作数，不推断别名或对象合法性。

### Modified Capabilities

- `llvm-bitcode-facts`: 丰富 ModuleFacts，同时保留事件/order/scope/debug 和未执行过程间特化的边界。
- `analysis-integrity-reporting`: 按 kind 的版本兼容、完整身份失效、事实引用校验与提取完整性报告；不引入风险退出码。

## Impact

- 修改范围限本项目 `src/`、`schemas/`、`python/memory_order_analyzer/`、CMake/测试、必要的版本元数据和 `doc/`；所有 OpenSpec 文件在当前项目内。
- 延续 C++20 + LLVM 21.1.8 和 Python 编排，不升级工具链，不接入 SVF/PhASAR/GenMC/DevKit，不引入新服务。可按职责拆分 C++ 文件，但新增源码必须进入构建和覆盖率枚举。
- CLI 仍为现有 collect/import-bc/index/link/doctor；旧 ModuleFacts JSON 不再被新消费者接受。完整性缺口沿用 0/2/1 基础设施退出约定，语义分析仍未运行。
- GCC/Clang C11/C17/C++17/C++20、compile-only、显式 scope、profile 隔离、来源与 lineage 约束不变；不运行被分析程序。
- P2 摘要、P3 线程/HB、P4 风险判定、CMake 目标导入及开发/生产容器整合均不在本 change。保留旧 checker 与历史 ARM 证据，不修改仓库根 CI 或生产 Dockerfile。
