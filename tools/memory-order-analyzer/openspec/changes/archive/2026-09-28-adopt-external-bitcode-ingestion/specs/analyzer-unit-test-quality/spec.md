## ADDED Requirements

### Requirement: Unit test every external ingestion executable path
所有新增、修改、删除或复用的 external bundle/record/report 契约、路径边界、流式 hash/copy、格式与 reader 校验、identity、artifact/scope 发布、cache、CLI、readiness、AST 对齐、降级、报告和迁移逻辑 SHALL 有带有效断言的单元测试，覆盖正常、边界、异常和 partial/unknown。集成 fixture 编译、Clang 成功、静态检查、零 finding 或历史 collect 测试 MUST NOT 替代单元测试。

#### Scenario: A path or identity error branch is untested
- **WHEN** 正常 bundle 集成通过但 path escape、输入变化、duplicate identity、stale digest 或 cache corruption 分支缺少单元断言
- **THEN** required gate 失败，相关任务不得完成或提示同步归档

#### Scenario: Removed producer code remains reachable
- **WHEN** parser、driver 或兼容层仍可触发 collect、dependency emission、Clang BC generation 或 llvm-link
- **THEN** 单元测试必须失败并指出禁止执行路径，不以该命令未被文档展示为通过

### Requirement: Enforce no-execution boundaries in unit and integration tests
项目 SHALL 使用注入 runner、argv 审计或进程边界测试证明 `ingest-bc-bundle`、`import-bc`、`index` 和下游生产分析不执行 compiler、dependency generator、assembler、linker、configure/build、网络、SSH 或目标程序。真实 fixture BC SHALL 在进入受测产品流程前预生成并清楚计为 test preparation；测试 MUST 覆盖无 GCC/Clang/llvm-link 环境下纯 ingestion 成功。

#### Scenario: A malformed input tempts a repair subprocess
- **WHEN** 输入为 ELF、GCC LTO、截断 BC 或 verify failure
- **THEN** 断言产品只返回格式/reader诊断且禁止工具 argv 集合保持为空

#### Scenario: AST assistance is enabled
- **WHEN** ingestion 后显式运行 source worker
- **THEN** 仅允许协议化 AST/source 解析请求，不出现 `-emit-llvm`、BC/object 输出或构建命令

### Requirement: Enforce project language and affected-module coverage for ingestion
交付本 change 前 SHALL 在锁定开发容器的新输出目录实际运行 unit-only 覆盖率入口；项目整体、Python、C++ 以及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%。统计 SHALL 纳入未加载 Python、未调用 C++、新增子目录、可执行头文件以及删除后仍残留的生产路径；不得缩小范围、排除自有业务逻辑、降低阈值或把集成 profile 合入单元覆盖。

#### Scenario: Overall coverage passes but the ingestion driver fails
- **WHEN** 整体与实现语言覆盖率达标，但 contracts、path validation、publication、readiness、CLI 或 report 任一受影响模块行/分支低于 90%
- **THEN** required gate 非零并列出模块，不能通过排除文件或平均百分比验收

#### Scenario: A formerly compiled module becomes unreachable
- **WHEN** 删除 collect/link 后旧自有执行文件不再被产品或单元加载但仍保留在源码范围
- **THEN** 质量入口仍将其纳入分母或要求删除/补测，不因不可达而自动消失

### Requirement: Publish repeatable external-ingestion acceptance
实施交付前 SHALL 独立运行全量单元测试、整体/语言/逐受影响模块双 90% 门禁、C11/C17/C++17/C++20 逐 TU bundle、跨 TU scope、IR-only、AST+IR、missing/failed、损坏/版本不兼容、x86 host/target、linked/optimized、cold/warm cache、既有 P1–A6/R1–R3 回归以及 schema/文档/OpenSpec 严格校验。验收 MUST 记录精确命令、环境/工具版本与 hash、测试数、line/branch hit/total、统计范围、排除理由、truth/完整性指标、禁止执行审计和报告位置。

#### Scenario: Optional source inputs are unavailable
- **WHEN** 外部 BC ingestion 和 IR-only 回归完成，但某用例没有源码/compile database
- **THEN** 核心 IR 输入验收可完成，该用例明确 source unavailable/partial，不伪造 AST 对齐

#### Scenario: Any required gate fails
- **WHEN** 单元、双 90%、bundle truth、禁止执行、既有回归、缓存、schema 或文档校验任一失败
- **THEN** 任务保持未完成并记录差距，只提示继续 apply/修复，不提示同步归档
