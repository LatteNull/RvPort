## ADDED Requirements

### Requirement: 构建工作区必须安全且确定地发现受支持输入
正式 Build Workspace/Frontend SHALL 在 ScanContext 的输入和排除边界内发现 Make、Autoconf、已有 CMake/Meson/CTest 机器产物、compilation database 与 RPM spec 输入，并 SHALL 按规范化项目相对路径和输入 kind 确定性排序；它 MUST NOT 跟随逃逸 workspace 的路径或执行发现到的文件。

#### Scenario: 项目包含多类构建输入
- **WHEN** workspace 同时包含 C/C++、Makefile、configure、CMake File API reply、Meson introspection 和 RPM spec
- **THEN** composite workspace/frontend SHALL 把各输入路由到对应正式 adapter
- **AND** C/C++ 文件 SHALL 继续由既有 C/C++ Frontend 处理

#### Scenario: 构建路径逃逸 workspace
- **WHEN** symlink、include 或机器产物绝对路径指向 workspace 外部
- **THEN** scanner SHALL 拒绝读取该目标并产生结构化 Diagnostic
- **AND** 稳定 Entity/Evidence identity MUST NOT 包含机器绝对路径

### Requirement: 构建 Frontend 必须只产生 scanner-owned 可追溯事实
每个构建 adapter SHALL 从静态输入产生带 source span 或 JSON pointer、producer/version、parse mode、confidence 和配置 identity 的 scanner-owned Entity/Evidence；第三方语法节点、边界 model、parser 异常和 Legacy DTO MUST NOT 泄漏到 Normalizer、Analyzer 或 Detector。

#### Scenario: 构建语法可部分恢复
- **WHEN** 输入包含受支持语法和 parser ERROR/MISSING 或未知字段
- **THEN** Frontend SHALL 保留可定位 Evidence 并返回 partial Diagnostic
- **AND** 未恢复部分 MUST NOT 被解释为没有构建选择风险

#### Scenario: 重复扫描相同构建输入
- **WHEN** scanner/parser 版本、ScanContext 和输入字节相同
- **THEN** Entity/Evidence ID、排序和 Diagnostic 顺序 SHALL 相同
- **AND** identity MUST NOT 使用绝对 checkout 根、随机值、对象地址或时间

### Requirement: Make Frontend 与求值器必须实现安全有界语义子集
Make adapter SHALL 使用锁定的 tree-sitter-make 恢复 assignment、condition、include、target 和 recipe 边界；scanner-owned evaluator SHALL 支持字面文本、已知变量引用、`:=`、`=`、`+=`、`?=`、`ifeq/ifneq/ifdef/ifndef`、静态列表拼接、有限 workspace-local include、静态源码/目录/参数集合及架构 alias 比较，并 SHALL 对 include、展开、候选值和输出关系使用显式预算。

#### Scenario: Make 变量和条件选择 RISC-V 源码
- **WHEN** Makefile 通过受支持赋值、变量展开和互斥条件为 RISC-V target 选择源码或编译参数
- **THEN** evaluator SHALL 产生保留每次赋值、引用、条件和 SourceSpan 的确定选择事实
- **AND** Analyzer SHALL 能从 target architecture 追溯到最终源码或参数

#### Scenario: Make include 形成循环或越过预算
- **WHEN** 静态 include 循环或求值超过配置预算
- **THEN** evaluator SHALL 有界终止、保留已证明事实并返回 partial/unknown reason
- **AND** scanner MUST NOT 任意选择循环后的变量值

#### Scenario: Make recipe 或动态函数出现
- **WHEN** 输入包含 recipe、非白名单 function、动态 include、`eval`、普通 `$(shell ...)`、`!=` 或其他命令型求值
- **THEN** scanner SHALL 只保留对应 Evidence 和 unsupported/unknown Diagnostic
- **AND** 它 MUST NOT 启动 Make、shell 或任何外部命令

### Requirement: Autoconf 输入必须区分已生成 Shell 与受限 M4
已有 `configure`/`config.sub` SHALL 通过锁定的 tree-sitter-bash 恢复 assignment、case/if、架构模式和精确 command substitution；`configure.ac`/M4 SHALL 只识别批准的宏调用、字面参数和架构条件。scanner MUST NOT 运行 configure、Autom4te、M4 或任意宏命令。

#### Scenario: config.sub 接受 RISC-V triplet
- **WHEN** 已生成 config.sub 的可恢复分支包含目标 RISC-V 架构模式
- **THEN** scanner SHALL 建立 triplet selector 到 accepted branch 的可追溯选择关系
- **AND** 不相关 x86 branch SHALL 仅在互斥条件完整时标记 inactive

#### Scenario: config.sub 缺少 RISC-V 和通用路径
- **WHEN** 完整可恢复的架构选择只接受 x86 且没有 RISC-V 或通用 fallback
- **THEN** scanner SHALL 产生 `missing_riscv_selection_path` Observation 候选
- **AND** 它 MUST NOT 描述为 RISC-V 错误进入 x86 branch

