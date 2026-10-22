## ADDED Requirements

### Requirement: 预算和资源故障必须保留稳定未分析分母
任一 wall、CPU、RSS、文件、字节、输出、facts、evidence、rule、diagnostic、suppression 或结果大小预算耗尽时，扫描器 SHALL 停止新增受影响工作、终止或隔离相关 worker、保留已安全完成结果，并公开稳定 frontier 与未分析 planned 分母。存在可用结果时状态 MUST 为 `partial`，没有任何请求所需可用结果时 MUST 为 `failed`；不得以空 findings 表示安全。

#### Scenario: 全局 wall budget 在部分完成后耗尽
- **WHEN** 部分 source/evidence/assessment 已完成后共享 deadline 到期
- **THEN** 已完成结果原子发布、剩余范围计入 unknown/failed、状态为 partial 且退出码为 4

#### Scenario: 输出大小预算在发布前耗尽
- **WHEN** 完整结果超过允许的结果字节数
- **THEN** 既有正式结果保持不变，扫描器发布安全的失败状态或旁路最小诊断，不能截断 JSON 冒充完整结果

### Requirement: 缓存故障必须与分析输入故障分离
缓存 miss、损坏、不兼容、路径越界和发布失败 SHALL 使用独立稳定 diagnostic code。可以从可信输入重新计算时，缓存故障 MUST NOT 单独把扫描状态降为 partial/failed；无法重新计算时，状态由缺失的 source/IR/evidence 决定，而不是把缓存视为真值来源。

#### Scenario: 损坏缓存可重新计算
- **WHEN** 缓存摘要无效但源码、编译上下文和工具链有效
- **THEN** 扫描器诊断 cache corruption、重新计算并可返回 complete

### Requirement: 诊断预算必须保留根因和可操作性
重复诊断 SHALL 按稳定 code、stage、profile/TU 和安全根因聚合。达到诊断预算时 MUST 保留各阻断 stage 的代表根因、总出现数、受影响分母和一个预算终止记录；路径、源码、环境变量、凭据、堆栈和缓存根必须按现有脱敏规则处理。

#### Scenario: 大量 TU 缺少同一头文件
- **WHEN** 缺失头文件产生的原始诊断数超过上限
- **THEN** 输出一个或有界代表诊断及总计数，并保留 diagnostic budget 终止记录

### Requirement: 故障注入不得进入生产协议
测试 SHALL 通过可注入 clock、resource sampler、process runner、cache store、serializer、fsync 和 replace 精确触发异常。生产 scan request/schema MUST NOT 提供随机故障开关、任意异常类型或测试路径注入字段。

#### Scenario: 单元测试注入 fsync 失败
- **WHEN** 测试适配器在缓存或结果 fsync 阶段抛出错误
- **THEN** 原子恢复和状态映射可被独立断言，生产请求协议不包含该注入配置
