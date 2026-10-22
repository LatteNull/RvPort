# cpp-raii-synchronization-profiles

## Purpose

定义经实测验证、与工具链和标准库 ABI 精确绑定的 C++ RAII 同步 profile 及其保守采用边界。

## Requirements

### Requirement: Bind synchronization profiles to verified toolchain identity

每个 `CppRaiiSynchronizationProfile` SHALL 绑定 compiler family/version、C++17/C++20、standard-library kind/version、ABI、target triple、data layout、异常/RTTI 选项、相关头文件或 wrapper 指纹及模型版本。profile 只有在锁定开发环境实际编译、提取并验证声明的 mutex/RAII 形状后才可标记 `verified`。

#### Scenario: Exact libstdc++ profile matches
- **WHEN** request 的全部编译、标准库、ABI、target 和指纹字段与已实测 profile 完全一致
- **THEN** 系统可采用该 profile 的同步摘要并记录 profile identity 和验证证据

#### Scenario: A nearby version is not registered
- **WHEN** 标准库 vendor 相同但版本、ABI、target、异常选项或 wrapper 指纹任一不匹配
- **THEN** profile 不合格并产生 `library-profile-mismatch` frontier，不按相似名称或版本猜测

### Requirement: Keep synchronization summaries separate from thread lifecycle profiles

A4 profile MAY 引用 A3 的共同编译 fingerprint，但 mutex/RAII wrapper eligibility、owner 状态转换、系统边界和摘要摘要值 SHALL 独立版本化。更新 A4 profile MUST NOT 改变 A3 callback、join/detach 或线程对象语义。

#### Scenario: A3 is eligible but A4 is not
- **WHEN** 标准库线程 wrapper 匹配 A3 profile，而 mutex wrapper 指纹未通过 A4 验证
- **THEN** 保留 A3 生命周期结果，A4 为 partial/unknown，不能借用 A3 eligibility 建立同步

### Requirement: Validate libstdc++ and libc++ profiles independently

required gate SHALL 至少包含一个实际 libstdc++ profile 和一个实际 libc++ profile 的编译、source/IR 提取、摘要绑定与真值断言。一个 vendor 的结果 MUST NOT 替代另一个 vendor，合成 schema fixture MUST NOT 宣称运行时支持。

#### Scenario: Only libstdc++ is available
- **WHEN** libstdc++ required profile 已实测但 libc++ profile 无法实际编译或提取
- **THEN** A4 required gate 保持未完成并记录环境阻塞，不把 libc++ 标记为 verified

### Requirement: Treat system boundaries and wrapper drift conservatively

profile SHALL 明确系统声明/定义边界、允许的 wrapper/callee 形状、参数到 mutex 的绑定和异常出口。scope 内用户 wrapper 与系统摘要冲突、wrapper 漂移或底层调用归属不唯一时 MUST 产生冲突/frontier，不得删除候选或重复生成同步实例。

#### Scenario: A user wrapper resembles a library helper
- **WHEN** 用户定义与 profile helper 具有相似名称但实体、linkage 或系统边界不一致
- **THEN** 不采用系统摘要，并按用户跨 TU wrapper 规则解析或降级
