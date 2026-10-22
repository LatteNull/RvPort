## ADDED Requirements

### Requirement: Add independent four-language mutex and RAII truth sets

离线语料 SHALL 分别为 C11、C17、C++17、C++20 定义 planned、eligible、expected mode、mutex/owner/thread identity、proof/unknown 及风险结果。C SHALL 覆盖直接 pthread lock/unlock、跨 TU wrapper、全局和 struct/union 字段、相同/不同 mutex、未知 kind 与无锁反例；C++ SHALL 覆盖 `mutex`、`lock_guard`、受限 `unique_lock/scoped_lock`、move、异常、字段、跨 TU、no-debug、开放 scope、profile mismatch 和预算。

#### Scenario: C++ cases pass while C regresses
- **WHEN** C++17/C++20 A4 truth 全部匹配但 C11 或 C17 直接 pthread mutex identity/proof 改变
- **THEN** required semantic gate 失败，不以合并分母或 C++ 新能力掩盖 C 回归

#### Scenario: An unsupported ownership form is present
- **WHEN** fixture 使用 try/timed/recursive/robust mutex、未闭合 adopt/release 或通用指针别名
- **THEN** truth 明确要求 unknown/unsupported，不将其放入支持范围 risk/discharged 分母

### Requirement: Lock and review the archived mutex regression locally

项目 SHALL 保存 `memory-model-ir-checker/samples/safe/03_pthread_mutex.cpp` 的本地最小副本、来源路径、内容 hash、人工 truth 和 capability 声明；日常测试 MUST NOT 读取 sibling archive。只有 A4 完整证据链成立时才期望受限消解，历史工具输出不得作为 oracle。

#### Scenario: Local fixture hash changes
- **WHEN** 本地副本内容与记录 hash 或人工 truth 版本不一致
- **THEN** 验收失败并要求重新审核，不静默接受新的安全期望

### Requirement: Validate required standard-library profiles with real compilation

C++ truth SHALL 至少用锁定开发镜像实际编译一个 libstdc++ 和一个 libc++ profile，并执行 source/IR 提取、binding、A4 图和结果断言。合成 schema 数据 MAY 用于单元错误路径，但 MUST NOT 计入 runtime support 或 required truth 分母。

#### Scenario: A vendor fixture cannot compile
- **WHEN** required vendor/profile 因环境缺失无法真实编译和提取
- **THEN** 对应 profile 标记未完成且 required gate 失败，不用另一 vendor 或合成 fixture 替代
