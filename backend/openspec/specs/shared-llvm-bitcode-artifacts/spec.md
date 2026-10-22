## Purpose

定义 source/x86 构建完成后生成、校验、存储和共享 LLVM Bitcode 制品的行为边界，使后续分析器能够复用同一组可追溯、不可变且不阻断主构建的 BC artifact-set。
## Requirements
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
系统 SHALL 对所有新生成的共享 BC 使用 `SharedLlvmBitcodeArtifactSet@2.0` 发布中立 manifest 和不可变 BC bundle，使多个分析器能够按统一协议共享制品而不依赖 RvPort 业务主键或彼此内部 schema。

#### Scenario: v2 manifest 保存可移植身份
- **WHEN** BC 生产结束并准备发布 manifest
- **THEN** manifest SHALL 包含 kind、schema version、artifact-set ID、source identity digest、原始编译数据库 SHA-256、规范化编译上下文 digest、producer、状态、计数、完整计划 records、可用 scopes 和生成时间
- **AND** manifest MUST NOT 包含 project ID、source revision ID、build run ID、数据库 ID、bucket、object key、凭据、环境变量值、远端绝对路径、服务器本机路径或完整编译命令

#### Scenario: produced record 保存完整消费契约
- **WHEN** 某个翻译单元成功生成并验证 BC
- **THEN** 对应 record SHALL 包含稳定 record ID、physical TU ID、context ID、平台 artifact key、源码相对路径和 SHA-256、语言与标准、production compiler、BC producer/host、target triple、data layout、ABI、优化/debug、module kind、compile record digest、可用 input digests、profile、profile version、通用 capabilities、可选版本化 sidecars、bundle 相对路径、大小和 SHA-256
- **AND** 消费者 SHALL 能根据 profile 与 capabilities 判断该成员是否满足分析要求

#### Scenario: missing 或 failed record 不会从计划分母消失
- **WHEN** 某个计划翻译单元失败、跳过或不受支持
- **THEN** 该 record SHALL 保留在 manifest 中并包含稳定 TU/context/profile 身份、`missing` 或 `failed` 状态、reason code 及中英文脱敏诊断
- **AND** 该 record MUST NOT 引用 BC 或计入 produced 数量

#### Scenario: manifest 使用稳定身份算法
- **WHEN** 相同源码内容、规范化编译上下文、工具链、profile 和成功成员集合被重复生产
- **THEN** physical TU ID、context ID、artifact key 和 artifact-set ID SHALL 保持一致
- **AND** generated at、诊断文本、bundle 外部哈希及 RvPort 业务元数据 MUST NOT 参与 artifact-set ID 计算

#### Scenario: manifest 不泄露敏感路径
- **WHEN** 系统生成、校验、存储或返回 manifest 摘要
- **THEN** 所有源码和制品路径 SHALL 为受控相对路径
- **AND** manifest MUST NOT 包含可还原远端或后端宿主机目录结构的信息

#### Scenario: artifact-set 写入对象存储
- **WHEN** 至少一个 BC 成功生成并且 v2 manifest 与远端输出通过校验
- **THEN** worker SHALL 将 manifest JSON 和 BC tar.gz bundle 保存为 `BUILD_VALIDATION` 所有的 stored artifacts
- **AND** 两个制品 SHALL 通过数据库元数据关联相同的 `build_runs.id`
- **AND** worker SHALL 在数据库中只保存安全摘要、哈希、协议版本和 stored artifact ID

#### Scenario: bundle 布局和成员完整性得到验证
- **WHEN** worker 校验远端 bundle
- **THEN** bundle SHALL 只包含根目录 `manifest.json`、声明的 record、`bitcode/<record_id>.bc`、scope 和显式声明的 sidecar
- **AND** worker SHALL 校验每个 record、scope 和 sidecar 的相对路径、大小、SHA-256、计数、引用闭包和唯一性

#### Scenario: 下载 bundle 时拒绝路径逃逸
- **WHEN** bundle 包含绝对路径、父目录逃逸、反斜杠逃逸、符号链接、硬链接、设备文件、重复冲突条目、未声明文件或超预算内容
- **THEN** worker SHALL 拒绝整个待发布 artifact-set
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

### Requirement: 共享 BC 协议必须区分原始输入和规范化编译上下文
系统 SHALL 同时保存原始 `compile_commands.json` 的字节级 SHA-256 与规范化编译上下文摘要，且 MUST 使用规范化摘要而非数据库标识表达可移植的编译语义身份。

