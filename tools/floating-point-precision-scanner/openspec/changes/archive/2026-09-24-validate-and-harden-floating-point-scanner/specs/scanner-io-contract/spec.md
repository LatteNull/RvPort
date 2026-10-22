## ADDED Requirements

### Requirement: Schema 1.4 必须显式表达策略日期和缓存配置
scan request schema 1.4 SHALL 增加可选 ISO 8601 完整日期 `policy_as_of`、版本化 cache 配置以及新增结果/逻辑预算。cache 配置 MUST 包含 `off|read-only|write-only|read-write` 模式和经过允许根校验的 cache root。旧 schema 1.0–1.3 MUST 保持原解析、默认规则和无过期 suppression 行为；未知字段或不支持版本继续在分析前拒绝。

#### Scenario: 旧请求不读取当前日期
- **WHEN** schema 1.3 请求包含 suppression 且没有 policy 日期
- **THEN** suppression 按旧协议处理，系统当前日期不影响结果

#### Scenario: 有效 schema 1.4 缓存请求
- **WHEN** cache mode、root、预算和 policy 日期均合法
- **THEN** 规范化请求固定全部语义配置且不在结果中暴露绝对 cache root

### Requirement: Suppression 过期必须由显式 policy 日期决定
schema 1.4 suppression MAY 包含 `expires_on`。包含 `expires_on` 时请求 MUST 提供 `policy_as_of`；当 `policy_as_of` 晚于 `expires_on` 时 suppression MUST 过期、candidate finding 保持可见，并产生包含中英文理由的审计记录和诊断；日期相等时 suppression 仍有效。核心扫描器 MUST NOT 读取系统当前时间判断有效期。

#### Scenario: Suppression 已过期
- **WHEN** `policy_as_of=2026-10-01` 且匹配 suppression 的 `expires_on=2026-09-30`
- **THEN** finding 保持可见，suppression audit 标记 expired 且 suppressed 计数不增加

#### Scenario: 缺少 policy 日期
- **WHEN** schema 1.4 suppression 提供 expires_on 但请求未提供 policy_as_of
- **THEN** 请求在分析前以 invalid_request 和稳定诊断拒绝

### Requirement: 结果必须公开稳定预算、缓存和 suppression 审计
schema 1.4 result metadata SHALL 公开预算 limits、稳定逻辑用量、frontiers、cache schema/version 与 hit/miss/corrupt/write 计数；suppression audit SHALL 公开有效、过期、未匹配或预算未记录状态及双语理由。实际 wall/CPU/RSS telemetry、绝对 cache root 和系统时间 MUST NOT 进入 scan result semantic digest。

#### Scenario: 热缓存命中
- **WHEN** source facts、IR facts 或 evidence 从有效缓存读取
- **THEN** metadata 增加对应 hit 计数，但 findings、assessments 和 semantic digest 与冷缓存运行相同

### Requirement: Validation result 必须使用独立协议
质量与性能验证 SHALL 输出独立 `FloatingPointScannerValidationResult@1.0`，不得将 TP/FP/FN、reviewer、benchmark telemetry 或宿主资源采样混入生产 scan result。validation result MUST 通过独立 schema 校验并引用被验证 scan result、corpus 和 oracle digest。

#### Scenario: Validation 报告序列化
- **WHEN** corpus 验证和 benchmark 完成
- **THEN** 独立报告包含质量和性能分母，生产 scan result schema 与语义摘要保持不变
