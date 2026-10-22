## ADDED Requirements

### Requirement: Extract independent C++ thread ABI and object facts

LLVM thread worker SHALL 为 A3 生成独立的 C++ wrapper call、参数角色、calling convention、返回/异常出口、线程对象/native handle token、load/store/cast/phi/select、move 和 join/detach 候选事实，并引用原始 P1/P2/P3 节点而不修改其身份。只有 `CppThreadLibraryProfile` 完全匹配时才能给 wrapper 赋予规范化角色；局部事实存在 MUST NOT 单独视为已采用生命周期模型。

#### Scenario: A verified entry broker carries one callable payload
- **WHEN** wrapper 的 ABI、参数角色、对象 token 和 profile 与注册模型一致
- **THEN** 输出可审计 broker/callable payload 候选及成功/异常出口，交由 A3 组合层与 AST 证据求交

#### Scenario: A wrapper signature is similar but incompatible
- **WHEN** 符号名称相似但 calling convention、参数数量、类型布局或 target 不匹配
- **THEN** 保留原始调用并产生 wrapper mismatch，不赋予 construct/join/detach 角色

### Requirement: Distinguish standard-library broker calls from direct pthread calls

worker SHALL 标记已采用标准库边界内作为实现细节的 pthread create/join 调用，并以 model-owned evidence 关联其外层 C++ 操作；不得把同一底层调用同时作为独立用户 pthread 生命周期和 A3 生命周期。边界不完整或调用来自用户 wrapper 时 MUST 保留两种候选的冲突/unknown，而不是静默去重。

#### Scenario: std thread lowers to pthread create
- **WHEN** 一个已采用构造 broker 唯一包含模型预期的底层 `pthread_create`
- **THEN** 底层调用只作为该 A3 构造的实现证据，线程实例和分母不重复

#### Scenario: Ownership of a pthread call is ambiguous
- **WHEN** 无法证明底层调用属于标准库 broker还是用户 wrapper
- **THEN** 记录冲突和完整性缺口，不任意删除 pthread 候选或生成双重实例
