## ADDED Requirements

### Requirement: 多版本 default 缺口必须有适用语义和范围闭合证据

Classifier SHALL 仅在机制确认为多版本、适用 compiler/language/target 规则要求 default、相关局部输入完整且同配置内证明未提供时形成 default 缺口分类，默认 actionable_non_blocking/medium。孤立 target 特化、声明-only、未知规则、条件未决和截断 SHALL 不被当作完整缺失证明。default 缺口 MUST NOT 自动表示全项目 portabilityGap 或真实编译失败。

#### Scenario: 缺口证据完整但无目标阻断证明
- **WHEN** 完整规则及范围证明缺少所需 default，但没有独立闭合的目标阻断 proof
- **THEN** SHALL 输出带范围/规则来源的可核查非阻断问题
- **AND** blocking SHALL 为 false，MUST NOT 声称执行过编译或整个项目不可迁移

#### Scenario: 无法验证定义或工具链
- **WHEN** 只有 default 声明、未知 compiler profile 或不完整版本绑定
- **THEN** SHALL 使用 unknown/medium 及明确 reason，保留原 fact 供后续分析补齐
- **AND** MUST NOT 输出 low/complete 或因零问题把项目评为 ready

### Requirement: 多版本补充不得掩盖原 x86 风险或重复同一事实

Detector/Classifier SHALL 保留已有 x86 dependency 与 Knowledge provenance，按精确 Evidence/group/configuration 合并同根因未决候选并区分独立依赖。default 存在与运行时未选中 MUST NOT 撤销原 blocker 或改变编译期依赖；Assessor SHALL 使用相同范围与完整性，不从版本数量推导 readiness。

#### Scenario: Default 或共享体含 intrinsic
- **WHEN** default 定义或 target_clones 共用体含确认 AVX intrinsic
- **THEN** SHALL 保持原 high 局部风险或独立闭合 proof 的 blocker，关联版本上下文
- **AND** 不得因 clone 数量重复生成该 intrinsic occurrence

#### Scenario: 完整排除与候选合并
- **WHEN** 同一 occurrence 被现有互斥目标 proof 完整排除，或旧 generic attribute candidate 与新组观察对应同一根因
- **THEN** 前者 SHALL 保持 inactive/low，后者 SHALL 合并解释并保留原始 provenance
- **AND** MUST NOT 跨 configuration 合并、删除独立 feature fact 或让成员边代替排除 proof
