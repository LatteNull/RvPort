# KB Scanner CMake 源码分析规范

## Purpose

定义 CMake 源码的只读、有界解析与目标选择证明、参数作用域和配置拒绝分析，以及对应的单元覆盖和人工审校门禁。

## Requirements

### Requirement: CMake 源码必须经隔离适配器恢复可定位事实
Scanner SHALL 只读分析 CMakeLists.txt 与 workspace 内普通 .cmake，区分源码和 File API JSON，恢复命令、参数及完整 span，并转换为 scanner-owned records。未被已知入口引用的文件 SHALL 保留事实但不得被当作激活配置。解析依赖 SHALL 经独立容器验证并锁定，第三方节点 MUST NOT 泄漏到后续阶段。

#### Scenario: 多行命令和普通 cmake 片段
- **WHEN** 项目包含多行命令、引号/括号参数、注释及孤立 .cmake 文件
- **THEN** adapter SHALL 准确恢复受支持事实及命中位置，孤立文件不生成确定激活关系
- **AND** 注释内伪命令 MUST NOT 成为实际选择或拒绝证明

#### Scenario: 畸形输入和解析失败
- **WHEN** 语法错误、原生解析边界失败或解析预算耗尽
- **THEN** scanner SHALL 通过既有故障边界有界返回 partial/unknown Diagnostic 并保留可验证事实
- **AND** 不得将失败视为无风险或执行 CMake 来补证

### Requirement: CMake 求值必须有界且遵守目标配置与作用域
Evaluator SHALL 支持字面 set、简单变量/列表展开、list(APPEND)、有界 if/elseif/else、括号、NOT/AND/OR、已知布尔值、STREQUAL、安全 MATCHES 子集和本地 include/add_subdirectory。它 SHALL 区分目录、变量、target、参数顺序及配置；未知 cache/option、生成器表达式、函数/宏、未知命令副作用 SHALL 污染所影响的状态，不能跳过后声称确定。目标 CPU SHALL 来自 ScanContext，其他未知目标信息 MUST NOT 从宿主或 x86 已观察配置推断。

#### Scenario: 完整 CPU 条件
- **WHEN** 入口仅按 CMAKE_SYSTEM_PROCESSOR 的受支持条件区分 x86 和 RISC-V
- **THEN** 求值 SHALL 使用目标 CPU 确定对应分支，并保留条件与变量来源
- **AND** MUST NOT 建模 RISC-V 错误选中 x86 的交叉编译误选

#### Scenario: 外部覆盖和动态副作用
- **WHEN** 分支依赖未证明的 option/cache、生成器表达式或未知命令可能修改的变量
- **THEN** 相应分支及依赖选择 SHALL 为 unknown，不得用默认值或旧变量值证明 selected/inactive

#### Scenario: 路径与复杂度边界
- **WHEN** include 指向根外、形成循环，或展开/匹配/命令数超过预算
- **THEN** scanner SHALL 停止相关求值并给出可定位的稳定 reason
- **AND** MUST NOT 读取根外内容、执行命令或无限展开/匹配

### Requirement: CMake 目标参数必须证明实际作用对象
Scanner SHALL 恢复 add_library/add_executable/target_sources、target_compile_options/definitions、目录级编译选项/定义及必要的本地 target link/include 关系，依据 PRIVATE/PUBLIC/INTERFACE、目录、配置和源码归属建立关系。未知传播 SHALL 保持 unknown，机器参数 MUST NOT 无依据地转换成条件宏。

#### Scenario: 参数只属于一个目标
- **WHEN** 两个 target 中只有一个使用 -mavx2 或 -DUSE_AVX2
- **THEN** 只有被证明归属该 target 且适用的源码 SHALL 关联相应参数；另一个 target 不得借用同名宏或选项
- **AND** -D/-U 的顺序与源码覆盖 SHALL 由现有宏作用规则处理

#### Scenario: usage requirement 传播
- **WHEN** 本地 target_link_libraries 与 PUBLIC/INTERFACE/PRIVATE 的传播关系完整可解析
- **THEN** scanner SHALL 只沿正确方向传播适用编译信息并保存来源
- **AND** 外部包、循环或动态 target 关系 SHALL 保留 unknown，不能猜测整个目录共享参数

### Requirement: CMake 显式拒绝必须尊重控制流终止和必需范围
Analyzer SHALL 仅在入口、目标条件、执行顺序及必需范围完整时，为 message(FATAL_ERROR) 生成配置拒绝 proof 和 missing_riscv_selection_path Observation。终止点后的事实 SHALL 保留，但 MUST NOT 生成该配置的后续 selected target/source，也不得作为安全互斥排除证明。最终 blocking SHALL 由 Classifier 决定。

#### Scenario: 根配置先拒绝后声明 AVX 目标
- **WHEN** 必需入口对目标 RISC-V 确定到达 FATAL_ERROR，之后才声明 AVX library
- **THEN** scanner SHALL 证明该入口配置拒绝，并保留后续源码/参数事实
- **AND** MUST NOT 声称后续 library 已在 RISC-V 配置中选中或已安全隔离

#### Scenario: 拒绝条件或入口未知
- **WHEN** fatal 位于未引用片段、可选模块或未知条件内
- **THEN** scanner SHALL 限定其作用范围或保持 unknown，不得将它升级为项目级确定阻断

### Requirement: CMake 与风险修复必须通过隔离覆盖及人工审校
本 change 的所有新增和修改业务模块 SHALL 登记隔离单元测试，覆盖正常、边界及异常路径，并在独立 kb-scanner-test 容器使项目整体与每个受影响模块达到至少 90% 行和 90% 分支覆盖率。统计 SHALL 纳入未加载的项目自有可执行源码，排除项明确说明；组件/合同/端到端测试不得替代单元覆盖。

#### Scenario: 模块和安全验收
- **WHEN** 执行单元 inventory、原生解析组件及固定 demo-test1/最小反例回归
- **THEN** SHALL 分别报告可复跑命令、统计范围、逐模块/整体覆盖、报告路径与人工差异账本
- **AND** 未达门槛 SHALL 保持未完成，不安装本机依赖、不执行被扫描项目命令、不更新生产容器

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