#### Scenario: 原始编译数据库完全一致
- **WHEN** 两次生产使用字节完全一致的 `compile_commands.json`
- **THEN** `raw_compile_commands_sha256` SHALL 相同

#### Scenario: 仅工作目录前缀不同
- **WHEN** 两份编译数据库只有受控远端部署根目录不同且有效编译语义一致
- **THEN** 原始 SHA-256 MAY 不同
- **AND** 规范化编译上下文 digest SHALL 相同

#### Scenario: 编译语义发生变化
- **WHEN** 编译参数顺序、宏、include、语言标准、target、ABI 或 response-file 有效内容发生变化
- **THEN** 规范化编译上下文 digest SHALL 变化

### Requirement: 共享 BC profile 和 capability 必须显式版本化
系统 SHALL 为每个成功 BC 成员声明 profile、profile version 和平台级 capabilities；当前生产器 SHALL 至少支持 `source-preserving@1`，并 MUST NOT 将未实现语义或消费者已经生成的分析事实声明为 BC capability。

#### Scenario: 生成源码保持型 BC
- **WHEN** 生产器使用受控 debug 和 source-preserving 参数生成 BC
- **THEN** member profile SHALL 为 `source-preserving`
- **AND** profile version SHALL 为 `1`
- **AND** capabilities SHALL 如实声明 debug location、变量信息、source correlation、浮点操作/fast-math、原子 ordering、`syncscope`、fence、target/data layout、symbol linkage 及其他已验证能力

#### Scenario: 同一上下文发布多个 profile
- **WHEN** producer 为同一 `context_id` 生成 `source-preserving` 和 `build-faithful` 成员
- **THEN** 两个成员 SHALL 使用不同 artifact key
- **AND** manifest 计数 SHALL 区分 planned context 数量与 planned profile artifact 数量
- **AND** 两个 profile 的 capability SHALL 分别按实际内容声明

#### Scenario: 浮点精度消费者选择成员
- **WHEN** 浮点精度分析要求源码定位、浮点操作和 fast-math 信息
- **THEN** 消费者 SHALL 只选择声明对应通用 capability 且 profile 受支持的成员
- **AND** 协议 MUST NOT 要求 producer 声明浮点扫描器私有事实名称

#### Scenario: 强弱内存序消费者选择成员
- **WHEN** 强弱内存序分析要求 atomic ordering、`syncscope`、fence、target/data layout、debug source mapping 或跨 TU linkage
- **THEN** 消费者 SHALL 只选择声明对应通用 capability 且 profile 受支持的成员
- **AND** 协议 MUST NOT 要求 producer 声明内存序扫描器私有事实名称

#### Scenario: 消费者需要未提供能力
- **WHEN** 后续消费者要求 manifest 未声明的 profile 或 capability
- **THEN** 消费者 SHALL 将该成员视为不满足要求
- **AND** 系统 MUST NOT 仅因 BC 文件可解析而推断该能力存在

### Requirement: 共享 BC 必须支持跨翻译单元分析而不预链接模块
系统 SHALL 保留每个物理翻译单元和 profile 的独立 BC module、target/data layout 与 symbol linkage 信息，并 MAY 通过版本化 sidecar 提供源码绑定或跨 TU 符号索引；系统 MUST NOT 为简化消费而默认预链接全部 BC。

#### Scenario: 内存序分析建立跨 TU 关系
- **WHEN** 强弱内存序分析需要追踪跨文件函数调用、全局变量或发布订阅关系
- **THEN** manifest SHALL 提供稳定成员、context 和 symbol linkage 能力用于建立项目级索引
- **AND** 可选 symbol-index sidecar SHALL 使用版本、相对路径、大小和 SHA-256 进行完整性保护

#### Scenario: 没有跨 TU sidecar
- **WHEN** artifact-set 未声明 symbol-index sidecar
- **THEN** 消费者 MAY 从全部独立 BC member 构建自己的跨 TU 索引
- **AND** MUST NOT 将 sidecar 缺失解释为 BC 损坏

#### Scenario: 禁止默认预链接改变语义
- **WHEN** producer 发布共享 BC artifact-set
- **THEN** producer SHALL 保留物理 TU 边界
- **AND** MUST NOT 通过默认预链接改变 linkage、内联、原子操作或 debug mapping 后再冒充原始成员

