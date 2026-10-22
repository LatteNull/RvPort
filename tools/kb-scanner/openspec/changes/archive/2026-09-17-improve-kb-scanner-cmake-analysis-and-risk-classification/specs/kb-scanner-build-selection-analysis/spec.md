## MODIFIED Requirements

### Requirement: 构建工作区必须安全且确定地发现受支持输入
正式 Build Workspace/Frontend SHALL 在 ScanContext 的输入和排除边界内发现 Make、Autoconf（包括 config.guess）、CMake 源码（CMakeLists.txt 与普通 .cmake）、已有 CMake/Meson/CTest 机器产物、compilation database 与 RPM spec 输入，并 SHALL 按规范化项目相对路径和输入 kind 确定性排序；它 MUST NOT 跟随逃逸 workspace 的路径或执行发现到的文件。Scanner SHALL 仅复用现有输入目录和编译数据库；MUST NOT 新增 manifest、传参或读取远端构建目录。CMake 源码 SHALL 路由到独立源码 adapter，不与机器 JSON 混淆。

#### Scenario: 项目包含多类构建输入
- **WHEN** workspace 同时包含 C/C++、Makefile、configure、config.guess/config.sub、CMakeLists.txt、普通 .cmake、CMake File API reply、Meson introspection 和 RPM spec
- **THEN** composite workspace/frontend SHALL 把各输入路由到对应正式 adapter
- **AND** C/C++ 文件 SHALL 继续由既有 C/C++ Frontend 处理

#### Scenario: 构建路径逃逸 workspace
- **WHEN** symlink、include 或机器产物绝对路径指向 workspace 外部
- **THEN** scanner SHALL 拒绝读取该目标并产生结构化 Diagnostic
- **AND** 稳定 Entity/Evidence identity MUST NOT 包含机器绝对路径

## ADDED Requirements

### Requirement: CMake 选择闭包必须独立于 Make 语法并隔离观察配置
Build Selection SHALL 按 CMake target identity、源码路径、参数作用域与配置闭合统一 Relation/ProofPath，不得套用 Make recipe 或源文件 basename 猜测。源码 RISC-V 静态推导 SHALL 与源环境 x86 compdb/File API 分别保留；冲突、过期或目标 provenance 不足 SHALL 明确 unknown。新增关系预算 SHALL 按本阶段新增量计算。

#### Scenario: 没有前置终止的明确目标
- **WHEN** 有界 CMake 入口将源码与 x86 参数明确加入目标且控制路径完整
- **THEN** scanner SHALL 建立配置/条件、target、source/argument 与局部 x86 依赖的可追溯关系
- **AND** 每个关系 SHALL 保留实际 Evidence 与配置 identity

#### Scenario: x86 观察配置与目标分析共存
- **WHEN** compdb 显示 x86 使用 AVX，但目标 CMake 分支选择通用源码或条件未知
- **THEN** scanner SHALL 按各配置保留证据，不得把 x86 已编译事实当作 RISC-V selected
- **AND** 未解决冲突 SHALL 输出具体断点而不是静默覆盖
