# llvm-bitcode-facts

## Purpose

规范 compile-only BC 生成与导入、LLVM 解析校验、结构化 IR 事实和来源映射，明确受限执行与未知语义边界。

## Requirements

### Requirement: Generate verified compile-only artifacts

系统 SHALL 按有效 TU 配置执行 Clang 前端产生 BC，不要求或执行最终应用的原生链接/运行；SHALL 校验进程退出、预期产物存在且非空、LLVM 解析与 verify，成功后才发布/缓存。source-preserving 与 build-faithful profile SHALL 独立记录和标识，不能混合事件。

#### Scenario: Compiler exits successfully without an artifact

- **WHEN** 编译进程退出 0 但预期 BC 不存在或为空
- **THEN** TU 状态为失败且诊断为 artifact_missing，不计入成功 BC 数

#### Scenario: A source references an unavailable external implementation

- **WHEN** TU 声明合法但外部函数实现尚未提供
- **THEN** 允许 compile-only 生成和读取 BC，保留外部声明及未知效果，不强制最终应用链接

#### Scenario: Collect the same TU with two profiles

- **WHEN** 分别使用 source-preserving 和 build-faithful 编译同一源码配置
- **THEN** 产生具有 profile 来源的独立 ArtifactKey 和事实，不拼接成一次执行证据

### Requirement: Import and validate existing bitcode with provenance

系统 SHALL 支持已有 BC 导入，区分格式、reader、verify、target/layout 与来源一致性错误；SHALL 记录实际 reader、可获知的 producer 和来源可信状态。没有来源 manifest 的 BC SHALL 仅提供可读取的 IR 事实并降级，不推断完整构建或范围归属。

#### Scenario: Invalid or incompatible input has a bc extension

- **WHEN** 输入扩展名为 bc 但格式错误、reader 不兼容或模块 verify 失败
- **THEN** 报告具体失败阶段，不仅凭扩展名或 magic 接受，不产生成功事实产物

#### Scenario: Producer is unknown but the module can be read

- **WHEN** 可读取的 BC 没有可靠 producer/configuration 元数据
- **THEN** 保留 IR 事实并明确 unknown provenance，禁止将该输入作为已验证配置成员自动联合链接

### Requirement: Extract structured memory and control-flow facts

C++ 核心 SHALL 使用 LLVM API 导出 ModuleFacts v2，包括模块身份、函数/全局定义声明、linkage、CFG、调用、内存事件及来源，并增加有类型值引用、条件边、调用实参/返回、静态初始化与 DataLayout 范围事实。事件 SHALL 区分普通/volatile/atomic load-store、RMW 类型、CAS 成功/失败序及 weak、fence order/syncscope、内存 intrinsic。未知 intrinsic/inline asm SHALL 标记 opaque effect，不能作为无效果调用。地址解析 SHALL 仅声明已实现的确定对象/GEP能力，其他地址保持 unknown。结构提取 SHALL 不执行值传播、调用点特化、别名/效果/线程或内存模型推理，不混合不同 profile 事件。

#### Scenario: CAS has distinct success and failure orders

- **WHEN** IR 包含 weak cmpxchg，成功序 acq_rel、失败序 acquire
- **THEN** 结构化事件保留两种 ordering 和 weak 属性，不压缩为单个 atomic 标记

#### Scenario: Signal fence is limited to one thread

- **WHEN** IR 包含 syncscope singlethread 的 fence 和普通 fence
- **THEN** 输出不同 scope 的事件，不将前者解释为通用跨线程同步

#### Scenario: Atomic operations remain inside a C++ wrapper

- **WHEN** O0 调用的标准库包装体含按形参选择 memory order 的多个分支
- **THEN** 保留调用实参、形参、局部值/存储关系、条件 CFG 和原始事件，声明尚未进行调用点特化，不将每个分支当作调用者必然执行的同步

#### Scenario: Rich facts are extracted without debug information

- **WHEN** 有效 BC 缺少 debug 元数据但包含调用参数、条件和内存操作数
- **THEN** 仍输出对应 v2 事实和原始事件身份方式，仅按已有约定降低源码定位状态，不猜源码变量或位置

### Requirement: Keep IR facts when source mapping is incomplete

事件身份 SHALL 基于 artifact/module、函数和 IR 位置，不基于变量显示名或源码行号；源码映射 SHALL 保存原始文件/行列/inline 链及来源一致性状态。缺 debug 或源码 hash 不一致 SHALL 降低定位完整度，不丢弃 IR 事件、不猜位置。

#### Scenario: Debug information is stripped

- **WHEN** 对有效 BC 去掉 debug 后再次读取
- **THEN** 对应可执行内存事件仍被提取，source_mapping 为 unavailable，不能通过删除事件制造干净结果

#### Scenario: Source content no longer matches recorded evidence

- **WHEN** 来源 manifest 中的源码 hash 与当前源码不同
- **THEN** 标记 source_mismatch，保留原始定位和 IR 事实，但不声称当前源码精确匹配

### Requirement: Bound compiler and worker execution

系统 SHALL 对编译、依赖发现、reader worker 和链接设置预算，限制日志大小，超时终止所启动的进程组，保留失败诊断；未完成临时产物 SHALL 不进入成功缓存。清理操作 SHALL 仅针对本任务验证过的输出目录，不改被分析源码。

#### Scenario: A compiler process exceeds its timeout

- **WHEN** 编译器或其子进程超出配置的时间预算
- **THEN** 本任务进程被终止，记录 timed_out，残片不作为 BC 成功产物发布，其他独立任务可继续
