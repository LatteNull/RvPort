## ADDED Requirements

### Requirement: Ingest supported compiler commands without shell execution

系统 SHALL 支持 GCC/Clang 的 C11/C17、C++17/C++20 编译数据库，校验 directory、file 和 arguments/command，优先使用字符串数组 arguments；SHALL 拒绝 MSVC/clang-cl、未知执行 wrapper 及含需执行的 shell 操作的 command。源文件/响应文件相对路径 SHALL 按对应工作目录和驱动语义解析，响应文件展开 SHALL 有循环、深度和大小限制。

#### Scenario: Arguments take precedence over command

- **WHEN** 一条记录同时有合法 arguments 和内容不同的 command
- **THEN** 使用 arguments 建立有效 argv，同时保留两份原始字段和选择依据，不执行 command

#### Scenario: Command requests shell substitution

- **WHEN** command 含命令替换、管道或需要执行的重定向
- **THEN** 标记不支持的命令语义，不经 shell 执行，不静默得到另一条编译命令

#### Scenario: Response files form a cycle

- **WHEN** GCC/Clang 响应文件递归引用自己或超过预算
- **THEN** 输出包含引用链的受限诊断，拒绝该 TU，其他独立 TU 仍可处理

### Requirement: Preserve production context and explain adaptation

TUManifest SHALL 保存原始/有效 argv、生产与分析编译器身份、语言标准、target/ABI/CPU、sysroot/SDK、宏与 include 有序序列、相关环境和每项保留/转换/移除/不支持记录。SHALL 区分驱动默认与显式选项，不以生成 BC 成功宣称与生产 GCC 语义等价；未支持的语义参数不得静默丢弃。

#### Scenario: GCC implicit C++ headers are required

- **WHEN** GCC 编译记录未显式给出标准库路径而分析 Clang 需要该路径
- **THEN** 根据经核验的 GCC 安装/SDK 信息作显式适配并记录来源；无法恢复时报告缺口，而不是伪造已成功适配

#### Scenario: Ordered macro operations affect preprocessing

- **WHEN** 原始参数含重复宏定义、取消定义及多个有顺序的 include 目录
- **THEN** 保留其有效顺序和含义，不将宏列表转换为丢失操作顺序的字典

### Requirement: Give each effective TU a stable configuration identity

CompileContextId SHALL 基于有效配置和工具链身份，不依赖数据库条目顺序；SHALL 保留同源码不同配置，外部绝对路径不得仅以 basename 参与身份。相同重复记录允许复用同一 TU，但 SHALL 保存原始记录到 TU 的映射。目标成员关系 SHALL 独立于 TU 配置身份。

#### Scenario: Reorder compilation database entries

- **WHEN** 只调整相同编译记录在数据库中的顺序
- **THEN** 各有效 TU 的 CompileContextId 保持不变，来源记录映射仍可追溯

#### Scenario: One source uses different macro configurations

- **WHEN** 相同 source 在两条记录中具有不同有效宏或 target
- **THEN** 产生不同配置身份和产物位置，不互相覆盖

### Requirement: Validate dependencies before artifact cache reuse

系统 SHALL 使用同配置依赖发现和源/头/响应文件内容指纹形成 ArtifactKey，包含系统头、工具链/SDK、分析 profile 和 schema 身份；每次缓存复用前 SHALL 重新发现依赖，验证输入稳定，不能仅比较上次记录的头文件。无法确认 SDK/依赖身份时 SHALL 禁止复用成功缓存。

#### Scenario: A new header shadows a previous include

- **WHEN** 搜索路径前方新增同名头文件，使实际 include 命中变化
- **THEN** 重新依赖发现识别新命中，旧 BC 缓存失效并重编译

#### Scenario: Inputs change while compiling

- **WHEN** 依赖采集与编译后的输入指纹不同且一次重试后仍不稳定
- **THEN** 输出 inputs_changed，不发布或缓存该 TU 为成功产物

#### Scenario: A required generated header is absent

- **WHEN** 编译上下文依赖未生成的头文件
- **THEN** 记录该 TU 的具体缺失前提，不自动执行构建脚本，也不将其从计划 TU 分母移除
