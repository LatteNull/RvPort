## ADDED Requirements

### Requirement: Bind RAII source operations to actual IR synchronization effects

SourceIRBinding SHALL 为每个 mutex/owner 构造、析构、move、lock/unlock 和 cleanup 候选记录 AST entity、IR call/invoke、参数/返回、对象 path、CFG/异常边、profile summary 及绑定基数。只有唯一或显式允许的有限绑定、同 profile/ABI 和完整引用闭包才可进入 A4 证明；名称、debug location 或类型相似 MUST NOT 单独采用。

#### Scenario: One destructor maps to normal and cleanup IR calls
- **WHEN** AST 析构在正常出口和异常 cleanup 各对应一个实际 unlock 调用
- **THEN** binding 分别保存带 guard 的 IR effect，并允许状态机检查所有出口是否闭合

#### Scenario: An IR lock call has no unique source owner
- **WHEN** 底层 wrapper 可绑定多个 guard/owner 且无法按对象和路径区分
- **THEN** 保留 binding 候选和歧义原因，不生成唯一 owner acquire

### Requirement: Reject AST-only synchronization completion

AST-only 模式 MAY 保存 mutex、owner、词法 lifetime 和调用形状作为 source candidate，但 MUST NOT 建立成功 acquire/release、held-region、mutex proof、SW、HB、risk 或 discharged。

#### Scenario: BC generation fails after successful AST extraction
- **WHEN** AST 完整识别 `lock_guard`，但该 TU 的 IR 生成或 A4 worker 失败
- **THEN** 输出 source candidate 和缺失 IR/profile 证据，结果为 partial/unknown
