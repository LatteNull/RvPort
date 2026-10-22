## ADDED Requirements

### Requirement: 系统必须在 source x86 远端环境生成共享 LLVM BC
系统 SHALL 在当前项目 source/x86 环境的真实构建成功且存在合法 `compile_commands.json` 后，在同一远端源码和构建上下文中生成共享 LLVM BC，且 MUST NOT 在 RISC-V 构建或非 source 环境重复生成。

#### Scenario: x86 构建成功后生成 BC
- **WHEN** 当前 source/x86 构建命令退出码为 `0`
- **AND** 构建目录存在合法 `compile_commands.json`
- **THEN** worker SHALL 在完成构建任务前进入共享 BC 后处理阶段
- **AND** BC 生产 SHALL 使用该构建的源码版本、部署目录、构建目录和编译数据库

#### Scenario: 非 source x86 构建不生成 BC
- **WHEN** 构建运行对应 RISC-V 目标环境、非 source 环境或不受支持架构
- **THEN** worker MUST NOT 启动 BC 编译
- **AND** BC 状态 SHALL 为 `NOT_ATTEMPTED` 或 `UNSUPPORTED` 并包含安全原因码

#### Scenario: 构建失败不尝试生成 BC
- **WHEN** 用户真实构建命令退出码非 `0`
- **THEN** worker SHALL 按真实退出码标记构建失败
- **AND** BC 状态 SHALL 为 `NOT_ATTEMPTED`

### Requirement: 系统必须使用版本锁定的远端托管 LLVM 工具链
系统 SHALL 使用 RvPort 提供且经过完整性校验的 x86_64 LLVM/Clang 21 托管工具链生成 BC，并 MUST NOT 默认修改远端系统软件源、系统软件包或用户已有编译器。

#### Scenario: 复用有效工具链缓存
- **WHEN** 远端环境工作目录存在相同 toolchain ID 的缓存
- **AND** 目录标记、bundle SHA-256、目标架构、必需可执行文件及 `clang --version` 均通过校验
- **THEN** worker SHALL 复用该缓存
- **AND** worker MUST NOT 重复上传工具链 bundle

#### Scenario: 原子部署缺失工具链
- **WHEN** 远端不存在有效工具链缓存
- **THEN** worker SHALL 将锁定 bundle 上传到远端受控临时目录
- **AND** worker SHALL 在校验 SHA-256 后解包并验证工具链
- **AND** worker SHALL 使用原子发布将其写入版本化缓存目录

#### Scenario: 不修改远端系统工具链
- **WHEN** 远端没有兼容的 Clang/LLVM
- **THEN** worker MUST NOT 自动调用系统包管理器安装或升级 Clang/LLVM
- **AND** worker MUST NOT 覆盖 `/usr/bin` 或用户配置的 GCC/Clang

#### Scenario: 工具链不兼容时安全失败
- **WHEN** 托管工具链无法执行、架构不匹配、校验失败或缓存锁等待超时
- **THEN** BC 状态 SHALL 为 `FAILED`
- **AND** 真实 x86 构建状态 MUST 保持由用户构建退出码决定

### Requirement: 系统必须逐翻译单元生成 source-preserving BC
BC 生产器 SHALL 只处理编译数据库中的 C/C++ compile entry，为每个翻译单元生成独立的 source-preserving BC，并 SHALL 保留可用于源码关联的 debug location。

#### Scenario: 规范化 C 编译条目
- **WHEN** 编译数据库条目表示 C 翻译单元
- **THEN** 生产器 SHALL 使用锁定的 `clang-21`
- **AND** SHALL 保留宏、include、语言标准、target、ABI 和 response file 语义
- **AND** SHALL 使用受控的 `-emit-llvm -c`、debug 和 source-preserving 优化参数

#### Scenario: 规范化 C++ 编译条目
- **WHEN** 编译数据库条目表示 C++ 翻译单元
- **THEN** 生产器 SHALL 使用锁定的 `clang++-21`
- **AND** SHALL 保留 C++ 标准库、宏、include、语言标准、target、ABI 和 response file 语义

#### Scenario: 单个 TU 失败不终止其他 TU
- **WHEN** 某个翻译单元包含 Clang 不支持的 GCC 专属参数、缺少输入或编译失败
- **THEN** 生产器 SHALL 记录该 TU 的脱敏失败分类
- **AND** SHALL 继续处理其余翻译单元
- **AND** MUST NOT 通过静默删除未知语义参数将失败伪装为成功

#### Scenario: 非 C/C++ 条目被跳过
- **WHEN** 编译数据库包含汇编、CUDA、Rust、生成器命令或无法确认语言的条目
- **THEN** 生产器 SHALL 将该条目标记为 skipped 或 unsupported
- **AND** MUST NOT 将其计为成功 BC

#### Scenario: BC 经过完整性验证
- **WHEN** 单个翻译单元编译退出码为 `0`
- **THEN** 生产器 SHALL 验证 BC 文件存在且非空
- **AND** SHALL 使用锁定 LLVM verifier 验证其可读性
- **AND** 只有验证成功的 BC 才能写入 manifest 成功项

### Requirement: 系统必须发布中立且不可变的 BC artifact-set
系统 SHALL 使用 `llvm-bitcode-artifact-set.v1` 或后续兼容版本发布中立 manifest 和 BC bundle，使多个分析器可共享制品而不依赖彼此内部 schema。

