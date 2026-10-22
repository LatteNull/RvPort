## ADDED Requirements

### Requirement: CMake 宏作用证明必须保留 usage 路径且拒绝无依据覆盖
CMake usage 分析 SHALL 为有效编译参数保留定义命令、目录/target scope、每个本地 target link 使用点、source membership 和 configuration；PRIVATE/PUBLIC/INTERFACE 的传播方向 SHALL 与已有规范一致。只有已证明的有序参数序列才能应用覆盖；不同来源的冲突定义 SHALL 保持 unknown，MUST NOT 以行号或遍历排序伪造顺序。

#### Scenario: 多层本地 usage 传播
- **WHEN** INTERFACE 库提供定义，经 PUBLIC link 传给实际编译当前源码的消费者
- **THEN** scanner SHALL 给出各 link 与参数定义、target/source 的真实上游证明
- **AND** PRIVATE 或仅用于接口的参数 SHALL 不泄漏到不适用的目标自身或消费者

#### Scenario: 来自不同库的冲突宏
- **WHEN** 两个适用 usage 来源为 USE_AVX2 提供不同值，或者与取消定义的先后关系不能确认
- **THEN** scanner SHALL 保留全部来源并提供 conflicting-build-macro 或 unknown-argument-order 断点
- **AND** 无论文件排序或遍历顺序如何变化 SHALL 不生成确定的启用/禁用结论

#### Scenario: 相同定义合流与配置隔离
- **WHEN** 多个适用来源的宏操作和值相同，但其他配置给出不同值
- **THEN** scanner SHALL 在各自配置内合流等价定义且保留来源，不跨配置合并
- **AND** 原有未知 cache/option、动态 generator expression、外部 target 和循环 SHALL 继续保持未知