### Requirement: 共享 BC 必须保存 memory-order-analyzer 所需的外部导入 provenance
系统 SHALL 为每个计划 record 保存足以确定性适配 `memory-order-analyzer` ExternalBitcodeArtifactRecord 的 producer、target、profile、source、compile record、input digest 和 module kind 信息，并 SHALL 明确区分 producer-attested 与后端验证字段。

#### Scenario: producer host 与 BC target 不同
- **WHEN** x86_64 producer host 生成非 x86 target 的 raw BC
- **THEN** record SHALL 分别保存 host triple 与 BC target triple、DataLayout 和 ABI
- **AND** MUST NOT 使用 producer host 代替分析 target

#### Scenario: BC 实际 target 与声明冲突
- **WHEN** 后端 verifier 从 BC 读取的 target triple 或 DataLayout 与 record 声明不一致
- **THEN** 对应 record SHALL 标记 failed
- **AND** MUST NOT 修改 module triple 或按声明值覆盖实际值

#### Scenario: 依赖 provenance 不完整
- **WHEN** producer 无法完整登记源码、头文件、response file 或生成输入摘要
- **THEN** record SHALL 标记 provenance 完整性缺口
- **AND** BC MAY 保持 produced 供 IR-only 分析，但不得声明 source/profile 等价或完整缓存覆盖

#### Scenario: 平台 key 不冒充分析器内部 key
- **WHEN** v2 record 被适配到 `memory-order-analyzer` external ingestion
- **THEN** adapter SHALL 将平台 record identity 作为外部 record 引用
- **AND** MUST NOT 将平台 artifact key 作为分析器内部 ArtifactKey
- **AND** 分析器 SHALL 继续基于 BC digest、record 语义和自身 extractor/schema/policy 计算内部 identity

### Requirement: 共享 BC 必须显式登记目标 scope 或完整性缺口
系统 SHALL 要求 v2 artifact-set 使用至少一个独立版本化 scope 描述 target ID、record membership、成员证据、closed、external boundaries、target triple 和 semantic digest；无法证明闭合目标时 MUST 生成覆盖全部计划 records 的开放 fallback scope，不得扫描现存 BC 猜测完整目标。

#### Scenario: 构建图提供闭合目标成员
- **WHEN** 构建上下文能够证明某目标的全部计划 records 和外部边界
- **THEN** scope MAY 声明 `closed=true`
- **AND** membership SHALL 使用稳定 record identity 且按确定顺序保存

#### Scenario: 构建流程无法确定闭合目标
- **WHEN** producer 只有逐 TU compile database 而没有可信 target membership
- **THEN** producer SHALL 按 target triple 生成稳定 fallback scope，将对应全部计划 records 纳入成员
- **AND** fallback scope SHALL 声明 `closed=false`、compile-database planned set 证据和未知 external boundaries
- **AND** 后续 memory-order ingestion SHALL 进入 partial/frontier，不得声称完整 scope

### Requirement: 新制品必须使用 v2 且历史 v1 仅允许读取
系统 SHALL 只为新 BC artifact-set 写入 v2 manifest，并 SHALL 对历史 v1 与缺少 BC 字段的记录提供明确的只读兼容状态。

#### Scenario: 新构建生成 BC
- **WHEN** 部署升级后 source/x86 构建进入 BC 生产阶段
- **THEN** producer SHALL 只生成 `SharedLlvmBitcodeArtifactSet@2.0`
- **AND** MUST NOT 创建新的 v1 manifest

#### Scenario: 查询历史 v1 制品
- **WHEN** 用户查询已经保存的 v1 构建记录
- **THEN** 响应 SHALL 保留其已有安全摘要并标识 `legacy=true`
- **AND** 后端 MUST NOT 在读取时转换、重写或重新上传该制品

### Requirement: v2 协议实现必须通过一致性与覆盖率门禁
v2 协议实现 SHALL 使用共享 schema、有效/无效 fixture 和 canonical identity 测试向量验证 Java 模型、Python producer 与校验器的一致性，并 SHALL 使用 mock 的外部连接完成独立单元测试。

#### Scenario: 跨实现身份一致
- **WHEN** Java 与 Python 使用同一测试向量计算 v2 身份
- **THEN** source identity、compile context、record identity、scope identity 和 artifact-set ID SHALL 完全一致

