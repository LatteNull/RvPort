## MODIFIED Requirements

### Requirement: 构建工作区必须安全且确定地发现受支持输入
正式 Build Workspace/Frontend SHALL 在 ScanContext 的输入和排除边界内发现 Make、Autoconf（包括 config.guess）、已有 CMake/Meson/CTest 机器产物、compilation database 与 RPM spec 输入，并 SHALL 按规范化项目相对路径和输入 kind 确定性排序；它 MUST NOT 跟随逃逸 workspace 的路径或执行发现到的文件。Scanner SHALL 仅复用现有输入目录和编译数据库；MUST NOT 新增 manifest、传参或读取远端构建目录。

#### Scenario: 项目包含多类构建输入
- **WHEN** workspace 同时包含 C/C++、Makefile、configure、config.guess/config.sub、CMake File API reply、Meson introspection 和 RPM spec
- **THEN** composite workspace/frontend SHALL 把各输入路由到对应正式 adapter
- **AND** C/C++ 文件 SHALL 继续由既有 C/C++ Frontend 处理

#### Scenario: 构建路径逃逸 workspace
- **WHEN** symlink、include 或机器产物绝对路径指向 workspace 外部
- **THEN** scanner SHALL 拒绝读取该目标并产生结构化 Diagnostic
- **AND** 稳定 Entity/Evidence identity MUST NOT 包含机器绝对路径

### Requirement: Autoconf 输入必须区分已生成 Shell 与受限 M4
已有 configure/config.guess/config.sub SHALL 通过锁定的 tree-sitter-bash 和 scanner-owned 有界分析恢复 assignment、case/if selector、匹配顺序、目标模式、精确探测、输出及退出依据；configure.ac/M4 SHALL 只识别批准的宏调用、字面参数和架构条件。分析 SHALL 区分多平台配置逻辑与已求值的 x86 配置结果，以配置单元、脚本版本及目标条件建立接受/拒绝/unknown 关系。scanner MUST NOT 运行 configure、辅助脚本、Autom4te、M4 或任意宏命令，MUST NOT 仅按架构关键词或 wildcard 判定支持。

#### Scenario: config.sub 接受 RISC-V triplet
- **WHEN** 已生成 config.sub 的完整可恢复路径对给定目标名称完成必要规范化、校验、有效输出并成功结束
- **THEN** scanner SHALL 建立 triplet selector 到实际 accepted path 的可追溯选择关系
- **AND** 不相关 x86 branch SHALL 仅在互斥条件完整时标记 inactive；仅包含目标模式不构成接受证明

#### Scenario: config.sub 缺少 RISC-V 和通用路径
- **WHEN** 完整可恢复且作用范围已知的架构选择只接受 x86，并证明目标进入拒绝路径而非可用通用 fallback
- **THEN** scanner SHALL 产生有配置/脚本范围的 missing_riscv_selection_path Observation 候选
- **AND** 它 MUST NOT 描述为 RISC-V 错误进入 x86 branch，也不得从不完整输入推断目标被拒绝

#### Scenario: M4 包含可执行宏
- **WHEN** configure.ac 包含 syscmd、esyscmd、动态 include 或未知参数展开
- **THEN** adapter SHALL 返回 unsupported/unknown Evidence 与 Diagnostic
- **AND** scanner MUST NOT 执行或模拟其副作用

#### Scenario: wildcard 分支失败与多个 case 共存
- **WHEN** 某一 case 的 wildcard 分支 exit 1，而同文件另一个 case 含 RISC-V 或 generic 名称
- **THEN** scanner SHALL 按各 case 的 selector、作用域、顺序和退出结果独立分析
- **AND** MUST NOT 借用另一个 case 的名称证明失败路径可用

#### Scenario: x86 成功构建提供配置结果
- **WHEN** 当前输入可见特定 x86 配置的 Makefile、config.h、config.status/log/cache 或 compile database
- **THEN** scanner SHALL 将它们作为 x86 已观察依据并隔离目标求值
- **AND** MUST NOT 因这些结果成功而替代 config.guess/sub 的 RISC-V 接受分析