#### Scenario: M4 包含可执行宏
- **WHEN** configure.ac 包含 `syscmd`、`esyscmd`、动态 include 或未知参数展开
- **THEN** adapter SHALL 返回 unsupported/unknown Evidence 与 Diagnostic
- **AND** scanner MUST NOT 执行或模拟其副作用

### Requirement: 已有构建机器产物必须只读并保留配置身份
Frontend SHALL 通过严格版本/边界校验读取已经存在的 CMake File API reply、Meson introspection、CTest 元数据和 compilation database，SHALL 保留 configuration、target、source、argument、dependency、artifact 与 schema provenance，并 MUST NOT 运行 CMake、Meson、CTest 或 compiler 来生成或补全这些产物。

#### Scenario: 机器产物确认 RISC-V target
- **WHEN** 已有 metadata 同时提供可验证的 RISC-V 配置 identity、target 和 source/argument/dependency
- **THEN** Analyzer SHALL 可建立 observed configuration 到这些选择项的 proof
- **AND** proof SHALL 引用具体输入文件和 JSON pointer/entry identity

#### Scenario: 机器产物缺失架构或已经过期
- **WHEN** metadata 没有目标架构 provenance、引用缺失文件或与源码静态事实冲突
- **THEN** scanner SHALL 保留 observed candidate 并返回 partial/unknown
- **AND** metadata MUST NOT 静默覆盖其他 producer 或被视为 RISC-V selected

#### Scenario: 机器产物不存在
- **WHEN** 项目未提交 CMake/Meson/CTest 机器产物
- **THEN** 对应 adapter SHALL 保持 unavailable 并允许其他静态输入继续分析
- **AND** 缺失产物 MUST NOT 触发 configure/setup/test 命令

### Requirement: RPM 必须由新轻量 Frontend 静态恢复架构选择
正式 RPM adapter SHALL 在新模块中恢复 section、`%ifarch/%ifnarch`、`ExclusiveArch/ExcludeArch`、依赖和构建/检查 section provenance，并 SHALL 将其转换为 scanner-owned Evidence；它 MUST NOT 导入或修改 Legacy parser，不得使用完整 RPM/specfile 求值环境。

#### Scenario: RPM 条件依赖包含 RISC-V 分支
- **WHEN** spec 的受支持架构条件为 RISC-V 选择 BuildRequires/Requires 或 section
- **THEN** Analyzer SHALL 建立 package architecture selector 到依赖/section 的选择关系
- **AND** 互斥 x86 条目 SHALL 保留 Evidence 并可标记 inactive

#### Scenario: RPM 架构约束排除 RISC-V
- **WHEN** `ExclusiveArch`/`ExcludeArch` 的完整静态值证明目标 RISC-V 不被允许
- **THEN** scanner SHALL 产生可追溯的目标路径缺口 Observation
- **AND** 最终 severity/blocking SHALL 留给后续 Classifier

#### Scenario: RPM 包含 shell Lua 或 include
- **WHEN** spec 包含 shell expansion、Lua、动态宏或 include
- **THEN** scanner SHALL 保留可定位 Evidence 并把依赖该值的选择标记 unknown
- **AND** scanner MUST NOT 初始化 RPM、加载 include 或执行宏

### Requirement: uname 架构探测必须按目标值静态替换且不建模误选
scanner SHALL 将精确、无包装的 `uname -m` 识别为 architecture selector，并 SHALL 在不执行命令的情况下以 ScanContext 的规范化 `riscv64` 或 `riscv32` 目标值进行符号求值；使用 probe 本身 MUST NOT 形成 Finding，且 scanner MUST NOT 建立交叉编译环境误选 x86 分支的路径。

#### Scenario: uname selector 具有 RISC-V 分支
- **WHEN** 完整选择结构包含匹配目标的 RISC-V branch
- **THEN** scanner SHALL 将该 branch 标记 selected 并把互斥 x86 branch 标记 inactive
- **AND** proof SHALL 从 uname Evidence 连接到 RISC-V branch 与其选择项

#### Scenario: uname selector 只有通用 fallback
- **WHEN** 结构没有 RISC-V 专用 branch 但具有 generic、portable、scalar 或 fallback branch
- **THEN** scanner SHALL 选择通用路径并把 x86 branch 标记 inactive
- **AND** scanner SHALL 继续分析通用路径中的源码、参数和依赖

#### Scenario: uname selector 缺少可用路径
- **WHEN** 结构只有 x86 branch，且没有 RISC-V 或通用 fallback
- **THEN** scanner SHALL 产生 `missing_riscv_selection_path` Observation
- **AND** Observation MUST NOT 声称 RISC-V 会选择 x86 branch

