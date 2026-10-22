## ADDED Requirements

### Requirement: Maintain an offline C++ thread lifecycle truth corpus

项目 SHALL 建立带人工裁决的 C++17/C++20 单 TU 与物理跨 TU 生命周期语料，覆盖锁定 libstdc++/libc++ profile、自由函数、lambda、成员函数、简单 functor、move、join、detach、joinable、析构、构造失败/异常、无 debug、开放 scope、profile/ABI mismatch、递归/循环和预算。truth SHALL 分别声明预期 callable、对象 lineage、ThreadContext、ThreadInstance、生命周期关系和 unknown 原因，不以编译成功、执行频率或外部工具作为 oracle。

#### Scenario: A joined lambda case is reviewed
- **WHEN** 人工 truth 指定唯一 lambda callback、一个动态实例和条件化 join relation
- **THEN** 验证器逐项比较身份、关系、guard、证据与完整性，而非只检查命令退出零

#### Scenario: A detached member-function case is reviewed
- **WHEN** truth 预期对象/成员 callback 可绑定但 detach 后仍可能并行
- **THEN** 断言存在 detach、没有 join-complete/not-parallel，并保存 receiver provenance

### Requirement: Preserve independent C pthread regression denominators

A3 语料 SHALL 持续运行 C11/C17 直接 `pthread_create`/`pthread_join` 正反与 unknown 基线，并将 C11、C17、C++17、C++20 的 planned/completed/failed/unknown 分母分别报告。C 夹具不得加载 C++ 标准库模型，C++ 新能力不得被用于补全 C 路径。

#### Scenario: C++ lifecycle cases pass while a C baseline regresses
- **WHEN** C++17/C++20 A3 truth 全部匹配但任一 C11/C17 pthread 基线身份或关系改变
- **THEN** required semantic gate 失败，不以合并分母或 C++ 结果掩盖回归