#### Scenario: memory-order-analyzer 兼容映射完整
- **WHEN** 使用 v2 fixture 生成 `memory-order-analyzer` ExternalBitcodeBundleManifest 和 ExternalBitcodeArtifactRecord
- **THEN** planned record、produced/missing/failed、producer、target、profile、source、compile/input digest 和 scope SHALL 无丢失映射
- **AND** 平台 artifact key MUST NOT 被当作分析器内部 ArtifactKey

#### Scenario: 覆盖正常异常和边界流程
- **WHEN** 执行 v2 协议单元测试
- **THEN** 测试 SHALL 覆盖 READY、PARTIAL、FAILED、planned records、开放/闭合 scope、重复记录、计数错误、哈希错误、路径逃逸、损坏归档、超预算、历史 v1 和主构建隔离
- **AND** 测试 MUST NOT 依赖真实 SSH、SFTP、对象存储、数据库、Redis 或 RabbitMQ

#### Scenario: 覆盖率未达门槛
- **WHEN** 项目整体或受影响模块的行覆盖率低于 90%，或工具支持的分支覆盖率低于 90%
- **THEN** 该 change MUST NOT 标记实现和质量验收完成

### Requirement: 后端必须解析当前分析所需的共享 BC 制品
系统 SHALL 根据项目、当前源码版本和成功的 source/x86 构建解析唯一的 `SharedLlvmBitcodeArtifactSet@2.0`、compile database 和源码制品，不得信任客户端传入对象 key 或服务器路径。

#### Scenario: 解析一致制品
- **WHEN** 构建、compile database、manifest 和源码具有一致的源码身份与编译上下文
- **THEN** resolver SHALL 返回固定的 artifact set ID、stored artifact reference 和校验摘要

#### Scenario: 制品身份不一致
- **WHEN** BC manifest 的源码身份、compile context 或构建关联与当前运行不一致
- **THEN** resolver MUST 拒绝该制品
- **AND** 分析任务 MUST NOT 启动

### Requirement: 分析输入必须安全物化
系统 SHALL 在 Worker 任务私有目录中流式下载并校验源码、compile database 和 BC bundle，且 SHALL 对路径、条目类型、大小、数量、SHA-256 和 manifest 声明执行严格校验。

#### Scenario: 正常物化
- **WHEN** 所有对象和归档成员满足 v2 manifest 与预算
- **THEN** materializer SHALL 生成只读输入目录和稳定相对路径

#### Scenario: 路径或内容不安全
- **WHEN** bundle 包含绝对路径、`..`、反斜杠逃逸、符号链接、硬链接、设备文件、重复条目、未声明文件或哈希错误
- **THEN** materializer MUST 终止并清理任务目录
- **AND** MUST NOT 调用分析工具

### Requirement: v2 制品必须确定性适配两个消费者
系统 SHALL 提供浮点扫描和 memory-order external bundle 的版本化 adapter，并 SHALL 保留计划分母、profile、capability、target、ABI、producer、输入摘要和 Scope 完整性。

#### Scenario: 适配浮点扫描器
- **WHEN** 浮点任务消费 v2 artifact set
- **THEN** adapter SHALL 固定 manifest SHA-256、请求的 profile 和所需 capability
- **AND** 不满足能力的 record SHALL 形成明确诊断而不是被静默忽略

#### Scenario: 适配内存序分析器
- **WHEN** 内存序任务消费 v2 artifact set
- **THEN** adapter SHALL 生成合法 external bundle/record/scope
- **AND** produced、missing、failed 与 open boundary MUST 保持不变

### Requirement: 共享 BC 必须保留真实语言标准和方言
共享 BC producer 和版本化 manifest SHALL 将分析工具链版本与源码语言标准分离，并 SHALL 为每个 C/C++ 翻译单元保留真实基础标准、方言来源和原始 `-std` 语义。系统 MUST NOT 为满足协议枚举而把旧标准升级为 C17 或 C++17。

#### Scenario: 显式 ISO C89 或 C99
- **WHEN** 编译记录包含 `-std=c89`、`-std=c90`、`-std=iso9899:1990` 或 `-std=c99`
- **THEN** record SHALL 保存等价规范化的基础标准和实际方言
- **AND** BC 生成 SHALL 保留原始编译参数语义
- **AND** MUST NOT 将 record 的标准写为 C17

