## ADDED Requirements

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
