## ADDED Requirements

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
