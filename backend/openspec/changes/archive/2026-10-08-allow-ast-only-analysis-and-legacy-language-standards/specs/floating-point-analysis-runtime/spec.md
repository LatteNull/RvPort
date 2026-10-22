## MODIFIED Requirements

### Requirement: 浮点分析必须消费当前构建上下文和共享 BC
系统 SHALL 仅基于当前源码版本、同源码版本成功的 source/x86 构建、真实 `compile_commands.json` 以及可解析的源/目标 profile 创建浮点分析任务；`SharedLlvmBitcodeArtifactSet` SHALL 是可选增强证据而不是任务创建的硬前置条件。

#### Scenario: 创建完整浮点分析
- **WHEN** 当前源码版本存在成功 x86 构建、compile database、全部计划翻译单元均具有校验成功的 produced BC record 和受支持的源/目标 profile
- **THEN** 后端 SHALL 创建 `FLOATING_POINT_ANALYSIS` 异步任务
- **AND** 运行模式 SHALL 为 `AST_BC_COMPLETE`
- **AND** 运行记录 SHALL 固定源码版本、构建、artifact set、环境配置版本、BC 覆盖分母和工具协议版本

#### Scenario: 缺少可用 BC 时执行 AST-only
- **WHEN** BC 未生成、状态为 FAILED、UNSUPPORTED 或 NOT_ATTEMPTED、制品缺失、哈希或身份无效，或没有 produced record
- **AND** 当前源码、成功 x86 构建和真实 compile database 可用
- **THEN** 后端 SHALL 创建浮点分析任务并省略 `bitcode_artifact_set`
- **AND** 运行模式 SHALL 为 `AST_ONLY`
- **AND** readiness、运行摘要和结果 MUST 返回稳定 BC 降级原因

#### Scenario: 部分 BC 按翻译单元混合运行
- **WHEN** artifact set 为 PARTIAL 且至少包含一个合法 produced record和完整失败分母
- **THEN** 后端 SHALL 对 produced 翻译单元运行 AST+BC
- **AND** SHALL 对没有可用 BC 的合法翻译单元运行 AST-only
- **AND** 运行模式 SHALL 为 `AST_BC_MIXED`
- **AND** readiness 与最终结果 MUST 保留计划、可用、失败和 AST-only 翻译单元计数

#### Scenario: BC 损坏不污染 AST 结果
- **WHEN** manifest、bundle、摘要、源码身份或编译上下文校验失败
- **THEN** 后端 MUST NOT 将该 BC 传给扫描器
- **AND** SHALL 在 compile database 可用时降级为 AST-only
- **AND** MUST NOT 把降级结果标记为完整 AST+BC 分析

#### Scenario: 旧语言标准保留真实编译语义
- **WHEN** compile database 中的 C/C++ 翻译单元使用 C89/C90、C99、C++98/C++03 或常见 GNU 方言
- **THEN** 浮点扫描 SHALL 使用真实 `-std` 参数生成 AST facts
- **AND** MUST NOT 将旧标准静默改写为 C17 或 C++17
- **AND** 单个不支持的编译上下文 SHALL 产生可审计的 unknown 或 unsupported，而不得阻断其他翻译单元
