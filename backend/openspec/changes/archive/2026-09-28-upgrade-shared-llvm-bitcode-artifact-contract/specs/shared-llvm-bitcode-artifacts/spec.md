## MODIFIED Requirements

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

## ADDED Requirements

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
