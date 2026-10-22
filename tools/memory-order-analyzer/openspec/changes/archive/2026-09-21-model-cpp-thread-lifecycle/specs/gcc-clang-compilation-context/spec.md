## ADDED Requirements

### Requirement: Capture C++ standard-library and ABI identity for lifecycle analysis

GCC/Clang C++17/C++20 编译上下文 SHALL 为 A3 记录生产与分析标准库 vendor/version、C++ ABI、target、异常/RTTI/线程配置、resource/sysroot、关键 driver 默认及可验证的头文件/wrapper digest，并把它们纳入 profile、依赖和缓存身份。无法恢复 GCC 隐式标准库或 Clang 重放不等价时 MUST 降级；C11/C17 profile SHALL 不加载或依赖这些 C++ 字段才能继续直接 pthread 分析。

#### Scenario: GCC uses implicit libstdc++ defaults
- **WHEN** 编译数据库没有显式标准库 include，但锁定 GCC 安装与依赖发现可以确定实际 libstdc++ 版本和路径
- **THEN** 记录可审计来源和完整 profile，再由 Clang 等价重放；无法恢复时报告 profile gap

#### Scenario: C17 pthread analysis runs beside C++ profiles
- **WHEN** 同一 scope 含 C17 pthread TU 与 C++20 `std::thread` TU
- **THEN** 两者保持独立语言/profile/cache 身份，C17 TU 不加载 C++ 标准库模型或以其结果补全 C 证据
