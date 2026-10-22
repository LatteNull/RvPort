# shared-bitcode-artifact-consumption Specification

## Purpose

定义浮点精度扫描器以只读方式消费共享 LLVM bitcode artifact-set 的版本、完整性、就绪状态、源码一致性、profile 能力和确定性规划契约。

## Requirements

### Requirement: 共享 BC artifact-set 必须版本化且不可变
扫描器 SHALL 只消费符合版本化 Draft 2020-12 schema 的 `SharedBitcodeArtifactSet`。manifest MUST 包含 artifact-set 身份、source revision、build run、compile database SHA-256、producer/toolchain/profile 版本、状态、成员分母和逐翻译单元不可变 artifact 身份；语义身份 MUST NOT 依赖临时目录、下载时间或对象存储位置。

#### Scenario: 读取 READY artifact-set
- **WHEN** manifest schema 受支持、状态为 `READY` 且所有必填身份字段有效
- **THEN** 扫描器建立只读 artifact-set 视图并按稳定键规划其 C/C++ 成员

#### Scenario: manifest 主版本不兼容
- **WHEN** artifact-set manifest 的 schema 主版本不受支持
- **THEN** 扫描器在启动 LLVM worker 前拒绝消费并返回可机器识别的版本诊断

### Requirement: artifact-set 路径和内容完整性必须在读取前验证
请求 SHALL 提供显式 artifact root、manifest 相对路径和预期 manifest SHA-256。扫描器 MUST 在读取前解析并校验 manifest/member/sidecar 路径仍位于 artifact root，拒绝绝对成员路径、路径穿越、越界符号链接、URL 和凭据；每个 BC 或 sidecar MUST 在 worker 使用前验证存在性、普通文件类型、声明大小和 SHA-256。

#### Scenario: 合法的相对成员路径
- **WHEN** manifest 和全部成员在解析符号链接后仍位于 artifact root 且大小、摘要一致
- **THEN** 扫描器允许对应成员进入 LLVM facts 提取

#### Scenario: 成员符号链接越界
- **WHEN** manifest 中的相对成员路径通过符号链接解析到 artifact root 外
- **THEN** 扫描器拒绝读取该目标、产生路径边界诊断且不向 worker 传递该路径

#### Scenario: BC 摘要不符
- **WHEN** 实际 BC 的 SHA-256 与 manifest 声明不一致
- **THEN** 对应翻译单元以完整性失败结束，不从该文件发布任何 LLVM facts

### Requirement: 扫描器不得生成、修改或等待共享 BC
托管共享模式下，扫描器 MUST NOT 调用编译器生成缺失 BC、修改 artifact-set、轮询生产状态或占用 worker 等待。仅 `READY` 和带有至少一个完整可用成员的 `PARTIAL` artifact-set 可以进入事实提取；`MISSING`、`QUEUED` 或 `GENERATING` SHALL 返回 `retryable=true` 的未就绪诊断。

#### Scenario: artifact-set 正在生成
- **WHEN** manifest 或平台适配输入声明状态为 `GENERATING`
- **THEN** 扫描器不启动 Clang/LLVM worker、不轮询，并以 `failed` 和可重试诊断结束本次请求

#### Scenario: PARTIAL artifact-set 含可用成员
- **WHEN** artifact-set 为 `PARTIAL` 且部分成员完整可用、部分成员带生产失败记录
- **THEN** 扫描器处理可用成员、保留失败分母并使整体结果至少为 `partial`

### Requirement: artifact-set 必须与源码输入和 profile 一致
扫描器 SHALL 在启动 LLVM worker 前，将 artifact-set 的 source revision、compile database SHA-256、physical TU/context 身份、语言、target、ABI、analysis compiler 和 profile 与规范化源码输入及请求 profile 比对。确定冲突 MUST 被拒绝，缺失的关键身份 MUST 保持 unknown 或使请求失败，不得用宿主默认值补齐。

#### Scenario: compile database 摘要匹配
- **WHEN** manifest 摘要与本次规范化 `compile_commands.json` 摘要一致且所有 context identity 可对应
- **THEN** 扫描器允许 AST 与 BC 进入后续独立 facts 提取

