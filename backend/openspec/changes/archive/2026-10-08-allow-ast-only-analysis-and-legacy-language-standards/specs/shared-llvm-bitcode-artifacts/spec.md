## ADDED Requirements

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
