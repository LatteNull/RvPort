## ADDED Requirements

### Requirement: Record A4 synchronization compilation identity without coupling C profiles

GCC/Clang C++17/C++20 编译上下文 SHALL 记录 A4 所需的标准库、版本、ABI、target、异常/RTTI 选项、wrapper/header fingerprint 和模型 identity，并纳入请求与缓存摘要。C11/C17 profile SHALL 保持独立且不得加载 C++ 标准库同步模型。

#### Scenario: One scope mixes C17 pthread and C++20 RAII
- **WHEN** 显式 scope 同时包含 C17 直接 pthread mutex TU 和 C++20 `lock_guard` TU
- **THEN** 每个 TU 使用自己的语言/profile identity，C17 结果不依赖或继承 C++ A4 profile

#### Scenario: Driver defaults hide standard-library identity
- **WHEN** compile command 未显式写出标准库或 ABI 选择且不能从可审计编译上下文确定
- **THEN** A4 profile eligibility 为 unknown/partial，不以主机默认值静默补全
