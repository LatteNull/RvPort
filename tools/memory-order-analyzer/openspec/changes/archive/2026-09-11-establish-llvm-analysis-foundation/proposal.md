## Why

项目目前只有技术文档与编译探针，尚无可复现的分析开发环境和生产级 BC 事实流水线。2026-09-11 ARM DevKit 25.3.0 实测验证了 compile-only BC 的可接入性，同时暴露出退出码为零但没有产物、独立 BC 未自动跨 TU 关联、缺 debug 后零建议以及正确同步仍被建议加屏障的问题，需要先建立可追溯且不夸大完整性的自有基础设施。

## What Changes

- 本 change 是**运行时基础设施实现变更**，不是文档整理或完整内存序检测器交付；建立 Python 编排层、LLVM C++ 事实提取核心及版本化产物契约。
- **本 change 创建独立 `Dockerfile.dev`，实际构建并验证开发容器**，提供固定工具链、编译、单元测试和覆盖率命令。与生产 Dockerfile 的合并明确留给另一个 change；不改生产镜像及仓库级容器配置。
- 编译输入限定 GCC/Clang 的用户态 C/C++，首轮验收覆盖 C11/C17、C++17/C++20；不实现 MSVC/clang-cl 支持。保留原始构建上下文及参数适配记录，不宣称分析 Clang 与生产 GCC 生成代码完全等价。
- 从编译数据库建立配置级 TU 身份，采集实际依赖，执行 compile-only BC 生成、结构校验、源码定位及内存/调用事实提取；支持有来源元数据的已有 BC 导入和明确降级。
- 实现显式目标范围内的符号索引、直接调用和全局引用绑定，以及可选限定范围 `llvm-link`；间接调用、复杂链接规则和指针关系保留候选/未知，不在本 change 实现全程序别名、函数效果传播或线程同步判定。
- 把构建、读取、源码映射、范围完整性及尚未实现的语义分析状态分开报告；不以成功退出、零事件或零建议解释程序安全。
- 固化 ARM 实测的可移植证据摘要与代表报告，更新文档中的版本、日期、GCC/Clang 范围和阶段状态；保留历史网络阻塞记录，不将 mm-check 作为正确性 oracle，也不把在线 SSH 作为日常测试前提。
- 所有自有可执行代码同步提供单元测试，项目整体及受影响模块的行覆盖率均至少 90%，支持分支指标时分支覆盖率也至少 90%；纳入现有自有探针脚本，不能用编译/集成实验代替单元测试。

## Capabilities

### New Capabilities

- `analyzer-development-container`: 独立、可构建、可验证的开发镜像、工具链锁定及项目级开发入口。
- `gcc-clang-compilation-context`: GCC/Clang 编译数据库、有效配置身份、参数适配与依赖/缓存输入管理。
- `llvm-bitcode-facts`: compile-only 生成、已有 BC 导入、LLVM 校验及带来源的 IR 事实输出。
- `scoped-module-association`: 显式分析范围、模块身份、直接符号引用关联与限定范围链接。
- `analysis-integrity-reporting`: 版本化运行报告、分层状态、完整性缺口和失败/降级退出约定。
- `analyzer-unit-test-quality`: 全部自有代码的单元测试、双维覆盖率门槛及可重复执行的质量验收。

### Modified Capabilities

- `bc-build-context-documentation`: 将当前支持范围明确限定 GCC/Clang，保留 BC 编译与生产编译语义不等价的边界。
- `memory-order-evidence-documentation`: 纳入新 ARM 实测证据及其限制，允许项目状态随实际完成的基础设施更新，继续明确尚无并发正确性判定能力。

## Impact

- 规划和实现均限定在 `tools/memory-order-analyzer/`。预计新增 `Dockerfile.dev`、项目级构建/工具链配置、`src/`、`python/`、`tests/`、`scripts/` 及事实/报告 schema；现有 `doc/` 和 README 按实施进度更新。
- 首阶段复用 Clang/LLVM、CMake/Ninja、GoogleTest 和 pytest/覆盖率工具；选择并验证一个固定 LLVM 工具链，不复用兄弟项目运行时或依赖其容器。外部工具的精确版本、来源和许可证在实现首个任务锁定。
- SVF、PhASAR、GenMC、herdtools7 和 DevKit 本阶段只定义未来接入边界，不新增强制依赖，不安装/运行远端后端；SVF 许可及后端版本兼容性不在此提案中假定已经解决。
- 不修改归档 checker、仓库根 OpenSpec、生产 Dockerfile 或远端安装；不自动插入屏障，不运行有竞争的被分析程序，不把 ARM 47 份成功状态报告当作检测准确率或单元测试覆盖率。
