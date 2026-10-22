## REMOVED Requirements

### Requirement: 基础扫描只生成事实而不发布风险结论
**Reason**: P1/P2 的 facts-only 安全边界已经完成使命，本阶段需要在不破坏事实层隔离的前提下执行已注册的核心迁移规则并发布 finding。

**Migration**: 默认请求改为执行四条核心规则；需要保留旧 facts-only 行为的调用方 SHALL 显式设置空规则集合 `rules.enabled=[]`，并依据新的 analysis version 和 metadata 解释结果。

本阶段的扫描器 SHALL 对所有计划 C/C++ 翻译单元执行 AST canonical facts 提取；当请求提供共享 BC 时，还 SHALL 执行 manifest 消费、LLVM facts 提取和 AST↔IR evidence 绑定。扫描器 MUST 保持 `findings` 为空，并 SHALL 在 metadata 中公开 `analysis_scope=facts_only`、`enabled_rule_count=0`、`ir_analysis`、请求/完成 profiles 和 source-mapping 状态。空 findings MUST NOT 被描述为已经完成风险检测或工程不存在浮点风险。

#### Scenario: 所有 AST 与共享 BC facts 完成
- **WHEN** 有效请求中的所有 C/C++ 翻译单元均成功产生所请求的 AST facts、LLVM facts 和必需 evidence
- **THEN** 结果状态为 `complete`、`findings` 为空，且 metadata 明确只完成事实和证据提取、未执行风险规则

#### Scenario: AST-only facts 完成
- **WHEN** 请求未提供共享 BC 且所有 AST canonical facts 成功
- **THEN** 结果可以为 `complete`，同时明确 `ir_analysis=not_requested`，不得暗示已验证最终 IR 行为

#### Scenario: 用户请求具体规则
- **WHEN** 本 change 请求包含非空规则启用列表
- **THEN** 扫描器在分析前返回 `invalid_request` 和双语 `rules_not_available` 诊断，而不是静默忽略

## MODIFIED Requirements

### Requirement: 稳定身份与确定性排序不依赖运行环境
扫描器 SHALL 使用规范化 schema/producer/profile/rule 版本、artifact/bundle digest、仓库相对 POSIX 路径、语义位置和语义载荷的 SHA-256 摘要生成稳定 facts、evidence、assessment 和 finding 身份，并 SHALL 使用显式稳定键排序 findings、diagnostics、assessments、source/IR facts、bindings、unknowns 和相关位置。finding ID MUST 包含 rule code/version、规范化 scope、主要位置、排序后的语义 evidence refs 与 profile fingerprints，但 MUST NOT 包含展示文本。绝对项目根、artifact root、临时目录、时间戳、进程 ID、locale 和并发完成顺序 MUST NOT 影响身份或语义输出。

#### Scenario: 相同证据重复执行规则
- **WHEN** 相同 source/IR facts、evidence、profiles 和规则版本在不同绝对工作区、artifact root 与调度顺序下执行
- **THEN** facts/evidence/assessment/finding ID、semantic digest 和序列化集合顺序完全相同

#### Scenario: 规则或语义证据发生变化
- **WHEN** 规范化源码位置、BC artifact key、IR 语义、binding method、profile fingerprint、rule major version 或语义 evidence refs 变化
- **THEN** 相应 assessment/finding 身份或 semantic digest 发生变化，避免与原结论错误合并

#### Scenario: 只有双语展示文本变化
- **WHEN** rule code/version、scope 和语义证据不变，仅中文或英文文案被修正
- **THEN** finding ID 保持不变，但完整输出文档摘要可以反映展示内容变化

## ADDED Requirements

### Requirement: 运行时执行已注册核心规则并保留 facts-only 兼容模式
扫描器 SHALL 在事实和 evidence 通过各自 schema/摘要校验后，按 registry 稳定顺序执行请求启用的规则，并将每个规则/scope 的结果记录为 `matched`、`not_matched`、`unknown`、`skipped` 或 `failed` assessment。只有 `matched` SHALL 生成 finding；`unknown`、`skipped` 和 `failed` MUST 进入独立分母和诊断，且不得被统计为安全。空规则集合 SHALL 跳过规则层、保持 `findings=[]` 并明确 `analysis_scope=facts_only`。

#### Scenario: 默认规则全部完成
- **WHEN** 请求省略规则配置，四条默认规则的必需 facts/evidence/profile 均完整且执行成功
- **THEN** 结果标记 `analysis_scope=core_migration_risks`，公开四条规则及逐状态 assessment 分母，并发布所有 matched findings

#### Scenario: 显式空规则集合
- **WHEN** 请求设置 `rules.enabled=[]`
- **THEN** 扫描器只完成 facts/evidence pipeline，结果标记 `facts_only`，且不把空 findings 描述为无迁移风险

#### Scenario: 单条规则发生可隔离异常
- **WHEN** 一条规则在某个 scope 内抛出已分类的可隔离异常，而其他规则输入有效
- **THEN** 该 scope assessment 为 `failed`，其他规则继续，整体状态按可用与失败 assessment 保守聚合
