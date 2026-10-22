## Why

扫描器已经具备十类 C/C++ 浮点迁移风险检测，但现有验证主要证明单个规则和协议行为，尚不能量化回答“在固定语料上检测得多准、拒绝判断得是否保守、规模增长和故障发生时结果是否仍可信”。在接入 RvPort 主流程之前，需要先建立可审计的真值、质量指标、资源预算、缓存与故障恢复门禁，避免把未分析范围、缓存污染或资源耗尽误报为安全。

## What Changes

- 建立版本化 reviewed validation corpus、显式 oracle 和验证结果协议，覆盖 C11、C17、C++17、C++20、x86/RISC-V profiles、AST-only、共享 LLVM BC、AST↔IR evidence、正例、反例、边界、`unknown`、异常及 suppression。
- 按 finding code 计算 TP、FP、FN、strict precision/recall、supported-only 指标、exact match 和 abstention/unknown；公开全部分母，零分母使用 `null`，本应判断却 abstain 的正例计入 strict recall 的漏检。
- 统一执行 wall time、CPU、峰值 RSS、文件数、artifact/BC 字节、worker 输出、facts、evidence、rule candidates、assessment、diagnostic 和 suppression 预算，并为截断范围记录稳定 frontier、`partial`/`failed` 状态和固定退出码。
- 引入 canonical facts/evidence 的版本化内容寻址缓存；最终 finding 不进入缓存。缓存键固定源码、编译上下文、profile、schema、producer、Clang/LLVM 和 artifact 摘要，损坏、不兼容或越界条目安全降级为 cache miss。
- 为 suppression 增加 `expires_on`，并使用请求显式提供的 `policy_as_of` 判断有效期，禁止读取系统当前时间影响扫描语义；补齐过期审计、诊断聚合、路径脱敏和原子发布恢复。
- 固定 benchmark container/host 描述、三档规模语料和 wall/CPU/峰值 RSS/结果大小/性能回退预算，验证重复运行、不同绝对工作区以及冷、热缓存的语义等价。
- 增加正常、边界、异常、`unknown`、故障注入、缓存损坏、预算耗尽和 suppression 过期单元测试，并保持全部项目自有 Python/C++ 源码以及受影响模块的行、分支覆盖率均不低于 90%。
- 本阶段不新增检测规则、不接入 RvPort 主流程，也不实现动态差分执行。

## Capabilities

### New Capabilities

- `scanner-validation-and-benchmarking`: 定义 reviewed corpus、oracle、质量指标、版本化验证报告、固定 benchmark 环境、规模工作负载和性能验收门禁。
- `scanner-analysis-cache`: 定义 canonical facts/evidence 内容寻址缓存的键、命中语义、完整性校验、原子发布、损坏恢复和冷/热结果等价性。

### Modified Capabilities

- `scanner-runtime-foundation`: 将全部已声明资源预算落实到 Clang、LLVM、事实映射、evidence、规则和输出全流程，并增加显式 policy 日期与稳定预算 frontier。
- `scanner-failure-semantics`: 明确各类预算耗尽、缓存故障、故障注入、诊断上限和原子恢复的保守状态、分母及退出码语义。
- `scanner-io-contract`: 扩展请求、结果和 suppression 审计协议，支持 `policy_as_of`、`expires_on`、缓存元数据及验证所需的确定性字段。
- `scanner-quality-gates`: 增加 reviewed corpus、检测质量、故障注入、性能资源与缓存等价门禁，同时保留整体和受影响模块行/分支覆盖率至少 90% 的要求。

## Impact

- 影响 `src/floating_point_precision_scanner` 中的协议、应用编排、Clang/LLVM 进程控制、规则预算、suppression、诊断、原子输出及新增验证/缓存模块。
- 影响 `src/cpp` LLVM worker 的预算统计、资源消耗报告和故障边界，但不改变十类规则的检测含义。
- 新增 validation corpus、oracle、benchmark fixtures、故障注入适配点、验证报告 schema、缓存布局和对应中文文档。
- scan request/result 将演进兼容版本；旧请求继续可读，新字段的缺省行为必须确定且不得依赖宿主时间或路径。
- 不改变共享 BC 的生产所有权：扫描器仍只读消费 x86 构建模块发布的不可变制品。
