## ADDED Requirements

### Requirement: 表达式规则缺失上下文必须按声明依赖传播
六条表达式风险规则 SHALL 在每个 scope 执行前校验 descriptor 声明的 canonical types、control-flow/use、loop/recurrence、call/environment summary、IR capability/evidence、profile 和 build-context 字段。缺失、unsupported、ambiguous、budget frontier 或事实冲突 MUST 使受影响 assessment 为 `unknown` 或 `failed`，并输出稳定双语 reason code；与规则无关的 unknown 字段 MUST NOT 阻断该 assessment。

#### Scenario: conversion 类型缺失
- **WHEN** `mixed-precision-conversion` 候选缺少 source 或 destination canonical type
- **THEN** 该候选 assessment 为 `unknown`，不按字面量后缀或变量名判断损失

#### Scenario: libm build context 缺失
- **WHEN** `math-library-variance` 需要比较两端库行为但任一 build context 的 libm identity/capability unknown
- **THEN** 该 assessment 为 `unknown`，其他不依赖 libm 的规则继续执行

#### Scenario: IR 与 AST 归约证据冲突
- **WHEN** AST 表示固定顺序累加，而 verified build-faithful IR 表示无法解释的不同 recurrence 或 flags
- **THEN** `reduction-reassociation` assessment 为 `unknown` 并报告 evidence conflict，不任选一侧生成确定 finding

#### Scenario: 无关 profile 字段未知
- **WHEN** architecture API 所需 declaration/target feature 完整，但数学库字段 unknown
- **THEN** `architecture-specific-fp-api` 按自身依赖完成，不因无关字段降级

### Requirement: 启发式规则失败不得伪装为确定性或无风险
启发式候选生成、rationale 选择、confidence 计算或 suppression 匹配失败时 SHALL 产生 `failed`/`unknown` assessment 或 suppression diagnostic，不得回退为 deterministic finding、`not_matched` 或静默删除。任何 heuristic finding MUST 保持人工确认标记；无法满足输出协议时不得发布该 finding。

#### Scenario: heuristic rationale 无模板
- **WHEN** 比较或归约规则命中一个未注册 rationale code
- **THEN** 对应 assessment 为 `failed` 或运行时安全失败，且不构造缺少中英文解释的 finding

#### Scenario: suppression 解析失败
- **WHEN** 源码 suppression 语法存在但 code、理由或范围不可验证
- **THEN** suppression 不生效，候选 finding 保留并输出可操作的双语诊断