#### Scenario: source revision 冲突
- **WHEN** artifact-set 的 source revision 与请求明确绑定的源码版本不同
- **THEN** 扫描器返回输入冲突诊断且不生成 AST↔IR evidence

#### Scenario: target 与 source profile 冲突
- **WHEN** BC manifest 声明的 target/ABI 与 source profile 的确定约束冲突
- **THEN** 扫描器在读取模块内容前拒绝该成员，且不得把冲突降级为普通 unknown

### Requirement: BC profile capability 必须显式选择
每个成员 SHALL 标识 `source-preserving` 或 `build-faithful` profile 及其生成策略版本。请求 MUST 显式列出 required profiles；首期默认只要求 `source-preserving`。扫描器 MUST 分开统计和输出不同 profile facts，不得用一个 profile 冒充另一个，也不得因未请求的可选 profile 缺失降低整体状态。

#### Scenario: 默认 source-preserving 可用
- **WHEN** 请求未覆盖 required profiles 且每个计划 TU 都存在有效 `source-preserving` BC
- **THEN** 扫描器只规划该 profile 并可在其全部完成时满足 BC 消费分母

#### Scenario: build-faithful 未被请求
- **WHEN** artifact-set 不包含 `build-faithful` 且请求只要求 `source-preserving`
- **THEN** 结果记录该 capability 不可用，但不因此变为 `partial`

#### Scenario: 必需 profile 缺失
- **WHEN** 请求明确要求 `build-faithful` 而某个计划 TU 没有对应成员
- **THEN** 该 TU/profile 计入 failed 或 unknown，整体结果不得为 `complete`

### Requirement: artifact 规划和消费必须确定且无副作用
扫描器 SHALL 按 profile、physical TU ID、context ID 和 artifact key 的稳定顺序规划成员，并 SHALL 以只读方式处理。重复成员、同一身份指向不同摘要或相同摘要具有冲突元数据 MUST 被诊断；并发完成顺序不得改变 facts、diagnostics、semantic digest 或成员分母。

#### Scenario: 相同 manifest 重复扫描
- **WHEN** 同一 artifact-set 在不同本地 materialization 根和不同 worker 完成顺序下扫描
- **THEN** 规范化成员身份、事实语义摘要、诊断排序和分母完全一致

#### Scenario: 重复 artifact key 指向不同内容
- **WHEN** manifest 中相同 artifact key 对应两个不同 SHA-256
- **THEN** manifest 被视为冲突输入并在 worker 启动前拒绝
### Requirement: BC 不得裁剪 AST 分母
扫描器 SHALL 把共享 BC 作为按翻译单元关联的可选增强证据。无 BC 或部分 BC 时，全部合法 C/C++ compile entry 仍 SHALL 进入 AST 计划；缺少 BC 的单元 SHALL 继续执行 AST 规则并以双语诊断说明 IR evidence break。

#### Scenario: 零 BC
- **WHEN** 请求省略 `bitcode_artifact_set`
- **THEN** 扫描器完成 AST-only 分析

#### Scenario: 部分 BC
- **WHEN** artifact set 只覆盖部分翻译单元
- **THEN** 有 BC 的单元使用 AST+IR，其余单元保持 AST-only

**上游校验与项目分母契约**

### Requirement: consumer 只接收版本感知校验后的项目 BC 覆盖摘要
后端 SHALL 在把共享 BC 交给扫描器前按 manifest 2.0/2.1 原始字段集合校验 canonical identity，
并分别提供 raw command、C/C++ candidate、唯一项目 TU、produced、failed、missing 与 excluded
计数。CMake/compiler probe、链接/归档命令、重复上下文和根外基础设施条目不得进入扫描器的
项目 TU 分母。校验失败 SHALL 保留具体阶段和原因，同时允许合法 compile database 继续 AST-only。

#### Scenario: 旧 2.0 制品被新版后端消费
- **WHEN** 2.0 record 不含 2.1 的语言标准字段且原始摘要有效
- **THEN** 后端不得注入 null 后重算摘要，并可将有效项目 BC 交给扫描器
- **AND** `source-preserving` 仍不得被解释为 `build-faithful`