#### Scenario: manifest 保存可追溯身份
- **WHEN** BC 生产结束
- **THEN** manifest SHALL 包含 source revision ID、build run ID、compile database SHA-256、toolchain ID、bundle SHA-256、producer/schema/profile 版本和生成时间
- **AND** 每个 TU SHALL 包含稳定 context ID、artifact key、源码相对路径、语言、target、ABI、bundle 相对路径、大小、SHA-256、状态和脱敏诊断

#### Scenario: manifest 不泄露敏感路径
- **WHEN** 系统生成或返回 manifest 摘要
- **THEN** manifest MUST NOT 包含远端绝对路径、服务器本机路径、完整编译命令、环境变量值、凭据、bucket 或 object key

#### Scenario: artifact-set 写入对象存储
- **WHEN** 至少一个 BC 成功生成并且远端输出通过校验
- **THEN** worker SHALL 将 manifest JSON 和 BC tar.gz bundle 保存为 `BUILD_VALIDATION` 所有的 stored artifacts
- **AND** 两个制品 SHALL 关联相同的 `build_runs.id`
- **AND** worker SHALL 在数据库中只保存安全摘要、哈希和 stored artifact ID

#### Scenario: 下载 bundle 时拒绝路径逃逸
- **WHEN** worker 校验远端 bundle
- **THEN** worker SHALL 拒绝绝对路径、父目录逃逸、符号链接逃逸、重复冲突条目和超出预算的归档
- **AND** 校验失败 SHALL 使 BC 状态为 `FAILED` 而不改变主构建状态

### Requirement: BC 状态必须独立且允许部分成功
系统 SHALL 使用 `NOT_ATTEMPTED`、`UNSUPPORTED`、`READY`、`PARTIAL` 和 `FAILED` 表达 BC 结果，并 SHALL 将 BC 可用性与真实构建状态完全分离。

#### Scenario: 全部计划 TU 成功
- **WHEN** 所有计划处理的 C/C++ TU 均生成并验证成功
- **AND** manifest 与 bundle 已持久化
- **THEN** BC 状态 SHALL 为 `READY`
- **AND** `available` SHALL 为 `true`

#### Scenario: 部分 TU 成功
- **WHEN** 至少一个计划 TU 成功且至少一个计划 TU 失败
- **AND** 成功 BC、manifest 与 bundle 已持久化
- **THEN** BC 状态 SHALL 为 `PARTIAL`
- **AND** `available` SHALL 为 `true`
- **AND** 摘要 SHALL 分别返回计划、成功、失败和跳过数量

#### Scenario: 没有可消费 BC
- **WHEN** 已尝试生成但没有 TU 成功，或制品回收、校验、持久化失败
- **THEN** BC 状态 SHALL 为 `FAILED`
- **AND** `available` SHALL 为 `false`
- **AND** 摘要 SHALL 返回稳定 reason code

#### Scenario: 缺少可用编译上下文
- **WHEN** 成功 x86 构建没有合法 `compile_commands.json` 或其中没有 C/C++ TU
- **THEN** BC 状态 SHALL 为 `UNSUPPORTED`
- **AND** 主构建 SHALL 继续为 `SUCCEEDED`

### Requirement: 共享 BC 生产必须受资源、取消和清理约束
系统 SHALL 对工具链上传、TU 数量、单 BC 大小、总输出大小、单 TU 时间、总阶段时间和下载大小设置可配置硬限制，并 SHALL 响应任务取消。

#### Scenario: 资源预算超限
- **WHEN** TU 数量、单文件、总输出或时间超过配置预算
- **THEN** 生产器 SHALL 停止新增工作并记录稳定原因码
- **AND** 已完成且可安全发布的 BC MAY 形成 `PARTIAL`
- **AND** 主构建状态 MUST NOT 因预算超限改变

#### Scenario: 任务取消时停止 BC 子进程
- **WHEN** 构建任务在 BC 阶段收到取消请求
- **THEN** worker SHALL 终止受控远端 BC 子进程并停止制品上传
- **AND** SHALL 按任务取消语义结束构建任务

#### Scenario: 临时输出最终清理
- **WHEN** BC 阶段成功、失败、取消或超时
- **THEN** worker SHALL 尽力删除任务级远端 BC 临时目录和本地临时下载
- **AND** 版本化且校验成功的 LLVM 工具链缓存 SHALL 保留供后续任务复用

### Requirement: 共享 BC 实现必须具备独立单元测试和覆盖率门禁
共享 BC 实现 SHALL 使用 mock 的 SSH/SFTP、进程、对象存储和数据库连接返回值完成独立单元测试，测试 MUST NOT 依赖真实外部服务，且项目整体与受影响模块行覆盖率和可用分支覆盖率 SHALL 均至少为 90%。

#### Scenario: 覆盖正常异常和边界流程
- **WHEN** 执行共享 BC 单元测试
- **THEN** 测试 SHALL 覆盖工具链缓存命中与部署、READY、PARTIAL、FAILED、UNSUPPORTED、路径逃逸、预算、取消、并发锁、损坏缓存和对象存储失败
- **AND** 测试 SHALL 对状态、计数、哈希、reason code、清理和主构建隔离进行有效断言

#### Scenario: 覆盖率未达门槛
- **WHEN** 项目整体或受影响模块的行覆盖率低于 90%，或工具支持的分支覆盖率低于 90%
- **THEN** 该 change MUST NOT 标记实现和质量验收完成
