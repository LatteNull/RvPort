## ADDED Requirements

### Requirement: Extract independent LLVM RAII synchronization candidates

LLVM worker SHALL 在不修改既有 pthread facts 的前提下登记普通 mutex wrapper call/invoke、参数对象、返回/异常状态、owner token、构造/析构/move、cleanup edge 和访问所在基本块；事实 SHALL 引用原始 IR identity、DataLayout、函数/TU/profile 和实际 CFG，不得用反汇编文本正则或函数名猜测替代 LLVM API 与 profile。

#### Scenario: Lock and unlock appear through ABI wrappers
- **WHEN** verified profile 将实际 IR call chain 识别为同一 mutex 的 acquire/release wrapper
- **THEN** worker 输出独立候选及完整来源，不直接生成跨线程同步或覆盖原 P3 pthread facts

#### Scenario: Wrapper ownership is ambiguous
- **WHEN** 无法证明底层 call 属于 profile 系统 helper、用户 wrapper还是两者重叠
- **THEN** 记录冲突和 frontier，不删除 pthread 候选或产生重复 mutex proof

### Requirement: Preserve exception and no-debug evidence

worker SHALL 保存 `invoke` 正常/异常后继、landingpad/cleanup、resume/return 和可用 debug location；无 debug 时 SHALL 仍以函数、块、指令和对象引用形成可审计 IR 证据，不得把位置缺失视为无 effect。

#### Scenario: Debug metadata is stripped
- **WHEN** C++ fixture 无 debug 但 IR 中保留实际 lock/unlock 与 cleanup CFG
- **THEN** A4 可继续形成 IR 级候选和证据链，报告位置降级但语义不因 debug 缺失而消失
