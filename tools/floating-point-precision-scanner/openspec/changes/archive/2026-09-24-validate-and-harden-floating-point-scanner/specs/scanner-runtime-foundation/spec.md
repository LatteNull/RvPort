## ADDED Requirements

### Requirement: 全流程预算必须由统一协调器执行
扫描器 SHALL 为每个请求建立统一 BudgetCoordinator，以共享 monotonic deadline、CPU/RSS sampler 和稳定逻辑计数约束 Clang 前端、LLVM worker、facts 映射、evidence、规则、诊断、suppression、缓存及输出。全局 wall time MUST 从请求开始累计且不得按 TU/worker 重置；CPU 和内存预算 MUST 同时约束扫描器及其子进程。平台无法强制某项请求预算时 MUST 在分析前公开 unsupported 能力或保守失败，不得声称预算已执行。

#### Scenario: 多个 TU 共用 wall deadline
- **WHEN** 前几个 TU 已消耗大部分全局 wall budget
- **THEN** 后续 TU 只能使用剩余时间，达到 deadline 后停止启动新工作并产生稳定预算 frontier

#### Scenario: Clang 超出内存预算
- **WHEN** AST 前端子进程超过请求的内存上限
- **THEN** 进程被隔离终止，对应 TU 计入 failed/unknown，其他已完成结果被保留

### Requirement: 逻辑预算必须在稳定排序后截断
文件数、artifact/BC 字节、worker 输出、facts、evidence candidates、rule candidates、assessment、evidence refs、related locations、diagnostic 和 suppression records SHALL 在候选按规范稳定键排序后执行限制。预算耗尽 MUST 记录预算名称、limit、稳定逻辑用量、受影响 rule/scope 和最后完成 frontier；未处理范围不得计为 not_matched。

#### Scenario: rule candidate 上限
- **WHEN** 稳定排序后的候选数量超过 `max_rule_candidates`
- **THEN** 只处理确定的前缀，剩余范围计入 unknown，重复运行产生相同 frontier

#### Scenario: diagnostic 上限
- **WHEN** 普通诊断达到 `max_rule_diagnostics`
- **THEN** 扫描器聚合或截断普通诊断并保留一个终止槽发布预算耗尽诊断

### Requirement: 易波动资源观测不得污染语义身份
scan result SHALL 记录预算 limit、稳定逻辑用量和 frontier，但实际 wall、CPU、RSS 样本 MUST 写入独立 validation/benchmark telemetry，不得进入 finding/assessment/cache key 或 scan semantic digest。相同输入因调度抖动产生不同采样值时语义结果仍须稳定。

#### Scenario: 两次运行耗时不同
- **WHEN** 相同输入两次运行的 wall time 或峰值 RSS 不同且均未超限
- **THEN** scan semantic digest、stable IDs 和集合排序保持相同，差异只出现在独立 telemetry
