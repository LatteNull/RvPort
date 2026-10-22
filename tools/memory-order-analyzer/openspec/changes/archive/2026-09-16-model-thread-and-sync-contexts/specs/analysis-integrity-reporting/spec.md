## ADDED Requirements

### Requirement: Validate P3 cross-layer evidence integrity

系统 SHALL 在消费 P3 产物前验证 BC、P1、P2、ThreadLocalFacts、ExecutionOrderFacts、ThreadContextGraph 和报告之间的 digest、scope/profile、版本、函数/调用/线程归属及引用闭包。P3 解释或补充 SHALL 不覆盖 P1/P2 原始诊断；缺少、矛盾、陈旧或伪造证据 MUST 阻止相关关系提升为确定事实。

#### Scenario: An order edge references another invocation

- **WHEN** 执行顺序边的端点属于不同且没有合法调用/生命周期连接的 invocation 或 ThreadInstance
- **THEN** 完整性校验拒绝该边并降低相关阶段状态，不让它参与 must-before、MHP 排除或同步组合

#### Scenario: A P2 summary is replaced after local thread extraction

- **WHEN** ThreadLocalFacts 仍引用旧 EffectSummary digest，而 artifact store 中提供了新摘要
- **THEN** P3 依赖被判陈旧并重算或失败，不把不同代际的效果与线程身份混合

### Requirement: Preserve P3 plans, unknown frontiers and completeness denominators

系统 SHALL 在分析前登记显式根、scope 成员和可见调用计划，并在报告中保留已处理、partial、failed、not_run、合并及未展开项。回调、句柄、线程、MHP、mutex、原子候选和定位统计 SHALL 给出清晰 hit/total；不得通过过滤未知项、超限项或不可读取成员提高完整率。

#### Scenario: A recursive spawn reaches the instance limit

- **WHEN** 已发现部分实例后触发线程实例预算
- **THEN** 报告保留原始入口、已知实例、合并桶、未展开 frontier 和实际预算，thread_modeling 不得为 complete

#### Scenario: Source mapping is unavailable but IR evidence remains usable

- **WHEN** BC 无 debug 信息而线程/顺序 IR 事实可生成
- **THEN** source_mapping 独立为 partial/unavailable，IR 分析结果保留，命令以 2 退出且不伪造源码位置

### Requirement: Isolate P3 policy and cache identities from earlier stages

P3 策略、模型或展示协议变化 SHALL 仅使受影响派生缓存失效，不修改 P1 ArtifactKey 或 P2 EffectSummary 身份；P3 request_hash SHALL 包含实际 roots、模型、预算和依赖，而可复用上下文模板身份 SHALL 排除调用者特有实例字段。

#### Scenario: Only the pthread model version changes

- **WHEN** BC、P1/P2 产物不变而 `posix-pthread` 模型版本变化
- **THEN** 重算 P3 局部采用、上下文和报告，不要求重编译 BC 或重写 P1/P2 历史产物
