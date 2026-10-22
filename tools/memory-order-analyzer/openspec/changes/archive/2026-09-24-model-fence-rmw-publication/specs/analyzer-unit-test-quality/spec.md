## ADDED Requirements

### Requirement: Unit test every A6 owned executable path
所有新增、修改或复用的 A6 Clang/LLVM worker、协议/schema/引用校验、事件归一化、对象和线程绑定、RF/MO 求解、release sequence、fence pairing、P4 overlay、frontier、预算、cache、CLI、报告与质量脚本 SHALL 有带有效断言的单元测试，覆盖正常、边界、异常和 partial/unknown 路径。集成 truth、编译成功、静态检查、外部工具或零 finding MUST NOT 替代单元测试。

#### Scenario: The truth matrix passes but a solver error branch is untested
- **WHEN** 四语言集成 truth 全部匹配，但 RF/MO solver 的预算、损坏约束或未闭合分支缺少单元断言
- **THEN** A6 质量门禁失败，相关任务不得标记完成或提示归档

#### Scenario: Existing code is reused by A6
- **WHEN** A6 复用 P1/R3 event helper、A5 binding、P4 aggregator 或现有 cache 逻辑
- **THEN** 受 A6 修改或新增行为的代码进入本次单元测试与受影响模块覆盖分母，不以历史验收替代

### Requirement: Enforce A6 project language and affected-module coverage
交付 A6 前 SHALL 实际运行单元覆盖率入口；项目整体、Python、C++ 以及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%。统计 SHALL 纳入未加载 Python、未调用 C++、新增子目录和可执行头文件，按 hit/total 聚合；不得缩小范围、排除自有业务逻辑、降低阈值或把集成 profile 合入单元覆盖。

#### Scenario: Overall coverage passes but one atomic module is below threshold
- **WHEN** 项目整体与实现语言覆盖率达标，但 source classifier、event extractor、solver 或 overlay 任一受影响模块的行或分支低于 90%
- **THEN** required gate 非零退出并列明模块，不能通过排除文件或平均百分比验收

#### Scenario: A new source file is not loaded
- **WHEN** 新增 A6 自有源码没有单元 coverage record
- **THEN** 质量入口将其纳入总数或因报告缺失失败，不因零加载从分母消失

### Requirement: Publish repeatable offline A6 quality acceptance
实施交付前 SHALL 在锁定的独立开发容器和新输出目录运行完整单元测试、整体/语言/逐受影响模块双 90% 门禁、四语言 truth、`-O0`/`-O2` 归一化、eager/R3 等价、既有全量回归、cold/warm cache 和文档/schema 校验。验收记录 MUST 包含精确命令、工具/标准库版本与 hash、测试数、line/branch hit/total、统计范围、排除理由、truth 指标、完整性、预算、报告位置和失败差距；日常 required gate MUST NOT 访问网络、SSH 或运行专有工具/被分析程序。

#### Scenario: An optional external comparison is absent
- **WHEN** 核心离线门禁通过但 GenMC、herdtools7 或 ARM DevKit 环境不可用
- **THEN** 核心验收可完成，外部对照明确记录 `not_run`，不得伪造一致性或安全结论

#### Scenario: Any required gate fails
- **WHEN** 单元、覆盖率、truth、归一化、等价、回归、缓存、schema 或文档校验任一失败
- **THEN** 任务保持未完成并保存实际差距，只能提示继续 apply/修复，不得提示同步归档
