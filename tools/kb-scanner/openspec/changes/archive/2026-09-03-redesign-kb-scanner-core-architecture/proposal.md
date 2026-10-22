## Why

当前 KB Scanner 已能深入识别大量 x86 头文件、intrinsic、builtin、编译参数、汇编和条件分支，但其主体仍是面向单文件匹配的 MVP。与 RVSmartPorting Wiki 的 C/C++ x86→RISC-V 迁移知识交叉验证后，主要差距集中在构建变量流、测试语义、跨文件关系和项目级就绪度，而不是继续堆叠孤立规则，因此需要先建立重写后的总体设计基线。

## What Changes

- 将 KB Scanner 的产品边界限定为 C/C++ 软件迁移分析；操作系统、内核、系统调用和硬件适配不进入本模块。
- 定义“工作区采集 → 事实归一化 → 关系建模 → 规则判定 → 项目评估 → 报告输出”的分层分析架构。
- 保留 `clang-x86-entries.json` 和 `gcc-x86-entries.json` 的现有内容、分类结构及 `generatedSet` 使用方式，继续将其作为编译器派生的 x86 事实数据源。
- 将原始事实、关系证据、局部发现和项目级评估分为不同领域对象，避免规则匹配同时承担解析、推理、降噪和报告职责。
- 定义源码、构建系统、RPM、测试、编译数据库和生成知识集的前端/提供者边界，使新增输入类型不再修改核心判定流程。
- 定义跨文件宏传播、Makefile 目标架构与源码选择、架构相关测试、替代实现和目标架构可达性的统一关系模型。
- 将构建选择分析限定为静态关系推导；可识别 `uname` 等架构探测来源，但假设探测结果正确，不分析交叉编译导致错误进入 x86 分支的场景。
- 定义项目级迁移就绪度及其证据要求，区分架构无关、仅 x86、多架构但无 RISC-V、部分 RISC-V 和完整 RISC-V。
- 保持现有 `scan-result.json` 主输出结构和字段语义兼容；新的内部分析模型必须投影为现有结果，新增信息只能采用向后兼容的可选字段。
- 本 change 只产出总体设计和行为规格，不重写运行时代码、不新增具体检测规则，也不承诺一次完成全部能力。

## Capabilities

### New Capabilities

- `kb-scanner-analysis-architecture`: 规定重写后 KB Scanner 的职责边界、编译器派生事实数据复用方式、分层分析管线、关系推理、项目级评估和输出契约。

### Modified Capabilities

无。该模块当前没有独立 OpenSpec 主规格。

## Impact

- 直接影响 `tools/kb-scanner/openspec` 下的设计和规格基线。
- 为未来重构 `kb_scanner/models.py`、`cpp_frontend.py`、`compile_commands.py`、`rules.py`、`report.py` 和 `cli.py` 提供约束，但本 change 不修改这些代码。
- 未来实现必须继续输出当前 `schemaVersion: "1.0"` 以及既有 `tool`、`rulePack`、`project`、`summary`、`findings`、`diagnostics` 顶层结构；不得以新结果结构替代现有契约。
- 与后端 `kb-scan-runtime` 的集成边界保持不变，本 change 不修改后端 parser、API、任务流程或数据库。
- 内存模型继续由独立的 memory-model IR checker 负责；KB Scanner 只保留结果关联边界，不重复实现 RVWMO 分析。