#### Scenario: 显式 GNU 旧方言
- **WHEN** 编译记录包含 `-std=gnu89`、`-std=gnu99`、`-std=gnu++98` 或 `-std=gnu++03`
- **THEN** record SHALL 同时保存对应基础标准和 GNU 方言
- **AND** 消费者 SHALL 能区分 GNU 扩展语义与纯 ISO 标准

#### Scenario: 未显式指定标准
- **WHEN** 编译记录不包含有效 `-std`
- **THEN** record SHALL 将标准来源标记为 `compiler-default`
- **AND** SHALL 保留 production compiler 身份
- **AND** MUST NOT 猜测或伪造为 C17、C++17 或其他固定标准

#### Scenario: 新旧消费者的协议版本边界
- **WHEN** manifest 使用扩展语言上下文的新协议版本
- **THEN** 支持该版本的消费者 SHALL 按基础标准和方言读取
- **AND** 不支持该版本的消费者 MUST 明确拒绝而不得按旧枚举误读

### Requirement: 共享 BC 失败分母必须支持 AST 降级关联
共享 BC manifest SHALL 为 produced、failed、missing 和 unsupported 翻译单元保留足以与原始 compile database 安全关联的源码和编译上下文身份，使消费者可以只对可用成员使用 BC，并对其余翻译单元执行 AST-only。

#### Scenario: PARTIAL artifact set
- **WHEN** 部分翻译单元成功生成 BC、部分翻译单元失败或缺失
- **THEN** manifest SHALL 保留全部计划翻译单元和状态分母
- **AND** 每个失败或缺失 record SHALL 保留源码相对路径、physical TU ID、context ID、compile record digest 和诊断
- **AND** 消费者 MUST NOT 使用 produced record 集合裁剪原始 compile database

#### Scenario: 全部 BC 失败
- **WHEN** 计划翻译单元均未生成可用 BC
- **THEN** BC 状态 SHALL 为 FAILED 并保留完整失败分母
- **AND** x86 构建成功状态 SHALL 保持不变
- **AND** 后续消费者 SHALL 能依据原始 compile database 选择 AST-only

### Requirement: 共享 BC 身份校验必须感知 manifest schema 版本
后端 SHALL 按 manifest 声明且受支持的 schema 版本所定义的原始字段集合验证 manifest、record、scope、artifact key 和 artifact-set canonical identity。读取旧版本时 MUST NOT 因当前强类型模型新增字段而把缺失字段序列化为 `null` 并参与旧摘要；读取新版本时 MUST NOT 忽略该版本要求的字段。系统 MUST NOT 为通过校验而重写、补签或重新上传历史制品。

#### Scenario: 合法 schema 2.0 被新版后端读取
- **WHEN** `SharedLlvmBitcodeArtifactSet@2.0` 的 record 不包含后续版本新增的 `dialect`、`standard_source` 和 `standard_option`
- **THEN** 后端 SHALL 使用 2.0 字段集合重算并验证 identity
- **AND** 不得把三个缺失字段作为显式 `null` 加入摘要

#### Scenario: 合法 schema 2.1 被读取
- **WHEN** manifest 声明 schema 2.1 且语言标准、方言和标准来源字段完整
- **THEN** 后端 SHALL 按 2.1 字段集合验证 identity 和语言上下文
- **AND** 2.1 必填字段缺失或非法时 SHALL 拒绝该制品

#### Scenario: 旧 manifest 内容被篡改
- **WHEN** schema 2.0 manifest 的源码身份、编译上下文、record、scope、BC 摘要或其他参与 identity 的字段被修改
- **THEN** 后端 MUST 拒绝该制品并返回具体的 identity 校验原因
- **AND** MUST NOT 以旧版本兼容为由跳过摘要验证

#### Scenario: 未知 manifest 版本
- **WHEN** manifest 声明后端不支持的 schema 版本
- **THEN** 后端 MUST 在解包或启动分析 worker 前拒绝消费
- **AND** SHALL 返回稳定的 unsupported schema 原因码

### Requirement: BC 校验失败必须保留可审计根因
后端 SHALL 将共享 BC 消费失败表示为结构化、双语且脱敏的诊断，至少区分 manifest parse/schema/identity、bundle layout、member size/digest、source/compile binding、materialization 和 LLVM worker 阶段。诊断 SHALL 包含稳定原因码、失败阶段、schema、producer/toolchain 及安全 artifact 身份；MUST NOT 把 manifest 或 bundle 校验错误统一伪装为 LLVM worker failure。

