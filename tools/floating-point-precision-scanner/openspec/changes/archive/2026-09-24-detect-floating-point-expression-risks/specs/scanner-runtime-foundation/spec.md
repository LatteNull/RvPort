## MODIFIED Requirements

### Requirement: 运行时执行已注册核心规则并保留 facts-only 兼容模式
扫描器 SHALL 在 source facts、IR facts、evidence、profiles 和可选 build contexts 通过各自 schema/摘要校验后，按 registry 稳定顺序执行请求启用的十条规则，并将每个 rule/scope 的结果记录为 `matched`、`not_matched`、`unknown`、`skipped` 或 `failed` assessment。descriptor SHALL 驱动所需 source/IR fact kinds、profile/build-context fields、IR capability、assessment scope、evidence mode 和预算；运行时不得为规则硬编码未声明依赖。只有 `matched` SHALL 形成 finding candidate；`unknown`、`skipped` 和 `failed` MUST 进入独立分母和诊断，且不得被统计为安全。有效 suppression 在稳定 candidate 身份生成后应用。空规则集合 SHALL 跳过规则层、保持 `findings=[]` 并明确 `analysis_scope=facts_only`。

#### Scenario: schema 1.3 默认规则全部完成
- **WHEN** schema 1.3 请求省略规则配置，十条默认规则的必需 facts/evidence/profile/build-context 均完整且执行成功
- **THEN** 结果标记 `analysis_scope=migration_risks`，公开十条规则、依赖摘要及逐状态 assessment 分母，并发布或审计抑制所有 matched candidates

#### Scenario: 显式空规则集合
- **WHEN** 请求设置 `rules.enabled=[]`
- **THEN** 扫描器只完成 facts/evidence pipeline，结果标记 `facts_only`，且不把空 findings 描述为无迁移风险

#### Scenario: 规则只依赖 AST
- **WHEN** 启用规则的 descriptor 不要求 IR，且所需 source facts/profile 完整
- **THEN** 该规则可完成 assessment，不因请求未提供共享 BC 而无关地变为 unknown

#### Scenario: 单条规则发生可隔离异常
- **WHEN** 一条规则在某个 scope 内抛出已分类的可隔离异常，而其他规则输入有效
- **THEN** 该 scope assessment 为 `failed`，其他规则继续，整体状态按可用与失败 assessment 保守聚合

## ADDED Requirements

### Requirement: 函数摘要和表达式规则执行必须有界且确定
运行时 SHALL 对函数摘要传播深度、调用边、comparison/reduction candidates、IR use-chain、related locations、suppression records 和每规则 wall/CPU 设置显式预算。所有候选 MUST 在截断前按 rule order、scope、规范化位置和 semantic fact IDs 排序；达到预算 MUST 保留已完成结果并记录最后稳定 frontier，且并发完成顺序不得改变输出。

#### Scenario: fenv 调用传播达到深度上限
- **WHEN** 直接调用摘要链超过配置传播深度
- **THEN** 已完成摘要保留，剩余调用边产生 unknown assessment/诊断和稳定 frontier

#### Scenario: 归约候选顺序变化
- **WHEN** 相同输入以不同 worker 完成顺序产生相同归约候选集合
- **THEN** 预算截断保留相同 candidates，assessment/finding/suppression 顺序和摘要完全一致
