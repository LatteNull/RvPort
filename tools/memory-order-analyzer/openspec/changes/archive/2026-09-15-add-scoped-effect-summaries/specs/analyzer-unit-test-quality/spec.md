## ADDED Requirements

### Requirement: Test independent evaluation protocol semantics and resource boundaries

局部求值协议及消费代码 SHALL 有有效单元断言，覆盖有限候选/unknown/bottom、guard 条件析取、重复边、绑定/祖先对象、依赖/请求调包、结构/工作预算和旧协议拒绝；所有代码纳入项目整体/语言/受影响逐模块行及可用分支至少 90%，P1 v2 黄金兼容不变。

#### Scenario: Empty or over-budget evaluation pretends to be complete

- **WHEN** 测试注入 pending 块、空有限域、unknown、陈旧请求 hash 或过深表达式
- **THEN** 验证器拒绝伪完整/非法结果且不栈溢出，合法有界输入与 P1 回归继续通过；未执行覆盖率不得勾选验收

### Requirement: Test local registry identities and LLVM query boundaries

新增登记与查询代码 SHALL 纳入整体/语言/逐模块行和分支至少 90% 单元门槛；SHALL 固定测试未物化 alloca、optnone/O0、MemoryPhi/回边、无布局/动态范围、登记预算错误、跨函数/陈旧/伪造证据及 P1 输出不变。集成通过 SHALL 不替代这些断言。

#### Scenario: An analysis node is disguised as a raw instruction

- **WHEN** 将 analysis_id 作为原始 SourceRef 或把未登记指令作为合法证明
- **THEN** 单测断言拒绝，合法同 BC 的独立登记和 P1 黄金回归仍通过

### Requirement: Include all P2 executable modules in unit-only coverage

P2 新增/修改/复用的 C++ 局部分析与 worker、Python schema/绑定/摘要/SCC/缓存/CLI/报告/质量逻辑及其他自有执行代码 SHALL 有正常、边界、异常、unknown 单元测试并纳入完整源码枚举。SHALL 保留整体、每语言和现有逐模块行/可用分支覆盖率至少 90% 门槛；未加载 Python、未调用 C++、新子目录及可执行头文件不得消失，缺少模块报告必须失败，集成 profile 不得补入。

#### Scenario: A new executable module is missed by the build or tests

- **WHEN** 新子目录中的模块或可执行头文件未被单元目标链接/调用，或 Python 模块未被加载
- **THEN** 统计将其纳入或因缺失报告失败，不缩小统计范围使覆盖率达标

#### Scenario: Overall coverage passes but a P2 module fails

- **WHEN** 项目整体行/分支均达标而某自有模块任一可用指标低于 90%
- **THEN** 质量入口非零退出，不把该模块排除、放宽门槛或标记验收完成

### Requirement: Assert semantic soundness boundaries independently of integration success

单元验收 SHALL 使用固定 IR/结构化输入有效断言参数/局部存储/精确整数/对象范围/返回/条件/未知传播、ABI 与 ODR 正反例、递归固定点/超限及协议/缓存失效。SHALL 包含禁止共享/atomic/volatile 常量转发、禁止参数默认不别名、未知外部效果非空、未收敛摘要非 complete、may 不提升 must 的负例。真实编译集成 SHALL 独立验证三个物理 TU、同名 static、字段范围、多调用实参和固定 atomic 包装。

#### Scenario: Raw instruction presence is insufficient for specialization

- **WHEN** atomic 包装内存在多个 order 分支而调用点传入 release
- **THEN** 测试断言调用上下文只含可达 release 原子写、对象和值正确、原始事实不变及相关未知状态正确，不只断言生成 BC 或含有 atomic 指令

#### Scenario: Conservative behavior prevents an unsound constant

- **WHEN** 反例包含共享/atomic load、逃逸局部或未知调用覆盖
- **THEN** 单元断言不能错误得到确定值/空效果，并检查 unknown 原因、条件和调用证据传播

#### Scenario: Identity reuse cannot manufacture semantic proofs

- **WHEN** 单测覆盖同实参不同调用点、递归相同 alloca/guard、循环内分配、模板缓存重绑定和预算合并
- **THEN** 分别断言实例隔离、调用者对象归属保留以及禁止合并实例强更新/must-alias/noalias/互斥提升；相关代码纳入整体及逐模块行/分支至少 90% 门槛

### Requirement: Execute and publish repeatable P2 quality acceptance

实施交付前 SHALL 在独立开发容器离线运行完整单元测试、覆盖率门槛和分离集成测试，使用新的输出目录，记录命令、测试结果、工具/标准库版本、整体/每语言/逐模块行与分支 hit/total、完整统计范围、排除理由和报告位置。SHALL 测试 89.99%/90% 边界、缺失报告、预算/超时、来源/引用错误以及输出确定性。未执行、环境阻塞、失败或覆盖不足 SHALL 不标记完成或提示归档。

#### Scenario: Quality or semantic acceptance cannot complete

- **WHEN** 任一单元/语义集成失败、覆盖不足、报告缺失或执行环境阻塞
- **THEN** 保存实际证据和差距，任务保持未完成并提示继续 apply/修复，不以历史 P1 覆盖率或 DevKit 零建议替代本次验收