#### Scenario: uname 命令形状不精确
- **WHEN** probe 带 wrapper、管道、重定向、环境前缀、额外命令或未知参数
- **THEN** scanner SHALL 将其保持 unsupported/unknown
- **AND** scanner MUST NOT 执行命令或猜测输出

### Requirement: 构建选择必须形成有完整性状态的统一关系链
Build Selection Analyzer SHALL 将 architecture selector、build variable、condition/branch、source set、directory、compile/link argument、dependency、target、package 与 section 建立 scanner-owned Relation/ProofPath，并 SHALL 为每个目标 RISC-V 选择结果区分 `selected`、`inactive`、`not_selected` 和 `unknown`；所有端点与 Evidence 引用 MUST 存在于同一 AnalysisSnapshot。

#### Scenario: 目标选择链完整
- **WHEN** 受支持输入完整证明某源码、参数或依赖进入 RISC-V target
- **THEN** AnalysisSnapshot SHALL 包含从 architecture/configuration selector 到 target item 的完整 proof
- **AND** 每条 Relation SHALL 保留 producer、条件、Evidence 和求值状态 provenance

#### Scenario: 分支被完整互斥条件排除
- **WHEN** 完整条件证明 x86 branch 对目标 RISC-V 不成立
- **THEN** Analyzer SHALL 将该 branch 及其依赖选择标记 inactive/not_selected
- **AND** 它 MUST NOT 删除 x86 Evidence 或把该状态直接解释为项目 ready

#### Scenario: 没有发现选择关系
- **WHEN** 输入缺失、表达式不支持或 provenance 不足以判断 target item
- **THEN** Analyzer SHALL 返回 unknown/partial reason
- **AND** 缺少 proof MUST NOT 被转换为 not_selected 或 inactive

### Requirement: 构建选择阶段必须产生非最终的可追溯 Observation
Build Selection Detector SHALL 仅从有效 build Relation/ProofPath 产生或补充 selected-x86、inactive-x86、missing-target-path 和 unknown Observation，并 SHALL 引用适用的源码/参数 KnowledgeEntry 与全部 Evidence/Relation ID；本阶段 MUST NOT 决定最终 blocker、severity 或 RISC-V readiness。

#### Scenario: RISC-V target 选择 x86 编译参数
- **WHEN** 完整 proof 表明 RISC-V target 选择了命中 compiler-derived x86 KnowledgeEntry 的参数
- **THEN** Detector SHALL 产生 `build_selected_x86_dependency` Observation
- **AND** 两份现有 Clang/GCC knowledge source provenance SHALL 原样可追溯

#### Scenario: x86 项只存在于 inactive branch
- **WHEN** 完整 selector proof 将 x86 源码或参数排除在 RISC-V target 外
- **THEN** Detector SHALL 记录 `build_inactive_x86_path` 上下文
- **AND** 最终 guarded/non-blocking 分类 SHALL 留给后续阶段

#### Scenario: 选择 proof 不完整
- **WHEN** relation 或 proof 因动态表达式、缺失输入或预算截断为 unknown/partial
- **THEN** Detector SHALL 保留 `build_selection_unknown` 和原因
- **AND** Detector MUST NOT 升级为 selected、inactive、非阻断或 ready

### Requirement: 构建选择实现必须通过人工基线和独立单元测试门禁
本 capability SHALL 使用版本化、scanner 不可自动重写的人工选择 baseline 验证 selector、分支、源码、参数、依赖和 target proof；每个新增或实质修改业务模块 SHALL 映射到隔离单元测试，并 SHALL 在唯一 `kb-scanner-test` 容器中通过至少 90% line / 80% branch 覆盖门禁、无副作用门禁和完整回归。

#### Scenario: 验收 AVX Makefile 参数
- **WHEN** qualification 扫描阶段 5 baseline 中 4 个 Makefile
- **THEN** 人工审计的 24 个 x86 flag occurrence SHALL 全部具有准确 SourceSpan 和选择 provenance
- **AND** 每项 SHALL 根据可用构建证据标记 selected、inactive 或 unknown，而不是继续无说明 deferred

#### Scenario: 审计模块测试清单
- **WHEN** 新增、删除或重命名 build frontend、evaluator、normalizer、analyzer、detector 或组合器模块
- **THEN** test inventory SHALL 同步映射隔离 unit suite 与 fake/mock 边界
- **AND** 缺失映射或覆盖率低于门槛 SHALL 使容器测试失败

#### Scenario: 验证恶意输入和兼容合同
- **WHEN** 容器扫描包含 Make/M4/CMake/RPM 命令构造的 fixture 并运行 Legacy/output regression
- **THEN** marker 文件、workspace 和外部状态 SHALL 无副作用，且 scanner 不启动项目命令
- **AND** 默认 CLI 的 schema 1.0、顶层字段、三个 artifact、现有 YAML/`generatedSet` 与两份 compiler facts SHALL 保持不变