#### Scenario: record semantic digest 不一致
- **WHEN** manifest record 的 canonical digest 与声明值不一致
- **THEN** 运行摘要 SHALL 报告 record identity 校验阶段和稳定 digest mismatch 原因码
- **AND** 不得仅返回 `BITCODE_WORKER_VALIDATION_FAILED`

#### Scenario: bundle 成员损坏
- **WHEN** manifest identity 有效但 bundle 中某个 BC 的大小或 SHA-256 不匹配
- **THEN** 诊断 SHALL 标识 member integrity 阶段、受影响的安全 record/artifact 身份和不可重试属性
- **AND** 不得启动该成员的 LLVM worker

#### Scenario: 默认诊断脱敏
- **WHEN** 校验异常包含远端绝对路径、对象存储 key、堆栈、源码或凭据信息
- **THEN** 默认任务事件、运行摘要和结果诊断 MUST 移除这些内容
- **AND** SHALL 保留足以区分根因的安全摘要和中英文建议

#### Scenario: BC 无效时保留 AST-only
- **WHEN** BC 制品因真实校验错误被拒绝但源码和合法 compile database 仍可用
- **THEN** 浮点分析 SHALL 安全降级为 AST-only 并保留具体 BC 降级原因
- **AND** MUST NOT 把降级结果标记为完整 AST+BC

### Requirement: 编译命令和项目翻译单元分母必须分离
系统 SHALL 以统一、确定性的 compile-entry 分类分别记录原始命令数、C/C++ 编译候选数、唯一项目翻译单元数、BC produced/failed/missing 数和带原因的 excluded 数。浮点分析覆盖率 SHALL 以合法项目 C/C++ 翻译单元为分母；MUST NOT 对原始命令数与 manifest planned 数简单取最大值，也 MUST NOT 让构建系统探针、编译器识别文件、重复上下文或非 C/C++ 命令污染项目证据覆盖率。

#### Scenario: compile database 混合构建命令
- **WHEN** compile database 同时包含项目 C/C++、链接/归档命令、重复条目和其他语言命令
- **THEN** 摘要 SHALL 分别返回 raw command、C/C++ candidate、project TU 和 excluded 数量
- **AND** 只有唯一合法项目 C/C++ TU 进入浮点 AST planned 分母

#### Scenario: CMake 编译器探针位于根外
- **WHEN** C/C++ 条目对应 `CMakeCXXCompilerABI.cpp`、CompilerId 或其他可证明的构建系统探针
- **THEN** 系统 SHALL 以稳定原因分类为构建基础设施条目
- **AND** 其失败 MUST NOT 使项目源码 BC 覆盖率看似缺失

#### Scenario: 项目 TU 只有部分 BC
- **WHEN** 三个项目 TU 中两个具有合法 produced BC、一个具有 failed 或 missing record
- **THEN** 项目覆盖摘要 SHALL 报告 planned=3、usable=2 和 AST-only=1
- **AND** 原始 compile database 中的无关命令数不得改变这些值

#### Scenario: 无法证明的生成源码
- **WHEN** build 目录中的 C/C++ 条目无法确定是项目生成源码还是构建探针
- **THEN** 系统 SHALL 保留该条目的稳定身份和显式分类诊断
- **AND** MUST NOT 仅按目录名称静默排除

### Requirement: BC 兼容修复必须通过跨版本和故障单元测试
实现 SHALL 使用固定 schema 2.0/2.1 manifest、bundle 和 canonical identity 测试向量验证 Java consumer 与 Python producer 一致性，并 SHALL 使用 mock 外部连接覆盖正常、边界和异常路径。backend 项目整体及受影响模块的行覆盖率和可用分支覆盖率 MUST 均至少为 90%。

#### Scenario: 跨版本有效和篡改矩阵
- **WHEN** 在 Linux Docker 中执行 BC 协议单元测试
- **THEN** 测试 SHALL 覆盖 2.0/2.1 有效制品、新增字段缺失/空值、record/manifest/scope 摘要篡改、bundle 成员损坏、未知版本和 AST-only 降级
- **AND** 测试 SHALL 对稳定原因码、阶段、分母和脱敏内容进行有效断言

#### Scenario: 覆盖率未达门槛
- **WHEN** backend 整体或受影响模块任一行覆盖率低于 90%，或可统计的分支覆盖率低于 90%
- **THEN** 本 change 的实现与质量任务 MUST 保持未完成
