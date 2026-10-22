## ADDED Requirements

### Requirement: CMake 测试注册必须保留静态来源和作用域

CMake Analyzer SHALL 恢复 enable_testing、add_test(NAME name COMMAND local-executable-target literal-args...)，支持已有有界字面变量/列表展开。注册 SHALL 关联有效目录、配置、条件、命令参数与唯一普通本地 executable target，支持收集后解析前向引用，不执行 CMake 或测试发现。旧式无 NAME 签名 SHALL 保留候选，MUST NOT 套用新签名的 target 解析规则。

#### Scenario: 架构分支中的注册

- **WHEN** 已引用目录启用测试，并在受支持目标 CPU 分支注册普通本地 executable
- **THEN** SHALL 展示启用位置、注册位置、架构条件、target 定义与 source membership，分别表达运行选择和编译选择
- **AND** 目标 CPU SHALL 来自扫描上下文，不从 x86 已观察配置推断

#### Scenario: 前向引用或跨目录同名测试

- **WHEN** 注册出现在 target 声明前，或两个目录注册同名测试
- **THEN** SHALL 通过受支持作用域和配置解析前向 target，并隔离不同目录测试身份
- **AND** 冲突声明或 target 解析歧义 SHALL 保持 unknown，不依赖遍历顺序合并

#### Scenario: 动态或不支持的注册

- **WHEN** 注册依赖未知 option/cache、生成器表达式、函数/宏、外部 executable、shell wrapper、动态发现或无法解释的运行过滤
- **THEN** SHALL 保留相关事实、命令参数与 unknown 断点，不确认该命令实际调用哪一个测试 body
- **AND** MUST NOT 执行工具补证或将已忽略命令当成安全完整注册

### Requirement: 测试禁用属性不得撤销独立编译依赖

Analyzer SHALL 支持同目录 set_tests_properties 的字面 DISABLED 布尔值与可证明的命令顺序；未知属性值、作用域冲突或影响运行语义的未支持属性 SHALL 使相关运行关系保持 unknown。运行禁用 SHALL 只影响对应测试注册/运行选择，不改变独立证明的 target 编译关系。

#### Scenario: 已禁用测试仍被编译

- **WHEN** RISC-V 配置下测试注册 DISABLED 为真，但其 executable 的 x86 source 仍被确定编译
- **THEN** SHALL 区分已禁用的测试运行与仍存在的 x86 编译依赖
- **AND** MUST NOT 将该编译问题降为 x86_test_guarded 或安全就绪

#### Scenario: 属性顺序未知

- **WHEN** DISABLED 来自未知展开或不能证明先后的冲突赋值
- **THEN** 对应测试运行选择 SHALL 为 unknown 并保留全部可定位来源
- **AND** MUST NOT 用文件排序或最后遍历结果替代赋值证明
